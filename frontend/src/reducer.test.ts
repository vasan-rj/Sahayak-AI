import { describe, expect, it } from "vitest";
import { reducer } from "./App";
import type { FormSnapshot } from "./useWebSocket";

const initial = {
  form: null as FormSnapshot | null,
  agentCaption: "",
  userCaption: "",
  lang: "hi",
  complete: false,
  error: null as string | null,
};

const blankForm: FormSnapshot = {
  template_id: "t",
  title: "T",
  fields: [],
  complete: false,
};

describe("App reducer", () => {
  it("stores the form snapshot and completion flag", () => {
    const s = reducer(initial, { type: "form_snapshot", form: { ...blankForm, complete: true } });
    expect(s.form?.template_id).toBe("t");
    expect(s.complete).toBe(true);
  });

  it("routes captions by side and tracks language", () => {
    let s = reducer(initial, { type: "caption", side: "agent", text: "नमस्ते", lang: "hi", final: true });
    expect(s.agentCaption).toBe("नमस्ते");
    s = reducer(s, { type: "caption", side: "user", text: "vanakkam", lang: "ta", final: true });
    expect(s.userCaption).toBe("vanakkam");
    expect(s.lang).toBe("ta");
  });

  it("sets complete on form_complete and records errors", () => {
    expect(reducer(initial, { type: "form_complete" }).complete).toBe(true);
    expect(reducer(initial, { type: "error", detail: "live_error" }).error).toBe("live_error");
  });

  it("ignores audio/field_update/interrupted (handled elsewhere or snapshot-driven)", () => {
    expect(reducer(initial, { type: "audio", data: "AAAA" })).toEqual(initial);
    expect(reducer(initial, { type: "interrupted" })).toEqual(initial);
  });
});
