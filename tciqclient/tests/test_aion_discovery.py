"""Tests for AION-based orion-res discovery (IQ-PYTHON-002)."""
from unittest import mock

import pytest
import responses as responses_lib

from tciqrestclient.aion_discovery import (
    discover_via_aion,
    AION_ORION_RES_PORT_NAME,
    AION_DISCOVERY_TIMEOUT,
    _AionIAMSession,
)
from tciqrestclient.exceptions import IQConnectionError

AION = "https://aion.example.com"
_TOKEN_RESP = {
    "access_token": "tok-abc",
    "refresh_token": "ref-xyz",
    "expires_in": 3600,
}
_ORG_RESP = {"id": "org-1"}
_INSTANCES = [
    {
        "node": {"name": "node-a"},
        "ports": [
            {"name": "stcapi", "http": {"url": "http://10.0.0.1:8888"}},
            {"name": "iq", "http": {"url": "http://10.0.0.1:9200"}},
        ],
    }
]


def _register_happy_path(rsps, instances=None):
    rsps.add(
        responses_lib.GET,
        AION + "/api/iam/organizations/default",
        json=_ORG_RESP,
    )
    rsps.add(
        responses_lib.POST,
        AION + "/api/iam/oauth2/token",
        json=_TOKEN_RESP,
    )
    rsps.add(
        responses_lib.GET,
        AION + "/api/inv/product-instances",
        json=instances if instances is not None else _INSTANCES,
    )


@responses_lib.activate
def test_discover_returns_host_port_and_token():
    _register_happy_path(responses_lib)
    host, port, token = discover_via_aion(AION, "user@example.com", "pass")
    assert host == "10.0.0.1"
    assert port == 9200
    assert token == "tok-abc"


@responses_lib.activate
def test_discover_sends_bearer_token_to_product_instances():
    _register_happy_path(responses_lib)
    discover_via_aion(AION, "user@example.com", "pass")
    inv_call = responses_lib.calls[2]
    assert inv_call.request.headers.get("Authorization") == "Bearer tok-abc"


@responses_lib.activate
def test_discover_node_name_filter_selects_correct_instance():
    instances = [
        {
            "node": {"name": "node-a"},
            "ports": [
                {"name": "iq", "http": {"url": "http://192.168.1.1:9200"}},
            ],
        },
        {
            "node": {"name": "node-b"},
            "ports": [
                {"name": "iq", "http": {"url": "http://192.168.1.2:9200"}},
            ],
        },
    ]
    _register_happy_path(responses_lib, instances=instances)
    host, port, _ = discover_via_aion(
        AION, "user@example.com", "pass", node_name="node-b")
    assert host == "192.168.1.2"


@responses_lib.activate
def test_discover_custom_port_name():
    instances = [
        {
            "node": {},
            "ports": [
                {"name": "iq-service", "http": {"url": "http://10.0.0.5:9300"}},
            ],
        }
    ]
    _register_happy_path(responses_lib, instances=instances)
    host, port, _ = discover_via_aion(
        AION, "user@example.com", "pass", orion_res_port_name="iq-service")
    assert host == "10.0.0.5"
    assert port == 9300


@responses_lib.activate
def test_discover_no_matching_port_raises():
    instances = [
        {
            "node": {"name": "node-a"},
            "ports": [
                {"name": "stcapi", "http": {"url": "http://10.0.0.1:8888"}},
            ],
        }
    ]
    _register_happy_path(responses_lib, instances=instances)
    with pytest.raises(IQConnectionError, match="iq"):
        discover_via_aion(AION, "user@example.com", "pass")


@responses_lib.activate
def test_login_failure_raises():
    responses_lib.add(
        responses_lib.GET,
        AION + "/api/iam/organizations/default",
        json=_ORG_RESP,
    )
    responses_lib.add(
        responses_lib.POST,
        AION + "/api/iam/oauth2/token",
        status=401,
        body="Unauthorized",
    )
    with pytest.raises(IQConnectionError, match="login failed"):
        discover_via_aion(AION, "bad-user", "bad-pass")


