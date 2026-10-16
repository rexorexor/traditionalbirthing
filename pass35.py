#!/usr/bin/env python3
"""Pass 3.5: normalize every CSS url() to a root-absolute local path.

CSS url() resolves against the CSS file's own URL, so the only unambiguous
form for a multi-depth tree is root-absolute: /universal/fonts/x.woff.
HTML pages sit at the docroot and are already verified clean; leave them.

Resolution rules (no cleverness, resolve then check):
  https?://host/path   host in mirror set -> /path (local), else leave external
  //host/path          -> https://host/path, same as above
  /universal/...       -> already root-absolute, normalize host by prefix
  /content/v...        -> images.squarespace-cdn.com
  /static/...          -> static1.squarespace.com
  /website-component-definition/... -> definitions.sqspcdn.com
  ../x or bare x       -> resolve against the CSS file's local dir on disk,
                          then express relative to SITE -> prefix "/"

Output: url("/universal/fonts/x.woff") etc.  ?query variants are already on
disk as __query filenames; keep them that way.
"""
import os
import re
import subprocess
import posixpath
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"

MIRROR_HOSTS = {
    "assets.squarespace.com",
    "images.squarespace-cdn.com",
    "definitions.sqspcdn.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "elfsightcdn.com",
}
PREFIX_HOSTS = [
    ("/website-component-definition/", "definitions.sqspcdn.com"),
    ("/content/v", "images.squarespace-cdn.com"),
    ("/static/", "static1.squarespace.com"),
]

URL_PAREN_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)


def host_for_local_path(path: str) -> str:
    for prefix, host in PREFIX_HOSTS:
        if path.startswith(prefix):
            return host
    return "assets.squarespace.com"


def to_root_absolute(u: str, css_file: Path):
    """Return local root-absolute path string (leading /) or None to leave as-is."""
    u = u.strip().strip(' \t"\'')
    if not u:
        return None
    lo = u.lower()
    if lo.startswith(("data:", "#", "%23", "javascript:", "mailto:", "tel:", "sms:")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith(("http://", "https://")):
        p = urlparse(u)
        if p.netloc not in MIRROR_HOSTS:
            return None  # external, leave
        local = p.path  # keep query out; variant files are __query on disk
        if p.query:
            base, ext = posixpath.splitext(p.path.lstrip("/"))
            local = "/" + (f"{base}__{p.query}{ext}" if ext else p.path.lstrip("/") + f"__{p.query}")
        return local
    if u.startswith("/"):
        return u
    # relative -> resolve against the CSS file's real directory, then rel to SITE
    target = (css_file.parent / u).resolve()
    try:
        rel = target.relative_to(SITE).as_posix()
    except ValueError:
        return None
    return "/" + rel


def main():
    css_files = [p for p in SITE.rglob("*") if p.is_file() and p.suffix == ".css"]
    print(f"CSS files: {len(css_files)}")
    changed = 0
    targets = set()
    for css in css_files:
        text = css.read_text(encoding="utf-8", errors="replace")
        new = text

        def repl(m):
            q, u = m.group(1), m.group(2)
            ra = to_root_absolute(u, css)
            if ra is None:
                return m.group(0)
            targets.add(ra.lstrip("/"))
            return f"url({q}{ra}{q})"

        new = URL_PAREN_RE.sub(repl, text)
        if new != text:
            css.write_text(new, encoding="utf-8")
            changed += 1
    print(f"rewritten: {changed}")
    print(f"distinct root-absolute targets: {len(targets)}")

    # fetch any target missing on disk via curl (urllib fails on akamai cert)
    missing = [t for t in sorted(targets) if not (SITE / t).exists() or (SITE / t).stat().st_size == 0]
    print(f"missing on disk: {len(missing)}")
    fetched = failed = 0
    for t in missing:
        src = f"https://{host_for_local_path('/' + t)}/{t}"
        dest = SITE / t
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["curl", "-sS", "--max-time", "30", "-A",
                            "Mozilla/5.0 (compatible; archive-fetch/3.5)",
                            "-o", str(dest), "-w", "%{http_code}", src],
                           capture_output=True, text=True)
        code = r.stdout.strip()
        ok = code == "200" and dest.exists() and dest.stat().st_size > 0
        if ok:
            fetched += 1
        else:
            failed += 1
            print(f"  FAIL {code} {src[:110]}")
        import time
        time.sleep(0.1)
    print(f"fetched: {fetched}, failed: {failed}")

    # write the target list for the verifier
    (HERE / "pass35_targets.txt").write_text("\n".join(sorted(targets)), encoding="utf-8")
    print("targets written to pass35_targets.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
