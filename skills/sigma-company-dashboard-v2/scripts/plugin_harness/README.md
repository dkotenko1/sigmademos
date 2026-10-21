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
