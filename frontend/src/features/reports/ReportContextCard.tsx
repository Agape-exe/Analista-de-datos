import { Card } from "../../components/ui/card";
import { useIntake } from "../data-intake/IntakeProvider";
import { useReport } from "./ReportProvider";

export function ReportContextCard() {
  const { result } = useIntake();
  const { reportIdentity } = useReport();
  return <Card className="quality-card" aria-label="Contexto del reporte">
        <h2>{reportIdentity?.origin === "recovered" ? "Reporte recuperado" : "Reporte generado"}</h2>
        <p>Dataset del reporte: {reportIdentity?.datasetId ?? "Identidad no disponible en este reporte histórico"}</p>
        <p>{reportIdentity?.matchesActiveDataset === true
          ? "Este reporte corresponde al dataset activo."
          : reportIdentity?.matchesActiveDataset === false
            ? "Este reporte pertenece a otro dataset. No describe el dataset activo."
            : result
              ? "No se puede verificar que este reporte corresponda al dataset activo."
              : "Consulta histórica: no hay un dataset activo asociado."}</p>
        {reportIdentity?.previous && <p role="status">{
          reportIdentity.previousReason === "generation-failed"
            ? "La regeneración falló. Se muestra el reporte anterior, no un resultado nuevo."
            : reportIdentity.previousReason === "recovery-failed"
              ? "La consulta falló. Se muestra el reporte anterior, no el solicitado."
              : reportIdentity.previousReason === "generation-cancelled" || reportIdentity.previousReason === "recovery-cancelled"
                ? "Se canceló la espera. Se muestra el reporte anterior; la ejecución en el servidor puede continuar."
                : "Se muestra el reporte anterior mientras se procesa la nueva solicitud."
        }</p>}
      </Card>;
}
