import { describe, expect, it } from 'vitest';

import { extractA2UISurfaceId, mergeA2UIMessageStream } from '../../../stores/agent/a2uiMessages';

describe('mergeA2UIMessageStream', () => {
  it('appends incremental surfaceUpdate payloads to preserve previous beginRendering', () => {
    const previous =
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}\n' +
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}';
    const incoming =
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"world"}}}}]}}';

    const merged = mergeA2UIMessageStream(previous, incoming);

    expect(merged).toContain('"beginRendering"');
    expect(merged.split('\n')).toHaveLength(3);
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
});
