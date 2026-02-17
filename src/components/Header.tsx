import React from 'react';
import { FileAudio } from 'lucide-react';

function Header() {
  return (
    <header className="text-center mb-12">
      <div className="flex items-center justify-center gap-3 mb-4">
        <FileAudio className="w-8 h-8 sm:w-10 sm:h-10 text-blue-400" aria-hidden="true" />
        <h1 className="text-2xl sm:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
          Davrine Transcription
        </h1>
      </div>
    </header>
  );
}

export default React.memo(Header);
