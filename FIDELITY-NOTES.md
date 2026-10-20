# Fidelity Notes — Eleventy rebuild of www.traditionalbirthing.com

Source of truth: the October 2026 static mirror (`/projects/traditionalbirthing/mirror/`).
Goal is visual fidelity to the live Squarespace design; deviations are logged below.

## Layout blocks kept as static HTML includes (not re-templated)

The four content pages (/, /home, /contact, /ibclc) are built on Squarespace's
"fluid engine" grid: every block is absolutely positioned via per-block inline
`<style>` rules (`fe-block` + `fluid-engine` grid measurement CSS). Rebuilding
those grids as Markdown/template markup would change rendering, so **all body
sections are preserved as-is** as Eleventy includes:

- `src/_includes/sections/index/` — 2 sections (home page body)
- `src/_includes/sections/home/` — 2 sections
- `src/_includes/sections/contact/` — 3 sections
- `src/_includes/sections/ibclc/` — 4 sections

Each `src/pages/*.md` file carries the front matter (title, description, nav
order, permalink) and includes those sections via `src/_includes/page.njk`.
Per-page `<body>` tag (Squarespace "tweak" classes) is preserved per page in
`src/_includes/body-open/*.njk` because those tweak classes drive site-wide CSS.

Page text is therefore still editable, but in the include files (and via Pages
CMS rich-text fields), not in the Markdown body — Markdown bodies hold the
three Coming-soon pages and the 404 only.

## Header/nav — templated

The shared header was templated into `src/_includes/partials/header.njk`:
nav items are generated from `src/_data/nav.json` (IBCLC, Birth, Postpartum,
About, Contact) with active-state (`aria-current`) support. The only per-page
differences in the original (theme token `white` vs `white-bold`, active nav
item) are parameterized. Birth/Postpartum/About now point at real Coming-soon
pages instead of dead links.

## Contact form — replaced (dead in static copy)

The Squarespace form block on /contact (block `d982279bf1970883ab70`) rendered
client-side from JS and submitted to
`https://magnolia-jellyfish-td43.squarespace.com` — non-functional in a static
copy. Replaced with a styled block using the site's own button/text classes:
an email link (`liz@traditionalbirthing.com`, found 28× in the mirror,
including `mailto:` links) and the Book online button
(`https://elizabeth-weisenfluh.clientsecure.me/#services`).
The dead form's wrapper class `fe-block fe-block-d982279bf1970883ab70` was
kept so the original block positioning CSS still applies.

## Elfsight reviews embed — kept as live embed

`elfsight-app-29930253-…` (Google Reviews) on / and /home loads at runtime
from Elfsight's platform via local `platform.js`. **Depends on the site's
Elfsight account staying active; the widget may be domain-locked to the
Squarespace domain (`www.traditionalbirthing.com` / `magnolia-jellyfish-td43.squarespace.com`)** —
if it does not render under a new domain, the widget's domain setting must be
updated in the Elfsight dashboard (or the embed replaced).

## Scripts dropped

Removed entirely (present in mirror, absent here):
- `universal/scripts-compressed/extract-css-runtime-*.js` (2 files)
- `universal/scripts-compressed/audio-player-*.js` (2 files)
- `<link rel="preconnect">` hints to `images.squarespace-cdn.com` /
  `file.squarespace-cdn.com`
- All other Squarespace runtime JS that the mirror's pages loaded in `<head>`
  (visitor-site-error-reporter, moment-js, cldr, common-vendors, commerce,
  user-account-core, performance, polyfiller) — none are needed for static
  layout; the pages are server-rendered HTML + CSS.

Scripts kept:
- `static/vta/.../site-bundle.js` — Squarespace's visitor bundle. **Required
  for layout/nav behavior**: it drives the mobile burger/overlay menu
  (`header--menu-open`), header dynamic behavior, and image lazy-loading.
- `/platform.js` — Elfsight loader (reviews embed, see above).

## Book online button

All clientsecure.me links (and `target="_blank"`) preserved exactly as in the
mirror, including the footer "Client Portal Access" button and the
`/#services` deep link on "Request a free consultation!" / "Request a visit
online!" / "Book online" buttons.

## Coming-soon pages

/birth, /postpartum, /about are new (the live pages are locked mid-edit,
HTTP 401). Each is a single light-themed section using the site's own
typography classes (`sqsrte-text-color--accent/black`), site buttons
(`sqs-block-button-element`), and the shared header/footer — matching the
site design rather than introducing new CSS. `noindex`-style canonicals are
omitted for these placeholder pages (marked `noCanonical`).

## Visitor runtime (restored 2026-10-16)

The original rebuild dropped Squarespace's visitor runtime from `<head>`.
Live-vs-local Playwright comparison proved it is load-bearing: section-divider
clip paths (empty `d="M0,0"` placeholders in the static HTML — true even in
raw live HTML — clip the whole section background to nothing; this hid the
contact/ibclc hero photos and the white divider fills, exposing the body
cream, which IS this design's `--white-hsl`), scaled text (`left:-10000px`
until the runtime adds `.loaded`), the header scroll-back controller
(site-bundle reads `Static.SQUARESPACE_CONTEXT.tweakJSON` at boot), image
load/effect machinery, and JSON-LD/OG parity.

