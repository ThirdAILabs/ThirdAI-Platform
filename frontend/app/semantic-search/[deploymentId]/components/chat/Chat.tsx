import React, { useContext, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes, padding } from '../../stylingConstants';
import { ModelServiceContext } from '../../Context';
import { ChatMessage, ModelService } from '../../modelServices';
import TypingAnimation from '../TypingAnimation';

const ChatContainer = styled.section`
  position: fixed;
  width: 60%;
  left: 10%;
  display: flex;
  flex-direction: column;
  justify-content: end;
  z-index: 100;
  height: 100%;
  font-family: Helvetica, Arial, sans-serif;
`;

const ChatBoxContainer = styled.section`
  /* border-bottom: solid 1px black; */
  padding: 15px 15px 0 15px;
`;

const ChatBoxSender = styled.section`
  font-size: ${fontSizes.l};
  font-weight: bold;
  color: ${color.accent};
`;

const ChatBoxContent = styled.section`
  font-size: ${fontSizes.m};
  padding-bottom: 15px;
`;

const TypingAnimationContainer = styled.section`
  padding: ${padding.card} 0 7px 0;
`;

function ChatBox({ message }: { message: ChatMessage }) {
  return (
    <ChatBoxContainer>
      <ChatBoxSender>{message.sender === 'human' ? '👋 You' : '🤖 AI'}</ChatBoxSender>
      <ChatBoxContent>
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </ChatBoxContent>
    </ChatBoxContainer>
  );
}

function AILoadingChatBox() {
  return (
    <ChatBoxContainer>
      <ChatBoxSender>🤖 AI</ChatBoxSender>
      <TypingAnimationContainer>
        <TypingAnimation />
      </TypingAnimationContainer>
    </ChatBoxContainer>
  );
}

const ChatBar = styled.textarea`
  background-color: ${color.textInput};
  /* width: 100%; */
  font-size: ${fontSizes.m};
  padding: 20px 20px 27px 20px;
  margin: 10px 0 50px 0%;
  border-radius: ${borderRadius.textInput};
  outline: none;
  border: none;
  transition-duration: ${duration.transition};
  height: ${fontSizes.xl};
  resize: none;
  font-family: Helvetica, Arial, sans-serif;

  &:focus {
    height: 100px;
    transition-duration: ${duration.transition};
  }
`;

const ScrollableArea = styled.section`
  overflow-y: scroll;
  display: flex;
  flex-direction: column-reverse;
  height: 80%;
`;

const AllChatBoxes = styled.section``;

const Placeholder = styled.section`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  font-size: ${fontSizes.l};
  height: 80%;
`;

export default function Chat(props: any) {
  const modelService = useContext<ModelService | null>(ModelServiceContext);

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [textInput, setTextInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const scrollableAreaRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    modelService?.getChatHistory().then(setChatHistory);
  }, []);

  function onEnterPress(e: any) {
    if (e.keyCode === 13 && e.shiftKey === false) {
      e.preventDefault();
      if (aiLoading) {
        return;
      }
      if (!textInput.trim()) {
        return;
      }
      console.log(scrollableAreaRef.current?.scrollTop);
      if (scrollableAreaRef.current) {
        scrollableAreaRef.current.scrollTop = 0;
      }
      const lastTextInput = textInput;
      const lastChatHistory = chatHistory;
      setAiLoading(true);
      setChatHistory((history) => [...history, { sender: 'human', content: textInput }]);
      setTextInput('');
      modelService
        ?.chat(textInput)
        .then(({ response }) => {
          setChatHistory((history) => [...history, { sender: 'AI', content: response }]);
          setAiLoading(false);
        })
        .catch((_) => {
          alert('Failed to send chat. Please try again.');
          setChatHistory(lastChatHistory);
          setTextInput(lastTextInput);
          setAiLoading(false);
        });
    }
  }

  return (
    <ChatContainer>
      <ScrollableArea ref={scrollableAreaRef}>
        {chatHistory.length ? (
          <AllChatBoxes>
            {chatHistory.map((message, i) => (
              <ChatBox key={i} message={message} />
            ))}
            {aiLoading && <AILoadingChatBox />}
          </AllChatBoxes>
        ) : (
          <Placeholder> Ask anything to start chatting! </Placeholder>
        )}
      </ScrollableArea>
      <ChatBar
        placeholder="Ask anything..."
        onKeyDown={onEnterPress}
        value={textInput}
        onChange={(e) => setTextInput(e.target.value)}
      />
    </ChatContainer>
  );
}
