"""Explicit adapters for the two historical Excel player-data layouts."""
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from .records import validate_game_code


def parse_flag(value: Any) -> bool:
    """Accept the archive's boolean/0/1 spellings; never use bool('FALSE')."""
    token = str(value).strip().upper()
    if token in ("TRUE", "1", "1.0"):
        return True
    if token in ("FALSE", "0", "0.0"):
        return False
    raise ValueError("Expected TRUE/FALSE or 0/1 flag, got {!r}".format(value))


def parse_position(value: Any) -> int:
    token = str(value).strip()
    if token in ("0", "0.0"):
        return 0
    if token in ("1", "1.0"):
        return 1
    raise ValueError("Expected player position 0 or 1, got {!r}".format(value))


def require_unique(frame: pd.DataFrame, keys: Any, context: str) -> None:
    keys = [keys] if isinstance(keys, str) else list(keys)
    if frame[keys].isna().any().any() or frame[keys].eq("").any().any():
        raise ValueError("{}: missing join key".format(context))
    duplicate = frame.duplicated(keys, keep=False)
    if duplicate.any():
        examples = frame.loc[duplicate, keys].head(3).to_dict("records")
        raise ValueError("{}: duplicate keys {}".format(context, examples))


def normalize_source(frame: pd.DataFrame, context: str) -> pd.DataFrame:
    """Validate two distinct positions and exactly one winner per historical game."""
    result = frame.copy()
    result["game_code"] = result["game_code"].map(validate_game_code)
    require_unique(result, "game_code", context)
    for slot in (1, 2):
        prefix = "player{}_".format(slot)
        if result[prefix + "username"].isna().any() or \
                result[prefix + "username"].astype(str).str.strip().eq("").any():
            raise ValueError("{}: missing player username".format(context))
        result[prefix + "username"] = result[prefix + "username"].astype(str)
        result[prefix + "position"] = result[prefix + "position"].map(parse_position)
        for flag in ("is_win", "is_resigned", "is_expired"):
            result[prefix + flag] = result[prefix + flag].map(parse_flag)
    same = result.player1_position.eq(result.player2_position)
    if same.any():
        raise ValueError("{}: players share a position in {}".format(
            context, result.loc[same, "game_code"].head(3).tolist()))
    win_count = result.player1_is_win.astype(int) + result.player2_is_win.astype(int)
    if win_count.ne(1).any():
        raise ValueError("{}: expected exactly one winner in {}".format(
            context, result.loc[win_count.ne(1), "game_code"].head(3).tolist()))
    return result


def read_sheet(path: Path, sheet: str) -> pd.DataFrame:
    """Preserve identifiers such as 'NA' and textual nulls rather than treating them as NaN."""
    return pd.read_excel(path, sheet_name=sheet, dtype=object,
                         keep_default_na=False, engine="openpyxl")


def load_sources(data_root: Path, config: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    result = {}
    for name, spec in config["sources"].items():
        raw = read_sheet(data_root / spec["workbook"], spec["sheet"])
        columns = spec["columns"]
        missing = set(columns.values()) - set(raw.columns)
        if missing:
            raise ValueError("{}: missing source columns {}".format(name, sorted(missing)))
        frame = raw.loc[:, list(columns.values())].copy()
        frame.columns = list(columns)
        frame["source_file"] = spec["workbook"]
        frame["source_sheet"] = spec["sheet"]
        frame["source_row"] = range(2, len(frame) + 2)
        if len(frame) != spec["expected_games"]:
            raise ValueError("{}: expected {} source games, got {}".format(
                name, spec["expected_games"], len(frame)))
        result[name] = normalize_source(frame, name)
    return result


def players_from_source(
    source: pd.DataFrame, position_mapping: Dict[str, int]
) -> pd.DataFrame:
    """Stack source slots, then identify players by position rather than slot or result."""
    if set(position_mapping) != {"top", "bottom"} or \
            set(position_mapping.values()) != {0, 1}:
        raise ValueError("Position mapping must assign top/bottom to distinct 0/1 positions")
    reverse_mapping = {value: key for key, value in position_mapping.items()}
    parts = []
    metadata = [column for column in ("game_code", "batch", "source_sequence_number",
                                      "source_file", "source_sheet", "source_row")
                if column in source]
    for slot in (1, 2):
        part = source.loc[:, metadata].copy()
        part["source_player_slot"] = slot
        for field in ("username", "position", "is_win", "is_resigned", "is_expired"):
            target = "player_position" if field == "position" else field
            part[target] = source["player{}_{}".format(slot, field)]
        part["screenshot_position"] = part.player_position.map(reverse_mapping)
        parts.append(part)
    players = pd.concat(parts, ignore_index=True)
    require_unique(players, ["game_code", "player_position"], "players")
    return players.sort_values(["game_code", "player_position"]).reset_index(drop=True)
