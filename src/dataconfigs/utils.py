import copy
import inspect
from types import CodeType, GenericAlias, UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    ForwardRef,
    Mapping,
    TypeAliasType,
    TypeVar,
    Union,
    _GenericAlias,
    _UnionGenericAlias,
)

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer
else:
    from typing import TypeAlias

    from _collections_abc import Buffer

    ReadableBuffer: TypeAlias = Buffer


type UnpackableType = (
    UnionType
    | _GenericAlias
    | GenericAlias
    | TypeAliasType
    | TypeVar
    | str
    | ReadableBuffer
    | CodeType
    | ForwardRef
)


def slots_to_dict(obj: Any) -> dict[str, Any]:
    """Converts an object with slots to a dictionary.

    Some classes use slots instead of a dictionary to store their
    attributes. This function converts such objects to a dictionary
    because instantiated objects with slots do not have a ``__dict__``
    attribute.

    Args:
        obj (typing.Any): The object (either the class or instance) to
            convert.

    Returns:
        dict[str, typing.Any]: The dictionary representation of the
        object attributes.
    """
    return {k: getattr(obj, k) for k in obj.__slots__}


def is_dynamically_created(obj: Any, fn_name: str) -> bool:
    """Checks if a method is dynamically created.

    This function checks if a method is dynamically created, i.e., if
    it is not defined in the class but rather added at runtime by
    executing string-based code.

    Examples:
        >>> class TestClassStaticMethod:
        ...     def method(self): pass
        >>> is_dynamically_created(TestClassStaticMethod, "method")
        False
        >>> class TestClassDynamicMethod:
        ...     pass
        >>> exec("def method(self): pass", globals(), locals())
        >>> TestClassDynamicMethod.method = locals()["method"]
        >>> is_dynamically_created(TestClassDynamicMethod, "method")
        True

    Args:
        obj (typing.Any): The object (either the class or instance) to
            check.
        fn_name (str): The name of the method to check within the
            object.

    Returns:
        bool: :data:`True` if the method is dynamically created,
        :data:`False` otherwise.
    """
    if not hasattr(obj, fn_name):
        return False

    try:
        return not inspect.getsource(getattr(obj, fn_name))
    except OSError:
        return True


def is_type_unpackable(annotation: type[Any] | UnpackableType) -> bool:
    """Checks if a type annotation is unpackable.

    This function checks if a type annotation is unpackable, i.e., if
    it contains nested types, such as :class:`typing.Union`,
    :class:`typing.TypeVar`, :class:`typing.ForwardRef`, etc.

    Args:
        annotation (type[typing.Any] | UnpackableType): The type
            annotation to check.

    Returns:
        bool: :data:`True` if the annotation is unpackable,
        :data:`False` otherwise.
    """
    return isinstance(
        annotation,
        (
            UnionType,
            _GenericAlias,
            GenericAlias,
            TypeAliasType,
            TypeVar,
            str,
            ReadableBuffer,
            CodeType,
            ForwardRef,
        ),
    )


def unpack_typevar(annotation: TypeVar) -> type[Any] | UnpackableType | None:
    """Unpacks a TypeVar annotation into a basic type.

    Given a TypeVar annotation, this function will unpack the annotation
    into a basic type if possible. The priority order is as follows:

        1. Default value
        2. Constraints
        3. Bound

    Examples:
        >>> T = TypeVar("T")
        >>> TC = TypeVar("TC", str, bytes)
        >>> TB = TypeVar("TB", bound=os.PathLike | str | bytes)
        >>> TCD = TypeVar("TCD", str, bytes, default=str)
        >>> TBD = TypeVar("TBD", default=str, bound=str | bytes)
        >>> unpack_typevar(T)
        None
        >>> unpack_typevar(TC)
        Union[str, bytes]
        >>> unpack_typevar(TB)
        os.PathLike | str | bytes
        >>> unpack_typevar(TCD)
        str
        >>> unpack_typevar(TBD)
        str

    Args:
        annotation (TypeVar): The TypeVar annotation to unpack.

    Returns:
        type[typing.Any] | UnpackableType | None: The unpacked basic
        type or :data:`None` if the TypeVar has no default, constraints,
        or bound.
    """
    if hasattr(annotation, "has_default") and annotation.has_default():
        # Only for Python >=3.13
        return annotation.__default__
    elif len(annotation.__constraints__) == 1:
        # We can just return the constraint
        return annotation.__constraints__[0]
    elif len(annotation.__constraints__) > 1:
        # We need to construct a dummy union type for constraints
        return _UnionGenericAlias(Union, annotation.__constraints__)
    elif annotation.__bound__ is not None:
        # Some bound is specified
        return annotation.__bound__
    else:
        return None


