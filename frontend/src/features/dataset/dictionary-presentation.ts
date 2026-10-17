import type { DictionaryEntry } from "../../types/intake";

export const dictionaryFieldLabels = {
  description: "Descripción", data_type: "Tipo técnico", semantic_type: "Tipo semántico",
};
export const dictionarySourceLabels = { official: "Oficial", manual: "Manual", schema: "Esquema", inferred: "Inferida" };

export function isInferred(entry: DictionaryEntry, field: keyof typeof dictionaryFieldLabels) {
  return entry.source === "inferred" || (entry.inferred_fields ?? []).includes(field);
}

export function semanticLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    numeric: "Numérica", categorical: "Categórica", temporal: "Temporal",
    identifier: "Identificador", text: "Texto", unknown: "Desconocido",
  };
  return value ? (Object.hasOwn(labels, value) ? labels[value] : value) : "No disponible";
}

// Translate only known system messages. Supplied metadata and unknown messages stay intact.
export function dictionaryMessage(value: string | null | undefined): string {
  if (!value) return "No disponible";
  const messages: Record<string, string> = {
    "No non-null values available for inference.": "No hay valores no nulos disponibles para inferir.",
    "Explicit identifier label and discrete values.": "Nombre explícito de identificador y valores discretos.",
    "Values have UUID structure.": "Los valores tienen estructura UUID.",
    "Boolean values represent categories.": "Los valores booleanos representan categorías.",
    "Observed numeric values; uniqueness alone is not an ID.": "Valores numéricos observados; la unicidad por sí sola no indica un identificador.",
    "Near-unique digit codes with leading zeros.": "Códigos de dígitos casi únicos con ceros iniciales.",
    "Column name suggests free text; meaning is unverified.": "El nombre de la columna sugiere texto libre; el significado no está verificado.",
    "Short labels and configured cardinality policy.": "Etiquetas cortas y política de cardinalidad configurada.",
    "Text values outside the categorical policy.": "Valores de texto fuera de la política categórica.",
    "Mixed or unsupported local value types.": "Tipos de valores mezclados o no compatibles.",
    "Compatible semantic role supplied by the data dictionary.": "Rol semántico compatible proporcionado por el diccionario de datos.",
    "Identifier candidate is not unique; it may be a foreign key, not a primary key.": "El identificador candidato no es único; podría ser una clave foránea, no una clave primaria.",
    "Dictionary semantic role contradicts observed values.": "El rol semántico del diccionario contradice los valores observados.",
  };
  if (Object.hasOwn(messages, value)) return messages[value];
  for (const [message, translation] of Object.entries(messages)) {
    if (value.endsWith(`: ${message}`)) return value.slice(0, -message.length) + translation;
  }
  const date = /^Values match configured date format (.+)\.$/s.exec(value);
  if (date) return `Los valores coinciden con el formato de fecha configurado ${date[1] === "native datetime" ? "fecha nativa" : date[1]}.`;
  const unsupported = /^(.*)Unsupported dictionary semantic type: (.+)$/s.exec(value);
  if (unsupported) return `${unsupported[1]}Tipo semántico del diccionario no compatible: ${unsupported[2]}`;
  const excluded = /^Dictionary column '(.*)' is absent from the source and was excluded\.$/s.exec(value);
  if (excluded) return `La columna «${excluded[1]}» del diccionario no existe en el archivo y fue excluida.`;
  for (const [suffix, translation] of [
    [": supplied schema type differs from observed type.", ": el tipo del esquema proporcionado difiere del observado."],
    [": dictionary data type differs from observed type.", ": el tipo del diccionario difiere del observado."],
  ]) {
    if (value.endsWith(suffix)) return value.slice(0, -suffix.length) + translation;
  }
  return value;
}

export function dictionaryDescription(entry: DictionaryEntry): string {
  if (!entry.description) return "No disponible";
  if (!isInferred(entry, "description")) return entry.description;
  const generated = /^Column '(.*)' with observed type (.+) and proposed role (.+)\. Business meaning is unverified\.$/s.exec(entry.description);
  if (!generated) return entry.description;
  return `Columna «${generated[1]}» con tipo observado ${generated[2]} y rol propuesto ${semanticLabel(generated[3])}. El significado de negocio no está verificado.`;
}
