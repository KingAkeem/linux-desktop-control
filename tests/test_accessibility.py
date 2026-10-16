"""Observation isolation, scoping, privacy, and failure regressions. No desktop input."""
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from linux_desktop_control import accessibility as ax
from linux_desktop_control import accessibility_server as service


class Node:
    def __init__(self, name='fixture', role='frame', children=(), pid=42, text='example'):
        self.name, self.role, self.children, self.pid, self.text = name, role, list(children), pid, text

    def get_name(self):
        assert self.role != 'password text', 'password name must not be read'
        return self.name

    def get_description(self):
        assert self.role != 'password text', 'password description must not be read'
        return ''

    def get_role_name(self): return self.role
    def get_process_id(self): return self.pid
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, i): return self.children[i]
    def get_state_set(self): return SimpleNamespace(contains=lambda state: state == 'VISIBLE')
    def get_component_iface(self): return self
    def get_extents(self, *_): return SimpleNamespace(x=10, y=10, width=100, height=100)
    def get_text_iface(self): return self
    def get_text(self, start, end): return self.text[start:end]
    def get_character_count(self): return len(self.text)


API = SimpleNamespace(CoordType=SimpleNamespace(SCREEN=0),
                      Text=SimpleNamespace(get_character_count=lambda node: node.get_character_count(),
                                           get_text=lambda node, start, end: node.get_text(start, end)),
                      StateType=SimpleNamespace(**{name: name for name in
                          ('VISIBLE', 'SHOWING', 'FOCUSED', 'EDITABLE', 'ENABLED', 'SELECTED')}))
CONTEXT = {'pid': 42, 'title': 'fixture', 'bounds': [10, 10, 100, 100]}


@pytest.mark.parametrize('values', [(True, 1, 1, False), (0, 1, 1, False),
    (1, 0, 1, False), (1, 501, 1, False), (1, 1, 33, False), (1, 1, 1, 'yes')])
def test_invalid_requests_never_start_reader(monkeypatch, values):
    reader = Mock()
    monkeypatch.setattr(service, 'observe', reader)
    result = asyncio.run(service.accessibility_tree(*values))
    assert result.is_error
    reader.assert_not_called()


@pytest.mark.parametrize('payload', [{'operation': 'click'}, {'operation': 'setup'},
    {'operation': 'activate_window'}, {'operation': 'resume'}, {'command': 'shell'},
    {'window_id': 1, 'max_nodes': 2, 'max_depth': 3, 'include_text': False, 'action': 'click'}])
def test_no_mutation_passthrough(monkeypatch, payload):
    reader = Mock(side_effect=AssertionError('AT-SPI must not start'))
    monkeypatch.setattr(ax, 'atspi_api', reader)
    assert 'error' in ax.worker(payload)
    reader.assert_not_called()


def test_target_requires_pid_title_and_geometry():
    target = Node()
    desktop = Node(children=[Node(children=[Node('unrelated')], pid=99), Node(children=[target])])
    assert ax.selected_frame(desktop, CONTEXT, API, time.monotonic()+1) is target
    for context in [dict(CONTEXT, pid=2), dict(CONTEXT, title='other'), dict(CONTEXT, bounds=[900,900,100,100])]:
        with pytest.raises(ax.ObservationError, match='unique accessible frame'):
            ax.selected_frame(desktop, context, API, time.monotonic()+1)


def test_duplicate_frames_fail_without_broadening():
    desktop = Node(children=[Node(children=[Node(), Node()])])
    with pytest.raises(ax.ObservationError, match='unique'):
        ax.selected_frame(desktop, CONTEXT, API, time.monotonic()+1)


def test_unrelated_app_names_and_descendants_are_not_read():
    unrelated = Node(pid=99)
    unrelated.get_name = Mock(side_effect=AssertionError('private app name'))
    unrelated.get_child_count = Mock(side_effect=AssertionError('private children'))
    target = Node()
    assert ax.selected_frame(Node(children=[unrelated, Node(children=[target])]), CONTEXT,
                             API, time.monotonic()+1) is target
    unrelated.get_name.assert_not_called()
    unrelated.get_child_count.assert_not_called()


def test_bounded_discovery_never_reads_children_past_limit():
    desktop = Node(children=[Node()]*257)
    desktop.get_child_at_index = Mock()
    with pytest.raises(ax.ObservationError, match='bound'):
        ax.selected_frame(desktop, CONTEXT, API, time.monotonic()+1)
    desktop.get_child_at_index.assert_not_called()


def test_node_depth_text_and_password_limits():
    secret = Node(name='secret-name', role='password text', text='secret-password', children=[Node('hidden-secret')])
    root = Node(children=[Node('x'*1000, role='text', text='y'*1000), secret])
    result = ax.read_tree(root, API, 10, 10, False, time.monotonic()+1)
    assert all('text' not in row for row in result['nodes'])
    result = ax.read_tree(root, API, 10, 10, True, time.monotonic()+1)
    assert len(result['nodes']) == 3
    assert len(result['nodes'][1]['name']) == ax.MAX_FIELD
    assert result['nodes'][1]['text_truncated']
    assert result['nodes'][2]['redacted']
    assert 'secret' not in json.dumps(result)
    assert ax.read_tree(root, API, 1, 10, False, time.monotonic()+1)['truncated']
    shallow = ax.read_tree(root, API, 10, 0, False, time.monotonic()+1)
    assert len(shallow['nodes']) == 1 and shallow['truncated']


