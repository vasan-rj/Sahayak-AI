import { useCallback, useEffect, useState } from "react";
import {
  api,
  blankTemplate,
  type AdminClient,
  type FieldSpec,
  type SessionDetail,
  type SessionSummary,
  type Template,
  type TemplateSummary,
} from "./adminApi";
import "./admin.css";

type Tab = "templates" | "sessions";

export default function AdminApp({ client = api }: { client?: AdminClient }) {
  const [tab, setTab] = useState<Tab>("templates");
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [editing, setEditing] = useState<Template | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const say = (m: string) => setMsg(m);
  const fail = (e: unknown) => setMsg(e instanceof Error ? e.message : String(e));

  const refreshTemplates = useCallback(async () => {
    try {
      setTemplates(await client.listTemplates());
    } catch (e) {
      fail(e);
    }
  }, [client]);

  useEffect(() => {
    refreshTemplates();
  }, [refreshTemplates]);

  useEffect(() => {
    if (tab === "sessions") client.listSessions().then(setSessions).catch(fail);
  }, [tab, client]);

  // --- template actions ---
  const editTemplate = async (id: string) => {
    try {
      setEditing(await client.getTemplate(id));
    } catch (e) {
      fail(e);
    }
  };

  const save = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      await client.saveTemplate(editing);
      say(`Saved "${editing.template_id}"`);
      setEditing(null);
      await refreshTemplates();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const activate = async (id: string) => {
    try {
      await client.activate(id);
      say(`Activated "${id}" — the applicant app now fills this form`);
      await refreshTemplates();
    } catch (e) {
      fail(e);
    }
  };

  const del = async (id: string) => {
    try {
      await client.deleteTemplate(id);
      if (editing?.template_id === id) setEditing(null);
      await refreshTemplates();
    } catch (e) {
      fail(e);
    }
  };

  const upload = async (file: File) => {
    setBusy(true);
    say("Reading the form…");
    try {
      setEditing(await client.parseForm(file));
      say("Parsed — review the fields and Save");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  // --- editor field mutations ---
  const patchField = (i: number, patch: Partial<FieldSpec>) =>
    setEditing((t) => t && { ...t, fields: t.fields.map((f, j) => (j === i ? { ...f, ...patch } : f)) });
  const addField = () =>
    setEditing(
      (t) => t && { ...t, fields: [...t.fields, { id: "", label: "", type: "voice", extract: "", ask: "" }] },
    );
  const removeField = (i: number) =>
    setEditing((t) => t && { ...t, fields: t.fields.filter((_, j) => j !== i) });

  return (
    <div className="admin">
      <header className="admin-top">
        <h1>Sahayak Admin</h1>
        <nav>
          <button className={tab === "templates" ? "on" : ""} onClick={() => setTab("templates")}>
            Forms
          </button>
          <button className={tab === "sessions" ? "on" : ""} onClick={() => setTab("sessions")}>
            Sessions
          </button>
        </nav>
      </header>

      {msg && <div className="admin-msg">{msg}</div>}

      {tab === "templates" && (
        <div className="admin-grid">
          <section className="col">
            <div className="col-head">
              <h2>Forms</h2>
              <button onClick={() => setEditing(blankTemplate())}>+ New</button>
            </div>
            <label className="upload">
              📄 Upload a blank form → auto-build
              <input
                type="file"
                accept="image/*"
                data-testid="upload-input"
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
              />
            </label>
            <ul className="tlist">
              {templates.map((t) => (
                <li key={t.template_id} className={t.active ? "active" : ""} data-testid={`tpl-${t.template_id}`}>
                  <div className="tinfo">
                    <strong>{t.title}</strong>
                    <span>
                      {t.template_id} · {t.field_count} fields {t.active && "· ACTIVE"}
                    </span>
                  </div>
                  <div className="tactions">
                    {!t.active && <button onClick={() => activate(t.template_id)}>Activate</button>}
                    <button onClick={() => editTemplate(t.template_id)}>Edit</button>
                    <button className="danger" onClick={() => del(t.template_id)}>
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="col">
            <div className="col-head">
              <h2>Editor</h2>
            </div>
            {!editing ? (
              <p className="ph">Pick a form to edit, upload one, or start a New form.</p>
            ) : (
              <div className="editor">
                <label>
                  Template id
                  <input
                    data-testid="tpl-id"
                    value={editing.template_id}
                    onChange={(e) => setEditing({ ...editing, template_id: e.target.value })}
                  />
                </label>
                <label>
                  Title
                  <input
                    data-testid="tpl-title"
                    value={editing.title}
                    onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                  />
                </label>
                <div className="fields">
                  {editing.fields.map((f, i) => (
                    <div key={i} className="frow" data-testid={`frow-${i}`}>
                      <input
                        placeholder="id"
                        value={f.id}
                        onChange={(e) => patchField(i, { id: e.target.value })}
                      />
                      <input
                        placeholder="label"
                        data-testid={`field-label-${i}`}
                        value={f.label}
                        onChange={(e) => patchField(i, { label: e.target.value })}
                      />
                      <select
                        value={f.type}
                        data-testid={`field-type-${i}`}
                        onChange={(e) => patchField(i, { type: e.target.value as FieldSpec["type"] })}
                      >
                        <option value="document">document</option>
                        <option value="voice">voice</option>
                      </select>
                      {f.type === "document" && (
                        <input
                          placeholder="source_doc"
                          value={f.source_doc ?? ""}
                          onChange={(e) => patchField(i, { source_doc: e.target.value })}
                        />
                      )}
                      <input
                        placeholder="extract"
                        value={f.extract}
                        onChange={(e) => patchField(i, { extract: e.target.value })}
                      />
                      <input
                        placeholder="ask (Hindi)"
                        value={f.ask}
                        onChange={(e) => patchField(i, { ask: e.target.value })}
                      />
                      <button className="danger" onClick={() => removeField(i)}>
                        ✕
                      </button>
                    </div>
                  ))}
                  <button onClick={addField}>+ Field</button>
                </div>
                <div className="editor-actions">
                  <button className="primary" data-testid="save" disabled={busy} onClick={save}>
                    Save
                  </button>
                  <button onClick={() => setEditing(null)}>Cancel</button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {tab === "sessions" && (
        <div className="admin-grid">
          <section className="col">
            <div className="col-head">
              <h2>Sessions</h2>
            </div>
            <ul className="slist">
              {sessions.map((s) => (
                <li key={s.id} data-testid={`sess-${s.id}`} onClick={() => client.getSession(s.id).then(setDetail).catch(fail)}>
                  <strong>{s.id}</strong>
                  <span>
                    {s.fields} fields {s.complete ? "· complete" : ""} · {s.entries} entries
                  </span>
                </li>
              ))}
              {sessions.length === 0 && <p className="ph">No sessions yet.</p>}
            </ul>
          </section>
          <section className="col">
            <div className="col-head">
              <h2>Capture log</h2>
            </div>
            {!detail ? (
              <p className="ph">Pick a session to see its hash-chained capture log.</p>
            ) : (
              <div className="detail">
                <p className={detail.verified ? "verify ok" : "verify bad"}>
                  {detail.verified ? "✓ chain verified" : "✗ chain broken"}
                </p>
                <ol className="entries">
                  {detail.entries.map((e) => (
                    <li key={e.seq}>
                      <code>{e.kind}</code>
                      {e.kind === "field_captured" && (
                        <span>
                          {String(e.data.field)} = <b>{String(e.data.value)}</b>{" "}
                          {e.data.source === "document" ? "📄" : "🎤"}
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
