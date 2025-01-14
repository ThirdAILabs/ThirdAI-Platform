import React, { useState } from 'react';
import { InputLabel, Button, Autocomplete, TextField, Checkbox } from '@mui/material';
import RangeSlider from './Slider';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import CheckBoxIcon from '@mui/icons-material/CheckBox';

const icon = <CheckBoxOutlineBlankIcon fontSize="small" />;
const checkedIcon = <CheckBoxIcon fontSize="small" />;

interface MetaData {
  attributeName: string;
  attributeValue: {
    min: number;
    max: number;
  };
}

interface MetaDataProps {
  metadata: MetaData;
  handleSubmit: (props: { [key: string]: [] }) => void;
}

const MetadataRenderer: React.FC<MetaDataProps> = ({ metadata, handleSubmit }) => {
  const [selectedValues, setSelectedValues] = useState<any>({});

  const handleSliderChange = (event: any, value: number | number[], attributeName: string) => {
    setSelectedValues((prev: any) => ({
      ...prev,
      [attributeName]: value,
    }));
  };

  const handleAutocompleteChange = (event: any, value: string[], attributeName: string) => {
    setSelectedValues((prev: any) => ({
      ...prev,
      [attributeName]: value,
    }));
  };

  const onSubmit = () => {
    handleSubmit(selectedValues);
  };

  return (
    <div className="">
      {Object.entries(metadata).map(([attributeName, attributeValue]) => (
        <div key={attributeName} className="mb-4">
          <InputLabel className="block mb-2">{attributeName}</InputLabel>
          {Array.isArray(attributeValue) ? (
            <Autocomplete
              multiple
              id="checkboxes-tags-demo"
              options={attributeValue}
              disableCloseOnSelect
              getOptionLabel={(option) => option.toString()}
              value={selectedValues[attributeName] || []}
              onChange={(event, value) => handleAutocompleteChange(event, value, attributeName)}
              renderOption={(props, option, { selected }) => {
                const { key, ...optionProps } = props;
                return (
                  <li key={key} {...optionProps}>
                    <Checkbox
                      icon={icon}
                      checkedIcon={checkedIcon}
                      style={{ marginRight: 8 }}
                      checked={selected}
                    />
                    {option}
                  </li>
                );
              }}
              style={{ width: 500 }}
              renderInput={(params) => <TextField {...params} label={'Filter selected options'} />}
            />
          ) : attributeValue &&
            typeof attributeValue === 'object' &&
            !Array.isArray(attributeValue) ? (
            <div>
              <RangeSlider
                attributeName={attributeName}
                selectedValues={selectedValues}
                attributeValue={{
                  min: attributeValue.min,
                  max: attributeValue.max,
                }}
                handleSliderChange={handleSliderChange}
              />
            </div>
          ) : (
            <div>Unsupported data type for {attributeName}</div>
          )}
        </div>
      ))}
      <Button variant="contained" className="ml-[40%]" onClick={onSubmit}>
        Submit
      </Button>
    </div>
  );
};

export default MetadataRenderer;
