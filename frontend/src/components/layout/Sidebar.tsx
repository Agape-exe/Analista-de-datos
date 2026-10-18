import { NavLink, useNavigate } from "react-router-dom";
import { Activity, BookOpen, ChartNoAxesCombined, CircleHelp, Database, GitBranch, Layers,
  LayoutDashboard, ListChecks, MessageSquare, Plus, ScanSearch, ShieldCheck, Sparkles, TriangleAlert,
  type LucideIcon } from "lucide-react";
import { useIntake } from "../../features/data-intake/IntakeProvider";
import { Button } from "../ui/button";

const groups: { label?: string; links: { label: string; icon: LucideIcon; to?: string }[] }[] = [
  { links: [{ label: "Resumen", icon: LayoutDashboard }] },
  { label: "Datos", links: [
    { label: "Dataset", icon: Database, to: "/dataset" },
    { label: "Calidad de datos", icon: ShieldCheck, to: "/quality" }, { label: "Diccionario de datos", icon: BookOpen, to: "/dictionary" },
  ] },
  { label: "Exploración", links: [
    { label: "Asociaciones", icon: ScanSearch, to: "/associations" }, { label: "Patrones", icon: Layers, to: "/patterns" },
    { label: "Anomalías", icon: TriangleAlert, to: "/anomalies" },
  ] },
  { label: "Análisis", links: [
    { label: "Relaciones", icon: GitBranch }, { label: "Hallazgos", icon: Sparkles, to: "/report" },
  ] },
  { label: "Evaluación", links: [
    { label: "Traza", icon: ListChecks, to: "/trace" }, { label: "Métricas", icon: Activity },
  ] },
  { label: "Asistente", links: [{ label: "Chat", icon: MessageSquare }] },
];

export function Sidebar() {
  const { reset, loading } = useIntake();
  const navigate = useNavigate();
  return <aside className="sidebar">
    <a className="brand" href="/" aria-label="Inicio de Analista de Datos IA">
      <span className="brand-icon"><ChartNoAxesCombined size={17} /></span>
      <span className="sidebar-label">Analista de Datos IA</span>
    </a>
    <Button className="new-analysis" aria-label="Nuevo análisis" disabled={loading} onClick={() => { reset(); navigate("/"); }}>
      <Plus size={15} /><span className="sidebar-label">Nuevo análisis</span>
    </Button>
    <nav aria-label="Navegación principal">
      {groups.map((group, index) => <div className="nav-group" key={group.label || index}>
        {group.label && <p className="nav-group-label">{group.label}</p>}
        {group.links.map(({ label, icon: Icon, to }) => to
          ? <NavLink key={label} to={to} title={label} aria-label={label} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <Icon size={15} /><span className="sidebar-label">{label}</span>
          </NavLink>
          : <button key={label} className="nav-item unavailable" disabled title={`${label} — Próximamente`}>
            <Icon size={15} /><span className="sidebar-label">{label}</span><span className="soon">Pronto</span>
          </button>)}
      </div>)}
    </nav>
    <div className="sidebar-footer">
      <div className="evidence-note"><CircleHelp size={14} /><strong>Comprende antes de analizar</strong>
        <p>Revisa el esquema detectado y luego explora las asociaciones candidatas.</p>
      </div>
      <p>Ingesta de datos · v0.1<br /><span>Pronto = Próximamente</span></p>
    </div>
  </aside>;
}
