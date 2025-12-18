from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


@dataclass
class PipelineEventSink:
    """
    A tiny JSONL event emitter for UI integration.

    - Each line is a single JSON object.
    - Intended to be consumed by a GUI (e.g. SwiftUI) to render progress.
    - When disabled, emit() is a cheap no-op.
    """

    fp: Optional[TextIO]

    @staticmethod
    def disabled() -> "PipelineEventSink":
        return PipelineEventSink(fp=None)

    @staticmethod
    def from_target(target: Optional[str]) -> "PipelineEventSink":
        """
        target:
          - None/"" -> disabled
          - "-" -> stdout
          - otherwise -> append to file path
        """
        if not target:
            return PipelineEventSink.disabled()
        if target == "-":
            return PipelineEventSink(fp=sys.stdout)
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        # line-buffered for near realtime UI updates
        f = p.open("a", encoding="utf-8", buffering=1)
        return PipelineEventSink(fp=f)

    def close(self) -> None:
        try:
            if self.fp and self.fp not in (sys.stdout, sys.stderr):
                self.fp.close()
        except Exception:
            # Best-effort; never fail the pipeline for UI concerns.
            pass

    def emit(self, event: str, **data: Any) -> None:
        if not self.fp:
            return
        payload: Dict[str, Any] = {
            "ts": time.time(),
            "event": event,
            "data": data,
        }
        try:
            self.fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.fp.flush()
        except Exception:
            # Best-effort; never fail the pipeline for UI concerns.
            return


