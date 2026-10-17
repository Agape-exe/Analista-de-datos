import { Outlet } from "react-router-dom";
import { DatasetHeader } from "./DatasetHeader";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Saltar al contenido</a>
    <Sidebar />
    <div className="workspace"><DatasetHeader />
      <main id="main-content" className="main-content"><Outlet /></main>
    </div>
  </div>;
}
