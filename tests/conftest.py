import os
import tempfile

import pytest

os.environ.setdefault(
    "FLOWLINE_DATA_DIR", tempfile.mkdtemp(prefix="flowline-tests-")
)


@pytest.fixture(autouse=True)
def force_fake_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
