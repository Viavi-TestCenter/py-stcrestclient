"""Shared pytest fixtures. HTTP is mocked with `responses` so tests never
touch a real network or orion-res server.
"""
import pytest
import responses as responses_lib

BASE_URL = "http://fake-orion-res:9200"


@pytest.fixture
def mocked_responses():
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def iq_client(monkeypatch):
    """A connected IQClient with a fixed base_url, environment isolated so
    stray TCIQ_* variables or a real .env file on the machine running the
    tests never leak in."""
    for var in ("TCIQ_BASE_URL", "TCIQ_HOST", "TCIQ_PORT", "TCIQ_INSTALL_DIR",
                "TCIQ_DATABASE_ID", "TCIQ_TIMEOUT", "TCIQ_DEBUG",
                "TCIQ_AION_URL", "TCIQ_AION_USERNAME", "TCIQ_AION_PASSWORD",
                "TCIQ_AION_NODE_NAME", "TCIQ_AION_PORT_NAME", "TCIQ_AION_CA_CERT"):
        monkeypatch.delenv(var, raising=False)

    from tciqrestclient import IQClient
    return IQClient(base_url=BASE_URL, load_env=False)
