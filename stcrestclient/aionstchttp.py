"""
AionStcHttp -- StcHttp subclass with transparent AION authentication
and automatic token refresh.

Usage::

    from stcrestclient.aionstchttp import AionStcHttp

    stc = AionStcHttp(
        aion_url='https://aion.example.com',   # or set AION_URL
        username='user@example.com',            # or set AION_USERNAME
        password='secret',                      # or set AION_PASSWORD
        product_ca_cert='/path/to/ca_crt.pem',
    )
    stc.new_session(user_name='myuser', session_name='mysession')
    stc.create("port", under="project1", name="myport")
    stc.end_session()

The class transparently:
  - Discovers the default org and authenticates with AION IAM before connecting.
  - Discovers the stcapi host/port from AION inventory.
  - Injects the Bearer token into every HTTP request.
  - Proactively refreshes the token at 80% of its lifetime.
  - Reactively refreshes and retries on 401/4002 (AUTH_TOKEN_INVALID).

Original StcHttp users are unaffected -- they do not import this module.

"""
from __future__ import absolute_import
from __future__ import print_function

import os

try:
    from . import resthttp
    from .stchttp import StcHttp
    from .aionauth import AionAuth
except (ImportError, ValueError):
    import resthttp
    from stchttp import StcHttp
    from aionauth import AionAuth


class AionStcHttp(StcHttp):
    """StcHttp subclass with transparent AION IAM authentication.

    Handles login, product-instance discovery, token injection, and token
    refresh automatically.  The API is identical to StcHttp -- customers
    call the same methods with no changes.

    Arguments:
    aion_url        -- AION platform base URL, e.g. 'https://aion.example.com'.
                       Falls back to AION_URL environment variable if not supplied.
    username        -- AION user email / username.
                       Falls back to AION_USERNAME environment variable if not supplied.
    password        -- AION user password.
                       Falls back to AION_PASSWORD environment variable if not supplied.
    node_name       -- AION node name hosting the target product instance,
                       e.g. '10.109.120.117'.  Use together with ui_port to
                       uniquely identify an instance when multiple nodes or
                       instances are present.
    ui_port         -- UI port number of the target product instance.  When
                       multiple instances are running on the same node, supply
                       this together with node_name to uniquely identify the
                       desired one (e.g. 64006 selects the instance whose UI
                       port is 64006 and connects to its stcapi port).
                       Omit when only one instance is present.
    product_ca_cert -- Path to CA certificate file used to verify the stcapi
                       HTTPS connection, e.g. '/path/to/product_ca_cert.pem'.
                       Required when the stcapi endpoint uses HTTPS.
    aion_ca_cert    -- Path to CA certificate file used to verify the AION
                       platform HTTPS connection, e.g. '/path/to/aion_ca.pem'.
                       Required when the AION platform uses HTTPS.
    debug_print     -- Enable debug output.
    timeout         -- HTTP request timeout in seconds.

    Environment variables:
    AION_URL      -- AION platform base URL (used when aion_url is not supplied).
    AION_USERNAME -- AION user email / username (used when username is not supplied).
    AION_PASSWORD -- AION user password (used when password is not supplied).

    """

    def __init__(self, aion_url=None, username=None, password=None,
                 node_name=None, ui_port=None, product_ca_cert='', aion_ca_cert='',
                 debug_print=False, timeout=None):
        aion_url = aion_url or os.environ.get('AION_URL')
        username = username or os.environ.get('AION_USERNAME')
        password = password or os.environ.get('AION_PASSWORD')

        if not aion_url:
            raise RuntimeError('aion_url is required (or set AION_URL)')
        if not username:
            raise RuntimeError('username is required (or set AION_USERNAME)')
        if not password:
            raise RuntimeError('password is required (or set AION_PASSWORD)')

        # Discover org and login to AION
        self._auth = AionAuth(aion_url, ca_cert=aion_ca_cert,
                              debug_print=debug_print)
        self._auth.login(username, password)

        # Discover stcapi proto/host/port from AION inventory
        proto, host, port = self._auth.get_stcapi_endpoint(node_name=node_name, ui_port=ui_port)

        # Initialise StcHttp -- proto/host/port from inventory, token injected into base headers
        super(AionStcHttp, self).__init__(
            server=host,
            port=port,
            use_https=(proto == 'https'),
            ca_cert=product_ca_cert,
            debug_print=debug_print,
            timeout=timeout,
            token=self._auth.access_token,
        )

        # Replace self._rest with _AionRestHttp so every HTTP call goes
        # through the refresh wrapper.
        aion_rest = _AionRestHttp.__new__(_AionRestHttp)
        aion_rest.__dict__.update(self._rest.__dict__)
        aion_rest._proactive_cb = self._auth.needs_refresh
        aion_rest._refresh_cb = self._do_refresh
        self._rest = aion_rest

    def _do_refresh(self):
        """Refresh the AION token and return the new access token string."""
        if self._dbg_print:
            print('===> refreshing AION token')
        self._auth.refresh()
        if self._dbg_print:
            print('===> AION token refreshed successfully')
        return self._auth.access_token


class _AionRestHttp(resthttp.RestHttp):
    """RestHttp subclass that wraps every HTTP method with token-refresh logic.

    Two callbacks are installed by AionStcHttp after construction:
      _proactive_cb  -- () -> bool  : True if a proactive refresh is needed.
      _refresh_cb    -- () -> str   : Performs the refresh, returns new token.

    """

    def __init__(self, *args, **kwargs):
        super(_AionRestHttp, self).__init__(*args, **kwargs)
        self._proactive_cb = None
        self._refresh_cb = None

    def _wrap(self, fn, *args, **kwargs):
        """Run fn, refreshing the token proactively and on TokenExpiredError."""
        if self._proactive_cb and self._proactive_cb():
            if self._dbg_print:
                print('===> proactive token refresh triggered before request')
            new_token = self._refresh_cb()
            self.add_header('Authorization', 'Bearer ' + new_token)
            if self._dbg_print:
                print('===> proactive token refresh complete, retrying with new token')
        try:
            return fn(*args, **kwargs)
        except resthttp.TokenExpiredError:
            if self._dbg_print:
                print('===> token expired (401/4002), triggering reactive refresh')
            if self._refresh_cb:
                new_token = self._refresh_cb()
                self.add_header('Authorization', 'Bearer ' + new_token)
                if self._dbg_print:
                    print('===> reactive token refresh complete, retrying request')
                return fn(*args, **kwargs)
            raise

    def get_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).get_request, *args, **kwargs)

    def post_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).post_request, *args, **kwargs)

    def put_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).put_request, *args, **kwargs)

    def delete_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).delete_request, *args, **kwargs)

    def download_file(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).download_file, *args, **kwargs)

    def upload_file(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).upload_file, *args, **kwargs)

    def upload_file_mp(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).upload_file_mp, *args, **kwargs)

    def upload_files(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).upload_files, *args, **kwargs)

    def bulk_get_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).bulk_get_request, *args, **kwargs)

    def bulk_put_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).bulk_put_request, *args, **kwargs)

    def bulk_post_request(self, *args, **kwargs):
        return self._wrap(super(_AionRestHttp, self).bulk_post_request, *args, **kwargs)
