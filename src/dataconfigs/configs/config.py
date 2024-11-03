import re
from dataclasses import is_dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
else:
    from dataclasses import Field
    from typing import Any, ClassVar

    class DataclassInstance(Protocol):
        __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


class Config(DataclassInstance, Protocol):
    """An empty Config class.

    This class mainly serves the purpose of a type-annotation - there is
    no need for the actual Config classes to extend this "parent".
    """


def is_config(obj: object | type[object]) -> bool:
    # Matched name examples: "Config", "MyConfig1", "my_configMy"
    # Ignored name examples: "Random", "Configurable", "conf", "Configg"
    name = (obj if isinstance(obj, type) else type(obj)).__name__
    return is_dataclass(obj) and re.search(r"(?i)config(?:[^a-z]|$)", name)


# from typing import Callable
# import inspect

# class config:
#     def __init__(self, **kwargs: Config) -> None:
#         self.configs = kwargs

#     def __call__[T, **P](self, func: Callable[P, T]) -> Callable[P, T]:
#         # Get config type annotations

#         sig = inspect.signature(func)

#         for param_name, config_kwargs in self.configs.items():
#             param = sig.parameters.get(param_name)

#             if param is None:
#                 raise ValueError(f"Parameter '{param_name}' not found in {func.__name__} function signature")

#             # Get the param and its type from the signature
#             param_type = param.annotation
#             if not is_dataclass(param_type):
#                 raise ValueError(f"Parameter '{param_name}' is not a dataclass")

#         return wrapper
