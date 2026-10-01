"""Configuration resolution for tciqrestclient -- nothing hardcoded.

Every connection detail can come from the environment (or a .env file,
loaded via python-dotenv) instead of a constructor argument, so
``IQClient()`` with zero arguments works on a properly configured
machine. Recognized variables:

    TCIQ_BASE_URL          -- full base URL, e.g. http://127.0.0.1:9200.
                              Skips discovery and host/port composition
                              entirely when set.
    TCIQ_HOST              -- orion-res host (explicit override).
    TCIQ_PORT              -- orion-res port (explicit override).
    TCIQ_INSTALL_DIR       -- STC install dir, for stcbll.ini/orion-res.yaml
                              discovery (see discovery.py).
    TCIQ_DATABASE_ID       -- default "current test" database id.
    TCIQ_TIMEOUT           -- HTTP request timeout, in seconds.
    TCIQ_DEBUG             -- 1/true/yes to print each request's method, URL,
                              and JSON body before sending it.
    TCIQ_AION_URL          -- AION platform base URL for AION-based discovery.
                              Falls back to the bare AION_URL env var (no
                              TCIQ_ prefix -- stcrestclient's own AionStcHttp
                              convention) if this isn't set, so a machine
                              already configured for stcrestclient's AION
                              login needs no extra config here. Consolidated
                              2026-09-30 -- see HANDOVER.md section 0h.
    TCIQ_AION_USERNAME     -- AION username (email) for AION discovery. Falls
                              back to the bare AION_USERNAME env var, same as
                              TCIQ_AION_URL above.
    TCIQ_AION_PASSWORD     -- AION password for AION discovery. Falls back to
                              the bare AION_PASSWORD env var, same as
                              TCIQ_AION_URL above.
    TCIQ_AION_NODE_NAME    -- Optional AION node name to restrict instance search.
    TCIQ_AION_PORT_NAME    -- Port name under which orion-res appears in AION
                              product-instances (default: 'iq', confirmed
                              against a real AION org 2026-09-08).
    TCIQ_AION_CA_CERT      -- Optional path to CA certificate for AION HTTPS.
    TCIQ_VERIFY_SSL        -- TLS certificate verification for the main
                              orion-res connection (separate from
                              TCIQ_AION_CA_CERT, which only covers the AION
                              login itself). "false"/"0"/"no"/"off"
                              (case-insensitive) disables verification
                              entirely; any other non-empty value is used
                              as a CA bundle file path; unset leaves
                              verification at its default (on). CONFIRMED
                              needed 2026-09-22 against a real lab
                              deployment whose HTTPS certificate is
                              self-signed.

Precedence: explicit constructor kwarg > environment variable / .env >
IQConfigError if nothing resolves the base URL. AION is the one
exception worth calling out: when aion_url= is passed as an explicit
kwarg, it outranks a merely-ambient TCIQ_BASE_URL/TCIQ_HOST/
TCIQ_INSTALL_DIR *environment* variable (consistent with "explicit kwarg
beats environment") but still loses to an explicit base_url=/host=/
install_dir= *kwarg* on that same call. AION resolved purely from
TCIQ_AION_* environment variables (no aion_url= kwarg given) remains the
lowest-priority option overall, behind every other environment variable
too -- see resolve_config()'s own comments for exactly where this
distinction is applied.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv

from . import discovery
from .exceptions import IQConfigError

#: Used when neither an explicit timeout nor TCIQ_TIMEOUT is given.
DEFAULT_TIMEOUT = 120.0

#: Env var values (case-insensitive) treated as "true" for TCIQ_DEBUG.
_TRUTHY = ("1", "true", "yes", "on")

#: Env var values (case-insensitive) treated as "false" for TCIQ_VERIFY_SSL.
_FALSY = ("0", "false", "no", "off")


@dataclass
class IQConfig:
    base_url: str
    database_id: Optional[str] = None
    timeout: float = DEFAULT_TIMEOUT
    debug: bool = False
    auth_token: Optional[str] = None
    #: None (default) leaves TLS verification at its normal default
    #: (on) -- passed straight through to Transport, which itself only
    #: overrides a caller-supplied session's own verify setting when
    #: this isn't None. True/False/a CA bundle path all work exactly
    #: like the same-named `requests` parameter -- see transport.py.
    verify: Any = None


def resolve_config(base_url=None, host=None, port=None, install_dir=None,
                    database_id=None, timeout=None, use_https=False,
                    load_env=True, env_file=None, debug=None,
                    aion_url=None, aion_username=None, aion_password=None,
                    aion_node_name=None, aion_port_name=None,
                    aion_ca_cert=None, verify=None):
    """Resolve connection configuration from explicit arguments first,
    then the environment / a .env file.

    Arguments:
    base_url        -- Full base URL. Highest-priority way to point at
                       orion-res; skips host/port composition and discovery.
    host / port     -- Explicit orion-res address (discovery override).
    install_dir     -- STC install dir to discover orion-res's address from
                       (stcbll.ini / orion-res.yaml).
    database_id     -- Default database id for query()/get_test() calls.
    timeout         -- HTTP request timeout, in seconds.
    use_https       -- Use https:// when composing a base URL from host/port
                       or a discovered address.
    load_env        -- Load a .env file before reading environment variables.
                       True by default; set False to rely on the process
                       environment only.
    env_file        -- Explicit .env file path. None uses python-dotenv's
                       default search (current + parent directories).
    debug           -- Print each request's method/URL/JSON body before
                       sending. None (default) falls back to TCIQ_DEBUG.
    aion_url        -- AION platform base URL, e.g. 'https://aion.example.com'.
                       When given (along with aion_username/aion_password),
                       orion-res's address is discovered via AION's inventory
                       API instead of stcbll.ini / orion-res.yaml. Falls back
                       to TCIQ_AION_URL, then to the bare AION_URL env var
                       (stcrestclient's own AionStcHttp convention, no TCIQ_
                       prefix) if that's unset too.
    aion_username   -- AION username (email). Falls back to TCIQ_AION_USERNAME,
                       then to the bare AION_USERNAME env var.
    aion_password   -- AION password. Falls back to TCIQ_AION_PASSWORD, then
                       to the bare AION_PASSWORD env var.
    aion_node_name  -- Optional AION node name to restrict instance search.
                       Falls back to TCIQ_AION_NODE_NAME.
    aion_port_name  -- Name of the orion-res port entry in AION product-
                       instances. Default: 'iq' (confirmed against a real
                       AION org 2026-09-08). Falls back to
                       TCIQ_AION_PORT_NAME.
    aion_ca_cert    -- Optional CA certificate path for AION HTTPS. Falls
                       back to TCIQ_AION_CA_CERT.
    verify          -- TLS certificate verification for the *main*
                       orion-res connection (separate from aion_ca_cert=,
                       which only covers the AION login itself). True
                       (verify normally), False (skip verification --
                       only for a deployment you already trust, e.g. a
                       lab server with a self-signed cert), or a CA
                       bundle file path, exactly like `requests`' own
                       verify= parameter. None (default) falls back to
                       TCIQ_VERIFY_SSL, then leaves verification at its
                       normal default (on) if that's unset too.

    Return:
    IQConfig

    Raises:
    IQConfigError -- if no base URL can be resolved from any source.
    """
    if load_env:
        # find_dotenv()/load_dotenv() search upward from the current
        # working directory by default when env_file is None.
        load_dotenv(dotenv_path=env_file)

    # Resolve AION params from env when not explicit. TCIQ_AION_* is the
    # primary, dedicated name for this package; stcrestclient's own
    # bare AION_URL/AION_USERNAME/AION_PASSWORD (no TCIQ_ prefix, used by
    # AionStcHttp) is tried as a lower-priority fallback -- consolidating
    # the two so a user who already has those set for stcrestclient gets
    # AION discovery working here too, with no extra config. One-way only:
    # stcrestclient/aionstchttp.py itself is untouched and does not fall
    # back to TCIQ_AION_*.
    resolved_aion_url = (
        aion_url or os.environ.get("TCIQ_AION_URL")
        or os.environ.get("AION_URL"))
    resolved_aion_username = (
        aion_username or os.environ.get("TCIQ_AION_USERNAME")
        or os.environ.get("AION_USERNAME"))
    resolved_aion_password = (
        aion_password or os.environ.get("TCIQ_AION_PASSWORD")
        or os.environ.get("AION_PASSWORD"))
    resolved_aion_node = aion_node_name or os.environ.get("TCIQ_AION_NODE_NAME")
    resolved_aion_port = (aion_port_name
                          or os.environ.get("TCIQ_AION_PORT_NAME")
                          or "iq")
    resolved_aion_ca = aion_ca_cert or os.environ.get("TCIQ_AION_CA_CERT")

    # Resolve timeout early so AION discovery honours the user's configured
    # value (the requirement mandates a configurable timeout, default 120 s).
    resolved_timeout = timeout
    if resolved_timeout is None:
        env_timeout = os.environ.get("TCIQ_TIMEOUT")
        resolved_timeout = float(env_timeout) if env_timeout else DEFAULT_TIMEOUT

    # An explicit aion_url= kwarg on *this* call is a clear, direct
    # request for AION discovery -- it should outrank a merely-ambient
    # TCIQ_BASE_URL/TCIQ_HOST/TCIQ_INSTALL_DIR environment variable the
    # same way every other explicit kwarg here already does, even though
    # it still loses to an explicit base_url=/host=/install_dir= kwarg on
    # this same call. AION resolved purely from TCIQ_AION_* environment
    # variables (no aion_url= kwarg) has no such claim to priority -- it
    # stays the lowest-priority option, only attempted when nothing else,
    # kwarg or env, has already resolved an address (the original,
    # unchanged behavior for that case).
    aion_explicit = aion_url is not None
    auth_token = None
    aion_discovered_url = None
    if (resolved_aion_url and resolved_aion_username and resolved_aion_password
            and not base_url and not host and not install_dir
            and (aion_explicit or (
                not os.environ.get("TCIQ_BASE_URL")
                and not os.environ.get("TCIQ_HOST")
                and not os.environ.get("TCIQ_INSTALL_DIR")))):
        aion_discovered_url, auth_token = _discover_from_aion(
            resolved_aion_url, resolved_aion_username, resolved_aion_password,
            resolved_aion_node, resolved_aion_port, resolved_aion_ca,
            use_https, resolved_timeout)

    resolved_base_url = (
        base_url
        or _compose_base_url(host, port, use_https)
        or (install_dir and _compose_base_url(
            *discovery.discover_iq_address(install_dir), use_https))
        or (aion_explicit and aion_discovered_url)
        or os.environ.get("TCIQ_BASE_URL")
        or _compose_base_url(
            os.environ.get("TCIQ_HOST"), os.environ.get("TCIQ_PORT"),
            use_https)
        or _discover_from_env(use_https)
        or aion_discovered_url
    )

    if not resolved_base_url:
        raise IQConfigError(
            "could not resolve the orion-res base URL. Provide one of: "
            "base_url=, host=/port=, install_dir=, or aion_url= with "
            "aion_username=/aion_password= -- or set TCIQ_BASE_URL, "
            "TCIQ_HOST (+ optional TCIQ_PORT), TCIQ_INSTALL_DIR, or "
            "TCIQ_AION_URL + TCIQ_AION_USERNAME + TCIQ_AION_PASSWORD in "
            "the environment or a .env file.")

    resolved_database_id = (
        database_id or os.environ.get("TCIQ_DATABASE_ID") or None)

    resolved_debug = debug
    if resolved_debug is None:
        resolved_debug = os.environ.get("TCIQ_DEBUG", "").lower() in _TRUTHY

    resolved_verify = verify
    if resolved_verify is None:
        env_verify = os.environ.get("TCIQ_VERIFY_SSL")
        if env_verify:
            resolved_verify = (
                False if env_verify.lower() in _FALSY else env_verify)

    return IQConfig(
        base_url=resolved_base_url.rstrip("/"),
        database_id=resolved_database_id,
        timeout=resolved_timeout,
        debug=resolved_debug,
        auth_token=auth_token,
        verify=resolved_verify,
    )


def _discover_from_aion(aion_url, username, password, node_name, port_name,
                         ca_cert, use_https, timeout):
    """Authenticate to AION and return (base_url, access_token)."""
    from . import aion_discovery
    try:
        host, port, token = aion_discovery.discover_via_aion(
            aion_url, username, password,
            node_name=node_name,
            orion_res_port_name=port_name,
            ca_cert=ca_cert,
            timeout=timeout,
        )
    except Exception as e:
        from .exceptions import IQConnectionError
        raise IQConnectionError(
            "AION discovery failed: %s" % e) from e
    return _compose_base_url(host, port, use_https), token


def _discover_from_env(use_https):
    install_dir = os.environ.get("TCIQ_INSTALL_DIR")
    if not install_dir:
        return None
    return _compose_base_url(*discovery.discover_iq_address(install_dir), use_https)


def _compose_base_url(host, port, use_https):
    if not host:
        return None
    scheme = "https" if use_https else "http"
    if port:
        return "%s://%s:%s" % (scheme, host, port)
    return "%s://%s" % (scheme, host)
