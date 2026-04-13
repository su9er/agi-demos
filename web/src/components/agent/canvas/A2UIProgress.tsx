import { memo, useMemo } from 'react';

import type { CSSProperties } from 'react';

import { useA2UIActions, useA2UIState } from './a2uiInternals';
import {
  normalizeStyle,
  resolveBoundNumberValue,
  resolveBoundStringValue,
  type NumberValue,
  type StringValue,
} from './a2uiCustomUtils';

interface ProgressProperties {
  label?: StringValue | string;
  value?: NumberValue | number;
  max?: NumberValue | number;
  tone?: string;
  showValue?: boolean;
  style?: Record<string, unknown>;
}

type ProgressNode = Record<string, unknown> & {
  id: string;
  dataContextPath?: string;
  weight?: number;
  properties?: ProgressProperties;
};

const TONE_STYLES: Record<string, { track: string; fill: string; text: string }> = {
  neutral: {
    track: '#ebebeb',
    fill: '#171717',
    text: '#525252',
  },
  success: {
    track: '#e7f7ed',
    fill: '#0a6b2d',
    text: '#0a6b2d',
  },
  warning: {
    track: '#fff6e5',
    fill: '#a66a00',
    text: '#8a5b00',
  },
  error: {
    track: '#fdecec',
    fill: '#c53030',
    text: '#9f1c1c',
  },
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export const A2UIProgress = memo(function A2UIProgress({
  node,
  surfaceId,
}: {
  node: ProgressNode;
  surfaceId: string;
}) {
  const actions = useA2UIActions();
  const { version } = useA2UIState();

  const props = (node.properties ?? {}) as ProgressProperties;
  const label = useMemo(
    () => resolveBoundStringValue(props.label, node, surfaceId, actions),
    [actions, node, props.label, surfaceId, version]
  );
  const resolvedValue = useMemo(
    () => resolveBoundNumberValue(props.value, node, surfaceId, actions) ?? 0,
    [actions, node, props.value, surfaceId, version]
  );
  const resolvedMax = useMemo(() => {
    const maxValue = resolveBoundNumberValue(props.max ?? 100, node, surfaceId, actions);
    return typeof maxValue === 'number' && maxValue > 0 ? maxValue : 100;
  }, [actions, node, props.max, surfaceId, version]);
  const tone = TONE_STYLES[props.tone ?? 'neutral'] ?? {
    track: '#ebebeb',
    fill: '#171717',
    text: '#525252',
  };
  const clampedValue = clamp(resolvedValue, 0, resolvedMax);
  const percent = resolvedMax > 0 ? clamp((clampedValue / resolvedMax) * 100, 0, 100) : 0;
  const valueText = `${Math.round(percent)}%`;

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

  return (
    <div className="a2ui-progress" style={rootStyle}>
      <section style={sectionStyle}>
        {label || props.showValue !== false ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
            }}
          >
            <span
              style={{
                color: '#171717',
                fontSize: '14px',
                fontWeight: 500,
                lineHeight: '20px',
              }}
            >
              {label ?? 'Progress'}
            </span>
            {props.showValue !== false ? (
              <span
                style={{
                  color: tone.text,
                  fontSize: '12px',
                  fontWeight: 500,
                  lineHeight: '16px',
                }}
              >
                {valueText}
              </span>
            ) : null}
          </div>
        ) : null}
        <div
          role="progressbar"
          aria-label={label ?? node.id}
          aria-valuemin={0}
          aria-valuemax={resolvedMax}
          aria-valuenow={Math.round(clampedValue)}
          style={{
            width: '100%',
            height: '8px',
            borderRadius: '9999px',
            overflow: 'hidden',
            backgroundColor: tone.track,
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${percent}%`,
              borderRadius: '9999px',
              backgroundColor: tone.fill,
              transition: 'width 160ms ease-out',
            }}
          />
        </div>
      </section>
    </div>
  );
});
