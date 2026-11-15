"""Shared fixtures.

Every test runs against `FakePaprika`: aioresponses intercepts all aiohttp requests,
so the real Paprika service is never contacted and nothing needs mocking per test.
pytest-homeassistant-custom-component's socket blocking is a second safety net.
"""

from collections.abc import AsyncIterator, Iterator
import re

from aioresponses import aioresponses
import pytest

from custom_components.paprika.api import PaprikaApi

from .fake_paprika import TOKEN, FakePaprika, refuse

PAPRIKA_URL = re.compile(r"^https://(www\.)?paprikaapp\.com/api/.*")
ANY_URL = re.compile(r".*")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/paprika in every test."""


@pytest.fixture(autouse=True)
def paprika() -> Iterator[FakePaprika]:
    """The fake Paprika account that every request in a test is served from."""
    fake = FakePaprika()
    with aioresponses() as mock:
        for method in ("GET", "POST", "PUT", "DELETE"):
            mock.add(PAPRIKA_URL, method=method, callback=_bind(fake, method), repeat=True)
            mock.add(ANY_URL, method=method, callback=refuse, repeat=True)
        yield fake


def _bind(fake: FakePaprika, method: str):
    return lambda url, **kwargs: fake.handle(url, method=method, **kwargs)


@pytest.fixture
async def client() -> AsyncIterator[PaprikaApi]:
    """A PaprikaApi client signed in to the fake account."""
    api = PaprikaApi(TOKEN)
    yield api
    await api.async_close()
