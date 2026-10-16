#!/usr/bin/env python3
"""Pass 3: brute-force relative-URL resolver for the static archive.

For every CSS file and every HTML file:
  - Enumerate every url(...) in CSS; every href/src/srcset/data-src/data-image
    in HTML (including inline style="...url(...)...").
  - Resolve each URL against the file's own path.
  - Patterns:
      url(//host/...)         -> https://host/...
      url(/universal/...)     -> https://assets.squarespace.com/universal/...
      url(../../universal/...) -> resolved against file's dir, then rooted
                                  on /universal/, then https://assets.squarespace.com
      url(./...) or bare relative -> resolved against file's dir, rooted on /universal/
      url(data:...)           -> skip
      url(#fragment)          -> skip
  - Save each asset under SITE/<path>; ?query strings become __query in filename
  - Rewrite the file to a local relative path
  - Delete junk files and out-of-scope files (e.g. babylisteningmethod.html)
  - Re-download zero-byte CSS files
"""
import os
import re
import sys
import time
import posixpath
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request as ur
import urllib.error as ue
import urllib.parse as up

SITE = Path("/projects/traditionalbirthing/site")
RAW = Path("/projects/traditionalbirthing/raw2")
UA = "Mozilla/5.0 (compatible; archive-fetch/3.0)"
THROTTLE = 0.10
ASSETS_HOST = "assets.squarespace.com"
CDN_HOSTS = {
    "assets.squarespace.com",
    "images.squarespace-cdn.com",
    "definitions.sqspcdn.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "elfsightcdn.com",
    "www.jenholland.com",
}
HTML_PAGES = {
    "index.html":  "/",
    "home.html":   "/home",
    "contact.html": "/contact",
    "ibclc.html":  "/ibclc",
}

# ---------- URL resolution ----------

def is_skippable(u: str) -> bool:
    if not u: return True
    lo = u.lower().strip()
    # %23 is the url-encoded form of `#` (a fragment). Skip those.
    if lo.startswith(("#", "%23")): return True
    return lo.startswith(("data:", "javascript:", "mailto:", "tel:", "sms:"))

def resolve_url(u: str, owner_rel: str) -> str | None:
    """Resolve a URL candidate to an absolute https URL, or None if not fetchable."""
    u = u.strip().strip(' \t\n\r"\',;')
    if not u or is_skippable(u): return None
    if u.startswith("//"): return "https:" + u
    if u.startswith(("http://", "https://")): return u
    if u.startswith("/"):
        # path-absolute; pick CDN host by prefix
        if u.startswith("/universal/"):  return f"https://{ASSETS_HOST}" + u
        if u.startswith("/content/v"):    return "https://images.squarespace-cdn.com" + u
        if u.startswith("/website-component-definition/"):
            return "https://definitions.sqspcdn.com" + u
        if u.startswith("/static/"):     return "https://static1.squarespace.com" + u
        # default: assets.squarespace.com (covers /scripts-compressed, /images-v6, /fonts, /icons, etc.)
        return f"https://{ASSETS_HOST}" + u
    # bare relative path
    # URL-space resolution: the file's owner_rel is its URL path on the CDN.
    owner_url = "/" + owner_rel.lstrip("/")
    owner_dir_url = posixpath.dirname(owner_url)
    resolved = posixpath.normpath(posixpath.join(owner_dir_url, u))
    # Squarespace minified CSS sometimes uses overshoots like
    # `../../../../universal/foo`. normpath collapses the `..`s but can
    # produce a path above the CDN root, OR it can leave an already-doubled
    # `universal/universal/` segment if the source rel path itself
    # contained a literal `universal/universal/...`. Re-root to the owner's
    # directory (e.g. /universal/) in that case.
    if resolved.startswith("/.."):
        parts = [p for p in resolved.split("/") if p and p != ".."]
        resolved = "/" + "/".join(parts)
    # If the resolved path still has a doubled `universal/universal/`,
    # collapse it. This happens when the original rel path had `../universal/`
    # and the owner is already under `/universal/` (e.g. /universal/styles-compressed/).
    # After normpath we get `universal/...`; prepending `/` gives `/universal/...`
    # which is the correct URL. But if normpath already produced a path that
    # starts with `universal/universal/...`, strip the duplicate.
    if not resolved.startswith("/"):
        resolved = "/" + resolved
    # collapse a duplicated /universal/universal/ -> /universal/
    import re as _re
    resolved = _re.sub(r"^/universal/universal/", "/universal/", resolved)
    return f"https://{ASSETS_HOST}" + resolved

