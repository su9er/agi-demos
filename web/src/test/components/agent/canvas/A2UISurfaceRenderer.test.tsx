import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';

const { viewerSpy, respondToA2UIActionSpy, viewerThrowState } = vi.hoisted(() => ({
  viewerSpy: vi.fn(),
  respondToA2UIActionSpy: vi.fn().mockResolvedValue(undefined),
  viewerThrowState: { enabled: false },
}));

vi.mock('@copilotkit/a2ui-renderer', () => ({
  A2UIViewer: (props: unknown) => {
    viewerSpy(props);
    if (viewerThrowState.enabled) {
      throw new Error('mock a2ui viewer failure');
    }
    return null;
  },
}));

vi.mock('@/services/agentService', () => ({
  agentService: {
    respondToA2UIAction: respondToA2UIActionSpy,
  },
}));

import { A2UISurfaceRenderer } from '@/components/agent/canvas/A2UISurfaceRenderer';
import { useAgentV3Store } from '@/stores/agentV3';
import { useCanvasStore } from '@/stores/canvasStore';

describe('A2UISurfaceRenderer', () => {
  const components = [
    {
      id: 'root-1',
      component: {
        Text: {
          text: { literal: 'hello' },
        },
      },
    },
  ];
  const waitingText = 'Waiting for A2UI surface data...';

  beforeEach(() => {
    viewerSpy.mockClear();
    respondToA2UIActionSpy.mockClear();
    viewerThrowState.enabled = false;
    useAgentV3Store.setState({ activeConversationId: null });
    useCanvasStore.setState({ tabs: [], activeTabId: null });
    delete (Object.prototype as Record<string, unknown>).polluted;
  });

  it('renders strict JSONL envelopes', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"s1","components":${JSON.stringify(components)}}}`,
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: 'root-1',
      components,
    });
  });

  it('renders fenced multi-line JSON objects', () => {
    const messages = `\`\`\`json
{"beginRendering":{"surfaceId":"s1","root":"root-1"}}
{"surfaceUpdate":{"surfaceId":"s1","components":${JSON.stringify(components)}}}
\`\`\``;

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: 'root-1',
      components,
    });
  });

  it('renders a JSON array envelope payload', () => {
    const messages = JSON.stringify([
      { beginRendering: { surfaceId: 's1', root: 'root-1' } },
      { surfaceUpdate: { surfaceId: 's1', components } },
    ]);

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: 'root-1',
      components,
    });
  });

  it('renders legacy type-based component payloads from interactive canvas events', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root"}}',
      JSON.stringify({
        surfaceUpdate: {
          surfaceId: 's1',
          components: [
            {
              id: 'root',
              type: 'Column',
              children: ['title', 'input', 'submit', 'submit-label'],
              gap: 16,
              alignItems: 'stretch',
            },
            {
              id: 'title',
              type: 'Text',
              text: { literal: 'Legacy A2UI payload' },
              fontSize: 24,
            },
            {
              id: 'input',
              type: 'TextField',
              label: { literal: 'Name' },
              text: { path: '/form/name' },
            },
            {
              id: 'submit',
              type: 'Button',
              child: 'submit-label',
              action: { name: 'submit_form' },
            },
            {
              id: 'submit-label',
              type: 'Text',
              text: { literal: 'Submit' },
            },
          ],
        },
      }),
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          root?: string;
          components?: Array<{ id: string; component: Record<string, unknown> }>;
        }
      | undefined;
    expect(props?.root).toBe('root');
    const rootComponent = props?.components?.find((entry) => entry.id === 'root')?.component?.Column as
      | { children?: { explicitList?: string[] } }
      | undefined;
    const textFieldComponent = props?.components?.find((entry) => entry.id === 'input')?.component
      ?.TextField as { text?: { path?: string } } | undefined;
    expect(rootComponent?.children?.explicitList).toEqual([
      'title',
      'input',
      'submit',
      'submit-label',
    ]);
    expect(textFieldComponent?.text?.path).toBe('/form/name');
    expect(Object.keys(props?.components?.[0] ?? {})).toEqual(['id', 'component']);
  });

  it('renders snake_case and typed envelope variants', () => {
    const messages = [
      '{"begin_rendering":{"surface_id":"s1","root":"root-1"}}',
      `{"type":"surface_update","payload":{"surface_id":"s1","components":${JSON.stringify(components)}}}`,
      '{"data_model_update":{"surface_id":"s1","path":"/","contents":[{"status":"ok"}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: 'root-1',
      components,
      data: { status: 'ok' },
    });
  });

  it('renders flat single-object payloads with top-level components and dataModel', async () => {
    const messages = JSON.stringify({
      beginRendering: { surfaceId: 'server-surface', root: 'root' },
      surfaceUpdate: { surfaceId: 'server-surface' },
      dataModel: { form: { selected: 'request_env_var' } },
      components: [
        {
          id: 'root',
          component: {
            Column: {
              children: ['title', 'button', 'button-text'],
            },
          },
        },
        {
          id: 'title',
          component: {
            Text: {
              text: { literal: '选择测试项' },
            },
          },
        },
        {
          id: 'button',
          component: {
            Button: {
              child: 'button-text',
              action: {
                name: 'select_tool',
                context: {
                  tool: 'request_env_var',
                },
              },
            },
          },
        },
        {
          id: 'button-text',
          component: {
            Text: {
              text: { literal: 'request_env_var' },
            },
          },
        },
      ],
    });

    useAgentV3Store.setState({ activeConversationId: 'conv-1' });
    useCanvasStore.setState({
      tabs: [
        {
          id: 'a2ui-tab-1',
          title: 'A2UI',
          type: 'a2ui-surface',
          content: '',
          dirty: false,
          createdAt: Date.now(),
          history: [],
          historyIndex: -1,
          a2uiSurfaceId: 'server-surface',
          a2uiHitlRequestId: 'hitl-req-1',
        },
      ],
      activeTabId: 'a2ui-tab-1',
    });

    render(<A2UISurfaceRenderer surfaceId="server-surface" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          root?: string;
          data?: Record<string, unknown>;
          onAction?: (action: {
            actionName: string;
            sourceComponentId: string;
            timestamp: string;
            context: Record<string, unknown>;
          }) => void;
        }
      | undefined;
    expect(props?.root).toBe('root');
    expect(props?.data).toMatchObject({
      form: {
        selected: 'request_env_var',
      },
    });

    await act(async () => {
      props?.onAction?.({
        actionName: 'select_tool',
        sourceComponentId: 'button',
        timestamp: new Date().toISOString(),
        context: { tool: 'request_env_var' },
      });
    });

    await waitFor(() => {
      expect(respondToA2UIActionSpy).toHaveBeenCalledWith(
        'hitl-req-1',
        'select_tool',
        'button',
        {
          tool: 'request_env_var',
        }
      );
    });
  });

  it('falls back to the only discovered surfaceId when prop id mismatches', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"server-surface","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"server-surface","components":${JSON.stringify(components)}}}`,
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="client-tab-id" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: 'root-1',
      components,
    });
  });

  it('keeps waiting when multiple mismatched surfaceIds are mixed', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s2","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"s2","components":${JSON.stringify(components)}}}`,
      '{"beginRendering":{"surfaceId":"s3","root":"root-2"}}',
      `{"surfaceUpdate":{"surfaceId":"s3","components":${JSON.stringify(components)}}}`,
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.getByText(waitingText)).toBeInTheDocument();
    expect(viewerSpy).not.toHaveBeenCalled();
  });

  it('blocks prototype-polluting keys in data updates', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"s1","components":${JSON.stringify(components)}}}`,
      '{"dataModelUpdate":{"surfaceId":"s1","path":"/","contents":[{"safe":"ok"},{"__proto__":{"polluted":"yes"}}]}}',
      '{"dataModelUpdate":{"surfaceId":"s1","path":"/__proto__","contents":[{"polluted":"yes"}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    const props = viewerSpy.mock.calls[0]?.[0] as { data?: Record<string, unknown> } | undefined;
    expect(props?.data).toMatchObject({ safe: 'ok' });
    expect((Object.prototype as Record<string, unknown>).polluted).toBeUndefined();
  });

  it('dispatches actions with resolved fallback surface context', async () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"server-surface","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"server-surface","components":${JSON.stringify(components)}}}`,
    ].join('\n');

    useAgentV3Store.setState({ activeConversationId: 'conv-1' });
    useCanvasStore.setState({
      tabs: [
        {
          id: 'a2ui-tab-1',
          title: 'A2UI',
          type: 'a2ui-surface',
          content: '',
          dirty: false,
          createdAt: Date.now(),
          history: [],
          historyIndex: -1,
          a2uiSurfaceId: 'server-surface',
          a2uiHitlRequestId: 'hitl-req-1',
        },
      ],
      activeTabId: 'a2ui-tab-1',
    });

    render(<A2UISurfaceRenderer surfaceId="client-tab-id" messages={messages} />);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          onAction?: (action: {
            actionName: string;
            sourceComponentId: string;
            timestamp: string;
            context: Record<string, unknown>;
          }) => void;
        }
      | undefined;

    await act(async () => {
      props?.onAction?.({
        actionName: 'approve',
        sourceComponentId: 'btn-1',
        timestamp: new Date().toISOString(),
        context: { ok: true },
      });
    });

    await waitFor(() => {
      expect(respondToA2UIActionSpy).toHaveBeenCalledWith('hitl-req-1', 'approve', 'btn-1', {
        ok: true,
      });
    });
  });

  it('shows an inline error and skips dispatch when HITL request_id is missing', async () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"server-surface","root":"root-1"}}',
      `{"surfaceUpdate":{"surfaceId":"server-surface","components":${JSON.stringify(components)}}}`,
    ].join('\n');

    useAgentV3Store.setState({ activeConversationId: 'conv-1' });
    useCanvasStore.setState({
      tabs: [
        {
          id: 'a2ui-tab-1',
          title: 'A2UI',
          type: 'a2ui-surface',
          content: '',
          dirty: false,
          createdAt: Date.now(),
          history: [],
          historyIndex: -1,
          a2uiSurfaceId: 'server-surface',
        },
      ],
      activeTabId: 'a2ui-tab-1',
    });

    render(<A2UISurfaceRenderer surfaceId="client-tab-id" messages={messages} />);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          onAction?: (action: {
            actionName: string;
            sourceComponentId: string;
            timestamp: string;
            context: Record<string, unknown>;
          }) => void;
        }
      | undefined;

    props?.onAction?.({
      actionName: 'approve',
      sourceComponentId: 'btn-1',
      timestamp: new Date().toISOString(),
      context: { ok: true },
    });

    expect(respondToA2UIActionSpy).not.toHaveBeenCalled();
    expect(
      await screen.findByText('This interactive surface is no longer awaiting input.')
    ).toBeInTheDocument();
  });

  it('repairs malformed surfaceUpdate-only payloads and infers a synthetic root', () => {
    const messages =
      '{"surfaceUpdate":{"components":[{"id":"rev-value","component":{"Text":{"literal":"¥145,230"},"style":{"fontSize":"28px","fontWeight":"bold","color":"#10b981"}}}},{"id":"rev-change","component":{"Text":{"literal":"↑ 15.8%"},"style":{"fontSize":"14px","color":"#10b981"}}}}]}}';

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: '__a2ui_auto_root',
    });
  });

  it('normalizes Text literal + sibling style component payloads', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"t1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"t1","component":{"Text":{"literal":"hello"},"style":{"color":"#10b981"}}}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          components?: Array<{ id: string; component: Record<string, unknown> }>;
        }
      | undefined;
    const first = props?.components?.[0];
    const textPayload = first?.component?.Text as
      | { text?: { literal?: string }; style?: { color?: string } }
      | undefined;
    expect(textPayload?.text?.literal).toBe('hello');
    expect(textPayload?.style?.color).toBe('#10b981');
  });

  it('rebuilds root when beginRendering root component is missing after partial updates', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"missing-root"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"t1","component":{"Text":{"text":{"literal":"hello"}}}},{"id":"t2","component":{"Text":{"text":{"literal":"world"}}}}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: '__a2ui_auto_root',
    });
  });

  it('falls back to text-only surface when component schema is invalid', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"row-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"row-1","component":{"Row":{"gap":"8px"}}},{"id":"t1","component":{"Text":{"literal":"hello"}}}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      root: '__a2ui_text_fallback_root',
    });
  });

  it('normalizes legacy TextField value and onChange payloads into text bindings', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"field-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"field-1","component":{"TextField":{"label":{"literal":"Name"},"value":"Alice","onChange":{"name":"form/name"}}}}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    const props = viewerSpy.mock.calls[0]?.[0] as
      | {
          components?: Array<{ id: string; component: Record<string, unknown> }>;
        }
      | undefined;
    const textFieldPayload = props?.components?.[0]?.component?.TextField as
      | { text?: { path?: string; literal?: string } }
      | undefined;
    expect(textFieldPayload?.text).toMatchObject({
      path: '/form/name',
      literal: 'Alice',
    });
  });

  it('supports A2UI valueMap data updates and path-bound string values', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"field-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"field-1","component":{"TextField":{"label":{"path":"/labels/name"},"text":{"path":"/form/name"}}}}]}}',
      '{"dataModelUpdate":{"surfaceId":"s1","path":"/","contents":[{"key":"labels","valueMap":[{"key":"name","valueString":"Name"}]},{"key":"form","valueMap":[{"key":"name","valueString":"Alice"}]},{"key":"profile","valueMap":[{"key":"nickname"}]},{"key":"items","valueMap":[{"key":"0","valueString":"a"},{"key":"1","valueString":"b"}]},{"key":"rawJson","valueString":"[1,2]"}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.queryByText(waitingText)).not.toBeInTheDocument();
    expect(viewerSpy).toHaveBeenCalledTimes(1);
    expect(viewerSpy.mock.calls[0]?.[0]).toMatchObject({
      data: {
        labels: { name: 'Name' },
        form: { name: 'Alice' },
        profile: { nickname: null },
        items: ['a', 'b'],
        rawJson: '[1,2]',
      },
    });
  });

  it('clears rendered state after deleteSurface', () => {
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello"}}}}]}}',
      '{"deleteSurface":{"surfaceId":"s1"}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.getByText(waitingText)).toBeInTheDocument();
    expect(viewerSpy).not.toHaveBeenCalled();
  });

  it('shows text fallback when A2UIViewer throws', () => {
    viewerThrowState.enabled = true;
    const messages = [
      '{"beginRendering":{"surfaceId":"s1","root":"root-1"}}',
      '{"surfaceUpdate":{"surfaceId":"s1","components":[{"id":"root-1","component":{"Text":{"text":{"literal":"hello fallback"}}}}]}}',
    ].join('\n');

    render(<A2UISurfaceRenderer surfaceId="s1" messages={messages} />);
    expect(screen.getByText('hello fallback')).toBeInTheDocument();
    expect(screen.queryByText('A2UI render error')).not.toBeInTheDocument();
  });
});