@responses_lib.activate
def test_org_discovery_failure_raises():
    responses_lib.add(
        responses_lib.GET,
        AION + "/api/iam/organizations/default",
        status=503,
        body="Service Unavailable",
    )
    with pytest.raises(IQConnectionError, match="org discovery failed"):
        discover_via_aion(AION, "user@example.com", "pass")


@responses_lib.activate
def test_port_with_invalid_url_raises():
    instances = [
        {
            "node": {},
            "ports": [
                {"name": "iq", "http": {"url": "not-a-url"}},
            ],
        }
    ]
    _register_happy_path(responses_lib, instances=instances)
    with pytest.raises(IQConnectionError, match="invalid URL"):
        discover_via_aion(AION, "user@example.com", "pass")


# ---------------------------------------------------------------------------
# AION_ORION_RES_PORT_NAME -- CONFIRMED 'iq' 2026-09-08 against a real AION
# org (58 product-instances, 20+ carrying an 'iq' port, zero named
# 'orion-res' -- see HANDOVER.md section 9). Was wrongly 'orion-res' before.
# ---------------------------------------------------------------------------

def test_aion_orion_res_port_name_default_is_iq():
    assert AION_ORION_RES_PORT_NAME == "iq"


# ---------------------------------------------------------------------------
# IQ-PYTHON-002: Discovery timeout (configurable, default 120 s)
# ---------------------------------------------------------------------------

def test_aion_discovery_timeout_constant():
    """AION_DISCOVERY_TIMEOUT must equal 120.0 (spec default)."""
    assert AION_DISCOVERY_TIMEOUT == 120.0


def test_aion_session_default_timeout():
    """_AionIAMSession stores the default timeout."""
    session = _AionIAMSession(AION)
    assert session._timeout == AION_DISCOVERY_TIMEOUT


def test_aion_session_custom_timeout():
    """_AionIAMSession stores a caller-supplied timeout."""
    session = _AionIAMSession(AION, timeout=30.0)
    assert session._timeout == 30.0


@responses_lib.activate
def test_discover_passes_timeout_to_requests():
    """discover_via_aion propagates timeout= to every HTTP call."""
    _register_happy_path(responses_lib)
    with mock.patch("requests.get") as mock_get, \
         mock.patch("requests.post") as mock_post:
        # re-register so the mocked calls don't raise ConnectionError
        mock_get.return_value = mock.Mock(
            ok=True, json=mock.Mock(side_effect=[
                _ORG_RESP, _INSTANCES]))
        mock_post.return_value = mock.Mock(
            ok=True, json=mock.Mock(return_value=_TOKEN_RESP))
        discover_via_aion(AION, "user@example.com", "pass", timeout=5.0)
    for call in mock_get.call_args_list:
        assert call.kwargs.get("timeout") == 5.0
    for call in mock_post.call_args_list:
        assert call.kwargs.get("timeout") == 5.0


@responses_lib.activate
def test_discover_default_timeout_is_120_seconds():
    """When timeout= is not given, 120.0 is used for all HTTP calls."""
    _register_happy_path(responses_lib)
    with mock.patch("requests.get") as mock_get, \
         mock.patch("requests.post") as mock_post:
        mock_get.return_value = mock.Mock(
            ok=True, json=mock.Mock(side_effect=[
                _ORG_RESP, _INSTANCES]))
        mock_post.return_value = mock.Mock(
            ok=True, json=mock.Mock(return_value=_TOKEN_RESP))
        discover_via_aion(AION, "user@example.com", "pass")
    for call in mock_get.call_args_list:
        assert call.kwargs.get("timeout") == 120.0
    for call in mock_post.call_args_list:
        assert call.kwargs.get("timeout") == 120.0
