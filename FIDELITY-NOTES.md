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

## Asset notes

- All CSS, fonts (30 files), and images (196 files) reused as-is from the
  mirror; no styles rewritten. Asset references were converted to
  root-absolute paths (`/content/...`, `/static/...`, `/universal/...`) so
  nested slugs (`/home/` etc.) resolve — verified 0 broken local refs.
- Favicon served locally from `/content/v1/.../favicon__format=100w.ico`.
- sitemap.xml lists the 4 content pages with the live site's lastmod dates.
- No /cart page (per instructions; Squarespace's live /cart is a generic
  shell and was never in the mirror).

## Editing model

- Page front matter (title/description/nav order): `src/pages/*.md`
- Coming-soon + 404 body text: `src/pages/*.md` (Markdown)
- Content page body text: `src/_includes/sections/<page>/section-*.njk`
  (search for `sqs-html-content` blocks)
- Nav items: `src/_data/nav.json`
- Pages CMS config: `.pages.yml` (pages + images only)

## Build

```
cd /projects/traditionalbirthing
npm install --include=dev   # note: global npm config omits devDependencies
npm run build               # → site/
npm run dev                 # → http://localhost:8080
```
