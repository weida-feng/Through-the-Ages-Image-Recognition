"""Original PCA/KNN training method, organized into Python functions."""
import json
from pathlib import Path
import platform
from typing import Any, Dict, List, Tuple

from .catalog import EMPTY_CARD, card_info
from .records import read_records


def training_examples(labels: Path, image_root: Path, kind: str) -> List[Tuple[Path, str]]:
    """Return paired paths/labels and fail clearly when the full archive is absent."""
    examples = []
    for code, row in read_records(labels).items():
        if kind == "leader":
            if len(row.values) != 10:
                raise ValueError("Leader labels require eight age fields and two crop counts")
            top = tuple(name for name in row.values[:4] if name != EMPTY_CARD)
            bottom = tuple(name for name in row.values[4:8] if name != EMPTY_CARD)
            if (len(top), len(bottom)) != (int(row.values[8]), int(row.values[9])):
                raise ValueError("Leader counts do not match labels for {}".format(code))
            for prefix, names in (("p1", top), ("p2", bottom)):
                for index, name in enumerate(names):
                    path = Path(image_root) / code / "{}_{}.jpg".format(prefix, index)
                    examples.append((path, name))
        elif kind == "wonder":
            paths = []
            for prefix in ("w1", "w2"):
                for index in range(10):
                    path = Path(image_root) / code / "{}_{}.jpg".format(prefix, index)
                    if not path.exists():
                        break
                    paths.append(path)
            if len(paths) != len(row.values):
                raise FileNotFoundError("{} has {} labels but {} wonder crops; "
                                        "the full 900-game image archive is needed".format(
                                            code, len(row.values), len(paths)))
            examples.extend(zip(paths, row.values))
        else:
            raise ValueError("Unknown card kind: {!r}".format(kind))
    missing = [path for path, _ in examples if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing {} training crops, including {}. "
            "The supplied project contains samples only.".format(len(missing), missing[0]))
    for _, name in examples:
        card_info(name, kind)
    return examples


def train_model(labels: Path, image_root: Path, output: Path, kind: str) -> Dict[str, Any]:
    """Fit the historical PCA+K=3 recipe; this does not measure held-out accuracy."""
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(
            "Choose an empty training output directory; archived models are preserved")
    examples = training_examples(labels, image_root, kind)
    import joblib
    import numpy as np
    import sklearn
    from sklearn.decomposition import PCA
    from sklearn.neighbors import KNeighborsClassifier

    from .cropping import feature_vector, read_grayscale

    features = np.vstack([feature_vector(read_grayscale(path), kind) for path, _ in examples])
    names = [name for _, name in examples]
    pca = PCA(n_components=0.95, whiten=True, random_state=0, svd_solver="full").fit(features)
    classifier = KNeighborsClassifier(n_neighbors=3, weights="uniform", n_jobs=-1)
    classifier.fit(pca.transform(features), names)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(pca, output / "pca.pkl")
    joblib.dump(classifier, output / "classifier.pkl")
    shape = [48, 48] if kind == "leader" else [64, 120]
    metadata = {
        "origin": "refactored_original_training",
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        kind: {
            "pca_file": "pca.pkl",
            "classifier_file": "classifier.pkl",
            "input_shape": shape,
            "components": int(pca.n_components_),
            "classes": len(classifier.classes_),
            "training_samples": len(examples),
        },
        "note": (
            "Original PCA/KNN method confirmed by the author; "
            "the shared leader/wonder notebook workflow is now organized as Python functions."
        ),
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata

