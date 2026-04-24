import { waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SharedFileBrowser } from '@/components/blackboard/tabs/SharedFileBrowser';
import { render, screen } from '@/test/utils';

const listFilesMock = vi.fn();

vi.mock('@/services/blackboardFileService', () => ({
  blackboardFileService: {
    listFiles: (...args: unknown[]) => listFilesMock(...args),
    createDirectory: vi.fn(),
    uploadFile: vi.fn(),
    downloadFile: vi.fn(),
    deleteFile: vi.fn(),
  },
}));

describe('SharedFileBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listFilesMock.mockResolvedValue([]);
  });

  it('marks the file browser as an owned authoritative surface', async () => {
    render(<SharedFileBrowser tenantId="t-1" projectId="p-1" workspaceId="ws-1" />);

    await waitFor(() => {
      expect(listFilesMock).toHaveBeenCalledWith('t-1', 'p-1', 'ws-1', '/');
    });

    const boundaryBadge = screen.getByText('blackboard.filesSurfaceHint').closest('div');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-boundary', 'owned');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-authority', 'authoritative');
  });
});
