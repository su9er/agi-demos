export function buildAgentWorkspacePath({
  tenantId,
  conversationId,
  projectId,
  workspaceId,
}: {
  tenantId?: string | undefined;
  conversationId?: string | undefined;
  projectId?: string | undefined;
  workspaceId?: string | null | undefined;
}): string {
  const basePath = tenantId ? `/tenant/${tenantId}/agent-workspace` : '/tenant/agent-workspace';
  const conversationPath = conversationId ? `${basePath}/${conversationId}` : basePath;
  const params = new URLSearchParams();
  if (projectId) params.set('projectId', projectId);
  if (workspaceId) params.set('workspaceId', workspaceId);
  const query = params.toString();
  return query ? `${conversationPath}?${query}` : conversationPath;
}
