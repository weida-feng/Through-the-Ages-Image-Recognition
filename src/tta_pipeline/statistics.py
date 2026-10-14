"""Descriptive card statistics with explicit game populations and denominators."""
import hashlib
import json
import math
from pathlib import Path
import platform
from typing import Any, Dict, Tuple

import pandas as pd

from .catalog import CATALOGS, EMPTY_CARD
from .sources import parse_flag, parse_position, require_unique

AGES = ("A", "I", "II", "III")
COHORT_DESCRIPTIONS = {
    "completed": "No resignation or expiration flag; primary descriptive population",
    "resigned": "Any resignation flag, including games also carrying expiration flags",
    "resigned_no_expiration": "Resigned games without any expiration flag",
    "all_processed": "All supplied canonical recognition games",
    "historical_5239": "Early 5239-game batch, for historical Excel comparison",
    "later_6724": "Later 6724-game completed batch",
    "completed_without_review_cases": "Completed population excluding pending recognition review games",
}


def wilson_interval(wins: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Nominal binomial interval; repeated-player dependence is not adjusted here."""
    if total < 0 or wins < 0 or wins > total or not math.isfinite(z) or z <= 0:
        raise ValueError("Invalid Wilson counts or z value")
    if total == 0:
        return math.nan, math.nan
    rate = wins / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def load_prepared(prepared: Path) -> Dict[str, pd.DataFrame]:
    """Read the exported schema and verify identity, outcomes, and card metadata."""
    tables = {name: pd.read_csv(Path(prepared) / (name + ".csv"), dtype=object,
                               keep_default_na=False)
              for name in ("games", "players", "leader_slots", "wonders", "quality_findings")}
    games, players = tables["games"], tables["players"]
    require_unique(games, "game_code", "statistics games")
    games["winner_position"] = games.winner_position.map(parse_position)
    for field in ("has_resignation", "has_expiration"):
        games[field] = games[field].map(parse_flag)
    players["player_position"] = players.player_position.map(parse_position)
    for field in ("is_win", "is_resigned", "is_expired"):
        players[field] = players[field].map(parse_flag)
    require_unique(players, ["game_code", "player_position"], "statistics players")
    if set(players.game_code) != set(games.game_code):
        raise ValueError("Statistics player/game keys differ")
    counts = players.groupby("game_code").agg(player_rows=("player_position", "size"),
                                              wins=("is_win", "sum"))
    if counts.player_rows.ne(2).any() or counts.wins.ne(1).any():
        raise ValueError("Statistics require two players and one winner per game")
    player_games = players.merge(games[["game_code", "winner_position", "has_resignation",
                                        "has_expiration"]], on="game_code", validate="many_to_one")
    if player_games.is_win.ne(player_games.player_position.eq(player_games.winner_position)).any():
        raise ValueError("Prepared player/game winner fields disagree")
    flags = players.groupby("game_code")[["is_resigned", "is_expired"]].any()
    flags = flags.reindex(games.game_code).reset_index(drop=True)
    if flags.is_resigned.ne(games.has_resignation).any() or \
            flags.is_expired.ne(games.has_expiration).any():
        raise ValueError("Prepared player/game ending flags disagree")
    for kind, name in (("leader", "leader_slots"), ("wonder", "wonders")):
        frame = tables[name]
        frame["player_position"] = frame.player_position.map(parse_position)
        frame["is_win"] = frame.is_win.map(parse_flag)
        frame["age_index"] = pd.to_numeric(frame.age_index, errors="raise")
        frame["card_id"] = pd.to_numeric(frame.card_id, errors="raise")
        key = "age" if kind == "leader" else "card_index"
        require_unique(frame, ["game_code", "player_position", key], name)
        if kind == "leader":
            frame["is_present"] = frame.is_present.map(parse_flag)
            if frame.is_present.ne(frame.card_name.ne(EMPTY_CARD)).any():
                raise ValueError("Leader presence flags disagree with card names")
            grouped = frame.groupby(["game_code", "player_position"]).age.agg(tuple)
            if len(grouped) != len(players) or any(set(ages) != set(AGES) for ages in grouped):
                raise ValueError("Prepared leaders must have four age slots per player")
            actual = frame.loc[frame.is_present]
        else:
            actual = frame
        if not actual.card_name.isin(CATALOGS[kind]).all():
            raise ValueError("Prepared {} table contains unknown card names".format(kind))
        for card in CATALOGS[kind].values():
            rows = actual.loc[actual.card_name.eq(card.name)]
            if rows.card_id.ne(card.identifier).any() or rows.age_index.ne(card.age).any() or \
                    rows.age.ne(AGES[card.age]).any():
                raise ValueError("Prepared metadata disagrees for {}".format(card.name))
        # The archive's card rules allow only one use of a given card in a game.
        require_unique(actual, ["game_code", "card_name"], kind + " uses")
        checked = frame.merge(players[["game_code", "player_position", "is_win", "username"]],
                              on=["game_code", "player_position"], how="left",
                              validate="many_to_one", suffixes=("", "_player"), indicator=True)
        if checked._merge.ne("both").any() or checked.is_win.ne(checked.is_win_player).any() or \
                checked.username.ne(checked.username_player).any():
            raise ValueError("Prepared card/player identity or winner fields disagree")
    report = json.loads((Path(prepared) / "reconciliation.json").read_text(encoding="utf-8"))
    for name, frame in tables.items():
        if len(frame) != report["table_rows"][name]:
            raise ValueError("Prepared {} count differs from its reconciliation report".format(name))
    return tables


def select_cohorts(games: pd.DataFrame, reviewed_codes: Any) -> Dict[str, pd.DataFrame]:
    completed = ~games.has_resignation & ~games.has_expiration
    masks = {
        "completed": completed,
        "resigned": games.has_resignation,
        "resigned_no_expiration": games.has_resignation & ~games.has_expiration,
        "all_processed": pd.Series(True, index=games.index),
        "historical_5239": games.batch.eq("5239"),
        "later_6724": games.batch.eq("20220506"),
        "completed_without_review_cases": completed & ~games.game_code.isin(reviewed_codes),
    }
    return {name: games.loc[mask].copy() for name, mask in masks.items()}


def summarize_cards(cards: pd.DataFrame, kind: str, games: pd.DataFrame, cohort: str) -> pd.DataFrame:
    """Include every catalog category; zero-use win rates and intervals remain missing."""
    uses = cards.loc[cards.game_code.isin(games.game_code) & cards.card_name.ne(EMPTY_CARD)].copy()
    require_unique(uses, ["game_code", "card_name"], kind + " uses")
    if not uses.card_name.isin(CATALOGS[kind]).all():
        raise ValueError("Unknown card in statistics input")
    counts = uses.groupby("card_name").agg(usage_count=("is_win", "size"), wins=("is_win", "sum"),
                                           users_count=("username", "nunique")).to_dict("index")
    result = []
    for card in CATALOGS[kind].values():
        row = counts.get(card.name, {"usage_count": 0, "wins": 0, "users_count": 0})
        n, wins = int(row["usage_count"]), int(row["wins"])
        low, high = wilson_interval(wins, n)
        result.append({
            "cohort": cohort, "kind": kind, "card_name": card.name, "card_id": card.identifier,
            "age": AGES[card.age], "age_index": card.age, "cohort_games": len(games),
            "cohort_player_rows": len(games) * 2, "usage_count": n, "wins": wins, "losses": n - wins,
            "users_count": int(row["users_count"]),
            "selection_rate": n / len(games) if len(games) else math.nan,
            "player_usage_rate": n / (len(games) * 2) if len(games) else math.nan,
            "win_rate": wins / n if n else math.nan, "wilson_low": low, "wilson_high": high,
        })
    return pd.DataFrame(result)


def leader_coverage(slots: pd.DataFrame, games: pd.DataFrame, cohort: str) -> pd.DataFrame:
    rows = slots.loc[slots.game_code.isin(games.game_code)]
    result = []
    for age_index, age in enumerate(AGES):
        subset = rows.loc[rows.age.eq(age)]
        missing = subset.card_name.eq(EMPTY_CARD)
        absent = subset.loc[missing]
        n = len(subset)
        result.append({"cohort": cohort, "age": age, "age_index": age_index,
                       "cohort_games": len(games), "player_slots": n,
                       "present_slots": n - len(absent), "absent_slots": len(absent),
                       "present_rate": (n - len(absent)) / n if n else math.nan,
                       "absent_wins": int(absent.is_win.sum()),
                       "absent_losses": int((~absent.is_win).sum())})
    return pd.DataFrame(result)


def sensitivity_table(metrics: pd.DataFrame) -> pd.DataFrame:
    parts = []
    comparisons = (("completed", "all_processed"), ("completed", "resigned"),
                   ("completed", "completed_without_review_cases"),
                   ("resigned", "resigned_no_expiration"), ("historical_5239", "later_6724"))
    fields = ["kind", "card_id", "card_name", "age", "usage_count", "win_rate", "selection_rate"]
    for baseline, comparison in comparisons:
        left = metrics.loc[metrics.cohort.eq(baseline), fields]
        right = metrics.loc[metrics.cohort.eq(comparison), fields]
        joined = left.merge(right, on=["kind", "card_id", "card_name", "age"],
                            validate="one_to_one", suffixes=("_baseline", "_comparison"))
        joined.insert(0, "comparison_cohort", comparison)
        joined.insert(0, "baseline_cohort", baseline)
        joined["win_rate_delta_pp"] = (joined.win_rate_comparison - joined.win_rate_baseline) * 100
        joined["selection_rate_delta_pp"] = (joined.selection_rate_comparison - joined.selection_rate_baseline) * 100
        parts.append(joined)
    return pd.concat(parts, ignore_index=True)


def build_statistics(prepared: Path) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    tables = load_prepared(prepared)
    cohorts = select_cohorts(tables["games"], tables["quality_findings"].game_code.unique())
    metrics, coverage, cohort_rows = [], [], []
    for name, games in cohorts.items():
        for kind, source in (("leader", "leader_slots"), ("wonder", "wonders")):
            metrics.append(summarize_cards(tables[source], kind, games, name))
        coverage.append(leader_coverage(tables["leader_slots"], games, name))
        players = tables["players"].loc[tables["players"].game_code.isin(games.game_code)]
        cohort_rows.append({"cohort": name, "games": len(games), "player_rows": len(players),
                            "unique_usernames": players.username.nunique(),
                            "games_with_resignation": int(games.has_resignation.sum()),
                            "games_with_expiration": int(games.has_expiration.sum()),
                            "pending_review_games": int(games.game_code.isin(tables["quality_findings"].game_code).sum()),
                            "definition": COHORT_DESCRIPTIONS[name]})
    combined = pd.concat(metrics, ignore_index=True)
    result = {"card_statistics": combined, "leader_coverage": pd.concat(coverage, ignore_index=True),
              "cohorts": pd.DataFrame(cohort_rows), "sensitivity": sensitivity_table(combined)}
    report = {
        "schema_version": 1, "origin": "current_python_automation_of_historical_excel_statistics",
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "primary_cohort": "completed", "cohort_games": {name: len(games) for name, games in cohorts.items()},
        "card_categories": {"leader": len(CATALOGS["leader"]), "wonder": len(CATALOGS["wonder"])},
        "table_rows": {name: len(frame) for name, frame in result.items()},
        "selection_rate_definition": "Card uses / cohort games; not player rows or estimated card availability",
        "win_rate_definition": "Winning uses / all uses of that card in the cohort",
        "wilson_z": 1.96,
        "interpretation": "Descriptive observed associations. Repeated players, other card choices, "
                          "game state and card availability are not controlled; Wilson intervals "
                          "are nominal binomial summaries without dependence or multiple-comparison adjustment.",
        "prepared_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted(Path(prepared).glob("*.csv"))},
    }
    report["prepared_sha256"]["reconciliation.json"] = hashlib.sha256(
        (Path(prepared) / "reconciliation.json").read_bytes()).hexdigest()
    return result, report


def analyze_archive(
    prepared: Path, data_root: Path, output: Path, charts: bool = False, font: Any = None
) -> Dict[str, Any]:
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty statistics output directory")
    tables, report = build_statistics(prepared)
    from .statistics_reference import compare_statistics_reference

    comparison, summary = compare_statistics_reference(data_root, tables)
    tables["historical_comparison"] = comparison
    report["historical_excel_comparison"] = summary
    report["table_rows"]["historical_comparison"] = len(comparison)
    if summary["mismatched_values"]:
        raise ValueError("Statistics disagree with saved historical Excel values")
    from .reporting import write_statistics_report

    if charts:
        # Resolve dependencies and font before creating output files.
        from .reporting import chart_font
        from matplotlib import __version__ as matplotlib_version

        resolved_font = chart_font(font)
        report["plotting"] = {"matplotlib_version": matplotlib_version,
                              "font_family": resolved_font.get_name(),
                              "font_file": Path(resolved_font.get_file()).name}
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output / (name + ".csv"), index=False, encoding="utf-8-sig", lineterminator="\n")
    report["figures"] = []
    if charts:
        from .reporting import create_figures

        report["figures"] = create_figures(tables["card_statistics"], output, font)
    write_statistics_report(tables, report, output / "report.md")
    (output / "analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
