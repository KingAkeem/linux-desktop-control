# Tray controls verification

Local development on October 16, 2026, on Ubuntu GNOME X11 with Python 3.12.
This record accompanies the 0.1.0b3 prerelease.

## Automated and package checks

- 84 automated tests passed, including the existing controller and companion
  suites. New checks cover hidden-panel operation, local Resume, tray/host
  loss, missing optional bindings, stable icon identity, startup fallback,
  and refusing a start when no local Stop UI is ready.
- Ruff's Python error checks and Git whitespace checks passed.
- Source and wheel builds passed. An installed-wheel check verified the tray
  module and the original seven MCP tools, with no Resume tool.
- The input backend, clipboard implementation, MCP server, and accessibility
  companion modules are unchanged from the published 0.1.0b2 release.
  Emergency shortcut grabbing, physical-input handling, ownership, and the
  watchdog retain their existing implementations.

## Live checks

The optional Ubuntu indicator binding was installed locally by the user.
The existing registered controller was used for the trial; no alternative
input backend or temporary runtime directory was used.

- The desktop's indicator host and the controller's registered menu were
  verified. The menu exposes Stop, Resume permission, Show controls, and
  Stop and quit. The stable keyboard icon has an `LDC` status label.
- Typing `Tray mode ready 8164` into a disposable Text Editor tab succeeded.
  Its returned screenshot was inspected, and the controller reported tray
  mode with the persistent panel hidden.
- Physical mouse takeover stopped control and latched Stop. Another typing
  request was rejected. No tool cleared or synthesized Resume permission.
- An early icon changed appearance after takeover and was difficult for the
  user to find. It was replaced with a stable keyboard icon and an explicit
  `LDC: active`, `LDC: stopped`, or `LDC: ready` label. The registered menu and
  label were verified through read-only inspection of this indicator.

## Coverage limits and final state

The user ended the test and asked to use the collected results. The user-facing
menu and local Resume round trip were not confirmed. Tray events only open
the local panel; the actual local Resume click is deliberately outside tool
control. A clean live start after the startup-flash fix was not exercised.
These checks remain unverified, rather than passed or awaiting another action.

Tray/host loss and missing-binding fallback were tested with injected states;
the desktop's shared indicator host was not disabled during the live trial.
The emergency shortcut was successfully grabbed at controller startup, but a
new physical shortcut press was not exercised in this trial. These results
do not establish support for other desktops, tray implementations, or Wayland.

The test was ended through `desktop_stop`. Final status confirmed input
inactive, no selected target, and Stop still latched. The controller and tray
were closed without clearing permission. No additional live checks were
performed for publication; the unverified checks above remain explicit
prerelease limitations.
