import { BookOpen, X } from "lucide-react";
import { useRef } from "react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

export function DataDictionaryUpload({ file, disabled, onChange }: {
  file: File | null; disabled: boolean; onChange: (file: File | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return <div className="dictionary-upload">
    <BookOpen size={20} className="muted" />
    <div><label htmlFor="dictionary-upload">Upload Data Dictionary <Badge>Optional</Badge></label>
      <p>{file ? file.name : "JSON descriptions, units and business meaning to guide interpretation."}</p>
    </div>
    <input ref={input} id="dictionary-upload" type="file" accept=".json" className="sr-only"
      aria-label="Data dictionary file" disabled={disabled}
      onChange={(event) => onChange(event.target.files?.[0] || null)} />
    <Button variant="outline" size="small" disabled={disabled} onClick={() => input.current?.click()}>
      {file ? "Change file" : "Choose file"}
    </Button>
    {file && <Button variant="ghost" size="small" aria-label="Remove dictionary" disabled={disabled}
      onClick={() => { onChange(null); if (input.current) input.current.value = ""; }}><X size={14} /></Button>}
  </div>;
}
