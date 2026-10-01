"""AION platform discovery for the orion-res (IQ) service.

On an AION deployment, orion-res's port is not written to stcbll.ini or
orion-res.yaml -- it is discovered dynamically via the AION inventory API:

  1. GET  <aion_url>/api/iam/organizations/default  -- discover org_id
  2. POST <aion_url>/api/iam/oauth2/token           -- password login
  3. GET  <aion_url>/api/inv/product-instances      -- find orion-res port

The orion-res service is expected to appear in product-instances as a port
entry whose ``name`` field is 'iq' (the default value of the
AION_ORION_RES_PORT_NAME constant below) -- CONFIRMED 2026-09-08 against a
real AION org (58 product-instances, 20+ of them carrying an 'iq' port,
zero named 'orion-res' -- see HANDOVER.md section 9). An earlier version
of this constant defaulted to 'orion-res', which never matched anything on
a real deployment; every real port URL found was also a bare
``scheme://host:port`` with no path component, so no such correction was
needed there. Override via the ``orion_res_port_name`` argument if your
deployment genuinely uses a different label.

AION also issues a Bearer access token that may be required for subsequent
calls to orion-res. ``discover_via_aion()`` returns the token alongside the
(host, port) tuple so the caller can inject it into the Transport.
"""
import time
from urllib.parse import urlparse

import requests

from .exceptions import IQConnectionError

#: Default name under which orion-res appears in AION product-instances
#: ports. CONFIRMED 'iq' against a real AION org 2026-09-08 (see module
#: docstring above) -- was wrongly 'orion-res' before that.
AION_ORION_RES_PORT_NAME = "iq"

#: Default HTTP timeout (seconds) applied to every AION IAM and inventory
#: request during discovery.  Matches IQClient's own DEFAULT_TIMEOUT in
#: config.py so neither value needs to be hardcoded in the other module.
AION_DISCOVERY_TIMEOUT = 120.0


class _AionIAMSession:
    """Lightweight AION IAM client -- just enough for orion-res discovery."""

    def __init__(self, aion_url, ca_cert=None, timeout=AION_DISCOVERY_TIMEOUT):
        self._url = aion_url.rstrip("/")
        self._verify = ca_cert if ca_cert else True
        self._timeout = timeout
        self._access_token = None
        self._refresh_token = None
        self._expires_in = 86400.0
        self._last_refresh = 0.0

    @property
    def access_token(self):
        return self._access_token

    def login(self, username, password, org_id=None):
        """Authenticate and store the resulting tokens."""
        if org_id is None:
            org_id = self._default_org()
        url = self._url + "/api/iam/oauth2/token"
        resp = requests.post(
            url,
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": org_id,
            },
            verify=self._verify,
            timeout=self._timeout,
        )
        if not resp.ok:
            raise IQConnectionError(
                "AION login failed (%s): %s" % (resp.status_code, resp.text[:300]))
        self._store_tokens(resp.json())

    def get_orion_res_endpoint(self, node_name=None,
                                port_name=AION_ORION_RES_PORT_NAME):
        """Query product-instances and return (host, port) for orion-res.

        Arguments:
        node_name -- Optional AION node name. When given, only instances on
                     that node are considered.
        port_name -- Name of the port entry to look for (default: 'iq').
        """
        if not self._access_token:
            raise IQConnectionError(
                "AION: not logged in; call login() first")
        url = self._url + "/api/inv/product-instances"
        headers = {"Authorization": "Bearer " + self._access_token}
        resp = requests.get(url, headers=headers, verify=self._verify,
                            timeout=self._timeout)
        if not resp.ok:
            raise IQConnectionError(
                "AION product-instances lookup failed (%s): %s" % (
                    resp.status_code, resp.text[:300]))
        instances = resp.json()
        for inst in instances:
            if (node_name is not None
                    and inst.get("node", {}).get("name") != node_name):
                continue
            for p in inst.get("ports", []):
                if p.get("name", "").lower() != port_name.lower():
                    continue
                port_url = (p.get("http") or {}).get("url", "")
                if not port_url:
                    continue
                parsed = urlparse(port_url)
                if not parsed.hostname or not parsed.port:
                    raise IQConnectionError(
                        "AION: orion-res port entry has invalid URL: %r"
                        % port_url)
                return parsed.hostname, parsed.port
        msg = ("AION: no port named %r found in product-instances" % port_name)
        if node_name is not None:
            msg += " for node_name=%r" % node_name
        raise IQConnectionError(msg)

    def _default_org(self):
        url = self._url + "/api/iam/organizations/default"
        resp = requests.get(url, verify=self._verify, timeout=self._timeout)
        if not resp.ok:
            raise IQConnectionError(
                "AION org discovery failed (%s): %s" % (
                    resp.status_code, resp.text[:300]))
        return resp.json()["id"]

    def _store_tokens(self, data):
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._expires_in = float(data.get("expires_in", 86400))
        self._last_refresh = time.time()


def discover_via_aion(aion_url, username, password, node_name=None,
                      orion_res_port_name=AION_ORION_RES_PORT_NAME,
                      ca_cert=None, timeout=AION_DISCOVERY_TIMEOUT):
    """Authenticate to AION and discover orion-res's host and port.

    Arguments:
    aion_url            -- AION platform base URL, e.g. 'https://aion.example.com'.
    username            -- AION user email / username.
    password            -- AION user password.
    node_name           -- Optional AION node name to restrict instance search.
    orion_res_port_name -- Name of the orion-res port entry in AION product-
                           instances. Default: 'iq' (confirmed against a
                           real AION org 2026-09-08). Override if your
                           deployment registers it under a different label.
    ca_cert             -- Optional path to a CA certificate bundle for verifying
                           AION's HTTPS certificate.
    timeout             -- HTTP request timeout in seconds applied to every
                           AION IAM and inventory request during discovery.
                           Default: 120.0 (AION_DISCOVERY_TIMEOUT). Pass None
                           to disable the timeout (not recommended in
                           production).

    Return:
    ``(host, port, access_token)`` -- the access_token is returned so the
    caller can inject it as a Bearer header when talking to orion-res on AION
    (which may require authentication, unlike a direct local install).

    Raises:
    IQConnectionError -- if authentication fails, the timeout is exceeded, or
                         no matching port is found.
    """
    session = _AionIAMSession(aion_url, ca_cert=ca_cert, timeout=timeout)
    session.login(username, password)
    host, port = session.get_orion_res_endpoint(
        node_name=node_name, port_name=orion_res_port_name)
    return host, port, session.access_token
