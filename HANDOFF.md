# HANDOFF — traditionalbirthing project (written 2026-10-16)

## What we built

1. **Audit (Oct 15):** Static mirror of www.traditionalbirthing.com verified page-by-page
   against the live sitemap (4 live pages: /, /home, /contact, /ibclc; /birth, /postpartum,
   /about locked at HTTP 401; /cart live but unmirrored). 0 broken refs in the mirror.
2. **Eleventy rebuild:** clean, editable source project. 8 output pages — 4 content
   (/, /home, /contact, /ibclc; Squarespace fluid-engine sections preserved as HTML
   includes), 3 styled "Coming soon" pages (/birth, /postpartum, /about), 404.
   Contact form replaced with email link + Book online button. Elfsight reviews embed
   kept live. SEO: per-page title/description, local favicon, sitemap.xml.
3. **Rendering fix:** cssSet wiring bug (pages built with 0 stylesheets) fixed per page;
   loud build guards added; per-page @font-face blocks restored with local font files;
   data-collection-id restored.
4. **Publish:** public repo `rexorexor/traditionalbirthing`, main branch, GitHub Actions
   workflow deploys `site/` to Pages on every push. Path-prefix rewrite makes all local
   refs work under the /traditionalbirthing/ subfolder. First deploy succeeded;
   live verification: 0 broken local refs on / and /contact/.

**Preview:** https://rexorexor.github.io/traditionalbirthing/
**Live site:** untouched (Squarespace still authoritative; DNS/domains never touched).

## Where everything lives (/projects/traditionalbirthing/)

- `mirror/` — immutable source-of-truth scrape (gitignored; never leaves this server).
  `raw/`, `raw2/` — older scrape attempts (gitignored).
- `src/` — Eleventy source:
  - `src/pages/*.md` — one file per page; front matter: title, description, navOrder,
    permalink, cssSet, sectionsDir/navActive (content pages) or comingSoonBase (placeholders).
  - `src/_includes/sections/<page>/section-*.njk` — the actual page bodies (mirror HTML).
    Edit page TEXT here (look for `sqs-html-content` blocks).
  - `src/_includes/partials/` — head.njk (guarded), header.njk (nav from _data), footer, post-footer.
  - `src/_includes/body-open/*.njk` — per-page <body> tags + siteWrapper.
  - `src/_data/` — nav.json, pages.json, csssets.json (per-page stylesheet lists),
    fontblocks.json (per-page @font-face), site.json.
  - `src/assets/` — all mirrored CSS/fonts/images/component files (copied from mirror).
- `site/` — build output (gitignored; GitHub rebuilds it).
- `scripts/pathprefix.js` — post-build rewrite to /traditionalbirthing/ for Pages preview.
- `.github/workflows/deploy.yml` — Actions build+deploy (npm install --include=dev →
  npm run build:pages → deploy-pages).
- `FIDELITY-NOTES.md` — every fidelity decision & deviation.
- `PUNCH-LIST.md` — known gaps from owner review.
- `gen.py` — the generator that produced templates/includes from the mirror (rerunnable;
  template edits must be made in gen.py or they'll be overwritten by a rerun).
- `scrape*.py`, `pass35.py`, `htmlfix.py` — original scrape tooling.
- `.pages.yml` — Pages CMS config (pages + images only).

## Commands

```
npm install --include=dev   # first install (global npm omits dev deps)
npm run dev                 # local preview at http://localhost:8080 (root-relative)
npm run build               # plain build → site/
npm run build:pages         # build + /traditionalbirthing/ prefix (what CI runs)
```

## Punch list (see PUNCH-LIST.md for detail)

- Missing images top of /contact (flowers) and /ibclc — markup + files exist; suspect
  the intentionally-dropped imageFluid/image-effect JS.
- "IN-PERSON AND VIRTUAL VISITS AVAILABLE" (/ibclc) and "SERVING SPRINGFIELD…"
  (/) present in HTML but not rendering — Squarespace scaled-text needs runtime JS.
- Tan where white should be on / and /ibclc — per-section theme vars to inspect.
- Hover-enlarge on the 3 home images not working (image-effect JS dropped).
- Nav reappear-on-scroll-up never fires (site-bundle Header controller; flaky on live too).
- Contact form: intentionally replaced (dead in static copy); a real form needs a
  static-friendly backend decision.

## Constraints to remember

- **Secrets:** GitHub token lives in the secret store as `GH_PAT` (env kind), account
  `rexorexor`, scopes `repo, workflow`. Use by reference only — never print/echo/log.
  The `GITHUB_TOKEN` entry is stale/dead and is also blocked from exec injection by the
  gateway (managed-GitHub-identity guard) — don't rely on it.
- **Secret snapshots:** each exec turn snapshots the store at turn start; a store save
  made mid-turn isn't visible until the next turn. If an env-kind value comes in at 41
  chars, it has a trailing newline — trim before use (current GH_PAT is clean 40).
- **npm quirks:** global config omits devDependencies (`--include=dev` required);
  bare `npx eleventy` installs the WRONG package — use `npx @11ty/eleventy` or npm scripts.
- **Nunjucks:** includes need the explicit `.njk` extension; an undefined variable in a
  loop silently iterates zero times (that was the stylesheet bug) — guards now throw on
  missing cssSet/fontblock.
- **gen.py regeneration:** rerunning regenerates templates/includes from the mirror —
  make template changes in gen.py, not just in the generated files.
- **Repo hygiene:** .gitignore excludes mirror/, site/, node_modules/, raw/, raw2/.
  The mirror never leaves the server; only the Eleventy source is published.
- **Scope fences:** don't touch DNS, custom domains, or anything Squarespace-side;
  the preview is a subfolder preview, not the real domain.
- **Minor:** memory index wanted a rebuild at some point
  (`openclaw memory status --index --agent skinnypete`) — recall worked via keyword fallback.

## Update 2026-10-16 (punch-list resolved)

All punch-list items fixed via restoring the Squarespace visitor runtime
(per-cssSet `src/_includes/runtime-head/*.njk`, generated by gen.py; telemetry
stripped). Divider clip-paths, scaled text, header scroll-back, and image
machinery now behave like live (Playwright-verified). Hover-enlarge on the 3
home images added as documented deviation (live currently has none). 8 runtime
files missing from the mirror were fetched from Squarespace CDNs. Every page's
front matter now carries `headerTheme`. gen.py no longer regenerates
.pages.yml (hand-maintained for Pages CMS). See PUNCH-LIST.md + FIDELITY-NOTES.md.
