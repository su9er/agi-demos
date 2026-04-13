const BEGIN_RENDERING_PATTERN = /"beginRendering"\s*:/;
const SURFACE_UPDATE_PATTERN = /"surfaceUpdate"\s*:/;
const DATA_MODEL_UPDATE_PATTERN = /"dataModelUpdate"\s*:/;
const DELETE_SURFACE_PATTERN = /"deleteSurface"\s*:/;

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
  return [input];
}

function tryParseJson(input: string): unknown {
  try {
    return JSON.parse(input) as unknown;
  } catch {
    return undefined;
  }
}

function extractJsonObjectSpans(input: string): Array<{ start: number; end: number }> {
  const spans: Array<{ start: number; end: number }> = [];
  let depth = 0;
  let start = -1;
  let inString = false;
  let escaped = false;

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (!char) continue;

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
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
      if (depth === 0) start = index;
      depth += 1;
      continue;
    }

    if (char === '}' && depth > 0) {
      depth -= 1;
      if (depth === 0 && start >= 0) {
        spans.push({ start, end: index + 1 });
        start = -1;
      }
    }
  }

  return spans;
}

function getEnvelopeSurfaceId(envelope: Record<string, unknown>): string | undefined {
  const payloads = [
    envelope.beginRendering,
    envelope.surfaceUpdate,
    envelope.dataModelUpdate,
    envelope.deleteSurface,
  ];
  for (const payload of payloads) {
    if (!isRecord(payload)) continue;
    const surfaceId = payload.surfaceId;
    if (typeof surfaceId === 'string' && surfaceId) {
      return surfaceId;
    }
  }
  return undefined;
}

function getEnvelopePayload(
  envelope: Record<string, unknown>,
  key: 'beginRendering' | 'surfaceUpdate' | 'dataModelUpdate' | 'deleteSurface'
): Record<string, unknown> | null {
  const payload = envelope[key];
  return isRecord(payload) ? payload : null;
}

function collectParsedEnvelopeRecords(messages?: string | null): Record<string, unknown>[] {
  if (!messages) return [];
  const normalized = stripMarkdownCodeFence(messages);
  if (!normalized) return [];

  const parsedWhole = tryParseJson(normalized);
  if (parsedWhole !== undefined) {
    return collectEnvelopeRecords(parsedWhole);
  }

  const lines = normalized.split(/\r?\n/);
  if (lines.length > 1) {
    const lineRecords: Record<string, unknown>[] = [];
    let lineParseFailed = false;
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('```')) continue;
      const parsedLine = tryParseJson(trimmed);
      if (parsedLine === undefined) {
        lineParseFailed = true;
        break;
      }
      lineRecords.push(...collectEnvelopeRecords(parsedLine));
    }
    if (!lineParseFailed && lineRecords.length > 0) return lineRecords;
  }

  const objectRecords: Record<string, unknown>[] = [];
  const spans = extractJsonObjectSpans(normalized);
  let cursor = 0;
  for (const span of spans) {
    if (normalized.slice(cursor, span.start).trim()) return [];
    const parsedChunk = tryParseJson(normalized.slice(span.start, span.end));
    if (parsedChunk === undefined) return [];
    objectRecords.push(...collectEnvelopeRecords(parsedChunk));
    cursor = span.end;
  }
  if (normalized.slice(cursor).trim()) return [];
  return objectRecords;
}

interface A2UIMessageStreamState {
  surfaceId: string | undefined;
  root: string | undefined;
  styles: Record<string, unknown> | undefined;
  componentsById: Map<string, Record<string, unknown>>;
  dataRecords: Array<Record<string, unknown>>;
}

function createMessageStreamState(): A2UIMessageStreamState {
  return {
    surfaceId: undefined,
    root: undefined,
    styles: undefined,
    componentsById: new Map<string, Record<string, unknown>>(),
    dataRecords: [],
  };
}

function buildDataRecord(
  dataModelUpdate: Record<string, unknown> | null
): Record<string, unknown> | null {
  if (!dataModelUpdate) return null;
  return { dataModelUpdate: { ...dataModelUpdate } };
}

