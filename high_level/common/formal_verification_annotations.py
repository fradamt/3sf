from typing import TypeVar, Optional, Callable, ParamSpec, NoReturn

C = TypeVar("C", bound=Callable)


def Requires(expr: bool) -> None:
    pass


def Init(c: C) -> C:
    return c


def Event(c: C) -> C:
    return c


def View(c: C) -> C:
    return c
