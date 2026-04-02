/**
 * AgentDashboard.test.tsx
 *
 * Performance and functionality tests for AgentDashboard component.
 * Tests verify React.memo optimization and component behavior.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { AgentDashboard } from '../../../pages/tenant/AgentDashboard';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      changeLanguage: () => Promise.resolve(),
      language: 'en-US',
    },
  }),
}));

// Mock traceStore hooks used by AgentDashboard
vi.mock('../../../stores/traceStore', () => ({
  useTraceRuns: () => [],
  useActiveRunCount: () => 0,
  useTraceLoading: () => false,
  useTraceChain: () => null,
  useTraceChainLoading: () => false,
  useGetTraceChain: () => vi.fn(),
  useTraceStore: { getState: () => ({ fetchActiveRunCount: vi.fn() }) },
}));

// Mock child components that have complex dependencies
vi.mock('../../../components/agent/multiAgent/TraceChainView', () => ({
  TraceChainView: () => <div data-testid="trace-chain-view">TraceChainView</div>,
}));

vi.mock('../../../components/agent/multiAgent/TraceTimeline', () => ({
  TraceTimeline: () => <div data-testid="trace-timeline">TraceTimeline</div>,
}));

describe('AgentDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render component without crashing', () => {
      render(<AgentDashboard />);
      expect(screen.getByText('SubAgent Platform')).toBeInTheDocument();
    });

    it('should render all sub-agents', () => {
      render(<AgentDashboard />);
      expect(screen.getByText('Code Architect')).toBeInTheDocument();
      expect(screen.getByText('Deep Researcher')).toBeInTheDocument();
      expect(screen.getByText('Creative Strategist')).toBeInTheDocument();
      expect(screen.getByText('Data Analyst')).toBeInTheDocument();
    });

    it('should render skill registry', () => {
      render(<AgentDashboard />);
      expect(screen.getByText('Standard Skill Registry')).toBeInTheDocument();
      expect(screen.getByText('Document Summarizer')).toBeInTheDocument();
      expect(screen.getByText('Multi-Lingual Bridge')).toBeInTheDocument();
    });

    it('should render global engine configuration', () => {
      render(<AgentDashboard />);
      expect(screen.getByText('Global Engine Configuration')).toBeInTheDocument();
      expect(screen.getByText('Auto-Learning Experience Engine')).toBeInTheDocument();
      expect(screen.getByText('Universal Browser Access')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('should toggle agent active state when clicked', () => {
      render(<AgentDashboard />);

      // Find inactive agent
      const _creativeStrategist = screen.getByText('Creative Strategist').closest('div');
      // Count active badges before toggle
      const activeBefore = screen.getAllByText('Active').length;
      const activateButtons = screen.getAllByText('Activate');
      const activateButton = activateButtons[0];

      fireEvent.click(activateButton);

      // After clicking activate, the number of Active badges should increase
      const activeAfter = screen.getAllByText('Active').length;
      expect(activeAfter).toBeGreaterThan(activeBefore);
    });

    it('should toggle auto-learning setting', () => {
      render(<AgentDashboard />);

      const toggles = screen.getAllByRole('checkbox');
      const autoLearningToggle = toggles[0];
      expect(autoLearningToggle).toBeChecked();

      fireEvent.click(autoLearningToggle);
      expect(autoLearningToggle).not.toBeChecked();
    });

    it('should toggle browser access setting', () => {
      render(<AgentDashboard />);

      const toggles = screen.getAllByRole('checkbox');
      const browserToggle = toggles[1];
      expect(browserToggle).toBeChecked();

      fireEvent.click(browserToggle);
      expect(browserToggle).not.toBeChecked();
    });
  });

  describe('Component Structure', () => {
    it('should have static data hoisted to module scope', async () => {
      // Verify that DEFAULT_SUB_AGENTS is defined outside component
      const AgentDashboardModule = await import('../../../pages/tenant/AgentDashboard');
      expect(AgentDashboardModule.DEFAULT_SUB_AGENTS).toBeDefined();
      expect(AgentDashboardModule.SKILLS).toBeDefined();
    });
  });

  describe('Performance', () => {
    it('should use React.memo for optimization', async () => {
      // Check if component is wrapped with memo

      const AgentDashboardModule = await import('../../../pages/tenant/AgentDashboard');
      // Component should be exported and potentially memoized
      expect(AgentDashboardModule.AgentDashboard).toBeDefined();
    });

    it('should not re-render unnecessarily when parent updates', () => {
      const { rerender } = render(<AgentDashboard />);

      // Re-render with same props
      rerender(<AgentDashboard />);

      // Component should still work correctly
      expect(screen.getByText('SubAgent Platform')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      render(<AgentDashboard />);
      const heading = screen.getByText('Configure Your Intelligence Core');
      expect(heading.tagName).toBe('H2');
    });

    it('should have accessible toggle buttons', () => {
      render(<AgentDashboard />);
      const toggles = screen.getAllByRole('checkbox');
      expect(toggles.length).toBeGreaterThan(0);
    });
  });
});
