import { BookOpen, Download, LoaderCircle, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { downloadJson } from "../../lib/download";
import type { IntakeResponse } from "../../types/intake";
import { useIntake } from "../data-intake/IntakeProvider";
import { DataDictionaryTable } from "./DataDictionaryTable";
import { dictionaryMessage } from "./dictionary-presentation";

export function DataDictionaryPage() {
  const { result, loading, error } = useIntake();
  if (loading) return <div className="processing-panel" role="status" aria-live="polite">
    <LoaderCircle size={18} className="spin" /><div><h1>Preparando el diccionario</h1><p>Espera a que termine la carga del dataset.</p></div>
  </div>;
  if (error) return <Card className="empty-state"><TriangleAlert size={28} />
    <div role="alert"><h1>No se pudo preparar el diccionario</h1>
      <p>La carga del dataset falló. Revisa el archivo CSV o TSV, el separador y el diccionario proporcionado para volver a intentarlo.</p>
      {error.requestId && <p>ID de solicitud: {error.requestId}</p>}</div>
    <Button asChild><Link to="/">Revisar carga</Link></Button>
  </Card>;
  if (!result) return <Card className="empty-state"><span className="upload-icon"><BookOpen size={28} /></span>
    <h1>Aún no hay dataset</h1><p>Primero carga un archivo CSV o TSV en Nuevo análisis para consultar su diccionario de datos.</p>
    <Button asChild><Link to="/">Ir a Nuevo análisis</Link></Button>
  </Card>;
  return <DictionaryContent key={result.profile.dataset_id} result={result} />;
}

function DictionaryContent({ result }: { result: IntakeResponse }) {
  const [downloadError, setDownloadError] = useState(false);
  const warnings = result.warnings ?? [];
  function download() {
    try {
      downloadJson(`${result.filename.replace(/\.[^.]+$/, "")}.dictionary.json`, result.summary.data_dictionary);
      setDownloadError(false);
    } catch {
      setDownloadError(true);
    }
  }
  return <div className="dataset-page dictionary-page">
    <div className="page-heading with-actions"><div><p className="eyebrow">Datos / Diccionario de datos</p>
      <h1>Diccionario de datos</h1><p>Metadatos de <strong>{result.filename}</strong>. Consulta su procedencia antes de interpretar cada columna.</p></div>
      <Button variant="outline" onClick={download} disabled={!result.summary.data_dictionary.entries?.length}><Download size={14} />Descargar diccionario JSON</Button>
    </div>
    <div className="provenance-bar dictionary-legend"><Badge>Proporcionado en el diccionario</Badge><Badge tone="info">Inferido · sin verificar</Badge>
      <span>Observado: tipo técnico del archivo. No disponible: dato ausente. No evaluada: confianza ausente.</span></div>
    {downloadError && <div className="error-panel" role="alert"><TriangleAlert size={18} /><p>No se pudo descargar el diccionario. Vuelve a pulsar el botón de descarga para reintentar.</p></div>}
    <DataDictionaryTable result={result} />
    {warnings.length > 0 && <Card className="warnings-card"><div className="card-heading"><h2><TriangleAlert size={17} />Advertencias del dataset</h2></div>
      <ul>{warnings.map((warning, index) => <li key={index}>{dictionaryMessage(warning)}</li>)}</ul></Card>}
  </div>;
}
