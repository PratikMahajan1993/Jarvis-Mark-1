import { mkdirSync, writeFileSync, existsSync } from "node:fs";
const name = process.argv[2];
if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
  console.error("usage: npm run new:feature <kebab-name>");
  process.exit(1);
}
const dir = `src/features/${name}`;
if (existsSync(dir)) {
  console.error(`${dir} exists`);
  process.exit(1);
}
mkdirSync(dir, { recursive: true });
const pascal = name.replace(/(^|-)(\w)/g, (_, __, c) => c.toUpperCase());
writeFileSync(
  `${dir}/${pascal}Card.tsx`,
  `export function ${pascal}Card() {\n  return <div className="rounded-lg border border-white/10 p-3">${pascal}</div>;\n}\n`,
);
writeFileSync(
  `../backend/app/features_${name.replace(/-/g, "_")}.py`,
  `from app.core.features import Feature, register_feature\n\nfeature = register_feature(Feature(id="${name}"))\n`,
);
console.log(`created ${dir} and backend feature module`);
