import { useEffect, useState } from "react";
import { IconDoc, IconMark } from "./Icons";
import { t } from "./i18n";
import SessionView from "./SessionView";

// Indian languages the applicant can pick. Native label first (what a non-reader
// recognises), English underneath for a helper.
const LANGUAGES: { code: string; native: string; en: string }[] = [
  { code: "hi", native: "हिन्दी", en: "Hindi" },
  { code: "ta", native: "தமிழ்", en: "Tamil" },
  { code: "te", native: "తెలుగు", en: "Telugu" },
  { code: "bn", native: "বাংলা", en: "Bengali" },
  { code: "mr", native: "मराठी", en: "Marathi" },
  { code: "kn", native: "ಕನ್ನಡ", en: "Kannada" },
  { code: "gu", native: "ગુજરાતી", en: "Gujarati" },
  { code: "pa", native: "ਪੰਜਾਬੀ", en: "Punjabi" },
  { code: "ml", native: "മലയാളം", en: "Malayalam" },
  { code: "or", native: "ଓଡ଼ିଆ", en: "Odia" },
  { code: "ur", native: "اردو", en: "Urdu" },
];

interface TemplateSummary {
  template_id: string;
  title: string;
  field_count: number;
  active: boolean;
}

type Phase = "language" | "document" | "session";

export default function App() {
  // The marketing landing.html (served at "/") owns the User/Admin choice; the
  // React app opens straight into the user flow — language, then document.
  const [phase, setPhase] = useState<Phase>("language");
  const [lang, setLang] = useState("hi");
  const [templateId, setTemplateId] = useState("");
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Load the forms the admin has published when the user reaches the picker.
  useEffect(() => {
    if (phase !== "document") return;
    setTemplates(null);
    setLoadError(null);
    fetch("/templates")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then(setTemplates)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)));
  }, [phase]);

  if (phase === "session") {
    return <SessionView templateId={templateId} lang={lang} onExit={() => setPhase("document")} />;
  }

  return (
    <div className="portal">
      <header className="portal-top">
        <span className="portal-logo" aria-hidden>
          <IconMark />
        </span>
        <span className="portal-name">
          Sahayak <span className="deva">सहायक</span>
        </span>
      </header>

      {phase === "language" && (
        <main className="portal-body">
          <StepHead
            onBack={() => window.location.assign("/")}
            step={1}
            of={2}
            title="अपनी भाषा चुनें"
            en="Choose your language"
          />
          <div className="lang-grid">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                className={`langcard ${lang === l.code ? "sel" : ""}`}
                data-testid={`lang-${l.code}`}
                onClick={() => {
                  setLang(l.code);
                  setPhase("document");
                }}
              >
                <strong>{l.native}</strong>
                <span>{l.en}</span>
              </button>
            ))}
          </div>
        </main>
      )}

      {phase === "document" && (
        <main className="portal-body">
          <StepHead
            onBack={() => setPhase("language")}
            step={2}
            of={2}
            title={t(lang, "pick_form")}
            en="Which form do you want to fill?"
          />
          {loadError && <p className="portal-err">Could not load forms: {loadError}</p>}
          {!templates && !loadError && <p className="portal-ph">{t(lang, "loading_forms")}</p>}
          {templates && templates.length === 0 && <p className="portal-ph">{t(lang, "no_forms")}</p>}
          <div className="doc-grid">
            {templates?.map((tpl) => (
              <button
                key={tpl.template_id}
                className="doccard"
                data-testid={`doc-${tpl.template_id}`}
                onClick={() => {
                  setTemplateId(tpl.template_id);
                  setPhase("session");
                }}
              >
                <span className="doccard-ic" aria-hidden>
                  <IconDoc />
                </span>
                <span className="doccard-body">
                  <strong>{tpl.title}</strong>
                  <span>
                    {tpl.field_count} {t(lang, "fields")}
                  </span>
                </span>
                <span className="doccard-go" aria-hidden>
                  ›
                </span>
              </button>
            ))}
          </div>
        </main>
      )}
    </div>
  );
}

function StepHead({
  onBack,
  step,
  of,
  title,
  en,
}: {
  onBack: () => void;
  step: number;
  of: number;
  title: string;
  en: string;
}) {
  return (
    <div className="stephead">
      <button className="backbtn" onClick={onBack} aria-label="Back">
        ‹
      </button>
      <div className="stephead-txt">
        <span className="stepnum">
          {step} / {of}
        </span>
        <h1>{title}</h1>
        <p>{en}</p>
      </div>
    </div>
  );
}
