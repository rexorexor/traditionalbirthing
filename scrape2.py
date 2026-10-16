#!/usr/bin/env python3
"""Pass 2: deeper asset discovery and rewrite.

Builds on pass 1 (HTML pages already on disk). Walks:
  - raw HTML for background-image, srcset, data-image, inline style urls, favicon, fonts
  - raw HTML and downloaded CSS for url(...) references and any host we mirror
  - 7 distinct ?format= variants per image (100w..2500w) preserved as separate files
Then re-downloads anything new and rewrites both HTML and CSS to local paths.
"""
import html as H
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import urllib.request as ur
import urllib.error as ue

ROOT = Path("/projects/traditionalbirthing")
RAW = ROOT / "raw2"          # fresh raw HTML
SITE = ROOT / "site"
UA = "Mozilla/5.0 (compatible; archive-fetch/2.0)"
BASE = "https://www.traditionalbirthing.com"
CONCURRENCY = 8
THROTTLE = 0.12

# Hosts whose assets we mirror
MIRROR_HOSTS = {
    "images.squarespace-cdn.com",
    "definitions.sqspcdn.com",
    "assets.squarespace.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "elfsightcdn.com",
    "www.jenholland.com",
}
# Internal page host (used to remap page links, not assets)
INTERNAL_HOST = "www.traditionalbirthing.com"

PAGES = {
    "index.html": "/",
    "home.html":  "/home",
    "contact.html": "/contact",
    "ibclc.html":  "/ibclc",
}

# ---------- fetch ----------

def fetch(url: str, dest: Path, max_tries=3, timeout=30):
    if dest.exists() and dest.stat().st_size > 0:
        return True, "cached", dest.stat().st_size
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, max_tries + 1):
        try:
            req = ur.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with ur.urlopen(req, timeout=timeout) as r:
                data = r.read()
                dest.write_bytes(data)
                time.sleep(THROTTLE)
                return True, r.status, len(data)
        except ue.HTTPError as e:
            if e.code in (404, 410):
                return False, e.code, 0
            if attempt < max_tries:
                time.sleep(0.4 * attempt)
                continue
            return False, e.code, 0
        except Exception as e:
            if attempt < max_tries:
                time.sleep(0.4 * attempt)
                continue
            return False, str(e), 0

# ---------- URL discovery ----------

ATTR_RE = re.compile(
    r'''\b(?:href|src|srcset|data-src|data-image|data-srcset|content|poster|cite|background)\s*=\s*["']([^"']+)["']''',
    re.I,
)
URL_RE = re.compile(r'https?://[^\s"\'<> )\\]+')
PROTO_RE = re.compile(r'(?<!:)//[^\s"\'<> )\\]+')

def normalize(u: str) -> str:
    u = u.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith(("http://", "https://")):
        return u
    if u.startswith("/"):
        return urljoin(BASE, u)
    return u

def host_of(u: str) -> str:
    try:
        return urlparse(normalize(u)).netloc
    except Exception:
        return ""

def is_mirror(u: str) -> bool:
    h = host_of(u)
    if h in MIRROR_HOSTS:
        return True
    if h.endswith(".squarespace-cdn.com") or h.endswith(".sqspcdn.com"):
        return True
    return False

def split_srcset(val: str):
    out = []
    for piece in val.split(","):
        piece = piece.strip()
        if piece:
            out.append(piece.split(None, 1)[0])
    return out

def collect_from_html(html: str):
    """Yield absolute asset URLs found in any attribute or free-floating."""
    seen = set()
    def emit(u):
        u = urldefrag(u)[0]
        if not u or u in seen:
            return
        # drop the trailing "] that the free-floating URL regex picks up from JSON
        u = u.rstrip(']"\\')
        if not u or u in seen:
            return
        proto = u.split(":", 1)[0].lower()
        if proto in ("data", "javascript", "mailto", "tel", "sms", "blob"):
            return
        if u.startswith("#"):
            return
        if not is_mirror(u):
            return
        seen.add(u)
        yield u

    for m in ATTR_RE.finditer(html):
        val = H.unescape(m.group(1))
        if val.startswith(("http:", "https:", "//", "/")):
            if "," in val and re.search(r"\d+w|\d+x", val):
                for u in split_srcset(val):
                    yield from emit(u)
            else:
                yield from emit(val)

    # free-floating inside JSON blobs / inline CSS
    for m in URL_RE.finditer(html):
        u = H.unescape(m.group(0).rstrip("),;\\"))
        if is_mirror(u):
            yield from emit(u)
    for m in PROTO_RE.finditer(html):
        u = "https:" + H.unescape(m.group(0).rstrip("),;\\"))
        if is_mirror(u):
            yield from emit(u)


