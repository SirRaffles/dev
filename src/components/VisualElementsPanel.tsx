import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Image, BarChart2, GitBranch, Code, FileText, X, ZoomIn, ChevronLeft, ChevronRight } from 'lucide-react';
import { API_URL } from '../utils/api';

interface VisualElement {
  element_id?: string;
  type?: string;
  image_path?: string;
  description?: string;
  text_content?: string;
  page?: number;
  slide?: number;
  ocr_confidence?: number;
}

// Visual element type icons
const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  slide: FileText,
  chart: BarChart2,
  diagram: GitBranch,
  code: Code,
  table: FileText,
  image: Image,
  default: Image,
};

// Visual element type colors
const TYPE_COLORS: Record<string, string> = {
  slide: 'bg-blue-500',
  chart: 'bg-green-500',
  diagram: 'bg-purple-500',
  code: 'bg-orange-500',
  table: 'bg-cyan-500',
  image: 'bg-pink-500',
  default: 'bg-slate-500',
};

// Helper to get full image URL
const getImageUrl = (imagePath: string): string => {
  if (!imagePath) return '';
  // If it's already a full URL, return as-is
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
    return imagePath;
  }
  // If it's a data URL, return as-is
  if (imagePath.startsWith('data:')) {
    return imagePath;
  }
  // Prepend API_URL for relative paths
  return `${API_URL}${imagePath}`;
};

interface VisualElementsPanelProps {
  visualElements?: VisualElement[];
  className?: string;
}

