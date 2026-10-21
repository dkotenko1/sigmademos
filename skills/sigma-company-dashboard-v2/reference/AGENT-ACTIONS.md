# Agent actions and workflows

What the generator builds, what was verified live, and what bit us. Written
after testing on the Arch Insurance workbook (paperbricks, 2026-10-21). Read the
official `sigma-skills:sigma-workbooks` `agents.md` first (see
`COMPANION-SKILLS.md`); this file only records what is specific to this
generator.

## What gets built

Capabilities are split per agent (Analyze / Configure / Navigate / Act), as the
official guidance recommends, instead of one agent that sees and does everything.

| Agent | Where | Capabilities |
|---|---|---|
| Copilot (`ag-book`) | Page 1 rail | Analyze the book; Configure (focus a product); Navigate (open the modeler page, open the product drawer) |
| Scenario Copilot (`ag-scenario`) | Page 2 rail | Configure (shock, switch scenario); Act (create scenario, set drivers for one line, set growth on every row, submit, approve); Navigate (to proposals) |
| Advisor (`ag-advisor`) | Page 1 rail, under the Copilot | Analyze the hero table; Act (save a remediation proposal); Navigate (to the modeler page). Built only when the company config has an `advisor` block and a `hero_table` |

Supporting elements: a visible **Scenario audit log** (when, scenario, status,
by, via Button/Agent, projected value at the time, note) written by the
Submit/Approve buttons and the Copilot alike, and a **Remediation proposals**
table written by the Advisor and readable by the Scenario Copilot.

Every tool that writes rows carries `requiresApproval: true`. Every agent lists
its write target in `dataSources` and is instructed to query it after the
confirmation is answered (approved OR skipped) before saying what changed.

### Config

```python
"advisor": {
    "name": "Appetite Advisor",
    "description": "...",
    "instructions": "domain role and scope; the generator appends the working rules",
}
```

## Verified live (draft mode, signed-in browser)

- Approval card appears for each write tool, names the target table and shows
  the agent-supplied values. Skip writes nothing; Approve runs the effect.
- A two-step tool (insert a scenario row, then set the active-scenario control)
  runs as one approval, and the same `agent-input` name feeds both steps.
- The per-line driver update works (Cyber +15% growth, +5 bps rate, +150 bps
  trend moved projected premium after losses by +$76M for that line).
- The Advisor's generated greeting reads the bound hero table (11 rows) and
  quotes real utilization figures.
- After a write, the Scenario Copilot queried Assumptions, Book and the audit
  log and reported what was actually there.

## Defects found by running it (all would have shipped past `verify`)

1. **Single-row `update-rows` fails on the linked assumptions grid.**
   `Unique row <column> not in update row definition`: the row identity
   includes the pivot value columns, which the agent cannot supply. Fix used
   here: the tool first sets a hidden `AgentLine` control, then updates with
   `whichRows: {type: formula, formula: "[Product] = [AgentLine] and
   [Scenario] = [scenarioSelect]"}`.
2. **Published view blocks every input-table write**:
   `Edits can only be made in draft mode`. This hits the Submit/Approve buttons
   and the existing New scenario flow too, not only agents. In the editor the
   spec-created tables show "Editable in draft" whether the spec says
   `inputMode: view` or `explore`; the per-table "Data entry permission"
   dropdown (draft / published restricted / published all access levels) is
   not carried by the API. **Demo from the editor in draft mode, or set the
   permission per table in the UI.** Not verified: that changing it in the UI
   makes published writes work, or that it survives an API `update`.
3. **Discarding a draft does not remove rows already written.** Input-table
   data lives in the warehouse. Clear test data with the workbook's own Reset
   scenarios button, in draft.
4. **Baseline scales with the number of scenario rows.** The pivot groups by
   product only and cross-joins the scenarios table, so two scenario rows
   double the baseline. Duplicate test scenarios made the dashboard read
   $5.9B instead of $2.97B until reset. Keep one scenario row per what-if, or
   fix the pivot grain in a follow-up.
5. A scenario agent existed in the spec but had **no chat element**, so nobody
   could reach it. Page 2 now has a rail for it.
6. Agent instruction strings built with `%` formatting must escape literal
   percent signs (`95%%`).

## Plugin data cannot be verified headlessly

PNG export never delivers plugin data, and in the embedded browser pane the
plugin tile fell back to its sample data (the Tendo plugin did not render at
all there). The Arch plugin now says why it is showing sample data (SDK not
loaded / no source configured / no data after 6s). Check the live binding in a
normal browser.
