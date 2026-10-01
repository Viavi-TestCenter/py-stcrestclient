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
    # Bare (no TCIQ_ prefix) fallback names consolidated with
    # stcrestclient's own AionStcHttp -- see config.py.
    "AION_URL", "AION_USERNAME", "AION_PASSWORD",
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


# ---------------------------------------------------------------------------
# Consolidated AION env vars: TCIQ_AION_URL/TCIQ_AION_USERNAME/
# TCIQ_AION_PASSWORD stay primary, but a bare (no TCIQ_ prefix)
# AION_URL/AION_USERNAME/AION_PASSWORD -- stcrestclient's own AionStcHttp
# convention -- is now tried as a lower-priority fallback, so a machine
# already configured for stcrestclient's AION login needs no extra
# TCIQ_-prefixed config to also get tciqrestclient's AION discovery
# working. One-way only: stcrestclient/aionstchttp.py itself is
# untouched and does not fall back to TCIQ_AION_*.
# ---------------------------------------------------------------------------

def test_bare_aion_env_vars_used_when_tciq_prefixed_unset(monkeypatch):
    monkeypatch.setenv("AION_URL", "https://aion.example.com")
    monkeypatch.setenv("AION_USERNAME", "bare-user")
    monkeypatch.setenv("AION_PASSWORD", "bare-pass")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-aion:9200"
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert args[:3] == ("https://aion.example.com", "bare-user", "bare-pass")


def test_tciq_prefixed_aion_env_vars_win_over_bare(monkeypatch):
    """When both are set, TCIQ_AION_* -- this package's own, dedicated
    name -- wins over the bare fallback, field by field."""
    monkeypatch.setenv("TCIQ_AION_URL", "https://tciq-aion.example.com")
    monkeypatch.setenv("TCIQ_AION_USERNAME", "tciq-user")
    monkeypatch.setenv("TCIQ_AION_PASSWORD", "tciq-pass")
    monkeypatch.setenv("AION_URL", "https://bare-aion.example.com")
    monkeypatch.setenv("AION_USERNAME", "bare-user")
    monkeypatch.setenv("AION_PASSWORD", "bare-pass")
    calls = _stub_aion(monkeypatch)
    resolve_config(load_env=False)
    (args, kwargs) = calls[0]
    assert args[:3] == (
        "https://tciq-aion.example.com", "tciq-user", "tciq-pass")


def test_bare_aion_env_vars_fill_in_per_field_independently(monkeypatch):
    """Each of the three AION fields resolves independently -- confirmed
    existing behavior for kwarg-vs-env mixing, now also true across the
    two env-var conventions: TCIQ_AION_URL wins for the URL specifically,
    while AION_USERNAME/AION_PASSWORD (no TCIQ_AION_* set for those two)
    fill in the rest."""
    monkeypatch.setenv("TCIQ_AION_URL", "https://tciq-aion.example.com")
    monkeypatch.setenv("AION_USERNAME", "bare-user")
    monkeypatch.setenv("AION_PASSWORD", "bare-pass")
    calls = _stub_aion(monkeypatch)
    resolve_config(load_env=False)
    (args, kwargs) = calls[0]
    assert args[:3] == (
        "https://tciq-aion.example.com", "bare-user", "bare-pass")


def test_explicit_aion_kwargs_win_over_both_env_conventions(monkeypatch):
    monkeypatch.setenv("TCIQ_AION_URL", "https://tciq-aion.example.com")
    monkeypatch.setenv("TCIQ_AION_USERNAME", "tciq-user")
    monkeypatch.setenv("TCIQ_AION_PASSWORD", "tciq-pass")
    monkeypatch.setenv("AION_URL", "https://bare-aion.example.com")
    monkeypatch.setenv("AION_USERNAME", "bare-user")
    monkeypatch.setenv("AION_PASSWORD", "bare-pass")
    calls = _stub_aion(monkeypatch)
    resolve_config(
        aion_url="https://explicit.example.com", aion_username="explicit-user",
        aion_password="explicit-pass", load_env=False)
    (args, kwargs) = calls[0]
    assert args[:3] == (
        "https://explicit.example.com", "explicit-user", "explicit-pass")


def test_bare_aion_env_only_still_loses_to_env_base_url(monkeypatch):
    """Same "lowest priority" precedence as the TCIQ_AION_*-only case
    (see test_env_only_aion_still_loses_to_env_base_url above) applies
    identically when AION is resolved purely from the bare env vars --
    it's still not explicit intent for this call (no aion_url= kwarg)."""
    monkeypatch.setenv("TCIQ_BASE_URL", "http://from-env:1111")
    monkeypatch.setenv("AION_URL", "https://aion.example.com")
    monkeypatch.setenv("AION_USERNAME", "u")
    monkeypatch.setenv("AION_PASSWORD", "p")
    calls = _stub_aion(monkeypatch)
    cfg = resolve_config(load_env=False)
    assert cfg.base_url == "http://from-env:1111"
    assert len(calls) == 0  # never attempted -- would have been discarded anyway


def test_bare_aion_env_vars_do_not_leak_when_unset(monkeypatch):
    """Sanity check on the test isolation itself: with none of the six
    AION-related env vars set, AION discovery is never attempted at all
    (guards against the bare fallback accidentally picking up a real
    AION_URL/AION_USERNAME/AION_PASSWORD left set on the machine actually
    running these tests -- see conftest.py's iq_client fixture and this
    file's own ENV_VARS list, both of which now clear these three too)."""
    calls = _stub_aion(monkeypatch)
    with pytest.raises(IQConfigError):
        resolve_config(load_env=False)
    assert len(calls) == 0


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
