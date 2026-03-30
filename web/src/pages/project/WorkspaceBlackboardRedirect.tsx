import { Navigate, useParams } from 'react-router-dom';

import { useAuthStore } from '@/stores/auth';
import { useTenantStore } from '@/stores/tenant';

import { buildWorkspaceBlackboardRedirectQuery } from '@/pages/project/blackboardRouteUtils';

export function WorkspaceBlackboardRedirect() {
  const {
    tenantId: tenantIdParam,
    projectId,
    workspaceId,
  } = useParams<{
    tenantId?: string;
    projectId?: string;
    workspaceId?: string;
  }>();
  const currentTenant = useTenantStore((state) => state.currentTenant);
  const user = useAuthStore((state) => state.user);
  const tenantId = tenantIdParam ?? currentTenant?.id ?? user?.tenant_id;

  if (!tenantId) {
    return (
      <div className="flex min-h-[240px] items-center justify-center text-sm text-zinc-500">
        Loading…
      </div>
    );
  }

  const query = buildWorkspaceBlackboardRedirectQuery(workspaceId);

  return (
    <Navigate
      to={`/tenant/${tenantId}/project/${projectId ?? ''}/blackboard${query ? `?${query}` : ''}`}
      replace
    />
  );
}
