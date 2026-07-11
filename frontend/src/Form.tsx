import { IconCheck, IconDoc, IconPrint, IconVoice } from "./Icons";
import { t } from "./i18n";
import type { FormField, FormSnapshot } from "./useWebSocket";

// Where a confirmed value came from — a small provenance marker in the record.
const SOURCE_ICON: Record<string, JSX.Element> = { document: <IconDoc />, voice: <IconVoice /> };
// What the person shows/does for a pending field — a picture cue, not words.
const TYPE_ICON: Record<string, JSX.Element> = { document: <IconDoc />, voice: <IconVoice /> };

/**
 * The digital form that fills itself live. Each field is a large card showing
 * its captured value, confirmation status, and where the value came from
 * (document vs voice). A dot rail tracks progress without any text to read.
 * When every field is confirmed, the finale appears and the view is printable.
 */
export function Form({ form, lang = "hi" }: { form: FormSnapshot | null; lang?: string }) {
  if (!form) {
    return (
      <div className="form form-loading">
        <p className="ph">Loading form…</p>
      </div>
    );
  }

  const total = form.fields.length;
  const done = form.fields.filter((f) => f.status === "confirmed").length;
  // The first not-yet-confirmed field is the one being worked on right now.
  const currentIdx = form.fields.findIndex((f) => f.status !== "confirmed");

  return (
    <div className={`form ${form.complete ? "form-complete" : ""}`}>
      <div className="form-head">
        <h3 className="form-title">{form.title}</h3>
        <div className="progress" aria-label={`${done} of ${total} done`}>
          <div className="dots">
            {form.fields.map((f, i) => (
              <span
                key={f.id}
                className={`pdot ${f.status === "confirmed" ? "pdot-done" : i === currentIdx ? "pdot-now" : ""}`}
              >
                {f.status === "confirmed" ? <IconCheck /> : i + 1}
              </span>
            ))}
          </div>
          <span className="pcount">
            {done}/{total}
          </span>
        </div>
      </div>

      <ol className="fields">
        {form.fields.map((f, i) => (
          <FieldCard key={f.id} field={f} current={i === currentIdx && !form.complete} />
        ))}
      </ol>

      {form.complete && (
        <div className="done" data-testid="form-done">
          <div className="done-msg">
            <span className="done-tick" aria-hidden>
              <IconCheck />
            </span>
            <span>
              {t(lang, "form_ready")}
              <em>Form complete — ready to print</em>
            </span>
          </div>
          <button onClick={() => window.print()}>
            <IconPrint /> {t(lang, "print")} · Print
          </button>
        </div>
      )}
    </div>
  );
}

function FieldCard({ field: f, current }: { field: FormField; current: boolean }) {
  const state = f.status === "confirmed" ? "confirmed" : current ? "current" : "pending";
  return (
    <li className={`field field-${state}`} data-testid={`field-${f.id}`}>
      <span className="ficon" aria-hidden>
        {f.status === "confirmed" ? (
          <span className="ftick" key="tick">
            <IconCheck />
          </span>
        ) : (
          TYPE_ICON[f.type] ?? null
        )}
      </span>
      <span className="fbody">
        <span className="flabel">{f.label}</span>
        <span className="fvalue" data-testid={`value-${f.id}`}>
          {f.value ?? "…"}
        </span>
      </span>
      {f.status === "confirmed" && f.source && (
        <span className="fsource" title={f.source} data-testid={`source-${f.id}`}>
          {SOURCE_ICON[f.source] ?? null}
        </span>
      )}
    </li>
  );
}
