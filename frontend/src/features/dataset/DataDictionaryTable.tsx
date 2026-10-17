import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { formatPercentage } from "../../lib/utils";
import type { DictionaryEntry, IntakeResponse } from "../../types/intake";
import { dictionaryDescription, dictionaryFieldLabels, dictionaryMessage, dictionarySourceLabels, isInferred, semanticLabel } from "./dictionary-presentation";

function FieldOrigin({ entry, field }: { entry: DictionaryEntry; field: keyof typeof dictionaryFieldLabels }) {
  return isInferred(entry, field) ? <Badge tone="info">Inferido</Badge> : <Badge>Proporcionado</Badge>;
}

export function DataDictionaryTable({ result }: { result: IntakeResponse }) {
  const entries = result.summary.data_dictionary.entries ?? [];
  const dictionary = new Map(entries.map((entry) => [entry.column_name, entry]));
  const profiles = new Map((result.profile.columns ?? []).map((column) => [column.column_name, column]));
  // Include every observed column, even when its dictionary entry is unavailable.
  const names = [...new Set([...profiles.keys(), ...dictionary.keys()])];
  return <Card className="column-card dictionary-card">
    <div className="card-heading"><div><h2>Metadatos por columna</h2>
      <p>{names.length} columnas · desplázate horizontalmente para consultar todos los campos.</p></div><Badge>Solo lectura</Badge></div>
    {entries.length === 0 && <p className="dictionary-empty" role="status">No existen metadatos disponibles en el diccionario de este dataset.{profiles.size > 0 && " Se muestran los tipos observados del perfil."}</p>}
    {names.length > 0 && <div className="table-scroll" role="region" aria-label="Diccionario de datos por columna" tabIndex={0}>
      <table className="dictionary-table"><caption className="sr-only">Diccionario del dataset {result.filename}</caption>
        <thead><tr>{["Columna", "Tipo técnico observado", "Tipo declarado", "Tipo semántico", "Descripción", "Unidad", "Procedencia y confianza", "Inferencias", "Advertencias"].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{names.map((name) => {
          const entry = dictionary.get(name);
          const column = profiles.get(name);
          const inferredFields = entry ? (Object.keys(dictionaryFieldLabels) as (keyof typeof dictionaryFieldLabels)[])
            .filter((field) => entry[field] != null && entry[field] !== "" && isInferred(entry, field)) : [];
          const declaredType = entry?.data_type && !isInferred(entry, "data_type") ? entry.data_type : null;
          return <tr key={name}>
            <th scope="row" className="variable-name">{name}</th>
            <td><code>{column?.data_type || "No disponible"}</code>{column?.data_type && <small>Observado en el archivo</small>}</td>
            <td><code>{declaredType || "No disponible"}</code>{declaredType && <Badge>Proporcionado</Badge>}</td>
            <td>{semanticLabel(entry?.semantic_type)}{entry?.semantic_type && <FieldOrigin entry={entry} field="semantic_type" />}
              <small>Rol del perfil: {semanticLabel(column?.semantic_type)}</small>
              <small>Fuente del rol: {column?.classification_source ? dictionarySourceLabels[column.classification_source] : "No disponible"}</small>
              {column?.classification_reason && <small>{dictionaryMessage(column.classification_reason)}</small>}</td>
            <td>{entry ? dictionaryDescription(entry) : "No disponible"}
              {entry?.description && <FieldOrigin entry={entry} field="description" />}
              {entry?.description && isInferred(entry, "description") && <small>Significado de negocio sin verificar</small>}</td>
            <td>{entry?.unit || "No disponible"}</td>
            <td><span>Fuente: {entry ? dictionarySourceLabels[entry.source] : "No disponible"}</span>
              <small>Confianza: {entry?.confidence == null ? "No evaluada" : formatPercentage(entry.confidence * 100)}</small>
              {entry?.confidence != null && <small>Valor recibido en el diccionario</small>}</td>
            <td>{inferredFields.length > 0 ? <><Badge tone="info">Campos inferidos</Badge><ul>{inferredFields.map((field) => <li key={field}>
              {dictionaryFieldLabels[field]}{field === "data_type" ? `: ${entry?.data_type || "No disponible"}` : ""}</li>)}</ul></> : "No disponible"}
              <small>Justificación: {dictionaryMessage(entry?.inference_reason)}</small></td>
            <td>{column?.warnings?.length ? <ul>{column.warnings.map((warning, index) => <li key={index}>{dictionaryMessage(warning)}</li>)}</ul> : "No disponible"}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>}
    <p className="table-footnote">El tipo declarado solo aparece si fue proporcionado. Las inferencias describen la estructura y no confirman significados de negocio. Una fuente oficial o manual puede contener campos completados por inferencia.</p>
  </Card>;
}
