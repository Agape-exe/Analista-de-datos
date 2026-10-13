import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = "import json; from app.api.main import app; print(json.dumps(app.openapi()))";
const schema = JSON.parse(execFileSync("uv", ["run", "python", "-c", python], {
  cwd: root, encoding: "utf8", maxBuffer: 10 * 1024 * 1024,
}));
const output = astToString(await openapiTS(schema));
writeFileSync(new URL("../src/types/api.ts", import.meta.url),
  "// Generated from FastAPI OpenAPI. Run npm run generate:api; do not edit.\n" + output);
console.log("Generated src/types/api.ts from backend contracts.");
