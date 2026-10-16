"""Explicit read-only live checks against the companion's disposable fixture.

Start tests/accessibility_fixture.py with a state JSON path, then pass that
path here. No input is sent and the production Stop latch is never reset.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from mcp import Client, StdioServerParameters
from Xlib import X, display

ROOT = Path(__file__).resolve().parents[1]


def desktop_state():
    d = display.Display()
    try:
        root = d.screen().root
        focused = root.get_full_property(d.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
        pointer = root.query_pointer()
        latch = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))/'linux-desktop-control/stopped'
        return {'focus': int(focused.value[0]) if focused is not None else None,
                'pointer': [pointer.root_x, pointer.root_y, pointer.mask],
                'stop_latched': latch.exists(),
                'stop_contents': latch.read_bytes().hex() if latch.exists() else None}
    finally:
        d.close()


async def run(state_path):
    state = json.loads(state_path.read_text())
    output = ROOT/'output/accessibility'
    output.mkdir(parents=True, exist_ok=True)
    before = desktop_state()
    config_path = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'config.toml'
    config_before = config_path.read_bytes()
    results = []
    async with Client(StdioServerParameters(command=sys.executable,
        args=['-m', 'linux_desktop_control.accessibility_server', 'serve'], env=dict(os.environ))) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {'accessibility_status', 'accessibility_tree'}
        assert all(t.annotations.read_only_hint for t in tools)
        async def read(**options):
            started = time.monotonic()
            result = await client.call_tool('accessibility_tree', dict(window_id=state['window_id'], **options))
            data = json.loads(next(c.text for c in result.content if c.type == 'text'))
            assert not result.is_error, data
            results.append({'options': options, 'seconds': round(time.monotonic()-started, 3),
                            'nodes': len(data['nodes']), 'read_errors': data['read_errors'],
                            'truncated': data['truncated']})
            return data
        ordinary = await read()
        assert all('text' not in n for n in ordinary['nodes'])
        expanded = await read(include_text=True)
        serialized = json.dumps(expanded)
        assert 'PASSWORD_MUST_NOT_LEAK_86527' not in serialized
        assert 'OTHER_WINDOW_MUST_NOT_LEAK_94631' not in serialized
        assert any(n.get('redacted') and n['role'] == 'password text' for n in expanded['nodes'])
        assert any(n.get('text') == state['text'] for n in expanded['nodes']), expanded
        assert expanded['read_errors'] == 0 and not expanded['truncated']
        tiny = await read(max_nodes=1)
        assert tiny['truncated'] and len(tiny['nodes']) == 1
        shallow = await read(max_depth=0)
        assert shallow['truncated'] and len(shallow['nodes']) == 1
        missing = await client.call_tool('accessibility_tree', {'window_id': 1})
        assert missing.is_error
        (output/'snapshot.json').write_text(json.dumps(expanded, indent=2))
    after = desktop_state()
    assert before == after, {'before': before, 'after': after, 'note': 'Physical user activity can also change this state.'}
    assert config_path.read_bytes() == config_before
    result = {'result': 'passed', 'checks': ['exact window scoping', 'same-process other window excluded',
        'password redaction', 'text opt-in', 'node limit', 'depth limit', 'invalid target refused',
        'unchanged focus', 'unchanged pointer', 'unchanged Stop latch', 'unchanged client config',
        'observation-only MCP discovery'], 'reads': results, 'desktop_state': before}
    (output/'read-checks.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    asyncio.run(run(Path(sys.argv[1])))
