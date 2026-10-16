# PUNCH-LIST — known gaps in the Eleventy rebuild

Logged 2026-10-15 from owner review of the built site (after the cssSet/stylesheet fix
landed same day). Source of truth for design: `/projects/traditionalbirthing/mirror/`.
Diagnostic notes below are observations from the Oct 15 sessions, not fixes.

## Missing images (which pages, roughly where)

- **/contact** — flower image(s) missing at the top of the page.
- **/ibclc** — image missing at the top of the page.

  Observation: the `<img>` markup for both top sections IS present in the built
  HTML and the referenced files exist on disk under `site/content/v1/...`
  (contact: `unsplash-image-koy6FlCCy5s.jpg`; ibclc: `unsplash-image-t2Sai-AqIpI.jpg`).
  Suspected cause: those fluid-engine image blocks relied on Squarespace's
  imageFluid component JS (image-effect-*.js visitor scripts) which the rebuild
  intentionally dropped from the head — without it the image sizing/visibility
  may never initialize. Needs investigation when picking this up.

## Missing text (which pages, what area)

- **/ibclc** — "IN-PERSON AND VIRTUAL VISITS AVAILABLE" missing from under the
  "lactation and infant feeding support" text at the top of the page.
- **/ (home)** — "SERVING SPRINGFIELD, EUGENE, AND SURROUNDING COMMUNITIES"
  missing from the page, under "Traditional Birth Services / Independent
  lactation and doula practice in Springfield, Oregon".

  Observation: BOTH strings ARE present in the built HTML (and in the mirror) —
  ibclc section-0 and home/index section-0. They are wrapped in Squarespace
  "scaled text" markup (`sqsrte-scaled-text-container` / `sqsrte-scaled-text`
  around a `<pre><code>`), which is JS-measured/scaled on the live site. With
  the runtime scripts dropped, the scaled-text sizing likely collapses/hides
  the text. Treat as a rendering mechanism gap, not lost content.

## Color not correct

- **/ (home) and /ibclc** — a lot of tan where it should be white.

  Observation: stylesheets and body classes now match the mirror exactly, so
  this is likely palette-variable application inside specific sections
  (per-section `data-section-theme` / `white-bold` tokens) rather than missing
  CSS globally. Needs a side-by-side check of the affected sections' CSS vars.

## Missing hover animations (which elements)

- **/ (home)** — the three linked images/cards ("Labor and Birth", "Prenatal",
  "Lactation") should enlarge on hover; they don't.

  Observation: the hover-enlarge effect on the live site is driven by the
  imageFluid image-effect JS and/or `:hover` rules keyed on JS-applied classes.
  The image-effect scripts exist on disk (`site/universal/.../image-effect-*.js`)
  but are no longer referenced by the built pages (intentional drop).
- **All pages** — the top navigation bar should reappear when scrolling back up
  from the middle/bottom of a page; it never does in the rebuild. (On the
  original live site this behavior is also flaky, so treat live as
  best-effort reference.) The behavior is driven by `site-bundle.js`
  (`Header` controller, `headerStyle: "dynamic"`) — script IS loaded in the
  build; why it never re-reveals needs investigation (possibly a
  scroll-listener prerequisite or missing body-level state class).

## Missing

- **/contact** — the contact form is missing. **This one is intentional**: the
  Squarespace form was dead in a static copy (submitted to
  `magnolia-jellyfish-td43.squarespace.com`), so it was replaced with a styled
  block offering an email link (liz@traditionalbirthing.com) and the Book
  online button (clientsecure.me). See FIDELITY-NOTES.md. If a real form is
  wanted later, it needs a static-friendly backend (e.g. Formspree) — decision
  pending.
