import threading
from typing import Optional
from app.models.schemas import JobProgress, JobStatus


class JobStore:
    """Thread-safe in-memory job store."""

    def __init__(self):
        self._jobs: dict[str, JobProgress] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, total_images: int = 0) -> JobProgress:
        job = JobProgress(
            job_id=job_id,
            status=JobStatus.PENDING,
            total_images=total_images,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[JobProgress]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[JobProgress]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            return job

    def delete(self, job_id: str):
        with self._lock:
            self._jobs.pop(job_id, None)


job_store = JobStore()
