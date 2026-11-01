from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    id: str
    project_id: str
    design_id: str
    events: queue.Queue = field(default_factory=queue.Queue)
    status: str = "queued"
    done: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    cancel_requested: threading.Event = field(default_factory=threading.Event)

    def emit(self, event: dict[str, Any] | None) -> None:
        self.events.put(event)

    def request_cancel(self) -> None:
        self.cancel_requested.set()


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, project_id: str, design_id: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], project_id=project_id, design_id=design_id)
        with self._lock:
            self.jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.request_cancel()
        return True

    def start(self, job: Job, work) -> None:
        def runner() -> None:
            job.status = "running"
            try:
                work(job)
            except Exception as exc:  # pragma: no cover - defensive boundary
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.emit({"type": "error", "message": job.error})
            finally:
                job.done = True
                job.emit(None)

        thread = threading.Thread(target=runner, daemon=True, name=f"flowline-{job.id}")
        thread.start()

    def stream(self, job: Job):
        while True:
            try:
                event = job.events.get(timeout=20)
            except queue.Empty:
                yield ": keepalive\n\n"
                if job.done:
                    break
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"
