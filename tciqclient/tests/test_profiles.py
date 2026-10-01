"""Result profiles (/profiles), against the real captured shape -- see
tciqrestclient/profiles.py's module docstring for the confirmed real
detail=/view_id= query-param behavior this mirrors.
"""
from unittest import mock

import responses as responses_lib

import fixtures
from tciqrestclient import profiles
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


def test_list_profiles(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/profiles", json=[fixtures.PROFILE])
    result = profiles.list_profiles(Transport(BASE))
    assert result == [fixtures.PROFILE]


def test_list_profiles_empty(mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/profiles", json=None)
    assert profiles.list_profiles(Transport(BASE)) == []


def test_list_profiles_no_params_by_default(mocked_responses):
    """Neither view_id= nor detail= given -- no query params sent at all,
    same as views.list_views(), letting the server apply its own default
    (confirmed real: full detail)."""
    mocked_responses.add(
        responses_lib.GET, BASE + "/profiles", json=[fixtures.PROFILE])
    transport = Transport(BASE)
    with mock.patch.object(transport, "get", wraps=transport.get) as spy:
        profiles.list_profiles(transport)
    assert spy.call_args.kwargs.get("params") is None


def test_list_profiles_detail_param_reaches_transport(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/profiles", json=[fixtures.PROFILE])
    transport = Transport(BASE)
    with mock.patch.object(transport, "get", wraps=transport.get) as spy:
        profiles.list_profiles(transport, detail="summary")
    assert spy.call_args.kwargs["params"] == {"detail": "summary"}


def test_list_profiles_view_id_param_reaches_transport(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/profiles", json=[fixtures.PROFILE])
    transport = Transport(BASE)
    with mock.patch.object(transport, "get", wraps=transport.get) as spy:
        profiles.list_profiles(
            transport, view_id="1b368e0a247d48aba94f319f8e120dcc")
    assert spy.call_args.kwargs["params"] == {
        "view_id": "1b368e0a247d48aba94f319f8e120dcc"}


def test_list_profiles_both_params_reach_transport(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/profiles", json=[fixtures.PROFILE])
    transport = Transport(BASE)
    with mock.patch.object(transport, "get", wraps=transport.get) as spy:
        profiles.list_profiles(
            transport, view_id="view-1", detail="full")
    assert spy.call_args.kwargs["params"] == {
        "view_id": "view-1", "detail": "full"}


def test_list_profiles_timeout_override_reaches_transport(mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/profiles", json=[])
    transport = Transport(BASE)
    with mock.patch.object(transport, "get", wraps=transport.get) as spy:
        profiles.list_profiles(transport, timeout=45)
    assert spy.call_args.kwargs["timeout"] == 45
