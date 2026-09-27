"""Gunicorn configuration (read automatically from the working directory)."""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = 30
graceful_timeout = 25  # below the pod's terminationGracePeriodSeconds
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
worker_tmp_dir = "/dev/shm"  # noqa: S108 - tmpfs heartbeat files, avoids disk-backed /tmp stalls
accesslog = None  # the app emits structured access logs
errorlog = "-"
control_socket_disable = True  # read-only root filesystem; the control interface is unused


def child_exit(server, worker):
    """Drop per-process metric files of dead workers (prometheus multiprocess mode)."""
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
