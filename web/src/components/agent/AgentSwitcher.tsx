import React, { useState, useRef, useEffect, useMemo } from 'react';

import { useTranslation } from 'react-i18next';

import { Bot, ChevronDown, Check } from 'lucide-react';

import {
  useDefinitions,
  useListDefinitions,
} from '@/stores/agentDefinitions';

export interface AgentSwitcherProps {
  activeAgentId?: string | undefined;
  onSelect: (agentId: string) => void;
  className?: string | undefined;
}

export const AgentSwitcher: React.FC<AgentSwitcherProps> = ({
  activeAgentId,
  onSelect,
  className = '',
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const definitions = useDefinitions();
  const listDefinitions = useListDefinitions();

  useEffect(() => {
    if (definitions.length === 0) {
      listDefinitions().catch((err: unknown) => {
        console.error('Failed to load agent definitions', err);
      });
    }
  }, [definitions.length, listDefinitions]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const enabledDefinitions = useMemo(() => {
    return definitions.filter((d) => d.enabled);
  }, [definitions]);

  const activeAgent = useMemo(() => {
    if (!activeAgentId) return null;
    return definitions.find((d) => d.id === activeAgentId) || null;
  }, [definitions, activeAgentId]);

  return (
    <div className={`relative inline-block ${className}`} ref={containerRef}>
      <button
        type="button"
        onClick={() => { setIsOpen(!isOpen); }}
        className="flex items-center gap-1.5 px-2 py-1 text-sm font-medium rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <Bot size={16} className="text-blue-500" />
        <span className="max-w-[150px] truncate">
          {activeAgent
            ? activeAgent.display_name || activeAgent.name
            : t('agent.selectAgent', 'Select Agent')}
        </span>
        <ChevronDown
          size={14}
          className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg z-50 overflow-hidden">
          <div
            className="max-h-80 overflow-y-auto p-1"
            role="listbox"
            aria-label={t('agent.availableAgents', 'Available Agents')}
          >
            {enabledDefinitions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-slate-500 dark:text-slate-400 italic text-center">
                {t('agent.noAgentsAvailable', 'No agents available')}
              </div>
            ) : (
              enabledDefinitions.map((agent) => {
                const isSelected = agent.id === activeAgentId;
                return (
                  <button
                    key={agent.id}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => {
                      onSelect(agent.id);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 flex items-center justify-between rounded-md text-sm transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                        : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700'
                    }`}
                  >
                    <div className="flex flex-col overflow-hidden mr-2">
                      <span className="font-medium truncate">
                        {agent.display_name || agent.name}
                      </span>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span
                          className={`text-[10px] leading-none px-1.5 py-0.5 rounded-sm border ${
                            agent.source === 'database'
                              ? 'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-900/20 dark:text-purple-400 dark:border-purple-800/50'
                              : 'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800/50'
                          }`}
                        >
                          {agent.source === 'database' ? 'DB' : 'System'}
                        </span>
                        <span className="text-[10px] leading-none text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          {t('agent.enabled', 'Enabled')}
                        </span>
                      </div>
                    </div>
                    {isSelected && (
                      <Check size={16} className="text-blue-600 dark:text-blue-400 shrink-0" />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
