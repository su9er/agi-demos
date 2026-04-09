const BEGIN_RENDERING_PATTERNS = [
  /"beginRendering"\s*:/,
  /"begin_rendering"\s*:/,
  /"type"\s*:\s*"beginRendering"/,
  /"type"\s*:\s*"begin_rendering"/,
];

const SURFACE_UPDATE_PATTERN =
  /"surfaceUpdate"\s*:|"surface_update"\s*:|"type"\s*:\s*"surfaceUpdate"|"type"\s*:\s*"surface_update"/;
const DATA_MODEL_UPDATE_PATTERN =
  /"dataModelUpdate"\s*:|"data_model_update"\s*:|"type"\s*:\s*"dataModelUpdate"|"type"\s*:\s*"data_model_update"/;
const DELETE_SURFACE_PATTERN =
  /"deleteSurface"\s*:|"delete_surface"\s*:|"type"\s*:\s*"deleteSurface"|"type"\s*:\s*"delete_surface"/;
const SURFACE_OPERATION_TYPES = new Set([
  'beginRendering',
  'begin_rendering',
  'surfaceUpdate',
  'surface_update',
  'dataModelUpdate',
  'data_model_update',
  'deleteSurface',
  'delete_surface',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function stripMarkdownCodeFence(input: string): string {
  const trimmed = input.trim();
  if (!trimmed.startsWith('```')) return trimmed;
  const lines = trimmed.split(/\r?\n/);
  if (lines.length < 3 || !lines[lines.length - 1]?.trim().startsWith('```')) {
    return trimmed;
  }
  return lines.slice(1, -1).join('\n').trim();
}

function collectEnvelopeRecords(input: unknown): Record<string, unknown>[] {
  if (Array.isArray(input)) {
    return input.filter((entry): entry is Record<string, unknown> => isRecord(entry));
  }
  if (!isRecord(input)) return [];

  if (Array.isArray(input.messages)) {
    return input.messages.filter((entry): entry is Record<string, unknown> => isRecord(entry));
  }
  const nestedData = isRecord(input.data) ? input.data : null;
  if (nestedData && Array.isArray(nestedData.messages)) {
    return nestedData.messages.filter((entry): entry is Record<string, unknown> => isRecord(entry));
  }
  return [input];
}

function tryParseJson(input: string): unknown {
  try {
    return JSON.parse(input) as unknown;
  } catch {
    return undefined;
  }
}

function extractJsonObjects(input: string): string[] {
  const objects: string[] = [];
  let startIndex = -1;
  let depth = 0;
  let inString = false;
  let escapeNext = false;

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (!char) continue;

    if (inString) {
      if (escapeNext) {
        escapeNext = false;
      } else if (char === '\\') {
        escapeNext = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }

    if (char === '"') {
      inString = true;
      continue;
    }
    if (char === '{') {
      if (depth === 0) {
        startIndex = index;
      }
      depth += 1;
      continue;
    }
    if (char !== '}') continue;

    depth -= 1;
    if (depth === 0 && startIndex >= 0) {
      objects.push(input.slice(startIndex, index + 1));
      startIndex = -1;
    }
  }

  return objects;
}

function getEnvelopeSurfaceId(envelope: Record<string, unknown>): string | undefined {
  const payloads = [
    envelope.beginRendering,
    envelope.begin_rendering,
    envelope.surfaceUpdate,
    envelope.surface_update,
    envelope.dataModelUpdate,
    envelope.data_model_update,
    envelope.deleteSurface,
    envelope.delete_surface,
  ];
  for (const payload of payloads) {
    if (!isRecord(payload)) continue;
    const surfaceId = payload.surfaceId ?? payload.surface_id;
    if (typeof surfaceId === 'string' && surfaceId) {
      return surfaceId;
    }
  }

  if (
    typeof envelope.type === 'string' &&
    SURFACE_OPERATION_TYPES.has(envelope.type) &&
    isRecord(envelope.payload)
  ) {
    const surfaceId = envelope.payload.surfaceId ?? envelope.payload.surface_id;
    if (typeof surfaceId === 'string' && surfaceId) {
      return surfaceId;
    }
  }
  return undefined;
}

export function extractA2UISurfaceId(messages?: string | null): string | undefined {
  if (!messages) return undefined;
  const normalized = stripMarkdownCodeFence(messages);
  const surfaceIds = new Set<string>();

  const parsedWhole = tryParseJson(normalized);
  if (parsedWhole !== undefined) {
    for (const envelope of collectEnvelopeRecords(parsedWhole)) {
      const surfaceId = getEnvelopeSurfaceId(envelope);
      if (surfaceId) {
        surfaceIds.add(surfaceId);
        if (surfaceIds.size > 1) return undefined;
      }
    }
    return surfaceIds.size === 1 ? [...surfaceIds][0] : undefined;
  }

  for (const line of normalized.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('```')) continue;
    const parsedLine = tryParseJson(trimmed);
    if (parsedLine === undefined) continue;
    for (const envelope of collectEnvelopeRecords(parsedLine)) {
      const surfaceId = getEnvelopeSurfaceId(envelope);
      if (surfaceId) {
        surfaceIds.add(surfaceId);
        if (surfaceIds.size > 1) return undefined;
      }
    }
  }

  if (surfaceIds.size > 0) {
    return surfaceIds.size === 1 ? [...surfaceIds][0] : undefined;
  }

  for (const chunk of extractJsonObjects(normalized)) {
    const parsedChunk = tryParseJson(chunk);
    if (parsedChunk === undefined) continue;
    for (const envelope of collectEnvelopeRecords(parsedChunk)) {
      const surfaceId = getEnvelopeSurfaceId(envelope);
      if (surfaceId) {
        surfaceIds.add(surfaceId);
        if (surfaceIds.size > 1) return undefined;
      }
    }
  }
  return surfaceIds.size === 1 ? [...surfaceIds][0] : undefined;
}

/**
 * Merge A2UI incremental update payloads into the prior message stream.
 *
 * Some canvas_update events only contain surfaceUpdate diffs (without beginRendering).
 * Replacing content with such diffs drops the root definition and causes renderer fallback.
 */
export function mergeA2UIMessageStream(
  previousMessages: string | undefined,
  incomingMessages: string
): string {
  if (!incomingMessages) return previousMessages ?? '';
  if (!previousMessages) return incomingMessages;

  const hasBeginRendering = BEGIN_RENDERING_PATTERNS.some((pattern) =>
    pattern.test(incomingMessages)
  );
  const hasDeleteSurface = DELETE_SURFACE_PATTERN.test(incomingMessages);
  const hasIncrementalUpdate =
    SURFACE_UPDATE_PATTERN.test(incomingMessages) ||
    DATA_MODEL_UPDATE_PATTERN.test(incomingMessages);
  if (hasBeginRendering || hasDeleteSurface || !hasIncrementalUpdate) {
    return incomingMessages;
  }

  return previousMessages.endsWith('\n')
    ? `${previousMessages}${incomingMessages}`
    : `${previousMessages}\n${incomingMessages}`;
}
