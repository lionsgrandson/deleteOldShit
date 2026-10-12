from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

SKIP_NAMES = {"$recycle.bin", "system volume information"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

@dataclass(frozen=True)
class ScanItem:
    path: Path
    is_dir: bool
    size: int
    modified: float

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"

def folder_size(path: Path, cancelled: Callable[[], bool] | None = None) -> int:
    total = 0
    try:
        for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
            if cancelled and cancelled():
                break
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_NAMES and not (Path(root) / d).is_symlink()]
            for filename in files:
                try:
                    total += (Path(root) / filename).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total

def scan_folder(root: Path, include_nested: bool, min_size: int = 0,
                cancelled: Callable[[], bool] | None = None,
                progress: Callable[[str], None] | None = None) -> list[ScanItem]:
    root = root.resolve()
    results: list[ScanItem] = []
    if not root.is_dir():
        raise ValueError("Choose a folder that exists.")
    def add(path: Path) -> None:
        if cancelled and cancelled():
            return
        try:
            if path.is_symlink() or path.name.lower() in SKIP_NAMES:
                return
            stat = path.stat()
            size = folder_size(path, cancelled) if path.is_dir() else stat.st_size
            if size >= min_size:
                results.append(ScanItem(path, path.is_dir(), size, stat.st_mtime))
            if progress:
                progress(str(path))
        except (OSError, ValueError):
            return
    if include_nested:
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            if cancelled and cancelled():
                break
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_NAMES and not (Path(current) / d).is_symlink()]
            current_path = Path(current)
            for name in dirs + files:
                add(current_path / name)
    else:
        try:
            for path in root.iterdir():
                add(path)
        except OSError as exc:
            raise ValueError(f"Cannot read this folder: {exc}") from exc
    return sorted(results, key=lambda item: (not item.is_dir, item.name.lower()))

def recycle_paths(paths: Iterable[Path]) -> list[Path]:
    """Move paths to the Windows Recycle Bin using the native shell."""
    items = [Path(path).absolute() for path in paths]
    if any(path.is_symlink() or not path.exists() for path in items):
        raise ValueError("Selected paths must exist and cannot be symbolic links.")
    if os.name != "nt":
        raise RuntimeError("Recycle Bin deletion is only available on Windows.")
    if not items:
        return []
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_bool),
            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p),
        ]
    source = "\0".join(str(path) for path in items) + "\0\0"
    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 3
    operation.pFrom = source
    operation.fFlags = 0x0040 | 0x0010 | 0x0400
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise OSError(f"Windows could not recycle the selection (code {result}).")
    return items

def modified_text(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
