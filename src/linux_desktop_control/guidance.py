"""Install shared desktop routing without changing unrelated user instructions."""
import os
from pathlib import Path
import tempfile

from .backend import DesktopError
from .paths import skill_source

START = '<!-- linux-desktop-control:start -->'
END = '<!-- linux-desktop-control:end -->'


def configure_guidance(remove=False, codex_home=None, check_only=False):
    home = Path(codex_home or os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    source = skill_source()
    target = home/'skills/linux-desktop-control'
    instructions = home/'AGENTS.md'
    skill_path = target/'SKILL.md'
    block = f'''{START}
## Linux desktop applications and games

For requests to inspect or operate native desktop apps on this Linux machine, use the globally configured `linux-desktop-control` MCP and read `{skill_path}`. Select it automatically for desktop UI tasks, including Steam games, when the task calls for graphical interaction. The separate integration provides screenshots, window selection, keyboard and mouse input, and Stop controls even when the built-in native computer-use provider is unavailable on Linux. Continue using existing browser tools and direct connectors where appropriate.

Control shares my keyboard and pointer. Announce the start, act within the requested task, verify screenshots, and stop when finished. Physical input stops automation; a local Stop latch requires me to click Resume permission. Do not bypass it. If this chat lacks the tools, check for an MCP reload or app restart rather than claiming the capability does not exist. This configuration applies to local chats using this machine and profile, not cloud-only chats or other hosts.
{END}'''
    before = instructions.read_text() if instructions.exists() else ''
    if (before.count(START) != before.count(END) or before.count(START) > 1
            or (START in before and before.index(END) < before.index(START))):
        raise DesktopError('Shared desktop instructions have ambiguous markers; left unchanged.')
    if (target.exists() or target.is_symlink()) and (not target.is_symlink() or target.resolve() != source):
        raise DesktopError('A different skill occupies this path; left unchanged.')
    if not remove and not (source/'SKILL.md').is_file():
        raise DesktopError('Packaged desktop skill is missing.')
    if check_only:
        return {}
    if START in before:
        begin = before.index(START)
        finish = before.index(END, begin) + len(END)
        if remove:
            begin -= int(begin > 0 and before[begin-1] == '\n')
            finish += int(finish < len(before) and before[finish] == '\n')
            after = before[:begin] + before[finish:]
        else:
            after = before[:begin] + block + before[finish:]
    else:
        after = before if remove else before + ('\n' if before.endswith('\n') else '\n\n' if before else '') + block + '\n'
    if not remove:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source, target_is_directory=True)
    elif target.is_symlink():
        target.unlink()
    if after != before:
        home.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=home, prefix='.desktop-guidance-')
        try:
            os.fchmod(fd, instructions.stat().st_mode & 0o777 if instructions.exists() else 0o600)
            with os.fdopen(fd, 'w') as out:
                out.write(after)
            if instructions.exists() and instructions.read_text() != before:
                raise DesktopError('Shared instructions changed concurrently; retry registration.')
            os.replace(temporary, instructions)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return {'skill_installed': not remove, 'global_guidance_installed': not remove}
