# Loads the project configuration files so the rest of the program
# can use one shared set of settings.

import os
import yaml


# Finds the main project folder
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Finds the config folder inside the project
CONFIG_DIR = os.path.join(REPO_ROOT, "config")

# Loads one YAML config file, checks that it exists 
# and is valid, then returns its settings as a dictionary.
def load_yaml(filename):
    path = os.path.join(CONFIG_DIR, filename)

    # Check that the file exists
    if not os.path.exists(path):
        raise FileNotFoundError("Could not find config file: " + path)

    # Try to open and read the YAML file
    try:
        with open(path, "r") as file:
            data = yaml.safe_load(file)

    except yaml.YAMLError as error:
        raise ValueError("Invalid YAML in " + filename + ": " + str(error))

    # If the file is empty, make it an empty dictionary instead of 
    # leaving it as 'None' which can cause issues.
    if data is None:
        data = {}

    # Make sure the YAML file contains settings
    if not isinstance(data, dict):
        raise ValueError(filename + " must contain key/value settings.")

    return data

# Checks that a config file contains all settings that are required.
def check_required_keys(data, required_keys, filename):
    for key in required_keys:
        if key not in data:
            raise ValueError(filename + " is missing required key: " + key)

# Replaces default config values with vehicle-specific values 
# from another YAML file.
def apply_overrides(config, override_file):
    override = load_yaml(override_file)

    for section in override:

        if section not in config:
            raise ValueError(
                "Unknown config section in override file: " + section
            )

        if not isinstance(override[section], dict):
            raise ValueError(
                "Override section " + section +
                " must contain key/value settings."
            )

        config[section].update(override[section])

# Loads all project config files, checks required settings, applies
# optional vehicle overrides, and returns the complete configuration.
def load_config(vehicle_override=None):
    config = {}

    config["pids"] = load_yaml("pids.yaml")
    config["modes"] = load_yaml("modes.yaml")
    config["windows"] = load_yaml("windows.yaml")
    config["models"] = load_yaml("models.yaml")
    config["runtime"] = load_yaml("runtime.yaml")

    # Make sure runtime.yaml has a config version
    check_required_keys(
        config["runtime"],
        ["config_version"],
        "runtime.yaml"
    )

    # Allow a vehicle-specific file to replace default settings
    if vehicle_override is not None:
        apply_overrides(config, vehicle_override)

    # Save config version at the top level too
    config["config_version"] = config["runtime"]["config_version"]

    return config
