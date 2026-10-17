import { LoaderCircle } from "lucide-react";
import { useState } from "react";
import { BoxPlot } from "../../components/charts/BoxPlot";
import { formatValue } from "../../components/charts/chart-utils";
import { Histogram } from "../../components/charts/Histogram";
import { Card } from "../../components/ui/card";
import type { BoxPlotChart, HistogramChart, NumericSummary, OutlierSummary } from "../../types/exploration";
import { useTool } from "./useTool";

export function ColumnExplorer({ datasetId, numeric, categorical }: {
  datasetId: string;
  numeric: string[];
  categorical: string[];
}) {
  const [column, setColumn] = useState(numeric[0]);
  const [groupBy, setGroupBy] = useState("");
  const histogram = useTool(datasetId, "chart_histogram", [column]);
  const box = useTool(datasetId, "chart_boxplot", groupBy ? [column, groupBy] : [column]);
  const summary = useTool(datasetId, "descriptive_statistics", [column]);
  const outliers = useTool(datasetId, "outliers", [column]);
  const stats = (summary.data?.result as Record<string, NumericSummary> | undefined)?.[column];
  const outlierStats = (outliers.data?.result as Record<string, OutlierSummary> | undefined)?.[column];

  return <Card className="explorer-card">
    <div className="card-heading"><div><h2>Column distribution</h2>
      <p>Histogram, box plot and outlier screening for one numeric column.</p></div>
      <div className="explorer-controls">
        <div className="field"><label htmlFor="explore-column">Column</label>
          <select id="explore-column" value={column} onChange={(event) => setColumn(event.target.value)}>
            {numeric.map((name) => <option key={name}>{name}</option>)}</select></div>
        <div className="field"><label htmlFor="explore-group">Group box plot by</label>
          <select id="explore-group" value={groupBy} onChange={(event) => setGroupBy(event.target.value)}>
            <option value="">No grouping</option>
            {categorical.map((name) => <option key={name}>{name}</option>)}</select></div>
      </div>
    </div>
    <dl className="stat-strip">
      {[
        ["Mean", stats?.mean], ["Median", stats?.median], ["Std. dev.", stats?.std],
        ["Min", stats?.min], ["Max", stats?.max], ["Skewness", stats?.skewness],
      ].map(([label, value]) => <div key={label as string}><dt>{label}</dt><dd>{formatValue(value as number | null | undefined)}</dd></div>)}
      <div><dt>IQR outliers</dt><dd>{outlierStats ? `${outlierStats.iqr.count} (${formatValue(outlierStats.iqr.percentage, 1)}%)` : "—"}</dd></div>
      <div><dt>Robust (MAD) outliers</dt><dd>{outlierStats?.mad.count == null ? "—" : outlierStats.mad.count}</dd></div>
    </dl>
    <div className="explorer-charts">
      <div><h3 className="chart-title">Distribution</h3>
        {histogram.data?.status === "SUCCESS"
          ? <Histogram chart={histogram.data.result as unknown as HistogramChart} stale={histogram.stale} />
          : <ChartState loading={histogram.loading} message={histogram.error?.message ?? histogram.data?.warnings?.[0]} />}
      </div>
      <div><h3 className="chart-title">Spread{groupBy && ` by ${groupBy}`}</h3>
        {box.data?.status === "SUCCESS"
          ? <BoxPlot chart={box.data.result as unknown as BoxPlotChart} stale={box.stale} />
          : <ChartState loading={box.loading} message={box.error?.message ?? box.data?.warnings?.[0]} />}
        {box.data?.warnings?.map((note) => <p className="chart-note" key={note}>{note}</p>)}
      </div>
    </div>
  </Card>;
}

function ChartState({ loading, message }: { loading: boolean; message?: string }) {
  return <div className="chart-placeholder">
    {loading ? <><LoaderCircle size={16} className="spin" />Computing…</> : message ?? "Not available."}
  </div>;
}
