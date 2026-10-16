#!/usr/bin/env python3
"""Generate the Eleventy project from the mirror (source of truth: /projects/traditionalbirthing/mirror)."""
import re, json, html as htmlmod
from pathlib import Path

ROOT = Path('/projects/traditionalbirthing')
MIR = ROOT / 'mirror'
INC = ROOT / 'src/_includes'
PAGES = ROOT / 'src/pages'
DATA = ROOT / 'src/_data'

PAGES_META = {
    'index':  dict(permalink='/', navOrder=0),
    'home':   dict(permalink='home/', navOrder=0),
    'contact': dict(permalink='contact/', navOrder=5),
    'ibclc':  dict(permalink='ibclc/', navOrder=1),
}
NAV = [
    dict(href='/ibclc/', label='IBCLC'),
    dict(href='/birth/', label='Birth'),
    dict(href='/postpartum/', label='Postpartum'),
    dict(href='/about/', label='About'),
    dict(href='/contact/', label='Contact'),
]

def read(name):
    return (MIR / name).read_text(errors='replace')

# ---------- generic rewrites applied to extracted HTML ----------
ASSET_PREFIXES = ('content/', 'static/', 'universal/', 'website-component-definition/', '@sqs/')

def rewrite(s):
    s = s.replace('href="index.html"', 'href="/"')
    s = s.replace('href="contact.html"', 'href="/contact/"')
    s = s.replace('href="ibclc.html"', 'href="/ibclc/"')
    s = s.replace('src="platform.js"', 'src="/platform.js"')
    # root-absolute asset refs so nested slugs (/home/ etc.) resolve
    def fix(m):
        tag = m.group(0)
        return re.sub(r'"(' + '|'.join(map(re.escape, ASSET_PREFIXES)) + r')', r'"/\1', tag)
    s = re.sub(r'<(script|link|img|source|image|use)[^>]*>', fix, s)
    # inline style url() and srcset/data-src attributes
    for attr in re.findall(r'(style|srcset|data-src|data-image)="[^"]+"', s):
        pass
    def fix_attr(m):
        name, val = m.group(1), m.group(2)
        new = re.sub(r'(?<![\w/.")(=])((?:' + '|'.join(map(re.escape, ASSET_PREFIXES)) + r')[\w./-]+)', r'/\1', val)
        new = re.sub(r'url\(("\'?)(?!/|data:|#|http)', lambda mm: 'url(' + mm.group(1) + '/' , new) if name == 'style' else new
        return f'{name}="{new}"'
    s = re.sub(r'(style|srcset|data-src|data-image)="([^"]+)"', fix_attr, s)
    return s

texts = {n: read(n + '.html') for n in ['home', 'index', 'contact', 'ibclc']}

# ---------- extract head metas ----------
def meta_of(name):
    t = texts[name]
    head = t[:t.find('</head>')]
    title = re.search(r'<title>(.*?)</title>', head, re.S).group(1).strip()
    title = htmlmod.unescape(title)
    desc = re.search(r'<meta name="description" content="(.*?)"\s*/?>', head, re.S).group(1)
    desc = htmlmod.unescape(desc).strip()
    return title, desc

# ---------- body tags ----------
body_tags = {}
for n in texts:
    body_tags[n] = re.search(r'<body[^>]*>', texts[n]).group(0)
print('body tag identical home/index:', body_tags['home'] == body_tags['index'])

# ---------- header ----------
hdr = texts['home'][texts['home'].find('<header'):texts['home'].find('</header>')+9]
# theme token in the <header ...> opening tag only
m = re.search(r'<header[^>]*class="[^"]*?"\s*data-section-theme="[^"]*"[^>]*>', hdr, re.S)
opentag = m.group(0)
hdr = re.sub(r'(class="\s*\n\s*\n\s*)(?:white|white-bold)(\n\s*\n\s*header theme-col--primary)',
             lambda mm: mm.group(1) + '{{ headerTheme }}' + mm.group(2), hdr, count=1)
hdr = hdr.replace('data-section-theme="white-bold"', 'data-section-theme="{{ headerTheme }}"', 1)
assert '{{ headerTheme }}' in hdr and 'white-bold' not in hdr

