import { render, screen } from '@testing-library/react';
import App from './App';

test('renders whisper transcription header', () => {
  render(<App />);
  const headerElement = screen.getByText(/Whisper Transcription/i);
  expect(headerElement).toBeInTheDocument();
});

test('renders file upload tab', () => {
  render(<App />);
  const uploadButton = screen.getByText(/Upload File/i);
  expect(uploadButton).toBeInTheDocument();
});

test('renders youtube url tab', () => {
  render(<App />);
  const youtubeButton = screen.getByText(/YouTube URL/i);
  expect(youtubeButton).toBeInTheDocument();
});
