import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../app/App";
import type { AnalysisReport, GroundedAnswer } from "../../lib/api-client";
import { reportFixture } from "../../test/report-fixture";

const catalog = {
  perfil: "¿Cuál es el perfil del dataset?",
  evidencias: "¿Qué evidencias respaldan el reporte?",
  metricas: "¿Qué métricas se midieron?",
};

const report = (runId: string): AnalysisReport => ({
  ...reportFixture,
  run_id: runId,
  evidence: [{ evidence_id: "evidence-001", analysis_id: "analysis-001", description: "Coeficiente medido" }],
  analysis_results: [{ analysis_id: "analysis-001", method: "pearson", variables: ["x", "y"],
    status: "SUCCESS", completeness: "complete", execution_time: 0, warnings: [] }],
});

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

function renderApp(path = "/chat") {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

async function recoverAndOpenChat(user: ReturnType<typeof userEvent.setup>, runId = "chat-run") {
  await user.type(screen.getByLabelText("ID de ejecución"), runId);
  await user.click(screen.getByRole("button", { name: "Consultar" }));
  await screen.findByText(`Ejecución: ${runId}`);
  await user.click(screen.getByRole("link", { name: "Chat" }));
  await screen.findByRole("button", { name: `Usar pregunta: ${catalog.evidencias}` });
}

afterEach(() => vi.unstubAllGlobals());

describe("Chat fundamentado", () => {
  it("requires a report and does not request the catalog before one exists", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderApp();
    expect(screen.getByRole("heading", { name: "Sin reporte disponible" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Hallazgos" })).toHaveAttribute("href", "/report");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses the backend catalog and links an answered response to its original evidence", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/questions/catalog")) return json({ questions: catalog });
      if (url.endsWith("/reports/chat-run") && !init?.method) return json(report("chat-run"));
      if (url.endsWith("/reports/chat-run/questions")) {
        const body = JSON.parse(String(init?.body));
        return json({ question: body.question, status: "ANSWERED", answer: "Una evidencia medida.",
          references: [{ path: "/evidence/0", evidence_id: "evidence-001", analysis_id: "analysis-001" }] } satisfies GroundedAnswer);
      }
      return json({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderApp("/report");
    await recoverAndOpenChat(user);
    await user.click(screen.getByRole("button", { name: `Usar pregunta: ${catalog.evidencias}` }));
    expect(screen.getByLabelText("Pregunta para el reporte")).toHaveValue("evidencias");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));
    expect(await screen.findByText("Una evidencia medida.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidencia evidence-001" }))
      .toHaveAttribute("href", "/report#evidence-evidence-001");
    expect(screen.getByText("/evidence/0")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Métricas" }));
    await user.click(screen.getByRole("link", { name: "Chat" }));
    expect(screen.getByText("Una evidencia medida.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/questions/catalog"))).toHaveLength(1);
  });

  it("shows abstention without presenting invented references", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/questions/catalog")) return json({ questions: catalog });
      if (url.endsWith("/reports/chat-run") && !init?.method) return json(report("chat-run"));
      const body = JSON.parse(String(init?.body));
      return json({ question: body.question, status: "ABSTAINED", answer: "Pregunta no soportada.", references: [] });
    }));
    const user = userEvent.setup();
    renderApp("/report");
    await recoverAndOpenChat(user);
    await user.type(screen.getByLabelText("Pregunta para el reporte"), "predice ventas");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));
    expect(await screen.findByText("Pregunta no soportada.")).toBeInTheDocument();
    expect(screen.getByText("Abstención")).toBeInTheDocument();
    expect(screen.getByText("Sin referencias: el sistema se abstuvo de responder.")).toBeInTheDocument();
  });

  it("cancels an in-flight answer and discards it when the report context changes", async () => {
    let release!: (response: Response) => void;
    const held = new Promise<Response>((resolve) => { release = resolve; });
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/questions/catalog")) return json({ questions: catalog });
      if (url.endsWith("/reports/chat-run/questions")) return held;
      if (url.endsWith("/reports/chat-run") && !init?.method) return json(report("chat-run"));
      if (url.endsWith("/reports/chat-run-2") && !init?.method) return json(report("chat-run-2"));
      return json({ detail: "Not found" }, 404);
    }));
    const user = userEvent.setup();
    renderApp("/report");
    await recoverAndOpenChat(user);
    await user.click(screen.getByRole("button", { name: `Usar pregunta: ${catalog.evidencias}` }));
    await user.click(screen.getByRole("button", { name: "Preguntar" }));
    await user.click(screen.getByRole("button", { name: "Cancelar espera" }));
    expect(screen.getByRole("status")).toHaveTextContent("Se canceló la espera");

    await user.click(screen.getByRole("link", { name: "Hallazgos" }));
    await user.clear(screen.getByLabelText("ID de ejecución"));
    await user.type(screen.getByLabelText("ID de ejecución"), "chat-run-2");
    await user.click(screen.getByRole("button", { name: "Consultar" }));
    await screen.findByText("Ejecución: chat-run-2");
    await user.click(screen.getByRole("link", { name: "Chat" }));
    release(json({ question: "evidencias", status: "ANSWERED", answer: "Respuesta tardía",
      references: [{ path: "/evidence/0", evidence_id: "evidence-001" }] }));
    await waitFor(() => expect(screen.queryByText("Respuesta tardía")).not.toBeInTheDocument());
    expect(screen.getByText("Aún no hay respuestas para este reporte.")).toBeInTheDocument();
  });
});
