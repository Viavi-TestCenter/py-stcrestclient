"""tciqrestclient -- Python client for TestCenter IQ's orion-res results
service.

    from tciqrestclient import IQClient

    iq = IQClient()  # everything from .env / environment -- see tciqrestclient.config
    tests = iq.list_tests(owner='jdoe')
    iq.use_test(tests[0]['id'])
    rows = iq.query(definition=my_query_definition)  # NOT name=; see tciqrestclient.views

See README.md at the package root for a usage overview, ../HANDOVER.md for
the full architecture writeup, and tciqrestclient/query.py +
tciqrestclient/views.py for what's confirmed vs. still assumed about the
query/view DSL.
"""
from .client import IQClient, DEFAULT_QUERY_LIMIT
from .query import merge_modifiers, rows_to_dicts
from .exceptions import (
    IQError,
    IQConfigError,
    IQConnectionError,
    IQRequestError,
    IQQueryError,
    IQViewError,
    IQReportError,
)
from .version import __version__

__all__ = [
    "IQClient",
    "DEFAULT_QUERY_LIMIT",
    "merge_modifiers",
    "rows_to_dicts",
    "IQError",
    "IQConfigError",
    "IQConnectionError",
    "IQRequestError",
    "IQQueryError",
    "IQViewError",
    "IQReportError",
    "__version__",
]
