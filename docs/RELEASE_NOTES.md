# Linux Desktop Control 0.1.0b2

This prerelease adds an optional read-only accessibility companion alongside
the existing Linux Desktop Control MCP server. It uses AT-SPI directly; it
does not include or run another project's desktop-control backend.

The existing seven input tools, visible Stop panel, Ctrl+Alt+Escape shortcut,
physical-input takeover, and local Resume permission are unchanged. All input
still goes through the original controller.

## What's included

- `accessibility_status` checks whether AT-SPI is available.
- `accessibility_tree` reads one explicitly selected X11 window, matched by
  process ID, exact title, and frame geometry.
- Text is opt-in. Password nodes and descendants are redacted. Reads have
  node, depth, field, output-size, and time limits.
- Hidden menu and toolbar controls are omitted so they do not crowd out
  document text. Partial reads and omissions are reported explicitly.
- The companion cannot focus, click, type, paste, activate accessibility
  actions, edit values, change settings, or clear Stop.

## Tested

67 automated tests passed, including all 36 existing input-controller tests.
Source and wheel builds and installed-package MCP checks passed.

On Ubuntu GNOME with X11 and Python 3.12, the existing controller typed into
a disposable document in LibreOffice Writer 24.2.7.2. The companion read the
typed text back within its default 200-node limit. Text opt-in, bounded reads,
stable focus/pointer/Stop/configuration, and closed-window refusal were also
verified. Input was stopped after the trial.

## Known limitations

- The companion is experimental and X11-only. Wayland is unsupported; other
  desktops and applications remain unverified.
- Writer exposed its Find controls but not the search field's value. Typing
  was verified by screenshot; accessibility readback of that value is not claimed.
- GNOME Text Editor 46.3 reported accessibility geometry that did not match
  its X11 window on the tested host. The reader refused the request. The
  matching rules were not relaxed, and support for this app is not claimed.
- Successful reads may still be partial. Labels and descriptions can contain
  private data even with text disabled. Password redaction is not a general
  secret detector or an OS sandbox.
- The earlier fixture trial refused Unicode paste because the current
  clipboard formats could not be preserved. No workaround was used; that
  trial does not establish Unicode paste success.

## Setup

The companion is optional and registered separately as
`linux-desktop-accessibility`. It needs the Ubuntu AT-SPI bindings
(`gir1.2-atspi-2.0`). Follow the [companion guide](https://github.com/KingAkeem/linux-desktop-control/blob/v0.1.0b2/docs/ACCESSIBILITY.md)
for its doctor, registration, and removal commands, then reload MCP servers.

Read the [trial results](https://github.com/KingAkeem/linux-desktop-control/blob/v0.1.0b2/docs/ACCESSIBILITY_VERIFICATION.md)
for the checks and coverage limits. The project remains MIT licensed.

---

# Linux Desktop Control 0.1.0b1

First beta of a local MCP server for visible Linux desktop apps, tested with
Codex on Ubuntu GNOME, X11, and Python 3.12.

It can select a window, capture visible pixels, and send bounded mouse and
keyboard input. Unicode paste is explicit. A visible Stop panel, emergency
shortcut, physical-input takeover, focus checks, and crash recovery help keep
control in the user's hands.

Installation, diagnostics, removal, and an optional Codex skill are included.
The project is available under the MIT license.

This beta shares your foreground pointer and keyboard. It is not an OS sandbox.
Screenshots are returned to your MCP client. Native Wayland, other desktop
environments, remote access, background desktops, and other MCP clients are
unsupported or unverified. Start with a disposable window and stay present.

Read README.md for setup, SECURITY.md for privacy details, and CONTRIBUTING.md
for bug reports. Feedback on clean installation and the tested X11 setup is
especially useful.
