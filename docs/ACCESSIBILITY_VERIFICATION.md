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

## Real-app follow-up

Tested on the same Ubuntu GNOME X11 host on October 16, 2026, using a disposable
document in LibreOffice Writer 24.2.7.2 with a separate temporary application
profile. No personal documents were opened.

- The first reads matched Writer correctly but spent the node budget on
  hidden menu commands and toolbar controls before reaching document text.
  The companion now omits hidden children of menus and toolbars. Omissions
  remain explicit through `truncated` and `omitted_hidden_controls`; node,
  depth, byte, time, and exact-window limits are unchanged.
- The existing globally configured input controller moved to the end of the
  test document, typed `Writer companion check 7429`, opened Find, and typed
  `compass`. Returned screenshots were inspected after every action.
- With text opted in, the companion read all five document paragraphs,
  including the typed marker, within the default 200-node budget and with
  zero read errors. Without text opt-in, no node contained a `text` field.
  A one-node read returned one node and reported truncation.
- A 500-node request returned 228 nodes. Writer's Find bar and controls were
  exposed, but the application did not expose the search field value in this
  tree. The screenshot verifies typing; accessibility readback of that value
  is not claimed. Both normal and larger observations report partial trees.
- Stable passive reads took about 1.4 to 1.6 seconds including MCP process
  startup and preserved focus, pointer, Stop latch, and client configuration.
  Reads during physical desktop activity are not evidence of invariance.
- Stop was initially latched. Opening the normal controller made the local
  Resume button available; input started only after status confirmed the
  user had cleared it locally. Explicit Stop ended input, and another typing
  request was rejected. Observation continued while input was inactive.
  After the owned test processes were closed, a read of the old Writer ID
  was rejected without returning another window's data.
- GNOME Text Editor 46.3 exposed a frame title and PID matching its selected
  window, but AT-SPI reported `[0, 0, 700, 520]` while X11 reported
  `[52, 27, 822, 642]`. The strict geometry check refused the read. No match
  rule was relaxed, and support for this application is not claimed.

The updated automated suite passes 67 tests, including all 36 original input
tests and menu/toolbar budget regressions. The seven existing input and
integration modules remain identical to the reviewed public beta. The
controller's UI, physical takeover, emergency shortcut, and local Resume
requirement were not changed. A windowless input mode is not part of this
companion.

Ruff's Python error checks and Git whitespace checks passed. Updated source
and wheel distributions built successfully; an installed-wheel STDIO MCP
check discovered only the two read-only tools and passed the status probe.

Private real-app snapshots and input screenshots are in ignored
`output/accessibility-real-app/`. These results qualify this narrow Writer
trial, not general application compatibility or Wayland support.