def unpack_type(
    annotation: type[Any] | UnpackableType,
    globals: dict[str, Any] | None = None,
    locals: Mapping[str, object] | None = None,
    generic_kwargs: dict[str, type[Any] | UnpackableType] = {},
) -> tuple[type[Any], ...]:
    """Unpacks a type annotation into a tuple of types.

    Given a type annotation that contains nested types, such as union,
    generic, typevar, forwardref, etc., this function will unpack the
    annotation into a tuple of basic types.

    Examples:
        >>> unpack_type(Union[int, str])
        (int, str)
        >>> type MyBoundedGenericType[T: int | float] = T | list[T]
        >>> unpack_type(MyBoundedGenericType)
        (int, float, list)

    Args:
        annotation (type[typing.Any] | UnpackableType): The type
            annotation to unpack.
        globals (dict[str, Any] | None, optional): The globals
            dictionary to use for evaluation if the annotation is of
            type :class:`str`, :class:`types.CodeType`,
            :class:`collections.abc.Buffer`, or :class:`ForwardRef`.
            Simply pass `globals()` if that's the case. Defaults to
            :data:`None`.
        locals (Mapping[str, object] | None, optional): The locals
            dictionary to use for evaluation if the annotation is of
            type :class:`str`, :class:`types.CodeType`,
            :class:`collections.abc.Buffer`, or :class:`ForwardRef`.
            Simply pass `locals()` if that's the case. Defaults to
            :data:`None`.
        generic_kwargs (dict[str, type[typing.Any]  |  UnpackableType], optional):
            The generic arguments to use for unpacking the generic
            types. Key is the name of teh generic parameter and value
            is its argument. If not provided, generic arguments will be
            extracted as defaults if any constraints, bounds, or
            defaults were specified. Defaults to ``{}``.

    Returns:
        tuple[type[typing.Any], ...]: The unpacked types.
    """
    if not is_type_unpackable(annotation):
        return (annotation,)

    # Copy to avoid recursive in-place modifications
    generic_kwargs = copy.deepcopy(generic_kwargs)

    if isinstance(annotation, (str, ReadableBuffer, CodeType, ForwardRef)):
        # The annotation is a TypeAlias, e.g.,
        # MyFruits: TypeAlias = "list[Fruit]"
        annotation = getattr(annotation, "__forward_arg__", annotation)
        annotation = eval(annotation, globals, locals)

    if isinstance(annotation, TypeVar):
        # Either get the provided TypeVar arg via [] or extract default
        arg = generic_kwargs.pop(annotation.__name__, unpack_typevar(annotation))
        return () if arg is None else unpack_type(arg, globals, locals, generic_kwargs)
    elif isinstance(annotation, (UnionType, _UnionGenericAlias)):
        # fmt: off
        # UnionType, _UnionGenericAlias
        return tuple(set(sum((
            list(unpack_type(arg, globals, locals, generic_kwargs))
            for arg in annotation.__args__
        ), [])))
        # fmt: on
    # elif hasattr(annotation, "__args__") and not hasattr(annotation, "__type_params__"): # noqa
    # _CallableGenericAlias, _LiteralGenericAlias, _ConcatenateGenericAlias etc.
    elif isinstance(annotation, (GenericAlias, _GenericAlias, TypeAliasType)):
        # Check if any generic arguments are provided via [...]
        generic_args = list(getattr(annotation, "__args__", ()))

        for type_param in getattr(annotation, "__type_params__", ()):
            if arg := generic_args.pop(0) if generic_args else None:
                # Generic argument provided inside [...]
                generic_kwargs[type_param.__name__] = arg
            elif type_param.__name__ in generic_kwargs:
                continue
            elif arg := unpack_typevar(type_param):
                # Extract default (default/constraint/bound)
                generic_kwargs[type_param.__name__] = arg

        if hasattr(annotation, "__value__"):
            return unpack_type(annotation.__value__, locals, globals, generic_kwargs)
        else:
            # Drops brackets [] if generic
            return (annotation.__origin__,)
    else:
        # How did we get here?
        return (annotation,)
