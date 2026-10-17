import { afterEach, describe, expect, it, vi } from "vitest";
import { submitIntake } from "./api-client";
import type { IntakeDraft } from "../types/intake";

const draft: IntakeDraft = {
  file: new File(["a\n1\n"], "sample.csv"), dictionary: null, delimiter: "\t", encoding: "utf-8",
};
afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("explains network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(submitIntake(draft)).rejects.toThrow("No se puede conectar con el backend");
  });
  it("explains non-JSON responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("html", { status: 502 })));
    await expect(submitIntake(draft)).rejects.toThrow("respuesta ilegible");
  });
  it("handles FastAPI 422 details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "Invalid delimiter" }] }), { status: 422 })));
    await expect(submitIntake(draft)).rejects.toThrow("Invalid delimiter");
  });
});
