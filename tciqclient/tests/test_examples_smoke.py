"""Smoke tests for examples/*.py -- catch a Python-level bug (a typo'd
method/exception name, a wrong signature, a stale attribute) that
py_compile can't, without needing a real orion-res server.

This is deliberately NOT a correctness test of tciqrestclient itself (that's what
every other file in this directory is for) -- the mock data below is
just complete enough that each example's main() can run to completion
without raising. If an example needs a code change and one of these
starts failing with an actual traceback (not an assertion), that's a
real bug in the example; fix the example, not the mock.

See TESTING.md section 3.2 for how to *manually* exercise these same
scripts against a real server -- that's the real correctness check for
example scripts that only really prove themselves against live orion-res
behavior (in particular: the four unconfirmed widget query builders, and
anything discovery-related).
"""
import os
import re
import sys

import pytest
import responses as responses_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

BASE = "http://fake-orion-res:9200"
OWNER = "she83111"

DATABASES = [
    {"id": "db1", "name": "Test One",
     "metadata": {"test.owner": OWNER, "test.started": "2026-01-01T00:00:00Z",
                  "test.running": "false"},
     "summary": {"count": 10}},
    {"id": "db2", "name": "Test Two",
     "metadata": {"test.owner": OWNER, "test.started": "2026-01-02T00:00:00Z",
                  "test.running": "false"},
     "summary": {"count": 20}},
    # A currently-running test for OWNER -- run_live_query.py's query(...,
    # user=OWNER) needs exactly one of these to resolve automatically.
    {"id": "db3", "name": "Test Three (running)",
     "metadata": {"test.owner": OWNER, "test.started": "2026-01-03T00:00:00Z",
                  "test.running": "true"},
     "summary": {"count": 5}},
    # generate_report.py hardcodes owner="bha83166" (the real user's own
    # username, edited in directly -- not "she83111" like every other
    # example here) -- its own entry, separate from OWNER above, so that
    # example's list_tests(owner=...) call still finds something.
    {"id": "db4", "name": "Test Four",
     "metadata": {"test.owner": "bha83166", "test.started": "2026-01-04T00:00:00Z",
                  "test.running": "false"},
     "summary": {"count": 15}},
]

# Real shape (result_sets/dimension_sets, not "tables") -- see
# HANDOVER.md section 9 and tests/test_new_features.py's own
# SCHEMA_RESPONSE for the fuller story of why this isn't "tables".
SCHEMA_FULL = {
    "result_sets": [
        {"name": "eot_table", "facts": [
            {"name": "frame_count", "display_name": "Frame Count",
             "type": "integer"},
            {"name": "stream_block_name", "display_name": "Stream Block Name",
             "type": "string"},
        ]},
    ],
    "dimension_sets": [],
}

# A minimal but real-shaped provider template -- see
# tciqrestclient/view_query_builder.py's module docstring for what each field
# means. Just rich enough to let query(name=...)/list_view_columns()
# actually build and run a query instead of raising IQViewError.
PROVIDER = {
    "name": "synthetic_provider",
    "base_query": {"multi_result": {
        "subqueries": [{"alias": "view", "subqueries": []}]}},
    "attribute_query_updates": [
        {"name": "stream_block.name", "alias_name": "stream_block_name",
         "display_name": "Stream Block Name",
         "query_updates": [{"key": "multi_result/subqueries/0/projections",
                             "values": ["raw.stream_block_name as stream_block_name"]}]},
        {"name": "rx_stream_stats.frame_count",
         "alias_name": "rx_stream_stats_frame_count", "display_name": "Rx Count",
         "query_updates": [{"key": "multi_result/subqueries/0/projections",
                             "values": ["raw.rx_count as rx_stream_stats_frame_count"]}]},
    ],
    "fact_query_updates": [],
    "derived_fact_query_updates": [],
    "default_order_updates": {},
}

VIEW = {
    "id": "view-1", "name": "Detailed Stream Results",
    "details": {
        "view_type": "single_level_table",
        "user_data": {"tables": [
            {"data_type": "live", "query_provider": "synthetic_provider",
             "columns": ["stream_block.name"], "primary_dimension_attributes": []},
            {"data_type": "eot", "query_provider": "synthetic_provider",
             "columns": ["stream_block.name", "rx_stream_stats.frame_count"],
             "primary_dimension_attributes": []},
        ]},
    },
    "effective_details": {"system_data": {"query_providers": [PROVIDER]}},
}

