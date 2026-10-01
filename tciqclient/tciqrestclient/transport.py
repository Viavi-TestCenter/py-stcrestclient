"""Thin HTTP transport over orion-res's bare REST endpoints.

Root paths only (e.g. ``/databases``, ``/queries``) -- the Swagger doc's
``/api/res/`` prefix is only used when proxied through a separate iq-data
service and is intentionally not used here (PLAN.md, section 2.1).

Bearer-token authentication is optional: pass ``auth_token=`` to inject an
``Authorization: Bearer <token>`` header on every request.  This is used for
AION deployments where orion-res sits behind AION's auth layer; direct
(non-AION) installs leave ``auth_token`` as None and send no auth header.

TLS certificate verification is controlled by ``verify=`` -- ``None``
(default) leaves ``requests``'/a caller-supplied ``session``'s own default
behavior untouched; ``True``/``False``/a CA bundle path are passed through
on every request exactly like the same-named ``requests`` parameter,
overriding the session's own default. Needed for a real lab deployment
whose HTTPS certificate is self-signed -- CONFIRMED 2026-09-22.
"""
import json
import time

import requests

from .exceptions import IQRequestError


class Transport:
    """Minimal JSON-in/JSON-out HTTP client bound to one base URL."""

    def __init__(self, base_url, timeout=120, session=None, debug=False,
                 auth_token=None, verify=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.debug = debug
        self._session = session or requests.Session()
        if auth_token:
            self._session.headers.update(
                {"Authorization": "Bearer " + auth_token})
        # None (default) means "don't override" -- omitted from every
        # request below, so a caller-supplied `session=` keeps whatever
        # `session.verify` it already has (e.g. a lab's self-signed cert
        # handled by setting `session.verify = False` before passing it
        # in) instead of this always winning over it. True/False/a CA
        # bundle path are passed through as-is on every request,
        # overriding the session's own default -- CONFIRMED needed
        # against a real labserver 2026-09-22 that put a self-signed-cert
        # HTTPS proxy in front of a previously-plain-HTTP deployment.
        self.verify = verify

    def get(self, path, params=None, timeout=None):
        return self._request_json("GET", path, params=params, timeout=timeout)

    def post(self, path, json_body=None, params=None, timeout=None):
        return self._request_json(
            "POST", path, json=json_body, params=params, timeout=timeout)

    def put(self, path, json_body=None, params=None, timeout=None):
        return self._request_json(
            "PUT", path, json=json_body, params=params, timeout=timeout)

    def delete(self, path, params=None, timeout=None):
        return self._request_json("DELETE", path, params=params, timeout=timeout)

    def get_raw(self, path, params=None, timeout=None):
        """GET a non-JSON resource (e.g. a downloaded report file) and
        return its raw bytes."""
        resp = self._send("GET", path, params=params, timeout=timeout)
        return resp.content

    def _request_json(self, method, path, timeout=None, **kwargs):
        resp = self._send(method, path, timeout=timeout, **kwargs)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as e:
            raise IQRequestError(
                "%s %s returned non-JSON content: %s" %
                (method, path, e)) from e

    def _send(self, method, path, timeout=None, **kwargs):
        url = self.base_url + path
        effective_timeout = timeout if timeout is not None else self.timeout
        if self.verify is not None:
            kwargs.setdefault("verify", self.verify)

        if self.debug:
            self._debug_print_request(method, url, effective_timeout, kwargs)

        started = time.monotonic()
        try:
            resp = self._session.request(
                method, url, timeout=effective_timeout, **kwargs)
        except requests.RequestException as e:
            if self.debug:
                print("<- %s %s FAILED after %.3fs: %s" % (
                    method, url, time.monotonic() - started, e))
            raise IQRequestError("%s %s failed: %s" % (method, url, e)) from e

        if self.debug:
            print("<- %s %s -> %s in %.3fs" % (
                method, url, resp.status_code, time.monotonic() - started))

        if not resp.ok:
            raise IQRequestError(
                "%s %s returned %s: %s" %
                (method, url, resp.status_code, resp.text[:500]))
        return resp

    @staticmethod
    def _debug_print_request(method, url, timeout, kwargs):
        print("-> %s %s (timeout=%s)" % (method, url, timeout))
        params = kwargs.get("params")
        if params:
            print("   params: %s" % json.dumps(params))
        body = kwargs.get("json")
        if body is not None:
            print("   body:")
            print(json.dumps(body, indent=2))
