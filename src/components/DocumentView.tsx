import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronRight, BookOpen, StickyNote } from 'lucide-react';

interface DocumentSection {
  type: string;
  content: string;
  level?: number;
  page?: number;
  slide?: number;
}

interface DocumentViewProps {
  documentMarkdown?: string;
  documentSections?: DocumentSection[];
  speakerNotes?: DocumentSection[];
  sourceType?: string;
  pageCount?: number;
  slideCount?: number;
}

function DocumentView({
  documentMarkdown,
  documentSections = [],
  speakerNotes = [],
  sourceType = 'pdf',
  pageCount,
  slideCount,
}: DocumentViewProps) {
  const [expandedSections, setExpandedSections] = useState<Record<number, boolean>>({});
  const [showSpeakerNotes, setShowSpeakerNotes] = useState(true);

  const toggleSection = (index: number) => {
    setExpandedSections(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  // Group sections by page/slide
  const groupedSections = documentSections.reduce<Record<string, DocumentSection[]>>((acc, section) => {
    const key = sourceType === 'pptx'
      ? `Slide ${section.slide || 'N/A'}`
      : `Page ${section.page || 'N/A'}`;

    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(section);
    return acc;
  }, {});

  // Filter speaker notes from sections
  const notes = documentSections.filter(s => s.type === 'note');
  const contentSections = documentSections.filter(s => s.type !== 'note');

  const renderSection = (section: DocumentSection, index: string | number) => {
    const isHeading = section.type === 'heading' || section.type === 'title';
    const isList = section.type === 'list';
    const isTable = section.type === 'table';

    if (isHeading) {
      const headingClass = section.level === 1
        ? 'text-xl font-bold text-white'
        : section.level === 2
        ? 'text-lg font-semibold text-slate-200'
        : 'text-base font-medium text-slate-300';

      return (
        <div key={index} className={`mb-3 ${headingClass}`}>
          {section.content}
        </div>
      );
    }

    if (isList) {
      return (
        <div key={index} className="mb-2 pl-4 text-slate-300">
          <span className="text-blue-400 mr-2">•</span>
          {section.content}
        </div>
      );
    }

    if (isTable) {
      return (
        <div key={index} className="mb-4 p-3 bg-slate-700/50 rounded-lg font-mono text-sm overflow-x-auto">
          <pre className="text-slate-300">{section.content}</pre>
        </div>
      );
    }

    return (
      <p key={index} className="mb-3 text-slate-300 leading-relaxed">
        {section.content}
      </p>
    );
  };

  // If we have raw markdown but no sections, render the markdown
  if (documentMarkdown && contentSections.length === 0) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 max-h-[60vh] min-h-[16rem] overflow-y-auto">
        <div className="prose prose-invert prose-sm max-w-none">
          <pre className="whitespace-pre-wrap text-slate-300 font-sans text-sm leading-relaxed">
            {documentMarkdown}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Document info */}
      <div className="flex items-center gap-4 p-3 bg-slate-700/50 rounded-lg">
        <FileText className="w-5 h-5 text-orange-400" />
        <div className="flex items-center gap-4 text-sm">
          {sourceType === 'pptx' && slideCount && (
            <span className="text-slate-300">
              <span className="text-slate-500">Slides:</span> {slideCount}
            </span>
          )}
          {sourceType === 'pdf' && pageCount && (
            <span className="text-slate-300">
              <span className="text-slate-500">Pages:</span> {pageCount}
            </span>
          )}
        </div>
        {notes.length > 0 && (
          <button
            onClick={() => setShowSpeakerNotes(!showSpeakerNotes)}
            className={`ml-auto flex items-center gap-2 px-3 py-1 rounded-lg text-sm transition-colors ${
              showSpeakerNotes
                ? 'bg-amber-500 text-white'
                : 'bg-slate-600 text-slate-300 hover:bg-slate-500'
            }`}
          >
            <StickyNote className="w-4 h-4" />
            Speaker Notes
          </button>
        )}
      </div>

      {/* Main content */}
      <div className="bg-slate-900/50 rounded-xl p-4 max-h-[60vh] min-h-[16rem] overflow-y-auto">
        {Object.entries(groupedSections).length > 0 ? (
          Object.entries(groupedSections).map(([groupName, sections], groupIndex) => (
            <div key={groupIndex} className="mb-6">
              <button
                onClick={() => toggleSection(groupIndex)}
                className="flex items-center gap-2 text-slate-400 hover:text-slate-300 mb-3"
              >
                {expandedSections[groupIndex] === false ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
                <BookOpen className="w-4 h-4" />
                <span className="text-sm font-medium">{groupName}</span>
              </button>

              {expandedSections[groupIndex] !== false && (
                <div className="pl-6 border-l-2 border-slate-700">
                  {sections.filter(s => s.type !== 'note').map((section, index) =>
                    renderSection(section, `${groupIndex}-${index}`)
                  )}

                  {/* Speaker notes for this slide/page */}
                  {showSpeakerNotes && sections
                    .filter(s => s.type === 'note')
                    .map((note, noteIndex) => (
                      <div
                        key={`note-${noteIndex}`}
                        className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg"
                      >
                        <div className="flex items-center gap-2 text-amber-400 text-xs mb-1">
                          <StickyNote className="w-3 h-3" />
                          Speaker Notes
                        </div>
                        <p className="text-amber-200 text-sm">{note.content}</p>
                      </div>
                    ))
                  }
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No structured content available</p>
            <p className="text-sm">The document may not have extractable text</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(DocumentView);
