import copy
import warnings
from collections import defaultdict
from dataclasses import (
    MISSING,
    Field,
    InitVar,
    asdict,
    dataclass,
    field,
    fields,
    is_dataclass,
)
from inspect import Parameter
from types import NoneType, UnionType
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    Mapping,
    MutableMapping,
    Self,
    Union,
    get_args,
    get_origin,
)

from docstring_parser import parse

from .config import Config, is_config


@dataclass(slots=True)
class ConfigParam:
    name: str
    type: type
    desc: str = ""
    default: Any = Parameter.empty
    config: "ConfigParams | None" = None
    inner_configs: tuple["ConfigParams", ...] = field(default_factory=tuple, init=False)
    _value: Any = field(default=Parameter.empty, init=False)

    def __post_init__(self) -> None:
        # Init list of ConfigParams objs
        configs: list[ConfigParams] = []

        if self.config is not None:
            # Propagate these
            config_kwargs = {
                "propagate_kwargs": self.config.propagate_kwargs,
                "doc_desc_newline": self.config.doc_desc_newline,
                "doc_type_max_depth": self.config.doc_type_max_depth,
            }
        else:
            # No config, not known
            config_kwargs = {}

        for config in get_args(self.type) if self.is_union else [self.type]:
            if is_config(config):
                # Append inner ConfigParams object with same attributes
                configs.append(ConfigParams(config, self, **config_kwargs))

        # Assign ConfigParams tuple
        self.inner_configs = tuple(configs)

        if is_config(self.default):
            # If config was provided as default, we set it as compiled
            config = self.get_config(self.default.__class__.__name__)
            config._compiled_config = self.default

        # Current value is default
        self._value = self.default

    @property
    def is_union(self) -> bool:
        return get_origin(self.type) in {Union, UnionType}

    @property
    def is_config(self) -> bool:
        types = get_args(self.type) if self.is_union else [self.type]
        return any(map(is_config, types))

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, value: Any) -> None:

        # If the parameter is an inner config and the value is a mapping
        # And if the union of types does not allow such type of mapping
        # Or it is allowed but the mapping contains default config names
        if (self.is_config and isinstance(value, Mapping)) and (
            len(default_configs := self.deep_find(value.keys())) > 0
            or not (self.is_union and type(value) in get_args(self.type))
        ):
            if len(value) == 0:
                return

            # Filter value dict from default inner configs
            filtered_params = {k: v for k, v in value.items()}

            for param, config in default_configs:
                # Remove config name from value dict
                filtered_params.pop(config.class_name)
                inner_config = value[config.class_name]

                if is_dataclass(inner_config):
                    # Assign dataclass object
                    param.value = inner_config
                elif isinstance(inner_config, Mapping):
                    # Assign mapping (for the given config)
                    param._update_inner_configs(inner_config, config.class_name)
                else:
                    raise TypeError(
                        f"Parameter '{config.class_name}' defines a default config, "
                        f"therefore, the value must be a dataclass or a dict "
                        f"(mapping). Got type '{type(inner_config)}'."
                    )

            # Update inner configs with filtered values
            self._update_inner_configs(filtered_params)
            return

        # Uncompile upper configs and update value
        self.config.compiled_config = None
        self._value = value

        if self.default is Parameter.empty or type(value) == type(self.default):
            # We need to update description
            self.update_desc_default(value)

        if is_config(value) and (config := self.get_config(value.__class__.__name__)):
            # Also set the compiled config
            config._compiled_config = value

    def _update_inner_configs(
        self,
        params: Mapping[str, Any],
        config_name: str | Iterable[str] | None = None,
    ) -> None:
        if len(params) == 0:
            # Empty
            return
        elif config_name is None:
            # Use all inner configs
            configs = self.inner_configs
        elif isinstance(config_name, str):
            # Use only the specified config
            configs = [c := self.get_config(config_name)] if c else []
        else:
            # Use all specified configs
            configs = [(c := self.get_config(name)) for name in config_name if c]

        if len(configs) == 0:
            raise TypeError(
                f"Could not find any config with the given name(s) '{config_name}'."
            )

        # A mapping will turn value into empty to indicate that
        # not all the possible values may have been provided
        self.config.compiled_config = None
        self._value = Parameter.empty

        if len(configs) == 1:
            # NOTE: here only config params should be present, no
            # default config names. However, default config names may
            # have been mistyped, thus perhaps we may want a more
            # appropriate error message

            # Uncompile & Update the only config
            configs[0].compiled_config = None
            configs[0].update(params)
            return

        # New configs and errors dict
        new_configs, errors = [], {}

        for config in configs:
            # Copy to revert if anything fails
            old_config = copy.deepcopy(config)

            try:
                # Try to update with new params
                config.compiled_config = None
                config.update(params)
                is_valid = True
            except TypeError as e:
                # Rollback if failed
                config = old_config
                is_valid = False
                errors[config.class_name] = e

            # Append to new configs
            config._is_valid = is_valid
            new_configs.append(config)

        if not any(c._is_valid for c in new_configs):
            # raise TypeError(
            #     f"Could not create a valid config for '{self.name}' and its following "
            #     f"target types: {tuple(c.class_name for c in configs)}. Please ensure "
            #     f"that all the required values for at least one of these configs are "
            #     f"provided."
            # )
            raise TypeError(
                f"Could not create a valid config for '{self.name}'. Please ensure "
                f"that all the required values for at least one of the config types "
                f"(allowed by this parameter) are provided. The following errors have "
                f"occurred: {'\n\t* '.join(f'{k}: {v}' for k, v in errors.items())}"
            )

        # Update inner configs with new ones
        self.inner_configs = tuple(new_configs)

    @classmethod
    def from_field(cls, field: Field, **kwargs) -> Self:
        if "desc" in field.metadata:
            # Metadata contains default parameter description
            kwargs.setdefault("desc", field.metadata["desc"])

        if field.default != MISSING:
            # Directly set default
            default = field.default
        elif field.default_factory != MISSING:
            # Set default by calling factory
            default = field.default_factory()
        else:
            # Required param indicator
            default = Parameter.empty

        return cls.from_value(
            name=kwargs.get("name", field.name),
            type=kwargs.get("type", field.type),
            value=kwargs.get("default", default),
            **kwargs,
        )

    @classmethod
    def from_value(cls, name: str, value: Any, **kwargs) -> Self:
        return cls(
            name=name,
            default=value,
            type=(t := kwargs.get("type", type(value))),
            desc=kwargs.get("desc", f"({t}) Defaults to {value}."),
            config=kwargs.get("config"),
        )

    def as_parameter(self) -> Parameter:
        return Parameter(
            self.name,
            Parameter.KEYWORD_ONLY,
            default=self.value,
            annotation=self.type,
        )

    def get_config(self, class_name: str) -> "ConfigParams | None":
        """Get inner config with the given class name.

        If this parameter is a config, a :class:`ConfigParams` object
        is returned for a config type that matches the given class name.
        If no such config is found, or if the parameter is not a config,
        :data:`None` is returned.

        Args:
            class_name (str): The class name of the config to find.

        Returns:
            ConfigParams | None: A :class:`ConfigParams` object if a
            matching config is found, or :data:`None` otherwise.
        """
        for config in self.inner_configs:
            if config.class_name == class_name:
                return config

        return None

    def deep_find(
        self,
        class_name: str | Collection[str],
        max_entries: int = -1,
    ) -> list[tuple[Self, "ConfigParams"]]:
        """Deep find inner configs with the given class name(s).

        Loops through all inner configs recursively to find the ones
        with the given class name(s). The search is depth-first -
        each branch of inner configs is searched in the order they
        appear in the type annotation. However, the outer configs of
        each branch are always found first.

        Args:
            class_name (str | typing.Collection[str]): The class name(s)
                to find.
            max_entries (int, optional): The maximum number of entries
                to find. It is very convenient to set this to ``1`` if
                you are only interested if any config with the given
                name exists. Defaults to ``-1`` (find all).

        Returns:
            list[tuple[ConfigParam, ConfigParams]]: A list of tuples
            containing the :class:`ConfigParam` object and its inner
            :class:`ConfigParams` mapping. Note that if ``max_entries``
            is set, the list may still contain fewer entries than the
            maximum.
        """
        if isinstance(class_name, str):
            # To tuple for convenience
            class_name = (class_name,)

        if len(class_name) == 0 or max_entries == 0:
            # No name
            return []

        # Init list
        configs = []

        for config in self.inner_configs:
            if config.class_name in class_name:
                # Found a matching config
                configs.append((self, config))

            if max_entries >= 0 and len(configs) >= max_entries:
                # Max
                break

        # NOTE: second loop is very important. It ensures outer configs
        # are at the beginning of the list. This will allow inner config
        # parameters to overwrite outer config parameters if needed.

        for config in self.inner_configs:
            for param in config.values():
                if param.is_config:
                    # Recursively search for inner configs
                    num_remain = max_entries - len(configs)
                    configs.extend(param.deep_find(class_name, num_remain))

        return configs

    def update_desc_default(self, default: Any = Parameter.empty) -> None:
        """Updates the description with the new default value.

        Takes a default value and updates the description of the
        parameter by removing the old default value and adding the
        new one, i.e., the description suffix "Defaults to {default}."
        is reset. If no default value is provided, i.e.,
        :attr:`inspect.Parameter.empty`, the suffix is dropped.

        Note:
            The description is updated in-place.

        Args:
            default (typing.Any, optional): The new default value to
                add to the description. If not provided, the suffix
                is dropped. Defaults to :attr:`inspect.Parameter.empty`.
        """
        # Remove old default value from description and add .
        desc = self.desc.rsplit("Defaults to ", 1)[0].strip()
        desc = desc if desc.endswith(".") else desc + "."

        if default is not Parameter.empty:
            # Add new default value to description
            desc += f" Defaults to {default}."

        # Update the desc
        self.desc = desc


