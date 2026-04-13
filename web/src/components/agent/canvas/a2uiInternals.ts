// @ts-expect-error CopilotKit does not publish declarations for this internal registry module.
import { ComponentRegistry as RawComponentRegistry } from '../../../../node_modules/@copilotkit/a2ui-renderer/dist/react-renderer/registry/ComponentRegistry.mjs';
// @ts-expect-error CopilotKit does not publish declarations for this internal provider module.
// prettier-ignore
import { useA2UIActions as rawUseA2UIActions, useA2UIState as rawUseA2UIState } from '../../../../node_modules/@copilotkit/a2ui-renderer/dist/react-renderer/core/A2UIProvider.mjs';

import type { ComponentType, NamedExoticComponent } from 'react';

export interface A2UINodeLike extends Record<string, unknown> {
  id?: string;
  dataContextPath?: string;
}

export interface A2UIActions {
  setData(node: A2UINodeLike, path: string, value: unknown, surfaceId: string): void;
  getData(node: A2UINodeLike, path: string, surfaceId: string): unknown;
  resolvePath(path: string, dataContextPath?: string): string;
}

export interface A2UIComponentRegistry {
  has(type: string): boolean;
  register(
    type: string,
    registration: {
      component: ComponentType<any> | NamedExoticComponent<any>;
    }
  ): void;
}

export const ComponentRegistry = RawComponentRegistry as unknown as {
  getInstance(): A2UIComponentRegistry;
};
export const useA2UIActions = rawUseA2UIActions as () => A2UIActions;
export const useA2UIState = rawUseA2UIState as () => { version: number };