# ---------- local path mapping ----------

def local_path_for_url(url: str) -> Path:
    p = up.urlparse(url)
    path = p.path.lstrip("/")
    if p.query:
        base, ext = posixpath.splitext(path)
        if not ext: ext = ""
        path = f"{base}__{p.query}{ext}"
    return SITE / path

def rel_from_to(asset_url: str, owner_file: Path) -> str:
    """Local path string, relative to the *docroot* (SITE/) — not the CSS
    file's directory. CSS at site/universal/styles-compressed/X.css and
    asset at site/universal/scripts-compressed/Y.png are at different
    depths; the rewriter needs docroot-absolute paths (e.g.
    "universal/scripts-compressed/Y.png") so nginx serves them directly.
    """
    target = local_path_for_url(asset_url)
    try:
        r = os.path.relpath(target, SITE)
    except ValueError:
        r = str(target)
    return r.replace(os.sep, "/")

# ---------- fetch ----------

def fetch(url: str, dest: Path, tries=3):
    if dest.exists() and dest.stat().st_size > 0:
        return True, "cached", dest.stat().st_size
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            req = ur.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with ur.urlopen(req, timeout=30) as r:
                data = r.read()
                dest.write_bytes(data)
                time.sleep(THROTTLE)
                return True, r.status, len(data)
        except ue.HTTPError as e:
            last_err = e.code
            if e.code in (404, 410): return False, e.code, 0
            if attempt < tries: time.sleep(0.4 * attempt)
        except Exception as e:
            last_err = str(e)[:60]
            if attempt < tries: time.sleep(0.4 * attempt)
    return False, last_err, 0

# ---------- extraction patterns ----------

URL_PAREN_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)
ATTR_RE = re.compile(
    r"""\b(?:href|src|srcset|data-src|data-image|data-srcset|poster|cite|background)\s*=\s*(["'])([^"']+)\1""",
    re.I,
)
INLINE_STYLE_URL_RE = re.compile(r"""style\s*=\s*["'][^"']*?url\(\s*(['"]?)([^'")]+)\1\s*\)[^"']*?["']""", re.I)

def split_srcset(val: str):
    out = []
    for piece in val.split(","):
        piece = piece.strip()
        if piece:
            out.append(piece.split(None, 1)[0])
    return out

# ---------- HTML rewrite ----------

def rewrite_html(html: str, page_file: Path) -> str:
    owner = page_file.relative_to(SITE).as_posix()
    def repl_attr(m):
        quote = m.group(1)
        prefix = m.group(0).split("=", 1)[0]
        val = m.group(2)
        is_srcset = (prefix.lower() == "srcset")
        # extract per-candidate URLs
        if is_srcset:
            cands = split_srcset(val)
        elif val.startswith(("http:", "https:", "//", "/")):
            cands = [val]
        else:
            cands = [val]
        out = []
        for u in cands:
            base, _, descr = u.partition(" ")
            abs_url = resolve_url(base, owner)
            if not abs_url or not abs_url.startswith("http"):
                out.append(u); continue
            host = up.urlparse(abs_url).netloc
            if host in CDN_HOSTS:
                out.append(f"{rel_from_to(abs_url, page_file)} {descr}".strip())
            elif host == "www.traditionalbirthing.com":
                pp = up.urlparse(abs_url).path
                local = {"/": "index.html", "/home": "home.html",
                         "/contact": "contact.html", "/ibclc": "ibclc.html"}.get(pp)
                if local:
                    try:
                        r = os.path.relpath(SITE / local, page_file.parent)
                    except ValueError:
                        r = local
                    out.append(f"{r.replace(os.sep, '/')} {descr}".strip())
                else:
                    out.append(u)
            else:
                out.append(u)
        return f'{prefix}={quote}{", ".join(out)}{quote}'
    new = ATTR_RE.sub(repl_attr, html)
    # inline style="...url(...)..."
    def repl_style(m):
        s = m.group(0)
        return URL_PAREN_RE.sub(
            lambda um: f"url({um.group(1)}{rel_from_to(resolve_url(um.group(2), owner) or '', page_file)}{um.group(1)})"
                if resolve_url(um.group(2), owner) and resolve_url(um.group(2), owner).startswith("http")
                else um.group(0),
            s,
        )
    new = INLINE_STYLE_URL_RE.sub(repl_style, new)
    return new

# ---------- CSS rewrite ----------

