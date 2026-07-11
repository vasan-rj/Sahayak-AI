import { useCallback, useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "open" | "closed";

export interface FormField {
  id: string;
  label: string;
  type: string;
  value: string | null;
  status: string;
  source: string | null;
}

export interface FormSnapshot {
  template_id: string;
  title: string;
  fields: FormField[];
  complete: boolean;
}

export type ServerEvent =
  | { type: "form_snapshot"; form: FormSnapshot }
  | { type: "field_update"; field: FormField }
  | { type: "caption"; side: "user" | "agent"; text: string; lang: string | null; final: boolean }
  | { type: "audio"; data: string }
  | { type: "form_complete" }
  | { type: "interrupted" }
  | { type: "error"; detail: string };

/**
 * WebSocket to the proxy. JSON control/event frames are decoded and handed to
 * `onEvent`; binary media (mic PCM, camera JPEG) is sent via `sendBinary`.
 */
export function useWebSocket(url: string, onEvent: (e: ServerEvent) => void) {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const ref = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    // Empty url = not ready yet (session gated behind the Start gesture). Stay idle.
    if (!url) {
      setStatus("connecting");
      return;
    }
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ref.current = ws;
    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (ev: MessageEvent) => {
      if (typeof ev.data === "string") {
        try {
          onEventRef.current(JSON.parse(ev.data) as ServerEvent);
        } catch {
          // ignore non-JSON text
        }
      }
    };
    return () => ws.close();
  }, [url]);

  const send = useCallback((obj: unknown) => {
    const ws = ref.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  const sendBinary = useCallback((bytes: Uint8Array) => {
    const ws = ref.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(bytes);
  }, []);

  return { status, send, sendBinary };
}
