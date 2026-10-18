import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { AssociationsPage } from "../features/associations/AssociationsPage";
import { IntakeProvider } from "../features/data-intake/IntakeProvider";
import { NewAnalysisPage } from "../features/data-intake/NewAnalysisPage";
import { DatasetOverviewPage } from "../features/dataset/DatasetOverviewPage";
import { DataDictionaryPage } from "../features/dataset/DataDictionaryPage";
import { DataQualityPage } from "../features/quality/DataQualityPage";
import { MetricsPage } from "../features/metrics/MetricsPage";
import { TracePage } from "../features/trace/TracePage";
import { ReportPage } from "../features/reports/ReportPage";
import { ReportProvider } from "../features/reports/ReportProvider";
import { SummaryPage } from "../features/summary/SummaryPage";

export function App() {
  return <IntakeProvider><ReportProvider><Routes><Route element={<AppShell />}>
    <Route index element={<NewAnalysisPage />} />
    <Route path="summary" element={<SummaryPage />} />
    <Route path="metrics" element={<MetricsPage />} />
    <Route path="trace" element={<TracePage />} />
    <Route path="report" element={<ReportPage />} />
    <Route path="dataset" element={<DatasetOverviewPage />} />
    <Route path="dictionary" element={<DataDictionaryPage />} />
    <Route path="quality" element={<DataQualityPage />} />
    <Route path="associations" element={<AssociationsPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes></ReportProvider></IntakeProvider>;
}
