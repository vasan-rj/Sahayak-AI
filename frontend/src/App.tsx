import { useCallback, useReducer, useRef } from "react";
import { Form } from "./Form";
import { useMedia } from "./useMedia";
import { useWebSocket, type FormSnapshot, type ServerEvent } from "./useWebSocket";

interface State {
  form: FormSnapshot | null;
  agentCaption: string;
  userCaption: string;
  lang: string;
  complete: boolean;
  error: string | null;
}

const initial: State = {
  form: null,
  agentCaption: "",
  userCaption: "",
  lang: "hi",
  complete: false,
  error: null,
};

export function reducer(s: State, e: ServerEvent): State {
  switch (e.type) {
    case "form_snapshot":
      return { ...s, form: e.form, complete: e.form.complete };
    case "form_complete":
      return { ...s, complete: true };
    case "caption":
      return e.side === "agent"
        ? { ...s, agentCaption: e.text, lang: e.lang ?? s.lang }
        : { ...s, userCaption: e.text, lang: e.lang ?? s.lang };
    case "error":
      return { ...s, error: e.detail };
    default:
      return s; // field_update (snapshot follows), audio (handled outside), interrupted
  }
}

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initial);

  // Media hook needs sendBinary from the socket; socket needs the audio handler
  // from media. Break the cycle with a stable ref filled in after the socket exists.
  const senderRef = useRef<(b: Uint8Array) => void>(() => {});
  const media = useMedia(useCallback((b: Uint8Array) => senderRef.current(b), []));

  const handleEvent = useCallback(
    (e: ServerEvent) => {
      if (e.type === "audio") media.playChunk(e.data);
      else dispatch(e);
    },
    [media],
  );

  const { status, sendBinary } = useWebSocket(wsUrl(), handleEvent);
  senderRef.current = sendBinary;

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          Sahayak <span className="deva">सहायक</span>
        </h1>
        <div className="badges">
          <span className={`lang lang-${state.lang}`}>{state.lang.toUpperCase()}</span>
          <span className={`status status-${status}`}>{status}</span>
        </div>
      </header>

      <main className="grid">
        <section className="panel camera">
          <video ref={media.videoRef} muted playsInline className="cam" />
          {!media.running && (
            <button className="startbtn" onClick={media.start}>
              Start session
            </button>
          )}
          {media.error && <p className="err">Camera/mic: {media.error}</p>}
        </section>

        <aside className="panel record">
          <Form form={state.form} />
        </aside>

        <section className="panel captions">
          <p className="cap cap-agent">{state.agentCaption || "…"}</p>
          <p className="cap cap-user">{state.userCaption}</p>
        </section>
      </main>

      {state.error && <div className="banner-error">Error: {state.error}</div>}
    </div>
  );
}
