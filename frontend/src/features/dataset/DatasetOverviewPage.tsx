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

export function DatasetOverviewPage() {
  const { result } = useIntake();
  if (!result) return <Card className="empty-state"><span className="upload-icon"><Database size={28} /></span>
    <h1>No dataset yet</h1><p>Upload a CSV or TSV to understand its structure and review the detected columns.</p>
    <Button asChild><Link to="/">Upload dataset <ArrowRight size={15} /></Link></Button>
  </Card>;
  const baseName = result.filename.replace(/\.[^.]+$/, "");
  const warnings = result.warnings ?? [];
  return <div className="dataset-page">
    <div className="provenance-bar"><Badge tone="info">Measured from your dataset</Badge><span>Deterministic intake · no LLM interpretation</span></div>
    <div className="page-heading with-actions"><div><p className="eyebrow">Data / Dataset</p><h1>Dataset Overview</h1>
      <p>Understand what the system detected before exploring your results.</p></div>
      <Button disabled title="Statistical tools are not implemented yet">Explore Associations <ArrowRight size={14} /></Button>
    </div>
    <DatasetMetrics result={result} />
    <ColumnUnderstandingTable result={result} />
    <Card className="quality-card"><div className="card-heading"><div><h2>Data quality at a glance</h2>
      <p>Measured completeness and validation status. Advanced quality checks come next.</p></div></div>
      <div className="quality-grid">
        <div><CheckCircle2 size={16} className="success-text" /><strong>Structure validated</strong><p>Unique headers and consistent row widths</p></div>
        <div><Info size={16} /><strong>{formatNumber(result.completeness.missing_cells)} missing cells</strong><p>Out of {formatNumber(result.completeness.total_cells)} total cells</p></div>
        <div><span className="quality-dash">—</span><strong>Duplicates · not evaluated</strong><p>Record-level checks are planned</p></div>
        <div><span className="quality-dash">—</span><strong>Outliers · not evaluated</strong><p>No anomaly screening has run</p></div>
      </div>
    </Card>
    {warnings.length > 0 && <Card className="warnings-card"><div className="card-heading"><h2><TriangleAlert size={17} />Review notes</h2>
      <Badge tone="warning">{warnings.length} warnings</Badge></div>
      <ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
    </Card>}
    <div className="results-footer"><div><h2>Your understanding starts here</h2><p>Download the metadata to review it or share it with your team.</p></div>
      <div className="inline-actions"><Button variant="outline" onClick={() => downloadJson(`${baseName}.profile.json`, result.profile)}>
        <Download size={14} />Download profile</Button>
        <Button variant="outline" onClick={() => downloadJson(`${baseName}.dictionary.json`, result.summary.data_dictionary)}>
          <Download size={14} />Download dictionary</Button></div>
    </div>
    <div className="info-note"><Info size={16} /><div><strong>Intake completed. Analysis comes next.</strong>
      <p>This view contains measured structure and clearly marked inferences. Associations, robustness checks and insights will be enabled as their tools become available.</p></div></div>
  </div>;
}
