# Companion skills: always load the official Sigma skills

This generator produces workbook and report specs. The shapes it emits are only
as current as the API, so every build session should also have the **official
Sigma skills** loaded and should consult them before touching anything the
generator does not already cover.

Source of truth: <https://github.com/sigmacomputing/sigma-agent-skills>
(Claude Code plugin `sigma-computing@sigma-computing`, skills prefixed
`sigma-skills:`; v0.3.0 as of 2026-09-16).

| Skill | Use it for |
|---|---|
| `sigma-skills:sigma-workbooks` | Workbook spec shapes: elements, controls, input tables, **agents**, layout, formulas. Read `reference/specification/agents.md` and `input-tables.md` before changing agents or writeback. |
| `sigma-skills:sigma-reports` | Report-as-code (the PDF statement): schema, layout, validation, convert-from-workbook. |
| `sigma-skills:sigma-cli` | Driving the API from the `sigma` CLI (`workbooks spec`, `export`, `pages`, tags, deployments). |
| `sigma-skills:sigma-data-models` | Data models, metrics, relationships, materialization. |
| `sigma-skills:sigma-api` | Auth, tokens, host selection, 401/403 triage. |

## The rule

1. Run `scripts/preflight.sh` at the start of a build session. It reports
   whether the official plugin is installed and the `sigma` CLI is
   authenticated, and prints the fix commands if not.
2. Before changing agents, tools or writeback behaviour, read the official
   `agents.md` and `input-tables.md` first. They are newer than this repo's
   notes and have already corrected several earlier claims.
3. When this repo's notes and the official skills disagree, trust the official
   skill, then confirm against a live `GET` readback of a created workbook.
4. Treat `verify` as necessary but not sufficient. Create or update on a real
   org, and for anything with runtime behaviour (agents, actions, plugins)
   exercise it in a signed-in browser. Several defects in this repo were only
   visible that way (see `AGENT-ACTIONS.md`).

## Keeping current

```bash
claude plugin marketplace update sigma-computing && claude plugin update sigma-computing
```

Check the repo's `CHANGELOG.md` for new releases; it adds skills and fixes
regularly.
