import React, { useEffect, useState } from 'react';

import { SearchOutlined } from '@ant-design/icons';
import { Table, Input, Tag, Space, Typography, Button } from 'antd';
import { useShallow } from 'zustand/react/shallow';

import { useProviderStore } from '@/stores/provider';

import { PROVIDERS } from '@/constants/providers';

import type { ModelCatalogEntry } from '@/types/memory';

const { Text } = Typography;

export interface ModelCatalogBrowserProps {
  onSelect?: (model: ModelCatalogEntry) => void;
  selectedModel?: string;
  filterProvider?: string;
}

export const ModelCatalogBrowser: React.FC<ModelCatalogBrowserProps> = ({
  onSelect,
  selectedModel,
  filterProvider,
}) => {
  const { catalogLoading, modelSearchResults } = useProviderStore(
    useShallow((s) => ({
      catalogLoading: s.catalogLoading,
      modelSearchResults: s.modelSearchResults,
    }))
  );

  const { fetchModelCatalog, searchModels } = useProviderStore(
    useShallow((s) => ({
      fetchModelCatalog: s.fetchModelCatalog,
      searchModels: s.searchModels,
    }))
  );

  const [localSearch, setLocalSearch] = useState('');

  useEffect(() => {
    fetchModelCatalog(filterProvider);
  }, [fetchModelCatalog, filterProvider]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocalSearch(value);
    searchModels(value);
  };

  const getProviderIcon = (providerValue: string) => {
    const meta = PROVIDERS.find((p) => p.value === providerValue);
    return meta ? meta.icon : '🤖';
  };

  const columns = [
    {
      title: 'Model',
      dataIndex: 'name',
      key: 'name',
      width: 220,
      render: (text: string, record: ModelCatalogEntry) => (
        <Space direction="vertical" size={0}>
          <Text strong>
            {record.provider && (
              <span className="mr-2" role="img" aria-label="provider">
                {getProviderIcon(record.provider)}
              </span>
            )}
            {text}
          </Text>
          {record.provider && <Text type="secondary" className="text-xs">{record.provider}</Text>}
        </Space>
      ),
    },
    {
      title: 'Context',
      dataIndex: 'context_length',
      key: 'context_length',
      width: 100,
      sorter: (a: ModelCatalogEntry, b: ModelCatalogEntry) => a.context_length - b.context_length,
      render: (val: number) => <Text>{val >= 1000000 ? `${(val / 1000000).toFixed(1)}M` : `${(val / 1000).toFixed(0)}k`}</Text>,
    },
    {
      title: 'Cost ($/1M)',
      key: 'cost',
      width: 120,
      render: (_: unknown, record: ModelCatalogEntry) => {
        const inCost = record.input_cost_per_1m;
        const outCost = record.output_cost_per_1m;
        if (inCost == null && outCost == null) return <Text type="secondary">-</Text>;
        return (
          <Space direction="vertical" size={0}>
            <Text className="text-xs">In: ${inCost?.toFixed(2) ?? '-'}</Text>
            <Text className="text-xs">Out: ${outCost?.toFixed(2) ?? '-'}</Text>
          </Space>
        );
      },
    },
    {
      title: 'Features',
      key: 'features',
      width: 200,
      render: (_: unknown, record: ModelCatalogEntry) => (
        <Space size={[0, 4]} wrap>
          {record.reasoning && <Tag color="gold">Reasoning</Tag>}
          {record.supports_tool_call && <Tag color="green">Tools</Tag>}
          {record.supports_attachment && <Tag color="purple">Vision</Tag>}
          {record.supports_structured_output && <Tag color="cyan">Structured</Tag>}
          {record.supports_temperature && <Tag>Temp</Tag>}
          {record.open_weights && <Tag color="orange">Open</Tag>}
        </Space>
      ),
    },
    {
      title: 'Capabilities',
      dataIndex: 'capabilities',
      key: 'capabilities',
      width: 150,
      render: (caps: string[]) => (
        <Space size={[0, 4]} wrap>
          {caps.map((cap) => (
            <Tag key={cap} color={cap === 'chat' ? 'blue' : cap === 'vision' ? 'purple' : cap === 'embedding' ? 'geekblue' : 'default'}>
              {cap}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      width: 90,
      render: (_: unknown, record: ModelCatalogEntry) => {
        const isSelected = selectedModel === record.name;
        return (
          <Button
            type={isSelected ? 'primary' : 'default'}
            size="small"
            onClick={() => onSelect?.(record)}
          >
            {isSelected ? 'Selected' : 'Select'}
          </Button>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Input
        placeholder="Search models by name, provider, or capability..."
        prefix={<SearchOutlined className="text-gray-400" />}
        value={localSearch}
        onChange={handleSearch}
        allowClear
      />
      <Table
        dataSource={modelSearchResults}
        columns={columns}
        rowKey="name"
        loading={catalogLoading}
        pagination={{ pageSize: 8 }}
        size="small"
        scroll={{ x: 880 }}
      />
    </div>
  );
};