function applyEnvelopeToState(
  state: A2UIMessageStreamState,
  envelope: Record<string, unknown>
): void {
  const beginRendering = getEnvelopePayload(envelope, 'beginRendering');
  const surfaceUpdate = getEnvelopePayload(envelope, 'surfaceUpdate');
  const dataModelUpdate = getEnvelopePayload(envelope, 'dataModelUpdate');
  const deleteSurface = getEnvelopePayload(envelope, 'deleteSurface');
  const envelopeSurfaceId = getEnvelopeSurfaceId(envelope);

  if (envelopeSurfaceId) {
    state.surfaceId = envelopeSurfaceId;
  }

  if (deleteSurface) {
    state.root = undefined;
    state.styles = undefined;
    state.componentsById.clear();
    state.dataRecords = [];
    return;
  }

  if (beginRendering) {
    if (typeof beginRendering.root === 'string' && beginRendering.root) {
      state.root = beginRendering.root;
    }
    if (isRecord(beginRendering.styles)) {
      state.styles = { ...beginRendering.styles };
    }
  }

  const componentSource = surfaceUpdate?.components;
  if (Array.isArray(componentSource)) {
    for (const rawComponent of componentSource) {
      if (!isRecord(rawComponent)) continue;
      if (typeof rawComponent.id !== 'string' || !rawComponent.id) continue;
      state.componentsById.set(rawComponent.id, rawComponent);
    }
  }

  const dataRecord = buildDataRecord(dataModelUpdate);
  if (dataRecord) {
    state.dataRecords.push(dataRecord);
  }
}

function serializeMessageStreamState(state: A2UIMessageStreamState): string {
  const records: Array<Record<string, unknown>> = [];
  if (state.root) {
    records.push({
      beginRendering: {
        ...(state.surfaceId ? { surfaceId: state.surfaceId } : {}),
        root: state.root,
        ...(state.styles ? { styles: state.styles } : {}),
      },
    });
  }

  if (state.componentsById.size > 0) {
    records.push({
      surfaceUpdate: {
        ...(state.surfaceId ? { surfaceId: state.surfaceId } : {}),
        components: [...state.componentsById.values()],
      },
    });
  }

  records.push(...state.dataRecords);
  return records.map((record) => JSON.stringify(record)).join('\n');
}

function extractSingleSurfaceId(records: Record<string, unknown>[]): string | undefined {
  const surfaceIds = new Set<string>();
  for (const envelope of records) {
    const surfaceId = getEnvelopeSurfaceId(envelope);
    if (!surfaceId) continue;
    surfaceIds.add(surfaceId);
    if (surfaceIds.size > 1) return undefined;
  }
  return surfaceIds.size === 1 ? [...surfaceIds][0] : undefined;
}

export function extractA2UISurfaceId(messages?: string | null): string | undefined {
  return extractSingleSurfaceId(collectParsedEnvelopeRecords(messages));
}

export function mergeA2UIMessageStream(
  previousMessages: string | undefined,
  incomingMessages: string
): string {
  if (!incomingMessages) return previousMessages ?? '';
  if (!previousMessages) return incomingMessages;

  const hasBeginRendering = BEGIN_RENDERING_PATTERN.test(incomingMessages);
  const hasDeleteSurface = DELETE_SURFACE_PATTERN.test(incomingMessages);
  const hasIncrementalUpdate =
    SURFACE_UPDATE_PATTERN.test(incomingMessages) ||
    DATA_MODEL_UPDATE_PATTERN.test(incomingMessages);
  if (hasBeginRendering || hasDeleteSurface || !hasIncrementalUpdate) {
    return incomingMessages;
  }

  const previousRecords = collectParsedEnvelopeRecords(previousMessages);
  const incomingRecords = collectParsedEnvelopeRecords(incomingMessages);
  if (previousRecords.length === 0 || incomingRecords.length === 0) {
    return incomingMessages;
  }

  const previousSurfaceId = extractSingleSurfaceId(previousRecords);
  const incomingSurfaceId = extractSingleSurfaceId(incomingRecords);
  if (!previousSurfaceId || !incomingSurfaceId || previousSurfaceId !== incomingSurfaceId) {
    return incomingMessages;
  }

  const state = createMessageStreamState();
  for (const record of previousRecords) {
    applyEnvelopeToState(state, record);
  }
  for (const record of incomingRecords) {
    applyEnvelopeToState(state, record);
  }

  const serialized = serializeMessageStreamState(state);
  return serialized || incomingMessages;
}
