"""Read the original headerless text formats without relying on row positions."""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterator, Tuple

GAME_CODE = re.compile(r"^[A-Z]{8}$")


@dataclass(frozen=True)
class TextRecord:
    sequence_number: int
    game_code: str
    values: Tuple[str, ...]


def validate_game_code(code: str) -> str:
    if not GAME_CODE.fullmatch(code):
        raise ValueError("Expected an eight-letter TTA game code, got {!r}".format(code))
    return code


def read_text(path: Path) -> str:
    """Detect the archive's UTF-16 BOM, otherwise read UTF-8 (optional BOM)."""
    raw = Path(path).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        return raw.decode(encoding)
    except UnicodeError as exc:
        raise ValueError("Cannot decode {} as {}".format(path, encoding)) from exc


def iter_records(path: Path) -> Iterator[TextRecord]:
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ValueError("{}:{}: missing game code".format(path, line_number))
        try:
            sequence = int(fields[0])
            code = validate_game_code(fields[1])
        except ValueError as exc:
            raise ValueError("{}:{}: {}".format(path, line_number, exc)) from exc
        yield TextRecord(sequence, code, tuple(fields[2:]))


def read_records(path: Path) -> Dict[str, TextRecord]:
    result = {}
    for row in iter_records(path):
        if row.game_code in result:
            raise ValueError("{}: duplicate game code {}".format(path, row.game_code))
        result[row.game_code] = row
    return result


def read_leader_matrix(path: Path) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    result = {}
    for code, row in read_records(path).items():
        if len(row.values) != 8:
            raise ValueError("{}: {} must have eight age-padded leader fields".format(path, code))
        result[code] = (row.values[:4], row.values[4:])
    return result


def pair_by_code(
    top: Dict[str, TextRecord], bottom: Dict[str, TextRecord]
) -> Iterator[Tuple[str, Tuple[str, ...], Tuple[str, ...]]]:
    """Join screenshot positions by key; file order and sequence numbers may differ."""
    if set(top) != set(bottom):
        raise ValueError("Top/bottom code mismatch: top-only={}, bottom-only={}".format(
            sorted(set(top) - set(bottom))[:5], sorted(set(bottom) - set(top))[:5]))
    for code in top:
        yield code, top[code].values, bottom[code].values

