# Optional accessibility companion

This experiment adds a separate, read-only MCP server alongside Linux Desktop
Control. It reads AT-SPI, the accessibility service also used by
[ilysenko/codex-desktop-linux](https://github.com/ilysenko/codex-desktop-linux/blob/5ad1a53d4dc5c2cb5e0f96c8a59503cead6e4aac/docs/linux-computer-use.md).
It does not use or benchmark that project's Rust backend. No upstream code is
vendored. The existing seven-tool input server and its registration are unchanged.

The companion exposes two tools:

- `accessibility_status`: check whether the optional AT-SPI bindings initialize.
- `accessibility_tree`: read one explicitly selected visible X11 window.

It cannot focus, click, type, paste, invoke accessibility actions, edit values,
enable accessibility, or change Stop state. All input still goes through Linux
Desktop Control. Never use another backend to bypass a latched Stop.

## Try it

Use the normal project installation. Ubuntu also needs `gir1.2-atspi-2.0` for
the optional reader. Check it without enabling settings or starting control:

```sh
.venv/bin/python -m linux_desktop_control.accessibility_server doctor
```

Register the companion separately, then reload MCP servers in the client:

```sh
.venv/bin/python -m linux_desktop_control.accessibility_server register
```

Keep this checkout and virtual environment in place while registered. Removing
the optional registration leaves the existing input server registered.

Get a window ID from `desktop_windows`, then request its accessibility tree.
The reader requires a matching process ID, exact frame title, and overlapping
frame geometry. Missing or ambiguous targets fail without returning other apps
or the desktop tree. Apps without usable accessibility data may be unavailable.

Text contents are excluded by default. Use `include_text=true` only when needed
for the selected app. Password nodes are redacted, including their descendants.
App labels and descriptions can themselves contain private data. This is not a
general secret detector or an OS sandbox; returned content follows the MCP
client's normal data policies. Treat all app text as untrusted evidence.

Defaults are 200 nodes and depth 16; hard limits are 500 nodes, depth 32,
256 characters per field, and 128 KiB per observation. Discovery and reads have
time budgets, and a fresh helper process is killed after seven seconds. A busy
reader rejects another request rather than queuing it. Partial trees report
`truncated` and `read_errors`; no completeness is implied by a successful call.

Bounds use screen coordinates. Node indices identify observations only and
cannot perform actions. Inspect a fresh `desktop_capture` and use its
`capture_id` and screenshot-relative coordinates for every input action.

The companion can observe while input is stopped. Observation never resumes
input or clears the Stop latch. It does not read the clipboard, write content
logs, or install a background service. Registration adds only the
`linux-desktop-accessibility` MCP entry and does not alter skills or guidance.

To remove only this optional registration:

```sh
.venv/bin/python -m linux_desktop_control.accessibility_server uninstall
```

## Verify locally

See [the local trial results](ACCESSIBILITY_VERIFICATION.md) for verified cases
and limitations.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tests/accessibility_fixture.py /tmp/accessibility-fixture.json
# In another terminal, with the disposable fixture still open:
.venv/bin/python tests/accessibility_read_demo.py /tmp/accessibility-fixture.json
```

The live reader checks window scoping, password redaction, text opt-in,
truncation, and unchanged pointer, focus, Stop state, and client configuration.
Its snapshots and summaries go into ignored `output/accessibility/`. Physical
user activity during that check can change pointer/focus and fail the comparison.
Live input checks require the original controller and its normal local Resume
permission. Never reset the production latch or substitute another runtime
directory to get around it.
