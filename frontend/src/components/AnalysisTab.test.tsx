import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { Slots } from "../api";
import AnalysisTab from "./AnalysisTab";

const slots = (overseas: boolean): Slots => ({
  dest_code: "OSAKA",
  purpose: "製品X納入調整",
  overseas,
  reuse_prev_proj: false,
});

afterEach(cleanup);

describe("AnalysisTab overseas row", () => {
  it("labels the overseas row 海外区分, matching the green-screen field, never the contradictory 海外出張", () => {
    render(<AnalysisTab slots={slots(false)} />);

    expect(screen.getByText("海外区分")).toBeTruthy();
    expect(screen.queryByText("海外出張")).toBeNull();
    expect(screen.getByText("国内")).toBeTruthy();
  });

  it("keeps the overseas code identifier and value separate from the display label", () => {
    render(<AnalysisTab slots={slots(true)} />);

    expect(screen.getByText("海外区分")).toBeTruthy();
    expect(screen.getByText("overseas")).toBeTruthy();
    expect(screen.getByText("海外")).toBeTruthy();
  });
});
