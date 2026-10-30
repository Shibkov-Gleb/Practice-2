"""Создание независимых XML-конфигураций для тестов."""

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

from src.main import main


DEFAULT_VALUES = {
    "package": "express",
    "repository": "https://registry.npmjs.org",
    "test_mode": "false",
    "output_file": "graph.svg",
    "ascii_tree": "true",
    "filter_substring": "debug",
}


def write_config(directory: Path, **changes: str) -> Path:
    """Сохранить XML с заданными изменениями настроек."""
    values = dict(DEFAULT_VALUES, **changes)
    root = ElementTree.Element("config")
    for name, value in values.items():
        ElementTree.SubElement(root, name).text = value
    path = directory / "config.xml"
    ElementTree.ElementTree(root).write(path, encoding="utf-8")
    return path


def run_main(*arguments: str) -> tuple[int, str, str]:
    """Запустить CLI в процессе и перехватить оба потока вывода."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()
