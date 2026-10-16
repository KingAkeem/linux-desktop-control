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