function VisualElementsPanel({
  visualElements = [],
  className = '',
}: VisualElementsPanelProps) {
  const [selectedElement, setSelectedElement] = useState<VisualElement | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());
  const lightboxRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const closeLightbox = useCallback(() => {
    setLightboxIndex(null);
    // Restore focus to the element that opened the lightbox
    if (previousFocusRef.current) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, []);

  const navigateLightbox = useCallback((direction: number) => {
    setLightboxIndex((prev) => {
      if (prev === null) return null;
      const newIndex = prev + direction;
      if (newIndex >= 0 && newIndex < visualElements.length) return newIndex;
      return prev;
    });
  }, [visualElements.length]);

  // Keyboard navigation for lightbox
  useEffect(() => {
    if (lightboxIndex === null) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          closeLightbox();
          break;
        case 'ArrowLeft':
          navigateLightbox(-1);
          break;
        case 'ArrowRight':
          navigateLightbox(1);
          break;
        case 'Tab': {
          const container = lightboxRef.current;
          if (!container) break;
          const focusable = container.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
          if (focusable.length === 0) break;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (e.shiftKey) {
            if (document.activeElement === first) {
              e.preventDefault();
              last.focus();
            }
          } else {
            if (document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
          break;
        }
        default:
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    // Focus the lightbox container for screen readers
    if (lightboxRef.current) lightboxRef.current.focus();

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [lightboxIndex, closeLightbox, navigateLightbox]);

  if (visualElements.length === 0) {
    return (
      <div className={`bg-slate-900/50 rounded-xl p-6 text-center ${className}`}>
        <Image className="w-12 h-12 mx-auto mb-3 text-slate-500 opacity-50" />
        <p className="text-slate-500">No visual elements extracted</p>
        <p className="text-sm text-slate-600">
          Charts, diagrams, and images will appear here when detected
        </p>
      </div>
    );
  }

  const getIcon = (type?: string) => {
    const Icon = TYPE_ICONS[type || 'default'] || TYPE_ICONS.default;
    return Icon;
  };

  const getColor = (type?: string) => {
    return TYPE_COLORS[type || 'default'] || TYPE_COLORS.default;
  };

  const openLightbox = (index: number) => {
    previousFocusRef.current = document.activeElement as HTMLElement;
    setLightboxIndex(index);
  };

  const handleElementClick = (element: VisualElement, index: number) => {
    setSelectedElement(element);

    // If element has an image, open lightbox
    if (element.image_path) {
      openLightbox(index);
    }
  };

  return (
    <div className={className}>
      {/* Element grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4" role="list" aria-label="Visual elements">
        {visualElements.map((element, index) => {
          const Icon = getIcon(element.type);
          const colorClass = getColor(element.type);

          return (
            <div
              key={element.element_id || index}
              role="listitem"
              tabIndex={0}
              aria-label={`${element.type || 'Visual'} element${element.page ? `, page ${element.page}` : ''}${element.slide ? `, slide ${element.slide}` : ''}: ${element.description || 'No description'}`}
              onClick={() => handleElementClick(element, index)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleElementClick(element, index); } }}
              className={`relative bg-slate-800 rounded-lg overflow-hidden cursor-pointer transition-all hover:ring-2 hover:ring-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none ${
                selectedElement?.element_id === element.element_id
                  ? 'ring-2 ring-blue-400'
                  : ''
              }`}
            >
              {/* Image preview or placeholder */}
              {element.image_path ? (
                <div className="aspect-video bg-slate-900 flex items-center justify-center">
                  {imageErrors.has(index) ? (
                    <Icon className="w-8 h-8 text-slate-500" />
                  ) : (
                    <img
                      src={getImageUrl(element.image_path)}
                      alt={element.description || 'Visual element'}
                      className="w-full h-full object-cover"
                      onError={() => {
                        setImageErrors((prev) => new Set(prev).add(index));
                      }}
                    />
                  )}
                </div>
              ) : (
                <div className="aspect-video bg-slate-900 flex items-center justify-center">
                  <Icon className="w-8 h-8 text-slate-500" />
                </div>
              )}

              {/* Type badge */}
              <div className={`absolute top-2 left-2 px-2 py-0.5 rounded text-xs text-white ${colorClass}`}>
                {element.type || 'unknown'}
              </div>

              {/* Zoom icon */}
              {element.image_path && (
                <div className="absolute top-2 right-2 p-1 bg-black/50 rounded">
                  <ZoomIn className="w-4 h-4 text-white" />
                </div>
              )}

              {/* Info */}
              <div className="p-3">
                {(element.slide || element.page) && (
                  <p className="text-xs text-slate-500 mb-1">
                    {element.slide ? `Slide ${element.slide}` : `Page ${element.page}`}
                  </p>
                )}
                <p className="text-sm text-slate-300 line-clamp-2">
                  {element.description || element.text_content || 'No description'}
                </p>
                {element.ocr_confidence !== undefined && element.ocr_confidence > 0 && (
                  <div className="mt-2 flex items-center gap-1">
                    <div className="flex-1 bg-slate-700 rounded-full h-1">
                      <div
                        className="bg-blue-500 h-1 rounded-full"
                        style={{ width: `${element.ocr_confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500">
                      {Math.round(element.ocr_confidence * 100)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Lightbox modal */}
      {lightboxIndex !== null && visualElements[lightboxIndex] && (
        <div
          ref={lightboxRef}
          role="dialog"
          aria-modal="true"
          aria-label={`Viewing ${visualElements[lightboxIndex].type || 'visual'} element ${lightboxIndex + 1} of ${visualElements.length}`}
          tabIndex={-1}
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center focus:outline-none"
          onClick={closeLightbox}
        >
          {/* Close button */}
          <button
            onClick={closeLightbox}
            aria-label="Close lightbox"
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-white" />
          </button>

          {/* Navigation buttons */}
          {lightboxIndex > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); navigateLightbox(-1); }}
              aria-label="Previous element"
              className="absolute left-4 p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ChevronLeft className="w-6 h-6 text-white" />
            </button>
          )}
          {lightboxIndex < visualElements.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); navigateLightbox(1); }}
              aria-label="Next element"
              className="absolute right-4 p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ChevronRight className="w-6 h-6 text-white" />
            </button>
          )}

          {/* Content */}
          <div
            className="max-w-4xl max-h-[80vh] flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            {visualElements[lightboxIndex].image_path && (
              <img
                src={getImageUrl(visualElements[lightboxIndex].image_path!)}
                alt={visualElements[lightboxIndex].description || 'Visual element'}
                className="max-w-full max-h-[60vh] object-contain rounded-lg"
              />
            )}
            <div className="mt-4 max-w-2xl text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <span className={`px-2 py-0.5 rounded text-xs text-white ${getColor(visualElements[lightboxIndex].type)}`}>
                  {visualElements[lightboxIndex].type}
                </span>
                {visualElements[lightboxIndex].slide && (
                  <span className="text-sm text-slate-400">
                    Slide {visualElements[lightboxIndex].slide}
                  </span>
                )}
                {visualElements[lightboxIndex].page && (
                  <span className="text-sm text-slate-400">
                    Page {visualElements[lightboxIndex].page}
                  </span>
                )}
              </div>
              <p className="text-slate-300">
                {visualElements[lightboxIndex].description}
              </p>
              {visualElements[lightboxIndex].text_content && (
                <p className="mt-2 text-sm text-slate-400 italic">
                  "{visualElements[lightboxIndex].text_content}"
                </p>
              )}
            </div>
            <p className="mt-4 text-xs text-slate-500">
              {lightboxIndex + 1} of {visualElements.length}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default React.memo(VisualElementsPanel);
