"""Independent comparisons with historical Excel imports and earlier wonder results."""
from collections import Counter
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

from .records import read_records
from .sources import parse_flag, parse_position, read_sheet, require_unique


def check_text_players(
    data_root: Path, config: Dict[str, Any], sources: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    reports = {}
    differences = []
    for spec in config["text_player_checks"]:
        path = Path("historical") / spec["batch"] / spec["file"]
        rows = read_records(data_root / path)
        source = sources[spec["source"]].set_index("game_code").to_dict("index")
        mismatch_codes = set()
        extras = Counter()
        for code, record in rows.items():
            if len(record.values) != spec["value_fields"] or code not in source:
                raise ValueError("{}: invalid or unmatched player record {}".format(path, code))
            values = record.values
            actual = ((values[0], parse_position(values[1]), parse_flag(values[2])),
                      (values[3], parse_position(values[4]), parse_flag(values[5])))
            row = source[code]
            expected = {row["player{}_position".format(slot)]:
                        (row["player{}_username".format(slot)], row["player{}_is_win".format(slot)])
                        for slot in (1, 2)}
            if {item[1] for item in actual} != set(expected):
                raise ValueError("{}: player positions disagree in {}".format(path, code))
            for username, position, is_win in actual:
                expected_name, expected_win = expected[position]
                if username != expected_name:
                    raise ValueError("{}: player names disagree in {}".format(path, code))
                if is_win != expected_win:
                    if spec["outcome_resolution"] != "source_workbook":
                        raise ValueError("{}: winner flags disagree in {}".format(path, code))
                    mismatch_codes.add(code)
                    differences.append({
                        "game_code": code, "batch": spec["batch"], "player_position": position,
                        "username": username, "field": "is_win", "text_value": is_win,
                        "workbook_value": expected_win, "text_source_file": path.as_posix(),
                        "text_sequence_number": record.sequence_number,
                        "workbook_source_file": row["source_file"],
                        "workbook_source_sheet": row["source_sheet"],
                        "workbook_source_row": row["source_row"], "resolution": "source_workbook",
                    })
            extras.update(values[6:])
        reports[spec["batch"]] = {
            "source_file": path.as_posix(), "compared_games": len(rows),
            "identity_mismatch_games": 0, "outcome_mismatch_games": len(mismatch_codes),
            "outcome_resolution": spec["outcome_resolution"],
            "extra_historical_field_values": dict(extras),
        }
    columns = ["game_code", "batch", "player_position", "username", "field", "text_value",
               "workbook_value", "text_source_file", "text_sequence_number",
               "workbook_source_file", "workbook_source_sheet", "workbook_source_row", "resolution"]
    return pd.DataFrame(differences, columns=columns), reports


def compare_historical_excel(
    data_root: Path, spec: Dict[str, str], tables: Dict[str, pd.DataFrame]
) -> Dict[str, Any]:
    """Compare every winner/loser field by game code, independently of sheet ordering."""
    reference = read_sheet(data_root / spec["workbook"], spec["sheet"])
    reference = reference.rename(columns={"code": "game_code"})
    require_unique(reference, "game_code", "historical Excel reference")
    games = tables["games"].loc[tables["games"].batch.eq(spec["batch"])]
    if set(reference.game_code) != set(games.game_code):
        raise ValueError("Historical Excel reference game codes differ from the prepared batch")
    players = {(row.game_code, row.player_position): row.username
               for row in tables["players"].itertuples(index=False)}
    leaders = {(row.game_code, row.player_position, row.age): row.card_name
               for row in tables["leader_slots"].itertuples(index=False)}
    wonders = {}
    for row in tables["wonders"].sort_values("card_index").itertuples(index=False):
        wonders.setdefault((row.game_code, row.player_position), []).append(row.card_name)
    ages = ("A", "I", "II", "III")
    compared_fields = ["player_win", "player_lose", "position_win"]
    compared_fields += ["{}方{}領袖".format(side, age) for side in ("勝", "負") for age in ages]
    compared_fields += ["{}方奇跡{}".format(side, i) for side in ("勝", "負") for i in range(1, 9)]
    if not set(compared_fields).issubset(reference.columns):
        raise ValueError("Historical Excel reference is missing winner/loser columns")
    reference_rows = reference.set_index("game_code").to_dict("index")
    mismatches = []
    mismatch_codes = set()
    mismatch_count = 0
    for game in games.itertuples(index=False):
        winner = game.winner_position
        loser = 1 - winner
        expected = {"player_win": players[(game.game_code, winner)],
                    "player_lose": players[(game.game_code, loser)], "position_win": winner}
        for side, position in (("勝", winner), ("負", loser)):
            expected.update({"{}方{}領袖".format(side, age): leaders[(game.game_code, position, age)]
                             for age in ages})
            names = wonders.get((game.game_code, position), [])
            if len(names) > 8:
                raise ValueError("Historical reference has only eight wonder columns per side")
            expected.update({"{}方奇跡{}".format(side, i): names[i - 1] if i <= len(names) else ""
                             for i in range(1, 9)})
        actual = reference_rows[game.game_code]
        for field, value in expected.items():
            if actual[field] != value:
                mismatch_count += 1
                mismatch_codes.add(game.game_code)
                if len(mismatches) < 10:
                    mismatches.append({"game_code": game.game_code, "field": field,
                                       "prepared": value, "historical": str(actual[field])})
    return {"source_file": spec["workbook"], "source_sheet": spec["sheet"],
            "batch": spec["batch"], "compared_games": len(games),
            "compared_fields_per_game": len(compared_fields),
            "compared_cells": len(games) * len(compared_fields),
            "mismatch_games": len(mismatch_codes), "mismatch_cells": mismatch_count,
            "mismatch_examples": mismatches}


def historical_cleanup(data_root: Path) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Record actual old/current differences without inventing deletion rules or reasons."""
    changes = []
    for position, index in (("top", 1), ("bottom", 2)):
        old_file = "historical/resign/resign_w{}o.txt".format(index)
        current_file = "historical/resign/resign_w{}.txt".format(index)
        old = read_records(data_root / old_file)
        current = read_records(data_root / current_file)
        if set(old) != set(current):
            raise ValueError("Historical/current resignation wonder codes differ")
        for code, record in old.items():
            before, after = record.values, current[code].values
            if before == after:
                continue
            removed = Counter(before) - Counter(after)
            added = Counter(after) - Counter(before)
            changes.append({
                "game_code": code, "batch": "resign", "screenshot_position": position,
                "old_cards": json.dumps(before, ensure_ascii=False),
                "current_cards": json.dumps(after, ensure_ascii=False),
                "removed_cards": json.dumps(list(removed.elements()), ensure_ascii=False),
                "added_cards": json.dumps(list(added.elements()), ensure_ascii=False),
                "old_source_file": old_file, "current_source_file": current_file,
                "reason": "not recorded in the supplied archive",
            })
    columns = ["game_code", "batch", "screenshot_position", "old_cards", "current_cards",
               "removed_cards", "added_cards", "old_source_file", "current_source_file", "reason"]
    frame = pd.DataFrame(changes, columns=columns)
    return frame, {"changed_player_rows": len(frame), "changed_games": frame.game_code.nunique()}
