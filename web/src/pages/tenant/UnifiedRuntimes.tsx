/**
 * Unified Runtimes panel.
 *
 * Read-only diagnostic view combining the two runtime surfaces MemStack
 * currently exposes independently:
 *
 *   - Agent Pool actors   (`poolService`, /admin/pool/*)
 *   - Project sandboxes   (`projectSandboxService`)
 *
 * Borrowed from multica's Unified Runtimes concept: operators want one
 * place to answer "is the agent slow because its actor is unhealthy or
 * because its sandbox died?" without tabbing through separate screens.
 *
 * This is intentionally **read-only** and non-mutating — control actions
 * already live on each dedicated page; this is a situational-awareness
 * aggregator.
 */
import { useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';
import { Alert, Badge, Card, Empty, Space, Table, Tag, Typography } from 'antd';

import { poolService, type PoolInstance, type PoolStatus } from '@/services/poolService';

const { Title, Text } = Typography;

interface RuntimeRow {
  key: string;
  kind: 'pool_actor' | 'sandbox';
  identifier: string;
  tenantId: string;
  projectId: string;
  status: string;
  health: string;
  tier?: string;
  lastActivity?: string | null;
  requests?: number;
  memoryMb?: number;
}

function statusColor(status: string): string {
  if (/fail|error|unhealthy|terminated/i.test(status)) return 'red';
  if (/pause|degraded|warn/i.test(status)) return 'orange';
  if (/ready|running|execut|active/i.test(status)) return 'green';
  if (/pending|creating|initializing/i.test(status)) return 'blue';
  return 'default';
}

export function UnifiedRuntimes() {
  const poolStatusQuery = useQuery<PoolStatus>({
    queryKey: ['runtimes', 'pool', 'status'],
    queryFn: () => poolService.getStatus(),
    refetchInterval: 15_000,
  });

  const poolInstancesQuery = useQuery({
    queryKey: ['runtimes', 'pool', 'instances'],
    queryFn: () => poolService.listInstances({ page: 1, page_size: 200 }),
    refetchInterval: 15_000,
  });

  const rows: RuntimeRow[] = useMemo(() => {
    const instances: PoolInstance[] = poolInstancesQuery.data?.instances ?? [];
    return instances.map((inst) => ({
      key: `pool:${inst.instance_key}`,
      kind: 'pool_actor',
      identifier: inst.instance_key,
      tenantId: inst.tenant_id,
      projectId: inst.project_id,
      status: inst.status,
      health: inst.health_status,
      tier: inst.tier,
      lastActivity: inst.last_request_at,
      requests: inst.active_requests,
      memoryMb: inst.memory_used_mb,
    }));
  }, [poolInstancesQuery.data]);

  const columns = [
    {
      title: 'Kind',
      dataIndex: 'kind',
      key: 'kind',
      width: 130,
      render: (kind: RuntimeRow['kind']) => (
        <Tag color={kind === 'pool_actor' ? 'geekblue' : 'purple'}>
          {kind === 'pool_actor' ? 'Pool Actor' : 'Sandbox'}
        </Tag>
      ),
    },
    {
      title: 'Identifier',
      dataIndex: 'identifier',
      key: 'identifier',
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: 'Tenant / Project',
      key: 'scope',
      render: (_: unknown, row: RuntimeRow) => (
        <Space direction="vertical" size={0}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {row.tenantId}
          </Text>
          <Text style={{ fontSize: 13 }}>{row.projectId}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
    },
    {
      title: 'Health',
      dataIndex: 'health',
      key: 'health',
      render: (h: string) => <Badge status={h === 'healthy' ? 'success' : h === 'degraded' ? 'warning' : 'error'} text={h} />,
    },
    {
      title: 'Tier',
      dataIndex: 'tier',
      key: 'tier',
      render: (t?: string) => (t ? <Tag>{t}</Tag> : '—'),
    },
    {
      title: 'Active / Memory',
      key: 'load',
      render: (_: unknown, row: RuntimeRow) => (
        <Text style={{ fontSize: 12 }}>
          {row.requests ?? 0} req · {Math.round(row.memoryMb ?? 0)} MB
        </Text>
      ),
    },
    {
      title: 'Last activity',
      dataIndex: 'lastActivity',
      key: 'lastActivity',
      render: (t?: string | null) => (t ? new Date(t).toLocaleString() : '—'),
    },
  ];

  const poolStatus = poolStatusQuery.data;

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            Runtimes
          </Title>
          <Text type="secondary">
            Unified view of agent-pool actors and project sandboxes. Read-only — use the dedicated pages for
            lifecycle actions.
          </Text>
        </div>

        {poolStatusQuery.isError && (
          <Alert type="warning" message="Pool status unavailable" description={(poolStatusQuery.error).message} />
        )}

        {poolStatus && (
          <Space size="large" wrap>
            <Card size="small" title="Pool total">
              <Title level={4} style={{ margin: 0 }}>{poolStatus.total_instances}</Title>
            </Card>
            <Card size="small" title="Hot / Warm / Cold">
              <Text>{poolStatus.hot_instances} / {poolStatus.warm_instances} / {poolStatus.cold_instances}</Text>
            </Card>
            <Card size="small" title="Ready / Executing">
              <Text>{poolStatus.ready_instances} / {poolStatus.executing_instances}</Text>
            </Card>
            <Card size="small" title="Unhealthy">
              {poolStatus.unhealthy_instances > 0 ? (
                <Text type="danger">{poolStatus.unhealthy_instances}</Text>
              ) : (
                <Text>{poolStatus.unhealthy_instances}</Text>
              )}
            </Card>
            <Card size="small" title="Memory">
              <Text>
                {Math.round(poolStatus.resource_usage.used_memory_mb)} / {Math.round(poolStatus.resource_usage.total_memory_mb)} MB
              </Text>
            </Card>
          </Space>
        )}

        <Card
          title="Instances"
          extra={
            <Text type="secondary" style={{ fontSize: 12 }}>
              Auto-refresh 15s
            </Text>
          }
        >
          {rows.length === 0 && !poolInstancesQuery.isLoading ? (
            <Empty description="No runtime instances" />
          ) : (
            <Table<RuntimeRow>
              columns={columns}
              dataSource={rows}
              loading={poolInstancesQuery.isLoading}
              pagination={{ pageSize: 25 }}
              size="small"
              rowKey="key"
            />
          )}
        </Card>

        <Alert
          type="info"
          showIcon
          message="Sandbox rows coming soon"
          description="Project sandboxes surface through projectSandboxService per-project. A future iteration will aggregate all sandboxes across the tenant here. Until then, use the project detail page."
        />
      </Space>
    </div>
  );
}

export default UnifiedRuntimes;
