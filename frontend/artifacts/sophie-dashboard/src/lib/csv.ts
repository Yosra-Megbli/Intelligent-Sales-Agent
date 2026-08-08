/**
 * Minimal CSV helpers - no dependency needed for what this dashboard uses
 * CSV for: exporting the leads table, and building a one-row CSV payload
 * for the manual "Nouveau Lead" form so it can go through the existing
 * `POST /api/leads/import` endpoint (see backend/api/leads_routes.py)
 * instead of requiring a new single-lead-create backend route.
 */

/** Escapes a single field per RFC 4180: wraps in quotes if it contains a
 * comma, quote, or newline, doubling any internal quotes. */
export function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/** Builds CSV text (with header row) from an array of objects, in the
 * given column order. */
export function toCsv(rows: Array<Record<string, unknown>>, columns: string[]): string {
  const header = columns.map(csvEscape).join(',');
  const lines = rows.map((row) => columns.map((col) => csvEscape(row[col])).join(','));
  return [header, ...lines].join('\r\n');
}

/** Triggers a browser download of the given text content as a file. */
export function downloadTextFile(filename: string, content: string, mimeType = 'text/csv;charset=utf-8;') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
