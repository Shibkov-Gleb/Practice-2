"""Создание независимых XML-конфигураций для тестов."""

from pathlib import Path
from xml.etree import ElementTree


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
