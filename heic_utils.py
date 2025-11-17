# -*- coding: utf-8 -*-
"""Obsługa konwersji plików HEIC na JPG na potrzeby aplikacji."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

from PIL import Image

HEIC_EXTS = (".heic", ".heif")
TARGET_MIN_BYTES = 1_000_000  # 1 MB
TARGET_MAX_BYTES = 2_000_000  # 2 MB
QUALITY_MIN = 40
QUALITY_MAX = 95
SUBSAMPLING = 2  # 4:2:0 chroma subsampling

_HEIF_REGISTERED = False


@dataclass
class ConversionResult:
    source: str
    target: str
    quality: int
    size_bytes: int


def list_heic_to_convert(directory: str) -> List[str]:
    """Zwraca listę plików HEIC w katalogu roboczym, które nie mają jeszcze pary JPG."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []
    results: List[str] = []
    for entry in dir_path.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in HEIC_EXTS:
            continue
        jpg_candidate = entry.with_suffix(".jpg")
        jpeg_candidate = entry.with_suffix(".jpeg")
        if jpg_candidate.exists() or jpeg_candidate.exists():
            continue
        results.append(str(entry))
    results.sort()
    return results


def convert_heic_batch(
    paths: Sequence[str],
    working_dir: str,
    backup_folder_name: str = "kopia heic",
    remove_source: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Tuple[List[ConversionResult], List[Tuple[str, str]]]:
    """
    Konwertuje podane pliki HEIC do JPG.

    Zwraca listę udanych konwersji oraz parę (plik, komunikat błędu) dla niepowodzeń.
    """
    heic_paths = [Path(p) for p in paths]
    if not heic_paths:
        return [], []

    _ensure_heif_registered()

    workdir_path = Path(working_dir)
    backup_dir = workdir_path / backup_folder_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    converted: List[ConversionResult] = []
    errors: List[Tuple[str, str]] = []

    total = len(heic_paths)
    done = 0

    for src in heic_paths:
        try:
            _copy_to_backup(src, backup_dir)
            target, quality, size = _convert_single(src)
            converted.append(ConversionResult(str(src), str(target), quality, size))
            if remove_source:
                try:
                    _remove_source_file(src)
                except Exception as exc:
                    errors.append((str(src), f"Przekonwertowano, ale nie udało się usunąć oryginału: {exc}"))
        except Exception as exc:
            errors.append((str(src), str(exc)))
        finally:
            done += 1
            if progress_callback:
                try:
                    progress_callback(done, total)
                except Exception:
                    pass

    return converted, errors


def _copy_to_backup(src: Path, backup_dir: Path) -> None:
    dst = backup_dir / src.name
    if dst.exists():
        return
    shutil.copy2(src, dst)


def _convert_single(src: Path) -> Tuple[Path, int, int]:
    target = src.with_suffix(".jpg")
    with Image.open(src) as image:
        rgb_image = image.convert("RGB")
        data, quality = _encode_with_target_size(rgb_image)
    target.write_bytes(data)
    return target, quality, len(data)


def _remove_source_file(src: Path) -> None:
    if src.exists():
        src.unlink()


def _encode_with_target_size(image: Image.Image) -> Tuple[bytes, int]:
    low = QUALITY_MIN
    high = QUALITY_MAX
    best: Tuple[int, int, bytes] | None = None  # (size, quality, data)

    while low <= high:
        quality = (low + high) // 2
        data = _encode_jpeg(image, quality)
        size = len(data)
        if size > TARGET_MAX_BYTES:
            high = quality - 1
        else:
            best = (size, quality, data)
            low = quality + 1

    if best is None:
        quality = QUALITY_MIN
        data = _encode_jpeg(image, quality)
        return data, quality

    size, quality, data = best
    if size < TARGET_MIN_BYTES and quality < QUALITY_MAX:
        for quality in range(quality + 1, QUALITY_MAX + 1):
            candidate = _encode_jpeg(image, quality)
            candidate_size = len(candidate)
            if candidate_size > TARGET_MAX_BYTES:
                break
            data = candidate
            size = candidate_size
    return data, quality


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        subsampling=SUBSAMPLING,
        optimize=True,
    )
    return buffer.getvalue()


def _ensure_heif_registered() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        from pillow_heif import register_heif_opener  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Brak zależności pillow-heif. Aby przekonwertować pliki HEIC, zainstaluj pakiet:\n"
            "    pip install pillow-heif"
        ) from exc
    register_heif_opener()
    _HEIF_REGISTERED = True
