
import { expect, test } from "vitest";
import {
  eligibleControls,
  validateControlSelection,
} from "./controlSelection";

const numeric = ["ventas", "publicidad", "campaña", "precio"];

test("AUD-038: excluye las variables analizadas", () => {
  expect(
    eligibleControls(numeric, ["ventas", "publicidad"]),
  ).toEqual(["campaña", "precio"]);
});

test("AUD-038: acepta una variable de control válida", () => {
  expect(
    validateControlSelection(
      numeric,
      ["ventas", "publicidad"],
      "campaña",
    ),
  ).toBeNull();
});

test("AUD-038: rechaza un control igual a una variable analizada", () => {
  expect(
    validateControlSelection(
      numeric,
      ["ventas", "publicidad"],
      "ventas",
    ),
  ).not.toBeNull();
});

test("AUD-038: rechaza controles inexistentes", () => {
  expect(
    validateControlSelection(
      numeric,
      ["ventas", "publicidad"],
      "desconocida",
    ),
  ).not.toBeNull();
});

test("AUD-038: exige dos variables numéricas distintas", () => {
  expect(
    validateControlSelection(
      numeric,
      ["ventas", "ventas"],
      "campaña",
    ),
  ).not.toBeNull();
});
