"""Sigma API helper — shells out to the sigma CLI (~/.sigma-cli/bin/sigma) for
every endpoint it exposes. The CLI owns auth entirely: no ~/.sigma-portals env
file, no /tmp token cache, no manual TTL. `sigma auth token`/`auth status` are
the only auth primitives this module touches, and the token is cached only for
the lifetime of this process (a module-level variable, not on disk) — the CLI
handles refresh on the next process.

Two endpoint families have NO CLI coverage as of the sigma-cli build checked
2026-08-25 (confirmed via `sigma api list-prefixes --refresh-spec`, not a stale
cache): report-as-code (`/v2/reports`) and plugin registration
(`/v2/plugins`). Those five functions (create_report/update_report/get_report/
register_plugin/list_plugins) fall back to a direct HTTP call, still sourcing
their bearer token from `sigma auth token` — see `_raw_call`. Drop this
fallback once the CLI adds those endpoints.
"""

import json
import re
import subprocess
import pathlib
import os
import urllib.error
import urllib.request

def _load_dotenv():
    """Load KEY=VALUE lines from the first .env found ($SIGMA_PROJECT_DIR, scripts/.env,
    the skill folder, the repo root, then the cwd). Real environment variables win."""
    here = pathlib.Path(__file__).resolve().parent
    proj = os.environ.get("SIGMA_PROJECT_DIR")
    for d in ([pathlib.Path(proj)] if proj else []) + [here, here.parent, here.parent.parent.parent, pathlib.Path.cwd()]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            return str(f)
    return None


DOTENV = _load_dotenv()

CLI = pathlib.Path(os.environ.get("SIGMA_CLI_BIN")
                    or (pathlib.Path.home() / ".sigma-cli" / "bin" / "sigma"))
# Unset -> the CLI's own default profile (`sigma auth set-default`).
PROFILE = os.environ.get("SIGMA_CLI_PROFILE") or None


def _profile_args():
    return ["-p", PROFILE] if PROFILE else []


# Org-specific ids. There are deliberately NO built-in fallbacks: a stale default
# silently pointed builds at someone else's org. Set them in .env (see
# .env.example) or the environment; `python3 scripts/doctor.py` checks them.
_REQUIRED = {
    "CONN_SNOWFLAKE": ("SIGMA_CONNECTION_ID",
                       "a WRITE-capable warehouse connection id (GET /v2/connections)"),
    "FOLDER_CLAUDE_BUILDER": ("SIGMA_FOLDER_ID",
                              "the destination folder id (My Documents/<folder>)"),
    "ORG_ID": ("SIGMA_ORG_ID", "your organization id (GET /v2/whoami)"),
}


class ConfigError(RuntimeError):
    pass


def __getattr__(name):
    """Lazy module attributes: required ids raise a helpful error only when a
    build actually needs them, and BASE is resolved on first use so the module
    imports without a CLI (tests, CI)."""
    if name in _REQUIRED:
        env, what = _REQUIRED[name]
        val = os.environ.get(env)
        if not val:
            raise ConfigError(
                "%s is not set. Add %s=<%s> to .env (copy .env.example) or export "
                "it. Run `python3 scripts/doctor.py` to check your setup." % (env, env, what))
        return val
    if name == "BASE":
        globals()["BASE"] = base = "https://" + _api_host()
        return base
    raise AttributeError(name)


def _base():
    return __getattr__("BASE") if "BASE" not in globals() else globals()["BASE"]


class SigmaError(RuntimeError):
    """Base for every error this module raises. `body` holds the raw JSON text
    the CLI (or, for the two unsupported endpoint families, the HTTP response)
    printed — existing call sites do `json.loads(exc.body)`, so this stays a
    string, not a parsed dict."""

    def __init__(self, status, body, url):
        self.status = status
        self.body = body
        self.url = url
        super().__init__("HTTP %s on %s\n%s" % (status, url, body))


