"""Проверки XML, шести параметров и локальных путей."""

import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from src.config import FIELD_NAMES, load_config
from src.validation import ConfigError
from tests.helpers import write_config


class ConfigTests(unittest.TestCase):
    """Проверка конфигурации в отдельном временном каталоге."""

    def setUp(self) -> None:
        """Создать каталог без зависимости от файлов проекта."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def test_valid_config(self) -> None:
        """Прочитать все шесть полей с правильными типами."""
        config = load_config(write_config(self.directory))
        self.assertEqual(config.package, "express")
        self.assertEqual(config.repository, "https://registry.npmjs.org")
        self.assertIs(config.test_mode, False)
        self.assertEqual(config.output_file, "graph.svg")
        self.assertIs(config.ascii_tree, True)
        self.assertEqual(config.filter_substring, "debug")
        with self.assertRaises(FrozenInstanceError):
            config.package = "changed"

    def test_missing_fields(self) -> None:
        """Отсутствие каждого из шести параметров является ошибкой."""
        for name in FIELD_NAMES:
            with self.subTest(name=name):
                path = write_config(self.directory)
                tree = ElementTree.parse(path)
                root = tree.getroot()
                root.remove(root.find(name))
                tree.write(path)
                with self.assertRaisesRegex(ConfigError, name):
                    load_config(path)

    def test_invalid_values(self) -> None:
        """В сообщении об ошибке должно быть имя параметра."""
        invalid_values = {
            "package": "bad name",
            "repository": "ftp://example.org",
            "test_mode": "yes",
            "output_file": "graph.png",
            "ascii_tree": "1",
            "filter_substring": "first\nsecond",
        }
        for name, value in invalid_values.items():
            with self.subTest(name=name):
                path = write_config(self.directory, **{name: value})
                with self.assertRaisesRegex(ConfigError, name):
                    load_config(path)

    def test_empty_values(self) -> None:
        """Только фильтр может иметь пустое значение."""
        for name in FIELD_NAMES:
            with self.subTest(name=name):
                path = write_config(self.directory, **{name: ""})
                if name == "filter_substring":
                    self.assertEqual(load_config(path).filter_substring, "")
                else:
                    with self.assertRaisesRegex(ConfigError, name):
                        load_config(path)

    def test_invalid_structure(self) -> None:
        """Отклонить неизвестные поля, повторы и вложенную разметку."""
        documents = (
            "<wrong />",
            '<config attribute="value" />',
            "<config>unexpected text</config>",
            "<config><unknown /></config>",
            "<config><package>A</package><package>B</package></config>",
            "<config><package><name>A</name></package></config>",
            '<config><package value="A" /></config>',
            "<config><package>A</package>unexpected text</config>",
        )
        path = self.directory / "config.xml"
        for document in documents:
            with self.subTest(document=document):
                path.write_text(document, encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_config(path)

    def test_invalid_xml_and_files(self) -> None:
        """Обработать ошибки XML и пути к конфигурации."""
        path = self.directory / "missing.xml"
        with self.assertRaises(ConfigError):
            load_config(path)
        with self.assertRaises(ConfigError):
            load_config(self.directory)
        path.write_text("<config>", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "XML"):
            load_config(path)
        path.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_unknown_encoding(self) -> None:
        """Обработать неподдерживаемую кодировку XML без traceback."""
        path = self.directory / "encoding.xml"
        path.write_text(
            '<?xml version="1.0" encoding="unknown"?><config />',
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_test_repository_relative_path(self) -> None:
        """Разрешить путь с пробелами относительно XML."""
        repository = self.directory / "test repository.json"
        repository.write_text("{}", encoding="utf-8")
        path = write_config(
            self.directory,
            package="A",
            repository=repository.name,
            test_mode="true",
            filter_substring="",
        )
        config = load_config(path)
        self.assertIs(config.test_mode, True)
        self.assertEqual(config.repository, repository.name)
        self.assertFalse((self.directory / "graph.svg").exists())

    def test_invalid_test_repository(self) -> None:
        """Отклонить неверный путь тестового репозитория."""
        for value in ("https://example.org", "missing.json", "."):
            with self.subTest(value=value):
                path = write_config(
                    self.directory, repository=value, test_mode="true"
                )
                with self.assertRaisesRegex(ConfigError, "repository"):
                    load_config(path)

    def test_unreadable_test_repository(self) -> None:
        """Сообщить об отказе в чтении тестового файла."""
        repository = self.directory / "repository.json"
        repository.write_text("{}", encoding="utf-8")
        path = write_config(
            self.directory, repository=repository.name, test_mode="true"
        )
        with patch("pathlib.Path.open", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(ConfigError, "repository"):
                load_config(path)

    def test_output_location(self) -> None:
        """Отклонить неверное место сохранения изображения."""
        (self.directory / "directory.svg").mkdir()
        for value in ("missing/graph.svg", "directory.svg"):
            with self.subTest(value=value):
                path = write_config(self.directory, output_file=value)
                with self.assertRaisesRegex(ConfigError, "output_file"):
                    load_config(path)

    def test_unwritable_output(self) -> None:
        """Обработать отсутствие прав без создания выходного файла."""
        path = write_config(self.directory)
        with patch("src.validation.os.access", return_value=False):
            with self.assertRaisesRegex(ConfigError, "output_file"):
                load_config(path)

    def test_invalid_urls(self) -> None:
        """Отклонить некорректные компоненты URL."""
        urls = (
            "registry.npmjs.org",
            "https://",
            "https://bad host/",
            "https://host:invalid/",
            "https://host:99999/",
            "https://[broken/",
            "https://user:password@host/",
            "https://%host/",
            "https://./",
        )
        for value in urls:
            with self.subTest(value=value):
                path = write_config(self.directory, repository=value)
                with self.assertRaisesRegex(ConfigError, "repository"):
                    load_config(path)

    def test_scoped_package_and_escaping(self) -> None:
        """Поддержать scoped-имя и стандартное экранирование XML."""
        path = write_config(
            self.directory, package="@scope/name", filter_substring="a&b"
        )
        config = load_config(path)
        self.assertEqual(config.package, "@scope/name")
        self.assertEqual(config.filter_substring, "a&b")
