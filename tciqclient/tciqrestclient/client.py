"""IQClient -- the single public entry point for tciqrestclient.

    from tciqrestclient import IQClient

    iq = IQClient()  # everything from .env / environment -- see config.py
    rows = iq.query('Detailed Stream Results', 'live', user='jdoe')
    # or, pointing at a specific test directly:
    rows = iq.query('Detailed Stream Results', database_id='abc123')
    # or, with a hand-built/captured definition:
    rows = iq.query(definition=my_query_definition)
"""
from . import config as config_mod
from . import databases
from . import query as query_mod
from . import queries
from . import reports
from . import transport as transport_mod
from . import view_query_builder
from . import views
import json as _json

from .exceptions import IQQueryError, IQRequestError, IQViewError

#: query()'s default row limit when the caller doesn't pass one -- a
#: safety net against accidentally pulling every row of a multi-million-
#: row test. Pass limit=None to leave the view/definition's own limit
#: untouched instead.
DEFAULT_QUERY_LIMIT = 1000

#: query(name=..., auto_repair=True)'s cap on how many "unknown
#: attribute" columns it will strip-and-retry for before giving up and
#: re-raising. Confirmed against a real view/database pair where a
#: single-stack test's database was missing ~21 dual-IP/MAC/VLAN/IPv6/
#: VXLAN/MPLS/TCP/UDP-config columns at once -- a view with many optional
#: per-protocol columns can legitimately need this many retries, so this
#: is generous headroom rather than a number derived from anything.
MAX_AUTO_REPAIR_ATTEMPTS = 100

#: metadata["test.running"] values (case-insensitive) treated as "yes,
#: this test is currently live" -- same convention as config.py's
#: TCIQ_DEBUG truthy parsing.
_RUNNING_TRUTHY = ("1", "true", "yes", "on")


def _is_running(test):
    value = (test.get("metadata") or {}).get("test.running")
    return isinstance(value, str) and value.strip().lower() in _RUNNING_TRUTHY


def _normalize_test_live(test_live):
    """Normalize query()/list_view_columns()'s test_live= to True (live),
    False (snapshot/eot), or None (no preference given -- the combined
    default with data_type=/table_index= also omitted is snapshot, per
    IQ-PYTHON-004).

    Accepts a real bool, or -- case-insensitively -- the strings "live"
    (-> True) or "eot"/"snapshot" (-> False), since a caller thinking in
    terms of "give me the live data" naturally reaches for that word, not
    a bare boolean. Any other string raises rather than being silently
    misinterpreted; any other non-string value is coerced with bool().
    """
    if test_live is None:
        return None
    if isinstance(test_live, str):
        value = test_live.strip().lower()
        if value in ("live", "true"):
            return True
        if value in ("eot", "snapshot", "false"):
            return False
        raise IQQueryError(
            "test_live must be True/False or one of the strings "
            "'live'/'eot'/'snapshot' (case-insensitive) -- got %r" %
            (test_live,))
    return bool(test_live)


