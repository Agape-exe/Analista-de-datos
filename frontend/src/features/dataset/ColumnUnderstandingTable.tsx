import { Info } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { formatNumber, formatPercentage } from "../../lib/utils";
import type { IntakeResponse } from "../../types/intake";

const roleLabels = { numeric: "Numeric", categorical: "Categorical", temporal: "Temporal", identifier: "Identifier", text: "Text", unknown: "Unknown" };
const sourceLabels = { official: "Official", manual: "Manual", schema: "Schema", inferred: "Inferred" };

export function ColumnUnderstandingTable({ result }: { result: IntakeResponse }) {
  const dictionary = new Map((result.summary.data_dictionary.entries ?? []).map((entry) => [entry.column_name, entry]));
  return <Card className="column-card"><div className="card-heading"><div>
    <h2>Column understanding</h2><p>{result.summary.columns} columns · structural roles are mutually exclusive.</p>
  </div><Badge>Read-only</Badge></div>
    <div className="table-scroll" role="region" aria-label="Column understanding table" tabIndex={0}>
      <table><thead><tr><th>Column</th><th>Detected type</th><th>Role</th><th>Description</th><th>Missing %</th><th>Unique</th><th>Source</th><th>Confidence</th></tr></thead>
        <tbody>{(result.profile.columns ?? []).map((column) => {
          const entry = dictionary.get(column.column_name);
          const missing = result.completeness.column_missing_percentages[column.column_name] ?? 0;
          return <tr key={column.column_name}>
            <td className="variable-name">{column.column_name}</td><td><code>{column.data_type}</code></td>
            <td title={column.classification_reason || undefined}>{roleLabels[column.semantic_type || "unknown"]}</td>
            <td className="description-cell"><span>{entry?.description || "No description supplied"}</span>
              {entry?.inferred_fields?.includes("description") && <small>Inferred description · business meaning unverified</small>}</td>
            <td className={missing > 0 ? "warning-text" : ""}>{formatPercentage(missing)}</td>
            <td>{column.unique_count == null ? "—" : formatNumber(column.unique_count)}</td>
            <td><Badge tone={entry?.source === "inferred" ? "info" : "neutral"}
              title={entry?.inferred_fields?.length ? `Inferred fields: ${entry.inferred_fields.join(", ")}` : "Supplied provenance"}>
              {entry?.source === "inferred" && <Info size={10} />}{entry ? sourceLabels[entry.source] : "Unknown"}
            </Badge></td>
            <td>{entry?.confidence == null ? <span className="muted">Not evaluated</span> : formatPercentage(entry.confidence * 100)}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <p className="table-footnote"><Info size={13} />Technical types and inferred roles describe observed structure. Supplied definitions retain their provenance; inferred additions are marked separately. Scroll horizontally to see all fields.</p>
  </Card>;
}
