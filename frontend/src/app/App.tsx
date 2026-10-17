import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { AssociationsPage } from "../features/associations/AssociationsPage";
import { IntakeProvider } from "../features/data-intake/IntakeProvider";
import { NewAnalysisPage } from "../features/data-intake/NewAnalysisPage";
import { DatasetOverviewPage } from "../features/dataset/DatasetOverviewPage";

import { ReportPage } from "../features/reports/ReportPage";

export function App() {
  return <IntakeProvider><Routes><Route element={<AppShell />}>
    <Route index element={<NewAnalysisPage />} />
    <Route path="report" element={<ReportPage />} />
    <Route path="dataset" element={<DatasetOverviewPage />} />
    <Route path="associations" element={<AssociationsPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route></Routes></IntakeProvider>;
}