desktop_item = '''{%- for item in nav %}
<div class="header-nav-item header-nav-item--collection{% if item.href == navActive %} header-nav-item--active{% endif %}">
  <a href="{{ item.href }}" data-animation-role="header-element" {% if item.href == navActive %}aria-current="page" {% endif %}>
    {{ item.label }}
  </a>
</div>
{%- endfor %}'''
overlay_item = '''{%- for item in nav %}
<div class="container header-menu-nav-item header-menu-nav-item--collection{% if item.href == navActive %} header-menu-nav-item--active{% endif %}">
  <a href="{{ item.href }}" {% if item.href == navActive %}aria-current="page" {% endif %}>
    <div class="header-menu-nav-item-content">{{ item.label }}</div>
  </a>
</div>
{%- endfor %}'''

# desktop nav lists (there are two identical <nav class="header-nav-list"> blocks)
hdr, n_desk = re.subn(r'(<nav class="header-nav-list">).*?(</nav>)',
                      lambda mm: mm.group(1) + desktop_item + mm.group(2), hdr, flags=re.S)
# overlay items: contiguous run
pat = re.compile(r'<div class="container header-menu-nav-item header-menu-nav-item--collection">\s*<a[^>]*>\s*<div class="header-menu-nav-item-content">\s*[^<]+\s*</div>\s*</a>\s*</div>', re.S)
items = list(pat.finditer(hdr))
assert items, 'overlay items not found'
run = hdr[items[0].start():items[-1].end()]
hdr = hdr.replace(run, overlay_item, 1)
print('desktop nav lists replaced:', n_desk, '| overlay items replaced:', len(items))
hdr = rewrite(hdr)
assert '{{' not in hdr.replace('{{ headerTheme }}','').replace("{{ item.href }}","").replace("{{ item.label }}","").replace("{%", "")
hdr_inc = INC / 'partials/header.njk'; hdr_inc.parent.mkdir(parents=True, exist_ok=True)
hdr_inc.write_text(hdr)

# ---------- footer ----------
ftr = texts['home'][texts['home'].find('<footer'):texts['home'].find('</footer>')+9]
ftr = rewrite(ftr)
(INC / 'partials/footer.njk').write_text(ftr)

# ---------- body-open (siteWrapper + floating cart) per page ----------
t = texts['home']
b = re.search(r'<body[^>]*>', t).end()
h = t.find('<header')
pre = t[b:h]
for n, bt in body_tags.items():
    (INC / f'body-open/{n}.njk').parent.mkdir(parents=True, exist_ok=True)
    (INC / f'body-open/{n}.njk').write_text(bt + rewrite(pre))
print('body-open includes written:', len(body_tags))

# ---------- post-footer (siteWrapper close + svg defs + site-bundle) ----------
fe = t.find('</footer>') + 9
e = t.find('</body>')
post = rewrite(t[fe:e])
(INC / 'partials/post-footer.njk').write_text(post)

# ---------- main sections ----------
for n in ['home', 'index', 'contact', 'ibclc']:
    tt = texts[n]
    main = tt[tt.find('<main'):tt.find('</main>')+7]
    d = INC / f'sections/{n}'; d.mkdir(parents=True, exist_ok=True)
    secs = re.findall(r'<section\b.*?</section>', main, re.S)
    for i, s in enumerate(secs):
        sid = re.search(r'data-section-id="([^"]+)"', s).group(1)
        (d / f'section-{i}-{sid[:8]}.njk').write_text(rewrite(s))
    print(n, 'sections:', len(secs))

# ---------- contact form surgery ----------
t = texts['contact']
i = t.find('fe-block fe-block-d982279bf1970883ab70')
start = t.rfind('<div', 0, i)
depth = 0; end = None
for mm in re.finditer(r'<div\b|</div>', t[start:]):
    depth += 1 if mm.group(0).startswith('<div') else -1
    if depth == 0:
        end = start + mm.end(); break
