import { useCallback, useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "open" | "closed";

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

/**
 * Minimal WebSocket hook for the walking skeleton: connect, track status, expose
 * the last decoded message, and send JSON. The real client will add audio/video
 * streaming and caption handling on top of this same connection.
 */
export function useWebSocket(url: string) {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [last, setLast] = useState<WsMessage | null>(null);
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    ref.current = ws;
    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (ev: MessageEvent) => {
      try {
        setLast(JSON.parse(ev.data as string) as WsMessage);
      } catch {
        // Non-JSON frame (e.g. binary media later) — ignore in the skeleton.
      }
    };
    return () => ws.close();
  }, [url]);

  const send = useCallback((msg: WsMessage) => {
    const ws = ref.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }, []);

  return { status, last, send };
}