QUERY_RESULT = {
    "result": {
        "columns": ["stream_block_name", "rx_stream_stats_frame_count"],
        "rows": [["sb1", "100"], ["sb2", "200"]],
    }
}

# -- AION mocks for discover_aion.py, matching test_aion_discovery.py's
# real endpoint shapes: GET org -> POST token (login) -> GET
# product-instances, in that order, per discover_via_aion() call.
AION_URL = "https://aion.example.com"
AION_ORG_RESP = {"id": "org-1"}
AION_TOKEN_RESP = {"access_token": "tok-abc", "refresh_token": "ref-xyz",
                    "expires_in": 3600}
AION_INSTANCES = [
    {"node": {"name": "some-node"},
     "ports": [{"name": "iq", "http": {"url": "http://10.0.0.9:9200"}}]},
]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # Hermetic against whatever real .env happens to exist on the machine
    # actually running these tests (e.g. a developer's own TCIQ_BASE_URL/
    # TCIQ_AION_* for manual testing against a real server) -- without
    # this, IQClient()'s own load_dotenv() call re-reads that real file
    # and silently undoes the delenv() calls below/in individual AION
    # tests, resolving to the developer's real server instead of the
    # mocked one and failing with a real (non-mock) connection error.
    monkeypatch.setattr("tciqrestclient.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("TCIQ_BASE_URL", BASE)
    for var in ("TCIQ_HOST", "TCIQ_PORT", "TCIQ_INSTALL_DIR", "TCIQ_DATABASE_ID",
                "TCIQ_AION_URL", "TCIQ_AION_USERNAME", "TCIQ_AION_PASSWORD",
                # Bare (no TCIQ_ prefix) fallback names consolidated with
                # stcrestclient's own AionStcHttp -- see config.py.
                "AION_URL", "AION_USERNAME", "AION_PASSWORD"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mocked_server():
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses_lib.GET, BASE + "/databases", json=DATABASES)

        # `responses` matches multiple registrations for the same URL in
        # strict FIFO order PER CALL, not by re-checking each one's own
        # matcher against every new request -- so a `?detail=full`
        # -matched entry only ever serves the *first* matching request;
        # any later call (even one that also satisfies that same
        # matcher) falls through to whatever's registered next. Several
        # examples here (inspect_database_schema.py in particular) hit
        # `?detail=full` more than once per run, so a static per-variant
        # `.add()` pair silently breaks after the first call. A callback
        # inspects each request itself and repeats indefinitely instead.
        def _database_by_id(db_json):
            def callback(request):
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(request.url).query)
                body = SCHEMA_FULL if query.get("detail") == ["full"] else db_json
                import json as _json
                return (200, {}, _json.dumps(body))
            return callback

        # fetch_view_data.py hardcodes a specific database id as its
        # "point at exactly this test" example -- not one of the
        # DATABASES list() returns, so it needs its own direct route.
        rsps.add_callback(
            responses_lib.GET, BASE + "/databases/k4s6ez3h25drbau7",
            callback=_database_by_id(
                {"id": "k4s6ez3h25drbau7", "name": "all-devices",
                 "metadata": {"test.owner": OWNER}}),
            content_type="application/json")
        for db in DATABASES:
            rsps.add_callback(
                responses_lib.GET, BASE + "/databases/%s" % db["id"],
                callback=_database_by_id(db), content_type="application/json")
        # Stateful views store, seeded with the one pre-existing VIEW --
        # manage_views.py's save_view()/find_view()/list_view_columns()/
        # query(name=...)/delete_view() cycle needs GET /views to actually
        # reflect a view POST /views just created (and stop reflecting one
        # DELETE /views/<id> just removed), or the "reuse"/"delete" halves
        # of that cycle never really execute -- a static single-item list
        # let the script silently fail its own find-view-back-by-name
        # check right after saving and return early, so this smoke test
        # reported PASSED while never exercising reuse/delete at all.
        views_store = [dict(VIEW)]

        def _views_list_cb(request):
            import json as _json
            return (200, {}, _json.dumps(list(views_store)))

        def _views_create_cb(request):
            import json as _json
            body = _json.loads(request.body or "{}")
            new_id = "view-%d" % (len(views_store) + 1)
            views_store.append({
                "id": new_id,
                "name": body.get("name"),
                "details": body.get("details"),
                "description": body.get("description", ""),
                # Deliberately no "effective_details" -- matches the real,
                # confirmed server quirk that a freshly saved view has no
                # system_data.query_providers of its own yet (HANDOVER.md
                # section 9); _find_provider_elsewhere() must find
                # "synthetic_provider" on VIEW (still in views_store) for
                # this example's own list_view_columns()/query(name=...)
                # calls to work, same as against a real server.
            })
            return (200, {}, _json.dumps({"id": new_id}))

        def _views_delete_cb(request):
            import re as _re
            match = _re.search(r"/views/([^/?]+)", request.url)
            view_id = match.group(1) if match else None
            views_store[:] = [v for v in views_store if v.get("id") != view_id]
            return (200, {}, "{}")

        rsps.add_callback(responses_lib.GET, BASE + "/views",
                           callback=_views_list_cb, content_type="application/json")
        rsps.add_callback(responses_lib.POST, BASE + "/views",
                           callback=_views_create_cb, content_type="application/json")
        rsps.add_callback(
            responses_lib.DELETE,
            re.compile(r"^" + re.escape(BASE) + r"/views/[^/]+$"),
            callback=_views_delete_cb, content_type="application/json")
        rsps.add(responses_lib.PUT, BASE + "/databases/db1",
                 json={"name": "renamed"})
        rsps.add(responses_lib.DELETE, BASE + "/databases/db1", json={})
        rsps.add(responses_lib.POST, BASE + "/queries", json=QUERY_RESULT)
        rsps.add(responses_lib.GET, BASE + "/report-templates",
                 json=[{"id": "tmpl1", "name": "Summary Report"}])
        # generate_report.py's find_unsupported_report_sections() call
        # fetches the template by id -- no "Traffic Test Report" here, so
        # it falls back to this one. Empty sections list means "nothing
        # to exclude" without needing a GET /views mock too.
        rsps.add(responses_lib.GET, BASE + "/report-templates/tmpl1",
                 json={"id": "tmpl1", "name": "Summary Report",
                       "details": {"sections": []}})
        rsps.add(responses_lib.POST, BASE + "/reports",
                 json={"id": "report-1", "status": "pending"})
        rsps.add(responses_lib.GET, BASE + "/reports/report-1/download",
                 body=b"%PDF-fake-report-bytes",
                 content_type="application/pdf")
        yield rsps, views_store