def rewrite_css(css_text: str, css_file: Path) -> str:
    owner = css_file.relative_to(SITE).as_posix()
    def repl(m):
        q = m.group(1)
        u = m.group(2)
        abs_url = resolve_url(u, owner)
        if abs_url and abs_url.startswith("http"):
            return f"url({q}{rel_from_to(abs_url, css_file)}{q})"
        return m.group(0)
    return URL_PAREN_RE.sub(repl, css_text)

# ---------- collector ----------

def collect_urls(file: Path) -> set:
    text = file.read_text(encoding="utf-8", errors="replace")
    owner = file.relative_to(SITE).as_posix()
    urls = set()
    if file.suffix == ".css":
        for m in URL_PAREN_RE.finditer(text):
            a = resolve_url(m.group(2), owner)
            if a: urls.add(a)
    else:
        for m in ATTR_RE.finditer(text):
            val = m.group(2)
            for u in (split_srcset(val) if ("," in val and re.search(r"\d+w|\d+x", val)) else [val]):
                a = resolve_url(u, owner)
                if a: urls.add(a)
        for m in INLINE_STYLE_URL_RE.finditer(text):
            a = resolve_url(m.group(2), owner)
            if a: urls.add(a)
    return urls

# ---------- main ----------

def main():
    print("[1/6] Enumerating every url() and attribute from every CSS and HTML file ...")
    files = [p for p in SITE.rglob("*") if p.is_file() and (p.suffix == ".css" or p.suffix == ".html")]
    all_urls = set()
    for f in files:
        all_urls |= collect_urls(f)
    print(f"  files scanned: {len(files)}")
    print(f"  unique URLs to consider: {len(all_urls)}")

    print("[2/6] Fetching any missing assets ...")
    to_fetch = [u for u in all_urls
                if not (local_path_for_url(u).exists() and local_path_for_url(u).stat().st_size > 0)]
    print(f"  to fetch: {len(to_fetch)}")
    results = {"ok": 0, "fail": 0, "cached": 0}
    fails = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, u, local_path_for_url(u)): u for u in to_fetch}
        for fut in futs:
            u = futs[fut]
            try:
                ok, code, size = fut.result()
            except Exception as e:
                ok, code, size = False, str(e), 0
            if ok and code == "cached": results["cached"] += 1
            elif ok: results["ok"] += 1
            else:
                results["fail"] += 1
                fails.append((u, code))
    print(f"  ok={results['ok']} cached={results['cached']} fail={results['fail']}")
    for u, c in fails[:30]:
        print(f"    {c} {u}")

    print("[3/6] Re-downloading zero-byte CSS files ...")
    for css in [p for p in SITE.rglob("*") if p.is_file() and p.suffix == ".css"]:
            url = f"https://{ASSETS_HOST}/universal/styles-compressed/{css.name}"
            ok, code, size = fetch(url, css)
            print(f"  {css.name}: ok={ok} code={code} size={size}")

    print("[4/6] Rewriting all CSS files ...")
    n_css = 0
    for css in [p for p in SITE.rglob("*") if p.is_file() and p.suffix == ".css"]:
        text = css.read_text(encoding="utf-8", errors="replace")
        new = rewrite_css(text, css)
        if new != text:
            css.write_text(new, encoding="utf-8"); n_css += 1
    print(f"  CSS files rewritten: {n_css}")

    print("[5/6] Rewriting HTML pages (from raw originals) ...")
    for fname, path in HTML_PAGES.items():
        page_path = SITE / fname
        raw_src = RAW / ("root.html" if path == "/" else (path.lstrip("/") + ".html"))
        raw = raw_src.read_text(encoding="utf-8", errors="replace")
        new = rewrite_html(raw, page_path)
        # also fix dead nav links (/about /birth /postpartum /cart)
        new = re.sub(
            r'''(\bhref\s*=\s*["'])(/about|/birth|/postpartum|/cart)(["'])''',
            lambda m: m.group(1) + "index.html" + m.group(3),
            new, flags=re.I,
        )
        page_path.write_text(new, encoding="utf-8")
        print(f"  {fname} rewritten ({len(new)} bytes)")

    print("[6/6] Deleting junk files and out-of-scope files ...")
    n_junk = 0
    for p in list(SITE.rglob("*")):
        if not p.is_file(): continue
        if p.name.endswith(('"', ']', ',')) or '\n' in p.name or p.name.startswith('"'):
            p.unlink(); n_junk += 1
    for extra in ["babylisteningmethod.html"]:
        f = SITE / extra
        if f.exists():
            f.unlink(); n_junk += 1
    print(f"  removed: {n_junk} junk files")

    print("\nDONE.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
