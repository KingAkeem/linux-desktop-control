"""Temporary in-memory clipboard holder; exits when the user next copies something.

No clipboard payload is written to disk. A separate process preserves restored
clipboard data even after the desktop control session exits.
"""
import json
import sys
import threading
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from Xlib import display

META = {'TARGETS', 'MULTIPLE', 'TIMESTAMP', 'SAVE_TARGETS'}
TEXT = {'UTF8_STRING', 'STRING', 'TEXT', 'COMPOUND_TEXT', 'text/plain',
        'text/plain;charset=utf-8', 'text/plain;charset=UTF-8'}
IMAGE = {mime for fmt in GdkPixbuf.Pixbuf.get_formats() if fmt.is_writable()
         for mime in fmt.get_mime_types()}


def preservation_kind(names):
    if 'image/png' in names and names <= IMAGE | META:
        return 'image'
    if names <= TEXT | META:
        return 'text'
    raise ValueError('Clipboard formats cannot be preserved; paste was not attempted.')


class Holder:
    def __init__(self, text):
        self.cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.d = display.Display()
        self.atom = self.d.intern_atom('CLIPBOARD')
        self.restored = False
        self.owner = None
        self.changed = False
        self.ready = False
        self.text = text
        self.started = time.monotonic()
        ok, targets = self.cb.wait_for_targets()
        names = {a.name() for a in targets} if ok else set()
        self.kind = preservation_kind(names)
        if self.kind == 'image':
            self.old = self.cb.wait_for_image()
            if self.old is None:
                raise ValueError('Clipboard image could not be preserved.')
            self.old = self.old.copy()
        else:
            self.old = self.cb.wait_for_text() if ok else None
            if ok and self.old is None:
                raise ValueError('Clipboard text could not be preserved.')
        self.cb.connect('owner-change', self.change)
        self.cb.set_text(text, -1)
        GLib.timeout_add(50, self.mark_ready)
        GLib.timeout_add(100, self.watchdog)

    def change(self, *_):
        if self.ready and not self.restored:
            self.changed = True
        if self.restored and self.owner is not None and getattr(self.d.get_selection_owner(self.atom), 'id', 0) != self.owner:
            Gtk.main_quit()

    def mark_ready(self):
        self.owner = getattr(self.d.get_selection_owner(self.atom), 'id', 0)
        self.ready = True
        print(json.dumps({'ready': True}), flush=True)
        threading.Thread(target=self.reader, daemon=True).start()
        return False

    def reader(self):
        # Restore on the explicit message or parent disconnect.
        sys.stdin.readline()
        GLib.idle_add(self.restore)

    def restore(self):
        if self.restored:
            return False
        untouched = not self.changed and getattr(self.d.get_selection_owner(self.atom), 'id', 0) == self.owner
        self.restored = True
        if untouched:
            if self.kind == 'image': self.cb.set_image(self.old)
            elif self.old is None: self.cb.clear()
            else: self.cb.set_text(self.old, -1)
            self.owner = getattr(self.d.get_selection_owner(self.atom), 'id', 0)
        try:
            print(json.dumps({'restored': untouched, 'clipboard_changed_by_user': not untouched}), flush=True)
        except (BrokenPipeError, OSError): pass
        if not untouched or self.old is None:
            Gtk.main_quit()
        return False

    def watchdog(self):
        if not self.restored and time.monotonic()-self.started > 10:
            self.restore()
        # Detect ownership loss even if the event arrives before the saved owner is updated.
        if self.restored and self.owner is not None and getattr(self.d.get_selection_owner(self.atom), 'id', 0) != self.owner:
            Gtk.main_quit()
            return False
        return True


def main():
    try:
        request = json.loads(sys.stdin.readline())
        holder = Holder(request['text'])
        Gtk.main()
        holder.d.close()
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Clipboard preservation failed.'
        print(json.dumps({'error': message}), flush=True)


if __name__ == '__main__': main()
