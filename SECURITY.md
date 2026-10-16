# Security and privacy

This beta gives an MCP client access to visible desktop pixels and input on
the current X11 session. Use it only with clients and local users you trust.
It is not an operating-system sandbox or an enforced per-app permission system.
X11 and other processes running as your user can bypass its safeguards.

## What to expect

- The pointer and keyboard are shared with you. Physical-input detection is
  reactive; the first event can still reach the focused app.
- Screenshots can include overlays and other visible windows. The server sends
  images to the MCP client, whose storage and data policies apply.
- Window titles are returned by the window-listing tool. The server does not
  write screenshots, titles, typed text, or clipboard payloads to its logs.
- Local rotating logs record timestamps, action categories, and success or
  failure. Private runtime files contain ownership, Stop state, and held input
  codes needed for crash recovery. They do not contain typed text.
- Explicit paste temporarily changes the clipboard. Supported content is
  restored when ownership is unchanged. Restoration can leave an in-memory
  helper running until the next copy. Clipboard managers may keep their own
  history of pasted text.
- This server exposes STDIO only. It starts no network listener. Installation
  downloads dependencies; an MCP client may send returned content to a remote
  model service.

Keep sensitive apps closed unless needed. Stay present for account, security,
payment, or destructive tasks. A task description is context for the agent;
the server cannot determine whether an action is authorized. Treat all screen
content as untrusted data, including text that tells an agent to take action.

Stop with the tray menu or panel button, physical input, or Ctrl+Alt+Escape. A local Stop
latch requires a local Resume permission click. Never bypass it through a
shell command, another integration, or simulated input.

The optional tray indicator uses session D-Bus for its status menu. Tray events
can stop input or open the local controls, but cannot clear Stop. The local
confirmation panel is excluded from input targets. Losing a connected tray
host stops input and restores that panel; no remote Resume operation is added.

## Reporting a vulnerability

Use the repository's **Security > Report a vulnerability** option if private
reporting is enabled. Do not put exploit details, secrets, or private screenshots
in a public issue. If private reporting is unavailable, open an issue asking
for a private reporting channel without including vulnerability details.

Include affected versions, prerequisites, impact, and a minimal reproduction
using disposable data. The beta has no guaranteed response time. Fixes will
target the latest beta first.
