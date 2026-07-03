"""Subprocess bootstrap: load a scraper file, call scrape(), print JSON."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("scraper", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
json.dump(mod.scrape(), sys.stdout)
