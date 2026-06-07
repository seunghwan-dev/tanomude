import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import App from "./App";
import * as api from "./api";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, getTask: vi.fn() };
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
      workflow: "shukko",
      instruction: "製品Xの納入調整のため大阪へ出張する。",
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

  it("falls back to the blank form when the restored task is still awaiting approval", async () => {
    vi.mocked(api.getTask).mockResolvedValue({
      id: 9,
      workflow: "shukko",
      instruction: "製品Xの納入調整のため大阪へ出張する。",
      status: "awaiting_approval",
      executions: [],
    });
    window.history.replaceState(null, "", "/?task=9");

    render(<App />);

    await waitFor(() => expect(api.getTask).toHaveBeenCalledWith(9));
    expect(screen.getByText(/指示を入力し/)).toBeTruthy();
    expect(screen.queryByText(/復元したタスク/)).toBeNull();
  });
});
