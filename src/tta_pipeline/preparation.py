"""Replace historical manual Excel preparation with reproducible keyed pandas joins."""
import hashlib
import json
from pathlib import Path
import platform
from typing import Any, Dict, Tuple

import pandas as pd

from .audit import audit_archive
from .catalog import card_info
from .reconciliation import check_text_players, compare_historical_excel, historical_cleanup
from .records import read_records
from .sources import load_sources, players_from_source, require_unique

AGES = ("A", "I", "II", "III")


def join_game_sources(
    games: pd.DataFrame, sources: Dict[str, pd.DataFrame], batch_sources: Dict[str, str]
) -> pd.DataFrame:
    """Require one matched source row per recognized game; never silently drop games."""
    require_unique(games, "game_code", "recognized games")
    parts = []
    for batch, subset in games.groupby("batch", sort=False):
        if batch not in batch_sources:
            raise ValueError("No player source configured for batch {}".format(batch))
        source = sources[batch_sources[batch]]
        require_unique(source, "game_code", "player source for " + batch)
        merged = subset.merge(source, on="game_code", how="left",
                              validate="one_to_one", indicator="_source_match")
        missing = merged._source_match.ne("both")
        if missing.any():
            raise ValueError("Missing player source for {}".format(
                merged.loc[missing, "game_code"].head(3).tolist()))
        parts.append(merged.drop(columns="_source_match"))
    return pd.concat(parts, ignore_index=True).sort_values("game_code").reset_index(drop=True)


