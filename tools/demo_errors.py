"""Демонстрация обработки ошибок всех шести параметров через CLI."""

import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree


PROJECT_DIR = Path(__file__).resolve().parents[1]
EXPECTED_ERROR = 2
INVALID_VALUES = {
    "package": "bad name",
    "repository": "ftp://example.org",
    "test_mode": "yes",
    "output_file": "graph.png",
    "ascii_tree": "1",
    "filter_substring": "first\nsecond",
}


def demonstrate_error(directory: Path, name: str, value: str) -> bool:
    """Изменить один параметр и показать реальное сообщение CLI."""
    tree = ElementTree.parse(PROJECT_DIR / "examples/config.xml")
    tree.getroot().find(name).text = value
    path = directory / f"{name}.xml"
    tree.write(path, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-B", "-m", "src.main", "--config", str(path)],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"\n{name}={value!r}")
    print(result.stderr.strip())
    print(f"Код завершения: {result.returncode}")
    return (
        result.returncode == EXPECTED_ERROR
        and name in result.stderr
        and not result.stdout
    )


def main() -> int:
    """Вернуть 0, если все шесть ошибок обработаны ожидаемым образом."""
    with tempfile.TemporaryDirectory() as directory:
        results = [
            demonstrate_error(Path(directory), name, value)
            for name, value in INVALID_VALUES.items()
        ]
    return int(not all(results))


if __name__ == "__main__":
    sys.exit(main())