def _run(module_name):
    import importlib
    if module_name in sys.modules:
        del sys.modules[module_name]
    module = importlib.import_module(module_name)
    module.main()


@pytest.mark.parametrize("module_name", [
    "discover_local",
    "inspect_database_schema",
    "manage_views",
    "query_modifiers",
    "run_json_definition_query",
    "multi_database_query",
    "auto_repair_demo",
    "fetch_view_data",
    "run_view_query",
    "modify_query_definition",
])
def test_example_runs_without_error(mocked_server, module_name):
    _run(module_name)


def test_run_live_query_runs_without_error(mocked_server, monkeypatch):
    # Not in the parametrized list above: run_live_query.py's polling
    # loop calls a real time.sleep(POLL_INTERVAL_SEC) between polls --
    # harmless against a real server, but would add several real seconds
    # to every test run here. Stub it out so this stays as fast as every
    # other smoke test.
    monkeypatch.setattr("time.sleep", lambda *_: None)
    _run("run_live_query")


def test_manage_views_actually_exercises_reuse_and_delete(mocked_server, capsys):
    """test_example_runs_without_error[manage_views] above only proves the
    script doesn't raise -- it used to report PASSED even when the mocked
    GET /views never reflected the view the script had just POSTed, so
    find_view()'s post-save check failed and the script returned early,
    silently skipping the "reuse" (list_view_columns()/query(name=...))
    and "delete" steps entirely (see mocked_server's views_store comment
    above). Assert on the actual outcome instead of just "didn't crash"."""
    _rsps, views_store = mocked_server
    _run("manage_views")

    output = capsys.readouterr().out
    assert "Couldn't find the view back by name after saving" not in output
    assert "Confirmed saved" in output
    assert "active column(s) on the clone" in output
    assert "row(s) queried back from the clone" in output
    assert "Deleted." in output
    # The example's own finally-block delete_view() must have actually
    # removed the view it created -- only the original seeded VIEW is
    # left in the mocked server's view store afterward.
    assert [v["id"] for v in views_store] == [VIEW["id"]]


