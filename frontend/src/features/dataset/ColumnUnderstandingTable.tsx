import { Info } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { formatNumber, formatPercentage } from "../../lib/utils";
import type { IntakeResponse } from "../../types/intake";

const roleLabels = { numeric: "Numérica", categorical: "Categórica", temporal: "Temporal", identifier: "Identificador", text: "Texto", unknown: "Desconocido" };
const sourceLabels = { official: "Oficial", manual: "Manual", schema: "Esquema", inferred: "Inferido" };

export function ColumnUnderstandingTable({ result }: { result: IntakeResponse }) {
  const dictionary = new Map((result.summary.data_dictionary.entries ?? []).map((entry) => [entry.column_name, entry]));
  return <Card className="column-card"><div className="card-heading"><div>
    <h2>Comprensión de columnas</h2><p>{result.summary.columns} columnas · los roles estructurales son mutuamente excluyentes.</p>
  </div><Badge>Solo lectura</Badge></div>
    <div className="table-scroll" role="region" aria-label="Tabla de comprensión de columnas" tabIndex={0}>
      <table><thead><tr><th>Columna</th><th>Tipo detectado</th><th>Rol</th><th>Descripción</th><th>% faltante</th><th>Únicos</th><th>Fuente</th><th>Confianza</th></tr></thead>
        <tbody>{(result.profile.columns ?? []).map((column) => {
          const entry = dictionary.get(column.column_name);
          const missing = result.completeness.column_missing_percentages[column.column_name] ?? 0;
          return <tr key={column.column_name}>
            <td className="variable-name">{column.column_name}</td><td><code>{column.data_type}</code></td>
            <td title={column.classification_reason || undefined}>{roleLabels[column.semantic_type || "unknown"]}</td>
            <td className="description-cell"><span>{entry?.description || "Sin descripción"}</span>
              {entry?.inferred_fields?.includes("description") && <small>Descripción inferida · significado de negocio sin verificar</small>}</td>
            <td className={missing > 0 ? "warning-text" : ""}>{formatPercentage(missing)}</td>
            <td>{column.unique_count == null ? "—" : formatNumber(column.unique_count)}</td>
            <td><Badge tone={entry?.source === "inferred" ? "info" : "neutral"}
              title={entry?.inferred_fields?.length ? `Campos inferidos: ${entry.inferred_fields.join(", ")}` : "Procedencia suministrada"}>
              {entry?.source === "inferred" && <Info size={10} />}{entry ? sourceLabels[entry.source] : "Desconocida"}
            </Badge></td>
            <td>{entry?.confidence == null ? <span className="muted">No evaluada</span> : formatPercentage(entry.confidence * 100)}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <p className="table-footnote"><Info size={13} />Los tipos técnicos y los roles inferidos describen la estructura observada. Las definiciones suministradas conservan su procedencia; los agregados inferidos se marcan por separado. Desplázate horizontalmente para ver todos los campos.</p>
  </Card>;
}
