"""Integration tests through the public IQClient facade -- exercises the
full step 1-4 flow from PLAN.md (discovery is covered separately in
test_discovery.py/test_config.py; here the base_url is given directly)."""
import json
import os

import pytest
import responses as responses_lib

import fixtures
from tciqrestclient.exceptions import IQQueryError, IQViewError

BASE = "http://fake-orion-res:9200"
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_data(filename):
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(
            "tests/data/%s is a real orion-res capture that isn't checked "
            "into this repo -- see HANDOVER.md section 9" % filename)
    with open(path) as f:
        return json.load(f)


def test_repr_and_base_url(iq_client):
    assert iq_client.base_url == BASE
    assert BASE in repr(iq_client)


def test_debug_true_reaches_transport_and_prints(mocked_responses, capsys):
    from tciqrestclient import IQClient
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", json=[])
    iq = IQClient(base_url=BASE, load_env=False, debug=True)
    iq.list_tests()
    out = capsys.readouterr().out
    assert "-> GET " + BASE + "/databases" in out


def test_debug_defaults_off(iq_client, mocked_responses, capsys):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", json=[])
    iq_client.list_tests()
    assert capsys.readouterr().out == ""


def test_list_tests(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = iq_client.list_tests()
    assert len(result) == len(fixtures.DATABASES_RESPONSE)


def test_list_tests_by_owner(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=fixtures.DATABASES_RESPONSE)
    result = iq_client.list_tests(owner="user")
    assert len(result) == 2


def test_use_test_then_get_test(iq_client, mocked_responses):
    db = fixtures.DATABASES_RESPONSE[1]
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases/" + db["id"], json=db)
    iq_client.use_test(db["id"])
    result = iq_client.get_test()
    assert result["id"] == db["id"]


def test_get_test_requires_default_or_explicit_id(iq_client):
    try:
        iq_client.get_test()
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass


def test_query_by_view_name_without_effective_details_raises(
        iq_client, mocked_responses):
    # fixtures.VIEW is a real (trimmed) `details` shape, but was captured
    # without effective_details.system_data.query_providers -- the
    # templates get_view_definition()/tciqrestclient.view_query_builder need to
    # build an executable query. See
    # test_query_by_view_name_builds_and_runs_real_query below for the
    # happy path against a real view export that does include them.
    mocked_responses.add(
        responses_lib.GET, BASE + "/views", json=[fixtures.VIEW])
    iq_client.use_test("n43grmtulrhgnkae")

    try:
        iq_client.query(name="Detailed Stream Results")
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "query_provider" in str(e)


def test_query_by_view_name_builds_and_runs_real_query(
        iq_client, mocked_responses):
    # End-to-end happy path: a real view export (with effective_details
    # intact) -> build_query_definition() -> merge_modifiers(limit=120)
    # produces exactly the real captured request body (see
    # test_view_query_builder.py for the same check in isolation); this
    # test additionally confirms it flows correctly through query(name=,
    # data_type=) end-to-end via the fake HTTP layer.
    view = _load_data("view_detailed_stream_results.json")
    expected_definition = _load_data(
        "dsr_query_unfiltered.json")["definition"]
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(
        name="Detailed Stream Results", data_type="eot", limit=120)

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["definition"] == expected_definition


def test_query_by_view_name_filter_accepts_display_name(
        iq_client, mocked_responses):
    # Vinod: filters should accept the GUI column label ("Rx Count"), not
    # just the internal alias ("rx_stream_stats_frame_count").
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(
        name="Detailed Stream Results", data_type="eot",
        filters=[("Rx Count", "gt", 100000)], sort="Rx Count DESC")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert "view.rx_stream_stats_frame_count>100000" in node["filters"]
    assert node["orders"][-1] == "view.rx_stream_stats_frame_count DESC"


def test_list_view_columns_via_client(iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])

    columns = iq_client.list_view_columns(
        "Detailed Stream Results", data_type="eot")
    by_name = {c["name"]: c for c in columns}
    assert by_name["rx_stream_stats.frame_count"]["display_name"] == (
        "Rx Count")


def test_query_by_view_name_timeout_reaches_views_lookup(
        iq_client, mocked_responses):
    from unittest import mock
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    with mock.patch.object(
            iq_client._transport, "get",
            wraps=iq_client._transport.get) as spy:
        iq_client.query(
            name="Detailed Stream Results", data_type="eot", timeout=45)
    assert spy.call_args.kwargs["timeout"] == 45


def test_query_auto_repair_strips_unknown_attribute_and_retries(
        iq_client, mocked_responses):
    # Real scenario reported by Vinod: the view's query_provider template
    # references an attribute (a "dual IP config" column) that this
    # particular database's schema doesn't have -- orion-res 400s with
    # VALIDATION_FAILED. auto_repair=True (the default) should strip that
    # column and retry rather than raising.
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown attribute name: "
                "tx_stream_config.ipv4_2_source_addr as "
                "tx_stream_config_ipv4_2_source_addr"),
        },
        status=400)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Detailed Stream Results", data_type="eot")
    assert len(rows) == 3  # succeeded on the retry

    # Nothing is printed/warned -- check last_dropped_columns instead.
    assert len(iq_client.last_dropped_columns) == 1
    assert "tx_stream_config_ipv4_2_source_addr" in (
        iq_client.last_dropped_columns[0])

    # The retried request no longer references the dropped column.
    second_request_body = json.loads(mocked_responses.calls[-1].request.body)
    sent = json.dumps(second_request_body)
    assert "tx_stream_config_ipv4_2_source_addr" not in sent


