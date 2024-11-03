import os
import unittest
from collections.abc import Callable
from types import NoneType
from typing import ForwardRef, TypeAlias, Union

from typing_extensions import TypeVar

from dataconfigs.utils import (
    is_dynamically_created,
    is_type_unpackable,
    slots_to_dict,
    unpack_type,
    unpack_typevar,
)


class TestUtils(unittest.TestCase):
    def test_slots_to_dict(self):
        class TestClass:
            __slots__ = ("a", "b")

            def __init__(self, a, b):
                self.a = a
                self.b = b

        obj = TestClass(1, 2)
        result = slots_to_dict(obj)
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_is_dynamically_created(self):
        class TestClassEmpty:
            pass

        class TestClassDynamicMethod:
            pass

        class TestClassStaticMethod:
            def method(self):
                pass

        exec("def method(self): pass", globals(), locals())
        TestClassDynamicMethod.method = locals()["method"]

        self.assertFalse(is_dynamically_created(TestClassEmpty, "method"))
        self.assertFalse(is_dynamically_created(TestClassStaticMethod, "method"))
        self.assertTrue(is_dynamically_created(TestClassDynamicMethod, "method"))

    def test_is_type_unpackable(self):
        self.assertTrue(is_type_unpackable(Union[int, str]))
        self.assertTrue(is_type_unpackable(int | str))
        self.assertTrue(is_type_unpackable(TypeVar("T")))
        self.assertTrue(is_type_unpackable("str"))
        self.assertTrue(is_type_unpackable(ForwardRef("SomeClass")))
        self.assertFalse(is_type_unpackable(int))
        self.assertFalse(is_type_unpackable(list))
        self.assertFalse(is_type_unpackable(str))

    def test_unpack_typevar(self):
        type PathType = os.PathLike | str | bytes

        T = TypeVar("T")
        TC = TypeVar("TC", str, bytes)
        TB = TypeVar("TB", bound=PathType)
        TD = TypeVar("TD", default=str)
        TCD = TypeVar("TCD", str, bytes, default=str)
        TBD = TypeVar("TBD", default=str, bound=PathType)

        self.assertEqual(unpack_typevar(T), None)
        self.assertEqual(unpack_typevar(TC), Union[str, bytes])
        self.assertEqual(unpack_typevar(TB), PathType)
        self.assertEqual(unpack_typevar(TD), str)
        self.assertEqual(unpack_typevar(TCD), str)
        self.assertEqual(unpack_typevar(TBD), str)

    def test_unpack_type_alias(self):
        class MyClass:
            pass

        MyClassAlias: TypeAlias = "MyClass"
        MyClassDupAlias: TypeAlias = "list[MyClass | MyClass] | list[MyClass]"
        MyGenericAlias = tuple[str, int]
        MyUnionAlias = Union[int, str] | float | int | None
        MyCallableAlias = Callable[[bool, int | float], None]
        MyComplexAlias = Union[MyClassAlias, MyUnionAlias, MyCallableAlias]

        self.assertEqual(set(unpack_type(MyClassAlias, globals(), locals())), {MyClass})
        self.assertEqual(set(unpack_type(MyClassDupAlias, globals(), locals())), {list})
        self.assertEqual(set(unpack_type(MyGenericAlias)), {tuple})
        self.assertEqual(set(unpack_type(MyUnionAlias)), {int, str, float, NoneType})
        self.assertEqual(set(unpack_type(MyCallableAlias)), {Callable})
        self.assertEqual(
            set(unpack_type(MyComplexAlias, globals(), locals())),
            {MyClass, int, str, float, NoneType, Callable},
        )

    def test_unpack_type_typealias(self):
        type MyInt = int
        type MyPath = os.PathLike | str | bytes
        type MyGeneric = tuple[str, int, MyPath]
        type MyIterable = MyPath | tuple | list | dict
        type MyGenericIterable[T, V] = MyPath | tuple[T, ...] | list[T] | dict[T, V]
        type MyExtraGenericIterable[T] = MyGenericIterable[T, T] | T

        self.assertEqual(set(unpack_type(MyInt)), {int})
        self.assertEqual(set(unpack_type(MyPath)), {os.PathLike, str, bytes})
        self.assertEqual(set(unpack_type(MyGeneric)), {tuple})
        self.assertEqual(
            set(unpack_type(MyIterable)),
            {os.PathLike, str, bytes, tuple, list, dict},
        )
        self.assertEqual(
            set(unpack_type(MyGenericIterable)),
            {os.PathLike, str, bytes, tuple, list, dict},
        )
        self.assertEqual(
            set(unpack_type(MyExtraGenericIterable)),
            {os.PathLike, str, bytes, tuple, list, dict},
        )

    def test_unpack_type_typevar(self):
        type PathType = os.PathLike | str | bytes

        T = TypeVar("T")
        TC = TypeVar("TC", str, bytes)
        TB = TypeVar("TB", bound=PathType)
        TD = TypeVar("TD", default=str)
        TCD = TypeVar("TCD", str, bytes, default=str)
        TBD = TypeVar("TBD", default=str, bound=PathType)
        TD2 = TypeVar("TD2", default=PathType | str)
        TB2 = TypeVar("TB2", bound=float | int | TC)
        TC2 = TypeVar("TC2", int | bool, T, T)

        self.assertEqual(set(unpack_type(T)), set())
        self.assertEqual(set(unpack_type(TC)), {str, bytes})
        self.assertEqual(set(unpack_type(TB)), {os.PathLike, str, bytes})
        self.assertEqual(set(unpack_type(TD)), {str})
        self.assertEqual(set(unpack_type(TCD)), {str})
        self.assertEqual(set(unpack_type(TBD)), {str})
        self.assertEqual(set(unpack_type(TD2)), {os.PathLike, str, bytes})
        self.assertEqual(set(unpack_type(TB2)), {float, int, str, bytes})
        self.assertEqual(set(unpack_type(TC2)), {int, bool})

    def test_unpack_type_complex(self):
        type MyPath = os.PathLike | str
        type MyGenericIterable[T, V] = MyPath | dict[T, V]
        type MyExtraGenericIterable[T] = MyGenericIterable[T, T] | T

        T = TypeVar("T")
        TC = TypeVar("TC", int, float)
        TB = TypeVar("TB", bound=MyExtraGenericIterable[bool] | TC | T)
        TD = TypeVar("TD", default=MyGenericIterable[TB, int] | None)

        type MyComplexAlias[T2: bool] = T2 | TC | T | MyGenericIterable[
            T, TC
        ] | MyExtraGenericIterable[TB]

        self.assertEqual(set(unpack_type(MyPath)), {os.PathLike, str})
        self.assertEqual(set(unpack_type(MyGenericIterable)), {os.PathLike, str, dict})
        self.assertEqual(
            set(unpack_type(MyExtraGenericIterable)), {os.PathLike, str, dict}
        )
        self.assertEqual(set(unpack_type(T)), set())
        self.assertEqual(set(unpack_type(TC)), {int, float})
        self.assertEqual(
            set(unpack_type(TB)), {os.PathLike, str, dict, bool, int, float}
        )
        self.assertEqual(set(unpack_type(TD)), {os.PathLike, str, dict, NoneType})
        self.assertEqual(
            set(unpack_type(MyComplexAlias)),
            {bool, int, float, os.PathLike, str, dict},
        )
        self.assertEqual(
            set(unpack_type(MyComplexAlias[bytes], globals(), locals())),
            {bytes, bool, int, float, os.PathLike, str, dict},
        )


if __name__ == "__main__":
    unittest.main()
