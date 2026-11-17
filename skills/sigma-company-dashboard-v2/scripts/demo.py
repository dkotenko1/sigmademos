#!/usr/bin/env python3
"""One command from config to a rendered demo.

    python3 scripts/demo.py <company>                      # doctor -> verify -> create -> screenshots
    python3 scripts/demo.py <company> --copy               # side-by-side copy; tracked ids untouched
    python3 scripts/demo.py <company> --update <workbookId># push to an existing workbook
    python3 scripts/demo.py <company> --dry-run            # doctor + verify only
    python3 scripts/demo.py <company> --surfaces command,model --report --no-shots

Steps (each stops the run on failure, with the fix printed by the step itself):
  1. doctor.py <company>      environment, ids, plugins, assets
  2. build_sofi.py verify     server-side dry run (nothing persisted)
  3. build_sofi.py create|update
       --copy / --update on a non-tracked workbook run with NO_STATE=1 so
       specs/workbook_id.txt and the edited-in-UI guard state are not overwritten
  4. build_statement.py create   (only with --report; companies with a statement)
  5. shot.py workbook <id> shots/<company>[-copy]/   (skip with --no-shots)

Prints the workbook URL(s) at the end.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent


def run(label, args, env, check=True):
    print("\n▶ %s" % label)
    r = subprocess.run([sys.executable] + args, cwd=str(HERE), env=env)
    if check and r.returncode != 0:
        print("\n✗ stopped: %s failed (exit %d)" % (label, r.returncode))
        sys.exit(r.returncode)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company")
    ap.add_argument("--surfaces", help="command | command,model | command,cohort | command,model,cohort")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--copy", action="store_true", help="create a NEW workbook without touching tracked state")
    g.add_argument("--update", metavar="WORKBOOK_ID", help="update this workbook in place")
    ap.add_argument("--report", action="store_true", help="also create the PDF statement report")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--skip-doctor", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="doctor + verify only; create nothing")
    a = ap.parse_args()

    env = dict(os.environ, COMPANY=a.company)
    if a.surfaces:
        env["SURFACES"] = a.surfaces

    # Is this the tracked workbook? Updating it keeps the guard; anything else must not.
    tracked = None
    tf = SKILL / "specs" / "workbook_id.txt"
    if tf.exists():
        tracked = tf.read_text().strip()
    side = a.copy or (a.update and a.update != tracked)
    if side:
        env["NO_STATE"] = "1"
    else:
        env.pop("NO_STATE", None)

    if not a.skip_doctor:
        run("doctor", ["doctor.py", a.company], env)
    run("verify (dry run, nothing persisted)", ["build_sofi.py", "verify"], env)
    if a.dry_run:
        print("\n\u2713 dry run complete; nothing was created")
        return

    if a.update:
        run("update %s" % a.update, ["build_sofi.py", "update", a.update], env)
        wid = a.update
    else:
        run("create" + (" (copy)" if a.copy else ""), ["build_sofi.py", "create"], env)
        f = SKILL / "specs" / (("workbook_id_copy_%s.txt" % a.company) if a.copy else "workbook_id.txt")
        wid = f.read_text().strip()

    if a.report:
        run("statement report", ["build_statement.py", "create"], env, check=False)

    if not a.no_shots:
        out = SKILL / "shots" / (a.company + ("-copy" if side else ""))
        run("screenshots -> %s" % out, ["shot.py", "workbook", wid, str(out)], env, check=False)

    print("\n✓ done. workbook id: %s" % wid)
    try:
        sys.path.insert(0, str(HERE))
        import sigmaapi as S
        meta = S.get_workbook_meta(wid)
        if meta.get("url"):
            print("  url: %s" % meta["url"])
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
