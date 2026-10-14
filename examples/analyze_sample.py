"""Validate and summarize the public sample with the project's analysis functions."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import pandas as pd

from tta_pipeline.statistics import leader_coverage, load_prepared, summarize_cards

ROOT = Path(__file__).resolve().parents[1]


def analyze_sample(data, output):
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty demo output directory")
    tables = load_prepared(data)
    games = tables["games"]
    completed = ~games.has_resignation & ~games.has_expiration
    populations = {
        "demo_completed": games.loc[completed],
        "demo_resigned": games.loc[games.has_resignation],
        "demo_all": games,
    }
    metrics, coverage = [], []
    for name, cohort in populations.items():
        for kind, source in (("leader", "leader_slots"), ("wonder", "wonders")):
            metrics.append(summarize_cards(tables[source], kind, cohort, name))
        coverage.append(leader_coverage(tables["leader_slots"], cohort, name))
    metrics = pd.concat(metrics, ignore_index=True)
    coverage = pd.concat(coverage, ignore_index=True)
    metadata = {
        "scope": "public_20_game_demo", "sample_is_random": False,
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "games": len(games), "players": len(tables["players"]),
        "population_games": {name: len(cohort) for name, cohort in populations.items()},
        "card_categories": {"leader": 48, "wonder": 32},
        "metric_rows": len(metrics), "leader_coverage_rows": len(coverage),
        "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(Path(data).glob("*.csv"))},
        "interpretation": "Sample-only statistics from a curated 20-game subset; not the published full-archive estimates",
    }
    output.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output / "sample_card_statistics.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(output / "sample_leader_coverage.csv", index=False, encoding="utf-8-sig")
    (output / "sample_analysis.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/demo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze_sample(args.data, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
