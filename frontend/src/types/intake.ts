import type { components } from "./api";

export type IntakeResponse = components["schemas"]["IntakeResponse"];
export type ColumnProfile = components["schemas"]["ColumnProfile"];
export type DictionaryEntry = components["schemas"]["DataDictionaryEntry"];

export interface IntakeDraft {
  file: File | null;
  dictionary: File | null;
  delimiter: string;
  encoding: string;
}

export interface IntakeError {
  message: string;
  requestId?: string;
}
