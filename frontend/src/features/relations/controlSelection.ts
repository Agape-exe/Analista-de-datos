
/**
 * AUD-038: Selección segura de variables de control.
 * Se permiten únicamente columnas numéricas distintas
 * de las dos variables analizadas.
 */

export function eligibleControls(
  numericColumns: string[],
  variables: string[],
): string[] {
  if (variables.length !== 2 || variables[0] === variables[1]) {
    return [];
  }

  return [...new Set(numericColumns)].filter(
    (column) =>
      column.trim().length > 0 &&
      !variables.includes(column),
  );
}

export function validateControlSelection(
  numericColumns: string[],
  variables: string[],
  control: string,
): string | null {
  if (
    variables.length !== 2 ||
    variables[0] === variables[1] ||
    !variables.every((variable) => numericColumns.includes(variable))
  ) {
    return "La correlación parcial requiere dos variables numéricas distintas.";
  }

  if (!control.trim()) {
    return "Debes seleccionar una variable de control.";
  }

  if (!eligibleControls(numericColumns, variables).includes(control)) {
    return "La variable de control no es válida para esta relación.";
  }

  return null;
}
