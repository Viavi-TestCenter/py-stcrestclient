"""
AION platform authentication and endpoint discovery.

Handles the interactions needed before talking to AION labserver:
  1. GET  /api/iam/organizations/default     -- discover org_id
  2. POST /api/iam/oauth2/token              -- login (password grant)
  3. POST /api/iam/oauth2/token              -- refresh (refresh_token grant)
  4. GET  /api/inv/product-instances         -- discover stcapi host/port

"""
from __future__ import absolute_import
from __future__ import print_function

import time

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import requests

# Fraction of token lifetime elapsed before a proactive refresh is triggered.
_REFRESH_THRESHOLD = 0.8


class AionError(Exception):
    """Raised when an AION IAM or inventory operation fails."""

    def __init__(self, message, http_status=None):
        self.http_status = http_status
        super(AionError, self).__init__(message)


class AionAuth(object):
    """
    Manages AION authentication and stcapi endpoint discovery.

    Typical usage::

        auth = AionAuth(aion_url='https://aion.example.com')
        org_id = auth.get_default_org()
        auth.login('user@example.com', 'password', org_id)
        proto, host, port = auth.get_stcapi_endpoint()
        # use auth.access_token as Bearer token for stcapi calls
        # call auth.refresh() to renew before expiry

    """

    def __init__(self, aion_url, ca_cert='', debug_print=False):
        """
        Arguments:
        aion_url    -- Base URL of the AION platform, e.g. 'https://aion.example.com'
        ca_cert     -- Path to CA certificate file used to verify the AION platform
                       HTTPS connection, e.g. '/path/to/aion_ca.pem'. 
        debug_print -- Enable debug print statements.
        """
        self._aion_url = aion_url.rstrip('/')
        self._ssl_verify = ca_cert if ca_cert else True
        self._dbg_print = bool(debug_print)
        self._access_token = None
        self._refresh_token = None
        self._expires_in = 86400
        self._last_refresh_time = 0.0

    def get_default_org(self):
        """Return the default organization ID from the AION platform.

          GET /api/iam/organizations/default

        Return:
        Organization ID string.

        """
        url = self._aion_url + '/api/iam/organizations/default'
        if self._dbg_print:
            print('===> GET %s' % url)
        resp = requests.get(url, verify=self._ssl_verify)
        if self._dbg_print:
            print('===> response status: %d %s' % (resp.status_code, resp.reason))
        if resp.status_code != 200:
            raise AionError(
                'failed to get default org: %d %s' % (resp.status_code, resp.text),
                resp.status_code)
        data = resp.json()
        if self._dbg_print:
            print('===> default org id: %s' % data['id'])
        return data['id']

    def login(self, username, password, org_id=None):
        """Login to the AION platform and store the resulting tokens.

          POST /api/iam/oauth2/token  {grant_type=password}

        If org_id is not supplied, get_default_org() is called automatically.

        Arguments:
        username -- AION user email / username.
        password -- AION user password.
        org_id   -- Organization ID to use as OAuth2 scope.  None to
                    auto-discover via get_default_org().

        """
        if org_id is None:
            org_id = self.get_default_org()
        url = self._aion_url + '/api/iam/oauth2/token'
        if self._dbg_print:
            print('===> POST %s' % url)
            print('  --- Params ---')
            print('    grant_type: password, username: %s, password: ******, scope: %s'
                  % (username, org_id))
        data = {
            'grant_type': 'password',
            'username': username,
            'password': password,
            'scope': org_id,
        }
        resp = requests.post(url, data=data, verify=self._ssl_verify)
        if self._dbg_print:
            print('===> response status: %d %s' % (resp.status_code, resp.reason))
        if resp.status_code != 200:
            raise AionError(
                'login failed: %d %s' % (resp.status_code, resp.text),
                resp.status_code)
        self._store_tokens(resp.json())
        if self._dbg_print:
            print('===> login succeeded, token expires_in: %ds' % self._expires_in)

    def refresh(self):
        """Refresh the access token using the stored refresh token.

          POST /api/iam/oauth2/token  {grant_type=refresh_token}

        Both access_token and refresh_token are replaced with the new values
        returned by IAM.

        """
        if not self._refresh_token:
            raise AionError('no refresh token available; call login() first')
        url = self._aion_url + '/api/iam/oauth2/token'
        if self._dbg_print:
            print('===> POST %s' % url)
            print('  --- Params ---')
            print('    grant_type: refresh_token')
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self._refresh_token,
        }
        resp = requests.post(url, data=data, verify=self._ssl_verify)
        if self._dbg_print:
            print('===> response status: %d %s' % (resp.status_code, resp.reason))
        if resp.status_code != 200:
            raise AionError(
                'token refresh failed: %d %s' % (resp.status_code, resp.text),
                resp.status_code)
        self._store_tokens(resp.json())
        if self._dbg_print:
            print('===> token refresh succeeded, new token expires_in: %ds' % self._expires_in)

    def get_stcapi_endpoint(self, node_name=None, ui_port=None):
        """Discover the stcapi host and port from AION inventory.

          GET /api/inv/product-instances

        Arguments:
        node_name -- Optional AION node name.  When supplied, only instances
                     on the named node are considered.
        ui_port   -- Optional integer UI port number.  When supplied, the
                     instance whose UI port (has_ui=true) matches this value
                     is selected.  When omitted, the first instance with a
                     stcapi port is used.

        Return:
        Tuple of (proto, host, port) for the stcapi product instance,
        where proto is 'http' or 'https' as reported by the inventory.

        """
        if not self._access_token:
            raise AionError('not logged in; call login() first')
        url = self._aion_url + '/api/inv/product-instances'
        if self._dbg_print:
            print('===> GET %s' % url)
        headers = {'Authorization': 'Bearer ' + self._access_token}
        resp = requests.get(url, headers=headers, verify=self._ssl_verify)
        if self._dbg_print:
            print('===> response status: %d %s' % (resp.status_code, resp.reason))
        if resp.status_code != 200:
            raise AionError(
                'failed to get product instances: %d %s' % (resp.status_code, resp.text),
                resp.status_code)
        instances = resp.json()
        for inst in instances:
            if node_name is not None and inst.get('node', {}).get('name') != node_name:
                continue
            ui_match = (ui_port is None)
            stcapi_url = None
            for p in inst.get('ports', []):
                http = p.get('http', {})
                name = p.get('name', '').lower()
                if not ui_match and http.get('has_ui') and urlparse(http.get('url', '')).port == ui_port:
                    ui_match = True
                if name == 'stcapi':
                    stcapi_url = http.get('url', '')
            if not ui_match or not stcapi_url:
                continue
            parsed = urlparse(stcapi_url)
            proto = parsed.scheme
            host = parsed.hostname
            port = parsed.port
            if not proto or not host or not port:
                raise AionError(
                    'stcapi port entry has invalid url: %s' % stcapi_url)
            if self._dbg_print:
                print('===> stcapi endpoint: %s://%s:%d' % (proto, host, port))
            return proto, host, port
        if node_name is not None and ui_port is not None:
            raise AionError(
                'no stcapi port entry found for node_name %s, ui_port %d' % (node_name, ui_port))
        if node_name is not None:
            raise AionError(
                'no stcapi port entry found for node_name %s' % node_name)
        if ui_port is not None:
            raise AionError(
                'no stcapi port entry found for ui_port %d' % ui_port)
        raise AionError('no stcapi port entry found in AION product instances')

    def needs_refresh(self):
        """Return True if the access token should be refreshed proactively.

        Triggers at 80% of the token lifetime to ensure the token does not
        expire during an active session.

        """
        if not self._access_token:
            return False
        elapsed = time.time() - self._last_refresh_time
        needed = elapsed >= self._expires_in * _REFRESH_THRESHOLD
        if needed and self._dbg_print:
            print('===> proactive token refresh needed (elapsed: %.0fs, threshold: %.0fs)'
                  % (elapsed, self._expires_in * _REFRESH_THRESHOLD))
        return needed

    @property
    def access_token(self):
        """Current access token string, or None if not logged in."""
        return self._access_token

    def _store_tokens(self, data):
        self._access_token = data['access_token']
        self._refresh_token = data['refresh_token']
        self._expires_in = float(data.get('expires_in', 86400))
        self._last_refresh_time = time.time()
