import json
import threading
import time
from unittest.mock import Mock

import pytest
from linux_desktop_control.backend import Backend, DesktopError, SessionLock
from linux_desktop_control.cli import configure


def fake_backend():
    b = Backend.__new__(Backend)
    b.target = 42
    b.geometry = Mock(return_value=(100,200,800,600))
    b.monitors = Mock(return_value=[{'width':3440,'height':1440}])
    b.captures = {'a': ({'origin':[100,200], 'width':800, 'height':600}, b.geometry(), b.monitors(), time.monotonic())}
    return b


def test_native_coordinates():
    b=fake_backend()
    assert b.point('a',799,599)==(899,799)
    for x,y in [(-1,0),(800,0),(0,600),(True,4)]:
        with pytest.raises(DesktopError): b.point('a',x,y)


def test_capture_invalidated_by_window_movement_or_monitor_change():
    b=fake_backend()
    b.geometry.return_value=(101,200,800,600)
    with pytest.raises(DesktopError,match='Stale'): b.point('a',10,10)
    b=fake_backend()
    b.monitors.return_value=[{'width':1920,'height':1080}]
    with pytest.raises(DesktopError,match='Stale'): b.point('a',10,10)


def test_desktop_capture_cannot_target_other_windows():
    b=fake_backend()
    meta,geom,monitors,at=b.captures['a']
    meta.update(origin=[0,0],width=3440,height=1440)
    with pytest.raises(DesktopError,match='selected window'): b.point('a',0,0)


def test_expired_and_unknown_captures():
    b=fake_backend()
    with pytest.raises(DesktopError): b.point('missing',1,1)
    meta,geom,monitors,_=b.captures['a']
    b.captures['a']=(meta,geom,monitors,time.monotonic()-61)
    with pytest.raises(DesktopError,match='Stale'): b.point('a',1,1)


def test_focus_and_cancellation():
    b=fake_backend()
    b.cancel=threading.Event()
    b.active=True
    b.deadline=float('inf')
    b.active_window=Mock(return_value=99)
    with pytest.raises(DesktopError,match='focus'): b.check()
    b.cancel.set()
    with pytest.raises(DesktopError,match='stopped'): b.check()


@pytest.mark.parametrize('action_request',[
    {'kind':'shell'}, {'kind':'drag','duration':float('nan')}, {'kind':'drag','duration':99},
    {'kind':'type','text':'x'*201}, {'kind':'paste','text':'x'*4001},
    {'kind':'scroll','steps':100}, {'kind':'key','keys':[]}, {'kind':'click','button':'invalid'}])
def test_validation_before_any_input(action_request):
    b=fake_backend()
    with pytest.raises(DesktopError): b.action(action_request)


