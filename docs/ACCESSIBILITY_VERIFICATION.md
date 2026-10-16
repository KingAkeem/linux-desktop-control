# Accessibility companion trial

Verified locally on October 16, 2026, on Ubuntu GNOME X11 with Python 3.12.
This is an isolated experiment using the system AT-SPI bindings. It does not
run or benchmark the Rust backend from `ilysenko/codex-desktop-linux`.

## Passed

- 64 automated tests, including all 36 existing input-server tests.
- Ruff's Python error checks and Git whitespace checks.
- Source distribution and wheel builds; installed-wheel MCP discovery found
  exactly two companion tools and the original seven input tools.
- Live reads in a disposable GTK fixture: exact window matching, exclusion of
  another window in the same process, password redaction, opt-in text, node and
  depth truncation, and rejection of invalid or closed targets.
- A stable passive-read run preserved focus, pointer position, Stop state,
  and client configuration. Its four reads took 0.76 to 0.99 seconds each.
  These timings describe this fixture and host only.
- The existing globally configured controller typed `Companion ready` and
  clicked the fixture button. Returned screenshots were visually inspected.
  The companion independently read back the text and `Clicks: 1`.
- Physical input during a subsequent read triggered the original Stop latch.
  The controller became inactive and rejected further typing. The companion
  still read the fixture while reporting the latched input stop.
- Byte comparisons against the reviewed beta confirmed that all seven input
  and integration modules are unchanged. Companion registration preserved all
  other client configuration, including the active input-server entry.

## Limits

Some passive invariance checks were inconclusive because the shared desktop
changed during the read. A separate stable run passed. The active-session
interruption established physical takeover and input refusal; it does not
establish unchanged focus or pointer during human activity.

Unicode paste was refused before input because the controller could not
preserve the clipboard's current formats. No workaround was attempted, and
Unicode paste success is not claimed for this trial. Typing and clicking were
verified through the original input controller.

The companion remains X11-only and observation-only. Other desktops, Wayland,
personal apps, and Steam games were not exercised in this trial. No app
runtime patches or accessibility settings were installed or changed. Test
windows were closed; input control finished inactive with Stop latched.

Local snapshots, registration results, input-source hashes, and the detailed
trial report are kept in ignored `output/accessibility/`. Reload MCP servers
to make the separately registered companion available in the client.
