export type TextBlock =
  | { kind: "prose"; text: string }
  | { kind: "table"; columns: string[]; rows: string[][] };

const PIPE_ROW = /^\s*\|.*\|\s*$/;
const SEP_CELL = /^:?-{3,}:?$/;

function cells(line: string): string[] {
  let stripped = line.trim();
  if (stripped.startsWith("|")) stripped = stripped.slice(1);
  if (stripped.endsWith("|")) stripped = stripped.slice(0, -1);
  return stripped.split("|").map((cell) => cell.trim());
}

function isSep(line: string): boolean {
  if (/^\s*\|?\s*:?-{3,}/.test(line) && !/[A-Za-z0-9]/.test(line)) return true;
  const parts = line.includes("|") ? cells(line) : [];
  return parts.length > 0 && parts.every((cell) => SEP_CELL.test(cell || ""));
}

export function splitMarkdownTables(text: string): TextBlock[] {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: TextBlock[] = [];
  const prose: string[] = [];
  let index = 0;

  const flush = () => {
    const chunk = prose.join("\n").trim();
    prose.length = 0;
    if (chunk) blocks.push({ kind: "prose", text: chunk });
  };

  while (index < lines.length) {
    const line = lines[index];
    if (PIPE_ROW.test(line) && index + 1 < lines.length && isSep(lines[index + 1])) {
      flush();
      const header = cells(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && PIPE_ROW.test(lines[index])) {
        rows.push(cells(lines[index]));
        index += 1;
      }
      const width = Math.max(header.length, ...rows.map((row) => row.length), 0);
      const pad = (row: string[]) => row.concat(Array(Math.max(0, width - row.length)).fill(""));
      if (header.some(Boolean)) {
        blocks.push({ kind: "table", columns: pad(header), rows: rows.map(pad) });
      }
      continue;
    }
    prose.push(line);
    index += 1;
  }
  flush();
  return blocks;
}
