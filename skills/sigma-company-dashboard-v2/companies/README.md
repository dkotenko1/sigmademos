# companies/

One file per customer. `scripts/company.py` loads every `companies/*.py` (except
names starting with `_`) at import time, in this order, *after* all shared helpers
and registries exist — so a customer file only contains that customer.

## What a customer file contains

The same pieces the built-in companies define inside `company.py`:

```python
MYCO = {"key": "myco", "name": "MyCo", "title": "...", "palette": {...},
        "products": [...], "subs": {...}, "logo_domain": "myco.com",
        "insight_mode": "formula"}          # default; "ai" opts into CallText/Cortex
FOOTPRINTS["myco"] = [...]
LABELS["myco"]     = {...}
SEGMENTS["myco"]   = {...}
VOCAB["myco"]      = {...}
POP["myco"]        = {...}
PLUGINS["myco"]    = {"hero": "<registered HOSTED plugin id>", "hero_label": "..."}
COMPANIES["myco"]  = MYCO
```

Copy the block of the closest existing company (search `company.py` for e.g.
`ARCH = {`) as the starting point. Optional statement data goes in
`_STMT_SOURCES["myco"]` / `STATEMENTS["myco"]`.

## Rules

* Use a **hosted** plugin id (GitHub Pages), never one whose URL is `localhost`.
  `python3 scripts/doctor.py myco` fails the build if it is.
* Put logo files in `assets/<prefix>_logo_white.datauri.txt` and SQL in `sql/`.
* Run `python3 scripts/demo.py myco --dry-run` before creating anything.
* To keep customer files outside the repo, set `COMPANIES_DIR=/path/to/dir`.
