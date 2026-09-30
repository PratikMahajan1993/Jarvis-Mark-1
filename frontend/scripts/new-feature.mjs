import {
  existsSync,
  mkdirSync,
  readdirSync,
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
    "usage: npm run new:feature <kebab-name> [--section] [--card <slot>] [--approval <kind>] [--tool <name>] [--intent] [--job <name>] [--migration <slug>]",
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
const migrationSlug = opt("--migration");
const wantSection = flag("--section");
const wantIntent = flag("--intent");

if (args.includes("--migration") && (typeof migrationSlug !== "string" || !/^[a-z][a-z0-9_]*$/.test(migrationSlug))) {
  console.error("--migration needs a slug like init or quote_fields");
  process.exit(1);
}

function collectOrders(dir, into) {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) collectOrders(path, into);
    else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      const text = readFileSync(path, "utf8");
      for (const match of text.matchAll(/\border:\s*(\d+)/g)) {
        const value = Number(match[1]);
        if (value >= 100) into.add(value);
      }
    }
  }
}

function nextSectionOrder() {
  const taken = new Set([100, 200, 300]);
  collectOrders(join(frontendRoot, "src", "features"), taken);
  const registry = join(frontendRoot, "src", "core", "sections", "registry.ts");
  if (existsSync(registry)) {
    const text = readFileSync(registry, "utf8");
    for (const match of text.matchAll(/\border:\s*(\d+)/g)) {
      const value = Number(match[1]);
      if (value >= 100) taken.add(value);
    }
  }
  let max = 300;
  for (const value of taken) if (value >= 100 && value > max) max = value;
  return max + 100;
}

function nextMigrationNumber() {
  const dir = join(repoRoot, "backend", "migrations");
  let max = 0;
  for (const entry of readdirSync(dir)) {
    const match = /^(\d+)_/.exec(entry);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return { number: max + 1, padded: String(max + 1).padStart(4, "0"), previous: String(max).padStart(4, "0") };
}

if (cardSlot) {
  writeFileSync(
    join(dir, `${pascal}Card.tsx`),
    `"use client";\n\nexport function ${pascal}Card() {\n  return (\n    <div className="rounded-lg border border-white/10 p-3 text-sm">${pascal}</div>\n  );\n}\n`,
  );
}

const sectionOrder = wantSection ? nextSectionOrder() : null;
const sectionSlot = `${name}.main`;

if (wantSection) {
  writeFileSync(
    join(dir, `${pascal}Section.tsx`),
    `"use client";\n\nimport { Slot, type SectionProps } from "@/sdk";\n\nexport function ${pascal}Section(_props: SectionProps) {\n  return (\n    <div className="flex h-full min-h-0 flex-col gap-3">\n      <Slot id="${sectionSlot}" />\n    </div>\n  );\n}\n`,
  );
}

const featureImports = [`import { defineFeature } from "@/sdk";`];
if (wantSection) {
  featureImports[0] = `import { defineFeature, defineSection, FEATURE_SECTION_THEME, featureSectionOrb } from "@/sdk";`;
  featureImports.push(`import { ${pascal}Section } from "./${pascal}Section";`);
}
if (cardSlot) featureImports.push(`import { ${pascal}Card } from "./${pascal}Card";`);

const featureBody = [`defineFeature({`, `  id: "${name}",`, `  title: "${pascal}",`];
if (wantSection) {
  featureBody.push(`  sections: [`);
  featureBody.push(`    defineSection({`);
  featureBody.push(`      id: "${name}",`);
  featureBody.push(`      order: ${sectionOrder},`);
  featureBody.push(`      label: "${pascal}",`);
  featureBody.push(`      orb: featureSectionOrb(),`);
  featureBody.push(`      theme: FEATURE_SECTION_THEME,`);
  featureBody.push(`      lazy: { mountWithin: 1, unmountBeyond: 2 },`);
  featureBody.push(`      slots: ["${sectionSlot}"],`);
  featureBody.push(`      component: ${pascal}Section,`);
  featureBody.push(`    }),`);
  featureBody.push(`  ],`);
}
if (cardSlot) {
  featureBody.push(`  cards: [`);
  featureBody.push(
    `    { id: "${name}.main", slot: "${cardSlot}", order: 50, size: "md", component: ${pascal}Card },`,
  );
  featureBody.push(`  ],`);
}
featureBody.push(`});`, ``);

writeFileSync(join(dir, "feature.ts"), `${featureImports.join("\n")}\n\n${featureBody.join("\n")}\n`);

writeFileSync(
  join(dir, "feature.test.ts"),
  `import { describe, expect, it } from "vitest";
import { validateFeatureList } from "@/sdk";

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

if (migrationSlug) {
  const next = nextMigrationNumber();
  const migrationPath = join(
    repoRoot,
    "backend",
    "migrations",
    `${next.padded}_${snake}_${migrationSlug}.sql`,
  );
  writeFileSync(
    migrationPath,
    `-- Description: ${name} ${migrationSlug}\n-- Dependencies: ${next.previous}\n--\n-- The migration runner splits on ';' and executes each statement. Do not wrap\n-- the file in BEGIN/COMMIT — a connection may already be inside a transaction,\n-- and SQLite commits DDL implicitly. Keep the script forward-only and idempotent\n-- (INSERT OR IGNORE, or ALTER that tolerates a duplicate column).\n\n-- idempotent inserts/updates go here\n`,
  );
  console.log(`migration ${next.padded}_${snake}_${migrationSlug}.sql`);
}

console.log(`created feature "${name}" and registered in frontend + backend indexes`);
