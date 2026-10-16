"""GTK main loop, independent action worker and fail-closed watchdog."""
import json
import os
import queue
import signal
import subprocess
import select
import struct
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, GLib
from Xlib import X, XK, display
from Xlib.ext import xinput

from .backend import Backend, DesktopError, SessionLock, lock_state, runtime_dir, emergency_release
from .tray import create_tray


class Controller:
    def __init__(self):
        self.lock = SessionLock()
        self.lock.acquire()
        emergency_release()
        self.backend = Backend()
        self.backend.clipboard = self.paste
        self.running = True
        self.heartbeat = time.monotonic()
        self.requests = queue.Queue(maxsize=1)
        self.busy = threading.Lock()
        self.output_lock = threading.Lock()
        self.hotkeys = display.Display()
        self.grab_shortcut()
        self.hotkeys.xinput_query_version()
        devices = self.hotkeys.xinput_query_device(xinput.AllDevices).devices
        self.synthetic_devices = {d.deviceid for d in devices if 'XTEST' in d.name}
        self.xinput_opcode = self.hotkeys.query_extension('XInputExtension').major_opcode
        self.hotkeys.screen().root.xinput_select_events([(xinput.AllMasterDevices,
            xinput.RawKeyPressMask | xinput.RawButtonPressMask | xinput.RawMotionMask)])
        self.hotkeys.sync()
        self.last_physical_input = 0.0
        self.window = Gtk.Window(title='Linux Desktop Control')
        self.window.set_keep_above(True)
        self.window.set_accept_focus(False)
        self.window.set_default_size(290, 130)
        self.window.move(16, 48)
        self.window.connect('delete-event', self.close_window)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.label = Gtk.Label(label='Stopped')
        box.pack_start(self.label, True, True, 0)
        stop = Gtk.Button(label='Stop · Ctrl+Alt+Escape')
        stop.connect('clicked', lambda *_: self.backend.stop(latch=True))
        box.pack_start(stop, True, True, 0)
        self.resume = Gtk.Button(label='Resume permission')
        self.resume.connect('clicked', self.resume_local)
        box.pack_start(self.resume, True, True, 0)
        self.window.add(box)
        box.show_all()
        self.window.realize()
        self.backend.ignore_windows.add(self.window.get_window().get_xid())
        self.panel_requested = (runtime_dir() / 'stopped').exists()
        self.ui_mode = 'initializing'
        self.ui_ready = threading.Event()
        self.ui_started = time.monotonic()
        self.tray = create_tray(stop=lambda: self.backend.stop(latch=True),
                               show_controls=self.show_controls,
                               quit_controller=self.quit_local,
                               unavailable=self.tray_unavailable)
        if self.tray is None or self.panel_requested:
            self.window.show()
            self.ui_mode = 'panel'
            self.ui_ready.set()
        GLib.timeout_add(50, self.tick)

    def grab_shortcut(self):
        code = self.hotkeys.keysym_to_keycode(XK.XK_Escape)
        errors = []
        for extra in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask):
            self.hotkeys.screen().root.grab_key(code, X.ControlMask | X.Mod1Mask | extra,
                                               False, X.GrabModeAsync, X.GrabModeAsync,
                                               onerror=lambda e, *_: errors.append(e))
        self.hotkeys.sync()
        if errors:
            self.hotkeys.close()
            raise DesktopError('Emergency shortcut is already in use. Input remains disabled.')

    def tick(self):
        self.heartbeat = time.monotonic()
        while self.hotkeys.pending_events():
            event = self.hotkeys.next_event()
            self.handle_input(event)
        active = self.backend.active
        self.label.set_text(('Controlling window ' + str(self.backend.target)) if active else 'Stopped')
        latched = (runtime_dir() / 'stopped').exists()
        self.resume.set_visible(latched)
        if self.tray is not None and self.tray.available:
            self.tray.update(active, latched)
            self.ui_mode = 'tray'
            self.ui_ready.set()
            if not self.panel_requested:
                self.window.hide()
        else:
            if not self.ui_ready.is_set() and time.monotonic() - self.ui_started < 0.75:
                return self.running
            self.ui_mode = 'panel'
            self.window.show()
            self.ui_ready.set()
        return self.running

    def handle_input(self, event):
        if event.type == X.KeyPress:
            self.backend.stop(latch=True)
        elif event.type == 35 and event.extension == self.xinput_opcode and event.evtype in (
                xinput.RawKeyPress, xinput.RawButtonPress, xinput.RawMotion):
            source = struct.unpack_from('=H', event.data, 10)[0]
            if source not in self.synthetic_devices:
                self.last_physical_input = time.monotonic()
                if not self.backend.cancel.is_set():
                    self.backend.stop(latch=True)

    def resume_local(self, *_):
        # Never exposed through MCP or IPC. The controller is excluded as an input target.
        (runtime_dir() / 'stopped').unlink(missing_ok=True)
        self.label.set_text('Ready for a new task')
        self.panel_requested = False
        if self.tray is not None and self.tray.available:
            self.window.hide()

    def show_controls(self):
        # Opening controls is safe over IPC; granting Resume permission is not exposed.
        self.backend.stop(latch=True)
        self.panel_requested = True
        self.window.show_all()
        return False

    def tray_unavailable(self):
        # Losing the only persistent Stop control cannot leave input running.
        self.show_controls()

    def quit_local(self):
        self.backend.stop(latch=True)
        self.shutdown()

    def close_window(self, *_):
        self.backend.stop(latch=True)
        if self.tray is not None and self.tray.available:
            self.panel_requested = False
            self.window.hide()
            return True
        self.shutdown()
        return False

    def paste(self, text):
        holder = subprocess.Popen([sys.executable, '-m', 'linux_desktop_control.clipboard'],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1, start_new_session=True)
        def response():
            readable, _, _ = select.select([holder.stdout], [], [], 3)
            if not readable:
                raise DesktopError('Clipboard helper timed out; input was stopped.')
            data = json.loads(holder.stdout.readline())
            if data.get('error'):
                raise DesktopError(data['error'])
            return data
        try:
            holder.stdin.write(json.dumps({'text': text})+'\n')
            holder.stdin.flush()
            response()
            try:
                self.backend.chord(['Ctrl', 'v'])
                self.backend.pause(0.25)
            finally:
                holder.stdin.write('restore\n')
                holder.stdin.flush()
                response()
        finally:
            holder.stdin.close()
            holder.stdout.close()
            # The holder may still own the restored clipboard. It exits on the next copy.
            threading.Thread(target=holder.wait, daemon=True).start()

    def respond(self, rid, result=None, err=None):
        with self.output_lock:
            try:
                print(json.dumps({'id': rid, 'result': result, 'error': err}), flush=True)
            except (BrokenPipeError, OSError):
                self.shutdown()

    def audit(self, kind, success):
        root = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'linux-desktop-control'
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        p = root/'actions.jsonl'
        if p.exists() and p.stat().st_size > 1_000_000:
            p.replace(root/'actions.previous.jsonl')
        with p.open('a') as f:
            f.write(json.dumps({'timestamp': time.time(), 'action': kind, 'success': success})+'\n')
        p.chmod(0o600)

    def worker(self):
        while self.running:
            try:
                req = self.requests.get(timeout=0.2)
            except queue.Empty:
                continue
            cmd, args = req['command'], req.get('args', {})
            success = False
            try:
                if cmd == 'start':
                    if not args.get('task', '').strip():
                        raise DesktopError('A task description is required.')
                    if not self.ui_ready.wait(timeout=1):
                        raise DesktopError('Local Stop controls are not ready; no input was sent.')
                    if time.monotonic() - self.last_physical_input < 1:
                        raise DesktopError('Physical input is active. Wait until the user has handed over the desktop.')
                    result = self.backend.start(args['window_id'], req['epoch'])
                elif cmd == 'select':
                    if not self.backend.active:
                        raise DesktopError('Start a session first.')
                    result = self.backend.select(args['window_id'])
                elif cmd == 'status':
                    result = self.backend.status()
                    result['controller_ui'] = self.ui_mode
                elif cmd == 'windows': result = self.backend.windows()
                elif cmd == 'capture': result = self.backend.capture(**args)
                elif cmd == 'action': result = self.backend.action(args)
                else: raise DesktopError('Unknown controller command.')
                success = True
                self.respond(req['id'], result=result)
            except Exception as exc:
                if cmd == 'start' and (runtime_dir() / 'stopped').exists():
                    GLib.idle_add(self.show_controls)
                # Never include request payloads or backend errors containing private data.
                message = str(exc) if isinstance(exc, DesktopError) else 'Desktop operation failed; inspect state before retrying.'
                self.respond(req['id'], err=message)
            finally:
                self.busy.release()
                self.audit(args.get('kind', cmd) if cmd == 'action' else cmd, success)

    def reader(self):
        try:
            for line in sys.stdin:
                req = json.loads(line)
                cmd = req['command']
                if cmd == 'stop':
                    self.respond(req['id'], self.backend.stop())
                elif cmd == 'shutdown':
                    self.shutdown()
                    return
                else:
                    if not self.busy.acquire(blocking=False):
                        self.respond(req['id'], err='Controller busy; no action queued.')
                    else:
                        req['epoch'] = self.backend.epoch
                        self.requests.put_nowait(req)
        finally:
            self.shutdown()

    def watchdog(self):
        while self.running:
            if time.monotonic() - self.heartbeat > 1.5:
                self.backend.stop(latch=True)
                self.running = False
                os._exit(2)
            if self.backend.active and lock_state() is not False:
                self.backend.stop(latch=True)
            time.sleep(0.15)

    def shutdown(self):
        self.backend.stop()
        self.running = False
        GLib.idle_add(Gtk.main_quit)

    def run(self):
        for fn in (self.worker, self.reader, self.watchdog):
            threading.Thread(target=fn, daemon=True).start()
        signal.signal(signal.SIGTERM, lambda *_: self.shutdown())
        signal.signal(signal.SIGINT, lambda *_: self.shutdown())
        self.respond('ready', {'ready': True})
        try:
            Gtk.main()
        finally:
            if self.tray is not None:
                self.tray.close()
            self.backend.close()
            self.hotkeys.close()
            self.lock.close()


def main():
    try:
        Controller().run()
    except Exception as exc:
        message = str(exc) if isinstance(exc, DesktopError) else 'Controller initialization failed.'
        print(json.dumps({'id': 'ready', 'error': message}), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
