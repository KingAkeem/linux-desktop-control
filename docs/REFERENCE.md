# Desktop control reference

Detailed setup, tool behavior, clipboard handling, and live checks. Run the
commands below from the project directory. For a quick start, see the
[README](../README.md).

## Requirements

- Ubuntu GNOME running an **X11 session**, with a reachable, unlocked desktop.
- System Python 3.12, venv support, GTK 3 bindings, XTEST, XInput2, and `gdbus`.
- A trusted local MCP client. Codex is the client tested so far.

On Ubuntu 24.04, install the system prerequisites if needed:

```sh
sudo apt-get update
sudo apt-get install python3-venv python3-gi gir1.2-gtk-3.0 libglib2.0-bin
```

Check `echo "$XDG_SESSION_TYPE"`; it must print `x11`. Running the client
through XWayland in a Wayland session does not make this backend compatible.
Lock checks currently use GNOME's ScreenSaver D-Bus service and fail closed
when the lock state is unknown.

## Installation

Download or clone this repository, enter its directory, and run the commands
below. `./install` creates a virtual environment using system GTK bindings and
downloads the pinned dependencies. It does not install OS packages. No root
privileges or network listener are required at runtime.

```sh
./install --register
.venv/bin/linux-desktop-control doctor
```

Use `./install` without `--register` to install without changing your client
configuration. `doctor` checks dependencies and reports desktop readiness; it
never starts input control. A compatible result does not verify that the
emergency shortcut is free; controller startup checks that separately.

Registration also installs an automatically selected user-level `linux-desktop-control` skill and adds a small routing section to the shared `~/.codex/AGENTS.md`. This makes the tool discoverable across local projects without asking each chat to learn it separately. The skill source lives in this repository and is linked into the user skills directory.

Reopen the Codex chat or reload its MCP servers after registration. If an existing chat still lacks the tools or instructions, restart the app. Global registration does not inject tools into already-running chats or cloud-only sessions. Configuration is added under `mcp_servers.linux-desktop-control`; other server entries are preserved.
Registration updates `config.toml`, links the bundled skill under `skills/`, and
adds a marked routing section to `AGENTS.md`, all beneath `CODEX_HOME` when set
or `~/.codex` by default. Existing conflicting servers or skills are rejected.
Review those changes before reconnecting your client. `./launch` starts the STDIO server, normally managed by Codex.

```sh
.venv/bin/linux-desktop-control uninstall
```

Uninstall unregisters this server, removes its managed skill link and shared guidance section, and preserves unrelated instructions, source and environment. End any active desktop task first. There is no startup service. Keep the checkout and virtual environment in
place while registered. Removal leaves source files, dependencies, logs, and
Stop state intact.

For another STDIO MCP client, configure the absolute path to `launch` as the
command and pass the desktop session's `DISPLAY`, `XAUTHORITY`,
`XDG_SESSION_TYPE`, `XDG_RUNTIME_DIR`, and `DBUS_SESSION_BUS_ADDRESS` as needed.
Do not expose this server as a remote service. Other clients are unverified.
See the [official Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for client configuration details.

## Using the tools

1. `desktop_windows` lists visible window IDs and titles.
2. `desktop_start(task, window_id)` focuses the requested window and displays the control panel.
3. `desktop_capture(scope="window")` returns a PNG with native dimensions, image origin, and capture ID. `scope="desktop"` captures the visible desktop instead.
4. `desktop_action` sends one bounded action and returns a fresh screenshot. Inspect that image to verify the outcome.
5. `desktop_stop` stops input, closes the controller and releases the session for another chat.

`desktop_status` reports compatibility, monitors, lock state, and controller status. `desktop_select_window(window_id)` explicitly changes the target during a session.

Actions: `click`, `double_click`, `move`, `scroll`, `drag`, `key`, `type`, `paste`.

Coordinates are relative to the **returned image**, at native resolution, and require `capture_id`. A drag also requires `end_x` and `end_y`. Window movement, resizing, monitor changes, a newer capture, or 60 seconds invalidate old coordinates. Screenshots contain only visible pixels; obscured windows are not reconstructed. Mouse actions reject points covered by another window.

Keyboard examples: `keys=["Ctrl", "a"]`, `keys=["Escape"]`. `type` accepts up to 200 characters in the current keyboard mapping. `paste` explicitly uses the clipboard and accepts up to 4000 characters, including Unicode. Drag duration is bounded to 3 seconds, scrolling to 20 steps, and actions to 8 seconds.

`input_delivered: true` means events were sent. It does not establish that a UI action succeeded. Errors may occur after partial input; do not blindly repeat them.

For a first check, open a disposable text editor window and ask your assistant:

> Use Linux Desktop Control to select the empty editor, type Hello Linux,
> capture the result, and stop.

Verify the screenshot and the visible Stop panel. For a repeatable fixture demo,
see the live validation commands below. Keep real documents and sensitive apps
closed during initial testing.

## Taking back control

Click **Stop** or press **Ctrl+Alt+Escape**. Physical keyboard input, mouse clicks, and mouse movement also stop control. The controller distinguishes XTEST input from physical XInput2 sources without recording key contents. Detection is reactive: the first physical input can still reach the focused application, and input already delivered cannot be undone. Leave the desktop idle while a task runs.

A local stop remains latched until **Resume permission** is clicked locally. MCP has no resume operation. Clicking Resume permits a new `desktop_start`; it does not resume an interrupted action. Closing the panel latches Stop too; a later start opens a panel where permission can be resumed. Never reset the latch through scripts to bypass a user's stop.

Only one controller can own a display session. The controller refuses to run if the emergency shortcut is unavailable. Unexpected focus changes block further input. Lock or unknown lock state, missing controller heartbeat, controller crash, and MCP disconnect stop input. Held keys and buttons are released, with crash recovery handled by the MCP parent.

The controller is not an operating-system sandbox. Shortcuts can open dialogs or change focus. Use it for specifically authorized tasks; existing boundaries on sending messages, purchases, deletion, and account changes still apply.

## Clipboard preservation and privacy

Plain text and PNG-compatible image clipboards are preserved in memory. Images retain their pixels; original encoded metadata and the exact advertised format list are not preserved. Rich text, file lists, and unsupported formats are rejected before changing the clipboard. If another application or the user takes clipboard ownership during paste, the tool does not overwrite that new clipboard.

A temporary clipboard-holder process keeps restored data available after the controller exits and terminates on the next clipboard ownership change. It has no network listener, startup registration, or disk payload. This is necessary on desktops without a clipboard manager.

The server does not save screenshots, typed text, clipboard contents, or window titles. It returns screenshots to the MCP client, where normal chat handling applies. Local rotating logs contain only time, action category, and success/failure. Runtime files are private to the user and contain the session lock, Stop latch, and currently held input needed for crash recovery.

The diagnostic clients under `tests/` explicitly save test screenshots to ignored `output/`. They are not part of the normal server behavior.

## Validation

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tests/live_demo.py
.venv/bin/python tests/safety_demo.py
```

The latter two commands take control of disposable GTK windows on the current desktop. Leave the keyboard and mouse idle while they run. Their runtime state is isolated from production; they never reset the production Stop latch. The live demo verifies MCP discovery and image content, text, Unicode paste, pointer actions, cancellation, and target closure. Safety tests cover exclusive ownership, focus theft, the global stop latch, and a controller crash during a drag. Screen-lock handling is tested with injected states rather than locking the user's desktop.

The initial scope is X11. Native Wayland, accessibility element targeting, remote access, and background operation in a separate desktop are not implemented.
