import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket } from "./useWebSocket";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  // test drivers
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useWebSocket", () => {
  it("connects, opens, and round-trips ping/pong", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost/ws"));
    expect(result.current.status).toBe("connecting");

    const sock = MockWebSocket.instances[0];
    act(() => sock._open());
    expect(result.current.status).toBe("open");

    act(() => result.current.send({ type: "ping", payload: "namaste" }));
    expect(JSON.parse(sock.sent[0])).toEqual({ type: "ping", payload: "namaste" });

    act(() => sock._emit({ type: "pong", payload: "namaste" }));
    expect(result.current.last).toEqual({ type: "pong", payload: "namaste" });
  });

  it("ignores non-JSON frames without crashing", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost/ws"));
    const sock = MockWebSocket.instances[0];
    act(() => sock._open());
    act(() => sock.onmessage?.({ data: "not json" }));
    expect(result.current.last).toBeNull();
  });

  it("does not send while the socket is still connecting", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost/ws"));
    const sock = MockWebSocket.instances[0];
    act(() => result.current.send({ type: "ping" }));
    expect(sock.sent).toHaveLength(0);
  });
});
