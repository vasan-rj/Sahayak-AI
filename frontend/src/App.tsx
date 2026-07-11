import { useWebSocket } from "./useWebSocket";

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

export default function App() {
  const { status, last, send } = useWebSocket(wsUrl());

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          Sahayak <span className="deva">सहायक</span>
        </h1>
        <span className={`status status-${status}`} data-testid="status">
          proxy: {status}
        </span>
      </header>

      <main className="grid">
        <section className="panel camera">
          <h2>Camera</h2>
          <p className="ph">Phone feed lands here (DroidCam virtual cam).</p>
        </section>

        <section className="panel captions">
          <h2>Captions · EN</h2>
          <p className="ph">Live captions, both sides, always English.</p>
        </section>

        <aside className="panel record">
          <h2>Field tracker · Witness log</h2>
          <p className="ph">Timestamped, hash-chained record of every catch.</p>
        </aside>

        <section className="panel verify">
          <h2>Verify</h2>
          <div className="btns">
            <button onClick={() => send({ type: "ping", payload: Date.now() })}>
              Ping proxy
            </button>
            <button disabled>Run verify pass</button>
          </div>
          <pre className="last">{last ? JSON.stringify(last) : "no messages yet"}</pre>
        </section>
      </main>
    </div>
  );
}