def test_query_auto_repair_strips_unknown_dimension_or_result_set_and_retries(
        iq_client, mocked_responses):
    # Real scenario CONFIRMED 2026-09-16 against a real AION-managed
    # orion-res server/view ("NFVi Advanced Kubernetes Platform Deployment
    # Summary" on 10.109.143.126): the same schema-mismatch situation as
    # test_query_auto_repair_strips_unknown_attribute_and_retries above,
    # but orion-res phrased the 400 as "unknown dimension or result set
    # name" instead of "unknown attribute name" -- the original regex only
    # matched the first phrasing, so auto_repair used to give up
    # immediately here instead of stripping the bad column and retrying.
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown dimension or "
                "result set name: tx_stream_config.ipv4_2_source_addr as "
                "tx_stream_config_ipv4_2_source_addr"),
        },
        status=400)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Detailed Stream Results", data_type="eot")
    assert len(rows) == 3  # succeeded on the retry

    assert len(iq_client.last_dropped_columns) == 1
    assert "tx_stream_config_ipv4_2_source_addr" in (
        iq_client.last_dropped_columns[0])

    second_request_body = json.loads(mocked_responses.calls[-1].request.body)
    sent = json.dumps(second_request_body)
    assert "tx_stream_config_ipv4_2_source_addr" not in sent


def test_query_auto_repair_false_raises_original_error(
        iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown attribute name: "
                "tx_stream_config.ipv4_2_source_addr as "
                "tx_stream_config_ipv4_2_source_addr"),
        },
        status=400)
    iq_client.use_test("n43grmtulrhgnkae")

    from tciqrestclient.exceptions import IQRequestError
    try:
        iq_client.query(
            name="Detailed Stream Results", data_type="eot",
            auto_repair=False)
        assert False, "expected IQRequestError"
    except IQRequestError as e:
        assert "unknown attribute name" in str(e)


def test_query_auto_repair_handles_many_sequential_broken_columns(
        iq_client, mocked_responses):
    # Real scenario reported by Vinod: a single-stack test's database was
    # missing ~21 dual-IP/MAC/VLAN/IPv6/VXLAN/MPLS/TCP/UDP-config columns
    # at once, all belonging to the same view -- each 400 only reports one
    # at a time, so this needs that many strip-and-retry round trips
    # before it can succeed. Uses all 10 "extra config" columns that are
    # actually present in this test view fixture's eot table.
    view = _load_data("view_detailed_stream_results.json")
    broken_columns = [
        "tx_stream_config.ipv4_2_source_addr",
        "tx_stream_config.ipv4_2_dest_addr",
        "tx_stream_config.eth2_2_src_mac",
        "tx_stream_config.eth2_2_dst_mac",
        "tx_stream_config.eth2_vlan_1_id",
        "tx_stream_config.eth2_vlan_2_id",
        "tx_stream_config.eth2_vlan_3_id",
        "tx_stream_config.eth2_vlan_4_id",
    ]
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    for raw_name in broken_columns:
        alias = raw_name.replace(".", "_")
        mocked_responses.add(
            responses_lib.POST, BASE + "/queries",
            json={
                "code": "VALIDATION_FAILED",
                "message": (
                    "Validation failed: name error; unknown attribute "
                    "name: %s as %s" % (raw_name, alias)),
            },
            status=400)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Detailed Stream Results", data_type="eot")
    assert len(rows) == 3
    assert len(iq_client.last_dropped_columns) == len(broken_columns)

    final_body = json.dumps(
        json.loads(mocked_responses.calls[-1].request.body))
    for raw_name in broken_columns:
        assert raw_name.replace(".", "_") not in final_body


def _synthetic_two_column_table_view(columns=("col_a", "col_b")):
    # Minimal single_level_table view with deterministic, simple aliases
    # for every column (raw_name == alias here, unlike the real
    # "Detailed Stream Results" fixture where a handful of columns --
    # e.g. stream_stats.frame_loss -- resolve through a differently-named
    # derived_fact_query_updates entry rather than a 1:1 dotted-to-
    # underscore alias). Keeping this self-contained avoids that mismatch
    # entirely for a test that just needs N columns whose raw "as <alias>"
    # error text it can predict exactly.
    provider = {
        "name": "synthetic_provider",
        "base_query": {
            "multi_result": {"subqueries": [{"alias": "view",
                                              "subqueries": []}]}
        },
        "attribute_query_updates": [
            {
                "name": col, "alias_name": col, "display_name": col,
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["raw.%s as %s" % (col, col)]},
                ],
            }
            for col in columns
        ],
        "fact_query_updates": [],
        "derived_fact_query_updates": [],
        "default_order_updates": {},
    }
    return {
        "name": "Synthetic Table",
        "details": {
            "view_type": "single_level_table",
            "user_data": {"tables": [{
                "data_type": "eot",
                "query_provider": "synthetic_provider",
                "columns": list(columns),
                "primary_dimension_attributes": [],
            }]},
        },
        "effective_details": {
            "system_data": {"query_providers": [provider]}},
    }


