"""Classify selected historical crops and measure an empty-region diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

from tta_pipeline.capture import template_difference
from tta_pipeline.cropping import read_grayscale
from tta_pipeline.recognition import CardPredictor

ROOT = Path(__file__).resolve().parents[1]


def recognize_crops(output):
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Choose an empty crop-demo output directory")
    config = json.loads((ROOT / "assets/demo/examples.json").read_text(encoding="utf-8"))
    predictors = {kind: CardPredictor.load(ROOT / "assets/models", kind)
                  for kind in ("leader", "wonder")}
    template = read_grayscale(ROOT / "assets/demo" / config["empty_template"])
    results = []
    for example in config["examples"]:
        path = ROOT / "assets/demo" / example["file"]
        predicted = predictors[example["kind"]].predict(path)
        row = dict(example, raw_prediction=predicted,
                   input_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        row["reference_agreement"] = (predicted == example["reference_label"]
                                      if example["reference_label"] is not None else None)
        if example["kind"] == "wonder":
            difference = template_difference(template, read_grayscale(path))
            row["empty_template_difference"] = difference
            row["empty_candidate"] = difference < config["empty_threshold"]
        results.append(row)
    report = {
        "scope": "selected_crop_demo", "python_version": platform.python_version(),
        "examples": results, "empty_threshold": config["empty_threshold"],
        "applied_to_raw_predictions": False,
        "interpretation": "Three historical-reference agreements and one empty-region failure; not held-out accuracy or a full screenshot run",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "crop_predictions.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(recognize_crops(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
