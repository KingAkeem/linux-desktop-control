"""Two disposable windows for accessibility privacy and coexistence checks."""
import json
import os
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

path = Path(sys.argv[1])
state = {'clicks': 0}
window = Gtk.Window(title=f'Accessibility Companion Test {os.getpid()}')
window.set_default_size(740, 400)
window.move(900, 400)
window.connect('destroy', Gtk.main_quit)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
box.set_border_width(24)
window.add(box)
box.pack_start(Gtk.Label(label='Read-only accessibility companion test'), False, False, 0)
entry = Gtk.Entry()
entry.get_accessible().set_name('Companion test text')
entry.set_text('Initial fixture text')
box.pack_start(entry, False, False, 0)
password = Gtk.Entry()
password.set_visibility(False)
password.set_text('PASSWORD_MUST_NOT_LEAK_86527')
password.get_accessible().set_name('Disposable password')
box.pack_start(password, False, False, 0)
button = Gtk.Button(label='Test click')
count = Gtk.Label(label='Clicks: 0')
def clicked(_):
    state['clicks'] += 1
    count.set_text(f'Clicks: {state["clicks"]}')
button.connect('clicked', clicked)
box.pack_start(button, False, False, 0)
box.pack_start(count, False, False, 0)
other = Gtk.Window(title=f'Accessibility Scope Sentinel {os.getpid()}')
other.set_default_size(320, 100)
other.move(200, 400)
other.add(Gtk.Label(label='OTHER_WINDOW_MUST_NOT_LEAK_94631'))
window.show_all()
other.show_all()

def snapshot():
    state.update(window_id=window.get_window().get_xid(), other_window_id=other.get_window().get_xid(),
                 text=entry.get_text(), widgets={})
    for name, widget in [('entry', entry), ('button', button), ('password', password)]:
        x, y = widget.translate_coordinates(window, 0, 0)
        allocation = widget.get_allocation()
        state['widgets'][name] = [x, y, allocation.width, allocation.height]
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state))
    temporary.replace(path)
    return True
GLib.timeout_add(50, snapshot)
Gtk.main()
