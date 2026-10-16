"""Locate resources in a source checkout or an installed distribution."""
from pathlib import Path
import sys


def checkout():
    root = Path(__file__).resolve().parents[2]
    return root if (root / 'pyproject.toml').is_file() and (root / 'launch').is_file() else None


def skill_source():
    root = checkout()
    if root is not None:
        return root / 'skills/linux-desktop-control'
    return Path(sys.prefix) / 'share/linux-desktop-control/skills/linux-desktop-control'


def launch_command():
    root = checkout()
    if root is not None:
        return {'command': str(root / 'launch')}
    return {'command': sys.executable, 'args': ['-m', 'linux_desktop_control.cli', 'serve']}
