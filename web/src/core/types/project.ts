/** Project identity — pure, framework-agnostic. */
export type ProjectId = string & { readonly __brand: 'ProjectId' };

export interface ProjectRef {
  id: ProjectId;
  name: string;
  tenantId: string;
}

export function projectIdOf(raw: string | number): ProjectId {
  return String(raw) as ProjectId;
}
