import { ArrowRight, CheckCircle2, Database, Download, Info, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { downloadJson } from "../../lib/download";
import { formatNumber } from "../../lib/utils";
import { useIntake } from "../data-intake/IntakeProvider";
import { ColumnUnderstandingTable } from "./ColumnUnderstandingTable";
import { DatasetMetrics } from "./DatasetMetrics";
import { DatasetPreviewPanel } from "./DatasetPreview";

export function DatasetOverviewPage() {
  const { result } = useIntake();
  if (!result || !result.profile.dataset_id) return <Card className="empty-state"><span className="upload-icon"><Database size={28} /></span>
    <h1>Aún no hay dataset</h1><p>Sube un CSV o TSV para comprender su estructura y revisar las columnas detectadas.</p>
    <Button asChild><Link to="/">Subir dataset <ArrowRight size={15} /></Link></Button>
  </Card>;
  const baseName = result.filename.replace(/\.[^.]+$/, "");
  const warnings = result.warnings ?? [];
  return <div className="dataset-page">
    <div className="provenance-bar"><Badge tone="info">Medido a partir de tu dataset</Badge><span>Ingesta determinista · sin interpretación de LLM</span></div>
    <div className="page-heading with-actions"><div><p className="eyebrow">Datos / Dataset</p><h1>Resumen del dataset</h1>
      <p>Comprende lo que detectó el sistema antes de explorar tus resultados.</p></div>
      <Button asChild><Link to="/associations">Explorar asociaciones <ArrowRight size={14} /></Link></Button>
    </div>
    <DatasetMetrics result={result} />
    <DatasetPreviewPanel key={result.profile.dataset_id} datasetId={result.profile.dataset_id} />
    <ColumnUnderstandingTable result={result} />
    <Card className="quality-card"><div className="card-heading"><div><h2>Calidad de datos de un vistazo</h2>
      <p>Completitud medida y estado de validación. Los controles de calidad avanzados vienen después.</p></div></div>
      <div className="quality-grid">
        <div><CheckCircle2 size={16} className="success-text" /><strong>Estructura validada</strong><p>Encabezados únicos y filas con ancho consistente</p></div>
        <div><Info size={16} /><strong>{formatNumber(result.completeness.missing_cells)} celdas faltantes</strong><p>De {formatNumber(result.completeness.total_cells)} celdas en total</p></div>
        <div><span className="quality-dash">—</span><strong>Duplicados · no evaluado</strong><p>Los controles por registro están planificados</p></div>
        <div><span className="quality-dash">—</span><strong>Valores atípicos · no evaluado</strong><p>No se ha ejecutado detección de anomalías</p></div>
      </div>
    </Card>
    {warnings.length > 0 && <Card className="warnings-card"><div className="card-heading"><h2><TriangleAlert size={17} />Notas de revisión</h2>
      <Badge tone="warning">{warnings.length} {warnings.length === 1 ? "advertencia" : "advertencias"}</Badge></div>
      <ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
    </Card>}
    <div className="results-footer"><div><h2>Tu comprensión empieza aquí</h2><p>Descarga los metadatos para revisarlos o compartirlos con tu equipo.</p></div>
      <div className="inline-actions"><Button variant="outline" onClick={() => downloadJson(`${baseName}.profile.json`, result.profile)}>
        <Download size={14} />Descargar perfil</Button>
        <Button variant="outline" onClick={() => downloadJson(`${baseName}.dictionary.json`, result.summary.data_dictionary)}>
          <Download size={14} />Descargar diccionario</Button></div>
    </div>
    <div className="info-note"><Info size={16} /><div><strong>Ingesta completada. Ahora explora las asociaciones.</strong>
      <p>Esta vista contiene la estructura medida y las inferencias claramente marcadas. Las asociaciones están disponibles como candidatas estadísticas y, en Hallazgos, puedes generar el reporte con su evidencia sobre este mismo dataset.</p></div></div>
  </div>;
}
