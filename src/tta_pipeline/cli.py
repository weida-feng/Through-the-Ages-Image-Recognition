"""Explicit entry points for archive review and optional vision tasks."""
import argparse
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence


def write_json(value: Any, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review the historical TTA recognition project")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Count and validate the historical text results")
    audit.add_argument("--data-root", type=Path, default=Path("data"))
    audit.add_argument("--output", type=Path, help="Optional full JSON report")
    recognize = commands.add_parser(
        "recognize", help="Extract and recognize one preserved screenshot")
    recognize.add_argument("screenshot", type=Path)
    recognize.add_argument("--game-code", required=True)
    recognize.add_argument("--models", type=Path, default=Path("assets/models"))
    recognize.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-examples", help="Run all preserved screenshots and report historical agreement")
    verify.add_argument("--data-root", type=Path, default=Path("data"))
    verify.add_argument("--models", type=Path, default=Path("assets/models"))
    verify.add_argument("--output", type=Path, required=True)
    train = commands.add_parser(
        "train", help="Original training method; requires the full labeled image archive")
    train.add_argument("--kind", choices=("leader", "wonder"), required=True)
    train.add_argument("--labels", type=Path, required=True)
    train.add_argument("--images", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    prepare = commands.add_parser("prepare", help="Join historical records and players with pandas")
    prepare.add_argument("--data-root", type=Path, default=Path("data"))
    prepare.add_argument("--output", type=Path, required=True)
    analyze = commands.add_parser("analyze", help="Calculate card statistics and verify old Excel results")
    analyze.add_argument("--prepared", type=Path, default=Path("results/prepared"))
    analyze.add_argument("--data-root", type=Path, default=Path("data"))
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--charts", action="store_true", help="Also export PNG and SVG figures")
    analyze.add_argument("--font", type=Path, help="Optional Chinese font file for card labels")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "audit":
            from .audit import audit_archive

            result = audit_archive(args.data_root)
            if args.output:
                write_json(result, args.output)
            summary = {key: value for key, value in result.items() if key != "findings"}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print("Review findings: {} across {} games".format(
                len(result["findings"]), result["affected_unique_games"]))
        elif args.command == "recognize":
            from .pipeline import recognize_screenshot

            result = recognize_screenshot(args.screenshot, args.game_code, args.models, args.output)
            write_json(result, args.output / "recognition.json")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "train":
            from .training import train_model

            result = train_model(args.labels, args.images, args.output, args.kind)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "verify-examples":
            from .sample_verification import verify_examples

            result = verify_examples(args.data_root, args.models, args.output)
            summary = {key: value for key, value in result.items()
                       if key not in ("input_sha256", "model_sha256", "reference_sha256")}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        elif args.command == "prepare":
            from .preparation import prepare_archive

            result = prepare_archive(args.data_root, args.output)
            summary = {key: value for key, value in result.items() if key != "input_sha256"}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        elif args.command == "analyze":
            from .statistics import analyze_archive

            result = analyze_archive(args.prepared, args.data_root, args.output, args.charts, args.font)
            summary = {key: value for key, value in result.items() if key != "prepared_sha256"}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    return 0

