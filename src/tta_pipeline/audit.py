"""Audit historical batches and avoid counting the 900/4339 subsets twice."""
import json
from pathlib import Path
from typing import Any, Dict

from .catalog import leaders_by_age
from .records import pair_by_code, read_leader_matrix, read_records
from .validation import check_cards


def audit_archive(data_root: Path) -> Dict[str, Any]:
    data_root = Path(data_root)
    manifest = json.loads((data_root / "datasets.json").read_text(encoding="utf-8"))
    batches = {}
    code_sets = {}
    findings = []
    for batch, spec in manifest["batches"].items():
        directory = data_root / "historical" / batch
        matrix = read_leader_matrix(directory / spec["leaders_matrix"])
        codes = set(matrix)
        if len(codes) != spec["expected_games"]:
            raise ValueError("{}: expected {} games, got {}".format(
                batch, spec["expected_games"], len(codes)))
        code_sets[batch] = codes
        issue_count = 0
        for kind in ("leader", "wonder"):
            plural = "leaders" if kind == "leader" else "wonders"
            if plural + "_top" in spec:
                top = read_records(directory / spec[plural + "_top"])
                bottom = read_records(directory / spec[plural + "_bottom"])
                if set(top) != codes or set(bottom) != codes:
                    raise ValueError("{}: {} game codes differ from the leader matrix".format(
                        batch, plural))
                pairs = pair_by_code(top, bottom)
            else:
                pairs = ((code, sides[0], sides[1]) for code, sides in matrix.items())
            for code, top_names, bottom_names in pairs:
                for issue in check_cards(code, top_names, bottom_names, kind):
                    findings.append(dict(issue.to_dict(), batch=batch))
                    issue_count += 1
                if kind == "leader" and "leaders_top" in spec:
                    expected = (leaders_by_age(top_names), leaders_by_age(bottom_names))
                    if expected != matrix[code]:
                        raise ValueError(
                            "{}: {} age-padded leaders do not match".format(batch, code))
        batches[batch] = {"role": spec["role"], "games": len(codes), "findings": issue_count}
    if code_sets["900"] & code_sets["4339"]:
        raise ValueError("The 900 and 4339 batches overlap")
    if code_sets["900"] | code_sets["4339"] != code_sets["5239"]:
        raise ValueError("The historical components do not equal the 5239 aggregate")
    canonical = manifest["canonical_batches"]
    total = sum(len(code_sets[batch]) for batch in canonical)
    unique = set().union(*(code_sets[batch] for batch in canonical))
    if total != len(unique):
        raise ValueError("Canonical batches contain duplicate games")
    return {"canonical_batches": canonical, "unique_games": len(unique),
            "batches": batches, "findings": findings,
            "affected_unique_games": len({f["game_code"] for f in findings})}

