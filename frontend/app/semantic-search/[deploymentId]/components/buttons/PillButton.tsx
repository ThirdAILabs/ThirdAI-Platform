import styled from 'styled-components';
import { color, duration, fontSizes, shadow } from '../../stylingConstants';

const PillButton = styled.button`
  background-color: ${color.accent};
  color: white;
  font-size: ${fontSizes.s};
  border: none;
  padding: 10px 30px;
  border-radius: 30px;
  transition-duration: ${duration.transition};
  width: fit-content;

  &:hover {
    cursor: pointer;
    box-shadow: ${shadow.button};
  }
  &:active {
    background-color: ${color.accentDark};
  }
`;

export default PillButton;
