import { ArrowRight, CheckCircle2, Database, Info, LoaderCircle, TriangleAlert } from "lucide-react";
import { useEffect, useRef, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { useIntake } from "./IntakeProvider";
import { DatasetUpload } from "./DatasetUpload";
import { DataDictionaryUpload } from "./DataDictionaryUpload";

export function NewAnalysisPage() {
  const { draft, updateDraft, loading, cancelled, cancel, error, analyze, contextRevision } = useIntake();
  const navigate = useNavigate();
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await analyze();
    if (response && mounted.current) navigate("/dataset");
  }
  return <div className="new-analysis-page">
    <div className="page-heading"><p className="eyebrow">Nuevo análisis</p>
      <h1>Analiza tus datos</h1>
      <p>Empieza con un dataset. Comprende su estructura antes de explorar relaciones y hallazgos.</p>
    </div>
    <Card className="intake-card"><form key={contextRevision} onSubmit={submit}>
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
      <div className="field planned-question"><label htmlFor="question">¿Qué te gustaría investigar? <Badge>Próximamente</Badge></label>
        <textarea id="question" disabled placeholder="Las preguntas de investigación estarán disponibles con el planificador de análisis." rows={2} />
      </div>
      <fieldset className="mode-fieldset"><legend>Modo de análisis</legend><div className="mode-options">
        <div className="mode-card selected"><div><span className="eyebrow">Ingesta</span><CheckCircle2 size={16} /></div>
          <strong>Comprende tu dataset</strong><p>Valida el archivo, clasifica las columnas y construye un diccionario de datos.</p></div>
        <div className="mode-card unavailable-mode"><div><span className="eyebrow">Rápido / Profundo</span><Badge>Próximamente</Badge></div>
          <strong>Explora la evidencia</strong><p>Herramientas estadísticas, controles y análisis multiagente en una próxima etapa.</p></div>
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
      {cancelled && <p role="status">Se canceló la espera de la carga. Los archivos y opciones se conservan para volver a intentarlo.</p>}
      {loading && <Button type="button" variant="outline" onClick={cancel}>Cancelar espera de carga</Button>}
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
