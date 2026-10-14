"""Readable reports and optional static figures for the descriptive analysis."""
import math
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .catalog import CATALOGS
from .statistics import AGES


def chart_font(font: Any = None) -> Any:
    """Resolve a font covering the preserved Chinese card names before plotting."""
    from matplotlib import font_manager
    from matplotlib.ft2font import FT2Font

    required = {ord(char) for catalog in CATALOGS.values() for name in catalog
                for char in name if ord(char) > 127}
    if font:
        candidates = [str(Path(font))]
    else:
        candidates = []
        for family in ("Noto Sans CJK SC", "Microsoft YaHei", "Arial Unicode MS",
                       "SimHei", "PingFang SC", "Heiti SC"):
            try:
                candidates.append(font_manager.findfont(family, fallback_to_default=False))
            except ValueError:
                continue
    for candidate in candidates:
        if Path(candidate).is_file() and required.issubset(FT2Font(candidate).get_charmap()):
            return font_manager.FontProperties(fname=candidate)
    raise ValueError("A font covering Chinese card names is required; supply --font /path/to/font")


def create_figures(metrics: pd.DataFrame, output: Path, font: Any = None) -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    label_font = chart_font(font)
    primary = metrics.loc[metrics.cohort.eq("completed")]
    games = int(primary.cohort_games.iloc[0])
    colors = {"leader": "#2563a6", "wonder": "#188574"}
    filenames = []

    def style_axis(axis: Any) -> None:
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
        axis.xaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(axis="x", alpha=0.18)
        axis.set_axisbelow(True)

    def save(figure: Any, stem: str) -> None:
        for extension in ("png", "svg"):
            filename = stem + "." + extension
            figure.savefig(Path(output) / filename, dpi=160, facecolor="white")
            filenames.append(filename)
        plt.close(figure)

    with plt.rc_context({"font.size": 11, "svg.fonttype": "path"}):
        for kind, title in (("leader", "Leaders"), ("wonder", "Wonders")):
            figure, axes = plt.subplots(2, 2, figsize=(16, 12))
            rows = primary.loc[primary.kind.eq(kind)]
            observed = rows.loc[rows.usage_count.gt(0)]
            lower = max(0, math.floor((float(observed.wilson_low.min()) - 0.025) * 20) / 20)
            upper = min(1, math.ceil((float(observed.wilson_high.max()) + 0.025) * 20) / 20)
            for age, axis in zip(AGES, axes.flat):
                data = rows.loc[rows.age.eq(age)].sort_values(
                    ["win_rate", "card_id"], ascending=[False, True], na_position="last")
                valid = data.usage_count.gt(0)
                y = list(range(len(data)))
                axis.errorbar(data.loc[valid, "win_rate"], [i for i, ok in enumerate(valid) if ok],
                              xerr=[data.loc[valid, "win_rate"] - data.loc[valid, "wilson_low"],
                                    data.loc[valid, "wilson_high"] - data.loc[valid, "win_rate"]],
                              fmt="o", color=colors[kind], ecolor=colors[kind],
                              markersize=5, elinewidth=1.5, capsize=3)
                axis.set_yticks(y, ["{}  (n={:,})".format(row.card_name, row.usage_count)
                                   for row in data.itertuples()], fontproperties=label_font)
                axis.invert_yaxis()
                axis.axvline(0.5, color="#808080", linewidth=1, linestyle="--")
                axis.set_xlim(lower, upper)
                axis.set_title("Age " + age, loc="left", fontweight="bold")
                axis.set_xlabel("Observed win rate")
                style_axis(axis)
            figure.suptitle("{}: observed win rates by age".format(title), fontsize=20, y=0.98)
            figure.text(0.5, 0.938, "Completed population: {:,} games; no resignation or expiration flags".format(games),
                        ha="center", color="#4b5563")
            figure.text(0.5, 0.018,
                        "Points: winning uses / card uses. Bars: nominal 95% Wilson intervals. n: card uses.\n"
                        "Descriptive associations; repeated players and game context are not adjusted.",
                        ha="center", fontsize=10, color="#4b5563")
            figure.tight_layout(rect=(0.025, 0.065, 0.985, 0.92), h_pad=3, w_pad=4)
            save(figure, kind + "s_completed_win_rates")

        figure, axes = plt.subplots(2, 4, figsize=(22, 13))
        selection_upper = min(1, math.ceil((float(primary.selection_rate.max()) + 0.04) * 10) / 10)
        for row_index, kind in enumerate(("leader", "wonder")):
            for column_index, age in enumerate(AGES):
                axis = axes[row_index, column_index]
                data = primary.loc[primary.kind.eq(kind) & primary.age.eq(age)].sort_values(
                    ["selection_rate", "card_id"], ascending=[False, True])
                y = list(range(len(data)))
                axis.barh(y, data.selection_rate, color=colors[kind], height=0.65)
                axis.set_yticks(y, data.card_name, fontproperties=label_font)
                axis.invert_yaxis()
                axis.set_xlim(0, selection_upper)
                for index, value in enumerate(data.selection_rate):
                    axis.text(value + 0.01, index, "{:.1%}".format(value), va="center", fontsize=9)
                axis.set_title("{} / Age {}".format(kind.capitalize(), age), loc="left", fontweight="bold")
                axis.set_xlabel("Games using the card / cohort games")
                style_axis(axis)
        figure.suptitle("Card selection rates by age", fontsize=20, y=0.98)
        figure.text(0.5, 0.94, "Completed population: {:,} games; denominator is games, not player rows".format(games),
                    ha="center", color="#4b5563")
        figure.text(0.5, 0.025,
                    "Within-game uniqueness is validated. Rates do not estimate availability-adjusted pick probability.\n"
                    "Absent leader slots are excluded from card categories and reported separately.",
                    ha="center", fontsize=10, color="#4b5563")
        figure.tight_layout(rect=(0.02, 0.065, 0.985, 0.925), h_pad=3, w_pad=3)
        save(figure, "completed_selection_rates")
    return filenames


