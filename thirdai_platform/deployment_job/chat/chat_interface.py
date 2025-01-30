import logging
from abc import ABC, abstractmethod
from threading import Lock
from typing import AsyncGenerator, List, Union

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
        db: Union[ndb.NeuralDB, ndbv2.NeuralDB, ndbv2.FastDB],
        chat_history_sql_uri: str,
        top_k: int = 5,
        chat_prompt: str = "Answer the user's questions based on the below context:",
        query_reformulation_prompt: str = "Given the above conversation, generate a search query that would help retrieve relevant sources for responding to the last message.",
        **kwargs,
    ):
        self.chat_history_sql_uri = chat_history_sql_uri
        if isinstance(db, ndb.NeuralDB):
            vectorstore = NeuralDBVectorStore(db)
        elif isinstance(db, ndbv2.NeuralDB) or isinstance(db, ndbv2.FastDB):
            vectorstore = NeuralDBV2VectorStore(db)
        else:
            raise ValueError(f"Cannot support db of type {type(db)}")

        retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

        query_transform_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                (
                    "user",
                    query_reformulation_prompt,
                ),
            ]
        )

        query_transforming_retriever_chain = RunnableBranch(
            (
                lambda x: len(x.get("messages", [])) == 1,
                # If only one message, then we just pass that message's content to retriever
                (lambda x: x["messages"][-1].content) | retriever,
            ),
            # If messages, then we pass inputs to LLM chain to transform the query, then pass to retriever
            query_transform_prompt | self.llm() | StrOutputParser() | retriever,
        ).with_config(run_name="chat_retriever_chain")

        question_answering_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    chat_prompt + "\n\n{context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        document_chain = create_stuff_documents_chain(
            self.llm(), question_answering_prompt
        )

        self.conversational_retrieval_chain = RunnablePassthrough.assign(
            context=query_transforming_retriever_chain
            | ChatInterface.parse_retriever_output,
        ).assign(
            answer=document_chain,
        )

        self.history_lock = Lock()

    @abstractmethod
    def llm(self) -> LLM:
        raise NotImplementedError()

    @staticmethod
    def parse_retriever_output(documents: List[Document]):
        top_k_docs = documents

        # The chatbot currently doesn't utilize any metadata, so we delete it to save memory
        for doc in top_k_docs:
            doc.metadata = {}

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
        chat_history_list = [
            {
                "content": message.content,
                "sender": "AI" if isinstance(message, AIMessage) else "human",
            }
            for message in chat_history.messages
        ]
        return chat_history_list

    def chat(self, user_input: str, session_id: str, **kwargs):
        chat_history = self._get_chat_history_conn(session_id=session_id)
        chat_history.add_user_message(user_input)
        response = self.conversational_retrieval_chain.invoke(
            {"messages": chat_history.messages}
        )
        chat_history.add_ai_message(response["answer"])

        return response["answer"]

    async def stream_chat(
        self, user_input: str, session_id: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        chat_history = self._get_chat_history_conn(session_id=session_id)
        chat_history.add_user_message(user_input)

        response_chunks = []
        async for chunk in self.conversational_retrieval_chain.astream(
            {"messages": chat_history.messages}
        ):
            if "answer" in chunk:
                response_chunks.append(chunk["answer"])
                yield chunk["answer"]

        full_response = "".join(response_chunks)
        chat_history.add_ai_message(full_response)
