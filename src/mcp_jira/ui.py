"""Shared Rich consoles for the interactive setup/install flows (design D1/D2).

``console`` writes to stdout (prompts, summaries, success); ``error_console``
writes to stderr (styled errors). ``highlight=False`` keeps user-supplied
values plain; markup stays enabled so values passed through
``rich.markup.escape`` render literally. Both consoles bind ``sys.stdout`` /
``sys.stderr`` lazily at each write, so pytest ``capsys`` captures their output
and non-TTY runs carry no ANSI codes.

The non-TTY branches of ``run_wizard``/``run_installer`` never touch these
consoles (design D8); they keep plain ``print()`` byte-identical.
"""

from __future__ import annotations

from rich.console import Console

console = Console(highlight=False)
error_console = Console(stderr=True, highlight=False)
