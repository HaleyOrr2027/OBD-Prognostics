# Tests for config.py

# Run with:
# $env:PYTHONPATH="src"
# pytest tests/unit/test_config.py -v

# I've never written Python tests before give me grace on this, alright?
# - Haley Orr :(

import pytest
import obd_anomaly.config as config


# Test that a normal YAML file loads correctly.
def test_valid_config(tmp_path, monkeypatch):
    file = tmp_path / "test.yaml"
    file.write_text("config_version: '1.0'\n")

    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    data = config.load_yaml("test.yaml")

    assert data["config_version"] == "1.0"


# Test that an error happens if the file does not exist.
def test_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        config.load_yaml("missing.yaml")


# Test that broken YAML gives an error.
def test_invalid_yaml(tmp_path, monkeypatch):
    file = tmp_path / "bad.yaml"
    file.write_text("setting: [broken")

    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        config.load_yaml("bad.yaml")


# Test that an error happens if a required setting is missing.
def test_missing_required_key():
    data = {}

    with pytest.raises(ValueError):
        config.check_required_keys(
            data,
            ["config_version"],
            "runtime.yaml"
        )