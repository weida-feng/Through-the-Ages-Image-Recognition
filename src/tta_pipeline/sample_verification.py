"""Exercise preserved screenshots and record agreement without inventing ground truth."""
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import sys
import tempfile
from typing import Any, Dict, List, Tuple

from .catalog import EMPTY_CARD
from .records import read_leader_matrix, read_records

PREFIX_FIELDS = {"p1": "leaders_top", "p2": "leaders_bottom",
                 "w1": "wonders_top", "w2": "wonders_bottom"}
CROP_NAME = re.compile(r"^(p[12]|w[12])_(\d+)\.jpg$")


def compare_sequences(actual: Any, expected: Any) -> Dict[str, Any]:
    """Require equal length and order; unequal lists are not truncated by zip."""
    actual, expected = tuple(actual), tuple(expected)
    return {"predicted_count": len(actual), "reference_count": len(expected),
            "matches": actual == expected, "predicted_labels": list(actual),
            "reference_labels": list(expected)}


def sample_inputs(data_root: Path) -> List[Tuple[str, Dict[str, Any], Path]]:
    config = json.loads((Path(data_root) / "examples.json").read_text(encoding="utf-8"))
    root = Path(data_root) / "examples"
    if {path.name for path in root.iterdir() if path.is_dir()} != set(config["groups"]):
        raise ValueError("Example groups differ from data/examples.json")
    result = []
    seen = set()
    saved_crops = 0
    for group, spec in config["groups"].items():
        folders = sorted(path for path in (root / group).iterdir() if path.is_dir())
        if len(folders) != spec["expected_games"]:
            raise ValueError("Example count differs for {}".format(group))
        for folder in folders:
            if folder.name in seen or not (folder / "img.jpg").is_file():
                raise ValueError("Missing screenshot or duplicate example code: {}".format(folder.name))
            seen.add(folder.name)
            saved_crops += sum(bool(CROP_NAME.fullmatch(path.name)) for path in folder.glob("*.jpg"))
            result.append((group, spec, folder))
    if len(result) != config["expected_games"] or saved_crops != config["expected_saved_crops"]:
        raise ValueError("Example screenshot/crop counts differ from manifest")
    return result


