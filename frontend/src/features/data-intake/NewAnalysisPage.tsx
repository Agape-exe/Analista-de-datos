import { ArrowRight, CheckCircle2, Database, Info, LoaderCircle, TriangleAlert } from "lucide-react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { useIntake } from "./IntakeProvider";
import { DatasetUpload } from "./DatasetUpload";
import { DataDictionaryUpload } from "./DataDictionaryUpload";

export function NewAnalysisPage() {
  const { draft, updateDraft, loading, error, analyze } = useIntake();
  const navigate = useNavigate();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await analyze()) navigate("/dataset");
  }
  return <div className="new-analysis-page">
    <div className="page-heading"><p className="eyebrow">Nuevo análisis</p>
      <h1>Analiza tus datos</h1>
      <p>Empieza con un dataset. Comprende su estructura antes de explorar relaciones y hallazgos.</p>
    </div>
    <Card className="intake-card"><form onSubmit={submit}>
      <DatasetUpload file={draft.file} disabled={loading} onChange={(file) => updateDraft({ file })} />
      <div className="upload-caption"><span><Database size={13} />Conectar a SQL <Badge>Próximamente</Badge></span>
        <span>Tu dataset se procesa localmente con Python.</span></div>
      <div className="reading-options">
        <div className="field"><label htmlFor="delimiter">Separador CSV</label>
          <select id="delimiter" value={draft.delimiter} disabled={loading || draft.file?.name.toLowerCase().endsWith(".tsv")}
            onChange={(event) => updateDraft({ delimiter: event.target.value })}>
            <option value=",">Coma (,)</option><option value=";">Punto y coma (;)</option>
            <option value={"\t"}>Tabulación</option><option value="|">Barra vertical (|)</option>
          </select>
        </div>
        <div className="field"><label htmlFor="encoding">Codificación del archivo</label>
          <select id="encoding" value={draft.encoding} disabled={loading} onChange={(event) => updateDraft({ encoding: event.target.value })}>
            <option value="utf-8">UTF-8</option><option value="utf-8-sig">UTF-8 con BOM</option>
            <option value="cp1252">Windows-1252</option><option value="latin-1">Latin-1</option>
          </select>
        </div>
      </div>
      <DataDictionaryUpload file={draft.dictionary} disabled={loading} onChange={(dictionary) => updateDraft({ dictionary })} />
      <div className="field"><p>Después de comprender el dataset puedes indicar tu pregunta y configurar el planificador en <Link to="/report">Configurar Hallazgos</Link>.</p></div>
      <fieldset className="mode-fieldset"><legend>Modo de análisis</legend><div className="mode-options">
        <div className="mode-card selected"><div><span className="eyebrow">Ingesta</span><CheckCircle2 size={16} /></div>
          <strong>Comprende tu dataset</strong><p>Valida el archivo, clasifica las columnas y construye un diccionario de datos.</p></div>
        <div className="mode-card"><div><span className="eyebrow">Rápido / Estándar</span><Badge>Disponible en Hallazgos</Badge></div>
          <strong>Explora la evidencia</strong><p>Tras la ingesta, ejecuta herramientas estadísticas, controles y revisión de evidencia. Consulta el plan y los eventos en Traza.</p></div>
      </div></fieldset>
      {error && <div className="error-panel" role="alert"><TriangleAlert size={19} /><div>
        <strong>No se pudo procesar el dataset</strong><p>{error.message}</p>
        <p>Revisa el formato del archivo, el separador y el diccionario, y vuelve a intentarlo. Tu configuración se conserva.</p>
        {error.requestId && <small>ID de solicitud: <code>{error.requestId}</code></small>}
      </div></div>}
      {loading && <div className="processing-panel" role="status" aria-live="polite">
        <LoaderCircle size={18} className="spin" /><div><strong>Comprendiendo tu dataset</strong>
          <p>Leyendo y validando el archivo, perfilando columnas y preparando el diccionario.</p></div>
      </div>}
      <div className="form-footer"><p>{draft.file ? "Listo para revisar tus datos. No se ejecutará ningún análisis estadístico." : "Selecciona un dataset para comenzar. Aún no se ha ejecutado ningún análisis."}</p>
        <Button type="submit" disabled={!draft.file || loading}>
          {loading ? <LoaderCircle size={15} className="spin" /> : <ArrowRight size={15} />}
          {loading ? "Procesando…" : "Comprender dataset"}
        </Button>
      </div>
    </form></Card>
    <div className="info-note"><Info size={16} /><div><strong>Un espacio de análisis, no una ventana de chat</strong>
      <p>Empieza por los datos. Revisa el esquema detectado y su procedencia. Luego explora las asociaciones y genera el reporte de hallazgos.</p>
    </div></div>
  </div>;
}
