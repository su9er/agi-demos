import { A2UIProgress } from './A2UIProgress';
import { A2UIRadio } from './A2UIRadio';
import { A2UITable } from './A2UITable';
import { ComponentRegistry } from './a2uiInternals';

export function ensureMemStackA2UIRegistry(): void {
  const registry = ComponentRegistry.getInstance();
  if (!registry.has('Radio')) {
    registry.register('Radio', { component: A2UIRadio });
  }
  if (!registry.has('Progress')) {
    registry.register('Progress', { component: A2UIProgress });
  }
  if (!registry.has('Table')) {
    registry.register('Table', { component: A2UITable });
  }
}
