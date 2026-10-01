"""Thin HTTP transport: root paths, JSON in/out, no auth headers."""
from unittest import mock

import requests
import responses as responses_lib

from tciqrestclient.exceptions import IQRequestError
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


def test_get_json(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", json=[{"id": "a"}])
    t = Transport(BASE)
    assert t.get("/databases") == [{"id": "a"}]


def test_post_json_sends_body(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json={"id": "q1"})
    t = Transport(BASE)
    result = t.post("/queries", json_body={"mode": "once"})
    assert result == {"id": "q1"}
    sent = mocked_responses.calls[0].request
    assert sent.body is not None
    assert b'"mode": "once"' in sent.body or b'"mode":"once"' in sent.body


def test_put(mocked_responses):
    mocked_responses.add(
        responses_lib.PUT, BASE + "/views/1", json={"id": "1"})
    t = Transport(BASE)
    assert t.put("/views/1", json_body={"name": "x"}) == {"id": "1"}


def test_delete_no_content(mocked_responses):
    mocked_responses.add(responses_lib.DELETE, BASE + "/views/1", status=204)
    t = Transport(BASE)
    assert t.delete("/views/1") is None


def test_get_raw_bytes(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/1/download",
        body=b"%PDF-fake", content_type="application/pdf")
    t = Transport(BASE)
    assert t.get_raw("/reports/1/download") == b"%PDF-fake"


def test_no_auth_header_sent(mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/version", json={})
    Transport(BASE).get("/version")
    sent = mocked_responses.calls[0].request
    assert "Authorization" not in sent.headers


def test_calls_go_to_root_path_not_api_res(mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/databases", json=[])
    Transport(BASE).get("/databases")
    sent = mocked_responses.calls[0].request
    assert "/api/res/" not in sent.url


def test_error_status_raises(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", status=500, body="boom")
    t = Transport(BASE)
    try:
        t.get("/databases")
        assert False, "expected IQRequestError"
    except IQRequestError as e:
        assert "500" in str(e)


def test_connection_error_raises(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        body=requests.exceptions.ConnectionError("refused"))
    t = Transport(BASE)
    try:
        t.get("/databases")
        assert False, "expected IQRequestError"
    except IQRequestError:
        pass


def test_non_json_response_raises(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", body="not json",
        content_type="text/plain")
    t = Transport(BASE)
    try:
        t.get("/databases")
        assert False, "expected IQRequestError"
    except IQRequestError:
        pass


def test_default_timeout_used_when_not_overridden():
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, timeout=10, session=session).get("/databases")
    assert session.request.call_args.kwargs["timeout"] == 10


def test_per_call_timeout_overrides_default():
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, timeout=10, session=session).get(
        "/databases", timeout=120)
    assert session.request.call_args.kwargs["timeout"] == 120


def test_per_call_timeout_on_post():
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, timeout=10, session=session).post(
        "/queries", json_body={"a": 1}, timeout=90)
    assert session.request.call_args.kwargs["timeout"] == 90


def test_verify_omitted_by_default(mocked_responses):
    # None (the default) must NOT be passed through as verify=None --
    # `requests` would treat an explicit None differently from simply
    # never passing the kwarg in some edge cases, and more importantly a
    # caller-supplied session's own `.verify` setting (e.g. verify=False
    # for a self-signed lab cert, set directly on the session before
    # passing it in) must be left alone rather than silently overridden.
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, session=session).get("/databases")
    assert "verify" not in session.request.call_args.kwargs


def test_verify_false_passed_through():
    # CONFIRMED real scenario 2026-09-22: a lab deployment with a
    # self-signed HTTPS certificate.
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, verify=False, session=session).get("/databases")
    assert session.request.call_args.kwargs["verify"] is False


def test_verify_ca_bundle_path_passed_through():
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        ok=True, content=b"{}", json=lambda: {})
    Transport(BASE, verify="/etc/ssl/lab-ca.pem", session=session).get(
        "/databases")
    assert session.request.call_args.kwargs["verify"] == "/etc/ssl/lab-ca.pem"


def test_debug_off_prints_nothing(mocked_responses, capsys):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json={"id": "q1"})
    Transport(BASE, debug=False).post("/queries", json_body={"a": 1})
    assert capsys.readouterr().out == ""


def test_debug_prints_method_url_and_body(mocked_responses, capsys):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json={"id": "q1"})
    Transport(BASE, debug=True).post(
        "/queries", json_body={"mode": "once"})
    out = capsys.readouterr().out
    assert "-> POST " + BASE + "/queries" in out
    assert '"mode": "once"' in out
    assert "<- POST " + BASE + "/queries -> 200" in out


def test_debug_prints_params(mocked_responses, capsys):
    mocked_responses.add(responses_lib.GET, BASE + "/databases", json=[])
    Transport(BASE, debug=True).get(
        "/databases", params={"detail": "full"})
    out = capsys.readouterr().out
    assert '"detail": "full"' in out


def test_debug_prints_failure_on_request_exception(mocked_responses, capsys):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        body=requests.exceptions.ConnectionError("refused"))
    t = Transport(BASE, debug=True)
    try:
        t.get("/databases")
    except IQRequestError:
        pass
    out = capsys.readouterr().out
    assert "-> GET " + BASE + "/databases" in out
    assert "FAILED" in out


def test_debug_shows_effective_timeout(mocked_responses, capsys):
    mocked_responses.add(responses_lib.GET, BASE + "/databases", json=[])
    Transport(BASE, timeout=10, debug=True).get(
        "/databases", timeout=90)
    out = capsys.readouterr().out
    assert "timeout=90" in out
