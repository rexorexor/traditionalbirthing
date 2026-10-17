# HANDOFF — card-title alignment task (written 2026-10-17 ~04:20 PDT)

## RESOLVED (2026-10-17, same day)

The "Recommended fix" below was implemented with one measured correction:
**top-align all three title blocks** (not bottom-align the left one). Reason,
from Playwright line-box data: all three titles bottom-anchor on a shared
baseline, so first-line Y = bottom − line_count; bottom-aligning the left
title moved nothing (its 4-line title fills its cell either way). Final fix
in gen.py's head template: all three fe-blocks get desktop rows 38→45
(38/3/45, 38/10/45, 38/17/45) + flex-start/flex-start alignment, scoped
to body#collection-66ebb0a6da1a206c459e169a and min-width:768px.
Also: the right-card `<br>` is now owned by a gen.py rewrite (applies to the
shared home/index section copies; regen-safe). Verified: first-line Y equal
at 1280 (1459) and 1512 (1638), spread 0px, on /home/ and /; left title
unchanged vs live. Logged in FIDELITY-NOTES.md.

## Task (owner request, improvement over the original)

On the main page's three hover cards ("Prenatal and Postpartum Lactation Care"
/ "Labor and Birth Doula Support" / "Postpartum Doula Support"), the owner
wants the LEFT card's title shifted DOWN one line so all three titles align.
Quote: "the 'Prenatal and Postpartum Lactation Care' text is one line higher
than the other two. can you shift that text down in line with the 2 sections
to the right of it?"

## Verified facts (Playwright, measured — do not re-derive)

- **The offset exists in the original Squarespace design too.** Live == local
  at 1280px and 1512px viewports. First-line Y of each title:
  - 1512px: left 1638, center 1710, right 1779 (left is ~1 line high; right
    ~1 line low)
  - 1280px: left 1459, center 1462 (equal!), right 1523 (low)
  So the anomaly is viewport-dependent — mixed alignment + unequal cell
  heights, not a rebuild bug.
- **Mechanism** (from the built page's embedded per-block CSS):
  - Left title block `fe-block-880db7bdccdc3e829fc2`: grid-area `38/3/49/10`
    (cell spans rows 38–48 — TALLER), content TOP-aligned
    (`.sqs-block { justify-content: flex-start }` +
    `.sqs-block-alignment-wrapper { align-items: flex-start }`).
  - Center title block `fe-block-5cc335a3ca57481f7bc5`: grid-area
    `38/10/45/17` (rows 38–44), content BOTTOM-aligned (`flex-end` rules).
  - Right title block `fe-block-82bd3482e81e510a3be2`: grid-area `38/17/45/24`
    (rows 38–44), alignment rules not yet extracted (behavior matches center —
    bottom-aligned).
  - All three blocks' cells START at grid row 38 (same top); the difference is
    cell height + top-vs-bottom alignment inside the cell.
- **Same block ids on / AND /home/** (index and home are identical copies of
  the same mirror section; both pages share body id
  `collection-66ebb0a6da1a206c459e169a`). One scoped CSS rule covers both.
- **Measurement gotcha that burned this session:** probes against
  `http://127.0.0.1:8080/` hit the INDEX page (the `/` route), whose section
  copy was NOT edited — not the /home/ page where the fix landed. Measure
  `/home/` explicitly. Also: text-node rects inside these h2s come back in
  duplicated pairs (~1 line apart) — some Squarespace layering artifact,
  identical on live and local; dedupe by Y and don't panic.

## Uncommitted working-tree state (exactly one code change)

- `src/_includes/sections/home/section-0-6ab6dae3.njk` (MODIFIED, not
  committed): right card title changed to
  `<span class="sqsrte-text-color--white">Postpartum <br>Doula Support</span>`
  so it renders 2 lines like the other two at all widths (it was 1 line at
  some widths). Build passes; built /home/ has all three h2s with `<br>`.
- Its rendered effect was never actually measured (the probe hit the index
  copy — see gotcha above). Recommendation: KEEP it (guarantees the 2-line
  title the alignment fix assumes) but verify on /home/ first.
- `HANDOFF-TITLE-ALIGN.md` (this file) is also untracked.
- Everything else (punch-list runtime restore etc.) is committed and pushed
  through `719235f`; live Pages preview verified good.

## Recommended fix (not yet implemented)

Make all three title blocks structurally identical so first lines align at
every viewport: same grid rows (38→45) + same bottom alignment (flex-end,
matching center/right which the owner likes). Concretely, a scoped override
added to the `<style>` block in gen.py's head template (next to the existing
hover-shim style — remember: template changes go in gen.py or a rerun
overwrites them):

```css
/* Owner request: align the 3 home-card titles (deviation from live). */
body#collection-66ebb0a6da1a206c459e169a .fe-block-880db7bdccdc3e829fc2 {
  grid-area: 38 / 3 / 45 / 10;
}
body#collection-66ebb0a6da1a206c459e169a .fe-block-880db7bdccdc3e829fc2 .sqs-block { justify-content: flex-end; }
body#collection-66ebb0a6da1a206c459e169a .fe-block-880db7bdccdc3e829fc2 .sqs-block-alignment-wrapper { align-items: flex-end; }
```

The `body#collection-…` ID prefix beats the body-embedded per-block rules
(specificity), so cascade order doesn't matter.

