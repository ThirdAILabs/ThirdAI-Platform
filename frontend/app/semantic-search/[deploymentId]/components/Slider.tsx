import * as React from 'react';
import Box from '@mui/material/Box';
import Slider from '@mui/material/Slider';

interface RangeSliderProps {
  attributeName: string;
  selectedValues: Record<string, number[]>;
  attributeValue: { min: number; max: number };
  handleSliderChange: (event: Event, value: number | number[], attributeName: string) => void;
}

export default function RangeSlider({
  attributeName,
  selectedValues,
  attributeValue,
  handleSliderChange,
}: RangeSliderProps) {
  let value = [attributeValue.min, attributeValue.max];
  if (selectedValues[attributeName] !== undefined && selectedValues[attributeName] !== null)
    value = selectedValues[attributeName];

  return (
    <Box sx={{ width: '85%', marginLeft: '2%' }}>
      <Slider
        value={value}
        onChange={(event, newValue) => handleSliderChange(event, newValue, attributeName)}
        min={attributeValue.min}
        max={attributeValue.max}
        valueLabelDisplay="auto"
      />
    </Box>
  );
}
