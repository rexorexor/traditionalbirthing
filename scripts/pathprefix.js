#!/usr/bin/env node
/**
 * Post-build path-prefix rewrite for GitHub Pages project sites.
 *
 * The built pages use root-absolute local URLs (/content/..., /universal/...,
 * /static/..., /website-component-definition/..., /@sqs/..., /platform.js)
 * plus site-root links ("/") and internal page links (/ibclc/ ...). On a
 * project site these must become /<prefix>/... to resolve under a subfolder.
 *
 * External URLs (http/https/protocol-relative), data: URIs, mailto:, tel:,
 * and #fragment refs are left untouched, as are CSS url(#...) fragments.
 * Idempotent: already-prefixed paths are skipped.
 *
 * Default prefix: /traditionalbirthing (override with PATH_PREFIX env).
 */
const fs = require("fs");
const path = require("path");

const SITE = path.join(__dirname, "..", "site");
const PREFIX = (process.env.PATH_PREFIX || "/traditionalbirthing").replace(/\/+$/, "");
const ASSET_SEGMENTS = ["content", "static", "universal", "website-component-definition", "@sqs"];
const LOCAL_PREFIX_RE = new RegExp("^/(" + ASSET_SEGMENTS.map(escapeRe).join("|") + ")(/|$)");
// Local pages that must resolve under the subfolder (nav links etc.).
// Keep in sync with src/_data/nav.json + src/pages/ (added faq|classes 2026-10-20).
const INTERNAL_PAGE_RE = /^\/(home|contact|ibclc|birth|postpartum|about|faq|classes)\/?$/;
// Top-level local files referenced from pages.
const LOCAL_FILE_RE = /^\/(platform\.js)$/;

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

function p(v) {
  if (typeof v !== "string" || !v.startsWith("/") || v.startsWith("//")) return v;
  if (v === PREFIX || v.startsWith(PREFIX + "/")) return v;
  if (LOCAL_PREFIX_RE.test(v)) return PREFIX + v;
  return v;
}

function prefixHref(v) {
  if (v === "/") return PREFIX + "/";
  if (INTERNAL_PAGE_RE.test(v) || LOCAL_FILE_RE.test(v)) return PREFIX + v;
  return p(v);
}

function rewriteSrcset(v) {
  return v.split(",").map((part) => {
    const trimmed = part.trim();
    if (!trimmed) return part;
    const sp = trimmed.indexOf(" ");
    const url = sp === -1 ? trimmed : trimmed.slice(0, sp);
    const rest = sp === -1 ? "" : trimmed.slice(sp);
    return prefixHref(url) + rest;
  }).join(", ");
}

function rewriteAttrs(html) {
  // double-quoted URL attrs (site-root "/" included)
  html = html.replace(/(\s(?:href|src|data-src|data-image|poster|data-background-image))="([^"]*)"/g,
    (m, name, val) => `${name}="${prefixHref(val)}"`);
  // srcset needs per-URL treatment
  html = html.replace(/(\ssrcset)="([^"]*)"/g, (m, name, val) => `${name}="${rewriteSrcset(val)}"`);
  // url(...) inside style attributes and <style> blocks in HTML
  html = html.replace(/url\(\s*(['"]?)(\/[^)'"]+)\1\s*\)/g, (m, q, val) => `url(${q}${p(val)}${q})`);
  // JSON-context asset paths (Squarespace component data blobs)
  html = html.replace(/(?<=[{"\s:,])\/(?:content|static|universal|website-component-definition|@sqs)\/[\w@.\/-]*/g,
    (m) => p(m));
  return html;
}

function rewriteCss(css) {
  return css.replace(/url\(\s*(['"]?)(\/[^)'"]+)\1\s*\)/g, (m, q, val) => `url(${q}${p(val)}${q})`);
}

let files = 0, links = 0;
const REF_RE = new RegExp(PREFIX + "/(content|static|universal|website-component-definition|@sqs|platform\\.js)", "g");
const PAGE_REF_RE = new RegExp(PREFIX + "\/(home|contact|ibclc|birth|postpartum|about|faq|classes)(\/|\"|$)", "g");
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) { walk(full); continue; }
    const ext = path.extname(entry.name).toLowerCase();
    if (ext !== ".html" && ext !== ".css") continue;
    const before = fs.readFileSync(full, "utf8");
    const after = ext === ".css" ? rewriteCss(before) : rewriteAttrs(before);
    if (after !== before) {
      fs.writeFileSync(full, after);
      files++;
      links += (after.match(REF_RE) || []).length + (after.match(PAGE_REF_RE) || []).length;
    }
  }
}
walk(SITE);

// Keep the sitemap self-consistent with the preview location.
const sitemap = path.join(SITE, "sitemap.xml");
if (fs.existsSync(sitemap)) {
  const before = fs.readFileSync(sitemap, "utf8");
  const after = before.replace(/https:\/\/www\.traditionalbirthing\.com(?=\/)/g,
    "https://rexorexor.github.io" + PREFIX);
  if (after !== before) { fs.writeFileSync(sitemap, after); files++; }
}

console.log(`pathprefix: rewrote ${files} file(s), ~${links} local refs now under ${PREFIX}/`);
