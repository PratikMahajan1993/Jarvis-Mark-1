import type { MailAttachment, Scene } from "./types";

const SKIP = new Set([
  "view",
  "open",
  "show",
  "drawing",
  "drawings",
  "file",
  "files",
  "this",
  "that",
  "with",
  "the",
  "and",
  "pdf",
  "these",
  "those",
  "selected",
  "mail",
  "email",
  "last",
  "from",
]);

const MAIL_OPEN = /\b(mail|email|e-mail|inbox|gmail|message|letter)\b/;
const DRAWING_HINT =
  /\b(pdf|drawing|drawings|attachment|attachments|dpis|rfnw|piston)\b|\.[a-z]{3,4}\b/i;
const DRAWING_CODE = /\b(?:open|view|show)\s+(?:the\s+)?([A-Za-z]*\d[A-Za-z0-9._-]*)\b/i;

export type ViewerCommand = "zoom-in" | "zoom-out" | "next" | "prev" | "close";

export function sceneAttachments(scene: Scene): MailAttachment[] {
  for (const widget of scene.widgets) {
    if (widget.type === "attachments") {
      return (widget.items || []) as MailAttachment[];
    }
  }
  return [];
}

export function isSavedLocal(att: MailAttachment): boolean {
  return (att.status === "local" || att.status === "both") && Boolean(att.local_name || att.local_path);
}

export function conversationToAttachment(focus: Record<string, unknown> | undefined): MailAttachment | null {
  if (!focus) return null;
  const filename = String(focus.filename || focus.local_name || "");
  const localName = String(focus.local_name || filename);
  const localPath = String(focus.local_path || "");
  if (!filename && !localName && !localPath) return null;
  return {
    attachment_id: String(focus.artifact_id || ""),
    filename: filename || localName,
    mime: String(focus.mime || ""),
    size: 0,
    readable: true,
    cad: true,
    status: "local",
    local_path: localPath || null,
    local_name: localName || null,
    drive_link: String(focus.drive_link || "") || null,
    artifact_id: String(focus.artifact_id || "") || null,
  };
}

export function isViewCommand(message: string): boolean {
  const text = message.toLowerCase();
  if (!/\b(view|open|show)\b/.test(text)) return false;
  if (MAIL_OPEN.test(text) && !DRAWING_HINT.test(text)) return false;
  return Boolean(DRAWING_HINT.test(text) || DRAWING_CODE.test(message) || /\bpiston\b/i.test(text));
}

function collectTokens(message: string): string[] {
  const tokens: string[] = [];
  for (const pattern of [
    /\b(?:view|open|show)\s+(?:the\s+)?([A-Za-z0-9._-]+)/gi,
    /\b([A-Za-z0-9._-]+\.pdf)\b/gi,
    /\b(DPIS\d+)\b/gi,
    /\b(RFNW[-_]?\d+)\b/gi,
  ]) {
    for (const match of message.matchAll(pattern)) {
      for (const group of match.slice(1)) {
        if (group) tokens.push(group);
      }
    }
  }
  if (/piston/i.test(message)) tokens.push("piston");
  if (!tokens.length) {
    for (const word of message.match(/[A-Za-z0-9]{4,}/g) || []) {
      if (!SKIP.has(word.toLowerCase())) tokens.push(word);
    }
  }
  return tokens;
}

export function matchViewAttachment(
  message: string,
  attachments: MailAttachment[],
): { attachment: MailAttachment | null; whisper: string | null } {
  if (!attachments.length) {
    return { attachment: null, whisper: "No attachments on the board." };
  }

  const tokens = collectTokens(message);
  if (!tokens.length) {
    if (attachments.length === 1) {
      const only = attachments[0];
      if (!isSavedLocal(only)) return { attachment: null, whisper: "Save it first, then I can open it." };
      return { attachment: only, whisper: null };
    }
    const preview = attachments
      .slice(0, 4)
      .map((row) => row.filename)
      .join(", ");
    return { attachment: null, whisper: `Which drawing? ${preview}` };
  }

  const hits: MailAttachment[] = [];
  const seen = new Set<string>();
  for (const row of attachments) {
    const fname = row.filename.toLowerCase();
    for (const token of tokens) {
      if (fname.includes(token.toLowerCase()) && !seen.has(row.attachment_id)) {
        hits.push(row);
        seen.add(row.attachment_id);
        break;
      }
    }
  }

  if (!hits.length) {
    if (attachments.length === 1) {
      const only = attachments[0];
      if (!isSavedLocal(only)) return { attachment: null, whisper: "Save it first, then I can open it." };
      return { attachment: only, whisper: null };
    }
    return { attachment: null, whisper: "Which drawing?" };
  }

  if (hits.length > 1) {
    const preview = hits
      .slice(0, 4)
      .map((row) => row.filename)
      .join(", ");
    return { attachment: null, whisper: `Several match — which one? ${preview}` };
  }

  const hit = hits[0];
  if (!isSavedLocal(hit)) {
    return { attachment: null, whisper: "Save it first, then I can open it." };
  }
  return { attachment: hit, whisper: null };
}

export function parseViewerCommand(text: string): ViewerCommand | null {
  const t = text.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  if (!t) return null;
  if (/\bclose\b|\bdone\b|\bexit\b/.test(t)) return "close";
  if (/\bzoom\s*in\b|\bzoom in\b|\bbigger\b|\bcloser\b/.test(t)) return "zoom-in";
  if (/\bzoom\s*out\b|\bzoom out\b|\bsmaller\b|\bfurther\b/.test(t)) return "zoom-out";
  if (/\bnext\s+page\b|\bnext page\b/.test(t) || (/\bnext\b/.test(t) && !/\btext\b/.test(t))) return "next";
  if (/\bprev(?:ious)?\s+page\b|\bprevious page\b|\bprevious\b|\bprev\b/.test(t)) return "prev";
  return null;
}
