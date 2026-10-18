import { LoaderCircle } from "lucide-react";
import { Button } from "../../components/ui/button";
import { useDatasetPreview } from "../dataset/useDatasetPreview";

/** The exact original record behind an example, read on demand from the dataset preview. */
export function RecordDetail({ datasetId, rowIndex, column }: { datasetId: string; rowIndex: number; column: string }) {
  const { page, error, loading, retry } = useDatasetPreview(datasetId, rowIndex, 1);
  const label = `Registro ${rowIndex + 1}`;
  if (loading) return <p role="status"><LoaderCircle size={14} className="spin" />Consultando {label}…</p>;
  if (error) return <div role="alert"><p>{error.message}</p>
    {error.kind === "request" && <Button variant="outline" size="small" onClick={retry}>Reintentar</Button>}</div>;
  const row = page?.rows[0];
  if (!page || !row) return <p role="alert">El servidor no devolvió {label}. No se infiere a partir del valor.</p>;
  return <dl className="record-detail" aria-label={`Valores de ${label}`}>
    {page.columns.map((item, position) => {
      const value = row[position];
      return <div key={item.name} className={item.name === column ? "analysed" : undefined}>
        <dt>{item.name}{item.name === column && <small> · columna analizada</small>}</dt>
        <dd>{value === null ? <span className="muted">Nulo</span> : String(value)}</dd>
      </div>;
    })}
  </dl>;
}
