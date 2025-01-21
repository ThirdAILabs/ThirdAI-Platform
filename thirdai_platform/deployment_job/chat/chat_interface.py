import json
import logging
from abc import ABC, abstractmethod

pass
import os
from threading import Lock
from typing import AsyncGenerator, Dict, List, Optional, Union

from deployment_job.chat.ndbv2_vectorstore import NeuralDBV2VectorStore
from fastapi import HTTPException, status
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.docstore.document import Document
from langchain.vectorstores import NeuralDBVectorStore
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.language_models.llms import LLM
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnablePassthrough
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2


class ChatInterface(ABC):
    def __init__(
        self,
        db: Union[ndb.NeuralDB, ndbv2.NeuralDB],
        chat_history_sql_uri: str,
        top_k: int = 5,
        chat_prompt: str = "Answer the user's questions based on the below context:",
        query_reformulation_prompt: str = "Given the above conversation, generate a search query that would help retrieve relevant sources for responding to the last message.",
        **kwargs,
    ):
        self.chat_history_sql_uri = chat_history_sql_uri
        self.top_k = top_k
        self.query_categories = set()

        # Store vectorstore
        if isinstance(db, ndb.NeuralDB):
            self.vectorstore = NeuralDBVectorStore(db)
        elif isinstance(db, ndbv2.NeuralDB):
            self.vectorstore = NeuralDBV2VectorStore(db)
        else:
            raise ValueError(f"Cannot support db of type {type(db)}")

        # Store prompts
        self.query_transform_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("user", query_reformulation_prompt),
            ]
        )

        # reformulation prompts
        self.query_transformation_chain = RunnableBranch(
            (
                lambda x: len(x.get("messages", [])) == 1,
                (lambda x: x["messages"][-1].content),
            ),
            self.query_transform_prompt | self.llm() | StrOutputParser(),
        )

        self.question_answering_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", chat_prompt + "\n\n{context}"),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # query categorization prompt
        self.query_categorization_prompt = (
            ChatPromptTemplate(
                [
                    (
                        "system",
                        "**Your task is to categorize the given query into one of the following predefined categories:**\n\n"
                        "{categories}\n\n"
                        "If none of the provided categories are appropriate for the query, create a new general category.\n\n"
                        "***Only output the category name.***",
                    ),
                    ("user", "{query}"),
                ]
            )
            | self.llm()
            | StrOutputParser()
        )

        # Store document chain
        self.document_chain = create_stuff_documents_chain(
            self.llm(), self.question_answering_prompt
        )

        self.history_lock = Lock()

    @abstractmethod
    def llm(self) -> LLM:
        raise NotImplementedError()

    def categorize_query(self, user_input: str):
        response: str = self.query_categorization_prompt.invoke(
            {"categories": ", ".join(self.query_categories), "query": user_input}
        )
        category = response.lower()
        self.query_categories.add(category)
        return category

    @staticmethod
    def parse_retriever_output(documents: List[Document]):
        top_k_docs = documents

        print("top_k_docs", top_k_docs, flush=True)

        # The chatbot currently doesn't utilize any metadata, so we delete it to save memory
        for doc in top_k_docs:
            doc.metadata["metadata"] = None

        return top_k_docs

    def _get_chat_history_conn(self, session_id: str):
        # The lock is to prevent table already exists errors if the method is called
        # twice in succession and both connections attempt to create the table.
        try:
            with self.history_lock:
                chat_history = SQLChatMessageHistory(
                    session_id=session_id, connection_string=self.chat_history_sql_uri
                )
            return chat_history
        except Exception as err:
            logging.error(
                "Error connecting to sql database to store chat history: " + err
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error connecting to sql database to store chat history",
            )

    def get_chat_history(self, session_id: str, **kwargs):
        chat_history = self._get_chat_history_conn(session_id=session_id)
        chat_history_list = []

        for message in chat_history.messages:
            message_dict = {
                "content": message.content,
                "sender": "AI" if isinstance(message, AIMessage) else "human",
            }

            # Add references if they exist in additional_kwargs
            if isinstance(message, AIMessage) and message.additional_kwargs.get(
                "references"
            ):
                message_dict["references"] = message.additional_kwargs["references"]

            chat_history_list.append(message_dict)

        return chat_history_list

    async def chat(
        self,
        user_input: str,
        session_id: str,
        constraints: Optional[Dict[str, Dict[str, str]]] = None,
        **kwargs,
    ):
        chat_history = self._get_chat_history_conn(session_id=session_id)
        chat_history.add_user_message(user_input)

        retriever = self.vectorstore.as_retriever(
            search_kwargs=(
                {"k": self.top_k, "constraints": constraints}
                if constraints
                else {"k": self.top_k}
            )
        )

        self.conversational_retrieval_chain = RunnablePassthrough.assign(
            context=self.query_transformation_chain
            | retriever
            | self.parse_retriever_output,
        ).assign(
            answer=self.document_chain,
        )

        response = await self.conversational_retrieval_chain.ainvoke(
            {"messages": chat_history.messages}
        )
        chat_history.add_ai_message(response["answer"])
        return response["answer"]

    def get_retriever(self, constraints=None):
        search_kwargs = {"k": self.top_k, "constraints": constraints}
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)

    async def stream_chat(
        self,
        user_input: str,
        session_id: str,
        document_path_prefix: str,
        constraints: Optional[Dict[str, Dict[str, str]]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        chat_history = self._get_chat_history_conn(session_id=session_id)
        chat_history.add_user_message(user_input)

        retriever = self.get_retriever(constraints)

        self.conversational_retrieval_chain = RunnablePassthrough.assign(
            context=self.query_transformation_chain
            | retriever
            | self.parse_retriever_output,
        ).assign(
            answer=self.document_chain,
        )

        response_chunks = []
        context_info = None

        async for chunk in self.conversational_retrieval_chain.astream(
            {"messages": chat_history.messages}
        ):
            if "answer" in chunk:
                response_chunks.append(chunk["answer"])
                yield chunk["answer"]
            elif "context" in chunk:
                context = [
                    {
                        "chunk_id": doc.metadata["chunk_id"],
                        "query": doc.metadata["query"],
                        "sourceURL": os.path.join(
                            str(document_path_prefix), doc.metadata["document"]
                        ),
                        "sourceName": doc.metadata["document"].split("/")[-1],
                        "content": doc.page_content,
                        "metadata": doc.metadata.get("metadata", {}),
                    }
                    for doc in chunk["context"]
                ]
                context_info = context  # Store context for later use
                yield "context: " + json.dumps(context)

        full_response = "".join(response_chunks)

        # Create AIMessage with additional metadata
        ai_message = AIMessage(
            content=full_response, additional_kwargs={"references": context_info}
        )

        # Add the enhanced message to chat history
        chat_history.add_message(ai_message)