class SigmaAPIError(SigmaError):
    """CLI exit 1 — Sigma returned an error response."""


class SigmaAuthError(SigmaError):
    """CLI exit 2 — credentials missing or invalid (or the CLI itself is
    missing/unauthenticated — see _require_cli / _api_host)."""


class SigmaValidationError(SigmaError):
    """CLI exit 3 — bad arguments/input (includes our own malformed --json)."""


class SigmaNetworkError(SigmaError):
    """CLI exit 4 — transport/DNS failure."""


_EXIT_ERRORS = {1: SigmaAPIError, 2: SigmaAuthError,
                3: SigmaValidationError, 4: SigmaNetworkError}


def _status_from_body(text, exit_code):
    """CLI API-error bodies carry a real HTTP `code`; the other exit codes
    don't map to one, so synthesize something call sites can still branch on."""
    try:
        code = json.loads(text).get("code")
        if isinstance(code, int):
            return code
    except (ValueError, AttributeError, TypeError):
        pass
    return {2: 401, 3: 400, 4: 599}.get(exit_code, 500)


def _require_cli():
    if not CLI.exists():
        raise SigmaAuthError(
            0, "sigma CLI not found at %s (set SIGMA_CLI_BIN to override)" % CLI,
            str(CLI))


def _run(args, url_for_error):
    """Run `sigma -p PROFILE api <args>`; return parsed stdout JSON on success."""
    _require_cli()
    proc = subprocess.run([str(CLI), *_profile_args(), "api", *args],
                           capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        err_cls = _EXIT_ERRORS.get(proc.returncode, SigmaAPIError)
        raise err_cls(_status_from_body(proc.stdout, proc.returncode),
                      proc.stdout, url_for_error)
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _j(obj):
    return json.dumps(obj)


_token_cache = None


def token():
    """Bearer token from the CLI, cached in memory for this process only — no
    disk cache, no TTL. Shelling out per call is too many subprocesses for a
    build that fires dozens of requests; a stale in-process token just means
    the *next* process re-fetches, which the CLI already handles."""
    global _token_cache
    if _token_cache is None:
        _require_cli()
        proc = subprocess.run([str(CLI), *_profile_args(), "auth", "token"],
                              capture_output=True, text=True, timeout=40)
        if proc.returncode != 0:
            raise SigmaAuthError(401, proc.stdout or proc.stderr,
                                 "sigma auth token -p %s" % (PROFILE or "<default>"))
        _token_cache = proc.stdout.strip()
    return _token_cache


def _api_host():
    _require_cli()
    proc = subprocess.run([str(CLI), *_profile_args(), "auth", "status"],
                          capture_output=True, text=True, timeout=40)
    # `auth status` writes its human-readable report to stderr, not stdout.
    combined = proc.stdout + proc.stderr
    m = re.search(r"API host:\s*(\S+)", combined)
    if proc.returncode != 0 or not m:
        raise SigmaAuthError(
            401,
            "sigma CLI profile %r is not authenticated (or is missing).\n"
            "Run: sigma auth login -p %s\n\n--- sigma auth status output ---\n%s"
            % (PROFILE or "<name>", PROFILE or "<name>", combined.strip()),
            "sigma auth status -p %s" % (PROFILE or "<default>"))
    return m.group(1)


# ---------------------------------------------------------------- workbooks


def _body(spec, dry_run=False):
    """Build a /v2/workbooks (or /v2/reports) request body from a builder SPEC.

    Builders still produce the historic ``{"name", "folderId", "document": {...}}``
    envelope; the content endpoints (official sigma-agent-skills v1.0.0) want the
    same payload under ``contents``. Accept either key so no builder has to
    change. ``document``/``contents`` is passed through untouched -- the flat
    ``elements`` + ``layout`` XML shape is already what the builders emit.
    """
    body = {k: v for k, v in spec.items() if k not in ("document", "contents")}
    contents = spec["contents"] if "contents" in spec else spec["document"]
    contents = dict(contents)
    contents.setdefault("schemaVersion", 1)
    contents.setdefault("kind", "workbook")
    if "themeOverrides" in contents or "themeName" in contents:
        contents = dict(contents)  # themeName/themeOverrides -> settings.theme
        theme = {}
        if "themeName" in contents:
            theme["name"] = contents.pop("themeName")
        if "themeOverrides" in contents:
            theme["overrides"] = contents.pop("themeOverrides")
        settings = dict(contents.get("settings", {}))
        settings["theme"] = dict(settings.get("theme", {}), **theme)
        contents["settings"] = settings
    if "themeOverrides" in contents or "themeName" in contents:
        contents = dict(contents)  # themeName/themeOverrides -> settings.theme
        theme = {}
        if "themeName" in contents:
            theme["name"] = contents.pop("themeName")
        if "themeOverrides" in contents:
            theme["overrides"] = contents.pop("themeOverrides")
        settings = dict(contents.get("settings", {}))
        settings["theme"] = dict(settings.get("theme", {}), **theme)
        contents["settings"] = settings
    # Elements are no longer nested in pages: hoist any legacy pages[].elements
    # into the flat contents.elements array (layout XML carries placement).
    if any("elements" in p for p in contents.get("pages", [])):
        contents = dict(contents)
        flat = list(contents.get("elements", []))
        pages = []
        for p in contents["pages"]:
            p = dict(p)
            flat += p.pop("elements", [])
            pages.append(p)
        overlays = list(contents.get("overlays", []))
        keep = []
        for p in pages:  # legacy modal/drawer "pages" are overlays now
            (overlays if p.get("type") in ("modal", "drawer") else keep).append(p)
        contents["elements"], contents["pages"] = flat, keep
        if overlays:
            contents["overlays"] = overlays
    body["contents"] = contents
    if dry_run:
        body["dryRun"] = True
    return body


def verify_workbook(spec):
    """Dry-run create (POST /v2/workbooks with dryRun). Nothing is persisted.
    Returns {"valid": bool, "errors": [...], "warnings": [...]}; raises
    SigmaAPIError on a 4xx, as the legacy /spec/verify did."""
    return _raw_call("POST", "/v2/workbooks", _body(spec, dry_run=True))


def create_workbook(spec):
    """POST /v2/workbooks with ``contents``. Response carries ``workbookId``.
    NB: a body without ``contents`` silently creates a BLANK workbook."""
    return _raw_call("POST", "/v2/workbooks", _body(spec))


def update_workbook(workbook_id, spec, document_version=None):
    """PUT /v2/workbooks/{id}/contents -- contents-only (name/folderId are
    ignored; rename/move with PUT /v2/files/{id}). Pass ``document_version``
    for an optimistic-concurrency check, omit for last-write-wins."""
    body = {"contents": _body(spec)["contents"]}
    if document_version is not None:
        body["documentVersion"] = document_version
    return _raw_call("PUT", "/v2/workbooks/%s/contents" % workbook_id, body)


def get_workbook(workbook_id):
    """GET /v2/workbooks/{id}?includeContents=true. The legacy ``document`` key
    is aliased to ``contents`` so older callers keep working."""
    r = _raw_call("GET", "/v2/workbooks/%s?includeContents=true" % workbook_id)
    if isinstance(r, dict) and "contents" in r:
        r.setdefault("document", r["contents"])
    return r


def get_workbook_meta(workbook_id):
    # Cheap: no spec body, just latestVersion/updatedAt/updatedBy.
    return _run(["workbooks", "get", "--params", _j({"workbookId": workbook_id})],
                "/v2/workbooks/%s" % workbook_id)


# ------------------------------------------------------- generic call() shim
#
# The CLI has no arbitrary-path escape hatch (it's an OpenAPI-operation tree,
# not a raw method+path client), so this only covers the exact (method, path)
# pairs the codebase actually calls today: qa_pg1.py's clone-and-render dance,
# and shot_report.py's PDF export kickoff. Add a route here if a new one shows
# up — don't widen this into a real generic client.

def call(method, path, body=None, accept="application/json", retry_auth=True):
    m = re.match(r"^/v2/workbooks/([^/]+)/(?:spec|contents)$", path)
    if method == "GET" and m:
        return get_workbook(m.group(1))
    if method == "POST" and path == "/v2/workbooks":
        return _run(["workbooks", "create", "--json", _j(body)], path)
    m = re.match(r"^/v2/files/([^/]+)$", path)
    if method == "DELETE" and m:
        return _run(["files", "delete", "--params", _j({"inodeId": m.group(1)})], path)
    m = re.match(r"^/v2/reports/([^/]+)/export$", path)
    if method == "POST" and m:
        return _run(["reports", "export",
                     "--params", _j({"reportId": m.group(1)}), "--json", _j(body)], path)
    # shot.py's page enumeration -- it renders one PNG per page, so it needs
    # the page list before it can export anything.
    m = re.match(r"^/v2/workbooks/([^/]+)/pages$", path)
    if method == "GET" and m:
        return _run(["workbooks", "pages", "list",
                     "--params", _j({"workbookId": m.group(1)})], path)
    m = re.match(r"^/v2/reports/([^/]+)/pages$", path)
    if method == "GET" and m:
        return _run(["reports", "pages", "list",
                     "--params", _j({"reportId": m.group(1)})], path)
    m = re.match(r"^/v2/workbooks/([^/]+)/export$", path)
    if method == "POST" and m:
        return _run(["workbooks", "export",
                     "--params", _j({"workbookId": m.group(1)}),
                     "--json", _j(body)], path)
    raise NotImplementedError(
        "sigmaapi.call() has no CLI route for %s %s. The sigma CLI has no "
        "generic arbitrary-path escape hatch, so call() only covers the paths "
        "this codebase actually uses — add a route above." % (method, path))


# ------------------------------------------------------------------ reports
#
# No CLI coverage — /v2/reports isn't in the CLI's OpenAPI surface at all
# (checked with --refresh-spec, 2026-08-25). Direct HTTP, CLI-sourced token.


def _raw_call(method, path, body=None):
    url = _base() + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": "Bearer " + token(), "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raise SigmaAPIError(exc.code, exc.read().decode(), url) from None
    except urllib.error.URLError as exc:
        raise SigmaNetworkError(0, str(exc.reason), url) from None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def verify_report(spec):
    """Dry-run create (POST /v2/reports with dryRun; ``contents`` required)."""
    return _raw_call("POST", "/v2/reports", _body(spec, dry_run=True))


def create_report(spec):
    return _raw_call("POST", "/v2/reports", _body(spec))


def update_report(report_id, spec, document_version=None):
    body = {"contents": _body(spec)["contents"]}
    if document_version is not None:
        body["documentVersion"] = document_version
    return _raw_call("PUT", "/v2/reports/%s/contents" % report_id, body)


def get_report(report_id):
    r = _raw_call("GET", "/v2/reports/%s?includeContents=true" % report_id)
    if isinstance(r, dict) and "contents" in r:
        r.setdefault("document", r["contents"])
    return r


# ------------------------------------------------------------------ plugins
#
# No CLI coverage — no `plugins` resource exists in the CLI at all.


def register_plugin(name, url, description=""):
    return _raw_call("POST", "/v2/plugins",
                     {"name": name, "url": url, "description": description,
                      "type": "element"})


def list_plugins():
    return _raw_call("GET", "/v2/plugins")


def describe(obj, limit=4000):
    """Pretty-print helper for poking at responses from the shell."""
    text = json.dumps(obj, indent=2) if not isinstance(obj, str) else obj
    return text[:limit]


if __name__ == "__main__":
    print("token ok, len", len(token()))
    print(describe(_run(["whoami", "get"], "/v2/whoami")))
