"""Thin subprocess wrapper over the OpenKB CLI.

playmaker invokes OpenKB as a black box (the ``openkb`` console script) rather
than importing its internals. This is the most non-invasive coupling and keeps
the layer robust across OpenKB version bumps (design.md D1, "keep the layer
non-invasive ... bump deliberately"). All LLM-heavy operations (ingest,
query, lint, recompile, remove) are OpenKB's; playmaker only reads the
resulting wiki files afterward.

The KB to operate on is selected via the ``OPENKB_DIR`` environment variable,
which OpenKB honors as a KB-root override.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from playmaker.paths import KB


class EngineError(RuntimeError):
    """OpenKB could not be invoked, or returned a non-zero exit code."""


@dataclass
class EngineResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def openkb_available() -> bool:
    return shutil.which("openkb") is not None


def _run(
    args: list[str],
    *,
    kb_root: Path | None = None,
    check: bool = True,
    stream: bool = False,
    input_text: str | None = None,
) -> EngineResult:
    if not openkb_available():
        raise EngineError(
            "The `openkb` engine is not installed. Install playmaker with its "
            "dependencies (which pin OpenKB), e.g. `pip install -e .`."
        )
    env = dict(os.environ)
    if kb_root is not None:
        env["OPENKB_DIR"] = str(Path(kb_root).resolve())

    cmd = ["openkb", *args]
    if stream:
        # Inherit stdio so the user sees OpenKB's live progress/streaming.
        proc = subprocess.run(cmd, env=env, input=input_text, text=True)
        result = EngineResult(proc.returncode, "", "")
    else:
        proc = subprocess.run(
            cmd, env=env, input=input_text, text=True, capture_output=True
        )
        result = EngineResult(proc.returncode, proc.stdout or "", proc.stderr or "")
    if check and not result.ok:
        raise EngineError(
            f"`openkb {' '.join(args)}` failed (exit {result.returncode}).\n"
            f"{result.stderr or result.stdout}"
        )
    return result


def init(kb_root: Path, *, model: str | None = None, language: str = "en") -> EngineResult:
    """Run ``openkb init`` in ``kb_root``.

    Pipes empty stdin so OpenKB's interactive prompts fall back to defaults
    when not overridden by flags (its ``_stdin_is_tty`` guard skips prompts on
    piped input).
    """
    kb_root = Path(kb_root)
    kb_root.mkdir(parents=True, exist_ok=True)
    args = ["init"]
    if model:
        args += ["--model", model]
    args += ["--language", language]
    # init writes into cwd, so run it with cwd=kb_root rather than OPENKB_DIR.
    if not openkb_available():
        raise EngineError("The `openkb` engine is not installed.")
    proc = subprocess.run(
        ["openkb", *args], cwd=str(kb_root), input="\n\n\n", text=True,
        capture_output=True,
    )
    res = EngineResult(proc.returncode, proc.stdout or "", proc.stderr or "")
    if not res.ok:
        raise EngineError(f"`openkb init` failed (exit {res.returncode}).\n{res.stderr or res.stdout}")
    return res


def add(kb: KB, source: str, *, stream: bool = True) -> EngineResult:
    """Ingest + compile a source (file, directory, or URL)."""
    return _run(["add", source], kb_root=kb.root, stream=stream)


def query(kb: KB, question: str, *, save: bool = False) -> EngineResult:
    args = ["query", question]
    if save:
        args.append("--save")
    # Non-streaming so we can return the answer text to the caller.
    return _run(args, kb_root=kb.root, stream=False)


def lint(kb: KB, *, stream: bool = True) -> EngineResult:
    return _run(["lint"], kb_root=kb.root, stream=stream, check=False)


def remove(kb: KB, identifier: str, *, yes: bool = True, stream: bool = True) -> EngineResult:
    args = ["remove", identifier]
    if yes:
        args.append("--yes")
    return _run(args, kb_root=kb.root, stream=stream)


def list_docs(kb: KB) -> EngineResult:
    return _run(["list"], kb_root=kb.root, stream=False, check=False)
