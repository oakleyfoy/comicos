/**
 * One-off codemod: align AppShell pages with the light canvas (patriot-sky).
 * Skips ops-heavy pages and intentional navy executive panels.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pagesDir = path.join(__dirname, "..", "src", "pages");

const SKIP = new Set([
  "OperationsPage.tsx",
  "InventoryDetailPage.tsx",
  "OrderImportPage.tsx",
  "OrderNewPage.tsx",
]);

const REPLACEMENTS = [
  [
    /rounded-2xl border border-white\/10 bg-slate-900\/60 px-3 py-2 text-sm/g,
    "rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm",
  ],
  [
    /rounded-xl border border-white\/10 bg-slate-900\/60 p-4/g,
    "rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
  ],
  [
    /rounded-2xl border border-white\/10 bg-slate-950\/45 p-4/g,
    "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm",
  ],
  [
    /rounded-3xl border border-white\/10 bg-slate-900\/65 p-5/g,
    "rounded-3xl border border-slate-200 bg-white p-5 shadow-sm",
  ],
  [
    /rounded-3xl border border-white\/10 bg-slate-900\/65 p-4/g,
    "rounded-3xl border border-slate-200 bg-white p-4 shadow-sm",
  ],
  [
    /rounded-xl border border-white\/5 bg-slate-950\/50 px-3 py-2 text-sm/g,
    "rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800",
  ],
  [
    /overflow-x-auto rounded-xl border border-white\/10"/g,
    'overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm"',
  ],
  [
    /overflow-x-auto rounded-2xl border border-white\/10"/g,
    'overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"',
  ],
  [
    /mt-3 overflow-x-auto rounded-xl border border-white\/10"/g,
    'mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm"',
  ],
  [
    /border-b border-white\/10 bg-slate-900\/80 text-xs uppercase text-slate-500/g,
    "border-b border-slate-200 bg-slate-800 text-xs uppercase text-slate-200",
  ],
  [
    /border-b border-white\/10 bg-slate-900\/80 text-xs uppercase tracking-wide text-slate-500/g,
    "border-b border-slate-200 bg-slate-800 text-xs uppercase tracking-wide text-slate-200",
  ],
  [
    /border-b border-white\/10 bg-slate-900\/80 text-xs uppercase tracking-\[0\.12em\] text-slate-500/g,
    "border-b border-slate-200 bg-slate-800 text-xs uppercase tracking-[0.12em] text-slate-200",
  ],
  [
    /className="px-4 py-2 text-white"/g,
    'className="px-4 py-2 font-medium text-slate-900"',
  ],
  [
    /className="px-4 py-3 font-medium text-white"/g,
    'className="px-4 py-3 font-medium text-slate-900"',
  ],
  [
    /className="px-4 py-2 font-medium text-white"/g,
    'className="px-4 py-2 font-medium text-slate-900"',
  ],
  [
    /className="px-4 py-3 text-slate-200"/g,
    'className="px-4 py-3 text-slate-800"',
  ],
  [
    /className="px-4 py-2 text-slate-200"/g,
    'className="px-4 py-2 text-slate-800"',
  ],
  [
    /className="px-4 py-3 text-slate-300"/g,
    'className="px-4 py-3 text-slate-600"',
  ],
  [
    /className="px-4 py-2 text-slate-300"/g,
    'className="px-4 py-2 text-slate-600"',
  ],
  [
    /className="border-b border-white\/5"/g,
    'className="border-b border-slate-100"',
  ],
  [
    /className="border-b border-white\/5 hover:bg-white\/\[0\.02\]"/g,
    'className="border-b border-slate-100 hover:bg-slate-50"',
  ],
  [
    /className="text-lg font-semibold text-white"/g,
    'className="text-lg font-semibold text-slate-900"',
  ],
  [
    /className="mt-1 text-2xl font-semibold text-white"/g,
    'className="mt-1 text-2xl font-semibold text-slate-900"',
  ],
  [
    /className="mt-2 text-2xl font-semibold text-white"/g,
    'className="mt-2 text-2xl font-semibold text-slate-900"',
  ],
  [
    /className="rounded-xl border border-white\/10 bg-slate-950 px-3 py-2 text-sm text-white"/g,
    "className=\"rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900\"",
  ],
  [
    /className="w-28 rounded-xl border border-white\/10 bg-slate-950 px-3 py-2 text-sm text-white"/g,
    "className=\"w-28 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900\"",
  ],
  [
    /className="w-36 rounded-xl border border-white\/10 bg-slate-950 px-3 py-2 text-sm text-white"/g,
    "className=\"w-36 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900\"",
  ],
  [
    /className="ml-1 rounded-lg border border-white\/10 bg-slate-950 px-2 py-1 text-white"/g,
    "className=\"ml-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900\"",
  ],
  [
    /className="text-sm text-slate-400"/g,
    'className="text-sm text-slate-600"',
  ],
  [
    /className="text-sm font-semibold uppercase tracking-wide text-slate-400"/g,
    'className="text-sm font-semibold uppercase tracking-wide text-slate-600"',
  ],
  [
    /className="text-sm font-semibold text-white"/g,
    'className="text-sm font-semibold text-slate-900"',
  ],
  [
    /<span className="font-medium text-white">/g,
    '<span className="font-medium text-slate-900">',
  ],
  [
    /<span className="text-cyan-200">/g,
    '<span className="font-medium text-teal-800">',
  ],
  [
    /<span className="text-amber-200">/g,
    '<span className="font-medium text-amber-800">',
  ],
  [
    /min-w-full text-left text-sm text-slate-200/g,
    "min-w-full text-left text-sm text-slate-800",
  ],
  [
    /text-rose-300/g,
    "text-rose-800",
  ],
  [
    /text-amber-200/g,
    "text-amber-800",
  ],
  [
    /text-orange-300/g,
    "text-orange-800",
  ],
];

function shouldProcess(content) {
  if (!content.includes('from "../components/AppShell"') && !content.includes("from '../components/AppShell'")) {
    return false;
  }
  return true;
}

function processFile(filePath) {
  const base = path.basename(filePath);
  if (SKIP.has(base)) {
    return false;
  }
  let content = fs.readFileSync(filePath, "utf8");
  if (!shouldProcess(content)) {
    return false;
  }
  const original = content;
  for (const [pattern, replacement] of REPLACEMENTS) {
    content = content.replace(pattern, replacement);
  }
  if (content !== original) {
    fs.writeFileSync(filePath, content, "utf8");
    return true;
  }
  return false;
}

const changed = [];
for (const name of fs.readdirSync(pagesDir)) {
  if (!name.endsWith(".tsx")) continue;
  const full = path.join(pagesDir, name);
  if (processFile(full)) changed.push(name);
}

console.log(`Updated ${changed.length} page(s):`);
for (const n of changed.sort()) console.log(`  - ${n}`);