def test_large_and_cyclic_trees_are_bounded():
    root = Node()
    root.children = [root]*2000
    result = ax.read_tree(root, API, 20, 32, False, time.monotonic()+1)
    assert len(result['nodes']) == 20 and result['truncated']
    assert all(row['parent_index'] is None or row['parent_index'] < row['index'] for row in result['nodes'])


def test_text_interface_failure_preserves_the_node():
    node = Node()
    node.get_character_count = Mock(side_effect=RuntimeError('unavailable'))
    result = ax.read_tree(node, API, 10, 10, True, time.monotonic()+1)
    assert len(result['nodes']) == 1
    assert result['nodes'][0]['name'] == 'fixture'
    assert result['nodes'][0]['text_unavailable']
    assert result['read_errors'] == 1


@pytest.mark.parametrize('role', ['menu', 'menu bar', 'tool bar'])
def test_hidden_controls_do_not_crowd_out_document_text(role):
    hidden = Node(name='hidden command')
    hidden.get_name = Mock(side_effect=AssertionError('hidden command content must not be read'))
    opened = Node(name='open command')
    opened.get_state_set = lambda: SimpleNamespace(contains=lambda state: state in ('VISIBLE', 'SHOWING'))
    menu = Node(role=role, children=[hidden]*10+[opened])
    document = Node(role='document text', children=[Node(role='paragraph', text='real document')])
    result = ax.read_tree(Node(children=[menu, document]), API, 20, 16, True, time.monotonic()+1)
    assert any(row.get('text') == 'real document' for row in result['nodes'])
    assert any(row.get('name') == 'open command' for row in result['nodes'])
    assert result['omitted_hidden_controls'] == 10
    assert result['truncated'] and result['read_errors'] == 0
    hidden.get_name.assert_not_called()


def test_byte_limit_is_valid_json_with_visible_truncation():
    result = {'nodes': [{'index': i, 'name': '\u2603'*256} for i in range(200)], 'truncated': False}
    data = ax.encode_result(result)
    assert len(data) <= ax.MAX_BYTES
    decoded = json.loads(data)
    assert decoded['truncated'] and decoded['nodes']


def test_target_changes_discard_tree(monkeypatch):
    monkeypatch.setattr(ax, 'require_unlocked', lambda: None)
    monkeypatch.setattr(ax, 'window_context', Mock(side_effect=[CONTEXT, dict(CONTEXT, title='changed')]))
    monkeypatch.setattr(ax, 'atspi_api', lambda: SimpleNamespace(get_desktop=lambda _: None))
    monkeypatch.setattr(ax, 'selected_frame', lambda *_: None)
    monkeypatch.setattr(ax, 'read_tree', lambda *_: {'nodes': [{'name': 'discard me'}]})
    with pytest.raises(ax.ObservationError, match='target changed'):
        ax.snapshot(1)


@pytest.mark.parametrize('output', ['(true,)', 'unknown'])
def test_locked_or_unknown_does_not_read_atspi(monkeypatch, output):
    monkeypatch.setattr(ax.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(returncode=0, stdout=output))
    reader = Mock()
    monkeypatch.setattr(ax, 'atspi_api', reader)
    with pytest.raises(ax.ObservationError, match='lock'):
        ax.snapshot(1)
    reader.assert_not_called()


def test_registration_preserves_input_server_and_round_trips(tmp_path):
    p = tmp_path/'config.toml'
    before = '# Keep me\nmodel="existing"\n[mcp_servers.linux-desktop-control]\ncommand="original-launch"\n'
    p.write_text(before)
    assert service.configure(config_path=p)['registered']
    assert before in p.read_text()
    assert not service.configure(config_path=p)['changed']
    assert not service.configure(remove=True, config_path=p)['registered']
    assert p.read_text().strip() == before.strip()


def test_registration_refuses_unrelated_companion(tmp_path):
    p = tmp_path/'config.toml'
    before = '[mcp_servers.linux-desktop-accessibility]\ncommand="unrelated"\n'
    p.write_text(before)
    with pytest.raises(ax.ObservationError, match='unrelated'):
        service.configure(config_path=p)
    assert p.read_text() == before


def test_only_observation_tools_are_exposed():
    async def run():
        tools = await service.server.list_tools()
        assert {tool.name for tool in tools} == {'accessibility_status', 'accessibility_tree'}
        assert all(tool.annotations.read_only_hint and not tool.annotations.destructive_hint for tool in tools)
    asyncio.run(run())


def test_timeout_and_cancellation_reap_helper(monkeypatch):
    class Input:
        def write(self, _): pass
        async def drain(self): pass
        def close(self): pass

    class Process:
        returncode = None
        stdin = Input()
        def __init__(self): self.stdout = self
        async def read(self, _): await asyncio.Event().wait()
        def kill(self): self.returncode = -9
        async def wait(self): return self.returncode

    async def run():
        processes = []
        async def spawn(*_a, **_k):
            process = Process()
            processes.append(process)
            return process
        monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', spawn)
        monkeypatch.setattr(service, 'HELPER_TIMEOUT', 0.01)
        result = await service.observe({'operation': 'probe'})
        assert 'timed out' in result['error'] and processes[-1].returncode == -9
        monkeypatch.setattr(service, 'HELPER_TIMEOUT', 10)
        task = asyncio.create_task(service.observe({'operation': 'probe'}))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert processes[-1].returncode == -9
        assert not service.busy.locked()
    asyncio.run(run())


def test_stop_state_is_observed_without_reset(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    root = tmp_path/'linux-desktop-control'
    root.mkdir()
    latch = root/'stopped'
    latch.write_bytes(b'unchanged')
    assert ax.stop_latched()
    assert latch.read_bytes() == b'unchanged'
