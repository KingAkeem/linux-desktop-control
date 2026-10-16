"""Optional status indicator. Tray events can stop input or open local controls only."""
import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk

WATCHER = 'org.kde.StatusNotifierWatcher'
WATCHER_PATH = '/StatusNotifierWatcher'


class TrayControls:
    def __init__(self, stop, show_controls, quit_controller, unavailable):
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3 as Indicator
        self.api = Indicator
        self.unavailable = unavailable
        self.closed = False
        self.connected = False
        self.host_ready = False
        self.previous = None
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        value = self.bus.call_sync(WATCHER, WATCHER_PATH,
            'org.freedesktop.DBus.Properties', 'Get',
            GLib.Variant('(ss)', (WATCHER, 'IsStatusNotifierHostRegistered')),
            GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NO_AUTO_START, 500, None)
        if not value.unpack()[0]:
            raise RuntimeError('No status indicator host is registered.')
        self.host_ready = True
        self.menu = Gtk.Menu()
        self.state = Gtk.MenuItem.new_with_label('Desktop control stopped')
        self.state.set_sensitive(False)
        self.menu.append(self.state)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.stop_item = Gtk.MenuItem.new_with_label('Stop · Ctrl+Alt+Escape')
        self.stop_item.connect('activate', lambda *_: stop())
        self.menu.append(self.stop_item)
        self.resume_item = Gtk.MenuItem.new_with_label('Resume permission…')
        # A remote DBusMenu event must never clear the local Stop latch.
        self.resume_item.connect('activate', lambda *_: show_controls())
        self.menu.append(self.resume_item)
        controls = Gtk.MenuItem.new_with_label('Show controls')
        controls.connect('activate', lambda *_: show_controls())
        self.menu.append(controls)
        self.menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem.new_with_label('Stop and quit')
        quit_item.connect('activate', lambda *_: quit_controller())
        self.menu.append(quit_item)
        self.menu.show_all()
        self.indicator = Indicator.Indicator.new(f'linux-desktop-control-{os.getpid()}',
            'process-stop-symbolic', Indicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_title('Linux Desktop Control')
        self.indicator.set_menu(self.menu)
        self.indicator.connect('connection-changed', self.connection_changed)
        self.subscription = self.bus.signal_subscribe(WATCHER,
            'org.freedesktop.DBus.Properties', 'PropertiesChanged', WATCHER_PATH,
            WATCHER, Gio.DBusSignalFlags.NONE, self.host_changed)
        self.watch = Gio.bus_watch_name_on_connection(self.bus, WATCHER,
            Gio.BusNameWatcherFlags.NONE, lambda *_: None, self.watcher_lost)
        self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)

    @property
    def available(self):
        return self.connected and self.host_ready and not self.closed

    def connection_changed(self, _indicator, connected):
        was_available = self.available
        self.connected = connected
        if was_available and not self.available:
            self.unavailable()

    def host_changed(self, _bus, _sender, _path, _interface, _signal, parameters):
        interface, changed, invalidated = parameters.unpack()
        if interface != WATCHER:
            return
        was_available = self.available
        if 'IsStatusNotifierHostRegistered' in changed:
            self.host_ready = bool(changed['IsStatusNotifierHostRegistered'])
        elif 'IsStatusNotifierHostRegistered' in invalidated:
            self.host_ready = False
        if was_available and not self.available:
            self.unavailable()

    def watcher_lost(self, *_):
        was_available = self.available
        self.host_ready = False
        if was_available:
            self.unavailable()

    def update(self, active, latched):
        current = (active, latched)
        if current == self.previous:
            return
        self.previous = current
        label = ('Desktop control active' if active else
                 'Stopped · local Resume required' if latched else 'Ready for a new task')
        self.state.set_label(label)
        self.resume_item.set_sensitive(latched)
        self.indicator.set_icon_full('input-keyboard-symbolic' if active else
                                     'process-stop-symbolic', label)

    def close(self):
        self.closed = True
        Gio.bus_unwatch_name(self.watch)
        self.bus.signal_unsubscribe(self.subscription)
        self.indicator.set_status(self.api.IndicatorStatus.PASSIVE)


def create_tray(**callbacks):
    try:
        return TrayControls(**callbacks)
    except (ImportError, ValueError, RuntimeError, GLib.Error):
        return None
