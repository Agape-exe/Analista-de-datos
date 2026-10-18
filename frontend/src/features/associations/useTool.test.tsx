import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/exploration";
import { useTool } from "./useTool";

afterEach(() => vi.unstubAllGlobals());

const result = (status: AnalysisResult["status"], variables: string[]): AnalysisResult => ({
  method: "outliers", status, completeness: "complete", variables,
  result: status === "SUCCESS" ? { ok: true } as never : null, warnings: [], execution_time: 0,
});
const json = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 });

function stub(status: AnalysisResult["status"] = "SUCCESS") {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => json(result(status, JSON.parse(String(init?.body)).variables)));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("reuses a successful result when the same inputs come back", async () => {
  const fetchMock = stub();
  const { result: hook, rerender } = renderHook(({ column }) => useTool("ds", "outliers", [column]), { initialProps: { column: "a" } });
  await waitFor(() => expect(hook.current.data?.variables).toEqual(["a"]));
  rerender({ column: "b" });
  await waitFor(() => expect(hook.current.data?.variables).toEqual(["b"]));
  rerender({ column: "a" });
  expect(hook.current).toMatchObject({ loading: false, stale: false, data: { variables: ["a"] } });
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("shares one request between components asking for the same tool", async () => {
  const fetchMock = stub();
  function Panel({ name }: { name: string }) {
    const tool = useTool("ds", "outliers", ["a"]);
    return <p>{name}: {tool.data ? "listo" : "cargando"}</p>;
  }
  render(<><Panel name="uno" /><Panel name="dos" /></>);
  await screen.findByText("uno: listo");
  expect(screen.getByText("dos: listo")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("keeps a shared request alive while another component still needs it", async () => {
  let resolve!: (value: Response) => void;
  const fetchMock = vi.fn(() => new Promise<Response>((done) => { resolve = done; }));
  vi.stubGlobal("fetch", fetchMock);
  function Panel({ name }: { name: string }) {
    const tool = useTool("ds", "outliers", ["a"]);
    return <p>{name}: {tool.data ? "listo" : "cargando"}</p>;
  }
  const view = render(<><Panel name="uno" /><Panel name="dos" /></>);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
  view.rerender(<Panel name="dos" />);
  await act(async () => resolve(json(result("SUCCESS", ["a"]))));
  expect(await screen.findByText("dos: listo")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("does not cache failed computations, so retry asks the server again", async () => {
  const fetchMock = stub("FAILED");
  const { result: hook } = renderHook(() => useTool("ds", "outliers", ["a"]));
  await waitFor(() => expect(hook.current.data?.status).toBe("FAILED"));
  act(() => hook.current.retry());
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
});
