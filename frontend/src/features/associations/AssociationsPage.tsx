import { ArrowRight, Info, LoaderCircle, ScanSearch, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CorrelationHeatmap } from "../../components/charts/CorrelationHeatmap";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { formatNumber } from "../../lib/utils";
import type { HeatmapChart, RankedRelationship, RelationshipRanking } from "../../types/exploration";
import { useIntake } from "../data-intake/IntakeProvider";
import { ColumnExplorer } from "./ColumnExplorer";
import { RelationshipDetail } from "./RelationshipDetail";
import { relationshipKey, RelationshipTable } from "./RelationshipTable";
import { useTool, type ToolError } from "./useTool";

export function AssociationsPage() {
  const { result } = useIntake();
  const datasetId = result?.profile.dataset_id;
  const numeric = result?.summary.numeric_columns ?? [];
  const categorical = result?.summary.categorical_columns ?? [];
  const ranking = useTool(datasetId, "relationship_ranking", []);
  const heatmap = useTool(datasetId, "chart_correlation_heatmap", numeric.length >= 2 ? [] : null);
  const [picked, setPicked] = useState<{ x: string; y: string } | null>(null);

  if (!result || !datasetId) return <Card className="empty-state"><span className="upload-icon"><ScanSearch size={28} /></span>
    <h1>No dataset yet</h1><p>Upload a CSV or TSV first. Associations are computed on the dataset kept in memory after intake.</p>
    <Button asChild><Link to="/">Upload dataset <ArrowRight size={15} /></Link></Button>
  </Card>;

  const expired = ranking.error?.expired || heatmap.error?.expired;
  if (expired) return <Card className="empty-state"><span className="upload-icon"><TriangleAlert size={28} /></span>
    <h1>Dataset no longer available</h1>
    <p>The server keeps a limited number of datasets in memory and forgets them on restart. Upload {result.filename} again to explore it.</p>
    <Button asChild><Link to="/">Upload again <ArrowRight size={15} /></Link></Button>
  </Card>;

  const data = ranking.data?.status === "SUCCESS" ? ranking.data.result as unknown as RelationshipRanking : null;
  const relationships = data?.top_relationships ?? [];
  const byKey = new Map(relationships.map((item) => [relationshipKey(item), item]));
  const pair = picked ?? relationships[0] ?? null;
  const selectedKey = pair ? relationshipKey(pair) : null;
  const heatmapChart = heatmap.data?.status === "SUCCESS" ? heatmap.data.result as unknown as HeatmapChart : null;
  const excluded = Object.entries(data?.excluded_columns ?? {});

  return <div className="associations-page">
    <div className="provenance-bar"><Badge tone="info">Computed in Python</Badge>
      <span>Deterministic statistics · no LLM interpretation</span></div>
    <div className="page-heading"><p className="eyebrow">Exploration / Associations</p><h1>Associations</h1>
      <p>Candidate relationships between columns of {result.filename}, ranked by a comparable strength score.</p></div>

    <div className="info-note candidates-note"><Info size={16} /><div><strong>These are statistical candidates, not findings.</strong>
      <p>Each pair is tested with the method that fits its column types. p-values are corrected for multiple comparisons
        ({data?.correction ?? "Benjamini-Hochberg"}) and only pairs below α = {data?.significance_level ?? 0.05} are listed.
        Correlation does not imply causation; robustness checks come next.</p></div></div>

    {ranking.loading && !ranking.data && <div className="processing-panel" role="status"><LoaderCircle size={16} className="spin" />
      <div><strong>Screening column pairs…</strong><p>Running correlation, group and contingency tests on every eligible pair.</p></div></div>}
    {ranking.error && <ErrorPanel error={ranking.error} />}
    {ranking.data && ranking.data.status !== "SUCCESS" && <div className="info-note"><Info size={16} /><div>
      <strong>No associations could be screened.</strong><p>{ranking.data.warnings?.[0]}</p></div></div>}

    {data && <>
      <div className="metrics-grid associations-metrics">
        <Metric label="Pairs evaluated" value={formatNumber(data.evaluated_pairs)} note="Numeric and categorical columns" />
        <Metric label="Significant candidates" value={formatNumber(data.significant_pairs)} note={`Adjusted p ≤ ${data.significance_level}`} />
        <Metric label="Shown" value={formatNumber(relationships.length)} note="Top ranked by score" />
        <Metric label="Excluded columns" value={formatNumber(excluded.length)} note="Constant or too many categories" />
      </div>

      <Card className="ranking-card"><div className="card-heading"><div><h2>Ranked relationships</h2>
        <p>Score is |r|, |ρ|, Cramér's V, η or √ε² — all on a 0–1 scale. Select a row to inspect it.</p></div>
        <Badge>{relationships.length} candidates</Badge></div>
        {relationships.length > 0
          ? <RelationshipTable relationships={relationships} selected={selectedKey}
            onSelect={(item: RankedRelationship) => setPicked({ x: item.x, y: item.y })} />
          : <p className="muted">No pair reached significance after correction.</p>}
        {pair && <RelationshipDetail key={selectedKey} datasetId={datasetId} x={pair.x} y={pair.y}
          ranked={byKey.get(selectedKey!)} numeric={numeric} />}
      </Card>
    </>}

    {numeric.length >= 2 && <Card className="heatmap-card"><div className="card-heading"><div><h2>Correlation matrix</h2>
      <p>Pearson r between numeric columns, pairwise complete rows. Select a cell to inspect the pair.</p></div></div>
      {heatmapChart ? <CorrelationHeatmap chart={heatmapChart} stale={heatmap.stale}
        onSelect={(x, y) => setPicked({ x, y })} />
        : heatmap.error ? <ErrorPanel error={heatmap.error} />
          : <div className="chart-placeholder"><LoaderCircle size={16} className="spin" />Computing matrix…</div>}
    </Card>}

    {numeric.length > 0 && <ColumnExplorer datasetId={datasetId} numeric={numeric} categorical={categorical} />}

    {(excluded.length > 0 || (data?.skipped_pairs.length ?? 0) > 0) && <Card className="warnings-card">
      <div className="card-heading"><h2><TriangleAlert size={17} />Not screened</h2></div>
      <ul>
        {excluded.map(([name, reason]) => <li key={name}><strong>{name}</strong>: {reason}</li>)}
        {data?.skipped_pairs.map((item) => <li key={`${item.x}-${item.y}`}><strong>{item.x} ↔ {item.y}</strong>: {item.reason}</li>)}
      </ul>
    </Card>}
  </div>;
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <Card className="metric-card"><p>{label}</p><strong>{value}</strong><small>{note}</small></Card>;
}

function ErrorPanel({ error }: { error: ToolError }) {
  return <div className="error-panel" role="alert"><TriangleAlert size={16} /><div><strong>{error.message}</strong>
    {error.requestId && <small>Request ID: {error.requestId}</small>}</div></div>;
}
