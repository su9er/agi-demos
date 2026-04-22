import type { PluginCapabilityCounts } from '@/types/channel';

interface PluginCapabilityCountEntry {
  key: keyof PluginCapabilityCounts;
  label: string;
  value: number;
}

const CAPABILITY_COUNT_ORDER: Array<keyof PluginCapabilityCounts> = [
  'channel_types',
  'tool_factories',
  'registered_tool_factories',
  'hooks',
  'commands',
  'services',
  'providers',
];

const CAPABILITY_COUNT_LABELS: Record<keyof PluginCapabilityCounts, string> = {
  channel_types: 'channels',
  tool_factories: 'active tools',
  registered_tool_factories: 'registered tools',
  hooks: 'hooks',
  commands: 'commands',
  services: 'services',
  providers: 'providers',
};

export function formatPluginCapabilityCounts(
  counts: PluginCapabilityCounts
): PluginCapabilityCountEntry[] {
  return CAPABILITY_COUNT_ORDER.map((key) => ({
    key,
    label: CAPABILITY_COUNT_LABELS[key],
    value: counts[key],
  }));
}
