# Changelog

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
