#!/usr/bin/env node
/**
 * content/*.md -> src/data/content.generated.json
 *
 * The portfolio page's copy lives in ../content (the same source of truth
 * scripts/build_corpus.py and backend/ingest.py read) so a resume edit is
 * one Markdown change, not three. This script only needs structure
 * (front-matter + "## heading" sections), not the BM25 statistics the
 * other two build steps compute — so it's a much smaller parser, not a
 * fourth mirror of the tokeniser/stemmer.
 *
 * Run automatically before `npm run build` (see package.json's
 * prebuild:content) and on demand with `node scripts/build-content.mjs`.
 */

import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CONTENT_DIR = path.join(REPO_ROOT, "content");
const OUT_PATH = path.join(__dirname, "..", "src", "data", "content.generated.json");

function parseFrontMatter(raw) {
  if (!raw.startsWith("---")) return [{}, raw];
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return [{}, raw];
  const meta = {};
  for (const line of raw.slice(3, end).trim().split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return [meta, raw.slice(end + 4)];
}

function chunkSections(body) {
  const blocks = body.split(/^## /m).slice(1);
  return blocks.map((block) => {
    const nl = block.indexOf("\n");
    const heading = (nl === -1 ? block : block.slice(0, nl)).trim();
    const text = nl === -1 ? "" : block.slice(nl + 1).split(/\s+/).join(" ").trim();
    return { heading, text };
  }).filter((s) => s.text);
}

function main() {
  const files = readdirSync(CONTENT_DIR).filter((f) => f.endsWith(".md")).sort();
  if (!files.length) {
    console.error(`No markdown found in ${CONTENT_DIR}`);
    process.exit(1);
  }

  const documents = files.map((file) => {
    const raw = readFileSync(path.join(CONTENT_DIR, file), "utf8");
    const [meta, body] = parseFrontMatter(raw);
    return {
      id: meta.id || path.basename(file, ".md"),
      section: meta.section || "misc",
      title: meta.title || "",
      type: meta.type || "",
      domain: meta.domain || "",
      date: meta.date || "",
      repo: meta.repo || "",
      status: meta.status || "",
      images: (meta.images || "").split(",").map((s) => s.trim()).filter(Boolean),
      volunteer: (meta.volunteer || "true").toLowerCase() !== "false",
      sections: chunkSections(body),
    };
  }).filter((d) => d.volunteer && d.sections.length); // gated docs (e.g. "posture") stay chat-only, not on the page

  writeFileSync(OUT_PATH, JSON.stringify({ generatedAt: new Date().toISOString(), documents }, null, 2));
  console.log(`  wrote ${path.relative(REPO_ROOT, OUT_PATH)} (${documents.length} documents)`);
}

main();
