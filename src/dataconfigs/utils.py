import inspect
from typing import Any

# class hybridmethod[T, **P, R]:
#     def __init__(self, method: Callable[Concatenate[T | type[T], P], R]):
#         self.method = method

#     def __get__(
#         self,
#         obj: T | None = None,
#         objtype: type[T] | None = None,
#     ) -> Callable[P, R]:
#         @functools.wraps(self.method)
#         def _wrapper(*args, **kwargs):
#             if obj is not None:
#                 return self.method(obj, *args, **kwargs)
#             else:
#                 return self.method(objtype, *args, **kwargs)

#         return _wrapper

#     @staticmethod
#     def as_nonproperty(method):
#         @hybridmethod
#         @functools.wraps(method)
#         def wrapper(*args, **kwargs):
#             return method(*args, **kwargs)

#         return wrapper

# class hybridproperty(property):
#     def __get__(self, obj, cls):
#         return self.fget(cls) if obj is None else self.fget(obj)


# def hybridmethod[
#     T, **P, R
# ](method: Callable[Concatenate[T | type[T], P], R]) -> Callable[P, R]:
#     # NOTE: This method is only suitable when the method has no
#     # additional arguments. Otherwise, type-hinting fails.

#     # We cannot simply wrap the target method with instanceclassmethod.
#     # This is because, due to "__get__" property, the decorated method
#     # will be interpreted as a property (only pylint misinterprets it).

#     # https://stackoverflow.com/a/28238047
#     class instanceclassmethod(classmethod):
#         def __get__(self, instance, type_):
#             descr_get = super().__get__ if instance is None else self.__func__.__get__
#             return descr_get(instance, type_)

#     @instanceclassmethod
#     @functools.wraps(method)
#     def wrapper(*args, **kwargs):
#         return method(*args, **kwargs)

#     return wrapper


def slots_to_dict(obj: Any) -> dict[str, Any]:
    return {k: getattr(obj, k) for k in obj.__slots__}


def is_dynamically_created(obj: Any, fn_name: str) -> bool:
    if not hasattr(obj, fn_name):
        return False

    try:
        return not inspect.getsource(getattr(obj, fn_name))
    except OSError:
        return True
