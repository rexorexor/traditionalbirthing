#!/usr/bin/env python3
"""Standalone HTML re-rewrite from pristine raw2 originals.

Only touches the 4 archive pages. Rules:
- CDN asset hosts -> local docroot-relative paths (pages sit at site root,
  so file-relative == docroot-relative)
- srcset candidates handled individually, ?format= variants preserved
- www.traditionalbirthing.com page links -> local .html files
- dead nav (/about /birth /postpartum /cart) -> index.html
- www.jenholland.com and all other hosts -> left external
"""
import re, os, html as H
from pathlib import Path
from urllib.parse import urlparse, urljoin

ROOT = Path("/projects/traditionalbirthing")
RAW = ROOT / "raw2"
SITE = ROOT / "site"

CDN_HOSTS = {
    "images.squarespace-cdn.com",
    "definitions.sqspcdn.com",
    "assets.squarespace.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "elfsightcdn.com",
}
INTERNAL_HOST = "www.traditionalbirthing.com"
BASE = "https://www.traditionalbirthing.com"

PAGES = {
    "index.html": "root.html",
    "home.html": "home.html",
    "contact.html": "contact.html",
    "ibclc.html": "ibclc.html",
}

ATTR_RE = re.compile(
    r"""\b(href|src|srcset|data-src|data-image|data-srcset|poster)\s*=\s*(["'])([^"']+)\2""",
    re.I,
)
URL_PAREN_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)

def normalize(u):
    u = u.strip()
    if u.startswith("//"): return "https:" + u
    if u.startswith(("http://", "https://")): return u
    if u.startswith("/"): return urljoin(BASE, u)
    return u

def split_srcset(val):
    out = []
    for piece in val.split(","):
        piece = piece.strip()
        if piece:
            bits = piece.split(None, 1)
            out.append((bits[0], bits[1] if len(bits) > 1 else ""))
    return out

def local_for(abs_url):
    """Docroot-relative local path for a CDN URL, or None to keep as-is."""
    p = urlparse(abs_url)
    host = p.netloc
    if host in CDN_HOSTS:
        path = p.path.lstrip("/")
        if p.query:
            base, dot, ext = path.rpartition(".")
            if dot:
                path = f"{base}__{p.query}.{ext}"
            else:
                path = f"{path}__{p.query}"
        return path
    if host == INTERNAL_HOST:
        pp = p.path
        if pp in ("/", ""): return "index.html"
        if pp == "/home": return "home.html"
        if pp == "/contact": return "contact.html"
        if pp == "/ibclc": return "ibclc.html"
        # dead nav handled separately post-substitution
        return None
    return None  # external: leave untouched

def rewrite(html_text):
    def repl_attr(m):
        attr, quote, val = m.group(1), m.group(2), H.unescape(m.group(3))
        if attr.lower() == "srcset" or ("," in val and re.search(r"\d+w|\d+x", val)):
            parts = []
            for u, dscr in split_srcset(val):
                nu = normalize(u)
                loc = local_for(nu)
                parts.append(f"{loc} {dscr}".strip() if loc else u)
            return f'{attr}={quote}{", ".join(parts)}{quote}'
        nu = normalize(val)
        loc = local_for(nu)
        if loc:
            return f'{attr}={quote}{loc}{quote}'
        return m.group(0)
    new = ATTR_RE.sub(repl_attr, html_text)

    # inline style url(): only fragments in this site's HTML; leave untouched
    return new

def main():
    for dest_name, raw_name in PAGES.items():
        raw = (RAW / raw_name).read_text(encoding="utf-8", errors="replace")
        new = rewrite(raw)
        # dead nav links -> index.html (careful: preserve closing quote)
        new = re.sub(
            r'''(\bhref\s*=\s*["'])(?:/about|/birth|/postpartum|/cart)(["'])''',
            lambda m: m.group(1) + "index.html" + m.group(2),
            new, flags=re.I,
        )
        (SITE / dest_name).write_text(new, encoding="utf-8")
        print(f"  {dest_name}: {len(new)} bytes")

    # sanity: every href/src value well-formed (no unterminated quotes)
    ok = True
    for dest_name in PAGES:
        h = (SITE / dest_name).read_text(encoding="utf-8", errors="replace")
        # a well-formed page: count of href=" equals count of bare href= occurrences
        n_attr = len(re.findall(r'\b(?:href|src)=', h))
        n_quoted = len(re.findall(r'\b(?:href|src)="', h)) + len(re.findall(r"\b(?:href|src)='", h))
        if n_attr != n_quoted:
            print(f"  ! {dest_name}: {n_attr} href/src attrs but {n_quoted} quoted")
            ok = False
    print("attr quoting:", "OK" if ok else "BROKEN")

if __name__ == "__main__":
    main()
