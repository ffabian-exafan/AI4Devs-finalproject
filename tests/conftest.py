"""Fixture compartida de pytest."""

import pytest

from app.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def _limpiar_cache_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
