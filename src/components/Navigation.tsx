import React from 'react';
import { FileAudio, Mic, Phone, Users, FolderOpen, Activity } from 'lucide-react';

export type NavTab = 'transcribe' | 'recordings' | 'calls' | 'speakers' | 'contexts' | 'activity';

interface NavigationProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

const TABS: { id: NavTab; label: string; icon: React.ComponentType<any> }[] = [
  { id: 'transcribe', label: 'Transcribe', icon: FileAudio },
  { id: 'recordings', label: 'Recordings', icon: Mic },
  { id: 'calls', label: 'Calls', icon: Phone },
  { id: 'speakers', label: 'Speakers', icon: Users },
  { id: 'contexts', label: 'Contexts', icon: FolderOpen },
  { id: 'activity', label: 'Activity', icon: Activity },
];

function Navigation({ activeTab, onTabChange }: NavigationProps) {
  return (
    <nav
      className="flex gap-1 bg-white/60 dark:bg-slate-800/60 backdrop-blur rounded-xl p-1 mb-6 border border-slate-200 dark:border-slate-700"
      aria-label="Main"
    >
      {TABS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          aria-current={activeTab === id ? 'page' : undefined}
          title={label}
          onClick={() => onTabChange(id)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all flex-1 justify-center ${
            activeTab === id
              ? 'bg-blue-500 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700'
          }`}
        >
          <Icon className="w-4 h-4" aria-hidden="true" />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default React.memo(Navigation);
