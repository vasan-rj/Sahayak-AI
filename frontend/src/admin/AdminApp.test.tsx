import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AdminApp from "./AdminApp";
import type { AdminClient, SessionDetail, Template } from "./adminApi";

const TPL: Template = {
  template_id: "jkp_pension_2a",
  title: "Jan Kalyan Pension Yojana",
  fields: [
    { id: "applicant_name", label: "Name of Applicant", type: "document", source_doc: "aadhaar", extract: "name", ask: "आधार?" },
    { id: "nominee_name", label: "Nominee Name", type: "voice", extract: "name", ask: "nominee?" },
  ],
};

const DETAIL: SessionDetail = {
  id: "s1",
  verified: true,
  entries: [
    { seq: 0, ts: "t", kind: "session_start", data: {}, prev_hash: "0", hash: "a" },
    { seq: 1, ts: "t", kind: "field_captured", data: { field: "applicant_name", value: "RAJESH", source: "document" }, prev_hash: "a", hash: "b" },
  ],
};

function mockClient(over: Partial<AdminClient> = {}): AdminClient {
  return {
    listTemplates: vi.fn().mockResolvedValue([
      { template_id: "jkp_pension_2a", title: "Jan Kalyan Pension Yojana", field_count: 2, active: true },
    ]),
    getTemplate: vi.fn().mockResolvedValue(TPL),
    saveTemplate: vi.fn().mockResolvedValue(TPL),
    deleteTemplate: vi.fn().mockResolvedValue({ ok: true }),
    activate: vi.fn().mockResolvedValue({ active: "jkp_pension_2a" }),
    parseForm: vi.fn().mockResolvedValue(TPL),
    listSessions: vi.fn().mockResolvedValue([{ id: "s1", entries: 2, fields: 1, complete: true, mtime: 1 }]),
    getSession: vi.fn().mockResolvedValue(DETAIL),
    ...over,
  };
}

describe("AdminApp", () => {
  it("lists templates and loads one into the editor for editing", async () => {
    const client = mockClient();
    render(<AdminApp client={client} />);

    await waitFor(() => expect(screen.getByTestId("tpl-jkp_pension_2a")).toBeTruthy());

    fireEvent.click(screen.getByText("Edit"));

    const label0 = (await screen.findByTestId("field-label-0")) as HTMLInputElement;
    expect(label0.value).toBe("Name of Applicant");

    fireEvent.change(label0, { target: { value: "Applicant Full Name" } });
    expect((screen.getByTestId("field-label-0") as HTMLInputElement).value).toBe("Applicant Full Name");
  });

  it("saves the edited template through the client", async () => {
    const client = mockClient();
    render(<AdminApp client={client} />);
    await waitFor(() => screen.getByTestId("tpl-jkp_pension_2a"));
    fireEvent.click(screen.getByText("Edit"));
    await screen.findByTestId("save");
    fireEvent.click(screen.getByTestId("save"));
    await waitFor(() => expect(client.saveTemplate).toHaveBeenCalled());
  });

  it("shows sessions and their capture log", async () => {
    const client = mockClient();
    render(<AdminApp client={client} />);
    fireEvent.click(screen.getByText("Sessions"));

    const row = await screen.findByTestId("sess-s1");
    fireEvent.click(row);

    await waitFor(() => expect(screen.getByText(/chain verified/i)).toBeTruthy());
    expect(screen.getByText("RAJESH")).toBeTruthy();
  });
});
