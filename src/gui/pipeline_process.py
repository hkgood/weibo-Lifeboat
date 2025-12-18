from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QProcess, Signal


@dataclass(frozen=True)
class PipelineLaunchSpec:
    config_path: Path
    phases: List[str]
    stop_after_no_new_pages: int = 3
    max_pages: int = 0  # 0 means unlimited (runner convention)
    detail_batch_size: int = 200
    detail_concurrency: int = 3
    retweet_threshold: int = 100
    antibot_cooldown_seconds: int = 1800
    antibot_max_cooldowns: int = 3


class PipelineProcess(QObject):
    """
    Runs `python -m src.pipeline.runner` as a subprocess and parses JSONL events from stdout.

    We use a subprocess (instead of in-process asyncio) so Cancel is easy and robust:
    just terminate/kill the child process.
    """

    started = Signal()
    finished = Signal(int)  # exit code
    log_line = Signal(str)  # stderr or non-json stdout lines
    event = Signal(dict)  # {"ts": ..., "event": ..., "data": {...}}

    def __init__(self) -> None:
        super().__init__()
        self._proc: Optional[QProcess] = None
        self._stdout_buf = b""
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def start(self, spec: PipelineLaunchSpec) -> None:
        if self._running:
            return

        proc = QProcess()
        proc.setProgram(sys.executable)

        args: List[str] = [
            "-m",
            "src.pipeline.runner",
            "--config",
            str(spec.config_path),
            "--phases",
            ",".join(spec.phases),
            "--stop-after-no-new-pages",
            str(spec.stop_after_no_new_pages),
            "--max-pages",
            str(spec.max_pages),
            "--detail-batch-size",
            str(spec.detail_batch_size),
            "--detail-concurrency",
            str(spec.detail_concurrency),
            "--retweet-threshold",
            str(spec.retweet_threshold),
            "--antibot-cooldown-seconds",
            str(spec.antibot_cooldown_seconds),
            "--antibot-max-cooldowns",
            str(spec.antibot_max_cooldowns),
            "--events-jsonl",
            "-",  # stdout
        ]
        proc.setArguments(args)

        proc.readyReadStandardOutput.connect(self._on_stdout)  # type: ignore[attr-defined]
        proc.readyReadStandardError.connect(self._on_stderr)  # type: ignore[attr-defined]
        proc.started.connect(self._on_started)  # type: ignore[attr-defined]
        proc.finished.connect(self._on_finished)  # type: ignore[attr-defined]

        self._proc = proc
        self._stdout_buf = b""
        self._running = True
        proc.start()

    def terminate(self) -> None:
        if not self._proc:
            return
        # Try graceful first; if it doesn't stop soon the UI can call kill().
        self._proc.terminate()

    def kill(self) -> None:
        if not self._proc:
            return
        self._proc.kill()

    def _on_started(self) -> None:
        self.started.emit()

    def _on_finished(self, exit_code: int, _status: Any) -> None:
        self._running = False
        self._proc = None
        self._stdout_buf = b""
        self.finished.emit(int(exit_code))

    def _on_stderr(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardError())
        if not data:
            return
        # Loguru defaults to stderr, so we show that as UI log.
        try:
            txt = data.decode("utf-8", errors="replace")
        except Exception:
            txt = str(data)
        for line in txt.splitlines():
            if line.strip():
                self.log_line.emit(line.rstrip())

    def _emit_stdout_line(self, line: bytes) -> None:
        b = line.strip()
        if not b:
            return
        try:
            payload = json.loads(b.decode("utf-8"))
            if isinstance(payload, dict) and "event" in payload:
                self.event.emit(payload)
                return
        except Exception:
            pass
        # Not JSONL (or parse failed) -> treat as log.
        try:
            self.log_line.emit(b.decode("utf-8", errors="replace"))
        except Exception:
            self.log_line.emit(str(b))

    def _on_stdout(self) -> None:
        if not self._proc:
            return
        chunk = bytes(self._proc.readAllStandardOutput())
        if not chunk:
            return
        self._stdout_buf += chunk
        while b"\n" in self._stdout_buf:
            line, self._stdout_buf = self._stdout_buf.split(b"\n", 1)
            self._emit_stdout_line(line)


