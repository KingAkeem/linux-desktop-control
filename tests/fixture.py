"""Disposable desktop app used only for local integration tests."""
import json
import os
from pathlib import Path
import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib

state_path = Path(sys.argv[1])
state = {'clicks': 0, 'double_clicks': 0, 'drag_events': 0, 'text': '', 'scroll': 0}
window = Gtk.Window(title=f'Desktop Control Test {os.getpid()}')
window.set_default_size(820, 650)
screen = Gdk.Screen.get_default()
window.move(max(0, (screen.get_width()-820)//2), max(0, (screen.get_height()-650)//2))
window.connect('destroy', Gtk.main_quit)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
box.set_border_width(20)
window.add(box)
box.pack_start(Gtk.Label(label='Disposable desktop control test'), False, False, 0)
entry = Gtk.Entry()
entry.set_placeholder_text('Test text')
box.pack_start(entry, False, False, 0)
button = Gtk.Button(label='Test click')
button.connect('clicked', lambda *_: state.update(clicks=state['clicks']+1))
button.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
button.connect('button-press-event', lambda _, e: state.update(double_clicks=state['double_clicks']+int(e.type == Gdk.EventType._2BUTTON_PRESS)))
box.pack_start(button, False, False, 0)
area = Gtk.DrawingArea()
area.set_size_request(600, 150)
area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
held = False
pos = [80, 70]
def draw(_, ctx):
    ctx.set_source_rgb(.12, .18, .26)
    ctx.paint()
    ctx.set_source_rgb(.15, .75, .6)
    ctx.arc(*pos, 22, 0, 6.283)
    ctx.fill()
def press(_, event):
    global held
    held = True
    return True
def release(_, event):
    global held
    held = False
    return True
def motion(_, event):
    if held:
        state['drag_events'] += 1
        pos[:] = [event.x, event.y]
        area.queue_draw()
area.connect('draw', draw)
area.connect('button-press-event', press)
area.connect('button-release-event', release)
area.connect('motion-notify-event', motion)
box.pack_start(area, False, False, 0)
scroll = Gtk.ScrolledWindow()
rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
for i in range(50): rows.pack_start(Gtk.Label(label=f'Test row {i+1}'), False, False, 4)
scroll.add(rows)
box.pack_start(scroll, True, True, 0)

def snapshot():
    state['text'] = entry.get_text()
    state['scroll'] = scroll.get_vadjustment().get_value()
    state['window_id'] = window.get_window().get_xid()
    state['drag_held'] = held
    state['widgets'] = {}
    for name, widget in [('entry',entry),('button',button),('area',area),('scroll',scroll)]:
        x,y = widget.translate_coordinates(window,0,0)
        a=widget.get_allocation()
        state['widgets'][name] = [x,y,a.width,a.height]
    temporary=state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state))
    temporary.replace(state_path)
    return True
window.show_all()
GLib.timeout_add(50,snapshot)
Gtk.main()
