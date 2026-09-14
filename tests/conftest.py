import asyncio

import pytest

from configuration.settings import Settings
from operations.initialize import initialize


@pytest.fixture
def settings(tmp_path):
    settings = Settings(data_dir=tmp_path)
    asyncio.run(initialize(settings))
    return settings
