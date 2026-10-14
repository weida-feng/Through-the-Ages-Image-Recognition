"""Load each PCA/KNN pair once and predict preserved Chinese card labels."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import card_info


@dataclass
class CardPredictor:
    kind: str
    pca: Any
    classifier: Any

    @classmethod
    def load(cls, directory: Path, kind: str) -> "CardPredictor":
        import joblib
        import sklearn

        directory = Path(directory)
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        expected_version = metadata["sklearn_version"]
        if sklearn.__version__ != expected_version:
            raise RuntimeError(
                "Models require scikit-learn {}, but this environment has {}. "
                "See docs/environment.md.".format(expected_version, sklearn.__version__))
        if kind not in ("leader", "wonder"):
            raise ValueError("Unknown card kind: {!r}".format(kind))
        spec = metadata[kind]
        pca = joblib.load(directory / spec["pca_file"])
        classifier = joblib.load(directory / spec["classifier_file"])
        if int(pca.n_features_in_) != spec["input_shape"][0] * spec["input_shape"][1]:
            raise ValueError("PCA input size does not match model metadata")
        if pca.components_.shape[0] != classifier.n_features_in_:
            raise ValueError("PCA output size does not match the classifier input")
        if len(classifier.classes_) != spec["classes"]:
            raise ValueError("Classifier class count does not match model metadata")
        for label in classifier.classes_:
            card_info(str(label), kind)
        return cls(kind, pca, classifier)

    def predict(self, path: Path) -> str:
        from .cropping import feature_vector, read_grayscale

        vector = feature_vector(read_grayscale(path), self.kind)
        label = str(self.classifier.predict(self.pca.transform(vector))[0])
        card_info(label, self.kind)
        return label

