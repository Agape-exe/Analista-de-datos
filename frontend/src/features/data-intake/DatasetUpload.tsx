import { FileSpreadsheet, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

interface Props {
  file: File | null;
  disabled: boolean;
  onChange: (file: File | null) => void;
}

export function DatasetUpload({ file, disabled, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  return <div className={`upload-zone ${dragging ? "dragging" : ""} ${disabled ? "busy" : ""}`}
    onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
    onDragLeave={() => setDragging(false)}
    onDrop={(event) => {
      event.preventDefault(); setDragging(false);
      if (!disabled && event.dataTransfer.files[0]) onChange(event.dataTransfer.files[0]);
    }}>
    <input ref={input} id="dataset-upload" type="file" className="sr-only" aria-label="Archivo del dataset"
      accept=".csv,.tsv" disabled={disabled}
      onChange={(event) => onChange(event.target.files?.[0] || null)} />
    <span className="upload-icon">{file ? <FileSpreadsheet size={26} /> : <Upload size={26} />}</span>
    <h2>{file ? file.name : "Arrastra tu dataset aquí"}</h2>
    <p>{file ? `${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 1 }).format(file.size / 1024)} KB · listo para validar`
      : "o busca el archivo en tu computadora"}</p>
    <div className="upload-formats"><Badge>CSV</Badge><Badge>TSV</Badge><Badge>TXT · Pronto</Badge></div>
    <div className="inline-actions"><Button variant="outline" size="small" disabled={disabled} onClick={() => input.current?.click()}>
      {file ? "Cambiar archivo" : "Elegir archivo"}
    </Button>{file && <Button variant="ghost" size="small" disabled={disabled} aria-label="Quitar dataset"
      onClick={() => { onChange(null); if (input.current) input.current.value = ""; }}><X size={14} /></Button>}</div>
  </div>;
}