def reference_lists(data_root: Path, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = json.loads((Path(data_root) / "datasets.json").read_text(encoding="utf-8"))
    batch = spec["historical_batch"]
    files = manifest["batches"][batch]
    folder = Path(data_root) / "historical" / batch
    leaders = read_leader_matrix(folder / files["leaders_matrix"])
    if spec.get("manual_leader_labels"):
        labels = read_records(Path(data_root) / spec["manual_leader_labels"])
        leaders = {code: (row.values[:4], row.values[4:8]) for code, row in labels.items()}
    references = {"p1": {code: tuple(x for x in pair[0] if x != EMPTY_CARD)
                          for code, pair in leaders.items()},
                  "p2": {code: tuple(x for x in pair[1] if x != EMPTY_CARD)
                          for code, pair in leaders.items()}}
    earlier = {}
    for prefix, side in (("w1", "top"), ("w2", "bottom")):
        references[prefix] = {code: row.values for code, row in
                              read_records(folder / files["wonders_" + side]).items()}
        old_path = spec.get("earlier_wonders_" + side)
        if spec.get("earlier_wonder_batch"):
            old_batch = spec["earlier_wonder_batch"]
            old_path = "historical/{}/{}".format(
                old_batch, manifest["batches"][old_batch]["wonders_" + side])
        if old_path:
            earlier[prefix] = {code: row.values for code, row in
                               read_records(Path(data_root) / old_path).items()}
    return references, earlier


def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def verify_examples(data_root: Path, models: Path, output: Path) -> Dict[str, Any]:
    """Load the four artifacts once, run every example, and preserve all differences."""
    import numpy as np
    from .capture import template_difference
    from .cropping import read_grayscale
    from .pipeline import recognize_with_predictors
    from .recognition import CardPredictor

    data_root, models, output = Path(data_root), Path(models), Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty sample verification output directory")
    inputs = sample_inputs(data_root)
    config = json.loads((data_root / "examples.json").read_text(encoding="utf-8"))
    template_path = data_root / config["empty_wonder_template"]
    empty_template = read_grayscale(template_path)
    empty_threshold = int(config["empty_wonder_difference_threshold"])
    if empty_threshold <= 0:
        raise ValueError("Empty-wonder diagnostic threshold must be positive")
    sources = {}
    for group, spec, _ in inputs:
        if group not in sources:
            sources[group] = reference_lists(data_root, spec)
    predictors = {kind: CardPredictor.load(models, kind) for kind in ("leader", "wonder")}
    package_names = ("numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl", "opencv-python")
    report = {"schema_version": 1, "python_version": platform.python_version(),
              "platform": platform.platform(), "process_architecture": platform.machine(),
              "isolated_virtual_environment": sys.prefix != sys.base_prefix,
              "dependency_versions": {name: version(name) for name in package_names},
              "model_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in sorted(models.glob("*.pkl"))},
              "input_sha256": {str(path.relative_to(data_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for _, _, folder in inputs for path in sorted(folder.glob("*.jpg"))},
              "reference_sha256": {str(path.relative_to(data_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in sorted((data_root / "historical").rglob("*.txt"))},
              "interpretation": "Historical-output agreement and sample integration verification, "
                                "not independent held-out accuracy. Training examples and historical "
                                "manual corrections are explicitly identified. Raw predictions are preserved."}
    report["model_sha256"]["metadata.json"] = hashlib.sha256((models / "metadata.json").read_bytes()).hexdigest()
    report["input_sha256"]["examples.json"] = hashlib.sha256((data_root / "examples.json").read_bytes()).hexdigest()
    report["input_sha256"]["datasets.json"] = hashlib.sha256((data_root / "datasets.json").read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    (output / "predictions").mkdir()
    samples, comparisons, saved_rows, empty_rows = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="generated-crops-", dir=str(output)) as generated:
        for group, spec, folder in inputs:
            code = folder.name
            references, earlier = sources[group]
            expected = {prefix: references[prefix][code] for prefix in PREFIX_FIELDS}
            result = recognize_with_predictors(folder / "img.jpg", code, predictors, Path(generated) / code)
            result["historical_reference_batch"] = spec["historical_batch"]
            result["example_role"] = spec["role"]
            checks, diagnostic_checks, flagged = [], [], []
            for prefix, field in PREFIX_FIELDS.items():
                actual = result[field]
                check = compare_sequences(actual, expected[prefix])
                diagnostic = list(actual)
                if prefix.startswith("w"):
                    diagnostic = []
                    for index, label in enumerate(actual):
                        crop_path = Path(generated) / code / "crops" / (prefix + "_{}.jpg".format(index))
                        difference = template_difference(empty_template, read_grayscale(crop_path))
                        is_candidate = difference < empty_threshold
                        row = {"group": group, "game_code": code, "prefix": prefix,
                               "crop_index": index, "predicted_label": label,
                               "difference_50x50": difference, "template_candidate": is_candidate}
                        empty_rows.append(row)
                        if is_candidate:
                            flagged.append(row)
                        else:
                            diagnostic.append(label)
                diagnostic_match = tuple(diagnostic) == expected[prefix]
                diagnostic_checks.append(diagnostic_match)
                old = earlier.get(prefix, {}).get(code)
                comparisons.append({"group": group, "game_code": code, "prefix": prefix,
                                    "reference_batch": spec["historical_batch"], **check,
                                    "diagnostic_without_template_candidates": diagnostic,
                                    "diagnostic_matches_reference": diagnostic_match,
                                    "earlier_reference_available": old is not None,
                                    "matches_earlier_reference": tuple(actual) == old if old is not None else "",
                                    "earlier_labels": list(old) if old is not None else []})
                checks.append(check["matches"])
                paths = sorted(folder.glob(prefix + "_*.jpg"),
                               key=lambda path: int(CROP_NAME.fullmatch(path.name)[2]))
                comparable = len(paths) == len(expected[prefix])
                pixels_comparable = len(paths) == len(actual)
                for index, path in enumerate(paths):
                    predicted = predictors["leader" if prefix.startswith("p") else "wonder"].predict(path)
                    if pixels_comparable:
                        before = read_grayscale(path)
                        after = read_grayscale(Path(generated) / code / "crops" / (prefix + "_{}.jpg".format(index)))
                        pixels_match = np.array_equal(before, after)
                    else:
                        pixels_match = ""
                    saved_rows.append({"group": group, "game_code": code, "prefix": prefix,
                                       "saved_file": str(path.relative_to(data_root)),
                                       "predicted_label": predicted,
                                       "reference_comparable": comparable,
                                       "reference_label": expected[prefix][index] if comparable else "",
                                       "matches_reference": predicted == expected[prefix][index] if comparable else "",
                                       "regenerated_pixels_comparable": pixels_comparable,
                                       "regenerated_pixels_match": bool(pixels_match) if pixels_comparable else ""})
            samples.append({"group": group, "game_code": code, "role": spec["role"],
                            "reference_batch": spec["historical_batch"],
                            "predicted_leaders": len(result["leaders_top"]) + len(result["leaders_bottom"]),
                            "predicted_wonders": len(result["wonders_top"]) + len(result["wonders_bottom"]),
                            "all_four_lists_match": all(checks), "matching_lists": sum(checks),
                            "empty_wonder_candidates": len(flagged),
                            "diagnostic_matching_lists": sum(diagnostic_checks),
                            "review_findings": len(result["findings"])})
            result["empty_wonder_diagnostic"] = {
                "candidates": flagged, "threshold": empty_threshold,
                "applied_to_raw_predictions": False}
            (output / "predictions" / (code + ".json")).write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report.update({"screenshots_completed": len(samples),
                   "generated_crops": sum(row["predicted_leaders"] + row["predicted_wonders"] for row in samples),
                   "historical_lists_compared": len(comparisons),
                   "historical_lists_matching": sum(row["matches"] for row in comparisons),
                   "screenshots_matching_all_four_lists": sum(row["all_four_lists_match"] for row in samples),
                   "saved_crops_classified": len(saved_rows),
                   "saved_crops_reference_comparable": sum(row["reference_comparable"] for row in saved_rows),
                   "saved_crops_matching_reference": sum(row["matches_reference"] is True for row in saved_rows),
                   "saved_crops_pixels_comparable": sum(row["regenerated_pixels_comparable"] for row in saved_rows),
                   "saved_crops_pixels_matching": sum(row["regenerated_pixels_match"] is True for row in saved_rows)})
    report["empty_wonder_diagnostic"] = {
        "template_file": config["empty_wonder_template"],
        "template_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(),
        "metric": "Sum of absolute grayscale differences over the first 50 x 50 pixels",
        "difference_threshold": empty_threshold,
        "candidate_crops": sum(row["template_candidate"] for row in empty_rows),
        "wonder_crops_compared": len(empty_rows),
        "historical_lists_matching_without_candidates": sum(row["diagnostic_matches_reference"] for row in comparisons),
        "screenshots_matching_without_candidates": sum(row["diagnostic_matching_lists"] == 4 for row in samples),
        "applied_to_raw_predictions": False,
        "origin": "Current diagnostic using the preserved nowonder.jpg and the metric/threshold "
                  "recorded in resigncheck.ipynb. The old notebook was not executed; its cal/cal_div "
                  "naming inconsistency is not treated as a functioning historical cleanup entry point."}
    _write_csv(samples, output / "samples.csv")
    _write_csv(comparisons, output / "historical_comparison.csv")
    _write_csv(saved_rows, output / "saved_crops.csv")
    _write_csv(empty_rows, output / "empty_wonder_candidates.csv")
    (output / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(samples, comparisons, report, output / "report.md")
    return report


def _write_report(samples: Any, comparisons: Any, report: Any, path: Path) -> None:
    lines = ["# Preserved screenshot verification", "",
             "All **{} screenshots** completed the organized crop → PCA → KNN → rule-check flow. "
             "The two model pairs were loaded once for this verification run.".format(report["screenshots_completed"]), "",
             "Python **{}**, process architecture **{}**, operating system **{}**. "
             "The scientific packages were installed in a separate virtual environment.".format(
                 report["python_version"], report["process_architecture"], report["platform"]), "",
             "| Dependency | Version |", "| --- | --- |"]
    lines += ["| {} | {} |".format(name, value) for name, value in report["dependency_versions"].items()]
    lines += ["", "## Results", "",
              "- {} generated crops were classified from the complete screenshots.".format(report["generated_crops"]),
              "- {} / {} historical top/bottom card lists match exactly, including order and count.".format(
                  report["historical_lists_matching"], report["historical_lists_compared"]),
              "- {} / {} screenshots match all four current reference lists.".format(
                  report["screenshots_matching_all_four_lists"], report["screenshots_completed"]),
              "- All {} preserved crop images also loaded and classified; {} / {} count-aligned predictions match the reference labels.".format(
                  report["saved_crops_classified"], report["saved_crops_matching_reference"], report["saved_crops_reference_comparable"]),
              "- {} / {} count-aligned preserved crops have identical decoded pixels after regeneration.".format(
                  report["saved_crops_pixels_matching"], report["saved_crops_pixels_comparable"]), "",
              "These are historical-output agreement checks, **not independent test-set accuracy**. "
              "The 900 group includes training examples; manual leader labels are used there. "
              "Other references are historical recognition results, some with subsequent manual cleanup. "
              "No current reference is substituted into the raw prediction.", "",
              "| Group | Game | Leaders | Wonders | Matching lists / 4 | Review findings |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    lines += ["| {} | {} | {} | {} | {} | {} |".format(
        row["group"], row["game_code"], row["predicted_leaders"], row["predicted_wonders"],
        row["matching_lists"], row["review_findings"]) for row in samples]
    diagnostic = report["empty_wonder_diagnostic"]
    lines += ["", "## Empty-wonder diagnostic", "",
              "The preserved `nowonder.jpg` template identifies **{} candidates among {} wonder crops**, "
              "using the recorded first-50×50 absolute-difference metric and a threshold of {}. "
              "Comparing the lists without those candidates yields **{} / {} matching lists** "
              "and **{} / {} matching screenshots**. This diagnostic does **not** alter raw predictions, "
              "remove any original files, or select exclusions by the predicted card name.".format(
                  diagnostic["candidate_crops"], diagnostic["wonder_crops_compared"],
                  diagnostic["difference_threshold"], diagnostic["historical_lists_matching_without_candidates"],
                  report["historical_lists_compared"], diagnostic["screenshots_matching_without_candidates"],
                  report["screenshots_completed"]), "",
              "The historical cleanup notebook contains the empty-template comparison and a deletion attempt, "
              "but uses `cal` where `cal_div` was defined. It was read as source evidence and not executed. "
              "The comparison here is current diagnostic automation of the recorded method; it does not establish "
              "which cleanup steps were actually run on every historical game. "
              "See [empty_wonder_candidates.csv](empty_wonder_candidates.csv) for every measured crop.", "",
              "## Differences requiring interpretation", "",
              "The table lists every difference between raw screenshot predictions and current references. "
              "Earlier wonder outputs are included where supplied. Agreement with an earlier output is evidence of historical consistency, "
              "not evidence that the earlier output was correct.", "",
              "| Group / game / list | Raw prediction | Current reference | Matches earlier reference |",
              "| --- | --- | --- | --- |"]
    for row in comparisons:
        if not row["matches"]:
            lines.append("| {} / {} / {} | {} | {} | {} |".format(
                row["group"], row["game_code"], row["prefix"],
                ", ".join(row["predicted_labels"]) or "empty",
                ", ".join(row["reference_labels"]) or "empty",
                row["matches_earlier_reference"] if row["earlier_reference_available"] else "unavailable"))
    lines += ["", "Group `5` is the preserved original directory name, mapped explicitly to early 5,239-game references. "
              "It contains saved leader crops only; wonders can still be extracted from its screenshots. "
              "Saved-crop reference and pixel comparisons are skipped when list lengths differ, preventing false index alignment.", "",
              "## Reproduce", "", "```bash",
              "tta-pipeline verify-examples --output results/vision-verification", "```", "",
              "Use the pinned legacy vision environment described in [environment notes](../../docs/environment.md), "
              "and choose an empty output directory. Regenerated JPEG crops are temporary; raw per-game predictions remain in `predictions/`. "
              "Run `tta-pipeline recognize` to keep crops for one screenshot. The original models, screenshots, crops and text results are unchanged.", "",
              "See [samples.csv](samples.csv), [historical_comparison.csv](historical_comparison.csv), "
              "[saved_crops.csv](saved_crops.csv), and [verification.json](verification.json) for complete values, runtime metadata and input hashes.", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
