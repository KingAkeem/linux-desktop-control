"""Bounded X11 operations. No subprocess commands are accepted from callers."""
from __future__ import annotations

import base64
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from Xlib import X, XK, display, protocol
from Xlib.ext import xtest
import mss
from PIL import Image


class DesktopError(RuntimeError):
    pass


def runtime_dir():
    root = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'linux-desktop-control'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise DesktopError('Runtime directory must be private and owned by you.')
    return root


class SessionLock:
    def __init__(self):
        self.file = None

    def acquire(self):
        self.file = (runtime_dir() / 'session.lock').open('a')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            self.file = None
            raise DesktopError('Another desktop controller is already running.') from None

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


def lock_state():
    try:
        r = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
                            '--object-path', '/org/gnome/ScreenSaver', '--method',
                            'org.gnome.ScreenSaver.GetActive'], capture_output=True, text=True, timeout=0.8)
        return {'(true,)': True, '(false,)': False}.get(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return None


def emergency_release():
    """Recover our held input after a controller crash, never release unrelated input."""
    p = runtime_dir() / 'held.json'
    if not p.exists():
        return
    held = json.loads(p.read_text())
    d = display.Display()
    for kind, code in reversed(held):
        xtest.fake_input(d, X.KeyRelease if kind == 'key' else X.ButtonRelease, code)
    d.sync()
    d.close()
    p.unlink(missing_ok=True)


class Backend:
    def __init__(self):
        if os.environ.get('XDG_SESSION_TYPE') != 'x11':
            raise DesktopError('This release requires an X11 session; Wayland is unsupported.')
        self.d = display.Display()
        if not self.d.has_extension('XTEST'):
            raise DesktopError('XTEST is unavailable on this display.')
        self.root = self.d.screen().root
        self.mutex = threading.RLock()
        self.cancel = threading.Event()
        self.cancel.set()
        self.target = None
        self.active = False
        self.held = []
        self.captures = {}
        self.deadline = float('inf')
        self.clipboard = None
        self.ignore_windows = set()
        self.epoch = 0

    def prop(self, w, name):
        p = w.get_full_property(self.d.intern_atom(name), X.AnyPropertyType)
        return None if p is None else p.value

    def active_window(self):
        v = self.prop(self.root, '_NET_ACTIVE_WINDOW')
        return int(v[0]) if v is not None and len(v) else None

    def geometry(self, wid):
        try:
            w = self.d.create_resource_object('window', wid)
            a, g = w.get_attributes(), w.get_geometry()
            if a.map_state != X.IsViewable:
                raise DesktopError('Target window is not visible.')
            p = self.root.translate_coords(w, 0, 0)
            return (p.x, p.y, g.width, g.height)
        except DesktopError:
            raise
        except Exception:
            raise DesktopError('Target window no longer exists.') from None

    def windows(self):
        with self.mutex:
            ids = self.prop(self.root, '_NET_CLIENT_LIST_STACKING')
            rows = []
            for wid in [] if ids is None else ids:
                wid = int(wid)
                if wid in self.ignore_windows:
                    continue
                try:
                    geom = self.geometry(wid)
                    w = self.d.create_resource_object('window', wid)
                    title = self.prop(w, '_NET_WM_NAME')
                    if isinstance(title, bytes):
                        title = title.decode('utf-8', 'replace')
                    rows.append({'window_id': wid, 'title': str(title or w.get_wm_name() or ''),
                                 'geometry': geom, 'focused': wid == self.active_window()})
                except Exception:
                    continue
            return rows

    def monitors(self):
        with mss.mss() as s:
            return [dict(m) for m in s.monitors]

    def status(self):
        return {'compatible': True, 'session_type': 'x11', 'locked': lock_state(),
                'monitors': self.monitors(), 'active': self.active, 'target_window': self.target,
                'stop_latched': (runtime_dir() / 'stopped').exists()}

    def select(self, wid):
        if wid not in {w['window_id'] for w in self.windows()}:
            raise DesktopError('Choose a visible application window returned by desktop_windows.')
        if lock_state() is not False:
            raise DesktopError('Desktop is locked or lock status is unavailable.')
        with self.mutex:
            w = self.d.create_resource_object('window', wid)
            ev = protocol.event.ClientMessage(window=w, client_type=self.d.intern_atom('_NET_ACTIVE_WINDOW'),
                                              data=(32, [2, X.CurrentTime, 0, 0, 0]))
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.d.flush()
        for _ in range(30):
            if self.cancel.is_set():
                raise DesktopError('Session stopped.')
            with self.mutex:
                if self.active_window() == wid:
                    self.target = wid
                    self.captures.clear()
                    return {'target_window': wid, 'focused': True}
            time.sleep(0.03)
        raise DesktopError('Window manager did not focus the selected window.')

    def start(self, wid, expected_epoch=None):
        if (runtime_dir() / 'stopped').exists():
            raise DesktopError('Stop is latched. Click Resume locally before starting again.')
        with self.mutex:
            if expected_epoch is not None and expected_epoch != self.epoch:
                raise DesktopError('Request cancelled by Stop.')
            self.cancel.clear()
        try:
            result = self.select(wid)
            with self.mutex:
                if self.cancel.is_set():
                    raise DesktopError('Request cancelled by Stop.')
                self.active = True
            return result
        except BaseException:
            self.stop()
            raise

    def stop(self, latch=False):
        self.cancel.set()
        if latch:
            (runtime_dir() / 'stopped').touch(mode=0o600)
        with self.mutex:
            self.epoch += 1
            self.active = False
            self.release()
            self.captures.clear()
        return {'active': False, 'stop_latched': (runtime_dir() / 'stopped').exists()}

    def check(self):
        if self.cancel.is_set() or not self.active:
            raise DesktopError('Session stopped.')
        if time.monotonic() > self.deadline:
            raise DesktopError('Action deadline exceeded; input may have been partially delivered.')
        if self.active_window() != self.target:
            raise DesktopError('Target lost focus. Select it explicitly before sending more input.')
        self.geometry(self.target)

    def capture(self, scope='window'):
        if scope not in ('window', 'desktop'):
            raise DesktopError('Capture scope must be window or desktop.')
        if lock_state() is not False:
            raise DesktopError('Desktop is locked or lock status is unavailable.')
        with self.mutex:
            if not self.active or self.cancel.is_set():
                raise DesktopError('Start a session before capturing the screen.')
            geom = self.geometry(self.target)
            monitors = self.monitors()
            desktop = monitors[0]
            x, y, w, h = geom if scope == 'window' else (desktop['left'], desktop['top'], desktop['width'], desktop['height'])
            left, top = max(x, desktop['left']), max(y, desktop['top'])
            right = min(x + w, desktop['left'] + desktop['width'])
            bottom = min(y + h, desktop['top'] + desktop['height'])
            if right <= left or bottom <= top:
                raise DesktopError('Target is outside the visible desktop.')
            region = {'left': left, 'top': top, 'width': right-left, 'height': bottom-top}
            with mss.mss() as s:
                shot = s.grab(region)
            output = io.BytesIO()
            Image.frombytes('RGB', shot.size, shot.rgb).save(output, format='PNG')
            cid = uuid.uuid4().hex
            meta = {'capture_id': cid, 'origin': [left, top], 'width': right-left, 'height': bottom-top,
                    'window_id': self.target, 'native_resolution': True, 'scope': scope,
                    'visible_pixels_only': True}
            self.captures = {cid: (meta, geom, monitors, time.monotonic())}
            return {'metadata': meta, 'png': base64.b64encode(output.getvalue()).decode()}

    def point(self, cid, x, y):
        if cid not in self.captures:
            raise DesktopError('Unknown or superseded capture. Capture again.')
        meta, geom, monitors, at = self.captures[cid]
        if time.monotonic() - at > 60 or geom != self.geometry(self.target) or monitors != self.monitors():
            raise DesktopError('Stale capture: window or display changed, or 60 seconds elapsed.')
        if type(x) is not int or type(y) is not int or not (0 <= x < meta['width'] and 0 <= y < meta['height']):
            raise DesktopError('Coordinates are outside the referenced image.')
        px, py = x + meta['origin'][0], y + meta['origin'][1]
        gx, gy, gw, gh = geom
        if not (gx <= px < gx+gw and gy <= py < gy+gh):
            raise DesktopError('Coordinates are outside the selected window.')
        return px, py

    def unobscured(self, px, py):
        """Reject points covered by another mapped root child, including overlays."""
        w = self.d.create_resource_object('window', self.target)
        top = w
        while True:
            parent = top.query_tree().parent
            if parent.id == self.root.id:
                break
            top = parent
        children = self.root.query_tree().children
        seen = False
        for other in children:
            if other.id == top.id:
                seen = True
                continue
            if not seen:
                continue
            try:
                a = other.get_attributes()
                if a.map_state != X.IsViewable or a.win_class == X.InputOnly:
                    continue
                g = self.geometry(other.id)
                if g[0] <= px < g[0]+g[2] and g[1] <= py < g[1]+g[3]:
                    raise DesktopError('Another window covers this point. Capture and select again.')
            except DesktopError:
                raise
            except Exception:
                continue

    def record_held(self):
        p = runtime_dir() / 'held.json'
        pending = p.with_suffix('.pending')
        fd = os.open(pending, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(json.dumps(self.held))
            stream.flush()
        pending.replace(p)

    def emit(self, kind, code, down):
        with self.mutex:
            if down:
                self.check()
                self.held.append((kind, code))
                self.record_held()
            xtest.fake_input(self.d, (X.KeyPress if down else X.KeyRelease) if kind == 'key' else
                             (X.ButtonPress if down else X.ButtonRelease), code)
            self.d.sync()
            if not down and (kind, code) in self.held:
                self.held.remove((kind, code))
                self.record_held()

    def release(self):
        for kind, code in list(reversed(self.held)):
            self.emit(kind, code, False)

    def pause(self, seconds):
        if self.cancel.wait(seconds):
            raise DesktopError('Session stopped; input may have been partially delivered.')
        with self.mutex:
            self.check()

    def move(self, point):
        with self.mutex:
            self.check()
            self.unobscured(*point)
            xtest.fake_input(self.d, X.MotionNotify, x=point[0], y=point[1])
            self.d.sync()

    def keycode(self, name):
        aliases = {'Ctrl': 'Control_L', 'Control': 'Control_L', 'Alt': 'Alt_L', 'Shift': 'Shift_L',
                   'Super': 'Super_L', 'Enter': 'Return', 'Esc': 'Escape', 'Space': 'space'}
        sym = XK.string_to_keysym(aliases.get(name, name))
        if not sym:
            raise DesktopError('Unknown key name.')
        code = self.d.keysym_to_keycode(sym)
        if not code:
            raise DesktopError('Key is unavailable in the active keyboard mapping.')
        return code

    def text_keys(self, text):
        mapping = self.d.get_keyboard_mapping(8, 248)
        out = []
        for char in text:
            sym = {'\n': XK.XK_Return, '\t': XK.XK_Tab}.get(char, ord(char))
            match = next(((code+8, bool(level)) for code, row in enumerate(mapping)
                          for level in range(min(2, len(row))) if row[level] == sym), None)
            if match is None:
                raise DesktopError('Text is unsupported by the keyboard mapping. Use explicit paste.')
            out.append(match)
        return out

    def chord(self, keys):
        codes = [self.keycode(k) for k in keys]
        if self.keycode('Escape') in codes and self.keycode('Ctrl') in codes and self.keycode('Alt') in codes:
            raise DesktopError('The emergency Stop shortcut cannot be synthesized.')
        try:
            for code in codes:
                self.emit('key', code, True)
            self.pause(0.025)
        finally:
            self.release()

    def action(self, req):
        kind = req.get('kind')
        allowed = {'click', 'double_click', 'move', 'scroll', 'drag', 'key', 'type', 'paste'}
        if kind not in allowed:
            raise DesktopError('Unsupported action kind.')
        duration = req.get('duration', 0.5)
        if not isinstance(duration, (int, float)) or not 0.05 <= duration <= 3:
            raise DesktopError('Duration must be between 0.05 and 3 seconds.')
        text = req.get('text', '')
        if not isinstance(text, str) or len(text) > 4000:
            raise DesktopError('Text must contain at most 4000 characters.')
        keys = req.get('keys', [])
        if not isinstance(keys, list) or not 0 <= len(keys) <= 5 or any(not isinstance(k, str) for k in keys):
            raise DesktopError('Supply at most five key names.')
        if kind == 'key' and not keys:
            raise DesktopError('Key chord must not be empty.')
        if kind in ('type', 'paste') and not text:
            raise DesktopError('Text must not be empty.')
        if kind == 'type' and len(text) > 200:
            raise DesktopError('Use paste for more than 200 characters.')
        steps = req.get('steps', 3)
        if type(steps) is not int or not 1 <= steps <= 20:
            raise DesktopError('Scroll steps must be between 1 and 20.')
        button = req.get('button', 'left')
        if button not in ('left', 'middle', 'right'):
            raise DesktopError('Button must be left, middle, or right.')
        direction = req.get('direction', 'down')
        if direction not in ('up', 'down', 'left', 'right'):
            raise DesktopError('Invalid scroll direction.')
        if lock_state() is not False:
            self.stop()
            raise DesktopError('Desktop is locked or lock status is unavailable.')
        self.deadline = time.monotonic() + 8
        try:
            with self.mutex:
                self.check()
                if self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask | X.LockMask):
                    raise DesktopError('Release keyboard modifiers and disable Caps Lock before input.')
                point = self.point(req.get('capture_id'), req.get('x'), req.get('y')) if kind in (
                    'click', 'double_click', 'move', 'scroll', 'drag') else None
                end = self.point(req.get('capture_id'), req.get('end_x'), req.get('end_y')) if kind == 'drag' else None
                typed = self.text_keys(text) if kind == 'type' else []
            if point:
                self.move(point)
            b = {'left': 1, 'middle': 2, 'right': 3}[button]
            if kind in ('click', 'double_click', 'scroll'):
                count = 2 if kind == 'double_click' else steps if kind == 'scroll' else 1
                if kind == 'scroll':
                    b = {'up': 4, 'down': 5, 'left': 6, 'right': 7}[direction]
                for _ in range(count):
                    self.emit('button', b, True)
                    self.emit('button', b, False)
                    self.pause(0.06)
            elif kind == 'drag':
                self.emit('button', b, True)
                n = max(2, int(duration / 0.02))
                for i in range(1, n+1):
                    self.pause(duration / n)
                    self.move((round(point[0]+(end[0]-point[0])*i/n), round(point[1]+(end[1]-point[1])*i/n)))
                self.emit('button', b, False)
            elif kind == 'key':
                self.chord(keys)
            elif kind == 'type':
                shift = self.keycode('Shift')
                for code, shifted in typed:
                    if shifted:
                        self.emit('key', shift, True)
                    self.emit('key', code, True)
                    self.emit('key', code, False)
                    if shifted:
                        self.emit('key', shift, False)
                    self.pause(0.02)
            elif kind == 'paste':
                if not self.clipboard:
                    raise DesktopError('Clipboard controller unavailable.')
                self.clipboard(text)
            self.pause(0.1)
        finally:
            with self.mutex:
                self.release()
            self.deadline = float('inf')
        try:
            result = self.capture()
        except Exception:
            return {'input_delivered': True, 'outcome_verified': False,
                    'capture_error': 'Post-action screenshot unavailable; inspect before any further action.'}
        result.update(input_delivered=True, outcome_verified=False)
        return result

    def close(self):
        self.stop()
        self.d.close()
