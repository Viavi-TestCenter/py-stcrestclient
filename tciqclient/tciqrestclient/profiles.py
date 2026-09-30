"""Result profiles (/profiles) -- CONFIRMED against a real server 2026-09-30.

A "profile" is a saved collection of views plus their dashboard layout --
i.e. what the TestCenter IQ GUI calls a results "template"/dashboard, not
to be confused with a single view (see tciqrestclient.views). Confirmed
real shape, `GET /profiles` against a live local server (112 real
profiles):

    {
      "id": "40cdae9295e94021b1e9b543593eb27b",
      "serial": 2,
      "name": "Consecutive Bad Packet Measurement Results",
      "description": "Result profile contains consecutive bad packet ...",
      "metadata": {"application.name": "TestCenter", ...},
      "details": {"layouts": [{"id": "<view id>", "location": "0,0"}, ...]},
      "views": [
        {"id": "<view id>", "parent_id": "", "serial": 0, "name": "",
         "description": "", "metadata": None, "details": None,
         "effective_details": None},
        ...
      ],
    }

`views` only carries each referenced view's id -- the rest of its fields
are always null/empty here, confirmed with both detail=summary and
detail=full (see below); use tciqrestclient.views.get_view() with a
view's id from this list to fetch its real definition.

`detail=` (query param, confirmed real): 'full' (the server's own
default when omitted) includes `details.layouts`; 'summary' sets
`details` to None instead, on every other field unchanged -- confirmed
byte-for-byte identical apart from that one key, same `views` list
either way, ~20% smaller response for one representative real profile
(1336 vs 1660 bytes). Unlike views.list_views() (which never exposes
detail= -- see its own docstring), this is exposed here since a real
deployment can have 100+ profiles and the difference, while modest per
profile, is a real, confirmed lever a caller may want.

`view_id=` (query param, confirmed real): restricts to only the profiles
whose `views` list references that view id (confirmed against a real
server: 2 of 112 profiles for one real view id, all correctly including
it; a nonexistent view id returns an empty list with a 200, not an
error).
"""


def list_profiles(transport, view_id=None, detail=None, timeout=None):
    """List all result profiles known to the server.

    Arguments:
    view_id -- Optional view id to filter by -- only profiles that
              reference this view (in their `views` list) are returned.
              Matched server-side (confirmed real query param).
    detail  -- 'full' (server default when omitted) or 'summary' (a
              somewhat smaller response -- excludes each profile's
              `details.layouts`; every other field, including `views`,
              is unchanged). See this module's docstring.
    timeout -- Override the client's default HTTP timeout for just this
              call.

    Return:
    List of profile dicts.
    """
    params = {}
    if view_id:
        params["view_id"] = view_id
    if detail:
        params["detail"] = detail
    return transport.get("/profiles", params=params or None, timeout=timeout) or []
