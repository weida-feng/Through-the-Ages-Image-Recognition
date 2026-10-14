"""Replace notebook conversion chains with one explicit card catalog."""
from dataclasses import dataclass
from typing import Dict, Literal, Tuple

from ._labels import LEADER_NAMES, WONDER_NAMES

CardKind = Literal["leader", "wonder"]
EMPTY_CARD = "无"


@dataclass(frozen=True)
class Card:
    name: str
    identifier: int
    age: int


CATALOGS: Dict[str, Dict[str, Card]] = {
    "leader": {name: Card(name, i, i // 12) for i, name in enumerate(LEADER_NAMES)},
    "wonder": {name: Card(name, i, i // 8) for i, name in enumerate(WONDER_NAMES)},
}


def card_info(name: str, kind: CardKind) -> Card:
    """Return a preserved name's identifier and age (A=0, I=1, II=2, III=3)."""
    if name == EMPTY_CARD:
        return Card(EMPTY_CARD, -1, -1)
    try:
        catalog = CATALOGS[kind]
    except KeyError as exc:
        raise ValueError("Unknown card kind: {!r}".format(kind)) from exc
    try:
        return catalog[name]
    except KeyError as exc:
        raise ValueError("Unknown {} name: {!r}".format(kind, name)) from exc


def leaders_by_age(names: Tuple[str, ...]) -> Tuple[str, ...]:
    """Pad absent ages, while rejecting collisions rather than dropping a leader."""
    result = [EMPTY_CARD] * 4
    for name in names:
        if name == EMPTY_CARD:
            continue
        age = card_info(name, "leader").age
        if result[age] != EMPTY_CARD:
            raise ValueError("Multiple leaders in age {}: {} / {}".format(age, result[age], name))
        result[age] = name
    return tuple(result)

