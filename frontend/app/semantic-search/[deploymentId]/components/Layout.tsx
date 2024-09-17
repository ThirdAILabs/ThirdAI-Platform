import { styled } from 'styled-components';

export const Spacer = styled.section<{ $height?: string; $width?: string }>`
  height: ${(props) => props.$height ?? '0'};
  width: ${(props) => props.$width ?? '0'};
`;

export const Pad = styled.section<{
  $left?: string;
  $right?: string;
  $top?: string;
  $bottom?: string;
}>`
  padding-left: ${(props) => props.$left ?? '0'};
  padding-right: ${(props) => props.$right ?? '0'};
  padding-top: ${(props) => props.$top ?? '0'};
  padding-bottom: ${(props) => props.$bottom ?? '0'};
`;
