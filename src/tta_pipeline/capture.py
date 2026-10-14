"""Consolidated historical Windows mouse macro; never runs at import time."""
from dataclasses import dataclass
from pathlib import Path
import platform
import time

from .records import validate_game_code


@dataclass(frozen=True)
class CaptureSettings:
    end_template: Path
    max_attempts: int = 30
    difference_threshold: int = 5000
    initial_wait_seconds: float = 15
    attempt_wait_seconds: float = 5


def template_difference(template, candidate) -> int:
    """Preserve the original 50 x 50 comparison with signed arithmetic."""
    import numpy as np

    if template.ndim != 2 or candidate.ndim != 2:
        raise ValueError("Template comparison requires grayscale images")
    if min(template.shape) < 50 or min(candidate.shape) < 50:
        raise ValueError("Template comparison requires at least 50 x 50 pixels")
    a = template[:50, :50].astype(np.int32)
    b = candidate[:50, :50].astype(np.int32)
    return int(np.abs(a - b).sum(dtype=np.int64))


def capture_game(game_code: str, output_root: Path, settings: CaptureSettings) -> Path:
    """Explicitly run the archived interface sequence on its original platform."""
    validate_game_code(game_code)
    directory = Path(output_root) / game_code
    screenshot = directory / "img.jpg"
    if screenshot.is_file():
        return screenshot
    if platform.system() != "Windows":
        raise RuntimeError(
            "The archived capture macro uses Windows pydirectinput and fixed UI coordinates")

    import pyautogui as mouse
    import pydirectinput as keyboard
    import pyperclip

    from .cropping import read_grayscale

    if settings.max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    template = read_grayscale(settings.end_template)
    directory.mkdir(parents=True, exist_ok=True)
    pyperclip.copy(game_code)
    mouse.click(65, 201, duration=2)
    mouse.click(1934, 1217, duration=2)
    mouse.click(2196, 1340, duration=2)
    mouse.moveTo(1221, 1085, duration=3)
    mouse.dragRel(1488, 0, 2)
    mouse.click(2345, 1848, duration=2)
    time.sleep(settings.initial_wait_seconds)
    temporary = directory / "capture_wait.jpg"
    try:
        for attempt in range(settings.max_attempts):
            mouse.screenshot(str(temporary))
            image = read_grayscale(temporary)
            candidate = image[809:861, 1730:2109]
            if template_difference(template, candidate) < settings.difference_threshold:
                time.sleep(2)
                break
            if attempt > 0 and attempt % 10 == 0:
                mouse.click(2030, 1859, duration=1)
            keyboard.press("enter")
            time.sleep(settings.attempt_wait_seconds)
        else:
            raise TimeoutError("End-of-game template was not found for {}".format(game_code))
        mouse.click(1040, 621, duration=2)
        time.sleep(5)
        mouse.screenshot(str(screenshot))
        mouse.click(3696, 158, duration=2)
        mouse.click(3782, 79, duration=2)
        mouse.click(2509, 1664, duration=2)
        time.sleep(10)
    finally:
        if temporary.is_file():
            temporary.unlink()
    return screenshot

