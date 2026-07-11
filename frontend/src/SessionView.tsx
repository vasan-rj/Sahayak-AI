import { useCallback, useReducer, useRef, useState } from "react";
import { Form } from "./Form";
import { IconDoc, IconMic, IconSound, IconVoice } from "./Icons";
import { t } from "./i18n";
import { useMedia } from "./useMedia";
import { useWebSocket, type FormSnapshot, type ServerEvent } from "./useWebSocket";

interface State {
  form: FormSnapshot | null;
  agentCaption: string;
  userCaption: string;
  lang: string;
  lastSide: "agent" | "user" | null;
  complete: boolean;
  error: string | null;
}

function makeInitial(lang: string): State {
  return {
    form: null,
    agentCaption: "",
    userCaption: "",
    lang,
    lastSide: null,
    complete: false,
    error: null,
  };
}

export function reducer(s: State, e: ServerEvent): State {
  switch (e.type) {
    case "form_snapshot":
      return { ...s, form: e.form, complete: e.form.complete };
    case "form_complete":
      return { ...s, complete: true };
    case "caption":
      return e.side === "agent"
        ? { ...s, agentCaption: e.text, lang: e.lang ?? s.lang, lastSide: "agent" }
        : { ...s, userCaption: e.text, lang: e.lang ?? s.lang, lastSide: "user" };
    case "error":
      return { ...s, error: e.detail };
    default:
      return s; // field_update (snapshot follows), audio (handled outside), interrupted
  }
}

function wsUrl(templateId: string, lang: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const p = new URLSearchParams();
  if (templateId) p.set("template", templateId);
  if (lang) p.set("lang", lang);
  return `${proto}://${window.location.host}/ws?${p.toString()}`;
}

export default function SessionView({
  templateId,
  lang,
  onExit,
}: {
  templateId: string;
  lang: string;
  onExit: () => void;
}) {
  const [state, dispatch] = useReducer(reducer, lang, makeInitial);
  // Nothing connects until the user taps Start. The agent greets on connect, so
  // if we opened the socket on mount its greeting audio would arrive before any
  // user gesture — and Chrome keeps the playback AudioContext suspended until a
  // gesture, so that greeting would be silent. Gating the socket behind Start
  // guarantees the audio context is already unlocked when the agent first speaks.
  const [started, setStarted] = useState(false);

  // Media hook needs sendBinary from the socket; socket needs the audio handler
  // from media. Break the cycle with a stable ref filled in after the socket exists.
  const senderRef = useRef<(b: Uint8Array) => void>(() => {});
  const media = useMedia(useCallback((b: Uint8Array) => senderRef.current(b), []));

  const handleEvent = useCallback(
    (e: ServerEvent) => {
      if (e.type === "audio") media.playChunk(e.data);
      else if (e.type === "interrupted") media.flushAgentAudio();
      else dispatch(e);
    },
    [media],
  );

  // Empty url until Start → useWebSocket stays idle and the agent can't greet yet.
  const { status, sendBinary } = useWebSocket(started ? wsUrl(templateId, lang) : "", handleEvent);
  senderRef.current = sendBinary;

  const onStart = useCallback(() => {
    void media.start(); // synchronously unlocks the playback AudioContext (gesture)
    setStarted(true); // now open the socket; the agent greets into a live context
  }, [media]);

  const mode: "speaking" | "listening" = state.lastSide === "agent" ? "speaking" : "listening";
  const copy = {
    // Primary line in the applicant's language; English gloss stays fixed below.
    top: mode === "speaking" ? t(lang, "agent_speaking") : t(lang, "your_turn"),
    sub: mode === "speaking" ? "Sahayak is speaking" : "Your turn — speak or show your card",
  };

  return (
    <div className="app">
      <header className="topbar">
        <button className="backbtn" onClick={onExit} aria-label="Back">
          ‹
        </button>
        <div className="brand">
          <span className="brandname">
            Sahayak <span className="deva">सहायक</span>
          </span>
        </div>
        <div className="badges">
          <span className={`lang lang-${state.lang}`}>{state.lang.toUpperCase()}</span>
          <span className={`dot dot-${status}`} title={status} aria-label={`connection ${status}`} />
        </div>
      </header>

      <main className="stage">
        <section className="talk">
          <div className={`camera state-${media.running ? mode : "idle"}`}>
            <video ref={media.videoRef} muted playsInline className="cam" />

            {media.running && (
              <>
                <div className="frameguide" aria-hidden>
                  <span className="fg-hint">{t(lang, "hold_card_here")} · Hold your card here</span>
                </div>
                <div className={`orb orb-${mode}`} aria-hidden>
                  <span className="orb-core">{mode === "speaking" ? <IconSound /> : <IconMic />}</span>
                </div>
                <div className="statepill">
                  <strong>{copy.top}</strong>
                  <em>{copy.sub}</em>
                </div>
              </>
            )}

            {!media.running && (
              <div className="welcome">
                <div className="welcome-orb" aria-hidden>
                  <IconMic />
                </div>
                <h2 className="welcome-title">
                  {t(lang, "talk_to_fill")}
                  <span>Fill the form just by talking</span>
                </h2>
                <ol className="welcome-steps">
                  <li>
                    <IconVoice className="ws-ic" />
                    {t(lang, "speak")}
                  </li>
                  <li>
                    <IconDoc className="ws-ic" />
                    {t(lang, "show_card")}
                  </li>
                </ol>
                <button className="startbtn" onClick={onStart}>
                  <IconMic className="startbtn-ic" />
                  {t(lang, "start")} · Start
                </button>
                {media.error && (
                  <p className="err">
                    {t(lang, "camera_mic")}: {media.error}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="captions" aria-live="polite">
            <p className="cap cap-agent">{state.agentCaption || (media.running ? "…" : "")}</p>
            {state.userCaption && <p className="cap cap-user">{state.userCaption}</p>}
          </div>
        </section>

        <aside className="record">
          <Form form={state.form} lang={lang} />
        </aside>
      </main>

      {state.error && (
        <div className="banner-error" role="alert">
          <span aria-hidden>⚠️</span> {t(lang, "something_wrong")} · {state.error}
        </div>
      )}
    </div>
  );
}
