"""Проверки HTTP-клиента npm без обращения к внешнему реестру."""

import json
import socket
import ssl
import unittest
from http import HTTPStatus
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from src.npm import (
    REQUEST_ATTEMPTS,
    REQUEST_TIMEOUT,
    DependencyError,
    build_metadata_url,
    fetch_direct_dependencies,
)


REPOSITORY = "https://registry.example.org/npm"
PACKAGE = "example-package"


def make_response(payload: bytes) -> MagicMock:
    """Создать HTTP-ответ с контекстным менеджером и заданным телом."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = payload
    return response


def fetch_metadata(metadata: object) -> dict[str, str]:
    """Передать метаданные клиенту через подменённый HTTP-ответ."""
    payload = json.dumps(metadata).encode("utf-8")
    with patch("src.npm.urlopen", return_value=make_response(payload)):
        return fetch_direct_dependencies(REPOSITORY, PACKAGE)


class NpmTests(unittest.TestCase):
    """Проверки запросов, данных npm и исключений транспорта."""

    def setUp(self) -> None:
        """Создать независимый набор метаданных для каждого теста."""
        self.metadata = {"name": PACKAGE, "version": "1.0.0"}
        sleeper = patch("src.npm.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_metadata_url(self) -> None:
        """Сохранить путь реестра и экранировать scoped-имя."""
        cases = (
            ("https://host", "demo", "https://host/demo/latest"),
            ("https://host/npm/", "demo", "https://host/npm/demo/latest"),
            ("https://host", "@scope/name",
             "https://host/@scope%2Fname/latest"),
            ("https://host/npm?q=x#part", "demo",
             "https://host/npm/demo/latest?q=x"),
        )
        for repository, package, expected in cases:
            with self.subTest(repository=repository, package=package):
                self.assertEqual(
                    build_metadata_url(repository, package), expected
                )

    def test_request_and_sorted_dependencies(self) -> None:
        """Проверить параметры запроса и сортировку результата."""
        self.metadata["dependencies"] = {"beta": "^2", "alpha": "~1"}
        payload = json.dumps(self.metadata).encode("utf-8")
        response = make_response(payload)
        with patch("src.npm.urlopen", return_value=response) as open_url:
            dependencies = fetch_direct_dependencies(REPOSITORY, PACKAGE)
        self.assertEqual(list(dependencies), ["alpha", "beta"])
        self.assertEqual(dependencies, {"alpha": "~1", "beta": "^2"})
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, f"{REPOSITORY}/{PACKAGE}/latest")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(
            open_url.call_args.kwargs, {"timeout": REQUEST_TIMEOUT}
        )
        response.__exit__.assert_called_once()

    def test_no_dependencies(self) -> None:
        """Отсутствие обоих полей означает отсутствие зависимостей."""
        self.assertEqual(fetch_metadata(self.metadata), {})

    def test_collect_versions_after_validation(self) -> None:
        """Не сохранять версию из некорректного ответа реестра."""
        versions = {}
        self.metadata["dependencies"] = {"beta": None}
        payload = json.dumps(self.metadata).encode("utf-8")
        with patch("src.npm.urlopen", return_value=make_response(payload)):
            with self.assertRaises(DependencyError):
                fetch_direct_dependencies(REPOSITORY, PACKAGE, versions)
        self.assertEqual(versions, {})

    def test_optional_dependencies(self) -> None:
        """Учесть приоритет необязательных зависимостей."""
        self.metadata["dependencies"] = {"shared": "^1", "regular": "*"}
        self.metadata["optionalDependencies"] = {
            "shared": "^2", "optional": "~3"
        }
        self.assertEqual(
            fetch_metadata(self.metadata),
            {"optional": "~3", "regular": "*", "shared": "^2"},
        )

    def test_development_and_peer_dependencies_excluded(self) -> None:
        """Исключить devDependencies и peerDependencies."""
        self.metadata["dependencies"] = {"runtime": "^1"}
        self.metadata["devDependencies"] = {"test-runner": "^2"}
        self.metadata["peerDependencies"] = {"host-library": "^3"}
        self.assertEqual(fetch_metadata(self.metadata), {"runtime": "^1"})

    def test_specs_preserved_without_extra_requests(self) -> None:
        """Сохранить спецификации и выполнить ровно один запрос."""
        dependencies = {
            "@scope/name": "^1.0.0 || ^2.0.0",
            "alias": "npm:other-package@^3",
            "empty": "",
            "git-package": "git+https://example.org/repository.git",
        }
        self.metadata["dependencies"] = dependencies
        payload = json.dumps(self.metadata).encode("utf-8")
        with patch(
            "src.npm.urlopen", return_value=make_response(payload)
        ) as open_url:
            self.assertEqual(
                fetch_direct_dependencies(REPOSITORY, PACKAGE), dependencies
            )
        open_url.assert_called_once()

    def test_http_not_found(self) -> None:
        """Превратить HTTP 404 в понятное сообщение о пакете."""
        error = HTTPError(
            REPOSITORY, HTTPStatus.NOT_FOUND.value, "Not Found", {}, None
        )
        with patch("src.npm.urlopen", side_effect=error):
            with self.assertRaisesRegex(DependencyError, PACKAGE):
                fetch_direct_dependencies(REPOSITORY, PACKAGE)

    def test_http_errors(self) -> None:
        """Сообщить об отказе доступа, лимите и сбое сервера."""
        codes = (
            HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN,
            HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE,
        )
        for code in codes:
            with self.subTest(code=code):
                error = HTTPError(REPOSITORY, code.value, "failure", {}, None)
                with patch("src.npm.urlopen", side_effect=error):
                    with self.assertRaisesRegex(
                        DependencyError, str(code.value)
                    ):
                        fetch_direct_dependencies(REPOSITORY, PACKAGE)

    def test_transport_errors(self) -> None:
        """Обработать DNS, тайм-аут и разрыв соединения."""
        errors = (
            URLError("DNS failure"), TimeoutError("timeout"),
            ConnectionResetError("reset"), IncompleteRead(b"partial"),
        )
        for error in errors:
            with self.subTest(error=error):
                with patch("src.npm.urlopen", side_effect=error):
                    with self.assertRaises(DependencyError):
                        fetch_direct_dependencies(REPOSITORY, PACKAGE)

    def test_read_error(self) -> None:
        """Обработать сбой чтения тела ответа и закрыть соединение."""
        response = make_response(b"")
        response.__enter__.return_value.read.side_effect = OSError("read")
        with patch("src.npm.urlopen", return_value=response):
            with self.assertRaises(DependencyError):
                fetch_direct_dependencies(REPOSITORY, PACKAGE)
        response.__exit__.assert_called_once()

    def test_retry_tls_eof_then_success(self) -> None:
        """Восстановиться после прямого или обёрнутого TLS EOF."""
        payload = json.dumps(self.metadata).encode("utf-8")
        error = ssl.SSLEOFError(8, "EOF occurred in violation of protocol")
        failures = (error, URLError(error), URLError(socket.timeout("TLS")))
        for failure in failures:
            with self.subTest(failure=failure):
                with patch("src.npm.urlopen", side_effect=[
                    failure, make_response(payload),
                ]) as open_url:
                    self.assertEqual(
                        fetch_direct_dependencies(REPOSITORY, PACKAGE), {}
                    )
                self.assertEqual(open_url.call_count, 2)
                self.sleep.assert_called_with(0.5)

    def test_retry_limit_and_package_diagnostic(self) -> None:
        """Ограничить число повторов и назвать сбойный пакет."""
        error = URLError(ssl.SSLEOFError(8, "TLS EOF"))
        with patch("src.npm.urlopen", side_effect=error) as open_url:
            with self.assertRaisesRegex(
                DependencyError, f"{PACKAGE} .*{REQUEST_ATTEMPTS}"
            ):
                fetch_direct_dependencies(REPOSITORY, PACKAGE)
        self.assertEqual(open_url.call_count, REQUEST_ATTEMPTS)
        self.assertEqual(self.sleep.call_count, REQUEST_ATTEMPTS - 1)

    def test_retry_interrupted_response(self) -> None:
        """Закрыть неполный ответ и повторить загрузку целиком."""
        broken = make_response(b"")
        broken.__enter__.return_value.read.side_effect = IncompleteRead(b"{")
        payload = json.dumps(self.metadata).encode("utf-8")
        with patch("src.npm.urlopen", side_effect=[
            broken, make_response(payload),
        ]):
            self.assertEqual(
                fetch_direct_dependencies(REPOSITORY, PACKAGE), {}
            )
        broken.__exit__.assert_called_once()
        self.sleep.assert_called_once()

    def test_certificate_error_without_retry(self) -> None:
        """Не повторять и не обходить ошибку проверки сертификата."""
        error = URLError(ssl.SSLCertVerificationError(1, "certificate"))
        with patch("src.npm.urlopen", side_effect=error) as open_url:
            with self.assertRaisesRegex(DependencyError, "certificate"):
                fetch_direct_dependencies(REPOSITORY, PACKAGE)
        open_url.assert_called_once()
        self.sleep.assert_not_called()

    def test_invalid_json(self) -> None:
        """Отклонить повреждённый JSON, HTML и неверную кодировку."""
        for payload in (b"{", b"<html>error</html>", b"\xff", b""):
            with self.subTest(payload=payload):
                with patch(
                    "src.npm.urlopen", return_value=make_response(payload)
                ):
                    with self.assertRaisesRegex(DependencyError, "JSON"):
                        fetch_direct_dependencies(REPOSITORY, PACKAGE)

    def test_invalid_metadata(self) -> None:
        """Отклонить ответ другого пакета и неполные метаданные."""
        documents = (
            [], None, "text", {},
            {"name": "other-package", "version": "1.0.0"},
            {"name": PACKAGE},
            {"name": PACKAGE, "version": ""},
            {"name": PACKAGE, "version": None},
            {"name": PACKAGE, "version": "1.0.0\nlabel"},
        )
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(DependencyError):
                    fetch_metadata(document)

    def test_invalid_dependency_sections(self) -> None:
        """Отклонить неверные типы полей обоих видов зависимостей."""
        for field in ("dependencies", "optionalDependencies"):
            for value in ([], None, "not an object"):
                with self.subTest(field=field, value=value):
                    document = dict(self.metadata, **{field: value})
                    with self.assertRaisesRegex(DependencyError, field):
                        fetch_metadata(document)

    def test_invalid_dependency_entries(self) -> None:
        """Отклонить неправильные имена, типы и управляющие символы."""
        entries = (
            {"bad name": "^1"}, {"": "^1"}, {"demo": None},
            {"demo": []}, {"demo": True}, {"demo": "^1\n^2"},
        )
        for entries_value in entries:
            with self.subTest(entries=entries_value):
                self.metadata["dependencies"] = entries_value
                with self.assertRaisesRegex(DependencyError, "dependencies"):
                    fetch_metadata(self.metadata)
