import React, { useState } from 'react';
import styled from 'styled-components';
import SaveButton from './buttons/SaveButton';
import Teach from './Teach';
import { HiChevronLeft } from 'react-icons/hi';

const PanelContainer = styled.div<{ $isVisible: boolean }>`
  position: fixed;
  right: ${(props) => (props.$isVisible ? '0' : '-300px')};
  top: 0;
  width: 300px;
  height: 100%;
  background-color: white;
  box-shadow: -2px 0 5px rgba(0, 0, 0, 0.1);
  transition: right 0.3s ease-in-out;
  padding: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 25px;
`;

const TriggerIcon = styled.button<{ $isVisible: boolean }>`
  position: fixed;
  top: 40%;
  right: 20px;
  transform: translateY(-50%);
  cursor: pointer;
  background-color: rgb(16, 33, 150);
  border: none;
  border-radius: 8px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;

  &:hover {
    background-color: rgb(13, 27, 121);
  }

  svg {
    transition: transform 0.3s ease;
    transform: ${(props) => (props.$isVisible ? 'rotate(180deg)' : 'rotate(0)')};
  }
`;

const PanelTitle = styled.h2`
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 10px 0;
  padding-bottom: 15px;
  border-bottom: 1px solid #e0e0e0;
`;

const SectionContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 15px;
`;

const SectionTitle = styled.h3`
  font-size: 20px;
  font-weight: 600;
  margin: 0;
`;

const SectionContent = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const SectionText = styled.span`
  font-size: 16px;
  flex: 1;
  margin-right: 10px;
`;

const ButtonContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 48px;
  height: 48px;
`;

interface SidePanelProps {
  chatEnabled: boolean;
  cacheEnabled: boolean;
  setCacheEnabled: (enabled: boolean) => void;
  reRankingEnabled: boolean;
  setReRankingEnabled: (enabled: boolean) => void;
  onSaveClick: () => void;
}

const SidePanel: React.FC<SidePanelProps> = ({
  chatEnabled,
  cacheEnabled,
  setCacheEnabled,
  reRankingEnabled,
  setReRankingEnabled,
  onSaveClick,
}) => {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <>
      <TriggerIcon
        $isVisible={isVisible}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        <HiChevronLeft size={28} color="white" />
      </TriggerIcon>
      <PanelContainer
        $isVisible={isVisible}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        <PanelTitle>Advanced Configuration</PanelTitle>

        {chatEnabled && (
          <SectionContainer>
            <SectionTitle>LLM Cache</SectionTitle>
            <SectionContent>
              <SectionText>Enable cache for faster responses</SectionText>
              <div className="flex items-center">
                <button
                  onClick={() => setCacheEnabled(!cacheEnabled)}
                  className={`relative inline-flex items-center h-6 rounded-full w-11 transition-colors duration-300 focus:outline-none ${
                    cacheEnabled ? 'bg-[rgb(16,33,150)]' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`transform transition-transform duration-300 inline-block w-4 h-4 bg-white rounded-full ${
                      cacheEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </SectionContent>
          </SectionContainer>
        )}

        <SectionContainer>
          <SectionTitle>Re-ranking</SectionTitle>
          <SectionContent>
            <SectionText>Enable cross-encoder re-ranking</SectionText>
            <div className="flex items-center">
              <button
                onClick={() => setReRankingEnabled(!reRankingEnabled)}
                className={`relative inline-flex items-center h-6 rounded-full w-11 transition-colors duration-300 focus:outline-none ${
                  reRankingEnabled ? 'bg-[rgb(16,33,150)]' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`transform transition-transform duration-300 inline-block w-4 h-4 bg-white rounded-full ${
                    reRankingEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </SectionContent>
        </SectionContainer>

        <SectionContainer>
          <SectionTitle>Save Model</SectionTitle>
          <SectionContent>
            <SectionText>Save as a new model</SectionText>
            <ButtonContainer>
              <SaveButton onClick={onSaveClick} />
            </ButtonContainer>
          </SectionContent>
        </SectionContainer>

        <SectionContainer>
          <SectionTitle>Teach</SectionTitle>
          <SectionContent>
            <SectionText>Associate phrases to teach the model</SectionText>
            <ButtonContainer>
              <Teach />
            </ButtonContainer>
          </SectionContent>
        </SectionContainer>
      </PanelContainer>
    </>
  );
};

export default SidePanel;
