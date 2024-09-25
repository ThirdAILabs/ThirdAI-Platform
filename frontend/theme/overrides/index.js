import Input from './Input';
import Button from './Button';

export default function ComponentsOverrides(theme) {
  return Object.assign(Input(theme), Button(theme));
}
