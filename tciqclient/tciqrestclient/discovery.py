"""Local discovery of the TestCenter IQ (orion-res) service address from
on-disk STC configuration files.

orion-res's address is not requested over the network; it's read from
configuration files already present in the STC installation directory.
Given that directory, two files are checked, in this order:

1. ``<install_dir>/stcbll.ini``, ``[enhancedResults]`` section -- populated
   when orion-res runs on a *different* host than this STC installation (a
   "remote" IQ server)::

       [enhancedResults]
       orionResServiceUrl=http://10.1.2.3:9200
       orionResServicePublicUrl=http://lab-server.example.com:9200

   ``orionResServicePublicUrl`` is preferred over ``orionResServiceUrl``
   when both are set, since it's the address reachable from outside the
   LabServer host. Either may be a bare ``host:port`` or a full URL.

2. ``<install_dir>/orion-res/etc/orion-res.yaml``, ``service.addr`` --
   populated when orion-res runs locally, alongside this STC installation
   (a "local" IQ server)::

       service:
         addr: 127.0.0.1:9200

Both files use the same relative paths and formats on Windows and Linux.
AION discovery is not yet implemented -- pass an explicit host/port or
base URL for AION deployments until support is added.
"""
import configparser
import os
import re

from .exceptions import IQConnectionError

try:
    import yaml
except ImportError:
    yaml = None

#: Relative path, under an STC install directory, to the config file that
#: names a *remote* orion-res (IQ) service.
STCBLL_INI_RELPATH = "stcbll.ini"

#: Relative path, under an STC install directory, to the config file that
#: names a *local* (co-located) orion-res (IQ) service.
ORION_RES_YAML_RELPATH = os.path.join("orion-res", "etc", "orion-res.yaml")


def _strip_matching_quotes(value):
    """A raw TCIQ_INSTALL_DIR (or an install_dir= kwarg copy-pasted from
    one) can arrive with a literal, matching pair of quotes still
    attached -- e.g. ``TCIQ_INSTALL_DIR="C:\\Program Files\\Viavi Solutions\\TestCenter"`` set directly in a Windows
    cmd.exe session. cmd.exe's own ``set`` keeps the quotes as part of
    the variable's actual value (unlike a ``.env`` file, where
    python-dotenv already strips a matching pair on its own -- this
    only matters for a real, pre-set environment variable, or a value
    passed straight through some other way that also doesn't strip
    them). Strips one matching leading/trailing ``"``/``'`` pair;
    anything else (no quotes, or a lone/mismatched one) is left
    untouched rather than guessed at.
    """
    if (isinstance(value, str) and len(value) >= 2
            and value[0] == value[-1] and value[0] in "\"'"):
        return value[1:-1]
    return value


def discover_iq_address(install_dir):
    """Find the (host, port) of the orion-res service for the given STC
    installation.

    Raises IQConnectionError if install_dir doesn't exist, or neither
    stcbll.ini nor orion-res.yaml yields a usable address.
    """
    install_dir = _strip_matching_quotes(install_dir)
    if not install_dir or not os.path.isdir(install_dir):
        raise IQConnectionError(
            "STC install_dir not found: %r" % (install_dir,))

    address = _from_stcbll_ini(install_dir)
    if address:
        return address

    address = _from_orion_res_yaml(install_dir)
    if address:
        return address

    raise IQConnectionError(
        "could not discover the orion-res service address under %r -- "
        "checked %s ([enhancedResults] orionResServicePublicUrl / "
        "orionResServiceUrl) and %s (service.addr). Pass host=/port= or "
        "base_url= explicitly instead." % (
            install_dir, STCBLL_INI_RELPATH, ORION_RES_YAML_RELPATH))


def _from_stcbll_ini(install_dir):
    path = os.path.join(install_dir, STCBLL_INI_RELPATH)
    if not os.path.isfile(path):
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(path)
    except configparser.Error as e:
        raise IQConnectionError(
            "failed to parse %s: %s" % (path, e)) from e

    if not parser.has_section("enhancedResults"):
        return None

    for key in ("orionResServicePublicUrl", "orionResServiceUrl"):
        value = parser.get("enhancedResults", key, fallback="").strip()
        if value:
            return _parse_host_port(value, path)
    return None


def _from_orion_res_yaml(install_dir):
    path = os.path.join(install_dir, ORION_RES_YAML_RELPATH)
    if not os.path.isfile(path):
        return None
    if yaml is None:
        raise IQConnectionError(
            "found %s but PyYAML is not installed -- run: "
            "pip install pyyaml" % path)

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        raise IQConnectionError("failed to parse %s: %s" % (path, e)) from e

    service = data.get("service") or {}
    addr = service.get("addr")
    if not addr:
        return None
    return _parse_host_port(addr, path)


_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _parse_host_port(value, source_path):
    """Accept a bare 'host:port', or a URL like 'http://host:port/path'."""
    value = value.strip()

    if _URL_SCHEME_RE.match(value):
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if not parsed.hostname or not parsed.port:
            raise IQConnectionError(
                "%s: could not parse host/port from %r" %
                (source_path, value))
        return parsed.hostname, parsed.port

    if ":" not in value:
        raise IQConnectionError(
            "%s: expected 'host:port' or a URL, got %r" %
            (source_path, value))

    host, _sep, port_str = value.rpartition(":")
    try:
        port = int(port_str)
    except ValueError:
        raise IQConnectionError(
            "%s: expected 'host:port' with a numeric port, got %r" %
            (source_path, value))
    return host, port
