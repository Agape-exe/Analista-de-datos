import type { AnalysisReport } from "../lib/api-client";
import { reportFixture } from "./report-fixture";

// Same keys emitted by InstrumentedLLMProvider / InstrumentedAnalyticsTool.
// No timestamps, stage IDs or per-call reasons are supplied by these producers.
export const traceFixture = {
  ...reportFixture, run_id: "trace-run", status: "FAILED",
  execution_trace: [
    { kind: "llm", status: "SUCCESS", duration_seconds: 0 },
    { kind: "tool", method: "fixture_tool", status: "SKIPPED", duration_seconds: 0.125 },
    { kind: "tool", method: "fixture_tool", status: "FAILED", duration_seconds: 0.000001 },
  ],
  stage_statuses: { DataUnderstanding: "SUCCESS", Planner: "SKIPPED", Analysis: "FAILED" },
  stage_durations: { DataUnderstanding: 0, Planner: 0.25, Analysis: 1.5 },
  warnings: ["Fixture warning"], errors: ["Fixture failure"],
} satisfies AnalysisReport;