def collect_from_css(css_text: str):
    """Yield absolute asset URLs found in url(...) and @import/url(src=)."""
    seen = set()
    # url(...)
    for m in re.finditer(r'url\(\s*([\'"]?)([^\'")]+)\1\s*\)', css_text, re.I):
        u = m.group(2).strip()
        if not u or u.startswith(("#", "data:")):
            continue
        nu = normalize(u)
        if is_mirror(nu) and nu not in seen:
            seen.add(nu)
            yield nu
    # background-image etc -- covered by url() above, but also pull src= from @font-face
    for m in re.finditer(r"@font-face\s*\{[^}]*?src\s*:\s*([^;}]+)", css_text, re.I | re.S):
        for um in re.finditer(r'url\(\s*([\'"]?)([^\'")]+)\1\s*\)', m.group(1)):
            u = um.group(2).strip()
            if not u or u.startswith(("#", "data:")):
                continue
            nu = normalize(u)
            if is_mirror(nu) and nu not in seen:
                seen.add(nu)
                yield nu

# ---------- variant expansion ----------

# 7 size variants that Squarespace uses in srcsets (100w, 300w, 500w, 750w, 1000w, 1500w, 2500w)
SIZE_VARIANTS = ["100w", "300w", "500w", "750w", "1000w", "1500w", "2500w"]
SIZE_MAP = {"100w": 100, "300w": 300, "500w": 500, "750w": 750,
            "1000w": 1000, "1500w": 1500, "2500w": 2500}

def expand_image_variants(url: str):
    """For a squarespace-cdn image, yield the base URL plus ?format=Nw variants."""
    yield url
    if "images.squarespace-cdn.com/content/" in url and "?" not in url:
        for v in SIZE_VARIANTS:
            yield f"{url}?format={v}"

# ---------- path mapping ----------

def url_to_local_path(url: str) -> Path:
    """Map a mirror asset URL to a local path under SITE/.

    Preserves the URL's path and (if present) the ?query string in the filename
    so distinct ?format= variants land as distinct files.
    """
    nu = normalize(url)
    p = urlparse(nu)
    path = p.path.lstrip("/")
    if p.query:
        # /content/v1/.../img.jpg?format=1000w -> .../img__format=1000w.jpg
        base, ext = os.path.splitext(path)
        path = f"{base}__{p.query}{ext}"
    return SITE / path

def url_to_local_rel(asset_url: str, page_file: Path) -> str:
    """Local path string, relative to the file that references it."""
    target = url_to_local_path(asset_url)
    try:
        rel = os.path.relpath(target, page_file.parent)
    except ValueError:
        rel = str(target)
    return rel.replace(os.sep, "/")

# ---------- HTML rewrite ----------

def rewrite_html(html: str, page_file: Path) -> str:
    def to_local(u: str) -> str:
        return url_to_local_rel(u, page_file)

    def repl_attr(m):
        prefix = m.group(0).split("=", 1)[0]
        quote = m.group(0)[-1]
        val = H.unescape(m.group(1))
        if prefix.lower() == "srcset":
            parts = []
            for piece in val.split(","):
                bits = piece.strip().split(None, 1)
                if not bits: continue
                u = bits[0]
                dscr = bits[1] if len(bits) > 1 else ""
                nu = normalize(u)
                if is_mirror(nu):
                    parts.append(f"{to_local(nu)} {dscr}".strip())
                else:
                    parts.append(f"{u} {dscr}".strip())
            return f'{prefix}={quote}{", ".join(parts)}{quote}'
        if val.startswith(("http:", "https:", "//", "/")):
            nu = normalize(val)
            h = host_of(nu)
            if is_mirror(nu):
                return f'{prefix}={quote}{to_local(nu)}{quote}'
            if h == INTERNAL_HOST:
                p = urlparse(nu).path
                local = {"/": "index.html", "/home": "home.html",
                         "/contact": "contact.html", "/ibclc": "ibclc.html"}.get(p)
                if local:
                    try:
                        rel = os.path.relpath(SITE / local, page_file.parent)
                    except ValueError:
                        rel = local
                    return f'{prefix}={quote}{rel.replace(os.sep, "/")}{quote}'
        return m.group(0)
    html = ATTR_RE.sub(repl_attr, html)

    def repl_free(m):
        u = H.unescape(m.group(0).rstrip("),;\\"))
        if is_mirror(u):
            return to_local(u) + (m.group(0)[-1] if not m.group(0).endswith("),;\\") else "")
        return m.group(0)
    html = URL_RE.sub(repl_free, html)
    return html

