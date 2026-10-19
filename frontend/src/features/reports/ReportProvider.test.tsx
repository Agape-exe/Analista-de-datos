import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { IntakeProvider, useIntake } from "../data-intake/IntakeProvider";
import { intakeFixture } from "../../test/fixture";
import { ReportProvider, useReport } from "./ReportProvider";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const report = (runId: string, datasetId?: string) => ({
  run_id: runId, status: "SUCCESS", insights: [], evidence: [], analysis_results: [],
  metrics: {}, stage_statuses: {}, warnings: [], errors: [],
  ...(datasetId ? { dataset_profile: { ...intakeFixture.profile, dataset_id: datasetId } } : {}),
});
const intake = (id: string) => ({ ...intakeFixture, profile: { ...intakeFixture.profile, dataset_id: id } });
function deferred() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}

function Probe() {
  const data = useIntake();
  const context = useReport();
  return <>
    <input aria-label="file" type="file" onChange={(e) => data.updateDraft({ file: e.target.files?.[0] || null })} />
    <button onClick={() => void data.analyze()}>load</button>
    <button onClick={data.reset}>reset</button>
    <button onClick={() => void context.generate("question")}>generate</button>
    <button onClick={() => void context.recover("run-a")}>recover A</button>
    <button onClick={() => void context.recover("run-b")}>recover B</button>
    <output data-testid="dataset">{data.result?.profile.dataset_id ?? "none"}</output>
    <output data-testid="run">{context.report?.run_id ?? "none"}</output>
    <output data-testid="compatible">{context.compatibleReport?.run_id ?? "none"}</output>
    <output data-testid="identity">{JSON.stringify(context.reportIdentity)}</output>
    <output data-testid="loading">{String(context.loading)}</output>
    <output data-testid="error">{context.error?.message}</output>
  </>;
}
function setup() {
  render(<IntakeProvider><ReportProvider><Probe /></ReportProvider></IntakeProvider>);
  return userEvent.setup();
}
async function loadDataset(user: ReturnType<typeof userEvent.setup>, id: string) {
  await user.upload(screen.getByLabelText("file"), new File(["x,y\n1,2"], id+".csv"));
  await user.click(screen.getByText("load", { exact: true }));
  await waitFor(() => expect(screen.getByTestId("dataset")).toHaveTextContent(id));
}
const identity = () => JSON.parse(screen.getByTestId("identity").textContent!);
afterEach(() => vi.unstubAllGlobals());

test("recovered reports are compatible only when their dataset ID matches", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intake("a"))
    : json(report(url.endsWith("run-a") ? "run-a" : "run-b", url.endsWith("run-a") ? "a" : "b"))));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("recover A"));
  expect(identity()).toMatchObject({ origin: "recovered", datasetId: "a", matchesActiveDataset: true });
  expect(screen.getByTestId("compatible")).toHaveTextContent("run-a");
  await user.click(screen.getByText("recover B"));
  expect(identity()).toMatchObject({ origin: "recovered", datasetId: "b", matchesActiveDataset: false });
  expect(screen.getByTestId("compatible")).toHaveTextContent("none");
  expect(screen.getByTestId("dataset")).toHaveTextContent("a");
});

test("legacy recovered reports do not inherit the active dataset identity", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intake("a")) : json(report("run-a"))));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("recover A"));
  expect(identity()).toMatchObject({ datasetId: null, matchesActiveDataset: null });
  expect(screen.getByTestId("compatible")).toHaveTextContent("none");
});

test("reset clears a historical report even when there is no active dataset", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(report("run-a", "a"))));
  const user = setup();
  await user.click(screen.getByText("recover A"));
  expect(screen.getByTestId("run")).toHaveTextContent("run-a");
  await user.click(screen.getByText("reset", { exact: true }));
  expect(screen.getByTestId("run")).toHaveTextContent("none");
});

