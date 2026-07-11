// Typed fetch wrappers for the admin API (see app/admin.py).

export interface FieldSpec {
  id: string;
  label: string;
  type: "document" | "voice";
  source_doc?: string;
  extract: string;
  ask: string;
}

export interface Template {
  template_id: string;
  title: string;
  fields: FieldSpec[];
}

export interface TemplateSummary {
  template_id: string;
  title: string;
  field_count: number;
  active: boolean;
}

export interface SessionSummary {
  id: string;
  entries: number;
  fields: number;
  complete: boolean;
  mtime: number;
}

export interface CaptureEntry {
  seq: number;
  ts: string;
  kind: string;
  data: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface SessionDetail {
  id: string;
  entries: CaptureEntry[];
  verified: boolean;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

async function ok<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || r.statusText);
  }
  return r.json() as Promise<T>;
}

export interface AdminClient {
  listTemplates(): Promise<TemplateSummary[]>;
  getTemplate(id: string): Promise<Template>;
  saveTemplate(t: Template): Promise<Template>;
  deleteTemplate(id: string): Promise<{ ok: boolean }>;
  activate(id: string): Promise<{ active: string }>;
  parseForm(file: File): Promise<Template>;
  listSessions(): Promise<SessionSummary[]>;
  getSession(id: string): Promise<SessionDetail>;
}

export const api: AdminClient = {
  listTemplates: () => fetch("/admin/templates").then(ok<TemplateSummary[]>),
  getTemplate: (id) => fetch(`/admin/templates/${id}`).then(ok<Template>),
  saveTemplate: (t) =>
    fetch("/admin/templates", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(t) }).then(
      ok<Template>,
    ),
  deleteTemplate: (id) => fetch(`/admin/templates/${id}`, { method: "DELETE" }).then(ok<{ ok: boolean }>),
  activate: (id) => fetch(`/admin/templates/${id}/activate`, { method: "POST" }).then(ok<{ active: string }>),
  parseForm: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/admin/parse-form", { method: "POST", body: fd }).then(ok<Template>);
  },
  listSessions: () => fetch("/admin/sessions").then(ok<SessionSummary[]>),
  getSession: (id) => fetch(`/admin/sessions/${id}`).then(ok<SessionDetail>),
};

export function blankTemplate(): Template {
  return {
    template_id: "",
    title: "",
    fields: [{ id: "", label: "", type: "voice", extract: "", ask: "" }],
  };
}
