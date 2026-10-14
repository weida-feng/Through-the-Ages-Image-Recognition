"""Historical time-line detector for the preserved 3840 x 2160 game interface."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np


@dataclass(frozen=True)
class ScanRegion:
    row: int
    y_start: int
    height: int
    x_offset: int
    width: int
    stop: int
    falling_edge: bool


REGIONS = {
    "p1": ScanRegion(1377, 1223, 144, -77, 144, 3100, True),
    "p2": ScanRegion(1835, 1686, 144, -77, 144, 3100, True),
    "w1": ScanRegion(1163, 1161, 64, 0, 120, 3020, False),
    "w2": ScanRegion(1625, 1629, 64, 0, 120, 3020, False),
}
SCREEN_SHAPE = (2160, 3840)


def read_grayscale(path: Path) -> np.ndarray:
    """Read with the same OpenCV grayscale conversion as the original notebooks."""
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("Cannot read image: {}".format(path))
    return image


def scan_region(image: np.ndarray, region: ScanRegion) -> List[np.ndarray]:
    crops = []
    x = 464
    while x < region.stop:
        right = int(image[region.row, x:x + 10].sum(dtype=np.int64))
        left = int(image[region.row, x - 10:x].sum(dtype=np.int64))
        found = (
            (right < 400 and left > 500) if region.falling_edge
            else (right > 500 and left < 300)
        )
        if found:
            x_start = x + region.x_offset
            crops.append(image[region.y_start:region.y_start + region.height,
                               x_start:x_start + region.width].copy())
            x += 50
        else:
            x += 1
    return crops


def extract_crops(image: np.ndarray) -> Dict[str, List[np.ndarray]]:
    if image.ndim != 2 or tuple(image.shape) != SCREEN_SHAPE:
        raise ValueError("Historical layout requires a 3840 x 2160 grayscale screenshot")
    return {prefix: scan_region(image, region) for prefix, region in REGIONS.items()}


def write_crops(crops: Dict[str, List[np.ndarray]], directory: Path) -> Dict[str, List[Path]]:
    """Write JPEGs before prediction, preserving the historical image round trip."""
    import cv2

    directory = Path(directory)
    existing = [p for prefix in REGIONS for p in directory.glob(prefix + "_*.jpg")]
    if existing:
        raise FileExistsError(
            "Crop output already contains images; choose a fresh directory: {}".format(directory))
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for prefix, images in crops.items():
        paths[prefix] = []
        for index, image in enumerate(images):
            path = directory / "{}_{}.jpg".format(prefix, index)
            if not cv2.imwrite(str(path), image):
                raise OSError("Cannot write crop: {}".format(path))
            paths[prefix].append(path)
    return paths


def feature_vector(image: np.ndarray, kind: str) -> np.ndarray:
    """Apply the preprocessing required by the saved model dimensions."""
    if image.ndim != 2:
        raise ValueError("Expected a grayscale card image")
    if kind == "leader":
        if tuple(image.shape) != (144, 144):
            raise ValueError("Expected a 144 x 144 leader crop")
        image = image[48:96, 48:96]
    elif kind == "wonder":
        if tuple(image.shape) != (64, 120):
            raise ValueError("Expected a 64 x 120 wonder crop")
    else:
        raise ValueError("Unknown card kind: {!r}".format(kind))
    return image.reshape(1, -1)