def test_query_auto_repair_raises_clear_error_when_every_column_missing(
        iq_client, mocked_responses):
    # Real scenario CONFIRMED 2026-09-16 against a real AION-managed
    # orion-res server/view: every column a view references can belong to
    # the same underlying table/measurement, which a database's schema
    # may lack *entirely* -- e.g. all 5 columns of a real "NFVi Advanced
    # Kubernetes Platform Deployment Summary" view all referenced the same
    # missing measurement. Left unguarded, auto_repair stripped every one
    # of them one at a time and then sent an empty query, which orion-res
    # rejected with an opaque "at least one projection is required" 400
    # that gave no hint the real cause was a wholesale missing table.
    # _run_with_auto_repair() must now raise a clear IQRequestError itself
    # (the SAME exception type this whole code path already raised before
    # this guard existed -- not a new IQQueryError, which a real run of
    # examples/aion_end_to_end.py confirmed slips past the dozens of
    # existing `except IQRequestError` sites across this repo's own
    # examples and crashes instead of printing the expected message),
    # before ever sending that empty request, once stripping would leave
    # the outermost query with zero projections -- exercised here by
    # reporting every single column of a 2-column synthetic view (not
    # just some, like test_query_auto_repair_handles_many_sequential_
    # broken_columns above) as broken, one at a time.
    all_columns = ("col_a", "col_b")
    view = _synthetic_two_column_table_view(all_columns)
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    for col in all_columns:
        mocked_responses.add(
            responses_lib.POST, BASE + "/queries",
            json={
                "code": "VALIDATION_FAILED",
                "message": (
                    "Validation failed: name error; unknown attribute "
                    "name: %s as %s" % (col, col)),
            },
            status=400)
    iq_client.use_test("n43grmtulrhgnkae")

    from tciqrestclient.exceptions import IQRequestError
    try:
        iq_client.query(name="Synthetic Table", data_type="eot")
        assert False, "expected IQRequestError"
    except IQRequestError as e:
        assert "every column" in str(e)
        assert "entirely missing" in str(e)

    # Every column was dropped before the guard fired -- no 400 for a
    # request beyond the last real column was ever needed/sent.
    assert len(iq_client.last_dropped_columns) == len(all_columns)
    assert mocked_responses.calls[-1].request.method == "POST"


def test_query_auto_repair_raises_last_error_once_attempts_exhausted(
        iq_client, mocked_responses, monkeypatch):
    # Reproduces the exact bug reported by Vinod: MAX_AUTO_REPAIR_ATTEMPTS
    # too low for a view with many broken columns -- the (n+1)th broken
    # column should still surface a clear IQRequestError, not swallow it
    # or loop forever, once the cap is genuinely exceeded.
    import tciqrestclient.client as client_mod
    monkeypatch.setattr(client_mod, "MAX_AUTO_REPAIR_ATTEMPTS", 1)

    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown attribute name: "
                "tx_stream_config.ipv4_2_source_addr as "
                "tx_stream_config_ipv4_2_source_addr"),
        },
        status=400)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown attribute name: "
                "tx_stream_config.ipv4_2_dest_addr as "
                "tx_stream_config_ipv4_2_dest_addr"),
        },
        status=400)
    iq_client.use_test("n43grmtulrhgnkae")

    from tciqrestclient.exceptions import IQRequestError
    try:
        iq_client.query(name="Detailed Stream Results", data_type="eot")
        assert False, "expected IQRequestError"
    except IQRequestError as e:
        # The second (unrepaired, attempts exhausted) error, not the
        # first -- confirms it made exactly one repair attempt then gave
        # up cleanly rather than looping or masking which column broke.
        assert "tx_stream_config_ipv4_2_dest_addr" in str(e)
    # The one successful repair attempt before exhausting is still
    # recorded, even though the call ultimately raised.
    assert iq_client.last_dropped_columns == [
        "tx_stream_config.ipv4_2_source_addr as "
        "tx_stream_config_ipv4_2_source_addr"]


