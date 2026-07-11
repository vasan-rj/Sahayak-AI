import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket, type ServerEvent } from "./useWebSocket";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.CONNECTING;
  binaryType = "blob";
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  send(data: unknown) {
    this.sent.push(data);
  }
  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }
  _open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }
  _emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
});
afterEach(() => vi.unstubAllGlobals());

describe("useWebSocket", () => {
  it("opens and delivers parsed server events to onEvent", () => {
    const events: ServerEvent[] = [];
    const { result } = renderHook(() => useWebSocket("ws://x/ws", (e) => events.push(e)));
    expect(result.current.status).toBe("connecting");

    const sock = MockWebSocket.instances[0];
    act(() => sock._open());
    expect(result.current.status).toBe("open");

    act(() => sock._emit({ type: "caption", side: "agent", text: "नमस्ते", lang: "hi", final: true }));
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "caption", side: "agent", text: "नमस्ते" });
  });

  it("ignores non-JSON text frames", () => {
    const events: ServerEvent[] = [];
    const { result } = renderHook(() => useWebSocket("ws://x/ws", (e) => events.push(e)));
    const sock = MockWebSocket.instances[0];
    act(() => sock._open());
    act(() => sock.onmessage?.({ data: "not json" }));
    expect(events).toHaveLength(0);
    void result;
  });

  it("sends JSON and binary only when open", () => {
    const { result } = renderHook(() => useWebSocket("ws://x/ws", () => {}));
    const sock = MockWebSocket.instances[0];
    act(() => result.current.send({ type: "ping" }));
    expect(sock.sent).toHaveLength(0); // still connecting

    act(() => sock._open());
    act(() => result.current.send({ type: "ping" }));
    act(() => result.current.sendBinary(new Uint8Array([1, 2, 3])));
    expect(sock.sent).toHaveLength(2);
    expect(JSON.parse(sock.sent[0] as string)).toEqual({ type: "ping" });
    expect(sock.sent[1]).toBeInstanceOf(Uint8Array);
  });
});
