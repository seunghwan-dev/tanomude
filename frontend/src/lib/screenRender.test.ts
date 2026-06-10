import { describe, expect, it } from "vitest";

import casesFixture from "../../../backend/tests/fixtures/cases.json";
import { actionToCommand, screenToTemplate } from "./screenRender";

interface GoldenStep {
  seq: number;
  type: string;
  target: string | null;
  value: string | null;
  key: string | null;
}

interface FixtureCase {
  case_id: string;
  golden: GoldenStep[];
}

const fixture = casesFixture as { cases: FixtureCase[] };
const goldenSteps: GoldenStep[] = fixture.cases.flatMap((entry) => entry.golden);

describe("actionToCommand over the golden fixture action shapes", () => {
  it("exercises every action type present in the golden fixtures", () => {
    const types = new Set(goldenSteps.map((step) => step.type));
    expect(types.has("field")).toBe(true);
    expect(types.has("fkey")).toBe(true);
    expect(types.has("nav")).toBe(true);
  });

  it("maps each field action to a type command carrying its target and value", () => {
    const fieldSteps = goldenSteps.filter((step) => step.type === "field");
    expect(fieldSteps.length).toBeGreaterThan(0);
    for (const step of fieldSteps) {
      expect(actionToCommand(step)).toEqual({ kind: "type", target: step.target, value: step.value });
    }
  });

  it("maps each fkey action to a key command carrying its key", () => {
    const fkeySteps = goldenSteps.filter((step) => step.type === "fkey");
    expect(fkeySteps.length).toBeGreaterThan(0);
    for (const step of fkeySteps) {
      expect(actionToCommand(step)).toEqual({ kind: "key", key: step.key });
    }
  });

  it("maps each nav action to a nav command carrying its target", () => {
    const navSteps = goldenSteps.filter((step) => step.type === "nav");
    expect(navSteps.length).toBeGreaterThan(0);
    for (const step of navSteps) {
      expect(actionToCommand(step)).toEqual({ kind: "nav", target: step.target });
    }
  });

  it("yields only known command kinds across the whole fixture", () => {
    for (const step of goldenSteps) {
      expect(["type", "key", "nav", "noop"]).toContain(actionToCommand(step).kind);
    }
  });
});

describe("screenToTemplate over the in-scope screen ids", () => {
  const cases: { id: string; base: string; overlay: string }[] = [
    { id: "menu", base: "menu", overlay: "none" },
    { id: "trip_input", base: "form", overlay: "none" },
    { id: "proj_prompt", base: "form", overlay: "lookup" },
    { id: "confirm", base: "form", overlay: "confirm" },
    { id: "submitted", base: "form", overlay: "submitted" },
  ];

  it.each(cases)("maps the $id screen to its template", ({ id, base, overlay }) => {
    const template = screenToTemplate(id);
    expect(template.id).toBe(id);
    expect(template.base).toBe(base);
    expect(template.overlay).toBe(overlay);
  });
});

describe("negative control: input guards must hold", () => {
  it("maps an unknown action type to a noop command", () => {
    expect(actionToCommand({ type: "zzz", target: null, value: null, key: null }).kind).toBe("noop");
  });

  it("maps an unknown screen id to the fallback template", () => {
    const template = screenToTemplate("aborted");
    expect(template.base).toBe("fallback");
    expect(template.id).toBe("aborted");
  });

  it("maps a null screen id to the fallback template", () => {
    expect(screenToTemplate(null).base).toBe("fallback");
  });
});
