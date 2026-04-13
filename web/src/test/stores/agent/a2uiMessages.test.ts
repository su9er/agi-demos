import { describe, expect, it } from 'vitest';

import {
  buildA2UIMessageStreamSnapshot,
  extractA2UISurfaceId,
  mergeA2UIMessageStream,
  mergeA2UIMessageStreamWithSnapshot,
} from '../../../stores/agent/a2uiMessages';

describe('mergeA2UIMessageStream', () => {
  it('rebuilds a merged surface snapshot for incremental surfaceUpdate payloads', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming =
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"world"}}}}]}}';

    const merged = mergeA2UIMessageStream(previous, incoming);

    expect(merged).toContain('"beginRendering"');
    expect(merged.split('\n')).toHaveLength(2);
    expect(merged).toContain('"world"');
  });

  it('replaces payload when incoming already contains beginRendering', () => {
    const previous = '{"surfaceUpdate":{"surfaceId":"s1","components":[]}}';
    const incoming = '{"beginRendering":{"surfaceId":"s1","root":"root-2"}}';

    const merged = mergeA2UIMessageStream(previous, incoming);

    expect(merged).toBe(incoming);
  });

  it('appends incremental dataModelUpdate payloads', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming = '{"dataModelUpdate":{"surfaceId":"s1","path":"/","contents":[{"count":2}]}}';

    const merged = mergeA2UIMessageStream(previous, incoming);

    expect(merged).toContain('"beginRendering"');
    expect(merged).toContain('"dataModelUpdate"');
    expect(merged.split('\n')).toHaveLength(3);
  });

  it('reuses the structured snapshot when merging incremental updates', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming =
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"world"}}}}]}}';
    const previousSnapshot = buildA2UIMessageStreamSnapshot(previous);

    const merged = mergeA2UIMessageStreamWithSnapshot(previousSnapshot, previous, incoming);

    expect(merged.messages).toContain('"world"');
    expect(merged.snapshot?.surfaceId).toBe('s1');
    expect(merged.snapshot?.components).toHaveLength(1);
  });

  it('materializes merged data into the structured snapshot', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming =
      '{"dataModelUpdate":{"surfaceId":"s1","path":"/","contents":[{"key":"stats","valueMap":[{"key":"count","valueNumber":2}]}]}}';
    const previousSnapshot = buildA2UIMessageStreamSnapshot(previous);

    const merged = mergeA2UIMessageStreamWithSnapshot(previousSnapshot, previous, incoming);

    expect(merged.snapshot?.data).toEqual({ stats: { count: 2 } });
  });

  it('preserves prior components when incremental updates switch array and object shapes', () => {
    const previous = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"root"}}}},{"id":"child-1","component":{"Text":{"text":{"literal":"child"}}}}]}}',
    ].join('\n');
    const incoming = JSON.stringify({
      surfaceUpdate: {
        surfaceId: 's1',
        components: {
          slot: {
            id: 'child-1',
            component: {
              Text: {
                text: { literal: 'updated child' },
              },
            },
          },
        },
      },
    });
    const previousSnapshot = buildA2UIMessageStreamSnapshot(previous);

    const merged = mergeA2UIMessageStreamWithSnapshot(previousSnapshot, previous, incoming);

    expect(Array.isArray(merged.snapshot?.components)).toBe(false);
    const components = merged.snapshot?.components as Record<
      string,
      { id: string; component: { Text?: { text?: { literal?: string } } } }
    >;
    expect(Object.values(components).map((component) => component.id)).toEqual(
      expect.arrayContaining(['root-1', 'child-1'])
    );
    const updatedChild = Object.values(components).find((component) => component.id === 'child-1');
    expect(updatedChild?.component.Text?.text?.literal).toBe('updated child');
  });

  it('ignores unsafe object-shaped component keys when building snapshots', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":{"__proto__":{"id":"poison","component":{"Text":{"text":{"literal":"bad"}}}},"root":{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}}}}',
    ].join('\n');

    const snapshot = buildA2UIMessageStreamSnapshot(messages);

    expect(snapshot).toBeDefined();
    expect(Array.isArray(snapshot?.components)).toBe(false);
    const components = snapshot?.components as Record<string, { id: string }>;
    expect(Object.keys(components)).toEqual(['root']);
    expect(Object.prototype.hasOwnProperty.call(components, '__proto__')).toBe(false);
    expect(components.root.id).toBe('root-1');
  });

  it('returns incoming payload when there is no previous message stream', () => {
    const incoming = '{"surfaceUpdate":{"surfaceId":"s1","components":[]}}';
    expect(mergeA2UIMessageStream(undefined, incoming)).toBe(incoming);
  });

  it('treats deleteSurface payloads as a full reset', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming = '{"deleteSurface":{"surfaceId":"s1"}}';

    const merged = mergeA2UIMessageStream(previous, incoming);

    expect(merged).toBe(incoming);
  });

  it('returns the raw incoming payload when incremental surfaceIds drift', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming =
      '{"surfaceUpdate":{"surfaceId":"s2","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"world"}}}}]}}';

    expect(mergeA2UIMessageStream(previous, incoming)).toBe(incoming);
  });

  it('extracts a single surface id from the message stream', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"surface-1","components":[]}}',
    ].join('\n');

    expect(extractA2UISurfaceId(messages)).toBe('surface-1');
  });

  it('returns undefined when the message stream mixes multiple surface ids', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
      '{"beginRendering":{"surfaceId":"surface-2","root":"root-2"}}',
    ].join('\n');

    expect(extractA2UISurfaceId(messages)).toBeUndefined();
  });

  it('ignores nested non-envelope surfaceId fields', () => {
    const messages = JSON.stringify({
      surfaceUpdate: {
        surfaceId: 'real-surface',
        components: [
          {
            id: 'btn-1',
            component: {
              Button: {
                child: 'label-1',
                action: {
                  name: 'submit',
                  context: {
                    surfaceId: 'domain-object-id',
                  },
                },
              },
            },
          },
        ],
      },
    });

    expect(extractA2UISurfaceId(messages)).toBe('real-surface');
  });

  it('supports pretty-printed multi-line JSON objects', () => {
    const messages = `
{
  "beginRendering": {
    "surfaceId": "surface-1",
    "root": "root-1"
  }
}
{
  "surfaceUpdate": {
    "surfaceId": "surface-1",
    "components": []
  }
}
`;

    expect(extractA2UISurfaceId(messages)).toBe('surface-1');
  });

  it('returns undefined for malformed chunked payloads', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"surface-1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"surface-1","components":[',
    ].join('\n');

    expect(extractA2UISurfaceId(messages)).toBeUndefined();
  });
});