**BEFORE shrinking the left cell rows 38–48 → 38–44:** check whether any OTHER
fe-block spans rows 45–48 in columns 3–9 of the same fluid-engine grid
(`.fe-6ab6dae31ec47c4e99260b78` on home/index). Grid rows are
`repeat(99, minmax(24px, auto))` — if the title block was the only content
making rows 45–48 tall, shrinking it lets those rows collapse and anything
positioned there shifts UP. If something occupies those rows, fall back to a
padding/margin-based downward shift of just the h2 inside the left block
(amount = distance needed to match the center title's first line; it scales
with viewport, so prefer a structural fix over fixed px if possible).

## Verification harness (ready to reuse)

- `/tmp/align1.js` — measures all three titles' per-line Y via TreeWalker +
  Range on live vs local at 1280/1512, screenshots to /tmp/shots/. Works;
  just point it at `http://127.0.0.1:8080/home/` for the fixed page (and `/`
  to confirm index got the same treatment). Pass/Fail = all three first-line
  Y equal at both widths.
- Local server: session `glow-forest` serves `/projects/traditionalbirthing/site`
  on 127.0.0.1:8080 (root-relative build). **After any `rm -rf site` +
  rebuild, RESTART it** (the old process holds the deleted directory inode
  and serves stale content — that cost this session several confusing loops).
- Prefixed-build smoke test (what CI ships): `npm run build:pages`, then
  serve a symlink root: `mkdir -p /tmp/pagesroot && ln -s
  /projects/traditionalbirthing/site /tmp/pagesroot/traditionalbirthing`,
  serve /tmp/pagesroot on another port, expect 200s under
  `/traditionalbirthing/...`.
- Live reference: https://www.traditionalbirthing.com/ (offset exists there —
  this fix intentionally DIVERGES from live).
- Playwright + deps live in the throwaway clone /tmp/pagescms
  (`node /tmp/align1.js` style; browser binary already installed).

## Env reminders (unchanged from HANDOFF.md)

- GH_PAT from secret store, use by reference; push form that works:
  `git push "https://x-access-token:$GH_PAT" main` (never echo it).
- npm needs `--include=dev`; `npx @11ty/eleventy` (not bare `eleventy`).
- Template edits go in gen.py; .pages.yml is hand-maintained (gen.py won't
  regenerate it).
- Scope fence: the live Squarespace site stays untouched; this is a
  rebuild-only improvement.
