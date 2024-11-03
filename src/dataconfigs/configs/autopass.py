import copy
import os
import warnings
from inspect import Parameter, signature
from typing import Any, Callable, Literal, Mapping

from ..utils import unpack_type
from .config import Config, is_config, is_dataclass


class autopass:
    def __init__(
        self,
        autopass_kind: Literal["config", "configurable", "both"] = "both",
        config_type_map: Mapping[str, type[Config]] | Literal["auto"] = "auto",
        is_config_fn: Callable[[Any], bool] = is_config,
        # ^ If your function accepts configs and other kinds of dataclasses, this will differentiate them
        ignore_warnings: bool = False,
        **kwargs: Config,
    ) -> None:
        self.autopass_kind = autopass_kind
        self.config_type_map = config_type_map if config_type_map != "auto" else {}
        self.is_config_fn = is_config_fn
        self.ignore_warnings = ignore_warnings
        self.configs = kwargs

        if invalid := [(k, v) for k, v in kwargs.items() if not self.is_valid(v)]:
            raise ValueError(
                f"Found invalid config type(s) in @autopass decorator: "
                f"{", ".join([f"{k} ({v.__class__.__name__})" for k, v in invalid])}. "
                f"The only allowed types are dataclasses, mappings (e.g., dicts), and "
                f"path-like objects (e.g., strings)."
            )

    @staticmethod
    def is_valid(cfg: Any) -> bool:
        return isinstance(cfg, (Mapping, os.PathLike, str, bytes)) or is_dataclass(cfg)

    def open_config(self, config):
        os.fspath(config)

    def make_config(self, config: Any, param: Parameter, fn_name: str = "?") -> Any:
        types = list(filter(self.is_config_fn, ts := unpack_type(param.annotation)))

        if len(types) == 0:
            if (
                Config not in ts
                and param.annotation is not Parameter.empty
                and not is_dataclass(config)
                and not self.ignore_warnings
            ):
                warnings.warn(
                    f"The type annotation of parameter '{param.name}' in function "
                    f"'{fn_name}' signature does not contain any valid config types. "
                    f"Instead, the following type(s) was/were found: "
                    f"{", ".join([t.__name__ for t in ts])}. For this reason, a dummy "
                    f"config dataclass will be auto-passed for this parameter. Please "
                    f"double-check that `is_config_fn` correctly identifies "
                    f"config types or at least annotate this parameter with "
                    f"`dataclasses.Config`. If this is intended, to suppress this "
                    f"warning, set `ignore_warnings=True`.",
                    UserWarning,
                )

            # TODO: Convert config to a dataclass if it not already is
            return None

        errors = []

        for config_type in types:
            try:
                # TODO: return valid config type
                return None
            except Exception as e:
                errors.append((config_type.__name__, e))

        # TODO: try default if it has

        raise ValueError(
            f"Could not create a valid config instance for the parameter "
            f"'{param.name}' in function '{fn_name}'. All possible config types "
            f"resulted in errors: {"".join([f"\n\t *{n}: {e}" for n, e in errors])}"
        )

    def _parse_kwargs(self, func):
        # Copy for popping & inspect
        cfg = copy.copy(self.configs)
        sig = signature(func)

        autokwargs, configurables, inferred_config_type_map = {}, {}, {}

        for param_name, param in sig.parameters.items():
            if param.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                # Skip *args and **kwargs
                continue
            elif param_name in cfg and self.autopass_kind != "configurable":
                # Function param matches decorator's - parse the config
                config = self.make_config(cfg.pop(param_name), param, func.__name__)
                autokwargs[param_name] = config
            elif param_name in cfg and param_name not in self.config_type_map:
                # TODO: add config type mapping from type annotations
                inferred_config_type_map[param_name] = None
            elif param_name not in cfg and self.autopass_kind != "config":
                maybe_configurable = None

        if self.autopass_kind != "configurable":
            return autokwargs

        # This could be further expanded
        configs = copy.copy(autokwargs)

        for param_name, config_cls in self.config_type_map.items():
            # Further populate configs for the type that we know
            if param_name not in configs and param_name in cfg:
                # TODO: convert to config_cls and add to configs
                config = cfg.pop(param_name)

        for param_name in cfg.keys():
            if param_name in self.config_type_map:
                # TODO: convert to config_cls and add to configs
                # NOTE: even if config is a config-dataclass, it will
                # be converted to config_cls
                config = cfg.pop(param_name)
            elif self.is_config_fn(cfg[param_name]):
                # Directly add a proper config dataclass
                configs[param_name] = cfg.pop(param_name)
            elif param_name in inferred_config_type_map:
                # The reason we keep `inferred_config_type_map` and
                # `self.config_type_map` separate is that the former is
                # only used as a backup - otherwise inferred types could
                # overwrite `cfg[param_name]` type if it is a config
                # dataclass.

                # TODO: convert to config_cls and add to configs
                config = cfg.pop(param_name)

        # By now we have:
        # * configs - properly created config instances (dataclasses)
        # * cfg - remaining configs for which we do not know the config
        #   type (could be dict, str, non-config dataclass)

        for param_name, configurable_types in configurables.items():
            # First pass: try to instantiate those configurables for
            # which all the config instances are defined
            for configurable_type in configurable_types:
                pass

            # Second pass: try to instantiate any configurable and for
            # any config it is missing, try to create any one successful
            # config from cfg.
            for configurable_type in configurable_types:
                pass

    def __call__[T, **P](self, func: Callable[P, T]) -> Callable[P, T]:
        # Get config type annotations
        sig = signature(func)

        for param_name, config_kwargs in self.configs.items():
            param = sig.parameters.get(param_name)

            if param is None:
                raise ValueError(
                    f"Parameter '{param_name}' not found in {func.__name__} function signature"
                )

            print(
                param_name,
                config_kwargs,
                param.name,
                param.annotation,
                type(param.annotation),
                type(type(param.annotation)),
                unpack_type(param.annotation),
            )

        return func