def _percent(value: float) -> str:
    return "not observed" if pd.isna(value) else "{:.2%}".format(value)


def write_statistics_report(tables: Dict[str, pd.DataFrame], report: Dict[str, Any], path: Path) -> None:
    """Generate a self-contained summary alongside the complete machine-readable tables."""
    metrics = tables["card_statistics"]
    primary = metrics.loc[metrics.cohort.eq("completed")]
    historical = report["historical_excel_comparison"]
    lines = [
        "# Through the Ages: descriptive analysis", "",
        "This report automates the statistical part of a historical personal project. "
        "The original workflow used manual Excel import and formulas; this Python report is current refactoring.", "",
        "## Populations", "",
        "The primary population contains **{:,} games** with neither resignation nor expiration flags. "
        "The supplied canonical archive has **{:,} distinct games**. The views below overlap; their counts must not be added.".format(
            report["cohort_games"]["completed"], report["cohort_games"]["all_processed"]), "",
        "| Population | Games | Unique usernames | Expiration-flagged games | Pending review games |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in tables["cohorts"].itertuples():
        lines.append("| {} | {:,} | {:,} | {:,} | {:,} |".format(
            row.cohort, row.games, row.unique_usernames, row.games_with_expiration, row.pending_review_games))
    lines += ["", "Resigned games include 17 games also carrying an expiration flag. "
              "Flags are preserved even when they belong to the winning player. "
              "Three age-order review cases remain pending; exclusion is a sensitivity view, not an assertion of recognition error.", "",
              "## Metric definitions", "",
              "- **Selection rate:** card uses / population games. Each card can occur at most once in a game; this is validated. "
              "It is not divided by player rows or estimated card availability.",
              "- **Player usage rate:** card uses / (2 × population games), provided separately in the CSV.",
              "- **Observed win rate:** winning uses / all uses of that card. Counts, wins, losses, and unique usernames are exported.",
              "- **Intervals:** nominal 95% Wilson binomial intervals, z = 1.96. Zero-use cards have no estimated win rate or interval.",
              "- **Absent leaders:** the four era-specific ‘无’ placeholders are retained for coverage and historical comparison, "
              "and excluded from the 48 leader categories.", "",
              "The interval calculation follows the [NIST Wilson method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). "
              "Repeated players, game state, other card choices, and card availability are not controlled. "
              "Intervals do not adjust for dependence or multiple comparisons. These are descriptive associations, not causal estimates of card strength.", "",
              "## Primary-population examples", "",
              "The table shows the highest observed win rate and most used card within each kind and age. "
              "All 80 categories, including sample sizes and intervals, are in [card_statistics.csv](card_statistics.csv).", "",
              "| Kind | Age | Highest observed win rate | Uses | Win rate (Wilson interval) | Most used card | Selection rate |",
              "| --- | --- | --- | ---: | --- | --- | ---: |"]
    for kind in ("leader", "wonder"):
        for age in AGES:
            subset = primary.loc[primary.kind.eq(kind) & primary.age.eq(age)]
            top = subset.sort_values(["win_rate", "card_id"], ascending=[False, True]).iloc[0]
            used = subset.sort_values(["usage_count", "card_id"], ascending=[False, True]).iloc[0]
            lines.append("| {} | {} | {} | {:,} | {} ({}–{}) | {} | {} |".format(
                kind, age, top.card_name, top.usage_count, _percent(top.win_rate),
                _percent(top.wilson_low), _percent(top.wilson_high), used.card_name, _percent(used.selection_rate)))
    lines += ["", "## Leader coverage", "",
              "Absent slots describe the recorded result; an absent slot alone does not establish a recognition failure.", "",
              "| Age | Completed absent slots | Completed absent share of player slots | Resigned absent slots | Resigned absent share |",
              "| --- | ---: | ---: | ---: | ---: |"]
    coverage = tables["leader_coverage"].set_index(["cohort", "age"])
    for age in AGES:
        completed, resigned = coverage.loc[("completed", age)], coverage.loc[("resigned", age)]
        lines.append("| {} | {:,} | {} | {:,} | {} |".format(
            age, int(completed.absent_slots), _percent(1 - completed.present_rate),
            int(resigned.absent_slots), _percent(1 - resigned.present_rate)))
    lines += ["", "## Population sensitivity", "",
              "Deltas are **comparison minus baseline**, in percentage points (pp). "
              "The table shows the largest absolute win-rate change across the 80 cards for each comparison; "
              "this selection is descriptive, not a significance test. See [sensitivity.csv](sensitivity.csv) for every card.", "",
              "| Baseline → comparison | Card | Baseline uses | Comparison uses | Win-rate delta (pp) |",
              "| --- | --- | ---: | ---: | ---: |"]
    for (baseline, comparison), group in tables["sensitivity"].groupby(
            ["baseline_cohort", "comparison_cohort"], sort=False):
        valid = group.dropna(subset=["win_rate_delta_pp"])
        if valid.empty:
            continue
        row = valid.loc[valid.win_rate_delta_pp.abs().idxmax()]
        lines.append("| {} → {} | {} | {:,} | {:,} | {:+.3f} |".format(
            baseline, comparison, row.card_name, row.usage_count_baseline,
            row.usage_count_comparison, row.win_rate_delta_pp))
    lines += ["", "## Historical Excel verification", "",
              "Python independently recomputed **{} saved values** across **{} rows** "
              "(80 card rows and four absent-leader rows) in the 5,239-game workbook: **{} mismatches**. "
              "COUNTIF formula layouts and game denominators were checked. "
              "The workbook was read unchanged, not recalculated in native Excel.".format(
                  historical["compared_values"], historical["compared_rows"], historical["mismatched_values"]), "",
              "The historical score is `Wilson lower bound / historical scale × 50`. "
              "The scale is 0.4656 for leaders; wonder scales are 0.471, 0.4688, 0.4646, and 0.4645 for ages A, I, II, III. "
              "This original scaled score is preserved only in the comparison table, without treating its constants as a calibrated strength model. "
              "Rates match within 1e-12 and scores within 1e-8 absolute tolerance.", "",
              "See [historical_comparison.csv](historical_comparison.csv) for source cell addresses and differences. "
              "Input hashes, versions, population counts, and figure names are recorded in [analysis.json](analysis.json).", ""]
    if report["figures"]:
        lines += ["## Figures", ""]
        for filename in report["figures"]:
            if filename.endswith(".png"):
                lines += ["![{}]({})".format(filename[:-4].replace("_", " "), filename), ""]
        lines += ["Each figure is also exported as SVG for publication.", ""]
    lines += ["## Files", "",
              "- [cohorts.csv](cohorts.csv): explicit population counts and definitions.",
              "- [card_statistics.csv](card_statistics.csv): 80 cards × 7 population views = 560 rows.",
              "- [leader_coverage.csv](leader_coverage.csv): four leader eras × 7 views = 28 rows.",
              "- [sensitivity.csv](sensitivity.csv): 80 cards × 5 comparisons = 400 rows.",
              "- [historical_comparison.csv](historical_comparison.csv): 84 original Excel rows and 252 value checks.",
              "- [analysis.json](analysis.json): provenance and verification metadata.", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
