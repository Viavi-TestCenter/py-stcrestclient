"""Real captured data (trimmed) from Vinod's browser Network tab, used as
fixture data so tests exercise tciqrestclient against the actual shapes orion-res
returns, not invented ones. See PLAN.md, section 2.2 and 2.3, for the full
untrimmed originals.
"""

# GET /databases?detail=summary -- trimmed to the fields tciqrestclient actually
# reads, and to 3 of the original 4 entries (dropping the row-count/
# storage-heavy "Untitled" one -- irrelevant to any test here).
DATABASES_RESPONSE = [
    {
        "id": "ipsqk4camfalbmcm",
        "name": "Qbv_Qbu_Rx_Analysis_On_Same_Port",
        "description": "",
        "metadata": {
            "application.id": "e8c43606b3924efbaa86f82bc47dd279",
            "application.name": "TestCenter",
            "test.configuration.name": "FRER_Qbu_Qbv_Rx_Analysis_On_Same_Port (1)",
            "test.duration_sec": "489052.421",
            "test.owner": "user",
            "test.owner.id": "",
            "test.running": "false",
            "test.started": "2021-03-16T09:34:04.000Z",
            "test.type.tags": "traffic,ieee1588v2,ieee8021as",
            "count": "1822",
        },
        "summary": {"count": 1822, "value_storage_kb": 920, "index_storage_kb": 5136},
    },
    {
        "id": "n43grmtulrhgnkae",
        "name": "SpirentIQ_demo_run_10streams",
        "description": "SpirentIQ vs SPLA",
        "metadata": {
            "application.id": "e8c43606b3924efbaa86f82bc47dd279",
            "application.name": "TestCenter",
            "test.configuration.name": "SpirentIQ_demo_run_1000streams",
            "test.duration_sec": "110.392",
            "test.owner": "user",
            "test.running": "false",
            "test.started": "2021-05-10T19:22:57.000Z",
            "test.type.tags": "traffic",
            "count": "245714",
        },
        "summary": {"count": 245714, "value_storage_kb": 61176, "index_storage_kb": 33152},
    },
    {
        "id": "bqfuklujp5f7rg52",
        "name": "stcuserdb",
        "description": "Spirent TestCenter User Model Database",
        "metadata": {
            "application.id": "762b2d02e36945b5bceafe7586807014",
            "application.version": "1.0",
            "latestInprogressImportTime": "2026-05-31 14:57:56",
        },
        "summary": {"count": 0, "value_storage_kb": 0, "index_storage_kb": 0},
    },
    {
        "id": "cwcmford7nag7d7v",
        "name": "Untitled",
        "description": "",
        "metadata": {
            "application.id": "e8c43606b3924efbaa86f82bc47dd279",
            "application.name": "TestCenter",
            "test.configuration.name": "65k_2port",
            "test.duration_sec": "838",
            "test.owner": "vinod.shelke@viavisolutions.com",
            "test.owner.id": "0aa6b8521dd74fd5af9c5260ca3a08b7",
            "test.running": "false",
            "test.started": "2026-05-31T08:57:35.000Z",
            "test.type.tags": "traffic",
            "count": "9260039",
        },
        "summary": {"count": 9260039, "value_storage_kb": 2838432, "index_storage_kb": 1084400},
    },
]

# The real multi_result query definition for the "Detailed Stream Results"
# view, exactly as captured (trimmed: fewer projections, since tciqrestclient never
# inspects individual projection strings -- only the tree shape, aliases,
# and the filters/groups/orders/limit/pagination siblings matter for the
# code under test).
QUERY_DEFINITION = {
    "multi_result": {
        "subqueries": [
            {
                "alias": "view",
                "subqueries": [
                    {
                        "alias": "rxss",
                        "subqueries": [],
                        "projections": [
                            "stream_block.name as stream_block_name",
                            "(rx_stream_stats.frame_count) as frame_count",
                        ],
                        "filters": [],
                        "groups": [],
                        "orders": [],
                    },
                    {
                        "alias": "txss",
                        "subqueries": [],
                        "projections": [
                            "stream_block.name as stream_block_name",
                            "(tx_stream_stats.frame_count) as frame_count",
                        ],
                        "filters": [],
                        "groups": [],
                        "orders": [],
                    },
                ],
                "projections": [
                    "rxss.test_snapshot_name as test_snapshot_name",
                    "txss.frame_count as tx_stream_stats_frame_count",
                    "rxss.frame_count as rx_stream_stats_frame_count",
                ],
                "filters": [
                    "rxss.tx_stream_stream_id=txss.tx_stream_stream_id",
                    "rxss.test_snapshot_name=txss.test_snapshot_name",
                ],
                "groups": [],
                "orders": [],
            }
        ],
        "projections": [
            "view.test_snapshot_name as test_snapshot_name",
            "view.tx_stream_stats_frame_count as tx_stream_stats_frame_count",
            "view.rx_stream_stats_frame_count as rx_stream_stats_frame_count",
        ],
        "filters": [],
        "groups": [],
        "orders": [
            "view.test_snapshot_name_order ASC",
            "view.tx_stream_stream_id ASC",
        ],
        "limit": 120,
        "pagination": {"mode": "forward"},
    }
}

