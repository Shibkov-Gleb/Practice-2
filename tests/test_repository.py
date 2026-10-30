"""Проверки тестового JSON-репозитория и выбора источника данных."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import load_config
from src.npm import DependencyError
from src.repository import create_dependency_loader, load_test_repository
from tests.helpers import write_config


class RepositoryTests(unittest.TestCase):
    """Проверить структуру JSON, ссылки и локальные пути."""

    def setUp(self) -> None:
        """Создать временный файл тестового репозитория."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "repository.json"

    def write_repository(self, repository: object) -> None:
        """Сохранить произвольный JSON-документ для проверки."""
        self.path.write_text(json.dumps(repository), encoding="utf-8")

    def test_valid_graph_with_cycles(self) -> None:
        """Разрешить общие зависимости, циклы и пустые списки."""
        repository = {
            "A": ["B", "C"], "B": ["C"], "C": ["A", "C"], "D": [],
        }
        self.write_repository(repository)
        self.assertEqual(load_test_repository(self.path), repository)

    def test_empty_repository(self) -> None:
        """Разрешить пустой JSON-объект как пустой репозиторий."""
        self.write_repository({})
        self.assertEqual(load_test_repository(self.path), {})

    def test_invalid_document(self) -> None:
        """Отклонить массив, строку и null вместо JSON-объекта."""
        for document in ([], "text", None):
            with self.subTest(document=document):
                self.write_repository(document)
                with self.assertRaises(DependencyError):
                    load_test_repository(self.path)

    def test_invalid_names(self) -> None:
        """Имена узлов должны состоять только из заглавных букв A-Z."""
        for name in ("", "a", "A1", "А", "@SCOPE/A", "A B"):
            with self.subTest(name=name):
                self.write_repository({name: []})
                with self.assertRaisesRegex(DependencyError, "A-Z"):
                    load_test_repository(self.path)

    def test_multiple_uppercase_letters(self) -> None:
        """Поддержать имена из нескольких заглавных латинских букв."""
        repository = {"ROOT": ["LIB"], "LIB": []}
        self.write_repository(repository)
        self.assertEqual(load_test_repository(self.path), repository)

    def test_invalid_dependency_lists(self) -> None:
        """Для каждого пакета требуется именно массив зависимостей."""
        for value in (None, "B", {"B": "*"}):
            with self.subTest(value=value):
                self.write_repository({"A": value})
                with self.assertRaisesRegex(DependencyError, "A:"):
                    load_test_repository(self.path)

    def test_invalid_dependency_names(self) -> None:
        """Отклонить неверный тип или формат имени зависимости."""
        for value in (None, [], {}, True, "b", "B2", "Б"):
            with self.subTest(value=value):
                self.write_repository({"A": [value]})
                with self.assertRaisesRegex(DependencyError, "A-Z"):
                    load_test_repository(self.path)

    def test_missing_reference(self) -> None:
        """Все упомянутые зависимости должны быть описаны явно."""
        self.write_repository({"A": ["B"]})
        with self.assertRaisesRegex(DependencyError, "B не описана"):
            load_test_repository(self.path)

    def test_duplicate_keys(self) -> None:
        """Не позволять JSON молча перезаписывать описание пакета."""
        self.path.write_text('{"A": [], "A": ["A"]}', encoding="utf-8")
        with self.assertRaisesRegex(DependencyError, "повторно"):
            load_test_repository(self.path)

    def test_invalid_json_and_encoding(self) -> None:
        """Обработать повреждённый JSON и неверную кодировку."""
        for payload in (b"{", b"", b"\xff"):
            with self.subTest(payload=payload):
                self.path.write_bytes(payload)
                with self.assertRaises(DependencyError):
                    load_test_repository(self.path)

    def test_unreadable_file(self) -> None:
        """Сообщить об отсутствии файла и отказе в чтении."""
        with self.assertRaises(DependencyError):
            load_test_repository(self.path)
        with patch("pathlib.Path.open", side_effect=PermissionError("denied")):
            with self.assertRaises(DependencyError):
                load_test_repository(self.path)

    def test_local_loader_relative_to_xml(self) -> None:
        """Читать локальный файл относительно XML без запросов npm."""
        self.write_repository({"A": ["B"], "B": []})
        path = write_config(
            self.directory, package="A", test_mode="true",
            repository=self.path.name,
        )
        with patch("src.repository.fetch_direct_dependencies") as fetch:
            loader = create_dependency_loader(load_config(path), path)
            self.assertEqual(loader("A"), ["B"])
            self.assertEqual(loader("B"), [])
        fetch.assert_not_called()

    def test_missing_package(self) -> None:
        """Обработать отсутствующий в репозитории исходный пакет."""
        self.write_repository({"A": []})
        path = write_config(
            self.directory, package="B", test_mode="true",
            repository=self.path.name,
        )
        loader = create_dependency_loader(load_config(path), path)
        with self.assertRaisesRegex(DependencyError, "Пакет B отсутствует"):
            loader("B")

    def test_remote_loader(self) -> None:
        """Передать URL и имя пакета существующему HTTP-клиенту npm."""
        path = write_config(self.directory)
        with patch(
            "src.repository.fetch_direct_dependencies", return_value={}
        ) as fetch:
            loader = create_dependency_loader(load_config(path), path)
            self.assertEqual(loader("express"), {})
        fetch.assert_called_once_with("https://registry.npmjs.org", "express")
