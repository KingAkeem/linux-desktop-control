import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import tomlkit
from .backend import Backend, DesktopError
from .paths import launch_command

SERVER_NAME = 'linux-desktop-control'


def configure(remove=False, config_path=None):
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    path = Path(config_path) if config_path is not None else home/'config.toml'
    path.parent.mkdir(parents=True, exist_ok=True)
    guard = path.parent / '.linux-desktop-control-config.lock'
    with guard.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        before = path.read_text() if path.exists() else ''
        document = tomlkit.parse(before)
        if remove and SERVER_NAME not in document.get('mcp_servers', {}):
            return {'changed': False, 'registered': False}
        servers = document.setdefault('mcp_servers', tomlkit.table())
        expected = launch_command()
        existing = servers.get(SERVER_NAME)
        if existing is not None and any(existing.get(key, []) != expected.get(key, []) for key in ('command', 'args')):
            raise DesktopError('An unrelated server already uses this name; configuration was not changed.')
        if remove:
            servers.pop(SERVER_NAME, None)
        else:
            servers[SERVER_NAME] = {**expected, 'startup_timeout_sec': 15, 'tool_timeout_sec': 30,
                                    'env_vars': ['DISPLAY', 'XAUTHORITY', 'XDG_SESSION_TYPE',
                                                 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS']}
        after = tomlkit.dumps(document)
        if before == after:
            return {'changed': False, 'registered': not remove}
        # Refuse to overwrite any concurrent app edit.
        if path.exists() and path.read_text() != before:
            raise DesktopError('Configuration changed concurrently; retry registration.')
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.desktop-config-')
        try:
            os.fchmod(fd, path.stat().st_mode & 0o777 if path.exists() else 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(after)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    return {'changed': True, 'registered': not remove, 'reload_required': True}


def doctor():
    """Check dependencies and desktop readiness without starting input control."""
    value = {'compatible': False, 'session_type': os.environ.get('XDG_SESSION_TYPE'),
             'python_supported': sys.version_info >= (3, 12), 'gtk_available': False,
             'gdbus_available': shutil.which('gdbus') is not None, 'xinput2_available': False}
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk  # noqa: F401
        value['gtk_available'] = True
    except (ImportError, ValueError):
        pass
    try:
        b = Backend()
        try:
            value.update(b.status())
            value['xinput2_available'] = b.d.has_extension('XInputExtension')
        finally:
            b.d.close()
    except Exception:
        value['message'] = 'X11 display or required extensions unavailable.'
    value['compatible'] = all((value.get('compatible'), value['python_supported'],
                               value['gtk_available'], value['gdbus_available'], value['xinput2_available']))
    value['ready_for_control'] = value['compatible'] and value.get('locked') is False and not value.get('stop_latched', False)
    return value


def register(remove=False):
    from .guidance import configure_guidance
    # Detect skill conflicts before changing the MCP configuration.
    configure_guidance(remove=remove, check_only=True)
    result = configure(remove=remove)
    result.update(configure_guidance(remove=remove))
    return result


def main():
    parser = argparse.ArgumentParser(description='Local X11 desktop control')
    parser.add_argument('command', choices=['serve', 'doctor', 'register', 'uninstall'])
    args = parser.parse_args()
    if args.command == 'serve':
        from .server import main as serve
        serve()
    elif args.command == 'doctor':
        value = doctor()
        print(json.dumps(value, indent=2))
        raise SystemExit(0 if value['compatible'] else 1)
    else:
        try:
            print(json.dumps(register(remove=args.command == 'uninstall')))
        except DesktopError as exc:
            print(json.dumps({'error': str(exc)}), file=sys.stderr)
            raise SystemExit(1) from None


if __name__ == '__main__':
    main()
