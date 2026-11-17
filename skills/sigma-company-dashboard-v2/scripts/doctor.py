#!/usr/bin/env python3
"""Preflight for a demo build. Run before building; fixes are printed inline.

    python3 scripts/doctor.py                 # environment only
    python3 scripts/doctor.py arch            # + that company's config, plugins, assets
    COMPANY=arch python3 scripts/doctor.py

Exit status is 1 if any hard check fails (warnings do not fail the run).
Checks: python, sigma CLI + auth, the three ids in .env, connection is
write-capable, folder exists, company config present, every registered plugin
used by the company is HOSTED (never localhost), and the generator can
assemble the spec locally (catches missing logo/SQL assets before any API call).
"""
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FAILS = 0


def ok(msg):
    print("  ✓ " + msg)


def warn(msg, fix=""):
    print("  ! " + msg + (("\n      fix: " + fix) if fix else ""))


def fail(msg, fix=""):
    global FAILS
    FAILS += 1
    print("  ✗ " + msg + (("\n      fix: " + fix) if fix else ""))


def section(t):
    print("\n== " + t)


def main():
    company = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("COMPANY"))
    section("python")
    if sys.version_info >= (3, 8):
        ok("python %d.%d" % sys.version_info[:2])
    else:
        fail("python %d.%d is too old" % sys.version_info[:2], "use python 3.8+")

    section("sigma CLI")
    try:
        import sigmaapi as S
    except Exception as exc:  # noqa: BLE001
        fail("could not import sigmaapi: %s" % exc)
        return finish()
    if S.DOTENV:
        ok("loaded %s" % S.DOTENV)
    else:
        warn(".env not found", "cp .env.example .env and fill it in")
    if not S.CLI.exists():
        fail("sigma CLI not found at %s" % S.CLI,
             "install it, or set SIGMA_CLI_BIN (see the sigma-computing:sigma-cli skill)")
        return finish()
    ok("CLI at %s" % S.CLI)
    try:
        host = S._api_host()
        ok("profile %s authenticated (%s)" % (S.PROFILE or "<default>", host))
    except Exception as exc:  # noqa: BLE001
        fail("profile %s is not authenticated" % (S.PROFILE or "<default>"),
             "sigma auth login%s" % ((" -p " + S.PROFILE) if S.PROFILE else ""))
        print("      " + str(exc).splitlines()[0][:140])
        return finish()

    section("ids (.env)")
    ids = {}
    for attr, env in (("CONN_SNOWFLAKE", "SIGMA_CONNECTION_ID"),
                      ("FOLDER_CLAUDE_BUILDER", "SIGMA_FOLDER_ID"),
                      ("ORG_ID", "SIGMA_ORG_ID")):
        try:
            ids[attr] = getattr(S, attr)
            ok("%s set" % env)
        except S.ConfigError as exc:
            (warn if attr == "ORG_ID" else fail)(str(exc).split(". Run")[0])

    try:
        who = S._raw_call("GET", "/v2/whoami")
        if ids.get("ORG_ID") and who.get("organizationId") != ids["ORG_ID"]:
            warn("SIGMA_ORG_ID (%s) differs from the authenticated org (%s)"
                 % (ids["ORG_ID"][:8], who.get("organizationId", "?")[:8]),
                 "you may be pointed at the wrong org/profile")
    except Exception:  # noqa: BLE001
        pass

    if "CONN_SNOWFLAKE" in ids:
        try:
            conns = S._raw_call("GET", "/v2/connections?limit=200")
            conns = conns.get("entries", conns) if isinstance(conns, dict) else conns
            c = next((x for x in conns if x.get("connectionId") == ids["CONN_SNOWFLAKE"]), None)
            if not c:
                fail("connection %s not found in this org" % ids["CONN_SNOWFLAKE"][:8],
                     "sigma api connections list")
            elif not c.get("writeAccess"):
                fail("connection %r is read-only; input tables need a write-capable one"
                     % c.get("name"))
            else:
                ok("connection %r (%s, write)" % (c.get("name"), c.get("type")))
        except Exception as exc:  # noqa: BLE001
            warn("could not list connections: %s" % str(exc).splitlines()[0][:100])
    if "FOLDER_CLAUDE_BUILDER" in ids:
        try:
            f = S._raw_call("GET", "/v2/files/%s" % ids["FOLDER_CLAUDE_BUILDER"])
            ok("folder %r (%s)" % (f.get("name"), f.get("path", "")))
        except Exception:  # noqa: BLE001
            fail("folder %s not found" % ids["FOLDER_CLAUDE_BUILDER"][:8],
                 "sigma api files list --params '{\"typeFilters\":[\"folder\"],\"limit\":200}'")

    if company:
        company_checks(S, company)
    return finish()


def company_checks(S, key):
    section("company %r" % key)
    import company as CO
    cfg = CO.COMPANIES.get(key)
    if not cfg:
        fail("no config for %r" % key,
             "known: %s. Add one in company.py or companies/%s.py" % (", ".join(sorted(CO.COMPANIES)), key))
        return
    ok("config found (%s)" % cfg.get("name", key))
    mode = cfg.get("insight_mode", "formula")
    if mode == "formula":
        ok("insight_mode formula (live formula takeaway)")
    else:
        warn("insight_mode=%r uses CallText/Cortex, which returns N/A on several orgs" % mode,
             'drop it or set "insight_mode": "formula"')

    plugs = CO.PLUGINS.get(key, {})
    try:
        reg = S._raw_call("GET", "/v2/plugins")
        reg = {p["pluginId"]: p for p in (reg.get("entries", reg) if isinstance(reg, dict) else reg)}
    except Exception as exc:  # noqa: BLE001
        reg = {}
        warn("could not list plugins: %s" % str(exc).splitlines()[0][:100])
    pid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for slot, pid in plugs.items():
        if not (isinstance(pid, str) and pid_re.match(pid)):
            continue
        p = reg.get(pid)
        if p is None:
            fail("plugin %s (%s) is not registered in this org" % (slot, pid[:8]),
                 "register it (S.register_plugin) and update PLUGINS[%r]" % key)
        elif "localhost" in p.get("url", "") or "127.0.0.1" in p.get("url", ""):
            fail("plugin %s (%s) is hosted on %s" % (slot, pid[:8], p["url"]),
                 "point PLUGINS[%r][%r] at the hosted twin; localhost hangs headless renders"
                 % (key, slot))
        else:
            ok("plugin %s -> %s" % (slot, p["url"]))

    env = dict(os.environ, COMPANY=key)
    r = subprocess.run([sys.executable, str(HERE / "build_sofi.py"), "dump"],
                       capture_output=True, text=True, env=env, cwd=str(HERE))
    if r.returncode == 0:
        ok("generator assembled the spec locally (assets + SQL present)")
    else:
        tail = (r.stderr.strip().splitlines() or ["?"])[-1][:200]
        fail("generator could not assemble the spec: %s" % tail,
             "usually a missing assets/<prefix>_logo_*.datauri.txt or sql/*.sql file")


def finish():
    print("\n" + ("doctor: all checks passed" if not FAILS else "doctor: %d check(s) failed" % FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