# POST /queries response, trimmed to 3 of the original ~90 rows.
QUERY_RESPONSE = {
    "id": "8eb0e76913754eb085e8194b52b36c7c",
    "database": {"id": "n43grmtulrhgnkae", "name": "SpirentIQ_demo_run_10streams"},
    "datastore": {"id": "default"},
    "mode": "once",
    "context": None,
    "result": {
        "id": "8eb0e76913754eb085e8194b52b36c7c",
        "context": None,
        "started": "2026-08-05T10:52:16.6916488Z",
        "prepare_time": 0,
        "execute_time": 0.7037139,
        "columns": [
            "test_snapshot_name",
            "tx_stream_stats_frame_count",
            "rx_stream_stats_frame_count",
        ],
        "rows": [
            ["Snapshot_4Kstreams", "44841", "43227"],
            ["Snapshot_4Kstreams", "44841", "43227"],
            ["Snapshot_4Kstreams", "44841", "43227"],
        ],
        "pagination": {
            "mode": "forward",
            "cursor": "WyJTbmFwc2hvdF80S3N0cmVhbXMiLCI2NTUzNiIsIjEwMDYiXQ==",
            "at_head": True,
            "at_tail": False,
        },
    },
}

# A real view object, as returned by GET /views (captured from a live
# server with Vinod's own "Detailed Stream Results" view, trimmed of most
# of its ~35 columns for brevity). CONFIRMED not to be a wrapper around a
# `multi_result` definition -- see the module docstring in tciqrestclient/views.py.
# `details` is a GUI table spec: a view_type, and one or more `tables`
# entries (one per data_type -- "live" while a test runs, "eot" for its
# final snapshot here) naming a server-side `query_provider` template by
# string id (one of ~449 distinct providers seen across a real server's
# views) plus the columns/filters/orders/dimensions to show. There is no
# endpoint or documented mapping from (query_provider, columns) to an
# executable `multi_result` tree -- that translation happens in the GUI's
# own JS. QUERY_DEFINITION above is that *translation's output* for this
# one view, captured separately from the GUI's actual POST /queries call
# -- not derived from VIEW["details"] below.
VIEW = {
    "id": "view-1",
    "parent_id": "",
    "serial": 1,
    "name": "Detailed Stream Results",
    "description": "",
    "metadata": {},
    "details": {
        "view_type": "single_level_table",
        "show_snapshot_selector": True,
        "user_data": {
            "refresh_rate_in_msec": 1000,
            "tables": [
                {
                    "data_type": "live",
                    "query_provider": "live_table_stream_traffic",
                    "columns": [
                        "stream_block.name",
                        "tx_stream_stats.frame_count",
                        "rx_stream_stats.frame_count",
                    ],
                    "filters": [],
                    "orders": [],
                    "primary_dimension_attributes": [
                        "stream_block.name", "tx_stream.stream_id",
                        "tx_port.name", "rx_port.name",
                    ],
                },
                {
                    "data_type": "eot",
                    "query_provider": "eot_table_stream_traffic",
                    "columns": [
                        "stream_block.name",
                        "tx_stream_stats.frame_count",
                        "rx_stream_stats.frame_count",
                    ],
                    "filters": [],
                    "orders": [],
                    "primary_dimension_attributes": [
                        "test.snapshot_name", "stream_block.name",
                        "tx_stream.stream_id", "tx_port.name",
                        "rx_port.name",
                    ],
                },
            ],
        },
    },
}
