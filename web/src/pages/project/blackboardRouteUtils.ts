export function syncBlackboardWorkspaceSearchParams(
  searchParams: URLSearchParams,
  options: {
    selectedWorkspaceId: string | null;
    workspacesLoading: boolean;
  }
): URLSearchParams | null {
  const currentQueryWorkspaceId = searchParams.get('workspaceId');

  if (!options.selectedWorkspaceId) {
    if (!currentQueryWorkspaceId || options.workspacesLoading) {
      return null;
    }

    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.delete('workspaceId');
    nextSearchParams.delete('open');
    return nextSearchParams;
  }

  if (currentQueryWorkspaceId === options.selectedWorkspaceId) {
    return null;
  }

  const nextSearchParams = new URLSearchParams(searchParams);
  nextSearchParams.set('workspaceId', options.selectedWorkspaceId);
  nextSearchParams.delete('open');
  return nextSearchParams;
}

export function clearBlackboardAutoOpenSearchParam(
  searchParams: URLSearchParams
): URLSearchParams | null {
  if (!searchParams.has('open')) {
    return null;
  }

  const nextSearchParams = new URLSearchParams(searchParams);
  nextSearchParams.delete('open');
  return nextSearchParams;
}

export function resolveRequestedWorkspaceSelection(
  requestedWorkspaceId: string | null,
  appliedRequestedWorkspaceId: string | null,
  workspaces: Array<{ id: string }>
): string | null {
  if (!requestedWorkspaceId || requestedWorkspaceId === appliedRequestedWorkspaceId) {
    return null;
  }

  return workspaces.some((workspace) => workspace.id === requestedWorkspaceId)
    ? requestedWorkspaceId
    : null;
}

export function buildWorkspaceBlackboardRedirectQuery(workspaceId?: string): string {
  const params = new URLSearchParams();

  if (workspaceId) {
    params.set('workspaceId', workspaceId);
    params.set('open', '1');
  }

  return params.toString();
}