test("a failed regeneration retains an explicitly previous report and removes compatibility", async () => {
  const pending = deferred();
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intake("a"))
    : ++calls === 1 ? json(report("run-a", "a")) : pending.promise));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("generate", { exact: true }));
  expect(screen.getByTestId("compatible")).toHaveTextContent("run-a");
  await user.click(screen.getByText("generate", { exact: true }));
  expect(identity()).toMatchObject({ previous: true, previousReason: "generating" });
  expect(screen.getByTestId("compatible")).toHaveTextContent("none");
  await act(async () => pending.resolve(json({ detail: "Service unavailable" }, 503)));
  expect(identity()).toMatchObject({ previous: true, previousReason: "generation-failed" });
  expect(screen.getByTestId("run")).toHaveTextContent("run-a");
  expect(screen.getByTestId("error")).toHaveTextContent("Service unavailable");
});

test("a failed recovery cannot present the previous report as the requested one", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("run-a") ? json(report("run-a", "a"))
    : json({ detail: "Not found" }, 404)));
  const user = setup();
  await user.click(screen.getByText("recover A"));
  await user.click(screen.getByText("recover B"));
  expect(identity()).toMatchObject({ previous: true, previousReason: "recovery-failed" });
  expect(screen.getByTestId("run")).toHaveTextContent("run-a");
});

test("a generation response for another dataset is rejected", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intake("a")) : json(report("wrong", "b"))));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("generate", { exact: true }));
  expect(screen.getByTestId("run")).toHaveTextContent("none");
  expect(screen.getByTestId("error")).toHaveTextContent("no corresponde al dataset solicitado");
});

test("a recovery response with an unexpected run ID is rejected", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(report("wrong", "a"))));
  const user = setup();
  await user.click(screen.getByText("recover A"));
  expect(screen.getByTestId("run")).toHaveTextContent("none");
  expect(screen.getByTestId("error")).toHaveTextContent("ID de ejecución solicitado");
});

test("late responses from dataset A cannot overwrite dataset B or end its loading state", async () => {
  const old = deferred(), next = deferred();
  let loads = 0;
  let oldSignal: AbortSignal | undefined;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/intake")) return json(intake(++loads === 1 ? "a" : "b"));
    if (url.endsWith("/a")) { oldSignal = init?.signal as AbortSignal; return old.promise; }
    return next.promise;
  }));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("generate", { exact: true }));
  await loadDataset(user, "b");
  expect(oldSignal?.aborted).toBe(true);
  await user.click(screen.getByText("generate", { exact: true }));
  await act(async () => old.resolve(json(report("run-a", "a"))));
  expect(screen.getByTestId("run")).toHaveTextContent("none");
  expect(screen.getByTestId("loading")).toHaveTextContent("true");
  await act(async () => next.resolve(json(report("run-b", "b"))));
  expect(screen.getByTestId("compatible")).toHaveTextContent("run-b");
  expect(screen.getByTestId("loading")).toHaveTextContent("false");
});

test("a recovery completed after reset cannot restore the old context", async () => {
  const pending = deferred();
  vi.stubGlobal("fetch", vi.fn(() => pending.promise));
  const user = setup();
  await user.click(screen.getByText("recover A"));
  await user.click(screen.getByText("reset", { exact: true }));
  await act(async () => pending.resolve(json(report("run-a", "a"))));
  expect(screen.getByTestId("run")).toHaveTextContent("none");
  expect(screen.getByTestId("loading")).toHaveTextContent("false");
});


test("a returned FAILED report replaces the former success instead of passing it off as current", async () => {
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/intake") ? json(intake("a"))
    : json(++calls === 1 ? report("run-a", "a") : { ...report("failed-run", "a"), status: "FAILED", errors: ["Workflow timeout"] })));
  const user = setup();
  await loadDataset(user, "a");
  await user.click(screen.getByText("generate", { exact: true }));
  await user.click(screen.getByText("generate", { exact: true }));
  expect(screen.getByTestId("run")).toHaveTextContent("failed-run");
  expect(identity()).toMatchObject({ previous: false, matchesActiveDataset: true });
});
