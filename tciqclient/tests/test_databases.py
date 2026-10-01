"""Tests (= databases) listing and owner filtering, against the real
captured GET /databases?detail=summary shape."""
import responses as responses_lib

import fixtures
from tciqrestclient import databases
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


def test_list_tests_returns_all_by_default(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = databases.list_tests(Transport(BASE))
    assert len(result) == len(fixtures.DATABASES_RESPONSE)


def test_list_tests_sends_detail_param(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    databases.list_tests(Transport(BASE), detail="full")
    sent = mocked_responses.calls[0].request
    assert "detail=full" in sent.url


def test_list_tests_filters_by_owner_client_side(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = databases.list_tests(Transport(BASE), owner="user")
    assert all(
        t["metadata"].get("test.owner") == "user" for t in result)
    assert len(result) == 2  # Qbv_Qbu... and SpirentIQ_demo_run_10streams


def test_list_tests_filters_by_specific_owner(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = databases.list_tests(
        Transport(BASE), owner="vinod.shelke@viavisolutions.com")
    assert len(result) == 1
    assert result[0]["id"] == "cwcmford7nag7d7v"


def test_list_tests_excludes_no_owner_when_filtering(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = databases.list_tests(Transport(BASE), owner="user")
    ids = [t["id"] for t in result]
    assert "bqfuklujp5f7rg52" not in ids  # stcuserdb -- no test.owner at all


def test_get_test(mocked_responses):
    db = fixtures.DATABASES_RESPONSE[1]
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases/" + db["id"], json=db)
    result = databases.get_test(Transport(BASE), db["id"])
    assert result["id"] == db["id"]
