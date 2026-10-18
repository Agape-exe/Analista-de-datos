import { afterEach, expect, test, vi } from "vitest";
import examples from "../../../tests/fixtures/eda-result-variants.json";
import { edaOutcome, type AnalysisResult } from "../types/exploration";
import { runTool } from "./api-client";

afterEach(() => vi.unstubAllGlobals());

test("shared Python/TypeScript JSON examples preserve every EDA variant", async () => {
  const kinds = [];
  for (const example of examples) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(example))));
    kinds.push(edaOutcome(await runTool("ds", example.method, {})).kind);
  }
  expect(kinds).toEqual(["success", "partial", "skipped", "failed"]);
  expect(edaOutcome({ method: "old", status: "SUCCESS" } as AnalysisResult).kind).toBe("success");
});

test("invalid partial and unsuccessful statistics are rejected at the boundary", async () => {
  for (const payload of [
    { method: "x", status: "FAILED", result: { mean: 10 } },
    { method: "x", status: "SUCCESS", completeness: "partial", column_results: {} },
  ]) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))));
    await expect(runTool("ds", "x", {})).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  }
});
