# Changelog

## 0.1.0b3

Moves controller status and Stop into a tray menu when the optional Ubuntu
indicator binding and a working host are available. The stable keyboard icon
shows an `LDC` status label; the panel is used for local Resume or fallback.
Tray events can open the panel but cannot grant permission. Physical takeover,
Ctrl+Alt+Escape, ownership, and the watchdog retain their existing behavior.

84 automated tests passed. Live typing with the panel hidden and physical
takeover passed. User confirmation of the menu/local Resume round trip and
a clean live start after the startup-flash fix were not completed. Tray loss
and missing-binding fallback have injected tests; a new physical emergency
shortcut press was not exercised. See the
[tray trial results](docs/TRAY_VERIFICATION.md) for the full coverage limits.

## 0.1.0b2

Adds an optional, separate read-only accessibility companion using AT-SPI.
The existing input controller, visible Stop panel, emergency shortcut,
physical-input takeover, and local Resume requirement are unchanged.

- Two observation tools: `accessibility_status` and `accessibility_tree`.
- Exact selected-window matching, opt-in text, password-node redaction, and
  bounded reads with explicit partial-tree reporting.
- Hidden menu and toolbar controls are omitted to leave room for document text.
- 67 automated tests and a real-app trial in LibreOffice Writer 24.2.7.2.

Writer's Find controls were exposed, but its search field value was not.
GNOME Text Editor 46.3 failed the strict geometry match on the tested host;
the reader refused without returning another app's content. The companion
remains X11-only and cannot send input or change Stop state. See the
[companion guide](docs/ACCESSIBILITY.md) and
[trial results](docs/ACCESSIBILITY_VERIFICATION.md) for details.

## 0.1.0b1

First public beta candidate. Local X11 desktop control over MCP, tested on
Ubuntu GNOME with Python 3.12.

- Seven tools for status, window discovery, starting control, selecting a
  window, capturing pixels, sending bounded input, and stopping.
- Visible Stop panel, emergency shortcut, physical-input takeover, focus
  checks, stale-coordinate rejection, exclusive sessions, and crash recovery.
- Explicit Unicode paste with preservation of supported clipboard content.
- Source installation, diagnostics, Codex registration, and removal.
- Bundled skill and launcher support in built Python distributions.
- Custom `CODEX_HOME` support and skill-conflict checks before registration.
- MIT license, contribution guidance, privacy notes, and automated checks.

Native Wayland, remote control, background desktops, and accessibility element
targeting are outside this beta's scope. The beta shares foreground input and
does not provide an operating-system sandbox.
