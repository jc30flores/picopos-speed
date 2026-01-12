import os
import shutil
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "menu_image"
    destination = root / "media" / "menu_image"
    if not source.exists():
        print(f"No source folder found at {source}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        print(f"Destination already exists at {destination}")
        return
    shutil.move(str(source), str(destination))
    print(f"Moved {source} -> {destination}")


if __name__ == "__main__":
    main()
