import React, { useRef } from 'react';
import styled from 'styled-components';
import { borderRadius, color, duration, fontSizes } from '../stylingConstants';

const SearchTextArea = styled.textarea`
  background-color: ${color.textInput};
  width: 80%;
  font-size: ${fontSizes.m};
  padding: 10px 10px 13px 10px;
  border-radius: ${borderRadius.textInput};
  outline: none;
  border: none;
  transition-duration: ${duration.transition};
  height: 100px;
  resize: none;
  font-family: Helvetica, Arial, sans-serif;
`;

interface SearchTextInputProps {
  placeholder: string;
  onSubmit: () => void;
  value: string;
  setValue: (value: string) => void;
}

export default function SearchTextInput({
  placeholder,
  onSubmit,
  value,
  setValue,
}: SearchTextInputProps) {
  const searchTextInputRef = useRef<HTMLTextAreaElement>(null);
  function onSearchEnterPress(e: any) {
    if (e.keyCode === 13 && e.shiftKey === false) {
      e.preventDefault();
      searchTextInputRef.current!.blur();
      onSubmit();
    }
  }

  return (
    <SearchTextArea
      ref={searchTextInputRef}
      placeholder={placeholder}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={onSearchEnterPress}
      onBlur={() => {
        searchTextInputRef.current!.scrollTop = 0;
      }}
    />
  );
}