def test_generate_report_runs_without_error(mocked_server, monkeypatch, tmp_path):
    """generate_report.py -- the flagship example for IQ-PYTHON-011 -- was
    not previously in this file's parametrize list at all (it had only a
    dead, wrong-URL mock route left over from an abandoned attempt to add
    it: '/reports/templates' instead of the real '/report-templates').
    Runs in an isolated tmp_path so the report.pdf/report_waited.pdf it
    writes don't litter the repo.

    wait_for_report()'s poll needs its own GET /reports/report-1 mock
    (separate from the existing GET .../download one) -- a terminal,
    non-"queued"/"generating" status here means the smoke test's first
    poll succeeds immediately, without a real time.sleep(POLL_INTERVAL_SEC)."""
    rsps, _views_store = mocked_server
    rsps.add(responses_lib.GET, BASE + "/reports/report-1",
              json={"id": "report-1", "status": "completed"})
    monkeypatch.chdir(tmp_path)
    _run("generate_report")
    assert (tmp_path / "report.pdf").read_bytes() == b"%PDF-fake-report-bytes"
    assert (tmp_path / "report_waited.pdf").read_bytes() == (
        b"%PDF-fake-report-bytes")


def test_discover_aion_runs_without_error(monkeypatch):
    # The autouse _env fixture sets TCIQ_BASE_URL so every *other* smoke
    # test gets a working default -- but that env var takes precedence
    # over explicit aion_url=/aion_username=/aion_password= kwargs (see
    # tciqrestclient/config.py's resolve_config()), which would make this test
    # resolve straight to TCIQ_BASE_URL without ever touching AION
    # discovery at all. Remove it so this test actually exercises what
    # it's named for.
    monkeypatch.delenv("TCIQ_BASE_URL", raising=False)
    """discover_aion.py never reaches orion-res itself (it only resolves
    an address) -- a dedicated, narrower mock of just the AION IAM +
    inventory endpoints, matching test_aion_discovery.py's real shapes.

    Call order: 3 of discover_aion.py's 4 IQClient(aion_url=...) attempts
    use the correct password, so login succeeds for all 3 -- but only the
    first ("basic") completes discovery end-to-end, finding AION_INSTANCES'
    "iq" port (the real default confirmed 2026-09-08, see HANDOVER.md
    section 0f). The other two still raise client-side afterward, each for
    a different, deliberate reason: aion_node_name="10.109.120.117" never
    matches AION_INSTANCES' node ("some-node"), and
    aion_port_name="iq-results" never matches its "iq" port label -- both
    exercise the "no matching port" error path, just via different
    mismatches. The 4th attempt deliberately uses the wrong password, so
    its login call must fail instead. Each attempt's own GET org / GET
    product-instances calls are identical every time, so one registered
    response for each serves all of them; only the login (POST token)
    responses differ across the 4 attempts, hence the explicit sequence.
    """
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses_lib.GET, AION_URL + "/api/iam/organizations/default",
                  json=AION_ORG_RESP)
        rsps.add(responses_lib.GET, AION_URL + "/api/inv/product-instances",
                  json=AION_INSTANCES)
        for _ in range(3):
            rsps.add(responses_lib.POST, AION_URL + "/api/iam/oauth2/token",
                      json=AION_TOKEN_RESP)
        rsps.add(responses_lib.POST, AION_URL + "/api/iam/oauth2/token",
                 status=401, body="Unauthorized")
        _run("discover_aion")


def test_aion_end_to_end_runs_without_error(mocked_server, monkeypatch):
    """aion_end_to_end.py -- unlike test_discover_aion_runs_without_error
    above (which only proves *discovery* resolves an address and never
    touches orion-res itself), this one points AION discovery's resolved
    address straight at the same mocked orion-res server every other
    example in this file already exercises (BASE) -- so everything
    downstream (list_tests/list_views/query(name=...)/live/filters/
    auto_repair/multi-database) runs against the exact same VIEW/
    DATABASES/QUERY_RESULT fixtures the local-mode examples use. That's
    deliberate: it proves the AION path and the local path really do
    converge on identical client behavior once connected, which is this
    script's whole point (see its module docstring)."""
    monkeypatch.delenv("TCIQ_BASE_URL", raising=False)
    monkeypatch.setenv("TCIQ_AION_URL", AION_URL)
    monkeypatch.setenv("TCIQ_AION_USERNAME", "user@example.com")
    monkeypatch.setenv("TCIQ_AION_PASSWORD", "secret")
    rsps, _views_store = mocked_server
    rsps.add(responses_lib.GET, AION_URL + "/api/iam/organizations/default",
              json=AION_ORG_RESP)
    rsps.add(responses_lib.POST, AION_URL + "/api/iam/oauth2/token",
              json=AION_TOKEN_RESP)
    rsps.add(responses_lib.GET, AION_URL + "/api/inv/product-instances",
              json=[{"node": {"name": "some-node"},
                     "ports": [{"name": "iq", "http": {"url": BASE}}]}])
    _run("aion_end_to_end")


