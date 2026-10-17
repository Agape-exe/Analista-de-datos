import { TriangleAlert } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { formatPValue, formatValue } from "../../components/charts/chart-utils";
import type { RankedRelationship } from "../../types/exploration";
import { methodLabel } from "./methods";

export function relationshipKey(item: { x: string; y: string }) {
  return [item.x, item.y].sort().join("\u0000");
}

export function RelationshipTable({ relationships, selected, onSelect }: {
  relationships: RankedRelationship[];
  selected: string | null;
  onSelect: (item: RankedRelationship) => void;
}) {
  return <div className="table-scroll" role="region" aria-label="Ranked relationships" tabIndex={0}>
    <table className="ranking-table"><thead><tr>
      <th>#</th><th>Variables</th><th>Method</th><th>Score</th><th>Strength</th><th>Adj. p-value</th><th>n</th><th>Notes</th><th />
    </tr></thead>
      <tbody>{relationships.map((item, index) => {
        const key = relationshipKey(item);
        const active = key === selected;
        return <tr key={key} className={active ? "selected" : ""}>
          <td className="muted">{index + 1}</td>
          <td className="variable-name">{item.x} <span className="muted">↔</span> {item.y}</td>
          <td>{methodLabel(item.method)}</td>
          <td><span className="score-cell"><span className="score-track"><span className="score-bar" style={{ width: `${item.score * 100}%` }} /></span>
            {item.score.toFixed(2)}</span></td>
          <td>{formatValue(item.strength)}</td>
          <td>{formatPValue(item.adjusted_p_value)}</td>
          <td>{formatValue(item.sample_size, 0)}</td>
          <td>{item.warnings.length > 0
            ? <Badge tone="warning" title={item.warnings.join("\n")}><TriangleAlert size={10} />{item.warnings.length}</Badge>
            : <span className="muted">—</span>}</td>
          <td><button type="button" className="link-button" aria-pressed={active}
            aria-label={`View ${item.x} and ${item.y}`} onClick={() => onSelect(item)}>{active ? "Viewing" : "View"}</button></td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}
