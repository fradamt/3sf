from typing import TypeVar, Optional, Callable, ParamSpec, NoReturn

TP = ParamSpec('TP')
TR = TypeVar('TR')

def Requires(expr: bool) -> None:
    pass


def Init(c: Callable[TP, TR]) -> Callable[TP, TR]:
    return c


def Event(c: Callable[TP, TR]) -> Callable[TP, TR]:
    return c


def View(c: Callable[TP,TR]) -> Callable[TP,TR]:
    return c
