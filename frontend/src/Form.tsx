import type { FormSnapshot } from "./useWebSocket";

const SOURCE_ICON: Record<string, string> = { document: "📄", voice: "🎤" };

/**
 * The digital form that fills itself live. Each field shows its captured value,
 * confirmation status, and where the value came from (document vs voice). When
 * every field is confirmed, the finale banner appears and the view is printable.
 */
export function Form({ form }: { form: FormSnapshot | null }) {
  if (!form) {
    return <p className="ph">Loading form…</p>;
  }
  return (
    <div className={`form ${form.complete ? "form-complete" : ""}`}>
      <h3 className="form-title">{form.title}</h3>
      <ol className="fields">
        {form.fields.map((f) => (
          <li key={f.id} className={`field field-${f.status}`} data-testid={`field-${f.id}`}>
            <span className="flabel">{f.label}</span>
            <span className="fvalue" data-testid={`value-${f.id}`}>
              {f.value ?? "…"}
            </span>
            {f.status === "confirmed" && f.source && (
              <span className="fsource" title={f.source} data-testid={`source-${f.id}`}>
                {SOURCE_ICON[f.source] ?? "•"}
              </span>
            )}
          </li>
        ))}
      </ol>
      {form.complete && (
        <div className="done" data-testid="form-done">
          <span>✓ Form complete — ready to print</span>
          <button onClick={() => window.print()}>Print</button>
        </div>
      )}
    </div>
  );
}
