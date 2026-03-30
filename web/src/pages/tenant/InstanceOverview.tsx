import React, { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Table, Tag, Card } from 'antd';
import { Eye, EyeOff } from 'lucide-react';

import { LazyButton, useLazyMessage } from '@/components/ui/lazyAntd';

import {
  useCurrentInstance,
  useInstanceMembers,
  useInstanceConfig,
  useInstanceStore,
} from '../../stores/instance';

import type { InstanceMemberResponse } from '../../services/instanceService';
import type { ColumnsType } from 'antd/es/table';

export const InstanceOverview: React.FC = () => {
  const { t } = useTranslation();
  const messageApi = useLazyMessage();

  const [showToken, setShowToken] = useState<boolean>(false);

  const instance = useCurrentInstance();
  const members = useInstanceMembers();
  const config = useInstanceConfig();
  const listMembers = useInstanceStore((s) => s.listMembers);

  useEffect(() => {
    if (instance?.id) {
      listMembers(instance.id);
    }
  }, [instance?.id, listMembers]);

  const handleCopyToken = () => {
    if (instance?.proxy_token) {
      navigator.clipboard.writeText(instance.proxy_token);
      messageApi?.success(t('tenant.instances.tokenCopied'));
    }
  };

  const memberColumns: ColumnsType<InstanceMemberResponse> = [
    {
      title: t('tenant.instances.columns.userId'),
      dataIndex: 'user_id',
      key: 'user_id',
    },
    {
      title: t('tenant.instances.columns.role'),
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => <Tag color={role === 'admin' ? 'blue' : 'default'}>{role}</Tag>,
    },
    {
      title: t('tenant.instances.columns.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: t('tenant.instances.columns.actions'),
      key: 'actions',
      render: () => (
        <LazyButton type="link" danger className="p-0">
          {t('tenant.instances.actions.removeMember')}
        </LazyButton>
      ),
    },
  ];

  if (!instance) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark">
          <p className="text-sm text-text-secondary dark:text-text-muted">
            {t('tenant.instances.detail.status')}
          </p>
          <p className="text-lg font-semibold mt-1">
            {t(`tenant.instances.status.${instance.status}`)}
          </p>
        </Card>
        <Card className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark">
          <p className="text-sm text-text-secondary dark:text-text-muted">
            {t('tenant.instances.detail.replicas')}
          </p>
          <p className="text-lg font-semibold mt-1">
            {instance.available_replicas || 0} / {instance.replicas}
          </p>
        </Card>
        <Card className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark">
          <p className="text-sm text-text-secondary dark:text-text-muted">
            {t('tenant.instances.detail.imageVersion')}
          </p>
          <p className="text-lg font-semibold mt-1">{instance.image_version}</p>
        </Card>
        <Card className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark">
          <p className="text-sm text-text-secondary dark:text-text-muted">
            {t('tenant.instances.detail.runtime')}
          </p>
          <p className="text-lg font-semibold mt-1">{instance.runtime}</p>
        </Card>
      </div>

      {instance.proxy_token && (
        <Card
          title={t('tenant.instances.detail.proxyToken')}
          className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark"
        >
          <div className="flex gap-4 items-center">
            <code className="bg-surface-muted dark:bg-surface-dark-alt px-4 py-2 rounded flex-1 break-all">
              {showToken ? instance.proxy_token : '••••••••••••••••••••••••••••••••'}
            </code>
            <LazyButton
              icon={showToken ? <EyeOff size={16} /> : <Eye size={16} />}
              onClick={() => {
                setShowToken(!showToken);
              }}
              aria-label={showToken ? 'Hide token' : 'Show token'}
            />
            <LazyButton onClick={handleCopyToken}>{t('common.copy')}</LazyButton>
          </div>
        </Card>
      )}

      <Card
        title={t('tenant.instances.detail.resources')}
        className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div>
            <p className="text-sm text-text-secondary dark:text-text-muted">
              {t('tenant.instances.detail.cpu')}
            </p>
            <p className="font-medium mt-1">
              {instance.cpu_request} / {instance.cpu_limit}
            </p>
          </div>
          <div>
            <p className="text-sm text-text-secondary dark:text-text-muted">
              {t('tenant.instances.detail.memory')}
            </p>
            <p className="font-medium mt-1">
              {instance.mem_request} / {instance.mem_limit}
            </p>
          </div>
          <div>
            <p className="text-sm text-text-secondary dark:text-text-muted">
              {t('tenant.instances.detail.storage')}
            </p>
            <p className="font-medium mt-1">
              {instance.storage_class || '-'} ({instance.storage_size || '-'})
            </p>
          </div>
          <div>
            <p className="text-sm text-text-secondary dark:text-text-muted">
              {t('tenant.instances.detail.quota')}
            </p>
            <p className="font-medium mt-1">
              CPU: {instance.quota_cpu || '-'}, Mem: {instance.quota_memory || '-'}, Pods:{' '}
              {instance.quota_max_pods || '-'}
            </p>
          </div>
        </div>
      </Card>

      <Card
        title={t('tenant.instances.detail.members')}
        className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark p-0"
        styles={{ body: { padding: 0 } }}
      >
        <Table
          columns={memberColumns}
          dataSource={members}
          rowKey="id"
          pagination={false}
          className="w-full"
        />
      </Card>

      <Card
        title={t('tenant.instances.detail.config')}
        className="bg-surface-light dark:bg-surface-dark rounded-lg border border-border-light dark:border-border-dark"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <h3 className="text-md font-medium mb-4">{t('tenant.instances.detail.envVars')}</h3>
            <pre className="bg-surface-muted dark:bg-surface-dark-alt p-4 rounded-lg overflow-x-auto text-sm">
              {JSON.stringify(config?.env_vars || instance.env_vars, null, 2)}
            </pre>
          </div>
          <div>
            <h3 className="text-md font-medium mb-4">
              {t('tenant.instances.detail.advancedConfig')}
            </h3>
            <pre className="bg-surface-muted dark:bg-surface-dark-alt p-4 rounded-lg overflow-x-auto text-sm">
              {JSON.stringify(config?.advanced_config || instance.advanced_config, null, 2)}
            </pre>
          </div>
        </div>
      </Card>
    </div>
  );
};
