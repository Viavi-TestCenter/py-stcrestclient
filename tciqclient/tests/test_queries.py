"""POST /queries -- one request/response per query, no WAMP/live mode."""
import responses as responses_lib

import fixtures
from tciqrestclient import queries
from tciqrestclient.exceptions import IQQueryError
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


def test_run_query_posts_expected_body(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    result = queries.run_query(
        Transport(BASE), "n43grmtulrhgnkae", fixtures.QUERY_DEFINITION)
    assert result == fixtures.QUERY_RESPONSE

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["database"] == {"id": "n43grmtulrhgnkae", "name": ""}
    assert sent_body["mode"] == "once"
    assert sent_body["datastore"] == {"id": ""}
    assert sent_body["definition"] == fixtures.QUERY_DEFINITION


def test_run_query_custom_mode_and_datastore(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    queries.run_query(
        Transport(BASE), "db-1", fixtures.QUERY_DEFINITION,
        mode="active", datastore_id="ds-1")

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["mode"] == "active"
    assert sent_body["datastore"] == {"id": "ds-1"}


def test_run_query_passes_timeout_override(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    from unittest import mock
    t = Transport(BASE)
    with mock.patch.object(t, "post", wraps=t.post) as spy:
        queries.run_query(
            t, "db-1", fixtures.QUERY_DEFINITION, timeout=120)
    assert spy.call_args.kwargs["timeout"] == 120


def test_run_query_requires_database_id():
    try:
        queries.run_query(Transport(BASE), "", fixtures.QUERY_DEFINITION)
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass


def test_run_query_requires_definition():
    try:
        queries.run_query(Transport(BASE), "db-1", None)
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass
