"""Discover the orion-res address from on-disk STC configuration files."""
import os
import textwrap

import pytest

from tciqrestclient import IQConnectionError
from tciqrestclient.discovery import discover_iq_address


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))


def test_missing_install_dir_raises(tmp_path):
    with pytest.raises(IQConnectionError):
        discover_iq_address(str(tmp_path / "does-not-exist"))


def test_no_config_files_raises(tmp_path):
    with pytest.raises(IQConnectionError):
        discover_iq_address(str(tmp_path))


def test_local_orion_res_yaml(tmp_path):
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"), """\
        service:
          addr: 127.0.0.1:9200
        """)
    assert discover_iq_address(str(tmp_path)) == ("127.0.0.1", 9200)


def test_remote_stcbll_ini_public_url_preferred(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=http://10.1.2.3:9200
        orionResServicePublicUrl=http://lab-server.example.com:9300
        """)
    assert discover_iq_address(str(tmp_path)) == (
        "lab-server.example.com", 9300)


def test_remote_stcbll_ini_falls_back_to_service_url(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=http://10.1.2.3:9200
        orionResServicePublicUrl=
        """)
    assert discover_iq_address(str(tmp_path)) == ("10.1.2.3", 9200)


def test_stcbll_ini_bare_host_port_no_scheme(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=10.1.2.3:9200
        """)
    assert discover_iq_address(str(tmp_path)) == ("10.1.2.3", 9200)


def test_stcbll_ini_takes_priority_over_yaml(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=http://remote-host:9200
        """)
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"), """\
        service:
          addr: 127.0.0.1:9200
        """)
    assert discover_iq_address(str(tmp_path)) == ("remote-host", 9200)


def test_falls_back_to_yaml_when_ini_section_empty(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=
        orionResServicePublicUrl=
        """)
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"), """\
        service:
          addr: 127.0.0.1:9200
        """)
    assert discover_iq_address(str(tmp_path)) == ("127.0.0.1", 9200)


def test_yaml_missing_service_addr_raises(tmp_path):
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"), """\
        service:
          other_key: value
        """)
    with pytest.raises(IQConnectionError):
        discover_iq_address(str(tmp_path))


def test_malformed_yaml_raises_with_helpful_message(tmp_path):
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"),
          "service: [unterminated")
    with pytest.raises(IQConnectionError, match="orion-res.yaml"):
        discover_iq_address(str(tmp_path))


def test_malformed_ini_raises_with_helpful_message(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), "not a valid ini [[[")
    with pytest.raises(IQConnectionError, match="stcbll.ini"):
        discover_iq_address(str(tmp_path))


def test_url_missing_port_raises(tmp_path):
    _write(str(tmp_path / "stcbll.ini"), """\
        [enhancedResults]
        orionResServiceUrl=http://10.1.2.3
        """)
    with pytest.raises(IQConnectionError):
        discover_iq_address(str(tmp_path))


def test_non_numeric_port_raises(tmp_path):
    _write(str(tmp_path / "orion-res" / "etc" / "orion-res.yaml"), """\
        service:
          addr: 127.0.0.1:not-a-port
        """)
    with pytest.raises(IQConnectionError):
        discover_iq_address(str(tmp_path))
