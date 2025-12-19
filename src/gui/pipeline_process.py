from __future__ import annotations

import json
import os
import sys
import threading
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
    Runs pipeline either as subprocess (dev) or in-thread (packaged).
    
    In packaged environment, modules are bundled and not accessible to external Python,
    so we run the pipeline in a separate thread instead of a subprocess.
    """

    started = Signal()
    finished = Signal(int)  # exit code
    log_line = Signal(str)  # stderr or non-json stdout lines
    event = Signal(dict)  # {"ts": ..., "event": ..., "data": {...}}

    def __init__(self) -> None:
        super().__init__()
        self._proc: Optional[QProcess] = None
        self._thread: Optional[threading.Thread] = None
        self._stdout_buf = b""
        self._running = False
        self._stop_requested = False

    def is_running(self) -> bool:
        return self._running

    def start(self, spec: PipelineLaunchSpec) -> None:
        if self._running:
            return

        self._stop_requested = False
        
        # 在打包环境中使用线程而非子进程（因为模块被打包无法被外部Python访问）
        if getattr(sys, 'frozen', False):
            self._running = True
            self.started.emit()
            
            # 在单独的线程中运行pipeline，避免阻塞GUI
            self._thread = threading.Thread(
                target=self._run_in_thread,
                args=(spec,),
                daemon=True
            )
            self._thread.start()
        else:
            # 开发环境：使用子进程（原有逻辑）
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
    
    def _run_in_thread(self, spec: PipelineLaunchSpec) -> None:
        """在线程中运行pipeline（仅用于打包环境）"""
        try:
            # 导入runner并运行
            from src.pipeline.runner import run_pipeline_from_gui
            
            # 运行pipeline，传入回调函数来发送事件
            exit_code = run_pipeline_from_gui(
                config_path=spec.config_path,
                phases=spec.phases,
                stop_after_no_new_pages=spec.stop_after_no_new_pages,
                max_pages=spec.max_pages,
                detail_batch_size=spec.detail_batch_size,
                detail_concurrency=spec.detail_concurrency,
                retweet_threshold=spec.retweet_threshold,
                antibot_cooldown_seconds=spec.antibot_cooldown_seconds,
                antibot_max_cooldowns=spec.antibot_max_cooldowns,
                event_callback=self._emit_event_from_thread,
                log_callback=self._emit_log_from_thread,
                should_stop=lambda: self._stop_requested
            )
        except Exception as e:
            self._emit_log_from_thread(f"[ERROR] Pipeline failed: {e}")
            import traceback
            self._emit_log_from_thread(traceback.format_exc())
            exit_code = 1
        finally:
            self._running = False
            self.finished.emit(exit_code)
    
    def _emit_event_from_thread(self, event_data: Dict[str, Any]) -> None:
        """从线程中安全地发送事件"""
        self.event.emit(event_data)
    
    def _emit_log_from_thread(self, message: str) -> None:
        """从线程中安全地发送日志"""
        self.log_line.emit(message)

    def terminate(self) -> None:
        if getattr(sys, 'frozen', False):
            # 打包环境：设置停止标志
            self._stop_requested = True
        else:
            # 开发环境：终止子进程
            if not self._proc:
                return
            self._proc.terminate()

    def kill(self) -> None:
        if getattr(sys, 'frozen', False):
            # 打包环境：强制设置停止标志
            self._stop_requested = True
            self._running = False
        else:
            # 开发环境：杀死子进程
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

