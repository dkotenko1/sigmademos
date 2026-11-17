#!/usr/bin/env python3
"""Offline self-test (no Sigma org, no CLI needed). Run in CI and before commits:

    python3 scripts/selftest.py
"""
import os
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
N = 0


def check(cond, msg):
    global N
    N += 1
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    print("ok  ", msg)


# 1. every python file compiles
repo = HERE.parent.parent.parent
bad = []
for f in repo.glob("skills/**/*.py"):
    try:
        compile(f.read_text(), str(f), "exec")
    except SyntaxError as exc:
        bad.append("%s: %s" % (f.relative_to(repo), exc))
check(not bad, "all skills/**/*.py compile%s" % ((" -- " + "; ".join(bad[:3])) if bad else ""))

# 2. sigmaapi imports with no CLI/profile and translates legacy specs
for k in ("SIGMA_CLI_PROFILE", "SIGMA_CONNECTION_ID", "SIGMA_FOLDER_ID", "SIGMA_ORG_ID"):
    os.environ.pop(k, None)
import sigmaapi as S  # noqa: E402
check(True, "sigmaapi imports without a CLI or profile")
try:
    S.CONN_SNOWFLAKE
    check(False, "unset SIGMA_CONNECTION_ID must raise ConfigError")
except S.ConfigError:
    check(True, "unset ids raise ConfigError (no stale org defaults)")
legacy = {"name": "n", "folderId": "f", "document": {
    "themeOverrides": {"a": 1},
    "pages": [{"id": "p", "name": "P", "elements": [{"id": "e1"}]},
              {"id": "m", "name": "M", "type": "modal", "modal": {}, "elements": [{"id": "e2"}]}]}}
b = S._body(legacy, dry_run=True)
c = b["contents"]
check(b["dryRun"] is True and "document" not in b, "_body: document -> contents, dryRun flag")
check([e["id"] for e in c["elements"]] == ["e1", "e2"], "_body: pages[].elements hoisted to flat elements")
check([p["id"] for p in c["pages"]] == ["p"] and [o["id"] for o in c["overlays"]] == ["m"],
      "_body: modal pages become overlays")
check(c["settings"]["theme"]["overrides"] == {"a": 1} and c["kind"] == "workbook",
      "_body: themeOverrides -> settings.theme, kind defaulted")

# 3. company registry
import company as CO  # noqa: E402
check(len(CO.COMPANIES) >= 10, "company registry loads (%d companies)" % len(CO.COMPANIES))
for key, cfg in CO.COMPANIES.items():
    assert cfg.get("key") == key and cfg.get("name"), "%s: key/name mismatch" % key
check(True, "every company has matching key + name")
src = (HERE / "company.py").read_text()
check(not re.search(r"https?://(localhost|127\.0\.0\.1)", src),
      "company.py contains no localhost URLs")
pid = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
for key, pl in CO.PLUGINS.items():
    for slot, v in pl.items():
        if slot in ("hero", "ticker") and v is not None:
            assert isinstance(v, str) and pid.match(v), "%s.%s is not a plugin id" % (key, slot)
check(True, "PLUGINS hero/ticker ids are well-formed")

# 4. external companies/ loader
with tempfile.TemporaryDirectory() as d:
    pathlib.Path(d, "clone.py").write_text('COMPANIES["clone"] = dict(COMPANIES["arch"], key="clone", name="Clone")\n')
    pathlib.Path(d, "_skip.py").write_text("raise SystemExit('must not load')\n")
    os.environ["COMPANIES_DIR"] = d
    import importlib
    importlib.reload(CO)
    check(CO.LOADED_EXTERNAL == ["clone.py"] and "clone" in CO.COMPANIES,
          "companies/ loader registers external files and skips _*.py")
    os.environ.pop("COMPANIES_DIR")

print("\nselftest: %d checks passed" % N)