- The runtime head is restored per-cssSet from the mirror
  (`src/_includes/runtime-head/<set>.njk`, generated by `gen.py`): context
  script, rollup registrations, polyfiller, universal scripts, and
  website-component-definition scripts — all URLs rewritten to local mirror
  paths. Telemetry is stripped: `visitor-site-error-reporter` and
  `performance-*` rollups are NOT restored.
- Eight files missing from the mirror were fetched from Squarespace's public
  CDNs into `src/assets/`: hash-rotated variants of universal scripts
  (`extract-css-runtime-6116832173dd2f2b`, `common-vendors-72fa9c07fc381882`,
  `commerce-c0e1549856382469`, `user-account-core-617cf16a65d56f3d`) used by
  the newer /index scrape, plus site-bundle's lazily-loaded webpack chunks
  (`7706.*`, `section-divider.*`, `floating-cart.*`) that are fetched on
  demand and were never in any page HTML.
- The runtime script tags are excluded from the `pathprefix.js` content-
  rewrite only where noted; `templateScriptsRootUrl` inside the context
  script is rewritten to the local/prefixed scripts dir.
- Benign console noise: 6 `[website.components.*] is already defined`
  page errors occur when serving the RAW mirror snapshot itself — inherent
  to Squarespace's own markup, not introduced by the rebuild. Runtime XHRs
  to Squarespace APIs (`/api/census/render-batch`, `/api/popup-overlay/render`)
  fail locally with 404/501; they are cosmetic-only (no visible impact).
- Every page's front matter now carries `headerTheme` (the header partial
  templates it; it previously rendered empty, diverging from live).

- All CSS, fonts (30 files), and images (196 files) reused as-is from the
  mirror; no styles rewritten. Asset references were converted to
  root-absolute paths (`/content/...`, `/static/...`, `/universal/...`) so
  nested slugs (`/home/` etc.) resolve — verified 0 broken local refs.
- Favicon served locally from `/content/v1/.../favicon__format=100w.ico`.
- sitemap.xml lists the 4 content pages with the live site's lastmod dates.
- No /cart page (per instructions; Squarespace's live /cart is a generic
  shell and was never in the mirror).

## Editing model

- Page front matter (title/description/nav order/headerTheme): `src/pages/*.md`
- Coming-soon + 404 body text: `src/pages/*.md` (Markdown)
- Content page body text: `src/_includes/sections/<page>/section-*.njk`
  (search for `sqs-html-content` blocks)
- Nav items: `src/_data/nav.json`
- Pages CMS config: `.pages.yml` (hand-maintained since the CMS extension:
  pages, nav, images, section-file entries; `settings.content.merge: true`.
  gen.py deliberately no longer regenerates it.)

## Title alignment deviation (2026-10-17, owner request)

- The 3 home-card titles ("Prenatal and Postpartum Lactation Care" / "Labor
  and Birth Doula Support" / "Postpartum Doula Support") bottom-anchor on a
  shared baseline in the Squarespace design, so their FIRST lines staircase
  with each title's line count (4/3/2 lines at 1512px; verified on live with
  Playwright). Owner asked for the titles to align; this is an intentional
  deviation from live.
- Fix (in `gen.py` head template, scoped to the home collection id and
  `min-width: 768px`): all three title fe-blocks get the same desktop grid
  rows (38/3/45, 38/10/45, 38/17/45 — left block live uses a taller cell
  38/3/49) and all three are TOP-aligned (flex-start) so first lines sit on
  one line at every width. Left title position is unchanged from live;
  center/right titles rise to meet it.
- Related: right card's title gets `<br>` after "Postpartum" (2 lines at all
  widths, applied to the shared home/index section copies via a gen.py
  rewrite) so all three titles wrap identically — also a deviation from live
  at narrow-desktop widths.
- Verified: first-line Y equal across all 3 titles at 1280 and 1512 (spread
  0px) on /home/ and /; left title's first line matches live exactly.
  Mobile (<768px) untouched — grid-areas there are unrelated and preserved.

## Build

```
cd /projects/traditionalbirthing
npm install --include=dev   # note: global npm config omits devDependencies
npm run build               # → site/
npm run dev                 # → http://localhost:8080
```

## 2026-10-20 — /birth/ full-fidelity rebuild (content-page pattern)

/birth/ upgraded from coming-soon body to page.njk + sectionsDir=birth with four
hand-authored sections (hero w/ image, white "what's included", 3-step flow, CTA)
using the site's Squarespace class vocabulary (page-section themes white-bold/white/
light, sqs-html-content blocks, site button classes). cssSet=home reused (no new
stylesheets); headerTheme=white (header over hero image, like IBCLC/Contact);
body-open/birth.njk copied from home's. Hero image reuses the site's existing
Labor-and-Birth home-card image (unsplash-image-ThbjgN2msG8, all srcset variants
local). Section files use section-{0..3}-<name>.njk naming (getSections sorts by
filename; numeric prefix is load-bearing). All [PLACEHOLDER] markers preserved.
