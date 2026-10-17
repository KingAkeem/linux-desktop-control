# Beta verification

For the tray controller in 0.1.0b3, see the
[tray trial results and uncompleted manual checks](docs/TRAY_VERIFICATION.md).

For the optional accessibility companion in 0.1.0b2, see the
[fixture and real-app trial results](docs/ACCESSIBILITY_VERIFICATION.md).
The following section records the original input-controller beta checks.

Verified locally on October 16, 2026, for version 0.1.0b1. The host runs
Ubuntu GNOME on X11 with Python 3.12 and a 3440 × 1440 display.

## Checks completed

- 36 automated tests passed, including coordinate validity, focus and
  cancellation, input limits, exclusive sessions, clipboard preservation,
  held-input recovery, custom client configuration, registration conflicts,
  distribution resource paths, and diagnostic failures.
- A fresh source installation passed from a checkout with spaces in its path.
  This used a new virtual environment and downloaded pinned dependencies.
- Both the source distribution and wheel built. Wheel installation, bundled
  skill discovery, registration, repeated registration, removal, seven-tool
  MCP discovery, and read-only desktop status passed outside the source tree.
- A separate virtual environment without system packages installed the locked
  dependencies and passed `pip check`.
- `pip-audit` reported no known vulnerabilities for the 38 pinned dependencies.
  This is a point-in-time advisory check, not a guarantee of security.
- Ruff's Python error checks, shell syntax checks, and Git whitespace checks
  passed.
- Live MCP checks passed in disposable GTK windows: screenshot content, focus,
  typing, Unicode paste, click, double-click, scroll, drag, cancellation during
  typing and dragging, and target closure.
- Live safety checks passed: exclusive ownership, a failed contender leaving
  the owner intact, focus theft rejection, the emergency shortcut, refusal to
  bypass Stop, and releasing a held mouse button after a controller crash.
- The returned fixture screenshot was visually inspected. The README image
  contains only the disposable test window.

The live checks used separate runtime state and left the production Stop state
intact. Desktop control was inactive when testing finished. Registration tests
used temporary client homes and did not register the beta into the live client.

## Coverage limits

All checks ran on one physical host. Fresh environments do not establish
compatibility with another distribution, desktop, display layout, Python
version, or MCP client. Native Wayland and other desktop environments remain
unsupported or unverified. GitHub-hosted CI is prepared but has not run because
this candidate has not been published.

Screen-lock and physical-input classification have injected tests; the real
screen was not locked during validation. Crash recovery cannot undo delivered
input. Physical takeover detection remains reactive. No OS sandbox is provided.

Historical local validation is retained in the private development history.
The publication candidate uses a separate initial commit to avoid publishing
personal paths and unrelated workflow files from that history.
