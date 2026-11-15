import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaomi1c.api.app import create_app  # noqa: E402
from xiaomi1c.secrets_store import SecretStore  # noqa: E402
from xiaomi1c.services.core import AppCore  # noqa: E402
from xiaomi1c.settings import SettingsStore  # noqa: E402
from xiaomi1c.storage.db import Database  # noqa: E402


@pytest.fixture
def core(tmp_path):
    (tmp_path / "maps").mkdir()
    c = AppCore(SettingsStore(tmp_path / "config.json"), SecretStore(use_keyring=False), Database(tmp_path / "t.db"), tmp_path)
    c.settings_store.update(sim_time_scale=200.0)
    c.reconfigure()
    yield c
    c.stop()


@pytest.fixture
def client(core):
    from fastapi.testclient import TestClient

    app = create_app(core)
    with TestClient(app, headers={"X-Xiaomi1C": "1"}) as tc:
        yield tc
