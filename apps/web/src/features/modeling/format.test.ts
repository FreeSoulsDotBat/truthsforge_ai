import { describe, expect, it } from "vitest";

import {
  PLACEHOLDER,
  formatConfidencePercentage,
  formatDurationMs,
  formatRiskPercentage,
  formatTimestamp,
  riskSeverity,
  riskSeverityClass,
  truncate
} from "./format";

describe("formatDurationMs", () => {
  it("returns placeholder for null/undefined/NaN/negative", () => {
    expect(formatDurationMs(null)).toBe(PLACEHOLDER);
    expect(formatDurationMs(undefined)).toBe(PLACEHOLDER);
    expect(formatDurationMs(NaN)).toBe(PLACEHOLDER);
    expect(formatDurationMs(-5)).toBe(PLACEHOLDER);
  });

  it("renders sub-second values in ms", () => {
    expect(formatDurationMs(0)).toBe("0 ms");
    expect(formatDurationMs(123)).toBe("123 ms");
    expect(formatDurationMs(999)).toBe("999 ms");
  });

  it("renders seconds with one decimal under 10s and integer above", () => {
    expect(formatDurationMs(1000)).toBe("1.0 s");
    expect(formatDurationMs(1234)).toBe("1.2 s");
    expect(formatDurationMs(9900)).toBe("9.9 s");
    expect(formatDurationMs(10_000)).toBe("10 s");
    expect(formatDurationMs(59_999)).toBe("60 s");
  });

  it("renders minutes + seconds for very long calls", () => {
    expect(formatDurationMs(60_000)).toBe("1 min");
    expect(formatDurationMs(75_000)).toBe("1 min 15 s");
    expect(formatDurationMs(125_000)).toBe("2 min 5 s");
  });
});

describe("formatConfidencePercentage / formatRiskPercentage", () => {
  it("clamps to [0, 1] and rounds", () => {
    expect(formatConfidencePercentage(0)).toBe("0%");
    expect(formatConfidencePercentage(0.5)).toBe("50%");
    expect(formatConfidencePercentage(0.826)).toBe("83%");
    expect(formatConfidencePercentage(1)).toBe("100%");
    expect(formatConfidencePercentage(1.5)).toBe("100%");
    expect(formatConfidencePercentage(-0.2)).toBe("0%");
  });

  it("returns placeholder for null/NaN", () => {
    expect(formatConfidencePercentage(null)).toBe(PLACEHOLDER);
    expect(formatRiskPercentage(undefined)).toBe(PLACEHOLDER);
    expect(formatRiskPercentage(NaN)).toBe(PLACEHOLDER);
  });

  it("formatRiskPercentage matches confidence shape (same range)", () => {
    expect(formatRiskPercentage(0.0)).toBe("0%");
    expect(formatRiskPercentage(0.5)).toBe("50%");
  });
});

describe("riskSeverity / riskSeverityClass", () => {
  it("classifies common bands", () => {
    expect(riskSeverity(null)).toBe("ok");
    expect(riskSeverity(0)).toBe("ok");
    expect(riskSeverity(0.1)).toBe("info");
    expect(riskSeverity(0.3)).toBe("warning");
    expect(riskSeverity(0.6)).toBe("danger");
    expect(riskSeverity(1.0)).toBe("danger");
  });

  it("riskSeverityClass returns a tailwind text colour", () => {
    expect(riskSeverityClass(0)).toContain("forge-muted");
    expect(riskSeverityClass(0.1)).toContain("forge-text");
    expect(riskSeverityClass(0.35)).toContain("forge-amber");
    expect(riskSeverityClass(0.8)).toContain("forge-red");
  });
});

describe("formatTimestamp", () => {
  it("returns placeholder for missing/invalid input", () => {
    expect(formatTimestamp(null)).toBe(PLACEHOLDER);
    expect(formatTimestamp(undefined)).toBe(PLACEHOLDER);
    expect(formatTimestamp("")).toBe(PLACEHOLDER);
    expect(formatTimestamp("not-a-date")).toBe(PLACEHOLDER);
  });

  it("formats valid ISO timestamps with pt-BR locale", () => {
    const formatted = formatTimestamp("2026-05-11T12:34:56Z");
    expect(formatted).not.toBe(PLACEHOLDER);
    // We intentionally do not pin the exact string because locale rendering
    // varies by environment; we just assert it is non-empty and looks like a
    // pt-BR date (DD/MM/YYYY) somewhere in the output.
    expect(formatted).toMatch(/\d{2}\/\d{2}\/\d{4}/);
  });
});

describe("truncate", () => {
  it("returns empty string for null/undefined", () => {
    expect(truncate(null)).toBe("");
    expect(truncate(undefined)).toBe("");
  });

  it("keeps short strings intact", () => {
    expect(truncate("abc", 10)).toBe("abc");
    expect(truncate("exact", 5)).toBe("exact");
  });

  it("adds ellipsis when truncating", () => {
    expect(truncate("hello world", 5)).toBe("hell…");
    expect(truncate("supercalifragilistic", 6)).toBe("super…");
  });

  it("trims trailing whitespace before adding the ellipsis", () => {
    expect(truncate("hello world", 7)).toBe("hello…");
  });
});
