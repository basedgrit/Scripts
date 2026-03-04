
from __future__ import annotations
from pathlib import Path
import argparse
import sys


# Which file endings belong in each folder.
EXT_MAP = {
    "Images": {"jpg", "jpeg", "png", "gif", "bmp", "webp", "heic", "tiff", "svg"},
    "Video": {"mp4", "mov", "mkv", "avi", "wmv", "webm"},
    "Audio": {"mp3", "wav", "flac", "m4a", "aac", "ogg"},
    "PDF": {"pdf"},
    "Docs": {"doc", "docx", "txt", "rtf", "odt"},
    "Spreadsheets": {"xls", "xlsx", "csv", "ods"},
    "Presentations": {"ppt", "pptx", "odp"},
    "Archives": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"},
    "Installers": {"exe", "msi", "msix", "appx", "bat", "cmd"},
    "Code": {"ps1", "py", "js", "ts", "html", "css", "json", "xml", "yml", "yaml", "sql"},
}


def category_for(ext: str) -> str:
    """Pick a folder name for this file ending. Use 'Other' if unknown."""
    ext = ext.lower().lstrip(".")
    for folder, exts in EXT_MAP.items():
        if ext in exts:
            return folder
    return "Other"


def unique_path(dest_dir: Path, filename: str) -> Path:
    """Choose a file path that does not overwrite an existing file."""
    p = dest_dir / filename
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def organize(folder: Path, dry_run: bool) -> int:
    """Sort files in this folder into subfolders and report how many moved."""
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    moved = 0
    files = [p for p in folder.iterdir() if p.is_file()]

    print(f"Organizing folder: {folder}")
    print(f"Found {len(files)} files.")

    for item in files:
        cat = category_for(item.suffix)
        dest_dir = folder / cat
        target = unique_path(dest_dir, item.name)

        # Skip it if it is already where it belongs.
        if item.parent == dest_dir:
            continue

        if dry_run:
            print(f"[DRY] {item.name} -> {dest_dir.name}/{target.name}")
            continue

        try:
            dest_dir.mkdir(exist_ok=True)
            item.rename(target)
            print(f"[MOVED] {item.name} -> {dest_dir.name}/{target.name}")
            moved += 1
        except OSError as e:
            print(f"[FAILED] {item} :: {e}", file=sys.stderr)

    print(f"Done. Moved {moved} file(s).")
    return moved


def main():
    """Read options from the command line and start sorting files."""
    parser = argparse.ArgumentParser(description="Organize a folder into type-based subfolders.")
    parser.add_argument("--path", type=str, default=str(Path.home() / "Downloads"),
                        help="Folder to organize (default: ~/Downloads)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without moving files")
    args = parser.parse_args()

    organize(Path(args.path).expanduser(), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
