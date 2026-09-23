"""Nothing hardcoded: connection config resolves from explicit args first,
then TCIQ_* environment variables / a .env file.
"""
import textwrap

import pytest

from tciqrestclient.config import resolve_config, DEFAULT_TIMEOUT
from tciqrestclient.exceptions import IQConfigError

ENV_VARS = (
    "TCIQ_BASE_URL", "TCIQ_HOST", "TCIQ_PORT", "TCIQ_INSTALL_DIR",
    "TCIQ_DATABASE_ID", "TCIQ_TIMEOUT", "TCIQ_DEBUG",
    "TCIQ_AION_URL", "TCIQ_AION_USERNAME", "TCIQ_AION_PASSWORD",
    "TCIQ_AION_NODE_NAME", "TCIQ_AION_PORT_NAME", "TCIQ_AION_CA_CERT",
    "TCIQ_VERIFY_SSL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_no_source_raises(monkeypatch):
    with pytest.raises(IQConfigError):
        resolve_config(load_env=False)


def test_explicit_base_url_wins(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env:1111")
    cfg = resolve_config(base_url="http://explicit:9200", load_env=False)
    assert cfg.base_url == "http://explicit:9200"


def test_explicit_host_port(monkeypatch):
    cfg = resolve_config(host="10.1.2.3", port=9200, load_env=False)
    assert cfg.base_url == "http://10.1.2.3:9200"


def test_explicit_host_port_https(monkeypatch):
    cfg = resolve_config(host="10.1.2.3", port=9200, use_https=True,
                         load_env=False)
    assert cfg.base_url == "https://10.1.2.3:9200"


def test_explicit_install_dir_discovers(tmp_path):
    _write_orion_yaml(tmp_path)
    cfg = resolve_config(install_dir=str(tmp_path), load_env=False)
    assert cfg.base_url == "http://127.0.0.1:9200"


def test_env_base_url(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env:1111")
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-env:1111"


def test_env_host_port(monkeypatch):
    monkeypatch.setenv("TCIQ_HOST", "10.9.9.9")
    monkeypatch.setenv("TCIQ_PORT", "9200")
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://10.9.9.9:9200"


def test_env_install_dir_discovers(tmp_path, monkeypatch):
    _write_orion_yaml(tmp_path)
    monkeypatch.setenv("TCIQ_INSTALL_DIR", str(tmp_path))
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://127.0.0.1:9200"


def test_precedence_explicit_over_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env:1111")
    cfg = resolve_config(base_url="http://explicit:2222", load_env=False)
    assert cfg.base_url == "http://explicit:2222"


def test_precedence_base_url_over_host_port(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env-url:1111")
    monkeypatch.setenv("TCIQ_HOST", "should-not-be-used")
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-env-url:1111"


def test_database_id_from_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DATABASE_ID", "db-123")
    cfg = resolve_config(load_env=False)
    assert cfg.database_id == "db-123"


def test_database_id_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DATABASE_ID", "db-env")
    cfg = resolve_config(database_id="db-explicit", load_env=False)
    assert cfg.database_id == "db-explicit"


def test_timeout_defaults(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    cfg = resolve_config(load_env=False)
    assert cfg.timeout == DEFAULT_TIMEOUT


def test_timeout_from_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_TIMEOUT", "30")
    cfg = resolve_config(load_env=False)
    assert cfg.timeout == 30.0


def test_timeout_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_TIMEOUT", "30")
    cfg = resolve_config(timeout=5, load_env=False)
    assert cfg.timeout == 5


def test_debug_defaults_false(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    cfg = resolve_config(load_env=False)
    assert cfg.debug is False


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
def test_debug_from_env_truthy_values(monkeypatch, value):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DEBUG", value)
    cfg = resolve_config(load_env=False)
    assert cfg.debug is True


def test_debug_from_env_falsy_value(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DEBUG", "0")
    cfg = resolve_config(load_env=False)
    assert cfg.debug is False


def test_debug_explicit_true_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DEBUG", "0")
    cfg = resolve_config(debug=True, load_env=False)
    assert cfg.debug is True


def test_debug_explicit_false_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_DEBUG", "1")
    cfg = resolve_config(debug=False, load_env=False)
    assert cfg.debug is False


def test_verify_defaults_none(monkeypatch):
    # None -- not True -- so Transport knows to leave a caller-supplied
    # session's own verify setting alone instead of always overriding it.
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    cfg = resolve_config(load_env=False)
    assert cfg.verify is None


@pytest.mark.parametrize("value", ["0", "false", "False", "no", "off"])
def test_verify_from_env_falsy_values(monkeypatch, value):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_VERIFY_SSL", value)
    cfg = resolve_config(load_env=False)
    assert cfg.verify is False


def test_verify_from_env_ca_bundle_path(monkeypatch):
    # Confirmed real scenario 2026-09-22: a self-signed lab certificate
    # -- anything that isn't a recognized falsy token is treated as a CA
    # bundle path instead, exactly like `requests`' own verify= parameter.
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_VERIFY_SSL", "/etc/ssl/lab-ca.pem")
    cfg = resolve_config(load_env=False)
    assert cfg.verify == "/etc/ssl/lab-ca.pem"


def test_verify_explicit_false_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_VERIFY_SSL", "/etc/ssl/lab-ca.pem")
    cfg = resolve_config(verify=False, load_env=False)
    assert cfg.verify is False


def test_verify_explicit_true_overrides_env(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://x:1")
    monkeypatch.setenv("TCIQ_VERIFY_SSL", "false")
    cfg = resolve_config(verify=True, load_env=False)
    assert cfg.verify is True


def test_base_url_trailing_slash_stripped(monkeypatch):
    cfg = resolve_config(base_url="http://x:1/", load_env=False)
    assert cfg.base_url == "http://x:1"


# ---------------------------------------------------------------------------
# IQ-PYTHON-002: AION precedence -- an explicit aion_url= kwarg must
# outrank a merely-ambient TCIQ_BASE_URL/TCIQ_HOST/TCIQ_INSTALL_DIR
# *environment* variable (the same "explicit kwarg beats environment"
# rule every other option here already follows), while still losing to
# an explicit base_url=/host=/install_dir= *kwarg* on that same call. AION
# resolved purely from TCIQ_AION_* environment variables (no aion_url=
# kwarg) has no such claim and remains the lowest-priority option. Real
# bug, found 2026-09-03 -- see HANDOVER.md section 9.
# ---------------------------------------------------------------------------

def _stub_aion(monkeypatch, url="http://from-aion:9200", token="tok"):
    """Replace config._discover_from_aion with a spy that returns a fixed
    result without making a real network call."""
    from tciqrestclient import config as config_mod
    calls = []

    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return url, token

    monkeypatch.setattr(config_mod, "_discover_from_aion", fake)
    return calls


def test_explicit_aion_kwarg_overrides_env_base_url(monkeypatch):
    monkeypatch.setenv("TCIQ_BASE_URL", "http://should-not-be-used:1111")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(
        aion_url="https://aion.example.com", aion_username="u",
        aion_password="p", load_env=False)
    assert cfg.base_url == "http://from-aion:9200"
    assert len(calls) == 1


def test_explicit_aion_kwarg_overrides_env_host(monkeypatch):
    monkeypatch.setenv("TCIQ_HOST", "should-not-be-used")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(
        aion_url="https://aion.example.com", aion_username="u",
        aion_password="p", load_env=False)
    assert cfg.base_url == "http://from-aion:9200"
    assert len(calls) == 1


def test_explicit_aion_kwarg_overrides_env_install_dir(monkeypatch):
    monkeypatch.setenv("TCIQ_INSTALL_DIR", "/should/not/be/read")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(
        aion_url="https://aion.example.com", aion_username="u",
        aion_password="p", load_env=False)
    assert cfg.base_url == "http://from-aion:9200"
    assert len(calls) == 1


def test_explicit_base_url_kwarg_still_beats_explicit_aion_kwarg(monkeypatch):
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(
        base_url="http://explicit:9200",
        aion_url="https://aion.example.com", aion_username="u",
        aion_password="p", load_env=False)
    assert cfg.base_url == "http://explicit:9200"
    assert len(calls) == 0  # never even attempted -- an explicit kwarg won


def test_env_only_aion_still_loses_to_env_base_url(monkeypatch):
    """Unchanged behavior: AION resolved purely from TCIQ_AION_*
    environment variables (no aion_url= kwarg) is NOT explicit intent for
    this call, and stays the lowest-priority option."""
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env:1111")
    monkeypatch.setenv("TCIQ_AION_URL", "https://aion.example.com")
    monkeypatch.setenv("TCIQ_AION_USERNAME", "u")
    monkeypatch.setenv("TCIQ_AION_PASSWORD", "p")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-env:1111"
    assert len(calls) == 0  # never attempted -- would have been discarded anyway


def test_env_only_aion_used_when_nothing_else_resolves(monkeypatch):
    """Baseline case, unchanged: pure env-sourced AION is still used when
    it's the only thing that resolves anything."""
    monkeypatch.setenv("TCIQ_AION_URL", "https://aion.example.com")
    monkeypatch.setenv("TCIQ_AION_USERNAME", "u")
    monkeypatch.setenv("TCIQ_AION_PASSWORD", "p")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-aion:9200"
    assert len(calls) == 1


def test_loads_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "TCIQ_BASE_URL=http://from-dotenv:9200\n"
        "TCIQ_DATABASE_ID=db-from-dotenv\n"
    )
    cfg = resolve_config(load_env=True, env_file=str(tmp_path / ".env"))
    assert cfg.base_url == "http://from-dotenv:9200"
    assert cfg.database_id == "db-from-dotenv"


def _write_orion_yaml(tmp_path):
    path = tmp_path / "orion-res" / "etc" / "orion-res.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent("""\
        service:
          addr: 127.0.0.1:9200
        """))
