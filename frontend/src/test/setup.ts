import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { requestGate } from "../lib/api-client";

afterEach(() => {
  cleanup();
  requestGate.reset();
});
