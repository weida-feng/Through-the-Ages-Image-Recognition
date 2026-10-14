"""Preserve the original rule-based checks and make their findings explicit."""
from collections import Counter
from dataclasses import asdict, dataclass
from typing import List, Tuple

from .catalog import CardKind, EMPTY_CARD, card_info


@dataclass(frozen=True)
class Finding:
    game_code: str
    kind: str
    rule: str
    position: str
    details: str

    def to_dict(self):
        return asdict(self)


def check_cards(game_code: str, top: Tuple[str, ...], bottom: Tuple[str, ...],
                kind: CardKind) -> List[Finding]:
    """Collect all findings; an age-order flag is a review request, not proof of error."""
    findings = []
    sides = {"top": tuple(n for n in top if n != EMPTY_CARD),
             "bottom": tuple(n for n in bottom if n != EMPTY_CARD)}
    overlap = sorted(set(sides["top"]) & set(sides["bottom"]))
    if overlap:
        findings.append(Finding(game_code, kind, "shared_card", "both", ", ".join(overlap)))
    for position, names in sides.items():
        repeated = sorted(n for n, count in Counter(names).items() if count > 1)
        if repeated:
            findings.append(Finding(game_code, kind, "repeated_card", position,
                                    ", ".join(repeated)))
        ages = []
        for name in names:
            try:
                ages.append(card_info(name, kind).age)
            except ValueError:
                findings.append(Finding(game_code, kind, "unknown_name", position, name))
        if len(ages) != len(names):
            continue
        if kind == "leader" and len(ages) != len(set(ages)):
            findings.append(Finding(game_code, kind, "repeated_age", position,
                                    "More than one leader in an age"))
        if any(a > b for a, b in zip(ages, ages[1:])):
            findings.append(Finding(game_code, kind, "age_order", position,
                                    "Recorded order is not nondecreasing by age"))
    return findings

