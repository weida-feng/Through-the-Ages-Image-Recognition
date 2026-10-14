"""Explicit orchestration of screenshot extraction, recognition, and review rules."""
from pathlib import Path
from typing import Any, Dict

from .records import validate_game_code
from .validation import check_cards


def recognize_screenshot(
    screenshot: Path, game_code: str, models: Path, output: Path
) -> Dict[str, Any]:
    from .recognition import CardPredictor

    validate_game_code(game_code)
    # Validate the environment before creating output files.
    predictors = {kind: CardPredictor.load(models, kind) for kind in ("leader", "wonder")}
    return recognize_with_predictors(screenshot, game_code, predictors, output)


def recognize_with_predictors(
    screenshot: Path, game_code: str, predictors: Dict[str, Any], output: Path
) -> Dict[str, Any]:
    """Run one screenshot, allowing a batch to reuse already validated model pairs."""
    from .cropping import extract_crops, read_grayscale, write_crops

    validate_game_code(game_code)
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty recognition output directory")
    if set(predictors) != {"leader", "wonder"} or any(
            model.kind != kind for kind, model in predictors.items()):
        raise ValueError("Recognition requires matching leader and wonder predictors")
    crops = extract_crops(read_grayscale(screenshot))
    paths = write_crops(crops, Path(output) / "crops")
    values = {}
    for prefix, filenames in paths.items():
        kind = "leader" if prefix.startswith("p") else "wonder"
        values[prefix] = tuple(predictors[kind].predict(path) for path in filenames)
    findings = []
    for kind, prefix in (("leader", "p"), ("wonder", "w")):
        findings.extend(check_cards(game_code, values[prefix + "1"], values[prefix + "2"], kind))
    return {"game_code": game_code, "leaders_top": values["p1"], "leaders_bottom": values["p2"],
            "wonders_top": values["w1"], "wonders_bottom": values["w2"],
            "findings": [finding.to_dict() for finding in findings],
            "note": "Raw recognition; historical manual corrections are not applied automatically."}

