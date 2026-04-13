import { beforeEach, describe, expect, it } from 'vitest';

import { replayCanvasEventsFromTimeline } from '../../../stores/agent/canvasReplay';
import { useCanvasStore } from '../../../stores/canvasStore';
import { useLayoutModeStore } from '../../../stores/layoutMode';

describe('canvasReplay', () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
    useLayoutModeStore.getState().setMode('chat');
  });

  it('replays A2UI request ids onto reopened canvas tabs', () => {
    const content = [
      '{"beginRendering":{"surfaceId":"surface-42","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"surface-42","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
    ].join('\n');

    replayCanvasEventsFromTimeline([
      {
        id: 'evt-1',
        type: 'canvas_updated',
        eventTimeUs: 1,
        eventCounter: 1,
        timestamp: 1,
        action: 'created',
        block_id: 'block-1',
        block: {
          id: 'block-1',
          block_type: 'a2ui_surface',
          title: 'Surface',
          content,
          metadata: {},
          version: 1,
        },
      } as any,
      {
        id: 'evt-2',
        type: 'a2ui_action_asked',
        eventTimeUs: 2,
        eventCounter: 2,
        timestamp: 2,
        block_id: 'block-1',
        request_id: 'hitl-req-1',
      } as any,
    ]);

    const tab = useCanvasStore.getState().tabs.find((item) => item.id === 'block-1');
    expect(tab?.a2uiSurfaceId).toBe('surface-42');
    expect(tab?.a2uiHitlRequestId).toBe('hitl-req-1');
    expect(useLayoutModeStore.getState().mode).toBe('canvas');
  });

  it('buffers replayed request ids that appear before the canvas event', () => {
    const content = [
      '{"beginRendering":{"surfaceId":"surface-42","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"surface-42","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
    ].join('\n');

    replayCanvasEventsFromTimeline([
      {
        id: 'evt-1',
        type: 'a2ui_action_asked',
        eventTimeUs: 1,
        eventCounter: 1,
        timestamp: 1,
        block_id: 'block-1',
        request_id: 'hitl-req-buffered',
      } as any,
      {
        id: 'evt-2',
        type: 'canvas_updated',
        eventTimeUs: 2,
        eventCounter: 2,
        timestamp: 2,
        action: 'created',
        block_id: 'block-1',
        block: {
          id: 'block-1',
          block_type: 'a2ui_surface',
          title: 'Surface',
          content,
          metadata: {},
          version: 1,
        },
      } as any,
    ]);

    const tab = useCanvasStore.getState().tabs.find((item) => item.id === 'block-1');
    expect(tab?.a2uiHitlRequestId).toBe('hitl-req-buffered');
  });

  it('materializes incremental A2UI dataModel updates during replay', () => {
    const initialContent = [
      '{"beginRendering":{"surfaceId":"surface-42","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"surface-42","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
    ].join('\n');
    const incrementalContent =
      '{"dataModelUpdate":{"surfaceId":"surface-42","path":"/","contents":[{"key":"stats","valueMap":[{"key":"count","valueNumber":2}]}]}}';

    replayCanvasEventsFromTimeline([
      {
        id: 'evt-1',
        type: 'canvas_updated',
        eventTimeUs: 1,
        eventCounter: 1,
        timestamp: 1,
        action: 'created',
        block_id: 'block-1',
        block: {
          id: 'block-1',
          block_type: 'a2ui_surface',
          title: 'Surface',
          content: initialContent,
          metadata: {},
          version: 1,
        },
      } as any,
      {
        id: 'evt-2',
        type: 'canvas_updated',
        eventTimeUs: 2,
        eventCounter: 2,
        timestamp: 2,
        action: 'updated',
        block_id: 'block-1',
        block: {
          id: 'block-1',
          block_type: 'a2ui_surface',
          title: 'Surface',
          content: incrementalContent,
          metadata: {},
          version: 2,
        },
      } as any,
    ]);

    const tab = useCanvasStore.getState().tabs.find((item) => item.id === 'block-1');
    expect(tab?.a2uiSnapshot?.surfaceId).toBe('surface-42');
    expect(tab?.a2uiSnapshot?.data).toEqual({ stats: { count: 2 } });
  });
});