# ---------- CSS rewrite ----------

def rewrite_css(css_text: str, css_file: Path) -> str:
    def repl(m):
        q1 = m.group(1)
        u = m.group(2).strip()
        if not u or u.startswith(("#", "data:")):
            return m.group(0)
        nu = normalize(u)
        if is_mirror(nu):
            try:
                rel = os.path.relpath(url_to_local_path(nu), css_file.parent)
            except ValueError:
                rel = str(url_to_local_path(nu))
            return f"url({q1}{rel.replace(os.sep, '/')}{q1})"
        return m.group(0)
    return re.sub(r'url\(\s*([\'"]?)([^\'")]+)\1\s*\)', repl, css_text, flags=re.I)

# ---------- main ----------

def main():
    # 0. Re-fetch raw HTML if not present
    if not (RAW / "ibclc.html").exists():
        for fname, path in PAGES.items():
            url = BASE + path
            dest = RAW / f"{'root' if path=='/' else path.lstrip('/')}.html"
            fetch(url, dest)

    # 1. Read pages and gather first-pass asset URLs
    print("[1/5] Loading HTML and collecting attribute URLs ...")
    page_html = {}
    for fname, _ in PAGES.items():
        src = RAW / f"{'root' if PAGES[fname]=='/' else PAGES[fname].lstrip('/')}.html"
        page_html[fname] = src.read_text(encoding="utf-8", errors="replace")
    asset_urls = []
    for h in page_html.values():
        for u in collect_from_html(h):
            asset_urls.append(u)
    print(f"  unique pre-CSS-sweep: {len(set(asset_urls))}")

    # 2. Read every downloaded CSS and pull url(...) refs
    print("[2/5] Scanning downloaded CSS for url(...) refs ...")
    css_assets = set()
    for css in SITE.rglob("*.css"):
        text = css.read_text(encoding="utf-8", errors="replace")
        for u in collect_from_css(text):
            css_assets.add(u)
    print(f"  CSS-discovered: {len(css_assets)}")

    # 3. Combine, expand image variants
    print("[3/5] Expanding image variants and downloading ...")
    all_urls = set(asset_urls) | css_assets
    expanded = []
    for u in all_urls:
        for v in expand_image_variants(u):
            expanded.append(v)
    expanded = list(dict.fromkeys(expanded))  # dedupe preserve order
    print(f"  total URLs to fetch: {len(expanded)}")

    # 4. Download
    results = {"ok": 0, "cached": 0, "fail": 0}
    failures = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(fetch, u, url_to_local_path(u)): u for u in expanded}
        for fut in as_completed(futs):
            u = futs[fut]
            ok, code, size = fut.result()
            if ok and code == "cached":
                results["cached"] += 1
            elif ok:
                results["ok"] += 1
            else:
                results["fail"] += 1
                failures.append((u, code))
    print(f"  done: ok={results['ok']} cached={results['cached']} fail={results['fail']}")
    if failures:
        print("  failures (first 10):")
        for u, c in failures[:10]:
            print(f"    {c} {u}")

    # 5. Rewrite HTML pages
    print("[4/5] Rewriting HTML ...")
    for fname, _ in PAGES.items():
        page_path = SITE / fname
        # re-fetch from raw to start from clean original
        src = RAW / f"{'root' if PAGES[fname]=='/' else PAGES[fname].lstrip('/')}.html"
        raw = src.read_text(encoding="utf-8", errors="replace")
        new = rewrite_html(raw, page_path)
        page_path.write_text(new, encoding="utf-8")
        print(f"  + {fname} ({len(new)} bytes)")

    # 6. Rewrite CSS files
    print("[5/5] Rewriting CSS url() refs ...")
    css_files = list(SITE.rglob("*.css"))
    for css in css_files:
        try:
            text = css.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  ! skip {css}: {e}")
            continue
        new = rewrite_css(text, css)
        if new != text:
            css.write_text(new, encoding="utf-8")
            print(f"  + {css.relative_to(SITE)}")
    print("\nDONE.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