formblock = t[start:end]
replacement = '''<div class="fe-block fe-block-d982279bf1970883ab70">
  <div class="sqs-block-content" style="text-align:center; padding: 4% 4% 4% 4%;">
    <div class="sqs-html-content" data-sqsp-text-block-content>
      <h3 style="text-align:center; white-space:pre-wrap" data-rte-preserve-empty="true"><span class="sqsrte-text-color--black">Prefer email, or ready to book?</span></h3>
      <p style="text-align:center; white-space:pre-wrap" data-rte-preserve-empty="true"><span class="sqsrte-text-color--black">Reach me directly at liz@traditionalbirthing.com &mdash; or request a visit through the secure booking portal.</span></p>
    </div>
    <div class="sqs-block-button-container--center" style="margin-top:1.75rem; display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; align-items:center;">
      <a href="mailto:liz@traditionalbirthing.com?subject=Interested%20in%20Traditional%20Birth%20Services" class="sqs-block-button-element--medium sqs-button-element--primary sqs-block-button-element" data-sqsp-button>Email Liz</a>
      <a href="https://elizabeth-weisenfluh.clientsecure.me/#services" class="sqs-block-button-element--medium sqs-button-element--primary sqs-block-button-element" data-sqsp-button target="_blank">Book online</a>
    </div>
  </div>
</div>'''
hit = 0
for f in (INC / 'sections/contact').glob('*.njk'):
    s = f.read_text()
    if formblock in s:
        f.write_text(s.replace(formblock, replacement)); hit += 1
print('form block replaced in', hit, 'section file(s); original size', len(formblock))

# ---------- css sets ----------
def css_of(name):
    head = texts[name][:texts[name].find('</head>')]
    out = []
    for l in re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', head):
        out.append(re.search(r'href=["\']([^"\']+)', l).group(1))
    return out

# Per-page stylesheet sets in exact mirror order (index==home, contact 9, ibclc 10).
csssets = {k: ['/' + u for u in css_of(k)] for k in ['index', 'home', 'contact', 'ibclc']}

# Per-page @font-face <style> block extracted verbatim from each mirror <head>,
# with CDN font urls rewritten to local root-absolute paths (/content/v2/...).
fontblocks = {}
for k in ['index', 'home', 'contact', 'ibclc']:
    head = texts[k][:texts[k].find('</head>')]
    m = re.search(r'<style data-sqsp-font-ids="[^"]*">.*?</style>', head, re.S)
    assert m, f"font-face block missing in mirror/{k}.html"
    fontblocks[k] = m.group(0).replace('https://file.squarespace-cdn.com/', '/')

# ---------- data files ----------
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'nav.json').write_text(json.dumps(NAV, indent=2))
(DATA / 'site.json').write_text(json.dumps({
    'url': 'https://www.traditionalbirthing.com',
    'name': 'Liz Weisenfluh IBCLC, THW Doula',
}, indent=2))
(DATA / 'pages.json').write_text(json.dumps({
    'home':   dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
    'index':  dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
    'contact': dict(collectionId='66f0d2010a176e32f3676171', cssSet='contact', headerTheme='white'),
    'ibclc':  dict(collectionId='6878284e734a911c16e6f720', cssSet='ibclc', headerTheme='white'),
    'birth': dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
    'postpartum': dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
    'about': dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
    '404': dict(collectionId='66ebb0a6da1a206c459e169a', cssSet='home', headerTheme='white-bold'),
}, indent=2))
(DATA / 'csssets.json').write_text(json.dumps(csssets, indent=2))
(DATA / 'fontblocks.json').write_text(json.dumps(fontblocks, indent=2))

# ---------- templates ----------
(INC / 'partials/head.njk').write_text('''<meta charset="utf-8"/>
<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<meta name="description" content="{{ description }}">
{%- if not noCanonical %}<link rel="canonical" href="{{ site.url }}{{ page.url }}"/>{% endif %}
<meta property="og:site_name" content="{{ site.name }}"/>
<meta property="og:title" content="{{ title }}"/>
<meta property="og:type" content="website"/>
<meta property="og:description" content="{{ description }}"/>
{%- if not noCanonical %}<meta property="og:url" content="{{ site.url }}{{ page.url }}"/>{% endif %}
<meta itemprop="name" content="{{ title }}"/>
<meta itemprop="description" content="{{ description }}"/>
<meta name="twitter:title" content="{{ title }}"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:description" content="{{ description }}"/>
<link rel="icon" type="image/x-icon" href="/content/v1/66ebb032b83aa7663c54a478/8b6f3ea8-31d7-4280-b995-2c201b372ae7/favicon__format=100w.ico"/>
{{- fontblocks[cssSet] | fontblockOrFail | safe }}
{%- set stylesheetList = csssets[cssSet] | csssetOrFail -%}
{%- for css in stylesheetList %}<link rel="stylesheet" href="{{ css }}"/>
{%- endfor %}
''')

