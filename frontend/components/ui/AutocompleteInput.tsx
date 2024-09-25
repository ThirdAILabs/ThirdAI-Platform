import { TextField } from '@mui/material';
import React, { useState, ChangeEvent } from 'react';

interface AutocompleteInputProps {
  value: string | string[];
  onChange: (value: string | string[]) => void;
  options: string[];
  multiple?: boolean;
  placeholder?: string;
}

const AutocompleteInput: React.FC<AutocompleteInputProps> = ({
  value,
  onChange,
  options,
  multiple = false,
  placeholder = '',
}) => {
  const [inputValue, setInputValue] = useState<string>(typeof value === 'string' ? value : '');
  const [filteredOptions, setFilteredOptions] = useState<string[]>([]);

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const input = e.target.value;
    setInputValue(input);

    const filtered = options.filter((option) => option.toLowerCase().includes(input.toLowerCase()));
    setFilteredOptions(filtered);
  };

  const handleOptionClick = (option: string) => {
    if (multiple && Array.isArray(value)) {
      if (!value.includes(option)) {
        onChange([...value, option]);
      }
      setInputValue('');
    } else {
      onChange(option);
      setInputValue(option); // Update the input value with the selected option
    }
    setFilteredOptions([]);
  };

  const handleRemove = (optionToRemove: string) => {
    if (multiple && Array.isArray(value)) {
      onChange(value.filter((option) => option !== optionToRemove));
    }
  };

  return (
    <div className="relative">
      <TextField
        type="text"
        value={multiple && Array.isArray(value) ? inputValue : inputValue}
        onChange={handleInputChange}
        placeholder={placeholder}
        className="w-full"
        // className="border border-gray-300 rounded px-2 py-1 mb-2 w-full"
      />
      {filteredOptions.length > 0 && (
        <ul className="absolute z-10 bg-white border border-gray-300 rounded shadow-md w-full max-h-40 overflow-y-auto">
          {filteredOptions.map((option, index) => (
            <li
              key={index}
              onClick={() => handleOptionClick(option)}
              className="px-2 py-1 hover:bg-blue-500 hover:text-white cursor-pointer"
            >
              {option}
            </li>
          ))}
        </ul>
      )}
      {multiple && Array.isArray(value) && value.length > 0 && (
        <div className="flex flex-wrap mt-2">
          {value.map((option, index) => (
            <div
              key={index}
              className="bg-blue-500 text-white px-2 py-1 rounded mr-2 mb-2 flex items-center"
            >
              {option}
              <button onClick={() => handleRemove(option)} className="ml-2 text-sm text-red-500">
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AutocompleteInput;
