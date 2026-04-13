import { memo, useMemo } from 'react';

import type { CSSProperties } from 'react';

import { useA2UIActions, useA2UIState } from './a2uiInternals';
import {
  normalizeNumberValue,
  normalizeStringValue,
  normalizeStyle,
  resolveBoundNumberValue,
  resolveBoundStringValue,
  type StringValue,
} from './a2uiCustomUtils';

interface TableColumn {
  header?: StringValue | string;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

interface TableRow {
  key?: string;
  cells?: unknown[];
}

interface TableProperties {
  caption?: StringValue | string;
  emptyText?: StringValue | string;
  columns?: Array<TableColumn | string>;
  rows?: Array<TableRow | unknown[]>;
  style?: Record<string, unknown>;
}

type TableNode = Record<string, unknown> & {
  id: string;
  dataContextPath?: string;
  weight?: number;
  properties?: TableProperties;
};

interface ResolvedColumn {
  key: string;
  header: string;
  align: 'left' | 'center' | 'right';
  width?: string;
}

interface ResolvedRow {
  key: string;
  cells: string[];
}

function resolveCellValue(
  input: unknown,
  node: TableNode,
  surfaceId: string,
  actions: ReturnType<typeof useA2UIActions>
): string {
  if (typeof input === 'string') {
    return input;
  }
  if (typeof input === 'number' && Number.isFinite(input)) {
    return String(input);
  }
  if (typeof input === 'boolean') {
    return input ? 'true' : 'false';
  }

  const resolvedString = resolveBoundStringValue(input, node, surfaceId, actions);
  if (typeof resolvedString === 'string') {
    return resolvedString;
  }

  const resolvedNumber = resolveBoundNumberValue(input, node, surfaceId, actions);
  if (typeof resolvedNumber === 'number') {
    return String(resolvedNumber);
  }

  if (normalizeNumberValue(input) || normalizeStringValue(input)) {
    return '';
  }

  if (input && typeof input === 'object' && !Array.isArray(input)) {
    const record = input as Record<string, unknown>;
    if (typeof record.literalBoolean === 'boolean') {
      return record.literalBoolean ? 'true' : 'false';
    }
    if (typeof record.literal === 'boolean') {
      return record.literal ? 'true' : 'false';
    }
  }

  return '';
}

function normalizeColumns(
  input: TableProperties['columns'],
  node: TableNode,
  surfaceId: string,
  actions: ReturnType<typeof useA2UIActions>
): ResolvedColumn[] {
  if (!Array.isArray(input)) {
    return [];
  }

  const normalizedColumns: ResolvedColumn[] = [];
  input.forEach((column, index) => {
    if (typeof column === 'string') {
      normalizedColumns.push({ key: `column-${index}`, header: column, align: 'left' });
      return;
    }
    if (!column || typeof column !== 'object' || Array.isArray(column)) {
      return;
    }

    const header = resolveBoundStringValue(column.header, node, surfaceId, actions);
    if (!header) {
      return;
    }
    normalizedColumns.push({
      key: `column-${index}`,
      header,
      align: column.align ?? 'left',
      ...(typeof column.width === 'string' ? { width: column.width } : {}),
    });
  });
  return normalizedColumns;
}

function normalizeRows(
  input: TableProperties['rows'],
  node: TableNode,
  surfaceId: string,
  actions: ReturnType<typeof useA2UIActions>
): ResolvedRow[] {
  if (!Array.isArray(input)) {
    return [];
  }

  return input.flatMap((row, rowIndex) => {
    const rawCells = Array.isArray(row)
      ? row
      : row && typeof row === 'object' && !Array.isArray(row)
        ? row.cells
        : undefined;
    if (!Array.isArray(rawCells)) {
      return [];
    }

    return [
      {
        key:
          row && typeof row === 'object' && !Array.isArray(row) && typeof row.key === 'string'
            ? row.key
            : `row-${rowIndex}`,
        cells: rawCells.map((cell) => resolveCellValue(cell, node, surfaceId, actions)),
      },
    ];
  });
}

export const A2UITable = memo(function A2UITable({
  node,
  surfaceId,
}: {
  node: TableNode;
  surfaceId: string;
}) {
  const actions = useA2UIActions();
  const { version } = useA2UIState();

  const props = (node.properties ?? {}) as TableProperties;
  const caption = useMemo(
    () => resolveBoundStringValue(props.caption, node, surfaceId, actions),
    [actions, node, props.caption, surfaceId, version]
  );
  const emptyText = useMemo(
    () => resolveBoundStringValue(props.emptyText, node, surfaceId, actions) ?? 'No data',
    [actions, node, props.emptyText, surfaceId, version]
  );
  const columns = useMemo(
    () => normalizeColumns(props.columns, node, surfaceId, actions),
    [actions, node, props.columns, surfaceId, version]
  );
  const rows = useMemo(
    () => normalizeRows(props.rows, node, surfaceId, actions),
    [actions, node, props.rows, surfaceId, version]
  );

  const rootStyle =
    node.weight !== undefined ? ({ '--weight': node.weight } as CSSProperties) : undefined;
  const sectionStyle = useMemo(
    () =>
      ({
        overflowX: 'auto',
        ...normalizeStyle(props.style),
      }) satisfies CSSProperties,
    [props.style]
  );

  if (columns.length === 0) {
    return null;
  }

  return (
    <div className="a2ui-table" style={rootStyle}>
      <section style={sectionStyle}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            borderSpacing: 0,
            fontSize: '14px',
            lineHeight: '20px',
            color: '#171717',
          }}
        >
          {caption ? (
            <caption
              style={{
                marginBottom: '8px',
                color: '#171717',
                fontSize: '14px',
                fontWeight: 500,
                textAlign: 'left',
              }}
            >
              {caption}
            </caption>
          ) : null}
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  style={{
                    borderBottom: '1px solid #eaeaea',
                    padding: '8px 12px',
                    color: '#666666',
                    fontSize: '12px',
                    fontWeight: 500,
                    textAlign: column.align,
                    width: column.width,
                  }}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row) => (
                <tr key={row.key}>
                  {columns.map((column, columnIndex) => (
                    <td
                      key={`${row.key}-${column.key}`}
                      style={{
                        borderBottom: '1px solid #f3f3f3',
                        padding: '10px 12px',
                        textAlign: column.align,
                        verticalAlign: 'top',
                      }}
                    >
                      {row.cells[columnIndex] ?? ''}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={columns.length}
                  style={{
                    padding: '16px 12px',
                    color: '#666666',
                    textAlign: 'center',
                  }}
                >
                  {emptyText}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
});