def test_query_by_view_name_unknown_data_type_raises(
        iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    iq_client.use_test("n43grmtulrhgnkae")
    try:
        iq_client.query(name="Detailed Stream Results", data_type="history")
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "history" in str(e)


def test_query_by_view_name_not_found(iq_client, mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[])
    iq_client.use_test("db-1")
    try:
        iq_client.query(name="Nonexistent")
        assert False, "expected IQViewError"
    except IQViewError:
        pass


def test_query_by_raw_definition(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    rows = iq_client.query(definition=fixtures.QUERY_DEFINITION)
    assert len(rows) == 3


def test_query_timeout_override_reaches_transport(iq_client, mocked_responses):
    from unittest import mock
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    with mock.patch.object(
            iq_client._transport, "post",
            wraps=iq_client._transport.post) as spy:
        iq_client.query(definition=fixtures.QUERY_DEFINITION, timeout=180)
    assert spy.call_args.kwargs["timeout"] == 180


def test_query_with_filters_and_sort(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    iq_client.query(
        definition=fixtures.QUERY_DEFINITION,
        filters=[("frame_count", "gt", 0)],
        sort=("frame_count", "desc"),
    )

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    node = sent_body["definition"]["multi_result"]
    assert node["filters"][-1] == "view.frame_count>0"
    assert node["orders"][-1] == "view.frame_count DESC"
    # original view definition untouched
    assert fixtures.QUERY_DEFINITION["multi_result"]["filters"] == []


def test_query_defaults_to_limit_1000(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    iq_client.query(definition=fixtures.QUERY_DEFINITION)

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["definition"]["multi_result"]["limit"] == 1000
    # the view's own default (120) is untouched in the original definition
    assert fixtures.QUERY_DEFINITION["multi_result"]["limit"] == 120


def test_query_limit_override(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    iq_client.query(definition=fixtures.QUERY_DEFINITION, limit=50)

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["definition"]["multi_result"]["limit"] == 50


def test_query_limit_none_keeps_views_own_limit(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    iq_client.query(definition=fixtures.QUERY_DEFINITION, limit=None)

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["definition"]["multi_result"]["limit"] == 120


def test_query_raw_result(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")
    result = iq_client.query(
        definition=fixtures.QUERY_DEFINITION, raw_result=True)
    assert result == fixtures.QUERY_RESPONSE["result"]


def test_query_rejects_both_name_and_definition(iq_client):
    try:
        iq_client.query(name="x", definition=fixtures.QUERY_DEFINITION)
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass


def test_query_rejects_neither_name_nor_definition(iq_client):
    try:
        iq_client.query()
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass


def test_query_requires_database_id(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    try:
        iq_client.query(definition=fixtures.QUERY_DEFINITION)
        assert False, "expected IQQueryError"
    except IQQueryError:
        pass


def test_save_view_roundtrip(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/views", json={"id": "view-9"})
    result = iq_client.save_view("New View", fixtures.VIEW["details"])
    assert result == {"id": "view-9"}


def test_generate_report_without_download(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    report = iq_client.generate_report("t1", "My Report")
    assert report == {"id": "r1"}


def test_generate_report_with_download(iq_client, mocked_responses, tmp_path):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/r1/download",
        body=b"%PDF-fake", content_type="application/pdf")
    iq_client.use_test("db-1")
    out = str(tmp_path / "out.pdf")
    result = iq_client.generate_report("t1", "My Report", output_path=out)
    assert result == out


def test_generate_report_snapshot_filter_sent_as_json_string(
        iq_client, mocked_responses):
    """CONFIRMED 2026-09-11 against a real captured GUI request (see
    tciqrestclient/reports.py's module docstring) -- test_snapshot_filter lives
    inside parameters, JSON-encoded as a string, not a top-level field.
    This superseded an earlier, wrong guess (a top-level "live" boolean
    and "snapshot_name" field) that a real capture disproved."""
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", snapshot_filter="Snapshot 1")
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["test_snapshot_filter"] == '["Snapshot 1"]'


def test_generate_report_snapshot_filter_accepts_a_list(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", snapshot_filter=["Snapshot 1", "Snapshot 2"])
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["test_snapshot_filter"] == (
        '["Snapshot 1", "Snapshot 2"]')


def test_generate_report_snapshot_filter_merges_into_given_parameters(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", snapshot_filter="Snapshot 1",
        parameters={"owner": "she83111"})
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["owner"] == "she83111"
    assert body["parameters"]["test_snapshot_filter"] == '["Snapshot 1"]'


def test_generate_report_confirmed_default_all_snapshots_sentinel(
        iq_client, mocked_responses):
    from tciqrestclient.reports import REPORT_ALL_SNAPSHOTS_FILTER
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER)
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["test_snapshot_filter"] == '["is_all_included"]'


def test_generate_report_live_and_snapshot_combined_filter(
        iq_client, mocked_responses):
    """CONFIRMED 2026-09-11 against a second real GUI capture, this time
    for "live and snapshot" report generation: test_snapshot_filter
    combines BOTH flags in one list, not a separate live/snapshot mode."""
    from tciqrestclient.reports import (
        REPORT_ALL_SNAPSHOTS_FILTER, REPORT_LIVE_INCLUDED_FILTER)
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report",
        snapshot_filter=[REPORT_ALL_SNAPSHOTS_FILTER,
                         REPORT_LIVE_INCLUDED_FILTER])
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["test_snapshot_filter"] == (
        '["is_all_included", "is_live_included"]')


def test_generate_report_database_name_sent_alongside_id(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", database_name="all-devices")
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["database"] == {"id": "db-1", "name": "all-devices"}


def test_generate_report_excluded_sections_sent_as_json_string(
        iq_client, mocked_responses):
    """CONFIRMED 2026-09-16: excluding a report template's chart-type
    section (via this real parameters.excluded_sections field) is what
    makes report generation actually succeed instead of crashing the
    report-rendering frontend -- see tciqrestclient/reports.py's module docstring."""
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", excluded_sections=["section_2"])
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["excluded_sections"] == '["section_2"]'


def test_generate_report_excluded_sections_merges_with_snapshot_filter(
        iq_client, mocked_responses):
    from tciqrestclient.reports import REPORT_ALL_SNAPSHOTS_FILTER
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report(
        "t1", "My Report", excluded_sections=["section_2"],
        snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER)
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert body["parameters"]["excluded_sections"] == '["section_2"]'
    assert body["parameters"]["test_snapshot_filter"] == '["is_all_included"]'


def test_find_unsupported_report_sections_delegates_to_reports_module(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/report-templates/tmpl-1",
        json={"id": "tmpl-1", "details": {"sections": [
            {"name": "section_2", "views": [{"name": "Chart View"}]},
        ]}})
    mocked_responses.add(
        responses_lib.GET, BASE + "/views",
        json=[{"name": "Chart View", "details": {"view_type": "x_y_chart"}}])
    result = iq_client.find_unsupported_report_sections("tmpl-1")
    assert result == ["section_2"]


def test_generate_report_omits_parameters_and_database_name_by_default(
        iq_client, mocked_responses):
    """Neither is sent at all when snapshot_filter=/database_name=/
    excluded_sections= are left at their None default -- exactly the
    pre-existing behavior, unchanged for any caller not using the new
    parameters."""
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("db-1")
    iq_client.generate_report("t1", "My Report")
    body = json.loads(mocked_responses.calls[-1].request.body)
    assert "parameters" not in body
    assert body["database"] == {"id": "db-1"}


def test_download_report(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/r1/download",
        body=b"%PDF-fake", content_type="application/pdf")
    assert iq_client.download_report("r1") == b"%PDF-fake"


# -- one query() method for every view_type -- multi-kind view_types ------
# -- (histogram/boxplot) and snapshot_name= (Phase 0/1 of --------------
# -- WIDGET_QUERY_PLAN.md) -- synthetic view, since no real capture -------
# -- exists yet for these (see that plan doc). -----------------------------

def _synthetic_boxplot_view(groups, columns=("col_a",)):
    provider = {
        "name": "synthetic_provider",
        "base_query": {
            "multi_result": {"subqueries": [{"alias": "view",
                                              "subqueries": []}]}
        },
        "attribute_query_updates": [
            {
                "name": col, "alias_name": col,
                "display_name": col,
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["raw.%s as %s" % (col, col)]},
                ],
            }
            for col in columns
        ],
        "fact_query_updates": [],
        "derived_fact_query_updates": [],
        "default_order_updates": {},
    }
    return {
        "name": "Synthetic Boxplot",
        "details": {
            "view_type": "boxplot",
            "user_data": {"tables": [{
                "data_type": "eot",
                "query_provider": "synthetic_provider",
                "columns": list(columns),
                "primary_dimension_attributes": [],
                "groups": groups,
            }]},
        },
        "effective_details": {
            "system_data": {"query_providers": [provider]}},
    }


def test_query_multi_kind_view_returns_dict_of_rows_one_request_each(
        iq_client, mocked_responses):
    view = _synthetic_boxplot_view(["latency", "jitter"])
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    # One /queries response per statistic -- order matches dict iteration
    # order of details.user_data.tables[0]["groups"], i.e. insertion order.
    latency_response = json.loads(json.dumps(fixtures.QUERY_RESPONSE))
    latency_response["result"]["rows"] = [["latency-row"]]
    jitter_response = json.loads(json.dumps(fixtures.QUERY_RESPONSE))
    jitter_response["result"]["rows"] = [["jitter-row"]]
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=latency_response)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=jitter_response)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Synthetic Boxplot", data_type="eot")

    assert set(rows) == {"latency", "jitter"}
    assert rows["latency"][0]["test_snapshot_name"] == "latency-row"
    assert rows["jitter"][0]["test_snapshot_name"] == "jitter-row"
    # One /queries POST per statistic, not one for the whole view.
    post_calls = [c for c in mocked_responses.calls
                  if c.request.method == "POST"]
    assert len(post_calls) == 2


def test_query_multi_kind_view_records_dropped_columns_per_sub_query(
        iq_client, mocked_responses):
    # Two columns per sub-query (not just one) -- so stripping the broken
    # "col_a" for "latency" leaves "col_b" behind, matching a realistic
    # one-broken-column-among-several case rather than tripping the
    # zero-projections-left guard (see test_query_auto_repair_raises_
    # clear_error_when_every_column_missing) as a side effect of this
    # fixture only ever having a single column.
    view = _synthetic_boxplot_view(["latency", "jitter"],
                                    columns=("col_a", "col_b"))
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    # "latency" 400s once then succeeds; "jitter" succeeds immediately.
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries",
        json={
            "code": "VALIDATION_FAILED",
            "message": (
                "Validation failed: name error; unknown attribute name: "
                "raw.col_a as col_a"),
        },
        status=400)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(name="Synthetic Boxplot", data_type="eot")

    assert iq_client.last_dropped_columns["latency"] == [
        "raw.col_a as col_a"]
    assert iq_client.last_dropped_columns["jitter"] == []


def test_query_snapshot_name_threads_through_to_built_definition(
        iq_client, mocked_responses):
    # "Detailed Stream Results" has no snapshot_filter_provider declared
    # -- so this exercises the fallback tier of _apply_snapshot_filter(),
    # CONFIRMED against a real server 2026-09-03 to need the "view."
    # alias qualifier (see HANDOVER.md section 9).
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(
        name="Detailed Stream Results", data_type="eot",
        snapshot_name="Snapshot_4Kstreams")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert "view.test_snapshot_name = 'Snapshot_4Kstreams'" in node["filters"]


def test_query_snapshot_name_against_live_table_raises(
        iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    iq_client.use_test("n43grmtulrhgnkae")

    try:
        iq_client.query(
            name="Detailed Stream Results", data_type="live",
            snapshot_name="Snapshot_4Kstreams")
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "live" in str(e)


# -- one query() end-to-end test per view_type -----------------------------
#
# All go through the same iq_client.query(name=...) call -- there's no
# separate method per widget type (see client.py's query() docstring).
# table is confirmed against a real capture (fixtures/data/*.json);
# x_y_chart/pie_chart/histogram use a hand-built synthetic view instead,
# since no real capture exists yet for those (see WIDGET_QUERY_PLAN.md) --
# boxplot's dedicated tests are above (it needed a "groups" table field
# _synthetic_boxplot_view() sets up specially). health_indicator/chart
# aren't in SUPPORTED_VIEW_TYPES at all (see
# test_health_indicator_and_ts_chart_still_unsupported in
# test_view_query_builder.py) -- deliberately out of scope for now.

def _synthetic_single_kind_view(name, view_type, data_type="eot",
                                 provider_overrides=None):
    provider = {
        "name": "synthetic_provider",
        "base_query": {
            "multi_result": {"subqueries": [{"alias": "view",
                                              "subqueries": []}]}
        },
        "attribute_query_updates": [
            {
                "name": "col_a", "alias_name": "col_a",
                "display_name": "Col A",
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["raw.col_a as col_a"]},
                ],
            },
        ],
        "fact_query_updates": [],
        "derived_fact_query_updates": [],
        "default_order_updates": {},
    }
    if provider_overrides:
        provider.update(provider_overrides)
    return {
        "name": name,
        "details": {
            "view_type": view_type,
            "user_data": {"tables": [{
                "data_type": data_type,
                "query_provider": "synthetic_provider",
                "columns": ["col_a"],
                "primary_dimension_attributes": [],
            }]},
        },
        "effective_details": {
            "system_data": {"query_providers": [provider]}},
    }


def test_query_table_view_eot(iq_client, mocked_responses):
    # single_level_table/paged_single_level_table -- confirmed
    # byte-for-byte against a real capture (see test_view_query_builder.py
    # for that check); this is the end-to-end query() path around it.
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Detailed Stream Results", data_type="eot")

    assert len(rows) == 3
    assert rows[0]["test_snapshot_name"] == "Snapshot_4Kstreams"


def test_query_table_view_live(iq_client, mocked_responses):
    # "live" data (a test still running) goes through the exact same
    # query() call as "eot" -- just a different table_index/data_type
    # resolving to a different query_provider/template (see
    # get_view_definition()). No snapshot_name= here -- see
    # test_query_snapshot_name_against_live_table_raises above for why
    # that combination is specifically rejected.
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Detailed Stream Results", data_type="live")

    assert len(rows) == 3
    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    # The live table's own provider (live_table_stream_traffic) has a
    # different join shape (rxss/txss under "view") than eot's -- confirm
    # the live template was actually used, not eot's.
    assert node["subqueries"][0]["alias"] == "view"
    assert {sq["alias"] for sq in node["subqueries"][0]["subqueries"]} == {
        "rxss", "txss"}


def test_query_xy_chart_view(iq_client, mocked_responses):
    # x_y_chart -- reverse-engineered from XYChartWidgetModel.getQueryDef()
    # (see WIDGET_QUERY_PLAN.md section 2.2), NOT yet confirmed against a
    # real capture. One query, same shape as table.
    view = _synthetic_single_kind_view("Synthetic XY Chart", "x_y_chart")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Synthetic XY Chart", data_type="eot")

    assert isinstance(rows, list)
    assert len(rows) == 3
    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert "raw.col_a as col_a" in node["subqueries"][0]["projections"]
    # xy-chart never applies a snapshot filter, even against its eot
    # table (see _build_xy_chart_query()'s docstring).
    assert node["filters"] == []


def test_query_pie_chart_view(iq_client, mocked_responses):
    # pie_chart -- reverse-engineered from PieChartWidgetModel.
    # getQueryDefinition() (see WIDGET_QUERY_PLAN.md section 2.3), NOT
    # yet confirmed against a real capture. One query; unlike xy-chart,
    # it does apply a snapshot filter.
    view = _synthetic_single_kind_view(
        "Synthetic Pie Chart", "pie_chart",
        provider_overrides={"group_by": "col_a"})
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(
        name="Synthetic Pie Chart", data_type="eot", snapshot_name="Snap1")

    assert isinstance(rows, list)
    assert len(rows) == 3
    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert "view.test_snapshot_name = 'Snap1'" in node["filters"]


def test_query_histogram_view_returns_rows_dict(iq_client, mocked_responses):
    # histogram -- reverse-engineered from HistogramWidgetModel.
    # buildQueryDefinitions() (see WIDGET_QUERY_PLAN.md section 2.4), NOT
    # yet confirmed against a real capture. One query per provider -- this
    # synthetic view only has one, so exactly one entry back.
    view = _synthetic_single_kind_view("Synthetic Histogram", "histogram")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    rows = iq_client.query(name="Synthetic Histogram", data_type="eot")

    assert set(rows) == {"synthetic_provider"}
    assert len(rows["synthetic_provider"]) == 3


# -- 2026-09-04 final-audit coverage gaps -----------------------------------
#
# Every test below closes a specific coverage gap surfaced by an
# independent, adversarially-verified pre-publish audit against the PRD:
# database_id= actually overriding a different use_test() default (IQ-
# PYTHON-007), all four query modifiers combined in one client-level
# call and applied identically to every sub-query of a multi-kind view
# (IQ-PYTHON-005), the true "neither table_index= nor data_type= given"
# default against a real live-first captured view (IQ-PYTHON-004), and
# generate_report()'s title= requirement raising IQReportError (not a
# bare TypeError) when omitted. Before these existed, each of these
# behaviors was correct by code inspection but had no automated
# regression test guarding it at the public IQClient API layer.

def test_query_database_id_overrides_use_test_default(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("default-db")
    iq_client.query(definition=fixtures.QUERY_DEFINITION, database_id="other-db")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["database"]["id"] == "other-db"


def test_get_test_database_id_overrides_use_test_default(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases/other-db", json={"id": "other-db"})
    iq_client.use_test("default-db")
    result = iq_client.get_test(database_id="other-db")
    assert result["id"] == "other-db"


_MIN_SCHEMA = {
    "result_sets": [{"name": "facts_table", "facts": [
        {"name": "frame_count", "type": "integer"}]}],
    "dimension_sets": [],
}


def test_list_table_names_database_id_overrides_use_test_default(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases/other-db", json=_MIN_SCHEMA)
    iq_client.use_test("default-db")
    tables = iq_client.list_table_names(database_id="other-db")
    assert tables[0]["name"] == "facts_table"
    assert BASE + "/databases/other-db" in mocked_responses.calls[-1].request.url


def test_list_fields_database_id_overrides_use_test_default(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases/other-db", json=_MIN_SCHEMA)
    iq_client.use_test("default-db")
    fields = iq_client.list_fields(database_id="other-db")
    assert fields[0]["name"] == "frame_count"


def test_generate_report_database_id_overrides_use_test_default(
        iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    iq_client.use_test("default-db")
    iq_client.generate_report("t1", "My Report", database_id="other-db")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["database"]["id"] == "other-db"


def test_generate_report_missing_title_raises_iqreporterror(iq_client):
    from tciqrestclient.exceptions import IQReportError
    iq_client.use_test("default-db")
    with pytest.raises(IQReportError, match="title"):
        iq_client.generate_report("t1")


def test_all_modifiers_combined_through_client_query(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(
        definition=fixtures.QUERY_DEFINITION,
        filters=[("frame_count", "gt", 0)],
        sort=("frame_count", "desc"),
        group_by="tx_stream_stream_id",
        time_range=("start_time", "2026-01-01T00:00:00Z", None),
    )

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert "view.frame_count>0" in node["filters"]
    assert any(f.startswith("view.start_time>=") for f in node["filters"])
    assert node["orders"][-1] == "view.frame_count DESC"
    assert node["groups"] == ["view.tx_stream_stream_id"]


def test_multi_kind_view_applies_same_modifiers_to_every_sub_query(
        iq_client, mocked_responses):
    view = _synthetic_boxplot_view(["latency", "jitter"])
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(
        name="Synthetic Boxplot", data_type="eot",
        filters=[("col_a", "gt", 0)], sort="col_a DESC")

    post_calls = [c for c in mocked_responses.calls
                  if c.request.method == "POST"]
    assert len(post_calls) == 2
    for call in post_calls:
        node = json.loads(call.request.body)["definition"]["multi_result"]
        assert "view.col_a>0" in node["filters"]
        assert node["orders"][-1] == "view.col_a DESC"


def test_query_by_view_name_default_picks_eot_against_real_live_first_fixture(
        iq_client, mocked_responses):
    # IQ-PYTHON-004: with neither table_index= nor data_type= given,
    # query(name=...) must default to snapshot ("eot") data -- codifies,
    # at the public IQClient.query() level, the manual verification the
    # 2026-09-04 final audit did ad-hoc (see HANDOVER.md section 9). The
    # real captured fixture below lists "live" before "eot" in its
    # tables array, so this would silently regress to live data if
    # get_view_definition()'s wiring (as opposed to _resolve_table_index()
    # in isolation, which test_views.py already covers) ever stopped
    # passing table_index=/data_type=None through correctly.
    view = _load_data("view_detailed_stream_results.json")
    assert view["details"]["user_data"]["tables"][0]["data_type"] == "live"
    expected_definition = _load_data(
        "dsr_query_unfiltered.json")["definition"]
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(name="Detailed Stream Results", limit=120)

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["definition"] == expected_definition


# -- test_live=/user= -- PM feedback on the final draft, 2026-09-04 -------
#
# query()'s data_type= was renamed to test_live= as the primary, simple
# way to pick live vs. snapshot data (a boolean, or the strings
# "live"/"eot"/"snapshot" -- see _normalize_test_live()); data_type=/
# table_index= remain as advanced escape hatches. A new user= lets a
# caller resolve database_id automatically by owner instead of looking
# it up themselves -- but only for live data, where "the one test this
# user currently has running" is unambiguous; for snapshot data a user
# can have many completed tests, so user= alone raises, asking for an
# explicit database_id= instead of guessing (exactly per product
# guidance: "for EOT, we can ask for database-id").

def test_normalize_test_live_accepts_bool_and_live_eot_synonyms():
    from tciqrestclient.client import _normalize_test_live
    assert _normalize_test_live(None) is None
    assert _normalize_test_live(True) is True
    assert _normalize_test_live(False) is False
    assert _normalize_test_live("live") is True
    assert _normalize_test_live("LIVE") is True
    assert _normalize_test_live("true") is True
    assert _normalize_test_live("eot") is False
    assert _normalize_test_live("EOT") is False  # the exact reported bug
    assert _normalize_test_live("snapshot") is False
    assert _normalize_test_live("false") is False


def test_normalize_test_live_rejects_unrecognized_string():
    from tciqrestclient.client import _normalize_test_live
    with pytest.raises(IQQueryError, match="test_live"):
        _normalize_test_live("sometimes")


def test_query_test_live_true_selects_the_live_table(iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(name="Detailed Stream Results", test_live=True)

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    # Same live-vs-eot join-shape check as test_query_table_view_live,
    # but reached via test_live=True instead of data_type="live".
    assert {sq["alias"] for sq in node["subqueries"][0]["subqueries"]} == {
        "rxss", "txss"}


def test_query_test_live_string_live_selects_the_live_table(
        iq_client, mocked_responses):
    # PM's own example script called this positionally as a string:
    # iq.query("Detailed Stream Results", "live", ...).
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query("Detailed Stream Results", "live")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    node = sent_body["definition"]["multi_result"]
    assert {sq["alias"] for sq in node["subqueries"][0]["subqueries"]} == {
        "rxss", "txss"}


def test_query_test_live_false_selects_eot_case_insensitively(
        iq_client, mocked_responses):
    # Reproduces the exact reported bug: data_type="EOT" (uppercase)
    # silently failed. test_live="EOT" must now work.
    view = _load_data("view_detailed_stream_results.json")
    expected_definition = _load_data(
        "dsr_query_unfiltered.json")["definition"]
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(name="Detailed Stream Results", test_live="EOT", limit=120)

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["definition"] == expected_definition


def test_query_data_type_still_works_case_insensitively(
        iq_client, mocked_responses):
    # The legacy/advanced data_type= kwarg is still accepted directly
    # (not just via test_live=), and is now also case-insensitive.
    view = _load_data("view_detailed_stream_results.json")
    expected_definition = _load_data(
        "dsr_query_unfiltered.json")["definition"]
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    iq_client.use_test("n43grmtulrhgnkae")

    iq_client.query(name="Detailed Stream Results", data_type="EOT", limit=120)

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["definition"] == expected_definition


_LIVE_TEST = {
    "id": "live-db-1", "name": "Currently Running",
    "metadata": {"test.owner": "jdoe", "test.running": "true"},
}
_COMPLETED_TEST = {
    "id": "done-db-1", "name": "Finished Earlier",
    "metadata": {"test.owner": "jdoe", "test.running": "false"},
}


def test_query_user_resolves_the_one_running_test(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases",
        json=[_LIVE_TEST, _COMPLETED_TEST])
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)

    iq_client.query(definition=fixtures.QUERY_DEFINITION,
                     test_live=True, user="jdoe")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["database"]["id"] == "live-db-1"


def test_query_user_raises_when_no_running_test(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", json=[_COMPLETED_TEST])
    with pytest.raises(IQQueryError, match="no live/running test"):
        iq_client.query(
            definition=fixtures.QUERY_DEFINITION, test_live=True, user="jdoe")


def test_query_user_raises_when_multiple_running_tests(
        iq_client, mocked_responses):
    other_live = dict(_LIVE_TEST, id="live-db-2")
    mocked_responses.add(
        responses_lib.GET, BASE + "/databases", json=[_LIVE_TEST, other_live])
    with pytest.raises(IQQueryError, match="multiple live/running tests"):
        iq_client.query(
            definition=fixtures.QUERY_DEFINITION, test_live=True, user="jdoe")


def test_query_user_for_snapshot_asks_for_database_id(iq_client):
    # Per product guidance: for eot/snapshot data, user= alone is
    # deliberately not enough (a user can have many completed tests) --
    # this must raise and point at database_id=, not guess one.
    with pytest.raises(IQQueryError, match="database_id"):
        iq_client.query(
            definition=fixtures.QUERY_DEFINITION, user="jdoe")  # test_live omitted -> snapshot default

    with pytest.raises(IQQueryError, match="database_id"):
        iq_client.query(
            definition=fixtures.QUERY_DEFINITION, test_live=False, user="jdoe")


def test_query_explicit_database_id_wins_over_user(iq_client, mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/queries", json=fixtures.QUERY_RESPONSE)
    # user="jdoe" would normally need a /databases lookup -- database_id=
    # given explicitly must skip that resolution entirely.
    iq_client.query(
        definition=fixtures.QUERY_DEFINITION,
        database_id="explicit-db", user="jdoe")

    sent_body = json.loads(mocked_responses.calls[-1].request.body)
    assert sent_body["database"]["id"] == "explicit-db"
    assert not any(c.request.url.endswith("/databases")
                   for c in mocked_responses.calls)


def test_list_view_columns_test_live_maps_to_data_type(
        iq_client, mocked_responses):
    view = _load_data("view_detailed_stream_results.json")
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[view])

    live_columns = iq_client.list_view_columns(
        "Detailed Stream Results", test_live=True, active_only=True)
    eot_columns = iq_client.list_view_columns(
        "Detailed Stream Results", test_live="eot", active_only=True)

    # The real view's live and eot tables have a different active-column
    # count (44 vs 40) -- confirms test_live= actually selected different
    # tables, not the same one twice.
    assert len(live_columns) == 44
    assert len(eot_columns) == 40
