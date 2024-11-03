import importlib
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Add submodules from src/dataconfigs
spec = spec_from_file_location(
    "dataconfigs",
    os.path.abspath(__file__),
    submodule_search_locations=[
        os.path.join(PROJECT_DIR, "src", "dataconfigs"),
        os.path.join(PROJECT_DIR, "test", "dataconfigs"),
    ],
)

# Reload the module with src submodules
dataconfigs = module_from_spec(spec)
sys.modules["dataconfigs"] = dataconfigs
importlib.reload(dataconfigs)
