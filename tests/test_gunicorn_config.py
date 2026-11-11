import importlib.util
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parent.parent / "docker" / "gunicorn_config.py"


def load():
    spec = importlib.util.spec_from_file_location("gunicorn_config_under_test", CONFIG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_defaults_to_four_workers(monkeypatch):
    monkeypatch.delenv("NWORKERS", raising=False)
    assert load().workers == 4


def test_blank_value_uses_the_default(monkeypatch):
    monkeypatch.setenv("NWORKERS", " ")
    assert load().workers == 4


def test_reads_nworkers(monkeypatch):
    monkeypatch.setenv("NWORKERS", "1")
    assert load().workers == 1


@pytest.mark.parametrize("value", ["0", "-2", "many", "1.5"])
def test_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("NWORKERS", value)
    with pytest.raises(SystemExit):
        load()