def test_exclusive_controller(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR',str(tmp_path))
    first,second=SessionLock(),SessionLock()
    first.acquire()
    try:
        with pytest.raises(DesktopError): second.acquire()
    finally: first.close()
    second.acquire()
    second.close()


def test_register_and_uninstall_preserve_existing_configuration(tmp_path):
    p=tmp_path/'config.toml'
    before='# Keep this comment\nmodel = "existing"\n[mcp_servers.existing]\ncommand = "existing-command"\n'
    p.write_text(before)
    configure(config_path=p)
    assert p.read_text().startswith(before)
    assert not configure(config_path=p)['changed']
    configure(remove=True,config_path=p)
    assert p.read_text().strip()==before.strip()


def test_register_refuses_unrelated_server(tmp_path):
    p=tmp_path/'config.toml'
    before='[mcp_servers.linux-desktop-control]\ncommand="unrelated"\n'
    p.write_text(before)
    with pytest.raises(DesktopError): configure(config_path=p)
    assert p.read_text()==before


def test_locked_or_unknown_lock_status_stops_before_input(monkeypatch):
    import linux_desktop_control.backend as module
    for locked in (True,None):
        b=fake_backend()
        b.stop=Mock()
        monkeypatch.setattr(module,'lock_state',lambda:locked)
        with pytest.raises(DesktopError,match='locked'):
            b.action({'kind':'click'})
        b.stop.assert_called_once()


def test_stop_latch_and_epoch_cancel_pending_start(tmp_path,monkeypatch):
    from linux_desktop_control.backend import runtime_dir
    monkeypatch.setenv('XDG_RUNTIME_DIR',str(tmp_path))
    b=fake_backend()
    b.mutex=threading.RLock()
    b.cancel=threading.Event()
    b.epoch=2
    with pytest.raises(DesktopError,match='cancelled'): b.start(42,expected_epoch=1)
    (runtime_dir()/'stopped').touch()
    with pytest.raises(DesktopError,match='latched'): b.start(42,expected_epoch=2)


def test_clipboard_supported_formats_and_rich_content_rejection():
    from linux_desktop_control.clipboard import preservation_kind
    assert preservation_kind({'UTF8_STRING','TARGETS'})=='text'
    assert preservation_kind({'image/png','TARGETS'})=='image'
    assert preservation_kind(set())=='text'
    with pytest.raises(ValueError): preservation_kind({'text/html','UTF8_STRING'})
    with pytest.raises(ValueError): preservation_kind({'application/octet-stream'})


def test_clipboard_never_overwrites_new_user_copy(monkeypatch):
    from linux_desktop_control.clipboard import Holder
    import linux_desktop_control.clipboard as module
    holder=Holder.__new__(Holder)
    holder.cb=Mock()
    holder.d=Mock()
    holder.d.get_selection_owner.return_value.id=20
    holder.atom=1
    holder.owner=10
    holder.restored=False
    holder.changed=True
    holder.old='previous'
    holder.kind='text'
    monkeypatch.setattr(module.Gtk,'main_quit',lambda:None)
    holder.restore()
    holder.cb.set_text.assert_not_called()
    holder.cb.set_image.assert_not_called()


def test_clipboard_restores_original_text(monkeypatch):
    from linux_desktop_control.clipboard import Holder
    holder=Holder.__new__(Holder)
    holder.cb=Mock()
    holder.d=Mock()
    holder.d.get_selection_owner.return_value.id=10
    holder.atom=1
    holder.owner=10
    holder.restored=False
    holder.changed=False
    holder.old='previous'
    holder.kind='text'
    holder.restore()
    holder.cb.set_text.assert_called_once_with('previous',-1)


def test_physical_input_stops_control_but_xtest_does_not():
    from types import SimpleNamespace
    import struct
    from linux_desktop_control.controller import Controller
    from Xlib.ext import xinput
    c=Controller.__new__(Controller)
    c.backend=Mock()
    c.backend.cancel.is_set.return_value=False
    c.synthetic_devices={4,5}
    c.xinput_opcode=131
    c.last_physical_input=0
    def raw(source):
        data=bytearray(22)
        struct.pack_into('=H',data,10,source)
        return SimpleNamespace(type=35,extension=131,evtype=xinput.RawKeyPress,data=bytes(data))
    c.handle_input(raw(5))
    c.backend.stop.assert_not_called()
    c.handle_input(raw(8))
    c.backend.stop.assert_called_once_with(latch=True)
    assert c.last_physical_input>0


def test_watchdog_unknown_lock_state_stops(monkeypatch):
    from linux_desktop_control.controller import Controller
    import linux_desktop_control.controller as module
    c=Controller.__new__(Controller)
    c.backend=Mock()
    c.backend.active=True
    c.running=True
    c.heartbeat=time.monotonic()
    monkeypatch.setattr(module,'lock_state',lambda:None)
    def finish(_): c.running=False
    monkeypatch.setattr(module.time,'sleep',finish)
    c.watchdog()
    c.backend.stop.assert_called_once_with(latch=True)


def test_failed_ledger_replace_preserves_recoverable_state(tmp_path,monkeypatch):
    from pathlib import Path
    from linux_desktop_control.backend import runtime_dir
    monkeypatch.setenv('XDG_RUNTIME_DIR',str(tmp_path))
    p=runtime_dir()/'held.json'
    p.write_text('[["button", 1]]')
    b=fake_backend()
    b.held=[('button',1),('key',50)]
    def interrupted(*_): raise OSError('simulated interruption')
    monkeypatch.setattr(Path,'replace',interrupted)
    with pytest.raises(OSError): b.record_held()
    assert json.loads(p.read_text())==[['button',1]]


def test_cancelled_mcp_request_stops_controller(monkeypatch):
    import asyncio
    import linux_desktop_control.server as module
    stopped=threading.Event()
    entered=threading.Event()
    def call(*_):
        entered.set()
        stopped.wait(timeout=2)
        return {'active':False}
    monkeypatch.setattr(module.bridge,'call',call)
    monkeypatch.setattr(module.bridge,'close',stopped.set)
    async def check():
        task=asyncio.create_task(module.invoke('action',{'kind':'type','text':'test'}))
        while not entered.is_set(): await asyncio.sleep(.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert stopped.is_set()
    asyncio.run(check())


def test_shared_guidance_round_trip_and_repeated_install(tmp_path):
    from linux_desktop_control.guidance import configure_guidance
    instructions=tmp_path/'AGENTS.md'
    before='My existing instructions.\n'
    instructions.write_text(before)
    configure_guidance(codex_home=tmp_path)
    installed=instructions.read_text()
    assert installed.startswith(before)
    assert (tmp_path/'skills/linux-desktop-control/SKILL.md').is_file()
    configure_guidance(codex_home=tmp_path)
    assert instructions.read_text()==installed
    instructions.write_text(installed+'\nAdditional unrelated guidance.\n')
    configure_guidance(remove=True,codex_home=tmp_path)
    assert instructions.read_text()==before+'\nAdditional unrelated guidance.\n'
    assert not (tmp_path/'skills/linux-desktop-control').is_symlink()


def test_shared_guidance_preserves_conflicting_skill(tmp_path):
    from linux_desktop_control.guidance import configure_guidance
    existing=tmp_path/'skills/linux-desktop-control'
    existing.mkdir(parents=True)
    with pytest.raises(DesktopError,match='different skill'):
        configure_guidance(codex_home=tmp_path)
    assert existing.is_dir()
    assert not (tmp_path/'AGENTS.md').exists()