def recognition_tables(
    data_root: Path, manifest: Dict[str, Any], position_mapping: Dict[str, int]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games, leaders, wonders = [], [], []
    for batch in manifest["canonical_batches"]:
        spec = manifest["batches"][batch]
        directory = Path("historical") / batch
        leader_file = directory / spec["leaders_matrix"]
        matrix = read_records(data_root / leader_file)
        if len(matrix) != spec["expected_games"]:
            raise ValueError("{}: unexpected recognition game count".format(batch))
        for code, record in matrix.items():
            if len(record.values) != 8:
                raise ValueError("{}: {} must have eight leader slots".format(batch, code))
            games.append({"game_code": code, "batch": batch, "batch_role": spec["role"],
                          "recognition_sequence_number": record.sequence_number})
            for offset, position in enumerate(("top", "bottom")):
                for age_index, name in enumerate(record.values[offset * 4:offset * 4 + 4]):
                    card = card_info(name, "leader")
                    if card.identifier >= 0 and card.age != age_index:
                        raise ValueError("{}: leader {} is in the wrong age slot".format(code, name))
                    leaders.append({
                        "game_code": code, "batch": batch, "screenshot_position": position,
                        "player_position": position_mapping[position], "age_index": age_index,
                        "age": AGES[age_index], "card_name": name, "card_id": card.identifier,
                        "is_present": card.identifier >= 0, "source_file": leader_file.as_posix(),
                        "source_sequence_number": record.sequence_number,
                    })
        for position in ("top", "bottom"):
            wonder_file = directory / spec["wonders_" + position]
            records = read_records(data_root / wonder_file)
            if set(records) != set(matrix):
                raise ValueError("{}: wonder/leader codes differ".format(batch))
            for code, record in records.items():
                for index, name in enumerate(record.values):
                    card = card_info(name, "wonder")
                    if card.identifier < 0:
                        raise ValueError("{}: wonder lists must contain actual card names".format(code))
                    wonders.append({
                        "game_code": code, "batch": batch, "screenshot_position": position,
                        "player_position": position_mapping[position], "card_index": index,
                        "age_index": card.age, "age": AGES[card.age], "card_name": name,
                        "card_id": card.identifier, "source_file": wonder_file.as_posix(),
                        "source_sequence_number": record.sequence_number,
                    })
    wonder_columns = ["game_code", "batch", "screenshot_position", "player_position",
                      "card_index", "age_index", "age", "card_name", "card_id", "source_file",
                      "source_sequence_number"]
    return (pd.DataFrame(games), pd.DataFrame(leaders),
            pd.DataFrame(wonders, columns=wonder_columns))


def attach_players(cards: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    fields = ["game_code", "player_position", "username", "is_win", "is_resigned",
              "is_expired", "outcome"]
    result = cards.merge(players.loc[:, fields], on=["game_code", "player_position"],
                         how="left", validate="many_to_one", indicator="_player_match")
    if result._player_match.ne("both").any():
        raise ValueError("Card record has no matched player")
    return result.drop(columns="_player_match")


def build_prepared_tables(data_root: Path) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """Build and reconcile in memory before writing any output files."""
    data_root = Path(data_root)
    manifest = json.loads((data_root / "datasets.json").read_text(encoding="utf-8"))
    config = json.loads((data_root / "preparation.json").read_text(encoding="utf-8"))
    position_mapping = config["position_mapping"]
    if set(position_mapping) != {"top", "bottom"} or set(position_mapping.values()) != {0, 1}:
        raise ValueError("Invalid screenshot/player position mapping")
    audit = audit_archive(data_root)
    sources = load_sources(data_root, config)
    source_pool = pd.concat(list(sources.values()), ignore_index=True)
    require_unique(source_pool, "game_code", "combined source workbooks")
    text_differences, text_checks = check_text_players(data_root, config, sources)
    recognized, leader_slots, wonders = recognition_tables(data_root, manifest, position_mapping)
    selected = join_game_sources(recognized, sources, config["batch_sources"])
    players = players_from_source(selected, position_mapping)
    players["outcome"] = players.is_win.map({True: "win", False: "loss"})
    game_columns = ["game_code", "batch", "batch_role", "recognition_sequence_number",
                    "source_sequence_number", "source_file", "source_sheet", "source_row"]
    games = selected.loc[:, game_columns].copy()
    games["winner_position"] = selected.player1_position.where(
        selected.player1_is_win, selected.player2_position)
    games["has_resignation"] = selected.player1_is_resigned | selected.player2_is_resigned
    games["has_expiration"] = selected.player1_is_expired | selected.player2_is_expired
    completed = games.batch_role.eq("canonical_completed")
    if (completed & (games.has_resignation | games.has_expiration)).any():
        raise ValueError("A completed batch contains resignation/expiration flags")
    if (games.batch_role.eq("canonical_resigned") & ~games.has_resignation).any():
        raise ValueError("A resigned batch contains a game without a resignation flag")
    tables = {"games": games, "players": players,
              "leader_slots": attach_players(leader_slots, players),
              "wonders": attach_players(wonders, players)}
    tables["leader_slots"] = tables["leader_slots"].sort_values(
        ["game_code", "player_position", "age_index"]).reset_index(drop=True)
    tables["wonders"] = tables["wonders"].sort_values(
        ["game_code", "player_position", "card_index"]).reset_index(drop=True)
    require_unique(tables["leader_slots"], ["game_code", "player_position", "age"], "leader slots")
    require_unique(tables["wonders"], ["game_code", "player_position", "card_index"], "wonders")
    if len(games) != audit["unique_games"] or len(players) != len(games) * 2 or \
            len(leader_slots) != len(games) * 8:
        raise ValueError("Prepared table counts do not reconcile with the archive")
    findings = []
    for finding in audit["findings"]:
        issue = dict(finding)
        issue["canonical_batch"] = "5239" if issue["batch"] in ("900", "4339") else issue["batch"]
        findings.append(issue)
    finding_columns = ["game_code", "kind", "rule", "position", "details", "batch", "canonical_batch"]
    tables["quality_findings"] = pd.DataFrame(findings, columns=finding_columns)
    tables["source_discrepancies"] = text_differences.sort_values(
        ["game_code", "player_position"]).reset_index(drop=True)
    cleanup, cleanup_report = historical_cleanup(data_root)
    tables["historical_cleanup"] = cleanup
    tables["unprocessed_source_games"] = source_pool.loc[
        ~source_pool.game_code.isin(games.game_code)].sort_values("game_code").reset_index(drop=True)
    reference = compare_historical_excel(data_root, config["historical_reference"], tables)
    if reference["mismatch_cells"]:
        raise ValueError("Prepared fields differ from historical Excel: {}".format(
            reference["mismatch_examples"][:3]))
    report = {
        "schema_version": 1, "origin": "current_pandas_automation_of_manual_excel_preparation",
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "canonical_batches": manifest["canonical_batches"], "position_mapping": position_mapping,
        "unique_games": len(games), "table_rows": {name: len(frame) for name, frame in tables.items()},
        "games_by_batch": {str(key): int(value) for key, value in games.groupby("batch").size().items()},
        "outcome_counts": {str(key): int(value) for key, value in players.outcome.value_counts().items()},
        "resigned_games_with_expiration_flag": int((games.has_resignation & games.has_expiration).sum()),
        "source_games_without_recognition": len(tables["unprocessed_source_games"]),
        "historical_excel_comparison": reference, "text_player_comparisons": text_checks,
        "historical_cleanup": cleanup_report, "review_findings": len(findings),
        "note": "No statistical filtering or new recognition corrections were applied. "
                "Unprocessed source games are listed separately; their exclusion reason is unknown.",
    }
    input_paths = {data_root / "datasets.json", data_root / "preparation.json"}
    input_paths.update(data_root / spec["workbook"] for spec in config["sources"].values())
    input_paths.update((data_root / "historical").rglob("*.txt"))
    report["input_sha256"] = {
        path.relative_to(data_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(input_paths)
    }
    return tables, report


def prepare_archive(data_root: Path, output: Path) -> Dict[str, Any]:
    """Export normalized UTF-8 CSVs and reconciliation evidence to a fresh folder."""
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty preparation output directory")
    tables, report = build_prepared_tables(data_root)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output / (name + ".csv"), index=False, encoding="utf-8-sig", lineterminator="\n")
    (output / "reconciliation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
