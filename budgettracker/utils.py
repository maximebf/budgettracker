import json
from importlib import import_module


CONFIG_FILENAME = 'config.json'


def load_adapter(package, name):
    return import_module('budgettracker.' + package + '.' + name)


def load_config(filename=CONFIG_FILENAME):
    with open(filename) as f:
        return json.load(f)