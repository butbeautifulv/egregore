from __future__ import annotations

import pytest

from bootstrap.catalog_loader import load_active_profile_pack, load_profile_pack, load_profile_pack_for


@pytest.mark.unit
def test_load_profile_pack_for_default_matches_unfiltered_load_profile_pack():
    base_profile, base_entries = load_profile_pack()
    scoped_profile, scoped_entries = load_profile_pack_for("cybersec-soc")
    assert scoped_profile.id == base_profile.id == "cybersec-soc"
    assert {e.name for e in scoped_entries} == {e.name for e in base_entries}


@pytest.mark.unit
def test_load_profile_pack_for_general_assistant_filters_to_its_own_personas():
    profile, entries = load_profile_pack_for("general-assistant")
    assert profile.id == "general-assistant"
    assert {e.name for e in entries} == {"consultant"}


@pytest.mark.unit
def test_load_profile_pack_for_gaia_benchmark_filters_to_its_own_personas():
    profile, entries = load_profile_pack_for("gaia-benchmark")
    assert profile.id == "gaia-benchmark"
    assert {e.name for e in entries} == {"gaia_solver"}


@pytest.mark.unit
def test_load_profile_pack_for_unknown_pack_raises():
    with pytest.raises(KeyError, match="Unknown product pack"):
        load_profile_pack_for("does-not-exist")


@pytest.mark.unit
def test_load_active_profile_pack_reads_profile_pack_id_env_var(monkeypatch):
    monkeypatch.delenv("PROFILE_PACK_ID", raising=False)
    default_profile, _ = load_active_profile_pack()
    assert default_profile.id == "cybersec-soc"

    monkeypatch.setenv("PROFILE_PACK_ID", "general-assistant")
    ga_profile, ga_entries = load_active_profile_pack()
    assert ga_profile.id == "general-assistant"
    assert {e.name for e in ga_entries} == {"consultant"}