(INC / 'page.njk').write_text('''<!doctype html>
<html lang="en">
<head>
{% include "partials/head.njk" %}
</head>
{% include "body-open/" + sectionsDir + ".njk" %}
{% include "partials/header.njk" %}
<main id="page" class="container" role="main">
  <article class="page-regions" id="page-regions" data-collection-id="{{ collectionId }}" data-item-id="" data-regions-source="collection">
  {%- for s in (sectionsDir | getSections) %}{% include s + ".njk" %}
  {%- endfor %}
  </article>
</main>
{% include "partials/footer.njk" %}
{% include "partials/post-footer.njk" %}
</body>
</html>
''')

(INC / 'coming-soon.njk').write_text('''{% set meta = pages[comingSoonBase] %}<!doctype html>
<html lang="en">
<head>
{% include "partials/head.njk" %}
</head>
{% include "body-open/" + comingSoonBase + ".njk" %}
{% include "partials/header.njk" %}
<main id="page" class="container" role="main">
  <article class="page-regions" id="page-regions" data-collection-id="{{ meta.collectionId }}" data-item-id="" data-regions-source="collection">
    <section data-test="page-section" data-section-theme="light" data-section-id="{{ page.url | slug }}" class="page-section layout-engine-section background-width--full-bleed section-height--small content-width--medium horizontal-alignment--center vertical-alignment--middle white-bold-section">
      <div class="section-border"><div class="section-background"></div></div>
      <div class="content-wrapper" style="padding-top: 10vw; padding-bottom: 10vw;">
        <div class="content" style="text-align:center; max-width: 42rem; margin-left: auto; margin-right: auto;">
          <h1 style="text-align:center; white-space:pre-wrap" data-rte-preserve-empty="true"><span class="sqsrte-text-color--accent">{{ title }}</span></h1>
          <div class="sqs-html-content" data-sqsp-text-block-content style="text-align:center;">
{{ content | safe }}
          </div>
          <div class="sqs-block-button-container--center" style="margin-top:2rem; display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; align-items:center;">
            <a href="/contact/" class="sqs-block-button-element--medium sqs-button-element--primary sqs-block-button-element" data-sqsp-button>Contact me</a>
            <a href="https://elizabeth-weisenfluh.clientsecure.me/#services" class="sqs-block-button-element--medium sqs-button-element--primary sqs-block-button-element" data-sqsp-button target="_blank">Book online</a>
          </div>
        </div>
      </div>
    </section>
  </article>
</main>
{% include "partials/footer.njk" %}
{% include "partials/post-footer.njk" %}
</body>
</html>
''')

