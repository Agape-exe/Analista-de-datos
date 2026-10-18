import { Check, FileText, LoaderCircle, Plus } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useIntake } from "../../features/data-intake/IntakeProvider";
import { useReport } from "../../features/reports/ReportProvider";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export function DatasetHeader() {
  const { result, draft, loading, error, reset } = useIntake();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { report } = useReport();
  const reportContext = (pathname === "/trace" || pathname === "/report") && report;
  return <header className="dataset-header">
    {reportContext ? <div className="dataset-context"><FileText size={16} className="muted" />
      <span className="dataset-filename">Reporte {reportContext.run_id}</span><Badge>{reportContext.status}</Badge>
      <span>Dataset: {reportContext.dataset_id ?? reportContext.dataset_profile?.dataset_id ?? "No registrado"}</span>
    </div> : <div className="dataset-context">
      <FileText size={16} className="muted" />
      <span className="dataset-filename">{result?.filename || draft.file?.name || "Ningún dataset cargado"}</span>
      {loading ? <Badge tone="info"><LoaderCircle size={12} className="spin" />Procesando ingesta</Badge>
        : result ? <><Badge>INGESTA</Badge><Badge tone="success"><Check size={12} />Ingesta completada</Badge>
          <span className="elapsed">{result.profiling_time.toFixed(2)} s</span></>
          : <Badge tone={error ? "warning" : "neutral"}>{error ? "Requiere corrección" : "Sin iniciar"}</Badge>}
    </div>}
    <Button variant="outline" size="small" disabled={loading} onClick={() => { reset(); navigate("/"); }}>
      <Plus size={13} /><span>Nuevo análisis</span>
    </Button>
  </header>;
}