def test_manage_test_database_declines_are_safe(mocked_server, monkeypatch):
    """Runs manage_test_database.py's main() with both confirmation
    prompts declined -- proves the confirmation gate itself works (no
    destructive call fires) without needing a real disposable database."""
    inputs = iter(["no", "no"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    import manage_test_database
    manage_test_database.TARGET_DATABASE_ID = "db1"
    manage_test_database.main()


def test_manage_test_database_accept_branch_runs(mocked_server, monkeypatch, capsys):
    """The decline-branch test above never exercised the actual
    rename_test()/delete_test() calls or their print formatting (the
    script's whole reason to exist) -- only the confirmation gate. Answer
    the confirmation phrase both times so that code genuinely runs too."""
    import manage_test_database
    inputs = iter([manage_test_database.CONFIRM_PHRASE,
                   manage_test_database.CONFIRM_PHRASE])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    manage_test_database.TARGET_DATABASE_ID = "db1"
    manage_test_database.main()

    output = capsys.readouterr().out
    assert "Renamed. Server now reports: renamed" in output
    assert "Deleted." in output


def test_bulk_cleanup_databases_no_thresholds_set_is_a_noop(
        mocked_server, capsys):
    """Both MIN_SIZE_KB/MAX_AGE_DAYS default to None -- confirms the
    script refuses to list/delete anything rather than accidentally
    matching every database on a server just because it was run."""
    import bulk_cleanup_databases
    bulk_cleanup_databases.MIN_SIZE_KB = None
    bulk_cleanup_databases.MAX_AGE_DAYS = None
    bulk_cleanup_databases.main()

    output = capsys.readouterr().out
    assert "are both unset" in output


def test_bulk_cleanup_databases_age_based_decline_is_safe(
        mocked_server, monkeypatch):
    """All 4 DATABASES fixture entries are dated 2026-01-0x -- long over
    30 days old by the time this runs -- so MAX_AGE_DAYS=30 matches all
    of them. Declining the confirmation must fire zero DELETEs."""
    import bulk_cleanup_databases
    bulk_cleanup_databases.MIN_SIZE_KB = None
    bulk_cleanup_databases.MAX_AGE_DAYS = 30
    monkeypatch.setattr("builtins.input", lambda *_: "no")
    bulk_cleanup_databases.main()


def test_bulk_cleanup_databases_age_based_accept_deletes_all_matches(
        mocked_server, monkeypatch, capsys):
    """Same setup as the decline test above, but confirming for real --
    db1 already has a mocked DELETE route (shared with the
    manage_test_database.py tests); db2/db3/db4 need their own here.
    (db4 -- see DATABASES above -- is owned by "bha83166", not OWNER, but
    list_databases_older_than() filters by age, not owner, so it's a
    match here too.)"""
    rsps, _views_store = mocked_server
    rsps.add(responses_lib.DELETE, BASE + "/databases/db2", json={})
    rsps.add(responses_lib.DELETE, BASE + "/databases/db3", json={})
    rsps.add(responses_lib.DELETE, BASE + "/databases/db4", json={})

    import bulk_cleanup_databases
    bulk_cleanup_databases.MIN_SIZE_KB = None
    bulk_cleanup_databases.MAX_AGE_DAYS = 30
    monkeypatch.setattr(
        "builtins.input", lambda *_: bulk_cleanup_databases.CONFIRM_PHRASE)
    bulk_cleanup_databases.main()

    output = capsys.readouterr().out
    assert "4 database(s) older than 30 day(s)" in output
    assert "Deleted." in output
    delete_urls = [c.request.url for c in rsps.calls
                   if c.request.method == "DELETE"]
    assert any("db1" in u for u in delete_urls)
    assert any("db2" in u for u in delete_urls)
    assert any("db3" in u for u in delete_urls)
    assert any("db4" in u for u in delete_urls)