# ---------- markdown pages ----------
PAGES.mkdir(parents=True, exist_ok=True)
def write_md(name, layout, extra, body):
    title, desc = meta_of(name)
    fm = {**dict(layout=layout, title=title, description=desc), **extra}
    fm_lines = ['---']
    for k, v in fm.items():
        fm_lines.append(f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {v}')
    fm_lines.append('---')
    (PAGES / f'{name}.md').write_text('\n'.join(fm_lines) + '\n\n' + body)

write_md('index', 'page.njk', dict(permalink='/', navOrder=0, sectionsDir='index', navActive='', cssSet='index', collectionId='66ebb0a6da1a206c459e169a'),
         '<!-- Body content is preserved as-is from the mirror in _includes/sections/index/ (Squarespace fluid-engine layout). -->\n')
write_md('home', 'page.njk', dict(permalink='home/', navOrder=0, sectionsDir='home', navActive='', cssSet='home', collectionId='66ebb0a6da1a206c459e169a'),
         '<!-- Body content is preserved as-is from the mirror in _includes/sections/home/ (Squarespace fluid-engine layout). -->\n')
write_md('contact', 'page.njk', dict(permalink='contact/', navOrder=5, sectionsDir='contact', navActive='/contact/', cssSet='contact', collectionId='66f0d2010a176e32f3676171'),
         '<!-- Body content is preserved as-is from the mirror in _includes/sections/contact/. The Squarespace form block was replaced with an email + Book online block (see FIDELITY-NOTES.md). -->\n')
write_md('ibclc', 'page.njk', dict(permalink='ibclc/', navOrder=1, sectionsDir='ibclc', navActive='/ibclc/', cssSet='ibclc', collectionId='6878284e734a911c16e6f720'),
         '<!-- Body content is preserved as-is from the mirror in _includes/sections/ibclc/ (Squarespace fluid-engine layout). -->\n')

CS = {
    'birth': dict(title='Birth', navOrder=2,
                  desc='Birth doula support page — coming soon. Traditional Birth Services, Liz Weisenfluh, Eugene & Springfield, Oregon.'),
    'postpartum': dict(title='Postpartum', navOrder=3,
                       desc='Postpartum care page — coming soon. Traditional Birth Services, Liz Weisenfluh, Eugene & Springfield, Oregon.'),
    'about': dict(title='About', navOrder=4,
                  desc='About Liz Weisenfluh — coming soon. IBCLC and certified birth & postpartum doula serving Eugene & Springfield, Oregon.'),
}
for slug, m in CS.items():
    (PAGES / f'{slug}.md').write_text(f'''---
layout: coming-soon.njk
title: "{m['title']}"
description: "{m['desc']}"
navOrder: {m['navOrder']}
permalink: {slug}/
comingSoonBase: home
cssSet: home
noCanonical: true
---

<p style="text-align:center; white-space:pre-wrap"><span class="sqsrte-text-color--black">Coming soon &mdash; this page is still being written.</span></p>
<p style="text-align:center; white-space:pre-wrap"><span class="sqsrte-text-color--black">Questions in the meantime? I&rsquo;m happy to talk birth, postpartum, and lactation support.</span></p>
''')

(PAGES / '404.md').write_text('''---
layout: coming-soon.njk
title: "Page not found"
description: "That page doesn't exist. Head back to Traditional Birth Services."
navOrder: 99
permalink: 404.html
comingSoonBase: home
cssSet: home
noCanonical: true
---

<p style="text-align:center; white-space:pre-wrap"><span class="sqsrte-text-color--black">That page doesn&rsquo;t exist in this archive.</span></p>
''')

# ---------- sitemap ----------
(ROOT / 'src/sitemap.njk').write_text('''---
permalink: /sitemap.xml
eleventyExcludeFromCollections: true
---
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{%- set sm = [["/","2026-09-27"],["/home/","2026-09-27"],["/contact/","2026-09-27"],["/ibclc/","2026-10-08"]] %}
{%- for u in sm %}
  <url><loc>{{ site.url }}{{ u[0] }}</loc><lastmod>{{ u[1] }}</lastmod></url>
{%- endfor %}
</urlset>
''')

# ---------- eleventy config ----------
(ROOT / 'eleventy.config.js').write_text('''const fs = require("fs");
const path = require("path");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({ "src/assets": "." });

  // Guards: never render a page silently without stylesheets/fonts.
  eleventyConfig.addNunjucksFilter("csssetOrFail", (v) => {
    if (!Array.isArray(v) || v.length === 0) {
      throw new Error("[head.njk] cssSet missing/unknown or csssets[cssSet] empty — refusing to build a page without stylesheets");
    }
    return v;
  });
  eleventyConfig.addNunjucksFilter("fontblockOrFail", (v) => {
    if (typeof v !== "string" || !v.includes("@font-face")) {
      throw new Error("[head.njk] fontblocks[cssSet] missing — refusing to build a page without @font-face");
    }
    return v;
  });

  eleventyConfig.addNunjucksFilter("getSections", (dir) => {
    const base = path.join(__dirname, "src/_includes/sections", dir);
    if (!fs.existsSync(base)) return [];
    return fs.readdirSync(base)
      .filter((f) => /^section-\\d+/.test(f))
      .sort()
      .map((f) => "sections/" + dir + "/" + f.replace(/\\.njk$/, ""));
  });

  return {
    dir: { input: "src", includes: "_includes", data: "_data", output: "site" },
    markdownTemplateEngine: "njk",
    templateFormats: ["md", "njk"],
  };
};
''')

# ---------- .pages.yml ----------
(ROOT / '.pages.yml').write_text('''# Pages CMS (https://pagescms.org) — minimal config: pages + images only.
media:
  input: src/assets/content
  output: /content

content:
  - name: pages
    label: Pages
    path: src/pages
    type: collection
    view:
      fields: [title, navOrder]
      primary: title
      sort: navOrder
    fields:
      - name: title
        label: Title
        type: string
      - name: description
        label: Meta description
        type: string
      - name: navOrder
        label: Nav order
        type: number
      - name: body
        label: Body
        type: rich-text
''')

print('GENERATION DONE')
