import os

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = 1  # the collector caches per process; one worker keeps DB load bounded
threads = 4
worker_class = "gthread"
timeout = 30
graceful_timeout = 10
worker_tmp_dir = "/dev/shm"  # noqa: S108 - tmpfs heartbeat files
control_socket_disable = True
errorlog = "-"
