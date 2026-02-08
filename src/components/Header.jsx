import React from 'react';
import { FileAudio } from 'lucide-react';

function Header() {
  return (
    <header className="text-center mb-12">
      <div className="flex items-center justify-center gap-3 mb-4">
        <FileAudio className="w-10 h-10 text-blue-400" />
        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
          Whisper Transcription
        </h1>
      </div>
    </header>
  );
}

export default React.memo(Header);
