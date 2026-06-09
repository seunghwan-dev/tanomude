import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import App from "./App";
import * as api from "./api";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, getTask: vi.fn(), getTaskPlan: vi.fn() };
});

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
  send() {}
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("App task-view persistence across reload", () => {
  it("restores the task view from ?task=<id> instead of the blank form", async () => {
    vi.mocked(api.getTask).mockResolvedValue({
      id: 7,
      workflow: "shutchou",
      instruction: "製品Xの納入調整のため大阪へ出張する。",
      fields: { dest: "大阪" },
      status: "submitted",
      executions: [],
    });
    window.history.replaceState(null, "", "/?task=7");

    render(<App />);

    expect(await screen.findByText(/復元したタスク/)).toBeTruthy();
    expect(api.getTask).toHaveBeenCalledWith(7);
    expect(screen.queryByText(/指示を入力し/)).toBeNull();
  });

  it("shows the blank form on a fresh visit with no task param", () => {
    window.history.replaceState(null, "", "/");

    render(<App />);

    expect(screen.getByText(/指示を入力し/)).toBeTruthy();
    expect(api.getTask).not.toHaveBeenCalled();
    expect(screen.queryByText(/復元したタスク/)).toBeNull();
  });

  it("restores an actionable approval card when the reloaded task is awaiting approval", async () => {
    const fields = { dest: "大阪", dept_date: "2026-06-10", ret_date: "2026-06-11", proj_hint: "P-001" };
    const instruction = "製品Xの納入調整のため大阪へ出張する。";
    vi.mocked(api.getTask).mockResolvedValue({
      id: 9,
      workflow: "shutchou",
      instruction,
      fields,
      status: "awaiting_approval",
      executions: [],
    });
    vi.mocked(api.getTaskPlan).mockResolvedValue({
      task: { id: 9, workflow: "shutchou", instruction, fields, status: "awaiting_approval" },
      plan: {
        id: 1,
        task_id: 9,
        version: 1,
        analysis: { dest_code: "OSAKA", purpose: "製品X納入調整", overseas: false, reuse_prev_proj: false },
        keysequence: [{ seq: 1, type: "nav", target: null, value: null, key: "Enter" }],
        grounding: [],
        status: "proposed",
        created_at: "2026-06-07T00:00:00Z",
      },
      refusal: null,
    });
    window.history.replaceState(null, "", "/?task=9");

    render(<App />);

    expect(await screen.findByText("出張申請 承認カード")).toBeTruthy();
    expect(api.getTaskPlan).toHaveBeenCalledWith(9);
    expect(screen.getByText("承認")).toBeTruthy();
    expect(screen.queryByText(/指示を入力し/)).toBeNull();

    fireEvent.click(screen.getByText("却下"));
    expect(await screen.findByText(/却下理由/)).toBeTruthy();
  });
});
