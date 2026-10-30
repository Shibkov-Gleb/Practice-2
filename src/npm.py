"""Получение прямых зависимостей через HTTP API реестра npm."""

__all__ = (
    "REQUEST_TIMEOUT",
    "DEPENDENCY_FIELDS",
    "DependencyError",
    "build_metadata_url",
    "fetch_direct_dependencies",
)

import json
from http import HTTPStatus
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from src.validation import PACKAGE_PATTERN


REQUEST_TIMEOUT = 10
DEPENDENCY_FIELDS = ("dependencies", "optionalDependencies")


class DependencyError(ValueError):
    """Ошибка получения или разбора метаданных пакета npm."""


def build_metadata_url(repository: str, package: str) -> str:
    """Дополнить URL реестра именем пакета и тегом latest."""
    parts = urlsplit(repository)
    package_path = quote(package, safe="@")
    path = f"{parts.path.rstrip('/')}/{package_path}/latest"
    return urlunsplit(parts._replace(path=path, fragment=""))


def fetch_direct_dependencies(repository: str, package: str) -> dict[str, str]:
    """Получить прямые runtime-зависимости latest без обхода графа."""
    url = build_metadata_url(repository, package)
    metadata = _read_metadata(url, package)
    _validate_metadata(metadata, package)
    dependencies = {}
    for field in DEPENDENCY_FIELDS:
        dependencies.update(_extract_section(metadata, field))
    return dict(sorted(dependencies.items()))


def _read_metadata(url: str, package: str) -> dict:
    """Выполнить HTTP-запрос и преобразовать JSON-ответ в объект."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "practice-2-dependencies/0.2",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
    except HTTPError as error:
        if error.code == HTTPStatus.NOT_FOUND:
            message = f"Пакет {package} или его версия latest не найдены."
        else:
            message = f"Реестр вернул HTTP {error.code}: {error.reason}."
        raise DependencyError(message) from error
    except (URLError, OSError, HTTPException) as error:
        message = f"Не удалось получить данные из реестра: {error}"
        raise DependencyError(message) from error
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise DependencyError("Реестр вернул некорректный JSON.") from error


def _validate_metadata(metadata: dict, package: str) -> None:
    """Проверить имя и версию в метаданных, полученных от реестра."""
    if not isinstance(metadata, dict):
        raise DependencyError("Метаданные npm должны быть JSON-объектом.")
    if metadata.get("name") != package:
        raise DependencyError("Имя пакета в ответе не совпадает с запросом.")
    version = metadata.get("version")
    if not isinstance(version, str) or not version.strip():
        raise DependencyError("В метаданных отсутствует версия пакета.")


def _extract_section(metadata: dict, field: str) -> dict[str, str]:
    """Прочитать и проверить словарь зависимостей одного типа."""
    dependencies = metadata.get(field, {})
    if not isinstance(dependencies, dict):
        raise DependencyError(f"{field}: ожидается JSON-объект.")
    for name, specification in dependencies.items():
        if not PACKAGE_PATTERN.fullmatch(name):
            raise DependencyError(f"{field}: некорректное имя зависимости.")
        _validate_specification(specification, field)
    return dependencies


def _validate_specification(specification: str, field: str) -> None:
    """Проверить строковый формат диапазона или адреса зависимости."""
    if not isinstance(specification, str):
        message = f"{field}: версия зависимости должна быть строкой."
        raise DependencyError(message)
    if not all(character.isprintable() for character in specification):
        raise DependencyError(f"{field}: управляющие символы в версии.")
