import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const repoRoot = join(frontendRoot, "..");

const name = process.argv[2];
if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
  console.error(
    "usage: npm run new:feature <kebab-name> [--section] [--card <slot>] [--approval <kind>] [--tool <name>] [--intent] [--job <name>]",
  );
  process.exit(1);
}

const args = process.argv.slice(3);
function flag(flagName) {
  return args.includes(flagName);
}
function opt(flagName) {
  const i = args.indexOf(flagName);
  return i >= 0 ? args[i + 1] : null;
}

const dir = join(frontendRoot, "src", "features", name);
const snake = name.replace(/-/g, "_");
const backendDir = join(repoRoot, "backend", "app", "features", snake);
const feIndex = join(frontendRoot, "src", "features", "index.ts");
const beInit = join(repoRoot, "backend", "app", "features", "__init__.py");
const pascal = name.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase());

function alreadyRegisteredFrontend() {
  if (!existsSync(feIndex)) return false;
  const text = readFileSync(feIndex, "utf8");
  return text.includes(`./${name}/feature`) || text.includes(`"${name}"`);
}

function alreadyRegisteredBackend() {
  if (!existsSync(beInit)) return false;
  const text = readFileSync(beInit, "utf8");
  return text.includes(`features.${snake}`) || text.includes(`as ${snake}`);
}

if (existsSync(dir) || existsSync(backendDir) || alreadyRegisteredFrontend() || alreadyRegisteredBackend()) {
  console.error(`feature id "${name}" already exists`);
  process.exit(1);
}

mkdirSync(dir, { recursive: true });
mkdirSync(backendDir, { recursive: true });
mkdirSync(join(repoRoot, "backend", "tests", "features"), { recursive: true });

const cardSlot = opt("--card");
const approvalKind = opt("--approval");
const toolName = opt("--tool");
const jobName = opt("--job");
const wantSection = flag("--section");
const wantIntent = flag("--intent");

if (cardSlot) {
  writeFileSync(
    join(dir, `${pascal}Card.tsx`),
    `"use client";\n\nexport function ${pascal}Card() {\n  return (\n    <div className="rounded-lg border border-white/10 p-3 text-sm">${pascal}</div>\n  );\n}\n`,
  );
}

writeFileSync(
  join(dir, "feature.ts"),
  cardSlot
    ? `import { defineFeature } from "@/sdk";
import { ${pascal}Card } from "./${pascal}Card";

defineFeature({
  id: "${name}",
  title: "${pascal}",
  cards: [
    { id: "${name}.main", slot: "${cardSlot}", order: 50, size: "md", component: ${pascal}Card },
  ],
});
`
    : `import { defineFeature } from "@/sdk";

defineFeature({
  id: "${name}",
  title: "${pascal}",
});
`,
);

writeFileSync(
  join(dir, "feature.test.ts"),
  `import { validateFeatureList } from "@/sdk";

describe("${name} feature id", () => {
  it("is a valid kebab id", () => {
    expect(validateFeatureList(["${name}"]).ok).toBe(true);
  });
});
`,
);

const beLines = [
  "from __future__ import annotations",
  "",
  "import asyncio",
  "",
  "from app.core.features import ApprovalKind, Feature, Intent, Job, ToolSpec, register_feature",
  "",
];
if (jobName) {
  beLines.push(`async def _job_${jobName}() -> None:`);
  beLines.push(`    await asyncio.sleep(0)`);
  beLines.push("");
}
beLines.push("FEATURE = register_feature(");
beLines.push("    Feature(");
beLines.push(`        id="${name}",`);
if (wantIntent) {
  beLines.push(
    `        intents=[Intent(name="${name}", examples=["${name} please"], section="monitor")],`,
  );
}
if (approvalKind) {
  beLines.push(`        approvals=[ApprovalKind(kind="${approvalKind}", title="${pascal}")],`);
}
if (toolName) {
  beLines.push(
    `        tools=[ToolSpec(name="${toolName}", description="${pascal} tool", handler=lambda **_: {"ok": True})],`,
  );
}
if (jobName) {
  beLines.push(`        jobs=[Job(name="${jobName}", every_s=3600, run=_job_${jobName})],`);
}
beLines.push(`        topics=["${name}.changed"],`);
beLines.push("    )");
beLines.push(")");
beLines.push("");

writeFileSync(join(backendDir, "feature.py"), beLines.join("\n"));
writeFileSync(join(backendDir, "__init__.py"), "from .feature import FEATURE\n");

writeFileSync(
  join(repoRoot, "backend", "tests", "features", `test_${snake}.py`),
  `from app.features.${snake} import FEATURE\n\n\ndef test_${snake}_registered():\n    assert FEATURE.id == "${name}"\n`,
);

{
  let text = readFileSync(feIndex, "utf8");
  if (!text.includes(`./${name}/feature`)) {
    text = `import "./${name}/feature";\n` + text;
  }
  text = text.replace(/export const FEATURES = \[([^\]]*)\] as const/, (_m, inner) => {
    const parts = inner
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.includes(`"${name}"`)) parts.push(`"${name}"`);
    return `export const FEATURES = [${parts.join(", ")}] as const`;
  });
  writeFileSync(feIndex, text);
}

{
  let text = readFileSync(beInit, "utf8");
  if (!text.includes(`from app.features.${snake} import FEATURE as ${snake}`)) {
    text = text.replace(
      /(from app\.core\.features import Feature\n)/,
      `$1from app.features.${snake} import FEATURE as ${snake}\n`,
    );
    if (!text.includes(`as ${snake}`)) {
      text = `from app.features.${snake} import FEATURE as ${snake}\n` + text;
    }
  }
  text = text.replace(/FEATURES: list\[Feature\] = \[([^\]]*)\]/, (_m, inner) => {
    const parts = inner
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.includes(snake)) parts.push(snake);
    return `FEATURES: list[Feature] = [${parts.join(", ")}]`;
  });
  writeFileSync(beInit, text);
}

if (wantSection) {
  console.log("note: --section stub only; wire a SectionDef when ready");
}

console.log(`created feature "${name}" and registered in frontend + backend indexes`);
