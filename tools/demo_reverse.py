"""Демонстрация обратных зависимостей на локальных репозиториях."""

import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
CASES = ("diamond", "cycle", "empty", "filter")


def main() -> int:
    """Показать ромб, цикл, отсутствие зависимых пакетов и фильтр."""
    failed = False
    for case in CASES:
        print(f"\nСценарий: {case}", flush=True)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "src.reverse", "--config",
             str(PROJECT_DIR / "examples" / f"reverse_{case}.xml")],
            cwd=PROJECT_DIR, check=False,
        )
        failed = failed or result.returncode != SUCCESS
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
