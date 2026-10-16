"""Registration and distribution regressions; never start desktop input."""
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
import tomlkit

from linux_desktop_control import cli, paths
from linux_desktop_control.backend import DesktopError
from linux_desktop_control.guidance import configure_guidance


def test_custom_home_registration_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))
    config = tmp_path/'config.toml'
    config.write_text('# Keep this\nmodel = "existing"\n')
    instructions = tmp_path/'AGENTS.md'
    instructions.write_text('Existing guidance.\n')
    assert cli.register()['registered']
    assert 'linux-desktop-control' in tomlkit.parse(config.read_text())['mcp_servers']
    assert not cli.register()['changed']
    assert not cli.register(remove=True)['registered']
    assert 'existing' in config.read_text()
    assert instructions.read_text() == 'Existing guidance.\n'


def test_conflicting_skill_does_not_change_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))
    config = tmp_path/'config.toml'
    original = 'model = "keep-me"\n'
    config.write_text(original)
    (tmp_path/'skills/linux-desktop-control').mkdir(parents=True)
    with pytest.raises(DesktopError, match='different skill'):
        cli.register()
    assert config.read_text() == original
    assert not (tmp_path/'AGENTS.md').exists()


def test_conflicting_server_does_not_install_guidance(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path))
    config = tmp_path/'config.toml'
    original = '[mcp_servers.linux-desktop-control]\ncommand = "other"\n'
    config.write_text(original)
    with pytest.raises(DesktopError, match='unrelated server'):
        cli.register()
    assert config.read_text() == original
    assert not (tmp_path/'skills/linux-desktop-control').exists()


def test_wheel_registration_command(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'checkout', lambda: None)
    config = tmp_path/'config.toml'
    cli.configure(config_path=config)
    server = tomlkit.parse(config.read_text())['mcp_servers']['linux-desktop-control']
    assert server['command'] == paths.sys.executable
    assert server['args'] == ['-m', 'linux_desktop_control.cli', 'serve']
    assert not cli.configure(config_path=config)['changed']
    assert not cli.configure(remove=True, config_path=config)['registered']


def test_wheel_skill_location(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'checkout', lambda: None)
    monkeypatch.setattr(paths.sys, 'prefix', str(tmp_path))
    assert paths.skill_source() == tmp_path/'share/linux-desktop-control/skills/linux-desktop-control'


def test_reversed_guidance_markers_are_preserved(tmp_path):
    from linux_desktop_control.guidance import START, END
    original = f'{END}\nKeep this\n{START}\n'
    (tmp_path/'AGENTS.md').write_text(original)
    with pytest.raises(DesktopError, match='ambiguous markers'):
        configure_guidance(codex_home=tmp_path)
    assert (tmp_path/'AGENTS.md').read_text() == original


def test_doctor_fails_closed_without_display(monkeypatch):
    monkeypatch.setattr(cli, 'Backend', Mock(side_effect=DesktopError('Unavailable')))
    result = cli.doctor()
    assert not result['compatible']
    assert not result['ready_for_control']


def test_doctor_checks_gtk_not_just_x11(monkeypatch):
    import sys
    backend = Mock()
    backend.status.return_value = {'compatible': True, 'locked': False, 'stop_latched': False}
    backend.d.has_extension.return_value = True
    monkeypatch.setattr(cli, 'Backend', lambda: backend)
    monkeypatch.setattr(cli.shutil, 'which', lambda _: '/usr/bin/gdbus')
    monkeypatch.setitem(sys.modules, 'gi', None)
    result = cli.doctor()
    assert not result['gtk_available']
    assert not result['compatible']
    assert not result['ready_for_control']
    backend.d.close.assert_called_once()


def test_installer_rejects_unknown_arguments_before_changes():
    install = Path(__file__).resolve().parents[1]/'install'
    result = subprocess.run(['sh', str(install), '--unknown'], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'Usage:' in result.stderr
