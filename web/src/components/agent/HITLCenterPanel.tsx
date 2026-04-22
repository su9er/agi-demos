/**
 * HITLCenterPanel — Track B P2-3 phase-2 (b-fe-hitl-center).
 *
 * Centralized list of pending HITL requests for a conversation with
 * category / request-type / visibility badges. Reuses the existing
 * ``/agent/hitl/conversations/{id}/pending`` endpoint for now; once
 * the new ``pending_reviews`` table (from ``b-hitl-policy``) is
 * exposed it can be swapped in without UI changes.
 *
 * Agent First note: the UI only *displays* what the backend classified
 * (``request_type``, ``metadata.category`` / ``metadata.visibility``).
 * It never classifies content itself.
 */

import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { restApi } from '../../services/agent/restApi';
import type { HITLRequestFromApi } from '../../types/hitl.unified';

export interface HITLCenterPanelProps {
  conversationId: string | null;
  onSelectRequest?: (requestId: string) => void;
  className?: string;
  autoRefreshMs?: number;
}

type FilterType = 'all' | 'clarification' | 'decision' | 'env_var';

const filterOptions: FilterType[] = ['all', 'clarification', 'decision', 'env_var'];

const badgeBase =
  'inline-flex h-[18px] items-center rounded-full border border-[rgba(0,0,0,0.08)] bg-[#ebebeb] px-2 text-[11px] font-medium text-[#171717]';

function getMetaString(metadata: Record<string, unknown> | undefined, key: string): string | null {
  if (!metadata) return null;
  const v = metadata[key];
  return typeof v === 'string' ? v : null;
}

export const HITLCenterPanel = memo<HITLCenterPanelProps>(
  ({ conversationId, onSelectRequest, className, autoRefreshMs = 5000 }) => {
    const { t } = useTranslation();
    const [requests, setRequests] = useState<HITLRequestFromApi[]>([]);
    const [filter, setFilter] = useState<FilterType>('all');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const fetchPending = useCallback(async () => {
      if (!conversationId) {
        setRequests([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const requestType = filter === 'all' ? undefined : filter;
        const resp = await restApi.getPendingHITLRequests(conversationId, requestType);
        setRequests(resp.requests ?? []);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setLoading(false);
      }
    }, [conversationId, filter]);

    useEffect(() => {
      void fetchPending();
      if (!conversationId || !autoRefreshMs) return;
      const id = setInterval(() => {
        void fetchPending();
      }, autoRefreshMs);
      return () => clearInterval(id);
    }, [fetchPending, conversationId, autoRefreshMs]);

    const visible = useMemo(() => requests, [requests]);

    if (!conversationId) return null;

    return (
      <aside
        className={className}
        data-testid="hitl-center-panel"
        aria-label={t('agent.hitl.center.aria', { defaultValue: 'Pending HITL requests' })}
      >
        <header className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-[#666]">
            {t('agent.hitl.center.title', { defaultValue: 'HITL Center' })}
            {visible.length > 0 && (
              <span className="ml-2 rounded-full bg-[#171717] px-1.5 text-[10px] font-medium text-white">
                {visible.length}
              </span>
            )}
          </h3>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterType)}
            className="h-[26px] rounded border border-[rgba(0,0,0,0.08)] bg-white px-2 text-xs text-[#171717]"
            aria-label={t('agent.hitl.center.filterAria', {
              defaultValue: 'Filter by HITL type',
            })}
          >
            {filterOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </header>

        {loading && visible.length === 0 && (
          <p className="text-sm text-[#666]">
            {t('agent.hitl.center.loading', { defaultValue: 'Loading...' })}
          </p>
        )}

        {error && (
          <p className="text-sm text-[#ee0000]">
            {t('agent.hitl.center.error', { defaultValue: 'Failed to load HITL requests' })}
          </p>
        )}

        {!loading && !error && visible.length === 0 && (
          <p className="text-sm text-[#999]">
            {t('agent.hitl.center.empty', { defaultValue: 'No pending requests.' })}
          </p>
        )}

        <ul className="space-y-2">
          {visible.map((req) => {
            const category = getMetaString(req.metadata, 'category');
            const visibility = getMetaString(req.metadata, 'visibility');
            return (
              <li
                key={req.id}
                className="cursor-pointer rounded-md border border-[rgba(0,0,0,0.08)] bg-white px-3 py-2 hover:border-[#0070f3]"
                onClick={() => onSelectRequest?.(req.id)}
              >
                <div className="mb-1 flex items-center gap-1">
                  <span className={badgeBase} data-testid="hitl-type-badge">
                    {req.request_type}
                  </span>
                  {category && (
                    <span className={badgeBase} title="category">
                      {category}
                    </span>
                  )}
                  {visibility && (
                    <span className={badgeBase} title="visibility">
                      {visibility}
                    </span>
                  )}
                </div>
                <p className="line-clamp-2 text-sm text-[#171717]">{req.question}</p>
                <p className="mt-1 text-[11px] text-[#999]">
                  {new Date(req.created_at).toLocaleString()}
                </p>
              </li>
            );
          })}
        </ul>
      </aside>
    );
  }
);

HITLCenterPanel.displayName = 'HITLCenterPanel';
