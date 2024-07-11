from typing import TypeVar, Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

from pyrsistent import PSet, PMap, PVector, pset, pmap, pvector
from .formal_verification_annotations import *
from functools import reduce

T1 = TypeVar('T1')
T2 = TypeVar('T2')


def pvector_of_one_element(e: T1) -> PVector[T1]:
    return pvector([e])


def pvector_concat(a: PVector[T1], b: PVector[T1]) -> PVector[T1]:
    return a.extend(b)


def from_set_to_pvector(s: PSet[T1]) -> PVector[T1]:
    return pvector(s)


def pset_get_empty() -> PSet[T1]:
    return pset()


def pset_merge(a: PSet[T1], b: PSet[T1]) -> PSet[T1]:
    return a.union(b)


def pset_merge_flatten(s: PSet[PSet[T1]]) -> PSet[T1]:
    return reduce(pset_merge, s, pset())


print(pset_merge_flatten(pset([pset([1, 2]), pset([2, 3])])))


def pset_intersection(s1: PSet[T1], s2: PSet[T1]) -> PSet[T1]:
    return s1.intersection(s2)


def pset_difference(s1: PSet[T1], s2: PSet[T1]) -> PSet[T1]:
    return s1.difference(s2)


def pset_get_singleton(e: T1) -> PSet[T1]:
    return pset([e])


def pset_add(s: PSet[T1], e: T1) -> PSet[T1]:
    return s.add(e)


def pset_pick_element(s: PSet[T1]) -> T1:
    Requires(len(s) > 0)
    return list(s)[0]


def pset_filter(p: Callable[[T1], bool], s: PSet[T1]) -> PSet[T1]:
    r: PSet[T1] = pset()

    for e in s:
        if p(e):
            r = r.add(e)

    return r
    # return pset(filter(p, s))


def pset_max(s: PSet[T1], a: Callable[[T1], SupportsRichComparison]) -> T1:
    Requires(len(s) > 0)
    return max(s, key=a)


def pset_sum(s: PSet[int]) -> int:
    return sum(s)


def pset_is_empty(s: PSet[T1]) -> bool:
    return len(s) == 0


def from_pvector_to_pset(v: PVector[T1]) -> PSet[T1]:
    return pset(v)


def pset_map(p: Callable[[T1], T2], s: PSet[T1]) -> PSet[T2]:
    r: PSet[T2] = pset()

    for e in s:
        r = r.add(p(e))

    return r


def pmap_has(pm: PMap[T1, T2], k: T1) -> bool:
    return k in pm


def pmap_get(pm: PMap[T1, T2], k: T1) -> T2:
    Requires(pmap_has(pm, k))
    return pm[k]


def pmap_get_empty() -> PMap[T1, T2]:
    return pmap()


def pmap_set(pm: PMap[T1, T2], k: T1, v: T2) -> PMap[T1, T2]:
    return pm.set(k, v)


def pmap_merge(a: PMap[T1, T2], b: PMap[T1, T2]) -> PMap[T1, T2]:
    return a.update(b)


def pmap_keys(d: PMap[T1, T2]) -> PSet[T1]:
    return pset(d.keys())


def pmap_values(d: PMap[T1, T2]) -> PSet[T2]:
    return pset(d.values())