class ConfigParams[T: Config](MutableMapping[str, ConfigParam]):
    def __init__(
        self,
        config_class: type[T],
        parent_param: ConfigParam | None = None,
        propagate_kwargs: bool = False,
        doc_desc_newline: str = "\n" + " " * 8,
        doc_type_max_depth: int = 1,
        doc_get_desc_fn: Callable[[Iterable[Field[Any]], str], str] | None = None,
    ):
        # First assign given simple attributes
        self._propagate_kwargs = propagate_kwargs
        self._doc_desc_newline = doc_desc_newline
        self._doc_type_max_depth = doc_type_max_depth
        self._doc_get_desc_fn = doc_get_desc_fn or self.get_desc_repr

        # Most important ones
        self.config_class = config_class
        self.param = parent_param

        # Store the config name and the param name
        self.class_name = config_class.__name__
        self.param_name = parent_param.name if parent_param is not None else None
        self.name = self.param_name or self.class_name

        # Initialize inner- and outer-related params
        self._compiled_config: Config | None = None
        self.inner_params: dict[str, ConfigParam] = {}
        self._is_valid = True

        # Extract fields from the config class
        fields = self.extract_fields(config_class)
        type_repr = self.get_type_repr(fields)
        desc_repr = self.get_desc_repr(fields, config_class.__doc__)

        for field in fields:
            # Create desc and create a ConfigParam object for each field
            desc = type_repr.get(field.name, "") + ": " + desc_repr.get(field.name, "")
            self.inner_params[field.name] = ConfigParam.from_field(
                field=field,
                desc=desc,
                config=self,
                propagate_kwargs=self.propagate_kwargs,
                doc_desc_newline=self.doc_desc_newline,
                doc_type_max_depth=self.doc_type_max_depth,
            )

    ####################################################################
    #                        Getters and Setters                       #
    ####################################################################

    @property
    def compiled_config(self) -> T | None:
        """The compiled config dataclass.

        Returns:
            Config | None: The compiled config dataclass or :data:`None`
            if the config has not been compiled yet.
        """
        return self._compiled_config

    @compiled_config.setter
    def compiled_config(self, value: T | None) -> None:
        """Set the compiled config dataclass.

        Caches the compiled config dataclass for later reuse, e.g.,
        when calling :meth:`as_dataclass`. If this is the inner config,
        the outer configs are "uncompiled" because they will need to be
        recompiled with the new values.

        Note:
            Uncompiling outer configs causes their values to spread
            across sibling configs updating them. Sibling values are
            guaranteed to be newer than outer complied config values
            because any change to sibling values would have caused the
            outer configs to be uncompiled.

        Args:
            value (Config | None): The compiled config dataclass.
        """
        if self.param is not None:
            # Compiling an inner config uncompiles all outer configs but
            # we need their values to update sibling config defaults
            config = asdict(c) if (c := self.param.config.compiled_config) else {}
            self.param.config.compiled_config = None
            self.param.config.update(config)

        # Set exact Config dataclass or uncompile current config if None
        config = asdict(c) if (c := self.compiled_config) and value is None else {}
        self._compiled_config = value
        self.update(config)

    @property
    def required_non_config(self) -> list[str]:
        """List of required non-inner-config parameters.

        Returns a list of parameter names that do not have values set
        but are required to initialize this config as a dataclass.
        Inner configs are purposely ignore because they could be
        compiled from their :attr:`ConfigParam` objects.

        Returns:
            list[str]: A list of missing parameters (except inner
            configs) that are required to initialize this config as a
            dataclass.
        """
        return [
            k for k, v in self.items() if v.value is Parameter.empty and not v.is_config
        ]

    @property
    def propagate_kwargs(self) -> bool:
        return self._propagate_kwargs

    @propagate_kwargs.setter
    def propagate_kwargs(self, value: bool) -> None:
        # Set the attr recursively
        self._propagate_kwargs = value
        self._setattr_recursively("propagate_kwargs", value)

    @property
    def doc_desc_newline(self) -> str:
        return self._doc_desc_newline

    @doc_desc_newline.setter
    def doc_desc_newline(self, value: str) -> None:
        # Set the attr recursively
        self._doc_desc_newline = value
        self._setattr_recursively("doc_desc_newline", value)
        # NOTE: desc not regenerated

    @property
    def doc_type_max_depth(self) -> int:
        return self._doc_type_max_depth

    @doc_type_max_depth.setter
    def doc_type_max_depth(self, value: int) -> None:
        # Set the attr recursively
        self._doc_type_max_depth = value
        self._setattr_recursively("doc_type_max_depth", value)
        # NOTE: desc not regenerated

    @property
    def doc_get_desc_fn(self) -> Callable[[str], str]:
        return self._doc_get_desc_fn

    @doc_get_desc_fn.setter
    def doc_get_desc_fn(self, value: Callable[[str], str]) -> None:
        # Set the attr recursively
        self._doc_get_desc_fn = value
        self._setattr_recursively("doc_get_desc_fn", value)
        # NOTE: desc not regenerated

    ####################################################################
    #                    Main Construction Methods                     #
    ####################################################################

    @staticmethod
    def extract_fields(config_base: type[Config]) -> tuple[Field[Any], ...]:
        # Filter out non-init fields because the user can't set them
        filtered_fields = [field for field in fields(config_base) if field.init]

        # Here we loop through config and all its base classes' params
        # to find the InitVar params. These are not included in fields
        for base in config_base.__mro__:
            if not is_dataclass(base):
                continue

            for key, val in base.__annotations__.items():
                if not isinstance(val, InitVar):
                    continue

                # Dummy field
                f = field()
                f.name = key
                f.type = val.type

                # Add dummy field to the list
                filtered_fields.append(f)

        return tuple(filtered_fields)

    def get_type_repr(self, fields: Iterable[Field[Any]]) -> dict[str, str]:
        def recurse(type, max_depth=1):
            if max_depth == 0:
                return ""

            if get_origin(type) in {Union, UnionType}:
                # Apply the same function to each type in the Union
                subs = (recurse(a, max_depth=max_depth) for a in get_args(type))
                desc = " | ".join(subs)
            elif hasattr(type, "__args__") and max_depth > 1:
                # Recurse generic types if max depth is not reached
                subs = (recurse(a, max_depth=max_depth - 1) for a in type.__args__)
                name = type.__name__ if hasattr(type, "__name__") else str(type)
                desc = f"{name}[{', '.join(subs)}]"
            elif type is NoneType:
                # Just None
                desc = "None"
            else:
                # __name__ excludes module path, gives pure class name
                desc = type.__name__ if hasattr(type, "__name__") else str(type)

            return desc

        return {f.name: f"({recurse(f.type, self.doc_type_max_depth)})" for f in fields}

    def get_desc_repr(
        self,
        fields: Iterable[Field[Any]],
        docstring: str = "",
    ) -> dict[str, str]:
        def add_default(desc, default=MISSING, default_factory=MISSING):
            if (default is MISSING and default_factory is MISSING) or (
                "defaults to" in desc.lower() or "default is" in desc.lower()
            ):
                # Default value is already given or not required
                return desc
            elif default is MISSING:
                # Default factory is given, thus we must call it
                desc = desc if desc.endswith(".") else desc + "."
                return f"{desc} Defaults to {default_factory()}."
            else:
                # Default value is given, can be used directly
                desc = desc if desc.endswith(".") else desc + "."
                return f"{desc} Defaults to {default}."

        try:
            # Try to parse the docstring
            params = parse(docstring).params
        except:
            params = []

        # Get the descriptions from the docstring for each parameter
        docstring_descs = {p.arg_name: p.description or "" for p in params}
        parameter_descs = {}

        for field in fields:
            if isinstance(field.metadata, Mapping) and "desc" in field.metadata:
                # Use provided meta description
                desc = field.metadata["desc"]
            else:
                # Use extracted docstring description
                desc = docstring_descs.get(field.name, "")

            # Add indentations to the description if needed
            desc = desc.replace("\n", self.doc_desc_newline)

            # Add default value if not already present
            desc = add_default(desc, field.default, field.default_factory)
            parameter_descs[field.name] = desc

        return parameter_descs

    def as_dataclass(self) -> T:
        # Will fail if this dataclass or any inner configs miss values

        if self.compiled_config is not None:
            # Config already compiled
            return self.compiled_config

        if (num := len(missing := self.required_non_config)) > 0:
            # Mimic pluralization modifier as in vanilla TypeError
            mod = ("", "es", "a ", "", "it") if num == 1 else ("s", "", "", "s", "them")

            raise TypeError(
                f"Config {self.name} missing {num} required parameter{mod[0]} that "
                f"do{mod[1]} not have {mod[2]}default value{mod[3]}: "
                f"{", ".join([f"'{m}'" for m in missing])}. Please assign {mod[4]} "
                f"before initializing the dataclass."
            )

        # Config's params
        config_kwargs = {}

        for name, param in self.items():
            if param.value is not Parameter.empty:
                # Simply assign the param's value
                config_kwargs[name] = param.value
            elif len(param.inner_configs) == 1:
                # Only one inner config, i.e., no Union of configs
                config_kwargs[name] = param.inner_configs[0].as_dataclass()
            else:
                # Separate valid and invalid (param mismatch) configs
                valid = [c for c in param.inner_configs if c._is_valid]
                invalid = [c for c in param.inner_configs if not c._is_valid]

                if config := param.get_config(param.default.__class__.__name__):
                    if config._is_valid:
                        # Put default/preferred valid config in front
                        valid = [config] + [c for c in valid if c is not config]
                    else:
                        # Put default/preferred invalid config in front
                        invalid = [config] + [c for c in invalid if c is not config]

                # Combine valid and invalid configs
                configs, errors = valid + invalid, {}

                for config in configs:
                    try:
                        # Try converting to a dataclass obj
                        valid_config = config.as_dataclass()
                        is_valid = config._is_valid
                        break
                    except TypeError as e:
                        # Values are missing
                        valid_config = None
                        errors[config.class_name] = e

                        # if config._is_valid:
                        #     # Globalize
                        #     error = e

                if valid_config is None:
                    # raise TypeError(
                    #     f"Could not create a valid config for '{name}' which has the "
                    #     f"following possible types: "
                    #     f"{tuple(c.class_name for c in param.inner_configs)}. Please "
                    #     f"ensure that all the required values for at least one of "
                    #     f"these configs are provided and that there are no extra "
                    #     f"arguments not defined in such config of choice."
                    # )
                    raise TypeError(
                        f"Could not create a valid config for '{name}'. Please ensure "
                        f"that all the required values for at least one of the config "
                        f"types (allowed by this parameter) are provided. The "
                        f"following errors have occurred: "
                        f"{'\n\t* '.join(f'{k}: {v}' for k, v in errors.items())}"
                    )
                elif not is_valid and len(valid) == 0:
                    # Impossible case, an error would have been raised
                    warnings.warn("How did we get here?", UserWarning)
                elif not is_valid and len(valid) == 1:
                    warnings.warn(
                        f"Based on the arguments provided, the preferred config type "
                        f"for parameter '{name}' is {valid[0].class_name}. However, "
                        f"the provided arguments are not complete and the following "
                        f"error has occurred: {errors[valid[0].class_name]}. "
                        f"Falling back to the default version of the config "
                        f"'{config.class_name}'."
                    )
                elif not is_valid:
                    warnings.warn(
                        f"Based on the arguments provided, the preferred config type "
                        f"for parameter '{name}' is one of "
                        f"{", ".join(f"'{c.class_name}'" for c in valid)}. However, "
                        f"all of these configs are missing some additional required "
                        f"values. The following errors have occurred: "
                        + "\n\t* ".join(
                            f"{k}: {v}" for k, v in list(errors.items())[: len(valid)]
                        )
                        + "Falling back to the default version of the config "
                        f"'{config.class_name}'."
                    )

                # Set the compiled config dataclass
                config_kwargs[name] = valid_config

        # Compile this config and return the dataclass object
        config_dataclass = self.config_class(**config_kwargs)
        self._compiled_config = config_dataclass

        return config_dataclass

    def as_parameters(self) -> list[Parameter]:
        return [p.as_parameter() for p in self.values()]

    def regenerate_descriptions(
        self,
        fields: tuple[Field[Any], ...],
        recurse: bool = False,
    ):
        if len(fields) == 0:
            # Extract fields if not provided
            fields = self.extract_fields(self.config_class)

        # Get type and description representations
        type_repr = self.get_type_repr(fields)
        desc_repr = self.get_desc_repr(fields, self.config_class.__doc__)

        for field in fields:
            # Create desc and use it to update the ConfigParam object
            desc = type_repr.get(field.name, "") + ": " + desc_repr.get(field.name, "")
            self.inner_params[field.name].desc = desc

            if recurse and self.inner_params[field.name].is_config:
                for config in self.inner_params[field.name].inner_configs:
                    # Recursively update descriptions if needed
                    config.regenerate_descriptions(recurse=True)

    # def param_descriptions(self) -> str:
    #     if len(self) == 0:
    #         return ""

    #     # Separator and indentation strs
    #     sep = self.doc_desc_newline + "* "
    #     ind = sep.replace("\n", "", 1)

    #     return ind + sep.join(f"{name} {param.desc}" for name, param in self.items())

    def _setattr_recursively(self, attr: str, value: Any) -> None:
        for param in self.values():
            for config in param.inner_configs:
                # Recursively update attribute
                setattr(config, attr, value)

    ####################################################################
    #                     MutableMapping Methods                       #
    ####################################################################

    def update(
        self,
        other: Mapping[str, Any],
        ignore_unknown: bool = False,
    ) -> set[str]:
        # Separate regular params from default config params
        regular_params, configs_params = {}, defaultdict(dict)
        used_keys = set()

        for key, value in other.items():
            if key in self:
                # Name matches some param
                regular_params[key] = value
                used_keys.add(key)
            else:
                for name, param in self.items():
                    if len(param.deep_find(key, max_entries=1)) > 0:
                        # Key specifies existing inner config class
                        configs_params[name][key] = value
                        used_keys.add(key)

                if not configs_params and not ignore_unknown:
                    # This will raise appropriate error later
                    regular_params[key] = value
                    used_keys.add(key)

        # Update defaults, then regular
        super().update(configs_params)
        super().update(regular_params)

        return used_keys

    def __setitem__(self, key: str, value: Any) -> None:
        if isinstance(value, ConfigParam):
            if value.config is not self:
                # Param belongs here
                value.config = self

                for config in value.inner_configs:
                    # Recursively update attributes and regen descs
                    config.propagate_kwargs = self.propagate_kwargs
                    config.doc_desc_newline = self.doc_desc_newline
                    config.doc_type_max_depth = self.doc_type_max_depth
                    config.regenerate_descriptions(recurse=True)

            # ConfigParam assigned directly
            self.inner_params[key] = value
        elif key in self.inner_params:
            # Non-ConfigParam updates value attr
            self.inner_params[key].value = value
        elif key in (
            inner_config_set := {self.class_name}
            | set(c.class_name for p in self.values() for c in p.inner_configs)
        ):
            # NOTE: this IF clause kind of repeats what `update()` has
            # already done. It is never executed if `update()` was used
            # unless some unknown parameters are detected. This is
            # expensive but necessary in case the default config is
            # directly assigned instead of using the `update()` method.

            if key == self.class_name:
                # Update this conf
                self.update(value)

            for name, param in self.items():
                # Init default dict
                inner_defaults = {}

                if config := param.get_config(key):
                    # Set default for inner config
                    inner_defaults[key] = value

                # Update inner config defaults
                self[name] = inner_defaults
        else:
            raise TypeError(
                f"Config {self.name} does not have a parameter named '{key}'.\n    * "
                "It is unusual to assign new parameters to an initialized config. If "
                "this is intended, please assign a ConfigParam object instead, e.g., "
                "by calling `ConfigParam.from_value()`.\n    * If your parameter "
                "defines a default config, its name must match the class name of "
                "either this config or one of the inner configs: "
                f"{', '.join(f'{c}' for c in inner_config_set)}."
            )

    def __getitem__(self, key: str) -> ConfigParam:
        return self.inner_params[key]

    def __delitem__(self, key: str) -> None:
        del self.inner_params[key]

    def __iter__(self) -> Iterable[str]:
        return iter(self.inner_params)

    def __len__(self) -> int:
        return len(self.inner_params)
