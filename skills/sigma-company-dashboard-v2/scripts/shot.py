"""Render a Sigma workbook or report to PNG/PDF headlessly.

This is the loop that makes a code-built dashboard self-verifying: build -> render
-> actually look at it -> fix. It uses the same async export/download pair that
already backs CSV export.

    POST {base}/v2/workbooks/{id}/export   {"format": {"type": "png"}}   -> queryId
    GET  {base}/v2/query/{queryId}/download                              -> bytes

Notes learned the hard way:
  * Poll `/v2/query/{queryId}/download`, NOT `/v2/workbooks/.../export/{queryId}`.
  * A zero-byte 200 means "not ready", not "failed" — sleep and retry.
  * Send `Accept: */*`; the payload is binary.
  * `pageId` scopes to one page, `elementId` to a single tile. PDF requires an
    elementId; PNG does not.

Usage:
    python3 shot.py workbook <workbookId> [outdir]      # every page
    python3 shot.py report   <reportId>   [outdir]
    python3 shot.py compare  <dirA> <dirB> [out.html]   # side-by-side contact sheet

Env: SHOT_MAX_WAIT (seconds per page, default 300).
"""

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

import sigmaapi as S

POLL_SECONDS = 3
# SHOT_MAX_WAIT seconds per page (default 300; was a fixed 180, which timed out
# heavy pages). A page that still times out is retried once with a fresh export.
MAX_WAIT = int(os.environ.get("SHOT_MAX_WAIT", "300"))


def _req(method, path, body=None, accept="application/json"):
    url = S.BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": "Bearer " + S.token(), "Accept": accept}
    if data:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def start_export(kind, doc_id, fmt="png", page_id=None, element_id=None):
    body = {"format": {"type": fmt}}
    if page_id:
        body["pageId"] = page_id
    if element_id:
        body["elementId"] = element_id
    path = "/v2/%s/%s/export" % ("workbooks" if kind == "workbook" else "reports", doc_id)
    with urllib.request.urlopen(_req("POST", path, body), timeout=90) as r:
        return json.loads(r.read().decode())


def download(query_id, out_path):
    """Poll until the render is ready. Zero bytes = still rendering."""
    waited = 0
    while waited < MAX_WAIT:
        try:
            with urllib.request.urlopen(
                    _req("GET", "/v2/query/%s/download" % query_id, accept="*/*"),
                    timeout=90) as r:
                blob = r.read()
            if blob:
                pathlib.Path(out_path).write_bytes(blob)
                return len(blob)
        except urllib.error.HTTPError as exc:
            # 404/409/425 = not ready yet; 5xx = the gateway gave up waiting on a
            # render that is still running. Both are retryable.
            if exc.code not in (404, 409, 425, 500, 502, 503, 504):
                raise
        except Exception:
            pass  # transient socket/read timeout while the render is in flight
        time.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    return 0


def pages(kind, doc_id):
    path = "/v2/%s/%s/pages" % ("workbooks" if kind == "workbook" else "reports", doc_id)
    try:
        r = S.call("GET", path)
        return [(p.get("pageId") or p.get("id"), p.get("name")) for p in r.get("entries", [])]
    except S.SigmaError:
        return []


def compare(dir_a, dir_b, out_html):
    """Side-by-side contact sheet of two shot folders (matching file names) as one
    self-contained HTML file -- no image libraries needed."""
    import base64
    a, b = pathlib.Path(dir_a), pathlib.Path(dir_b)
    names = sorted({p.name for p in a.glob("*.png")} | {p.name for p in b.glob("*.png")})

    def tag(d, n):
        f = d / n
        if not f.exists():
            return "<div class=miss>missing</div>"
        return '<img src="data:image/png;base64,%s">' % base64.b64encode(f.read_bytes()).decode()
    rows = "".join("<h3>%s</h3><div class=row><div><b>%s</b>%s</div><div><b>%s</b>%s</div></div>"
                   % (n, a.name, tag(a, n), b.name, tag(b, n)) for n in names)
    pathlib.Path(out_html).write_text(
        "<!doctype html><meta charset=utf-8><title>shot compare</title><style>"
        "body{font:14px system-ui;margin:16px}.row{display:flex;gap:12px;align-items:flex-start}"
        ".row>div{flex:1;min-width:0}img{width:100%;border:1px solid #ccc}"
        ".miss{padding:40px;background:#fee;color:#a00}</style>" + rows)
    print("wrote %s (%d pages)" % (out_html, len(names)))


def main():
    if sys.argv[1] == "compare":
        compare(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "compare.html")
        return
    kind = sys.argv[1]
    doc_id = sys.argv[2]
    outdir = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "../shots")
    outdir.mkdir(parents=True, exist_ok=True)

    pgs = pages(kind, doc_id)
    print("pages:", pgs or "(none returned — exporting whole document)")

    targets = [(pid, name) for pid, name in pgs] or [(None, "all")]
    for pid, name in targets:
        slug = (name or pid or "page").lower().replace(" ", "-").replace("/", "-")
        out = outdir / ("%s-%s.png" % (kind, slug))
        n = 0
        for attempt in (1, 2):
            try:
                job = start_export(kind, doc_id, "png", page_id=pid)
            except urllib.error.HTTPError as exc:
                print("  ✗ %-28s export failed %s %s" % (slug, exc.code, exc.read()[:160]))
                break
            qid = job.get("queryId")
            if not qid:
                print("  ✗ %-28s no queryId in %s" % (slug, job))
                break
            n = download(qid, out)
            if n:
                break
            if attempt == 1:
                print("  … %-28s timed out after %ds, retrying once" % (slug, MAX_WAIT))
        if n:
            print("  ✓ %-28s %d bytes -> %s" % (slug, n, out))
        elif n == 0:
            print("  ✗ %-28s timed out. Usual cause: a plugin hosted on localhost "
                  "(run `python3 scripts/doctor.py <company>`) or a very heavy page; "
                  "raise SHOT_MAX_WAIT." % slug)


if __name__ == "__main__":
    main()