class IQClient(object):
    """Python-native client for TestCenter IQ's orion-res results
    service.

    Nothing about the connection is hardcoded: every argument below can
    instead come from the environment or a ``.env`` file -- see
    ``tciqrestclient.config`` for the full list of ``TCIQ_*`` variables. Calling
    ``IQClient()`` with no arguments at all works on a properly
    configured machine.
    """

    def __init__(self, base_url=None, host=None, port=None,
                 install_dir=None, database_id=None, timeout=None,
                 use_https=False, load_env=True, env_file=None,
                 session=None, debug=None,
                 aion_url=None, aion_username=None, aion_password=None,
                 aion_node_name=None, aion_port_name=None, aion_ca_cert=None,
                 verify=None):
        """Connect to orion-res.

        Arguments:
        base_url        -- Full base URL, e.g. 'http://127.0.0.1:9200'.
                           Highest-priority way to point at orion-res.
        host / port     -- Explicit orion-res address (skips discovery).
        install_dir     -- STC install dir to discover orion-res's address
                           from (stcbll.ini / orion-res.yaml).
        database_id     -- Default database (test) id for query()/get_test()
                           calls made on this client. Can be changed later
                           with use_test(), or overridden per call.
        timeout         -- HTTP request timeout, in seconds.
        use_https       -- Use https:// when composing a base URL.
        load_env        -- Load a .env file before reading environment
                           variables (default True).
        env_file        -- Explicit .env file path (None searches upward from
                           the current directory, python-dotenv's default).
        session         -- Optional requests.Session to use (mainly for tests).
        debug           -- Print every request's method/URL/JSON body before
                           sending. None (default) falls back to TCIQ_DEBUG.
        aion_url        -- AION platform base URL, e.g.
                           'https://aion.example.com'. When given along with
                           aion_username/aion_password, orion-res's address is
                           discovered via AION's inventory API. Falls back to
                           TCIQ_AION_URL in the environment.
        aion_username   -- AION login email. Falls back to TCIQ_AION_USERNAME.
        aion_password   -- AION login password. Falls back to
                           TCIQ_AION_PASSWORD.
        aion_node_name  -- Optional AION node name to restrict discovery.
                           Falls back to TCIQ_AION_NODE_NAME.
        aion_port_name  -- Name of the orion-res port entry in AION product-
                           instances (default 'iq', confirmed against a
                           real AION org 2026-09-08). Falls back to
                           TCIQ_AION_PORT_NAME.
        aion_ca_cert    -- Optional CA certificate path for AION HTTPS.
                           Falls back to TCIQ_AION_CA_CERT.
        verify          -- TLS certificate verification for the *main*
                           orion-res connection (separate from
                           aion_ca_cert=, which only covers the AION
                           login itself). True (verify normally), False
                           (skip verification -- only for a deployment
                           you already trust, e.g. a lab server with a
                           self-signed certificate), or a CA bundle file
                           path -- exactly like `requests`' own verify=
                           parameter. None (default) falls back to
                           TCIQ_VERIFY_SSL, then to normal verification
                           if that's unset too. Confirmed needed
                           2026-09-22 against a real lab deployment
                           whose HTTPS certificate is self-signed.
        """
        cfg = config_mod.resolve_config(
            base_url=base_url, host=host, port=port, install_dir=install_dir,
            database_id=database_id, timeout=timeout, use_https=use_https,
            load_env=load_env, env_file=env_file, debug=debug,
            aion_url=aion_url, aion_username=aion_username,
            aion_password=aion_password, aion_node_name=aion_node_name,
            aion_port_name=aion_port_name, aion_ca_cert=aion_ca_cert,
            verify=verify,
        )
        self._config = cfg
        self._transport = transport_mod.Transport(
            cfg.base_url, timeout=cfg.timeout, session=session,
            debug=cfg.debug, auth_token=cfg.auth_token, verify=cfg.verify)
        self._default_database_id = cfg.database_id
        #: Raw projection fragments query()'s auto_repair dropped on its
        #: most recent call. Empty list if none were dropped, if the last
        #: query() call didn't use name=/auto_repair=True, or if it did
        #: but the view's view_type is one of the "single"-query kinds
        #: (see view_query_builder.build_query_definition()). For a
        #: "multi"-query kind (currently: histogram, boxplot -- one query
        #: per provider/statistic), this is instead a dict of
        #: {<name>: [<dropped fragment>, ...]} keyed the same way the
        #: returned rows are. Nothing is printed for any of this -- check
        #: here instead if you want to know whether a query's result is
        #: missing any columns.
        self.last_dropped_columns = []

    @property
    def base_url(self):
        return self._config.base_url

    def __repr__(self):
        return "<IQClient base_url=%r>" % (self._config.base_url,)

    # -- tests / databases (PLAN.md steps 2-3) -----------------------------

    def list_tests(self, owner=None, detail="summary"):
        """List tests. `owner` filters client-side on
        metadata["test.owner"] (the "Run By" column in the GUI)."""
        return databases.list_tests(self._transport, detail=detail,
                                    owner=owner)

    def get_test(self, database_id=None):
        """Get full metadata for one test. Uses the current default test
        (see use_test()) when database_id is omitted."""
        return databases.get_test(
            self._transport, database_id or self._require_database_id())

    def use_test(self, database_id):
        """Set the default database (test) id for subsequent query()/
        get_test()/generate_report() calls."""
        self._default_database_id = database_id

    def delete_test(self, database_id=None):
        """Delete a test database (permanently removes stored results).

        This is irreversible. CI/CD pipelines can use this to clean up
        completed test results after processing them.

        Uses the default database set via use_test() when database_id is
        omitted.
        """
        databases.delete_test(
            self._transport,
            database_id or self._require_database_id())

    def rename_test(self, new_name, database_id=None):
        """Rename a test database.

        Uses the default database set via use_test() when database_id is
        omitted.
        """
        return databases.rename_test(
            self._transport,
            database_id or self._require_database_id(),
            new_name)

    def get_database_schema(self, database_id=None):
        """Get the full schema for a database including table and field info.

        Returns the extended database record (detail=full). The schema
        structure depends on the orion-res server version. Use
        list_table_names() and list_fields() for structured access to the
        tables and attributes within.

        Uses the default database set via use_test() when database_id is
        omitted.
        """
        return databases.get_database_schema(
            self._transport,
            database_id or self._require_database_id())

    def list_table_names(self, database_id=None):
        """List the available tables within a database.

        Returns a list of table descriptor dicts. Each includes 'name' and
        'kind' ('result_set' or 'dimension_set' -- see
        tciqrestclient.databases.list_table_names()). Use list_fields() to discover
        columns within a specific table.

        Uses the default database set via use_test() when database_id is
        omitted.
        """
        return databases.list_table_names(
            self._transport,
            database_id or self._require_database_id())

    def list_fields(self, table_name=None, database_id=None):
        """List available fields (attributes) in a database, optionally
        scoped to a specific table.

        Arguments:
        table_name  -- Optional table name (see list_table_names()'s
                       'name' key) to restrict the result. None (default)
                       returns fields from all tables.
        database_id -- Database to inspect. Uses the default set via
                       use_test() when omitted.

        Return:
        List of field descriptor dicts. Each includes at minimum 'name';
        additional keys such as 'type' (the field's data type),
        'display_name', 'description', and 'unit' are included when
        reported by the server.
        """
        return databases.list_fields(
            self._transport,
            database_id or self._require_database_id(),
            table_name=table_name)

    def get_database_tables(self, database_id=None):
        """Alias for list_table_names() -- same thing, under the name
        requested in review feedback."""
        return databases.get_database_tables(
            self._transport, database_id or self._require_database_id())

    def get_table_schema(self, table_name, database_id=None):
        """Get one table's schema by name -- its own descriptor dict
        ("kind" plus "facts" or "attributes", per list_table_names()),
        rather than every table's.

        Arguments:
        table_name  -- The table's "name" (see list_table_names()) to
                       look up.
        database_id -- Database to inspect. Uses the default set via
                       use_test() when omitted.

        Raises:
        IQError -- if no table on this database has this name.
        """
        return databases.get_table_schema(
            self._transport, database_id or self._require_database_id(),
            table_name)

    def get_database_summary(self, database_id=None):
        """Get a database's summary metadata: row count and storage
        size. CONFIRMED real shape (see tests/fixtures.py): {"count",
        "value_storage_kb", "index_storage_kb"}.

        Uses the default database set via use_test() when database_id is
        omitted.
        """
        return databases.get_database_summary(
            self._transport, database_id or self._require_database_id())

    def list_databases_over_size(self, min_size_kb):
        """List databases at or over a total storage size (KB) --
        preview for delete_databases_over_size(); doesn't delete
        anything. See get_database_summary() for the size fields this is
        based on."""
        return databases.list_databases_over_size(self._transport, min_size_kb)

    def delete_databases_over_size(self, min_size_kb, dry_run=True):
        """Bulk-delete every database at or over a size threshold.

        This is destructive and irreversible, and can affect many
        databases at once. dry_run=True (the default) does NOT delete
        anything -- it only returns what would be deleted, same as
        list_databases_over_size(). Pass dry_run=False to actually
        delete.

        Arguments:
        min_size_kb -- Size threshold, in KB.
        dry_run     -- True (default): report matches without deleting.
                      False: delete every match.

        Return:
        The list of matching database dicts (whether or not they were
        actually deleted).
        """
        return databases.delete_databases_over_size(
            self._transport, min_size_kb, dry_run=dry_run)

    def list_databases_older_than(self, days):
        """List databases whose metadata["test.started"] is more than
        `days` days in the past -- preview for
        delete_databases_older_than(); doesn't delete anything."""
        return databases.list_databases_older_than(self._transport, days)

    def delete_databases_older_than(self, days, dry_run=True):
        """Bulk-delete every database older than a given age.

        This is destructive and irreversible, and can affect many
        databases at once. dry_run=True (the default) does NOT delete
        anything -- it only returns what would be deleted, same as
        list_databases_older_than(). Pass dry_run=False to actually
        delete.

        Arguments:
        days    -- Age threshold, in days.
        dry_run -- True (default): report matches without deleting.
                  False: delete every match.

        Return:
        The list of matching database dicts (whether or not they were
        actually deleted).
        """
        return databases.delete_databases_older_than(
            self._transport, days, dry_run=dry_run)

    # -- views --------------------------------------------------------------

    def list_views(self, timeout=None):
        """List all views. A server with many views can make this a
        large, slow response (each view includes its full
        effective_details.system_data.query_providers) -- pass timeout=
        to override the client's default for just this call."""
        return views.list_views(self._transport, timeout=timeout)

    def get_view(self, view_id, timeout=None):
        return views.get_view(self._transport, view_id, timeout=timeout)

    def find_view(self, name, timeout=None):
        """Find a view by display name, or None if no view has that
        name. See list_views() re: timeout=."""
        return views.find_view_by_name(
            self._transport, name, timeout=timeout)

    def list_view_columns(self, name, test_live=None, active_only=False,
                           timeout=None, data_type=None, table_index=None):
        """List a view's columns -- including each one's GUI display_name
        (e.g. "Rx Count") -- to see what query(name=name, filters=/sort=/
        group_by=) accepts (any of display_name, raw attribute path, bare
        column name, or alias_name resolve automatically; see query()'s
        docstring).

        Arguments:
        name        -- View name (looked up the same way as query(name=)).
        test_live   -- Which table -- same as query()'s test_live=.
        active_only -- False (default) lists every column the view's
                      query_provider supports. True restricts to only the
                      columns actually active on this table (what a query
                      for it actually returns).
        timeout     -- Same as query()'s timeout=, applied to the /views
                      lookup.
        data_type/table_index -- Advanced, rarely needed -- same as
                      query()'s. Prefer test_live= for the common
                      live/snapshot case.

        Return:
        List of {"name", "alias_name", "display_name"} dicts (see
        tciqrestclient.view_query_builder.list_view_columns()).
        """
        normalized_live = _normalize_test_live(test_live)
        if normalized_live is not None and data_type is None:
            data_type = "live" if normalized_live else "eot"
        view = views.find_view_by_name(self._transport, name, timeout=timeout)
        if not view:
            raise IQViewError("no view named %r" % (name,))
        return views.list_view_columns(
            view, table_index=table_index, data_type=data_type,
            active_only=active_only, transport=self._transport,
            timeout=timeout)

    def save_view(self, name, details=None, description="", definition=None):
        """Create/update a view.

        ``details`` (or its alias ``definition``) is a view's raw GUI table
        spec, not a query definition -- see tciqrestclient.views module docs. Typically
        read via get_view()/find_view(), modified, and passed back, rather
        than built from scratch.

        Both parameter names work:
            iq.save_view(name='My CI View', definition={...})
            iq.save_view(name='My CI View', details={...})
        """
        return views.save_view(self._transport, name, details=details,
                               description=description, definition=definition)

    def delete_view(self, view_id=None, name=None, timeout=None):
        """Delete a view.

        Exactly one of ``view_id`` or ``name`` must be given.

            iq.delete_view(view_id='abc123')
            iq.delete_view(name='My CI View')

        When ``name`` is given the view is looked up first (same cost as
        find_view()); pass ``timeout=`` to override the HTTP timeout for that
        lookup.
        """
        if name and view_id is None:
            view = views.find_view_by_name(
                self._transport, name, timeout=timeout)
            if not view:
                raise IQViewError("no view named %r" % (name,))
            view_id = view["id"]
        return views.delete_view(self._transport, view_id)

    # -- query (PLAN.md step 4) ----------------------------------------------

    def query(self, name=None, test_live=None, database_id=None, user=None,
              snapshot_name=None, filters=None, sort=None, group_by=None,
              time_range=None, limit=DEFAULT_QUERY_LIMIT, mode="once",
              raw_result=False, timeout=None, auto_repair=True,
              definition=None, data_type=None, table_index=None):
        """Run a query against a test's results and return rows as JSON.

        The common case is two arguments:

            iq.query('Detailed Stream Results', 'live', database_id='abc123')

        or, to find a user's own currently-running test automatically
        instead of looking up its database_id yourself:

            iq.query('Detailed Stream Results', 'live', user='jdoe')

        Exactly one of ``name`` or ``definition`` (an advanced escape
        hatch -- see below) must be given.

        name= builds an executable definition from the saved view's own
        query_provider templates (see tciqrestclient.views.get_view_definition() /
        tciqrestclient.view_query_builder) -- confirmed against real captures for
        table view_types, and also supported (but not yet real-capture-
        confirmed -- see tciqrestclient.view_query_builder's module docstring) for
        x_y_chart/pie_chart/histogram/boxplot; any other view_type raises
        IQViewError, since its result shape hasn't been checked. This is
        the *only* query method -- it looks at the view's own view_type
        internally rather than requiring a different call per widget
        type; the one visible difference is the return shape (see Return
        below), which follows the view's own query cardinality, not
        which method you called. filters=/sort=/etc. below are then
        layered on via tciqrestclient.query.merge_modifiers() -- note this
        qualifies filters against the view's outermost alias, which is
        NOT necessarily byte-identical to how the GUI's own filter box
        would shape the same filter (see tciqrestclient.view_query_builder module
        docstring); if a filtered name= query behaves unexpectedly,
        capture the GUI's own request with debug=True and compare.

        Arguments:
        name       -- Name of an existing view to build a definition
                      from.
        test_live  -- True for live (in-progress test) data, False (or
                      omitted) for snapshot/eot data -- the completed
                      result set, and the default per IQ-PYTHON-004's
                      "default to snapshot" requirement. Accepts a real
                      bool, or -- case-insensitively -- the strings
                      "live" or "eot"/"snapshot", so
                      test_live="live"/test_live="eot" both work exactly
                      as written, not just True/False. Ignored with
                      definition=.
        database_id -- Which test's results to query. Defaults to the
                      database set via use_test() / TCIQ_DATABASE_ID --
                      or see user= below to resolve it automatically
                      instead of looking it up yourself.
        user       -- Username/email to automatically find the right
                      database_id for, instead of passing database_id=
                      yourself (matches metadata["test.owner"], same as
                      list_tests(owner=)). Ignored if database_id= is
                      also given (database_id= always wins). Only
                      resolved automatically for test_live=True/"live":
                      finds the one test owned by `user` whose
                      metadata["test.running"] is true, and raises
                      IQQueryError if there's none or more than one
                      (pass database_id= explicitly to disambiguate).
                      For snapshot/eot data (test_live not "live") a user
                      can have any number of completed tests with no
                      signal for which one you mean, so user= alone
                      raises IQQueryError there too, asking for an
                      explicit database_id= (see list_tests(owner=user)
                      to find it) -- it's deliberately not guessed.
        snapshot_name -- With name= only: restrict results to one
                      specific named snapshot (mirrors the GUI's own
                      snapshot selector). None (default): no such
                      filter, i.e. every snapshot merged together, same
                      as before this argument existed. Only valid
                      against a table whose data_type is "eot" -- pass
                      test_live=False (or a "live" data_type otherwise
                      resolved away from) alongside it, or this raises
                      IQViewError; a "live" table (a test still running)
                      has no completed snapshots to filter by.
                      Additionally ignored by view_types that don't have
                      a snapshot filter at all even on their eot table
                      (x_y_chart). See
                      tciqrestclient.view_query_builder.build_query_definition()
                      for its confirmation status.
        filters    -- See tciqrestclient.query.merge_modifiers(). With name=, a
                      field can be given as its GUI display_name (e.g.
                      "Rx Count", case-insensitive), raw attribute path
                      (e.g. "rx_stream_stats.frame_count"), bare column
                      name (e.g. just "frame_count", when that's
                      unambiguous on this view -- see
                      tciqrestclient.view_query_builder.build_field_resolver()), or
                      internal alias (e.g. "rx_stream_stats_frame_count")
                      -- all resolve to the same column. Use
                      list_view_columns(name) to see what's available.
                      Ignored/not resolved with definition= (no view to
                      resolve display names against). For a "multi"-kind
                      view_type (see Return below), the same filters=
                      are applied to every one of its underlying queries.
        sort       -- See tciqrestclient.query.merge_modifiers(). Same field-name
                      resolution as filters= with name=.
        group_by   -- See tciqrestclient.query.merge_modifiers(). Same field-name
                      resolution as filters= with name=.
        time_range -- See tciqrestclient.query.merge_modifiers(). Same field-name
                      resolution as filters= with name=.
        limit      -- Max rows to return. Defaults to
                      DEFAULT_QUERY_LIMIT (1000) as a safety net against
                      accidentally pulling every row of a huge test --
                      pass a different number to change it, or limit=None
                      to leave the view/definition's own limit untouched
                      instead of overriding it.
        mode       -- 'once' (default). Live vs. snapshot both use a
                      single request/response -- there is no separate
                      live/subscription mode in this client.
        raw_result -- False (default) to get a list of row dicts. True
                      to get the raw `result` object (id, columns, rows,
                      pagination, timing) instead. For a "multi"-kind
                      view_type this applies per sub-query (see Return
                      below).
        timeout    -- Optional per-call HTTP timeout override, in
                      seconds, for this query only (doesn't change the
                      client's default). Applies to both the /queries
                      request(s) and, with name=, the /views lookup used
                      to find it by name -- GET /views returns every
                      view's full effective_details (needed to build the
                      query) and can be slow on a server with many
                      views. Use this instead of raising TCIQ_TIMEOUT
                      globally when a specific call is expected to take
                      a while. Narrowing the query itself with filters/
                      time_range/a smaller limit is usually the better
                      fix for a slow *query*, since a longer timeout
                      alone doesn't reduce how much work orion-res has to
                      do -- but a slow /views lookup has no such fix
                      short of a longer timeout.
        auto_repair -- With name= only (ignored for definition=): a
                      view's query_provider template is shared across
                      every database that uses that view, but not every
                      database's actual schema has every attribute the
                      template can reference -- e.g. a "dual IP/MAC/VLAN
                      config" column only exists for a test that actually
                      used that config; querying a single-stack test's
                      database with the same view can 400 with
                      VALIDATION_FAILED "unknown attribute name: ...".
                      True (default) catches that specific error, drops
                      the offending column from the built definition, and
                      retries (up to MAX_AUTO_REPAIR_ATTEMPTS times) --
                      silently; nothing is printed. Check
                      last_dropped_columns after the call if you want to
                      know whether (and which) columns were dropped, since
                      the returned rows are then missing whatever those
                      columns would have shown. False turns this off and
                      lets the original IQRequestError propagate instead.
                      For a "multi"-kind view_type, each underlying query
                      gets its own independent retry budget.
        definition -- Advanced escape hatch: a raw query definition (see
                      tciqrestclient.query module docs) to run directly -- as a
                      dict, or a JSON string -- instead of building one
                      from a view. Use name=/test_live= for everything
                      else; this is for a query captured directly from
                      the GUI's own network traffic, or one the built-in
                      view/filter helpers don't cover.
        data_type  -- Advanced, rarely needed: select the view's table by
                      its exact data_type string (e.g. "eot") instead of
                      via test_live=. Prefer test_live= -- this exists
                      for the rare view whose tables use a data_type
                      other than "live"/"eot". Case-insensitive. Ignored
                      with definition=. Takes precedence over test_live=
                      if both are given (don't pass both).
        table_index -- Advanced, rarely needed: which of the view's
                      tables to build a query for, by raw position,
                      bypassing test_live=/data_type= entirely (see
                      tciqrestclient.views.get_view_definition()). Almost never
                      needed -- test_live= (or data_type=) already
                      selects the right table by name for every view
                      seen in practice. Ignored with definition=.

        Return:
        For a view_type that's genuinely one query (table, x_y_chart,
        pie_chart -- or always, with definition=): a list of row dicts
        (columns zipped with each row), or the raw result object if
        raw_result=True. For a view_type that isn't (histogram: one
        query per provider; boxplot: one per statistic): a dict of
        {<name>: <rows or raw result>}, one entry per underlying query --
        see tciqrestclient.view_query_builder.build_query_definition()'s docstring
        for which view_types fall into which bucket. This is the one
        place the return shape depends on what you queried, not on which
        method you called (see name= above).
        """
        if isinstance(definition, str):
            try:
                definition = _json.loads(definition)
            except ValueError as e:
                raise IQQueryError(
                    "definition= is not valid JSON: %s" % e) from e

        if name and definition:
            raise IQQueryError(
                "specify either name= or definition=, not both")
        if not name and not definition:
            raise IQQueryError("specify name= or definition=")

        normalized_live = _normalize_test_live(test_live)
        if normalized_live is not None and data_type is None:
            data_type = "live" if normalized_live else "eot"

        resolve_field = None
        if name:
            # Same timeout= applies to the /views lookup as to the query
            # itself below -- listing views can be slow/large on a
            # server with many of them (see list_views()/find_view()).
            view = views.find_view_by_name(
                self._transport, name, timeout=timeout)
            if not view:
                raise IQViewError("no view named %r" % (name,))
            built = views.get_view_definition(
                view, table_index=table_index, data_type=data_type,
                snapshot_name=snapshot_name, transport=self._transport,
                timeout=timeout)
            # Lets filters=/sort=/group_by= use a column's GUI
            # display_name (e.g. "Rx Count"), raw attribute path (e.g.
            # "rx_stream_stats.frame_count"), or unambiguous bare column
            # name (e.g. "frame_count"), not just its internal alias
            # (e.g. "rx_stream_stats_frame_count") -- see
            # list_view_columns() to see what's available for a view.
            resolve_field = views.build_field_resolver(
                view, table_index=table_index, data_type=data_type,
                transport=self._transport, timeout=timeout)
        else:
            built = {"kind": "single", "definition": definition}

        if database_id:
            db_id = database_id
        elif user:
            db_id = self._resolve_database_id_for_user(
                user, want_live=bool(normalized_live))
        else:
            db_id = self._require_database_id()
        can_auto_repair = bool(name and auto_repair)

        if built["kind"] == "multi":
            rows = {}
            self.last_dropped_columns = {}
            for sub_name, sub_definition in built["definitions"].items():
                final_definition = query_mod.merge_modifiers(
                    sub_definition, filters=filters, sort=sort,
                    group_by=group_by, time_range=time_range, limit=limit,
                    resolve_field=resolve_field)
                # Recorded into self.last_dropped_columns[sub_name] as we
                # go (not just on success) -- so a sub-query that
                # ultimately raises still leaves behind whatever repairs
                # it *did* manage before that, same as the single-query
                # path below, and so do any sub-queries already finished
                # before this one failed.
                sub_dropped = self.last_dropped_columns.setdefault(
                    sub_name, [])
                result = self._run_with_auto_repair(
                    final_definition, db_id, mode, timeout, can_auto_repair,
                    sub_dropped)
                rows[sub_name] = (
                    result if raw_result else query_mod.rows_to_dicts(result))
            return rows

        final_definition = query_mod.merge_modifiers(
            built["definition"], filters=filters, sort=sort,
            group_by=group_by, time_range=time_range, limit=limit,
            resolve_field=resolve_field)
        self.last_dropped_columns = []
        result = self._run_with_auto_repair(
            final_definition, db_id, mode, timeout, can_auto_repair,
            self.last_dropped_columns)
        if raw_result:
            return result
        return query_mod.rows_to_dicts(result)

    def _run_with_auto_repair(self, final_definition, db_id, mode, timeout,
                               auto_repair, dropped_columns):
        """Shared by query()'s single- and multi-definition paths: run
        one query, retrying up to MAX_AUTO_REPAIR_ATTEMPTS times if it
        400s with an "unknown attribute" error auto_repair can strip and
        retry past (see view_query_builder.strip_unknown_attribute()).
        Appends each stripped fragment to `dropped_columns` (the caller's
        list, mutated in place) as it goes -- rather than building and
        returning its own list -- so a run that ultimately raises still
        leaves the caller's last_dropped_columns reflecting whatever was
        actually stripped before that, not just on a clean return.

        Return:
        The query's `result` object.

        Raises:
        IQRequestError -- CONFIRMED real scenario 2026-09-16 against a real
                        AION-managed orion-res server/view: every column a
                        view references can belong to the same underlying
                        table/measurement, which a specific database's
                        schema may lack *entirely* (not just one field of
                        it) -- e.g. all 5 columns of a real "NFVi Advanced
                        Kubernetes Platform Deployment Summary" view all
                        referenced the same missing
                        nfv_adv_k8s_instance_group_instance measurement.
                        Left unguarded, auto_repair would strip every one
                        of them one at a time and then send an empty
                        query, which orion-res rejects with an opaque
                        "at least one projection is required" 400 that
                        gives no hint the real cause was a wholesale
                        missing table. Raised here instead, before that
                        empty request is ever sent, once stripping would
                        leave the outermost query with zero projections --
                        deliberately IQRequestError (not a new exception
                        type) so every existing `except IQRequestError`
                        around a query() call -- there are dozens across
                        this repo's own examples -- keeps working exactly
                        as before; a real run against examples/
                        aion_end_to_end.py confirmed a different exception
                        class here would slip past its (and others')
                        existing handlers and crash instead of printing
                        the clean, expected message.
        """
        attempts_left = MAX_AUTO_REPAIR_ATTEMPTS if auto_repair else 0
        while True:
            try:
                response = queries.run_query(
                    self._transport, db_id, final_definition, mode=mode,
                    timeout=timeout)
                break
            except IQRequestError as e:
                raw_projection = (
                    view_query_builder.parse_unknown_attribute_error(
                        str(e)))
                if not raw_projection or attempts_left <= 0:
                    raise
                if not view_query_builder.strip_unknown_attribute(
                        final_definition, raw_projection):
                    raise
                attempts_left -= 1
                dropped_columns.append(raw_projection)
                _, outermost = query_mod._outermost_node(final_definition)
                if not outermost.get("projections"):
                    raise IQRequestError(
                        "auto_repair stripped every column this query "
                        "would have selected -- the underlying table/"
                        "measurement these columns belong to appears to "
                        "be entirely missing on this database, not just "
                        "one field of it (columns dropped: %s)" %
                        ", ".join(dropped_columns)) from e
        return response.get("result") or {}

    def _require_database_id(self):
        if not self._default_database_id:
            raise IQQueryError(
                "no database_id given and no default test set -- pass "
                "database_id=, call use_test(), or set TCIQ_DATABASE_ID")
        return self._default_database_id

    def _resolve_database_id_for_user(self, user, want_live):
        """query(user=...)'s auto-detection -- see query()'s own
        docstring for the user-facing contract. want_live=True is the
        only case this actually resolves anything: a user can have
        multiple completed (eot) tests with no signal for which one is
        meant, so that case always raises, asking for an explicit
        database_id= instead of guessing.
        """
        if not want_live:
            raise IQQueryError(
                "user=%r alone isn't enough to pick a snapshot (eot) "
                "test -- a user can have many completed tests. Pass "
                "database_id= explicitly (call list_tests(owner=%r) to "
                "find it)." % (user, user))
        matches = databases.list_tests(self._transport, owner=user)
        running = [t for t in matches if _is_running(t)]
        if not running:
            raise IQQueryError(
                "no live/running test found for user %r" % (user,))
        if len(running) > 1:
            raise IQQueryError(
                "multiple live/running tests found for user %r (ids: "
                "%s) -- pass database_id= explicitly to pick one" %
                (user, ", ".join(t["id"] for t in running)))
        return running[0]["id"]

    # -- reports --------------------------------------------------------------

    def list_report_templates(self):
        return reports.list_report_templates(self._transport)

    def get_report_template(self, template_id):
        return reports.get_report_template(self._transport, template_id)

    def find_unsupported_report_sections(self, template_id, timeout=None):
        """Find which sections of a report template reference a view
        whose real view_type isn't confirmed safe for report generation
        -- see generate_report()'s excluded_sections= and tciqrestclient/
        reports.py's module docstring for why this exists: a real,
        confirmed crash in the report-rendering frontend for at least
        one view_type ("x_y_chart"), root-caused against the actual
        orion-res/magellan-frontend source, not a guess.

        Pass the result straight to generate_report(excluded_sections=...)
        to skip those sections and get a real, complete report instead
        -- confirmed working end-to-end against a real server 2026-09-16
        (see examples/generate_report.py).

        Arguments:
        template_id -- Id of an existing report template.
        timeout     -- Passed through to the view lookup for each view a
                       section references.

        Return:
        List of section names -- [] if every section only references
        confirmed-safe (table) views.
        """
        template = reports.get_report_template(self._transport, template_id)
        return reports.find_unsupported_sections(
            self._transport, template, timeout=timeout)

    def generate_report(self, template_id, title=None, database_id=None,
                         database_name=None, format="pdf",
                         snapshot_filter=None, excluded_sections=None,
                         output_path=None, **extra):
        """Generate a report from an existing template and, when
        output_path is given, download it.

        Arguments:
        template_id -- Id of an existing report template.
        title       -- Report title. CONFIRMED required by a real server
                      2026-09-03 (see HANDOVER.md section 9) -- omitting
                      it 400s with "missing report title". Raises
                      IQReportError here (rather than a plain TypeError)
                      if left as None, so every tciqrestclient error is an IQError
                      subclass. An earlier version of this method didn't
                      expose it at all.
        database_id -- Database (test) to report on. Defaults to the one
                      set via use_test() / TCIQ_DATABASE_ID.
        database_name -- Optional -- see reports.create_report()'s
                      docstring. None (default) omits it; CONFIRMED
                      against a real server that this is fine.
        format      -- Output format. CONFIRMED lowercase 2026-09-03
                      (e.g. 'pdf', not 'PDF') -- the previous default,
                      'PDF', 400s with "unknown report format".
        snapshot_filter -- CONFIRMED against two real captures of the
                      GUI's own POST /reports request 2026-09-11 (see
                      tciqrestclient/reports.py's module docstring) -- an earlier
                      version of this parameter (test_live=/
                      snapshot_name=, sent as top-level "live"/
                      "snapshot_name" fields) was WRONG: neither exists
                      in a real request at all. The real mechanism is
                      parameters.test_snapshot_filter, a JSON-encoded
                      list of independent filter flags -- CONFIRMED real
                      values: "is_all_included" (every snapshot -- see
                      reports.REPORT_ALL_SNAPSHOTS_FILTER) and
                      "is_live_included" (also include live/in-progress
                      data -- see reports.REPORT_LIVE_INCLUDED_FILTER).
                      A single eot-only report sends just the first
                      flag; a "live and snapshot" report sends both
                      together -- pass a list to combine them the same
                      way:
                          generate_report(..., snapshot_filter=[
                              REPORT_ALL_SNAPSHOTS_FILTER,
                              REPORT_LIVE_INCLUDED_FILTER])
                      A bare string here becomes a one-item list. What a
                      request choosing one specific *named* snapshot
                      (rather than one of these two "include" flags)
                      looks like has NOT been captured -- if that exact
                      case matters, capture it from the GUI (report
                      wizard's snapshot picker, DevTools Network tab)
                      rather than assuming a snapshot's plain name
                      belongs in this list. None (default): parameters.
                      test_snapshot_filter is omitted entirely (this
                      method's pre-existing behavior -- unconfirmed
                      whether that differs from explicitly sending the
                      "include everything" flag above).
        excluded_sections -- CONFIRMED 2026-09-16, root-caused against
                      the actual orion-res/magellan-frontend source: a
                      report template's chart-type sections (view_type
                      "x_y_chart", confirmed) crash the report-rendering
                      frontend outright with a real, 100%-reproducible
                      TypeError -- universal across every database
                      tried, not data-specific. A list of section names
                      (the template's own `details.sections[].name`,
                      NOT the display name) to skip -- sent as
                      parameters.excluded_sections, JSON-encoded, the
                      same real field the GUI itself uses. Call
                      find_unsupported_report_sections(template_id) to
                      get this list generically instead of hardcoding
                      section names for one specific template. None
                      (default): omitted, matching this method's
                      pre-existing behavior.
        output_path -- Local path to download the finished report to.
        extra       -- Additional report fields (parameters, page_layout,
                      metadata, etc. -- see tciqrestclient/reports.py's module
                      docstring for confirmed real shapes) -- passed
                      through as-is. If extra["parameters"] is also
                      given, snapshot_filter=/excluded_sections= are
                      merged into it rather than replacing it.

        Return:
        The download path (if output_path given), else the raw report
        object (including its id, for a later download_report()/
        get_report() call once generation completes).
        """
        db_id = database_id or self._require_database_id()
        if snapshot_filter is not None:
            values = ([snapshot_filter] if isinstance(snapshot_filter, str)
                      else list(snapshot_filter))
            parameters = extra.setdefault("parameters", {})
            parameters["test_snapshot_filter"] = _json.dumps(values)
        if excluded_sections is not None:
            parameters = extra.setdefault("parameters", {})
            parameters["excluded_sections"] = _json.dumps(list(excluded_sections))
        report = reports.create_report(
            self._transport, template_id, db_id, title,
            format=format, database_name=database_name, **extra)
        if output_path:
            return reports.download_report_file(
                self._transport, report["id"], save_as=output_path)
        return report

    def get_report(self, report_id):
        return reports.get_report(self._transport, report_id)

    def download_report(self, report_id, save_as=None):
        return reports.download_report_file(
            self._transport, report_id, save_as=save_as)
