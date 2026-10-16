#!/usr/bin/env python3
"""Static archive scraper for traditionalbirthing.com.

Fetches all sitemap pages + every asset referenced from them, preserving
directory structure under /projects/traditionalbirthing/site/, then rewrites
HTML to use local relative paths so the archive works offline.
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
RAW = ROOT / "raw"
SITE = ROOT / "site"
UA = "Mozilla/5.0 (compatible; archive-fetch/1.0)"
BASE = "https://www.traditionalbirthing.com"
CONCURRENCY = 6
THROTTLE_SEC = 0.15

# Pages in the archive
PAGE_PLAN = {
    "index.html": "/",          # root landing -> site root
    "home.html":  "/home",
    "contact.html": "/contact",
    "ibclc.html":  "/ibclc",
}

# Attribute patterns that may carry URLs
ATTR_RE = re.compile(
    r'''\b(?:href|src|srcset|data-src|data-image|data-srcset|content|poster|cite)\s*=\s*["']([^"']+)["']''',
    re.I,
)
# Free-floating URLs (inside JSON blobs, inline CSS, etc.)
URL_RE = re.compile(r'https?://[^\s"\'<> )\\]+')
# Protocol-relative URLs
PROTO_RE = re.compile(r'(?<!:)//[^\s"\'<> )\\]+')

# Hosts we will mirror (everything else: strip or leave as external link)
MIRROR_HOSTS = {
    "images.squarespace-cdn.com",
    "definitions.sqspcdn.com",
    "assets.squarespace.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "elfsightcdn.com",
    "www.jenholland.com",
}

# Hosts that should remain external in the rewritten HTML (we'll still capture
# any static asset on the same host, but the page link itself stays external)
EXTERNAL_LINK_HOSTS = {
    "elizabeth-weisenfluh.clientsecure.me",
    "www.jenholland.com",
}

def fetch(url, dest: Path, max_tries=3, timeout=30):
    """Download url to dest, return (ok, code_or_err, size, ct)."""
    if dest.exists() and dest.stat().st_size > 0:
        return True, "cached", dest.stat().st_size, ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, max_tries + 1):
        try:
            req = ur.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with ur.urlopen(req, timeout=timeout) as r:
                data = r.read()
                ct = r.headers.get("Content-Type", "")
                dest.write_bytes(data)
                time.sleep(THROTTLE_SEC)
                return True, r.status, len(data), ct
        except ue.HTTPError as e:
            if e.code in (404, 410):
                return False, e.code, 0, ""
            if attempt < max_tries:
                time.sleep(0.5 * attempt)
                continue
            return False, e.code, 0, ""
        except Exception as e:
            if attempt < max_tries:
                time.sleep(0.5 * attempt)
                continue
            return False, str(e), 0, ""

def normalize(u: str, base: str = BASE) -> str:
    """Return absolute https URL."""
    u = u.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/"):
        return urljoin(base, u)
    return u

def split_srcset(u: str):
    """Split a srcset value into [(url, descriptor), ...]."""
    parts = []
    for piece in u.split(","):
        piece = piece.strip()
        if not piece:
            continue
        bits = piece.split()
        if not bits:
            continue
        parts.append((bits[0], bits[1] if len(bits) > 1 else ""))
    return parts

def collect_assets_from_html(html: str):
    """Return ordered list of absolute URLs to download."""
    seen = set()
    out = []

    def add(u):
        u = urldefrag(u)[0]
        if not u or u in seen:
            return
        # skip data:, javascript:, mailto:, tel:, anchors
        if u.split(":", 1)[0].lower() in ("data", "javascript", "mailto", "tel", "sms"):
            return
        nu = normalize(u)
        try:
            host = urlparse(nu).netloc
        except Exception:
            return
        if host in MIRROR_HOSTS:
            seen.add(u)
            out.append(nu)

    # 1. Attributes
    for m in ATTR_RE.finditer(html):
        val = H.unescape(m.group(1))
        if val.startswith(("http:", "https:", "//", "/")):
            if "," in val and (" 1x" in val or " 2x" in val or "w," in val or "w " in val):
                for url, _ in split_srcset(val):
                    add(url)
            else:
                add(val)

    # 2. Free-floating URLs in JSON / inline CSS (focus on mirror hosts)
    for m in URL_RE.finditer(html):
        u = H.unescape(m.group(0).rstrip("),;\\"))
        host = u.split("/", 3)[2] if "://" in u else ""
        if host in MIRROR_HOSTS:
            add(u)

    # 3. Protocol-relative
    for m in PROTO_RE.finditer(html):
        u = "https:" + H.unescape(m.group(0).rstrip("),;\\"))
        host = u.split("/", 3)[2] if "://" in u else ""
        if host in MIRROR_HOSTS:
            add(u)

    return out

def relpath_for(asset_url: str) -> Path:
    """Map an absolute asset URL to a local path under SITE/."""
    p = urlparse(asset_url)
    # /static/vta/.../scripts/foo.js -> vta/.../scripts/foo.js
    # /universal/scripts-compressed/foo.js -> universal/scripts-compressed/foo.js
    # /content/v1/.../foo.jpg -> content/v1/.../foo.jpg (images)
    path = p.path.lstrip("/")
    return SITE / path

def local_path(asset_url: str) -> str:
    """Return site-relative path string (forward slashes) for an asset URL."""
    return str(relpath_for(asset_url).relative_to(SITE))

def rewrite_html(html: str, page_filename: str) -> str:
    """Rewrite all mirror-host URLs in the HTML to local relative paths.

    `page_filename` is e.g. 'home.html' — used to build relative links for
    assets that sit at different depths.
    """
    page_dir = (SITE / page_filename).parent

    def to_local(asset_url: str) -> str:
        lp = SITE / urlparse(asset_url).path.lstrip("/")
        try:
            rel = os.path.relpath(lp, page_dir)
        except ValueError:
            rel = str(lp)
        return rel.replace(os.sep, "/")

    # Attribute rewrite
    def repl_attr(m):
        prefix = m.group(0).split("=", 1)[0]
        quote = m.group(0)[-1]  # " or '
        val = H.unescape(m.group(1))

        # srcset: handle per-candidate
        if prefix.lower() == "srcset":
            new_parts = []
            for url, descr in split_srcset(val):
                nu = normalize(url)
                host = urlparse(nu).netloc
                if host in MIRROR_HOSTS:
                    new_parts.append(f"{to_local(nu)} {descr}".strip())
                else:
                    new_parts.append(f"{url} {descr}".strip())
            return f'{prefix}={quote}{", ".join(new_parts)}{quote}'
        else:
            if val.startswith(("http:", "https:", "//", "/")):
                nu = normalize(val)
                host = urlparse(nu).netloc
                if host in MIRROR_HOSTS:
                    return f'{prefix}={quote}{to_local(nu)}{quote}'
                # internal page link -> local HTML
                if host == urlparse(BASE).netloc:
                    p = urlparse(nu).path
                    if p in ("/", ""):
                        local = "index.html"
                    elif p == "/home":
                        local = "home.html"
                    elif p == "/contact":
                        local = "contact.html"
                    elif p == "/ibclc":
                        local = "ibclc.html"
                    else:
                        return f'{prefix}={quote}{val}{quote}'
                    try:
                        rel = os.path.relpath(SITE / local, page_dir)
                    except ValueError:
                        rel = local
                    return f'{prefix}={quote}{rel.replace(os.sep, "/")}{quote}'
            return m.group(0)
    html = ATTR_RE.sub(repl_attr, html)

    # Free-floating URL rewrite (only for the same set of mirror hosts,
    # inside JSON/inline-CSS blobs)
    def repl_free(m):
        u = H.unescape(m.group(0).rstrip("),;\\"))
        nu = normalize(u)
        host = urlparse(nu).netloc
        if host in MIRROR_HOSTS:
            return to_local(nu) + (m.group(0)[-1] if not m.group(0).endswith("),;\\") else "")
        return m.group(0)
    html = URL_RE.sub(repl_free, html)
    return html

def main():
    SITE.mkdir(parents=True, exist_ok=True)

    # 1. Fetch all pages from the network to a local raw cache
    print(f"[1/4] Fetching {len(PAGE_PLAN)} pages from {BASE} ...")
    page_html = {}
    for fname, path in PAGE_PLAN.items():
        url = BASE + path
        dest = SITE / fname
        ok, code, size, ct = fetch(url, dest)
        if not ok:
            print(f"  ! {path}: failed ({code})")
            return 1
        page_html[fname] = dest.read_text(encoding="utf-8", errors="replace")
        print(f"  + {path} -> {fname} ({size} bytes)")

    # 2. Collect every asset URL across all pages
    print("[2/4] Collecting asset references ...")
    all_assets = []
    for fname, html in page_html.items():
        urls = collect_assets_from_html(html)
        print(f"  {fname}: {len(urls)} unique asset refs")
        all_assets.extend(urls)
    # dedupe, preserve order
    seen = set(); assets = []
    for a in all_assets:
        if a not in seen:
            seen.add(a); assets.append(a)
    print(f"  total unique assets: {len(assets)}")

    # 3. Download assets in parallel
    print(f"[3/4] Downloading {len(assets)} assets (concurrency={CONCURRENCY}) ...")
    results = {"ok": 0, "fail": 0, "cached": 0, "skipped": 0}
    failures = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(fetch, a, relpath_for(a)): a for a in assets}
        done = 0
        for fut in as_completed(futs):
            url = futs[fut]
            try:
                ok, code, size, ct = fut.result()
            except Exception as e:
                ok, code, size, ct = False, str(e), 0, ""
            done += 1
            if ok and code == "cached":
                results["cached"] += 1
            elif ok:
                results["ok"] += 1
            else:
                results["fail"] += 1
                failures.append((url, code))
            if done % 20 == 0 or done == len(assets):
                print(f"  {done}/{len(assets)} ok={results['ok']} cached={results['cached']} fail={results['fail']}")
    print(f"  done: ok={results['ok']} cached={results['cached']} fail={results['fail']}")
    if failures:
        print("  failures:")
        for u, c in failures[:30]:
            print(f"    {c} {u}")

    # 4. Rewrite HTML to use local paths
    print("[4/4] Rewriting HTML to local relative paths ...")
    for fname, html in page_html.items():
        new_html = rewrite_html(html, fname)
        (SITE / fname).write_text(new_html, encoding="utf-8")
        print(f"  + {fname} rewritten ({len(new_html)} bytes)")

    # 5. Generate a 404 fallback for offline browsing
    (SITE / "404.html").write_text(
        "<!doctype html><meta charset=utf-8><title>404 — Traditional Birthing archive</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:640px;margin:4em auto;padding:0 1em;color:#222}"
        "h1{font-size:1.6em}a{color:#0a66c2}</style>"
        "<h1>Page not found</h1><p>This page isn't part of the static archive. "
        "Try the <a href=\"index.html\">home page</a>.</p>",
        encoding="utf-8",
    )

    print("\nALL DONE.")
    print(f"Site root: {SITE}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
