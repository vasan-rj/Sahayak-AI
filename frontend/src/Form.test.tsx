import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Form } from "./Form";
import type { FormSnapshot } from "./useWebSocket";

function snap(overrides: Partial<FormSnapshot> = {}): FormSnapshot {
  return {
    template_id: "jkp_pension_2a",
    title: "Jan Kalyan Pension Yojana — Application",
    fields: [
      { id: "applicant_name", label: "Name of Applicant", type: "document", value: null, status: "pending", source: null },
      { id: "nominee_name", label: "Nominee Name", type: "voice", value: null, status: "pending", source: null },
    ],
    complete: false,
    ...overrides,
  };
}

describe("Form", () => {
  it("shows a loading placeholder before the first snapshot", () => {
    render(<Form form={null} />);
    expect(screen.getByText(/loading form/i)).toBeTruthy();
  });

  it("renders pending fields with a placeholder value", () => {
    render(<Form form={snap()} />);
    expect(screen.getByTestId("value-applicant_name").textContent).toBe("…");
    expect(screen.queryByTestId("form-done")).toBeNull();
  });

  it("fills a confirmed field with its value and source icon", () => {
    const s = snap({
      fields: [
        { id: "applicant_name", label: "Name of Applicant", type: "document", value: "RAJESH KUMAR", status: "confirmed", source: "document" },
        { id: "nominee_name", label: "Nominee Name", type: "voice", value: null, status: "pending", source: null },
      ],
    });
    render(<Form form={s} />);
    expect(screen.getByTestId("value-applicant_name").textContent).toBe("RAJESH KUMAR");
    expect(screen.getByTestId("source-applicant_name").getAttribute("title")).toBe("document");
  });

  it("shows the printable finale when complete", () => {
    const s = snap({
      fields: [
        { id: "applicant_name", label: "Name of Applicant", type: "document", value: "RAJESH KUMAR", status: "confirmed", source: "document" },
        { id: "nominee_name", label: "Nominee Name", type: "voice", value: "SUNITA DEVI", status: "confirmed", source: "voice" },
      ],
      complete: true,
    });
    render(<Form form={s} />);
    expect(screen.getByTestId("form-done")).toBeTruthy();
    expect(screen.getByTestId("source-nominee_name").getAttribute("title")).toBe("voice");
  });
});
