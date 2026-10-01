"""Tests for requirements added in the IQ-PYTHON-001..011 implementation:
  - IQ-PYTHON-003: delete_view(name=...), save_view(definition=...),
                   query(definition=<JSON string>)
  - IQ-PYTHON-006: get_database_schema, list_table_names, list_fields
  - IQ-PYTHON-010: delete_test, rename_test
  - IQ-PYTHON-002: AION config params wired through IQClient constructor
"""
import datetime
import json
import pytest
import responses as responses_lib

import fixtures
from tciqrestclient import IQClient
from tciqrestclient import databases
from tciqrestclient import views
from tciqrestclient.exceptions import IQQueryError, IQViewError, IQError, IQRequestError
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


# ---------------------------------------------------------------------------
# IQ-PYTHON-003: Named Views gaps
# ---------------------------------------------------------------------------

class TestDeleteViewByName:
    def test_delete_by_name_looks_up_then_deletes(self, mocked_responses):
        view = dict(fixtures.VIEW, id="view-id-1", name="My CI View")
        mocked_responses.add(
            responses_lib.GET, BASE + "/views", json=[view])
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/views/view-id-1", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.delete_view(name="My CI View")
        assert mocked_responses.calls[-1].request.method == "DELETE"
        assert "view-id-1" in mocked_responses.calls[-1].request.url

    def test_delete_by_name_not_found_raises(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/views", json=[])
        iq = IQClient(base_url=BASE, load_env=False)
        with pytest.raises(IQViewError, match="no view named"):
            iq.delete_view(name="Nonexistent View")

    def test_delete_by_view_id_still_works(self, mocked_responses):
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/views/abc123", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.delete_view(view_id="abc123")
        assert mocked_responses.calls[0].request.method == "DELETE"

    def test_delete_view_requires_one_arg(self, mocked_responses):
        iq = IQClient(base_url=BASE, load_env=False)
        with pytest.raises(IQViewError):
            iq.delete_view()  # neither view_id nor name


class TestSaveViewDefinitionAlias:
    def test_save_view_accepts_definition_kwarg(self, mocked_responses):
        mocked_responses.add(
            responses_lib.POST, BASE + "/views", json={"id": "new-1"})
        iq = IQClient(base_url=BASE, load_env=False)
        details_spec = {"view_type": "single_level_table"}
        iq.save_view(name="My View", definition=details_spec)
        body = json.loads(mocked_responses.calls[0].request.body)
        assert body["details"] == details_spec

    def test_save_view_accepts_details_kwarg(self, mocked_responses):
        mocked_responses.add(
            responses_lib.POST, BASE + "/views", json={"id": "new-2"})
        iq = IQClient(base_url=BASE, load_env=False)
        details_spec = {"view_type": "single_level_table"}
        iq.save_view(name="My View", details=details_spec)
        body = json.loads(mocked_responses.calls[0].request.body)
        assert body["details"] == details_spec

    def test_definition_kwarg_takes_precedence_over_details(self, mocked_responses):
        mocked_responses.add(
            responses_lib.POST, BASE + "/views", json={"id": "new-3"})
        iq = IQClient(base_url=BASE, load_env=False)
        iq.save_view(name="My View",
                     definition={"view_type": "x_y_chart"},
                     details={"view_type": "wrong"})
        body = json.loads(mocked_responses.calls[0].request.body)
        assert body["details"]["view_type"] == "x_y_chart"


_IQ_CLIENT_BASE = "http://fake-orion-res:9200"


class TestQueryDefinitionJsonString:
    def test_json_string_definition_is_parsed(self, mocked_responses, iq_client):
        mocked_responses.add(
            responses_lib.POST, _IQ_CLIENT_BASE + "/queries",
            json=fixtures.QUERY_RESPONSE)
        iq_client.use_test("db-1")
        definition_str = json.dumps(fixtures.QUERY_DEFINITION)
        rows = iq_client.query(definition=definition_str)
        assert len(rows) == len(fixtures.QUERY_RESPONSE["result"]["rows"])

    def test_invalid_json_string_raises(self, iq_client):
        iq_client.use_test("db-1")
        with pytest.raises(IQQueryError, match="not valid JSON"):
            iq_client.query(definition="not { valid json")


# ---------------------------------------------------------------------------
# IQ-PYTHON-006: Database Metadata
# ---------------------------------------------------------------------------

# Real shape, confirmed against a live server 2026-09-03 (see
# HANDOVER.md section 9) -- GET /databases/{id}?detail=full has no
# top-level "tables" key at all. "result_sets" (fact tables, e.g.
# "stream_results" below) carry a "facts" field list; "dimension_sets"
# (lookup/reference tables, e.g. "test" below) carry "attributes"
# instead. list_table_names()/list_fields() tag each with kind=
# "result_set"/"dimension_set" so callers can tell which is which.
SCHEMA_RESPONSE = {
    "id": "db-schema-1",
    "name": "My Test",
    "result_sets": [
        {
            "name": "stream_results",
            "raw_name": "db-schema-1_stream_results",
            "description": "Per-stream traffic results",
            "dimension_sets": ["test"],
            "primary_dimension_set": "test",
            "facts": [
                {"name": "tx_stream_stats.frame_count", "display_name": "Tx Count",
                 "description": "", "type": "integer", "unit": "none"},
                {"name": "rx_stream_stats.frame_count", "display_name": "Rx Count",
                 "description": "", "type": "integer", "unit": "none"},
            ],
            "summary": {"count": 100, "value_storage_kb": 1, "index_storage_kb": 1},
        },
    ],
    "dimension_sets": [
        {
            "name": "test",
            "raw_name": "db-schema-1_test",
            "description": "",
            "attributes": [
                {"name": "port_stats.rx_frame_rate", "display_name": "Rx Rate",
                 "description": "", "type": "float", "unit": "none"},
            ],
            "summary": {"count": -1, "value_storage_kb": 1, "index_storage_kb": 1},
        },
    ],
}


class TestDatabaseMetadata:
    def test_get_database_schema_calls_full_detail(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        result = iq.get_database_schema()
        sent_url = mocked_responses.calls[0].request.url
        assert "detail=full" in sent_url
        assert result["id"] == "db-schema-1"

    def test_get_database_schema_explicit_id(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-99",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        result = iq.get_database_schema(database_id="db-99")
        assert result is not None

    def test_list_table_names_returns_table_list(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        tables = iq.list_table_names()
        assert len(tables) == 2
        assert tables[0]["name"] == "stream_results"
        assert tables[0]["kind"] == "result_set"
        assert tables[1]["name"] == "test"
        assert tables[1]["kind"] == "dimension_set"

    def test_list_table_names_empty_when_no_tables(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json={"id": "db-1"})
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        assert iq.list_table_names() == []

    def test_list_fields_all_tables(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        fields = iq.list_fields()
        assert len(fields) == 3
        names = [f["name"] for f in fields]
        assert "tx_stream_stats.frame_count" in names
        assert "port_stats.rx_frame_rate" in names

    def test_list_fields_scoped_to_table(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        fields = iq.list_fields(table_name="stream_results")
        assert len(fields) == 2
        assert all("stream_stats" in f["name"] for f in fields)

    def test_list_fields_scoped_to_dimension_set_table(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        fields = iq.list_fields(table_name="test")
        assert len(fields) == 1
        assert fields[0]["name"] == "port_stats.rx_frame_rate"

    def test_database_schema_module_function_requires_id(self):
        with pytest.raises(IQError):
            databases.get_database_schema(Transport(BASE), "")

    def test_list_table_names_module_function(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        result = databases.list_table_names(Transport(BASE), "db-1")
        assert len(result) == 2

    def test_list_fields_module_function_no_table_filter(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        result = databases.list_fields(Transport(BASE), "db-1")
        assert len(result) == 3

    def test_get_database_tables_is_list_table_names_alias(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        assert iq.get_database_tables() == iq.list_table_names()

    def test_get_table_schema_returns_one_table_by_name(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        table = iq.get_table_schema("stream_results")
        assert table["kind"] == "result_set"
        assert len(table["facts"]) == 2

    def test_get_table_schema_not_found_raises(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json=SCHEMA_RESPONSE)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        with pytest.raises(IQError, match="no table named"):
            iq.get_table_schema("nonexistent_table")

    def test_get_database_summary_returns_summary_dict(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json={"id": "db-1",
                  "summary": {"count": 42, "value_storage_kb": 10,
                              "index_storage_kb": 5}})
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        assert iq.get_database_summary() == {
            "count": 42, "value_storage_kb": 10, "index_storage_kb": 5}

    def test_get_database_summary_missing_returns_empty_dict(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1", json={"id": "db-1"})
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("db-1")
        assert iq.get_database_summary() == {}


# ---------------------------------------------------------------------------
# Bulk cleanup: delete by size / delete by age (review feedback)
# ---------------------------------------------------------------------------

# Three databases: one big+old, one small+recent, one with no
# test.started at all (should never match an age-based filter).
_BIG_OLD = {
    "id": "db-big-old", "name": "Big Old",
    "metadata": {"test.started": "2020-01-01T00:00:00.000Z"},
    "summary": {"count": 1000000, "value_storage_kb": 900000,
                "index_storage_kb": 100000},
}
_SMALL_RECENT = {
    "id": "db-small-recent", "name": "Small Recent",
    "metadata": {"test.started":
                 (datetime.datetime.utcnow()).strftime(
                     "%Y-%m-%dT%H:%M:%S.000Z")},
    "summary": {"count": 10, "value_storage_kb": 1, "index_storage_kb": 1},
}
_NO_STARTED = {
    "id": "db-no-started", "name": "No Started Metadata",
    "metadata": {},
    "summary": {"count": 5, "value_storage_kb": 2, "index_storage_kb": 1},
}


class TestBulkDeleteBySize:
    def test_list_databases_over_size_filters_and_sorts_largest_first(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD, _NO_STARTED])
        iq = IQClient(base_url=BASE, load_env=False)
        matches = iq.list_databases_over_size(min_size_kb=1000)
        assert [t["id"] for t in matches] == ["db-big-old"]

    def test_delete_databases_over_size_dry_run_deletes_nothing(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        iq = IQClient(base_url=BASE, load_env=False)
        matches = iq.delete_databases_over_size(min_size_kb=1000)
        assert [t["id"] for t in matches] == ["db-big-old"]
        assert not any(
            c.request.method == "DELETE" for c in mocked_responses.calls)

    def test_delete_databases_over_size_actually_deletes_when_not_dry_run(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/databases/db-big-old", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.delete_databases_over_size(min_size_kb=1000, dry_run=False)
        delete_calls = [c for c in mocked_responses.calls
                        if c.request.method == "DELETE"]
        assert len(delete_calls) == 1
        assert "db-big-old" in delete_calls[0].request.url

    def test_list_databases_over_size_module_function(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        result = databases.list_databases_over_size(Transport(BASE), 1000)
        assert [t["id"] for t in result] == ["db-big-old"]


class TestBulkDeleteByAge:
    def test_list_databases_older_than_excludes_recent_and_unparseable(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD, _NO_STARTED])
        iq = IQClient(base_url=BASE, load_env=False)
        matches = iq.list_databases_older_than(days=30)
        assert [t["id"] for t in matches] == ["db-big-old"]

    def test_delete_databases_older_than_dry_run_deletes_nothing(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        iq = IQClient(base_url=BASE, load_env=False)
        matches = iq.delete_databases_older_than(days=30)
        assert [t["id"] for t in matches] == ["db-big-old"]
        assert not any(
            c.request.method == "DELETE" for c in mocked_responses.calls)

    def test_delete_databases_older_than_actually_deletes_when_not_dry_run(
            self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/databases/db-big-old", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.delete_databases_older_than(days=30, dry_run=False)
        delete_calls = [c for c in mocked_responses.calls
                        if c.request.method == "DELETE"]
        assert len(delete_calls) == 1
        assert "db-big-old" in delete_calls[0].request.url

    def test_list_databases_older_than_module_function(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases",
            json=[_SMALL_RECENT, _BIG_OLD])
        result = databases.list_databases_older_than(Transport(BASE), 30)
        assert [t["id"] for t in result] == ["db-big-old"]


# ---------------------------------------------------------------------------
# IQ-PYTHON-010: Database Management
# ---------------------------------------------------------------------------

class TestDatabaseManagement:
    def test_delete_test_sends_delete(self, mocked_responses):
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/databases/db-del", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.delete_test(database_id="db-del")
        assert mocked_responses.calls[0].request.method == "DELETE"
        assert "db-del" in mocked_responses.calls[0].request.url

    def test_delete_test_uses_default_database(self, mocked_responses):
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/databases/default-db", status=204)
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("default-db")
        iq.delete_test()
        assert "default-db" in mocked_responses.calls[0].request.url

    def test_delete_test_requires_database_id(self, monkeypatch):
        monkeypatch.delenv("TCIQ_DATABASE_ID", raising=False)
        iq = IQClient(base_url=BASE, load_env=False)
        with pytest.raises(IQQueryError, match="no database_id"):
            iq.delete_test()

    def test_delete_test_module_function_requires_id(self):
        with pytest.raises(IQError):
            databases.delete_test(Transport(BASE), "")

    def test_rename_test_sends_put_with_new_name(self, mocked_responses):
        # CONFIRMED against a real server 2026-09-17: PUT /databases/<id>
        # rejects a partial body -- {"name": ...} alone 400s
        # (RESOURCE_ID_MISMATCH), and even {"id": ..., "name": ...} 500s
        # with a real Go nil-map panic. The only body that works is the
        # full record from GET /databases/<id> with just "name" changed
        # -- see databases.rename_test()'s docstring for the full story.
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json={"id": "db-1", "name": "Old Name", "description": "",
                  "metadata": {"test.owner": "someone"}})
        mocked_responses.add(
            responses_lib.PUT, BASE + "/databases/db-1",
            json={"id": "db-1", "name": "New Name", "description": "",
                  "metadata": {"test.owner": "someone"}})
        iq = IQClient(base_url=BASE, load_env=False)
        result = iq.rename_test("New Name", database_id="db-1")
        body = json.loads(mocked_responses.calls[-1].request.body)
        assert body["name"] == "New Name"
        assert body["id"] == "db-1"
        assert body["metadata"] == {"test.owner": "someone"}
        assert result["name"] == "New Name"

    def test_rename_test_uses_default_database(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/default-db",
            json={"id": "default-db", "name": "Old Name"})
        mocked_responses.add(
            responses_lib.PUT, BASE + "/databases/default-db",
            json={"id": "default-db", "name": "Renamed"})
        iq = IQClient(base_url=BASE, load_env=False)
        iq.use_test("default-db")
        iq.rename_test("Renamed")
        assert "default-db" in mocked_responses.calls[-1].request.url

    def test_rename_test_module_function_requires_name(self):
        with pytest.raises(IQError):
            databases.rename_test(Transport(BASE), "db-1", "")

    def test_rename_test_module_function_requires_id(self):
        with pytest.raises(IQError):
            databases.rename_test(Transport(BASE), "", "New Name")

    def test_delete_test_server_error_raises_iqrequesterror(self, mocked_responses):
        # 2026-09-04 final-audit gap: every other DELETE/PUT-based
        # database-management test above mocks only the 200/204 happy
        # path -- the "server rejects the request" failure mode for
        # delete_test()/rename_test() specifically was previously covered
        # only indirectly, via test_transport.py's generic GET-based
        # error test.
        mocked_responses.add(
            responses_lib.DELETE, BASE + "/databases/db-del",
            json={"message": "database is in use"}, status=409)
        iq = IQClient(base_url=BASE, load_env=False)
        with pytest.raises(IQRequestError):
            iq.delete_test(database_id="db-del")

    def test_rename_test_server_error_raises_iqrequesterror(self, mocked_responses):
        mocked_responses.add(
            responses_lib.GET, BASE + "/databases/db-1",
            json={"id": "db-1", "name": "Old Name"})
        mocked_responses.add(
            responses_lib.PUT, BASE + "/databases/db-1",
            json={"message": "name already in use"}, status=409)
        iq = IQClient(base_url=BASE, load_env=False)
        with pytest.raises(IQRequestError):
            iq.rename_test("New Name", database_id="db-1")


# ---------------------------------------------------------------------------
# IQ-PYTHON-002: AION config wired through IQClient
# ---------------------------------------------------------------------------

class TestAionConfigWiring:
    def test_aion_params_passed_to_resolve_config(self, monkeypatch):
        """IQClient forwards aion_* params; when all three AION creds are
        given and no other address is set, it calls discover_via_aion."""
        from tciqrestclient import config as config_mod
        calls = []

        original = config_mod.resolve_config

        def spy(*args, **kwargs):
            calls.append(kwargs)
            return original(*args, base_url="http://10.0.0.1:9200", **{
                k: v for k, v in kwargs.items()
                if k not in ("base_url",)
            })

        monkeypatch.setattr(config_mod, "resolve_config", spy)
        IQClient(base_url="http://10.0.0.1:9200", load_env=False,
                 aion_url="https://aion.example.com",
                 aion_username="user",
                 aion_password="pass",
                 aion_node_name="node-a",
                 aion_port_name="orion-res",
                 aion_ca_cert="/path/to/ca.pem")
        assert calls[0]["aion_url"] == "https://aion.example.com"
        assert calls[0]["aion_username"] == "user"
        assert calls[0]["aion_password"] == "pass"
        assert calls[0]["aion_node_name"] == "node-a"
        assert calls[0]["aion_port_name"] == "orion-res"
        assert calls[0]["aion_ca_cert"] == "/path/to/ca.pem"

    def test_transport_bearer_token_injected(self):
        """When config resolves an auth_token, Transport sets the
        Authorization header on all requests."""
        from unittest import mock
        from tciqrestclient import config as config_mod
        from tciqrestclient.config import IQConfig

        fake_cfg = IQConfig(
            base_url="http://10.0.0.1:9200",
            auth_token="test-bearer-token",
        )
        with mock.patch.object(config_mod, "resolve_config",
                               return_value=fake_cfg):
            iq = IQClient(base_url="http://10.0.0.1:9200", load_env=False)
        auth_header = iq._transport._session.headers.get("Authorization")
        assert auth_header == "Bearer test-bearer-token"

    def test_no_aion_token_means_no_auth_header(self):
        iq = IQClient(base_url=BASE, load_env=False)
        assert "Authorization" not in iq._transport._session.headers
