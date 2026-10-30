"""Демонстрация третьего этапа на различных тестовых репозиториях."""

import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
DEMO_CASES = (
    ("Простой граф", "test_config.xml"),
    ("Общая транзитивная зависимость", "test_diamond.xml"),
    ("Цикл и самоссылка", "test_cycle.xml"),
    ("Фильтрация пакета B", "test_filter.xml"),
    ("Пакет без зависимостей", "test_empty.xml"),
    ("Фильтрация исходного пакета", "test_filtered_root.xml"),
)


def main() -> int:
    """Показать шесть запусков CLI без обращения к сети."""
    failed = False
    for title, filename in DEMO_CASES:
        print(f"\n{title} ({filename}):", flush=True)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "src.main", "--config",
             str(PROJECT_DIR / "examples" / filename)],
            cwd=PROJECT_DIR,
            check=False,
        )
        failed = failed or result.returncode != SUCCESS
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
