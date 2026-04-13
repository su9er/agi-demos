import { memo, useCallback, useEffect, useMemo, useState } from 'react';

import type { CSSProperties, ChangeEvent } from 'react';

import { useA2UIActions, useA2UIState } from './a2uiInternals';
import {
  normalizeStyle,
  resolveBindingPath,
  resolveBoundStringValue,
  type StringValue,
} from './a2uiCustomUtils';

interface RadioOption {
  label?: StringValue | string;
  text?: StringValue | string;
  value?: string | number | boolean;
}

interface RadioProperties {
  description?: StringValue | string;
  options?: RadioOption[];
  value?: StringValue | string;
  selection?: StringValue | string;
  selections?: { path?: string };
  selected?: StringValue | string;
  path?: string;
  style?: Record<string, unknown>;
}

type RadioNode = Record<string, unknown> & {
  id: string;
  dataContextPath?: string;
  weight?: number;
  properties?: RadioProperties;
};

interface ResolvedRadioOption {
  label: string;
  value: string;
}

function resolveDisplayString(
  input: unknown,
  node: RadioNode,
  surfaceId: string,
  actions: ReturnType<typeof useA2UIActions>
): string | undefined {
  return resolveBoundStringValue(input, node, surfaceId, actions);
}

function normalizeRadioOptions(
  input: unknown,
  node: RadioNode,
  surfaceId: string,
  actions: ReturnType<typeof useA2UIActions>
): ResolvedRadioOption[] {
  if (!Array.isArray(input)) {
    return [];
  }

  return input.flatMap((option) => {
    if (typeof option === 'string' && option.trim().length > 0) {
      return [{ label: option, value: option }];
    }
    if (!option || typeof option !== 'object' || Array.isArray(option)) {
      return [];
    }

    const record = option as RadioOption;
    const rawValue = record.value;
    const value =
      typeof rawValue === 'string' && rawValue.trim().length > 0
        ? rawValue
        : typeof rawValue === 'number' || typeof rawValue === 'boolean'
          ? String(rawValue)
          : undefined;
    if (!value) {
      return [];
    }

    const label = resolveDisplayString(
      record.label ?? record.text ?? value,
      node,
      surfaceId,
      actions
    );
    if (!label) {
      return [];
    }
    return [{ label, value }];
  });
}

export const A2UIRadio = memo(function A2UIRadio({
  node,
  surfaceId,
}: {
  node: RadioNode;
  surfaceId: string;
}) {
  const actions = useA2UIActions();
  const { version } = useA2UIState();

  const props = (node.properties ?? {}) as RadioProperties;
  const bindingInput =
    props.value ??
    props.selection ??
    props.selected ??
    props.selections ??
    (props.path ? { path: props.path } : undefined);
  const description = useMemo(
    () => resolveDisplayString(props.description, node, surfaceId, actions),
    [actions, node, props.description, surfaceId, version]
  );
  const options = useMemo(
    () => normalizeRadioOptions(props.options, node, surfaceId, actions),
    [actions, node, props.options, surfaceId, version]
  );
  const boundPath = useMemo(
    () => resolveBindingPath(bindingInput, node, actions),
    [actions, bindingInput, node]
  );
  const resolvedValue = useMemo(
    () => resolveBoundStringValue(bindingInput, node, surfaceId, actions),
    [actions, bindingInput, node, surfaceId, version]
  );
  const [localValue, setLocalValue] = useState<string | undefined>(resolvedValue);

  useEffect(() => {
    setLocalValue(resolvedValue);
  }, [resolvedValue]);

  const handleChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const nextValue = event.target.value;
      setLocalValue(nextValue);
      if (boundPath) {
        actions.setData(node, boundPath, nextValue, surfaceId);
      }
    },
    [actions, boundPath, node, surfaceId]
  );

  const rootStyle =
    node.weight !== undefined ? ({ '--weight': node.weight } as CSSProperties) : undefined;
  const sectionStyle = useMemo(
    () =>
      ({
        display: 'grid',
        gap: '8px',
        ...normalizeStyle(props.style),
      }) satisfies CSSProperties,
    [props.style]
  );

  if (options.length === 0) {
    return null;
  }

  return (
    <div className="a2ui-radio" style={rootStyle}>
      <section style={sectionStyle}>
        {description ? (
          <div
            style={{
              fontSize: '14px',
              fontWeight: 500,
              color: '#171717',
            }}
          >
            {description}
          </div>
        ) : null}
        <div
          role="radiogroup"
          aria-label={description ?? node.id}
          style={{
            display: 'grid',
            gap: '8px',
          }}
        >
          {options.map((option) => (
            <label
              key={option.value}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                color: '#171717',
                fontSize: '14px',
                lineHeight: '20px',
                cursor: 'pointer',
              }}
            >
              <input
                type="radio"
                name={`${surfaceId}-${node.id}`}
                value={option.value}
                checked={localValue === option.value}
                onChange={handleChange}
                style={{ accentColor: '#171717' }}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </section>
    </div>
  );
});
