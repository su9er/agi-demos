/**
 * Agent "teammates" panel — read-only listing of agent definitions scoped to
 * the current project. Phase-1 of multica's "agent as first-class member"
 * pattern; no mention syntax, no permission model, just situational awareness.
 *
 * Decisions baked in (see session files/p2-design-questions.md for rationale):
 *   - Scope: project (AgentDefinition.project_id). Cross-tenant is future work.
 *   - Display: list of rows with avatar glyph + name + enabled dot + status.
 *   - Actions: none. Click "Manage" to jump to /tenant/agent-definitions.
 */
import { Link } from 'react-router-dom';

import { useQuery } from '@tanstack/react-query';
import { Badge, Card, Empty, List, Skeleton, Space, Tag, Typography } from 'antd';
import { Bot } from 'lucide-react';

import { definitionsService } from '@/services/agent/definitionsService';

import type { AgentDefinition } from '@/types/multiAgent';

const { Text, Title } = Typography;

interface AgentTeammatesPanelProps {
  projectId: string;
}

function initials(name: string): string {
  const clean = name.trim();
  if (!clean) return 'A';
  const parts = clean.split(/[\s_-]+/).filter(Boolean);
  if (parts.length === 0) return 'A';
  const first = parts[0] ?? '';
  if (parts.length === 1) return first.slice(0, 2).toUpperCase() || 'A';
  const last = parts[parts.length - 1] ?? '';
  return ((first[0] ?? '') + (last[0] ?? '')).toUpperCase() || 'A';
}

export function AgentTeammatesPanel({ projectId }: AgentTeammatesPanelProps) {
  const query = useQuery<AgentDefinition[]>({
    queryKey: ['project', projectId, 'agent-definitions'],
    queryFn: () => definitionsService.list({ project_id: projectId }),
    enabled: Boolean(projectId),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const agents = query.data ?? [];

  return (
    <Card
      title={
        <Space>
          <Bot size={16} />
          <span>Agent teammates</span>
          {agents.length > 0 && <Tag>{agents.length}</Tag>}
        </Space>
      }
      extra={
        <Link to="/tenant/agent-definitions" style={{ fontSize: 13 }}>
          Manage
        </Link>
      }
      style={{ marginTop: 24 }}
    >
      {query.isLoading ? (
        <Skeleton active paragraph={{ rows: 2 }} />
      ) : agents.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Text type="secondary">
              No agent definitions for this project yet. Create one from{' '}
              <Link to="/tenant/agent-definitions">Agent Definitions</Link>.
            </Text>
          }
        />
      ) : (
        <List
          dataSource={agents}
          rowKey="id"
          renderItem={(agent) => {
            const displayName = agent.display_name ?? agent.name;
            const successPct =
              agent.success_rate == null ? null : Math.round(agent.success_rate * 100);
            return (
              <List.Item>
                <List.Item.Meta
                  avatar={
                    <div
                      aria-hidden
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 6,
                        background: agent.enabled ? '#f5f5f5' : '#fafafa',
                        color: agent.enabled ? '#171717' : '#999',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 13,
                        fontWeight: 500,
                        border: '1px solid rgba(0,0,0,0.08)',
                      }}
                    >
                      {initials(displayName)}
                    </div>
                  }
                  title={
                    <Space size="small">
                      <Text strong>{displayName}</Text>
                      <Badge
                        status={agent.enabled ? 'success' : 'default'}
                        text={<Text type="secondary" style={{ fontSize: 12 }}>{agent.enabled ? 'enabled' : 'disabled'}</Text>}
                      />
                    </Space>
                  }
                  description={
                    <Space size="large" wrap>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {agent.model ?? 'default model'}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {agent.total_invocations} invocations
                      </Text>
                      {successPct != null && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {successPct}% success
                        </Text>
                      )}
                      {agent.can_spawn && <Tag color="blue">can spawn</Tag>}
                      {agent.discoverable && <Tag>discoverable</Tag>}
                    </Space>
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </Card>
  );
}

export function AgentTeammatesSkeleton() {
  return (
    <Card style={{ marginTop: 24 }}>
      <Title level={5} style={{ marginBottom: 12 }}>
        Agent teammates
      </Title>
      <Skeleton active paragraph={{ rows: 2 }} />
    </Card>
  );
}
