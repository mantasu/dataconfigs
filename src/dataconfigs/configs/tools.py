from .configurable import _CONFIG_PARAMS, Configurable


def show_config_params(obj: Configurable | type[Configurable]) -> None:
    # Parameter description to show
    desc = ""

    for config_params in getattr(obj, _CONFIG_PARAMS):
        if len(config_params) == 0:
            continue

        # Separator and indentation strs
        sep = config_params.doc_desc_newline + "* "
        desc += sep + sep.join(f"{n} {p.desc}" for n, p in config_params.items())

    if isinstance(obj, type):
        # Remove first new line and print globals
        print(f"{obj.__name__} class config parameters (global defaults):")
        print(desc.replace("\n", "", 1))
    else:
        # Remove first new line and print locals
        print(f"{obj.__class__.__name__} instance config parameters (local defaults):")
        print(desc.replace("\n", "", 1))
