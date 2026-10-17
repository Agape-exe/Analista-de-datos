import { NavLink, useNavigate } from "react-router-dom";
import { Activity, BookOpen, ChartNoAxesCombined, CircleHelp, Database, GitBranch, Layers,
  LayoutDashboard, ListChecks, MessageSquare, Plus, ScanSearch, ShieldCheck, Sparkles, TriangleAlert,
  type LucideIcon } from "lucide-react";
import { useIntake } from "../../features/data-intake/IntakeProvider";
import { Button } from "../ui/button";

const groups: { label?: string; links: { label: string; icon: LucideIcon; to?: string }[] }[] = [
  { links: [{ label: "Overview", icon: LayoutDashboard }] },
  { label: "Data", links: [
    { label: "Dataset", icon: Database, to: "/dataset" },
    { label: "Data Quality", icon: ShieldCheck }, { label: "Data Dictionary", icon: BookOpen },
  ] },
  { label: "Exploration", links: [
    { label: "Associations", icon: ScanSearch }, { label: "Patterns", icon: Layers },
    { label: "Anomalies", icon: TriangleAlert },
  ] },
  { label: "Analysis", links: [
    { label: "Relationships", icon: GitBranch }, { label: "Insights", icon: Sparkles, to: "/report" },
  ] },
  { label: "Evaluation", links: [
    { label: "Trace", icon: ListChecks }, { label: "Metrics", icon: Activity },
  ] },
  { label: "Assistant", links: [{ label: "Chat", icon: MessageSquare }] },
];

export function Sidebar() {
  const { reset, loading } = useIntake();
  const navigate = useNavigate();
  return <aside className="sidebar">
    <a className="brand" href="/" aria-label="AI Data Analyst home">
      <span className="brand-icon"><ChartNoAxesCombined size={17} /></span>
      <span className="sidebar-label">AI Data Analyst</span>
    </a>
    <Button className="new-analysis" aria-label="New Analysis" disabled={loading} onClick={() => { reset(); navigate("/"); }}>
      <Plus size={15} /><span className="sidebar-label">New Analysis</span>
    </Button>
    <nav aria-label="Main navigation">
      {groups.map((group, index) => <div className="nav-group" key={group.label || index}>
        {group.label && <p className="nav-group-label">{group.label}</p>}
        {group.links.map(({ label, icon: Icon, to }) => to
          ? <NavLink key={label} to={to} title={label} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <Icon size={15} /><span className="sidebar-label">{label}</span>
          </NavLink>
          : <button key={label} className="nav-item unavailable" disabled title={`${label} — Coming Soon`}>
            <Icon size={15} /><span className="sidebar-label">{label}</span><span className="soon">Soon</span>
          </button>)}
      </div>)}
    </nav>
    <div className="sidebar-footer">
      <div className="evidence-note"><CircleHelp size={14} /><strong>Understand before analyzing</strong>
        <p>Review the detected schema and provenance. Statistical evidence comes next.</p>
      </div>
      <p>Data intake · v0.1<br /><span>Soon = Coming Soon</span></p>
    </div>
  </aside>;
}
