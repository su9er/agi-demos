import type { ModelCatalogEntry } from '@/types/memory';

export const normalizeProviderType = (providerType?: string): string | undefined => {
  if (!providerType) return undefined;
  return providerType.replace(/_coding$/, '').toLowerCase();
};

/**
 * Find the catalog entry that best matches a configured model name.
 *
 * Supports exact and suffix/prefix ("openai/gpt-4o" <-> "gpt-4o") matching.
 * Keep this strict to align with backend model resolution behavior.
 */
export const findModelInCatalog = (
  modelName: string,
  catalog: ModelCatalogEntry[]
): ModelCatalogEntry | null => {
  if (!modelName || catalog.length === 0) return null;

  const lower = modelName.toLowerCase();

  const exact = catalog.find((m) => m.name.toLowerCase() === lower);
  if (exact) return exact;

  const suffix = catalog.find((m) => m.name.toLowerCase().endsWith(`/${lower}`));
  if (suffix) return suffix;

  const prefix = catalog.find((m) => lower.endsWith(`/${m.name.toLowerCase()}`));
  if (prefix) return prefix;
  return null;
};

/**
 * Resolve canonical provider hint for filtering/validation.
 *
 * Prefer provider from the default model's catalog metadata when available,
 * and fall back to normalized provider type.
 */
export const resolveCatalogProviderHint = (
  catalog: ModelCatalogEntry[],
  defaultModelName?: string | null,
  providerType?: string
): string | undefined => {
  const normalizedDefaultModel = defaultModelName?.trim();
  const defaultModelMeta = normalizedDefaultModel
    ? findModelInCatalog(normalizedDefaultModel, catalog)
    : null;
  return defaultModelMeta?.provider?.toLowerCase() || normalizeProviderType(providerType);
};
