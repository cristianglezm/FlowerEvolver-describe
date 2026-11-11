import os
from prometheus_client import multiprocess  # noqa: F401


def _workers():
    """Number of gunicorn workers: NWORKERS, 4 when it is not set (the previous fixed value).

    Every worker loads its own copy of the ONNX models (~800 MB each), so set NWORKERS=1 on a
    small host. Kafka messages are consumed by one worker only (a single consumer group and
    auto-created topics have one partition), extra workers only add REST capacity.
    """
    raw = os.environ.get("NWORKERS", "").strip()
    if not raw:
        return 4
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"NWORKERS must be a positive integer, got {raw!r}")
    if value < 1:
        raise SystemExit(f"NWORKERS must be a positive integer, got {raw!r}")
    return value


workers = _workers()


def post_worker_exit(server, worker):
    prom_dir = os.environ.get("prometheus_multiproc_dir")
    if prom_dir and os.path.isdir(prom_dir):
        worker_metric_file = os.path.join(prom_dir, f"gauge_live_{worker.pid}.db")
        if os.path.exists(worker_metric_file):
            os.remove(worker_metric_file)
