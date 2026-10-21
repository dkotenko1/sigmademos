# Plugin host simulator

Headless exports and unauthenticated browsers never run a plugin's data
subscription, so a plugin can look fine and still never bind. This page plays
the host half of the SDK's postMessage protocol (init, config, element data) so
a plugin's data path can be tested locally.

```bash
cd scripts/plugin_harness
cp /path/to/plugin/index.html plugin.html     # keep the unpkg script tags, or point
                                              # them at local copies of React + the SDK
python3 -m http.server 8731 &                 # then open http://localhost:8731/harness.html
```

Edit `COLS` and the `init` config in `harness.html` to match the plugin's
editor-panel keys. You should see `init`, `config:inspector`, `subscribe:data`
in the log and the plugin rendering rows with no sample-data chip.

## Test every plugin at once

```bash
cd scripts/plugin_harness
PLUGINS_DIR=/path/to/plugins/plugins python3 serve_all.py &     # serves on :8732
# open http://127.0.0.1:8732/all_plugins.html?wait=5500&shape=object
```

For each plugin it answers the editor-panel request with matching fake columns,
then checks the plugin initialised, asked for data, and rendered it instead of
sample data. `?only=a,b` runs a subset, `?shape=string` passes the source as a
bare id, `?orig=1` loads the committed (git HEAD) version for before/after.
Keep the pane/tab visible while it runs: a hidden tab throttles timers.
`react.js` and `sdk.js` are the pinned React 18.3.1 and SDK 1.3.2 UMD builds.
