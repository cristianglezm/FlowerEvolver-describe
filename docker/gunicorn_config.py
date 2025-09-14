import os
from prometheus_client import multiprocess  # noqa: F401


def post_worker_exit(server, worker):
    prom_dir = os.environ.get("prometheus_multiproc_dir")
    if prom_dir and os.path.isdir(prom_dir):
        worker_metric_file = os.path.join(prom_dir, f"gauge_live_{worker.pid}.db")
        if os.path.exists(worker_metric_file):
            os.remove(worker_metric_file)
