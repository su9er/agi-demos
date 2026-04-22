/**
 * Curated Skills page (P2-4).
 *
 * Two tabs:
 *   1. "精选库" — list of admin-approved curated skills with Fork action.
 *   2. "我的提交" — caller's submission history (status + reviewer note).
 *
 * Submitting a private skill for review lives on the SkillList page; this
 * page is the read side for tenants.
 */

import { useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Empty,
  List,
  Modal,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import { GitFork, Library } from 'lucide-react';

import {
  curatedSkillAPI,
  type CuratedSkill,
  type SkillSubmission,
} from '@/services/curatedSkillService';

const { Text, Title, Paragraph } = Typography;

function statusColor(status: string): string {
  switch (status) {
    case 'pending':
      return 'orange';
    case 'approved':
      return 'green';
    case 'rejected':
      return 'red';
    default:
      return 'default';
  }
}

function ForkDialog({
  curated,
  open,
  onClose,
}: {
  curated: CuratedSkill | null;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [includeTriggers, setIncludeTriggers] = useState(true);
  const [includeExecutor, setIncludeExecutor] = useState(true);
  const [includeMetadata, setIncludeMetadata] = useState(true);

  const mutation = useMutation({
    mutationFn: () => {
      if (!curated) throw new Error('no curated skill');
      return curatedSkillAPI.fork(curated.id, {
        include_triggers: includeTriggers,
        include_executor: includeExecutor,
        include_metadata: includeMetadata,
      });
    },
    onSuccess: (result) => {
      message.success(`Forked. New skill id: ${result.skill_id}`);
      void qc.invalidateQueries({ queryKey: ['skills'] });
      onClose();
    },
    onError: (err: Error) => {
      message.error(err.message || 'Fork failed');
    },
  });

  return (
    <Modal
      title={curated ? `Fork "${(curated.payload.name as string) ?? 'skill'}"` : 'Fork'}
      open={open}
      onCancel={onClose}
      onOk={() => {
        mutation.mutate();
      }}
      okText="Fork"
      confirmLoading={mutation.isPending}
    >
      <Space direction="vertical" className="w-full">
        <Text type="secondary">选择复制到私有库时要包含的内容：</Text>
        <Checkbox
          checked={includeTriggers}
          onChange={(e) => {
            setIncludeTriggers(e.target.checked);
          }}
        >
          触发模式 (trigger patterns)
        </Checkbox>
        <Checkbox
          checked={includeExecutor}
          onChange={(e) => {
            setIncludeExecutor(e.target.checked);
          }}
        >
          执行器（tools + prompt_template + full_content）
        </Checkbox>
        <Checkbox
          checked={includeMetadata}
          onChange={(e) => {
            setIncludeMetadata(e.target.checked);
          }}
        >
          元数据 (metadata)
        </Checkbox>
      </Space>
    </Modal>
  );
}

function CuratedTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['skills', 'curated'],
    queryFn: () => curatedSkillAPI.list(),
  });
  const [forkTarget, setForkTarget] = useState<CuratedSkill | null>(null);

  if (isLoading) return <Skeleton active paragraph={{ rows: 4 }} />;

  const items = data ?? [];
  if (items.length === 0) {
    return <Empty description="精选库暂无已发布的 Skill" />;
  }

  return (
    <>
      <List
        dataSource={items}
        renderItem={(curated) => {
          const name = (curated.payload.name as string) ?? 'Unnamed skill';
          const description = (curated.payload.description as string) ?? '';
          return (
            <List.Item
              actions={[
                <Button
                  key="fork"
                  type="primary"
                  icon={<GitFork size={14} />}
                  onClick={() => {
                    setForkTarget(curated);
                  }}
                >
                  Fork 到私有库
                </Button>,
              ]}
            >
              <List.Item.Meta
                avatar={<Library size={20} />}
                title={
                  <Space>
                    <span>{name}</span>
                    <Tag color="blue">v{curated.semver}</Tag>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={2}>
                    <Paragraph type="secondary" ellipsis={{ rows: 2 }} className="!mb-0">
                      {description}
                    </Paragraph>
                    <Text type="secondary" className="text-xs">
                      hash: <code>{curated.revision_hash.slice(0, 12)}</code>
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          );
        }}
      />
      <ForkDialog
        curated={forkTarget}
        open={forkTarget !== null}
        onClose={() => {
          setForkTarget(null);
        }}
      />
    </>
  );
}

function SubmissionsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['skills', 'submissions', 'mine'],
    queryFn: () => curatedSkillAPI.listMySubmissions(),
  });

  if (isLoading) return <Skeleton active paragraph={{ rows: 4 }} />;

  const items = data ?? [];
  if (items.length === 0) {
    return <Empty description="暂无提交记录" />;
  }

  return (
    <List
      dataSource={items}
      renderItem={(s: SkillSubmission) => {
        const name = (s.skill_snapshot.name as string) ?? 'Unnamed';
        return (
          <List.Item>
            <List.Item.Meta
              title={
                <Space>
                  <span>{name}</span>
                  <Tag color="blue">v{s.proposed_semver}</Tag>
                  <Badge status={statusColor(s.status) as never} text={s.status} />
                </Space>
              }
              description={
                <Space direction="vertical" size={2}>
                  {s.submission_note ? (
                    <Text type="secondary">备注：{s.submission_note}</Text>
                  ) : null}
                  {s.review_note ? (
                    <Text type={s.status === 'rejected' ? 'danger' : 'secondary'}>
                      审核意见：{s.review_note}
                    </Text>
                  ) : null}
                  <Text type="secondary" className="text-xs">
                    submitted {new Date(s.created_at).toLocaleString()}
                  </Text>
                </Space>
              }
            />
          </List.Item>
        );
      }}
    />
  );
}

export default function CuratedSkills() {
  return (
    <Card className="max-w-5xl mx-auto">
      <Title level={3}>精选 Skill 库</Title>
      <Paragraph type="secondary">
        精选库包含管理员审核通过的 Skill 模板，所有租户都可以 fork 到自己的私有库进行修改。
      </Paragraph>
      <Tabs
        items={[
          { key: 'curated', label: '精选库', children: <CuratedTab /> },
          { key: 'submissions', label: '我的提交', children: <SubmissionsTab /> },
        ]}
      />
    </Card>
  );
}
