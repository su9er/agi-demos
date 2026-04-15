import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CanvasPanel } from '@/components/agent/canvas/CanvasPanel';
import { useCanvasStore } from '@/stores/canvasStore';
import { useLayoutModeStore } from '@/stores/layoutMode';

import {
  getNativeBlockFixtureCase,
  serializeNativeBlockContent,
} from '../../../fixtures/canvasNativeBlockFixtures';

vi.mock('@/components/mcp-app/StandardMCPAppRenderer', () => ({
  StandardMCPAppRenderer: () => null,
}));

vi.mock('@/components/agent/canvas/A2UISurfaceRenderer', () => ({
  A2UISurfaceRenderer: () => null,
}));

vi.mock('@/components/agent/canvas/useSyntaxHighlighter', () => ({
  useSyntaxHighlighter: () => null,
}));

describe('CanvasPanel block rendering', () => {
  beforeEach(() => {
    useCanvasStore.getState().reset();
    useLayoutModeStore.getState().setMode('canvas');
  });

  it('renders image preview from JSON payload', () => {
    useCanvasStore.getState().openTab({
      id: 'img-tab',
      title: 'Image Block',
      type: 'preview',
      content: JSON.stringify({
        url: 'https://example.com/chart-preview.png',
        mime_type: 'image/png',
      }),
    });

    render(<CanvasPanel />);

    const image = screen.getByRole('img', { name: 'Image Block' });
    expect(image).toHaveAttribute('src', 'https://example.com/chart-preview.png');
  });

  it('renders chart-style data payload as chart preview', () => {
    const fixtureCase = getNativeBlockFixtureCase('chart_top_level_datasets');
    useCanvasStore.getState().openTab({
      id: 'chart-tab',
      title: fixtureCase.title,
      type: fixtureCase.expected.frontendTabType,
      content: serializeNativeBlockContent(fixtureCase.content),
    });

    render(<CanvasPanel />);

    expect(screen.getByText('Sales')).toBeInTheDocument();
    expect(screen.getByText('Jan')).toBeInTheDocument();
    expect(screen.getByText('Feb')).toBeInTheDocument();
  });

  it('blocks unsafe media URLs from image payloads', () => {
    useCanvasStore.getState().openTab({
      id: 'unsafe-image-tab',
      title: 'Unsafe Image Block',
      type: 'preview',
      content: JSON.stringify({
        url: 'javascript:alert(1)',
        mime_type: 'image/png',
      }),
    });

    render(<CanvasPanel />);

    expect(screen.queryByRole('img', { name: 'Unsafe Image Block' })).not.toBeInTheDocument();
    expect(screen.getByText('Invalid media URL')).toBeInTheDocument();
  });

  it('blocks unsafe file URLs from office preview payloads', () => {
    useCanvasStore.getState().openTab({
      id: 'unsafe-office-tab',
      title: 'report.docx',
      type: 'preview',
      content: JSON.stringify({
        url: 'javascript:alert(1)',
      }),
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });

    render(<CanvasPanel />);

    expect(screen.queryByRole('link', { name: 'Download File' })).not.toBeInTheDocument();
    expect(screen.getByText('Invalid file URL')).toBeInTheDocument();
  });

  it('renders form-style data payload as read-only form preview', () => {
    useCanvasStore.getState().openTab({
      id: 'form-tab',
      title: 'Form Block',
      type: 'data',
      content: JSON.stringify({
        fields: [
          { name: 'email', label: 'Email', type: 'text', required: true },
          { name: 'plan', label: 'Plan', type: 'select', options: ['Free', 'Pro'] },
        ],
      }),
    });

    render(<CanvasPanel />);

    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Read-only form preview')).toBeInTheDocument();
  });

  it('normalizes chart series aliases and generates fallback labels', () => {
    const fixtureCase = getNativeBlockFixtureCase('chart_series_alias_generated_labels');
    useCanvasStore.getState().openTab({
      id: 'series-chart-tab',
      title: fixtureCase.title,
      type: fixtureCase.expected.frontendTabType,
      content: serializeNativeBlockContent(fixtureCase.content),
    });

    render(<CanvasPanel />);

    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('Cost')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('falls back to pretty-printed JSON when chart payloads are not renderable', () => {
    const fixtureCase = getNativeBlockFixtureCase('chart_invalid_payload_json_fallback');
    useCanvasStore.getState().openTab({
      id: 'broken-chart-tab',
      title: fixtureCase.title,
      type: fixtureCase.expected.frontendTabType,
      content: serializeNativeBlockContent(fixtureCase.content),
    });

    render(<CanvasPanel />);

    expect(screen.getByText(/"label": "Broken"/)).toBeInTheDocument();
    expect(screen.getByText(/"oops"/)).toBeInTheDocument();
  });

  it('renders widget HTML payloads in the isolated preview iframe path', () => {
    const fixtureCase = getNativeBlockFixtureCase('widget_html_preview');
    useCanvasStore.getState().openTab({
      id: 'widget-html-tab',
      title: fixtureCase.title,
      type: fixtureCase.expected.frontendTabType,
      content: serializeNativeBlockContent(fixtureCase.content),
    });

    render(<CanvasPanel />);

    expect(screen.getByTitle(fixtureCase.title)).toBeInTheDocument();
  });

  it('renders widget image payloads through preview media handling', () => {
    const fixtureCase = getNativeBlockFixtureCase('widget_image_preview');
    useCanvasStore.getState().openTab({
      id: 'widget-image-tab',
      title: fixtureCase.title,
      type: fixtureCase.expected.frontendTabType,
      content: serializeNativeBlockContent(fixtureCase.content),
    });

    render(<CanvasPanel />);

    const image = screen.getByRole('img', { name: fixtureCase.title });
    expect(image).toHaveAttribute('src', fixtureCase.expected.imageSrc);
  });
});
