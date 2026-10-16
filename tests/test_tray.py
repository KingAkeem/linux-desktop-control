"""Tray visibility and local-permission regressions. No desktop input."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from linux_desktop_control.backend import runtime_dir
from linux_desktop_control.controller import Controller
from linux_desktop_control.tray import TrayControls
from linux_desktop_control import tray


def controller(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    c = Controller.__new__(Controller)
    c.backend = Mock(active=False, target=42)
    c.hotkeys = Mock()
    c.hotkeys.pending_events.return_value = 0
    c.label, c.resume, c.window = Mock(), Mock(), Mock()
    c.tray = Mock(available=True)
    c.panel_requested = False
    c.running = True
    c.ui_mode = 'panel'
    return c


def test_available_tray_hides_panel_during_control(monkeypatch, tmp_path):
    c = controller(monkeypatch, tmp_path)
    c.backend.active = True
    assert c.tick()
    c.window.hide.assert_called_once()
    c.window.show.assert_not_called()
    c.tray.update.assert_called_once_with(True, False)
    assert c.ui_mode == 'tray'


def test_tray_request_cannot_grant_resume_permission(monkeypatch, tmp_path):
    c = controller(monkeypatch, tmp_path)
    latch = runtime_dir()/'stopped'
    latch.write_bytes(b'local permission required')
    c.show_controls()
    c.backend.stop.assert_called_once_with(latch=True)
    c.window.show_all.assert_called_once()
    assert c.panel_requested and latch.read_bytes() == b'local permission required'
    c.tick()
    c.window.hide.assert_not_called()


def test_local_resume_hides_panel_without_starting_input(monkeypatch, tmp_path):
    c = controller(monkeypatch, tmp_path)
    latch = runtime_dir()/'stopped'
    latch.touch()
    c.panel_requested = True
    c.resume_local()
    assert not latch.exists() and not c.panel_requested
    c.window.hide.assert_called_once()
    c.backend.start.assert_not_called()


def test_closing_tray_panel_latches_stop_and_keeps_controller(monkeypatch, tmp_path):
    c = controller(monkeypatch, tmp_path)
    c.shutdown = Mock()
    assert c.close_window() is True
    c.backend.stop.assert_called_once_with(latch=True)
    c.window.hide.assert_called_once()
    c.shutdown.assert_not_called()


def test_tray_loss_stops_before_showing_fallback_panel(monkeypatch, tmp_path):
    c = controller(monkeypatch, tmp_path)
    calls = Mock()
    calls.attach_mock(c.backend.stop, 'stop')
    calls.attach_mock(c.window.show_all, 'show')
    c.tray_unavailable()
    assert [call[0] for call in calls.mock_calls] == ['stop', 'show']
    c.backend.stop.assert_called_once_with(latch=True)
    assert c.panel_requested


@pytest.mark.parametrize('indicator', [None, SimpleNamespace(available=False)])
def test_missing_tray_keeps_panel_visible(monkeypatch, tmp_path, indicator):
    c = controller(monkeypatch, tmp_path)
    c.tray = indicator
    c.tick()
    c.window.show.assert_called_once()
    c.window.hide.assert_not_called()
    assert c.ui_mode == 'panel'


def indicator():
    t = TrayControls.__new__(TrayControls)
    t.connected = t.host_ready = True
    t.closed = False
    t.unavailable = Mock()
    return t


def test_indicator_disconnect_is_not_silent():
    t = indicator()
    t.connection_changed(None, False)
    assert not t.available
    t.unavailable.assert_called_once()


@pytest.mark.parametrize('changed,invalidated', [
    ({'IsStatusNotifierHostRegistered': False}, []),
    ({}, ['IsStatusNotifierHostRegistered'])])
def test_host_loss_or_unknown_state_reports_unavailable(changed, invalidated):
    t = indicator()
    parameters = SimpleNamespace(unpack=lambda: (tray.WATCHER, changed, invalidated))
    t.host_changed(None, None, None, None, None, parameters)
    assert not t.available
    t.unavailable.assert_called_once()


def test_watcher_loss_reports_unavailable():
    t = indicator()
    t.watcher_lost()
    assert not t.available
    t.unavailable.assert_called_once()


def test_optional_tray_failure_falls_back(monkeypatch):
    monkeypatch.setattr(tray, 'TrayControls', Mock(side_effect=ValueError('Missing optional typelib')))
    assert tray.create_tray() is None


def test_optional_binding_does_not_disable_panel_mode(monkeypatch):
    import gi
    from linux_desktop_control import cli
    backend = Mock()
    backend.status.return_value = {'compatible': True, 'locked': False, 'stop_latched': False}
    backend.d.has_extension.return_value = True
    monkeypatch.setattr(cli, 'Backend', lambda: backend)
    monkeypatch.setattr(cli.shutil, 'which', lambda _: '/usr/bin/gdbus')
    original = gi.require_version
    def require(name, version):
        if name == 'AyatanaAppIndicator3':
            raise ValueError('Optional typelib unavailable')
        return original(name, version)
    monkeypatch.setattr(gi, 'require_version', require)
    result = cli.doctor()
    assert result['compatible'] and result['gtk_available']
    assert not result['tray_binding_available']
