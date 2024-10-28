# Dataconfigs

## About

Dataconfigs provides a seamless integration between dataclasses as configs and any configurable classes that use these configs. The most powerful feature is that config attributes become part of configurable, i.e., no need for _explicit_ `.config` attribute (unless specified otherwise). This keep class definitions very siple yet decouples configurable parameters from class attributes. In terms of configs, it is a simplified hydra alternative, yet supporting more features.

## Features

Last 3 features are in development:
* Embedded config params in configurables (no need for separate `.config` attribute, unless specified otherwise)
* Easy type annotations (visible annotations, even though configs are never inherited from)
* Support for multiple, nested, hierarchical, and union configs, as well as non-atomic types
* Various file support (`json`, `yaml`, `pickle`)
* CLI support
* Decorator-based (inspired by Hydra)

## Quick Start

Install the library:

```bash
pip install dataconfigs
```

Check the [demo]().

### Simple Script Example

1. Simply define your config (must be a datacalss and contain the word Config in name!)
2. Extend the config with your configurable (it won't turn into a dataclass unless specified!)
3. Instantiate your configurable by optionally overwriting default config parameters

```python
from datacalsses import dataclass, is_dataclass
from paconfig import configurable, show_config_params

@datacalss
class MyConfig:
    """My config class
    Args:
        param1 (int): The first parameter.
        param2 (str): The second parameter.
    """
    param1: int = 0
    param2: str = "param2"

@configurable
class MyConfigurable(MyConfig):
    def __init__(self, attr1=1, attr2=2):
        print(self.param1, self.param2) # Already available!

assert not is_dataclass(MyConfigurable) # Only attributes were copied!
obj = MyConfigurable("attr1", param1=1) # Can overwrite config params! 
# 1, 'param2'
```

### Simple CLI Example (only ideas for now)

Assume you have `config.json` file as follows:
```json
{
    "param1": 111,
    "param2": "222"
}
```

One possibility is to directly make the configurable. Example `main.py`:
```python
@configurable("path/to/config.json", MyConfigurable, attr1="attr1")
def main(my_configurable):
    pass

if __name__ == "__main__":
    main()
```

We can still overwrite config params or the whole config file when calling:
```bash
paconfig main.py --param2 'custom' # 111, 'custom'
paconfig main.py --config path/to/config2.yaml
```

If we call `paconfig main.py -h`, descriptions will be extracted from docstrings:
```bash
Options:
--param1 : (int) The first parameter. Defaults to 111.
--param2 : (str) The second parameter. Defaults to '222'.
```

## Tutorials (TODO)

1. **Config classes**: there are many ways to define configs. The only restriction is that they must be dataclasses and contain an "Config" word in their class name (see basics):
    * **Basics**
    * **Unions & non-atomic types**
    * **Multiple, nested and hierarchical configs**
    * **Config files (json, yaml, pkl, etc.)**
2. **Configurables**: any class (configurable) that extends the config(-s) will only obtain its attributes and won't alter its class definition. The configurable class can inherit from any other parents in the usual manner.
    * **Config vs non-config attributes**
    * **Various ways to instantiate**
3. Compatibility with Third Party CLI
    * Pytorch Lightning
    * Tensorflow
    * Optuna
    * Ray

