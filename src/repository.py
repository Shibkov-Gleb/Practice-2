"""Источники зависимостей: реестр npm или локальный тестовый граф."""

__all__ = (
    "TEST_NAME_PATTERN",
    "create_dependency_loader",
    "load_test_repository",
)

import json
import re
from functools import partial
from pathlib import Path
from typing import Optional

from src.config import Config
from src.graph import DependencyLoader
from src.npm import DependencyError, fetch_direct_dependencies
from src.validation import resolve_path


TEST_NAME_PATTERN = re.compile(r"[A-Z]+")


def create_dependency_loader(
    config: Config, config_path: Path,
    versions: Optional[dict[str, str]] = None,
) -> DependencyLoader:
    """Выбрать источник данных, сохранив пути относительно XML."""
    if config.test_mode:
        path = resolve_path(config.repository, config_path.resolve().parent)
        repository = load_test_repository(path)
        return partial(_test_dependencies, repository)
    if versions is None:
        return partial(fetch_direct_dependencies, config.repository)
    return partial(
        fetch_direct_dependencies, config.repository, versions=versions
    )


def load_test_repository(path: Path) -> dict[str, list[str]]:
    """Прочитать JSON-граф и проверить его структуру и ссылки."""
    try:
        with path.open(encoding="utf-8") as stream:
            repository = json.load(stream, object_pairs_hook=_unique_pairs)
    except DependencyError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        message = f"Не удалось прочитать тестовый репозиторий: {error}"
        raise DependencyError(message) from error
    _validate_test_repository(repository)
    return repository


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    """Запретить повторяющиеся ключи в JSON-описании репозитория."""
    result = {}
    for name, dependencies in pairs:
        if name in result:
            raise DependencyError(f"Пакет {name} указан в JSON повторно.")
        result[name] = dependencies
    return result


def _validate_test_repository(repository: dict) -> None:
    """Проверить списки зависимостей и наличие всех упомянутых узлов."""
    if not isinstance(repository, dict):
        raise DependencyError("Тестовый репозиторий: ожидается JSON-объект.")
    for name, dependencies in repository.items():
        _validate_test_name(name)
        if not isinstance(dependencies, list):
            raise DependencyError(f"{name}: ожидается список зависимостей.")
        for dependency in dependencies:
            _validate_test_name(dependency)
            if dependency not in repository:
                raise DependencyError(
                    f"{name}: зависимость {dependency} не описана в JSON."
                )


def _validate_test_name(name: str) -> None:
    """Разрешить имена из одной или нескольких заглавных букв A-Z."""
    if not isinstance(name, str) or not TEST_NAME_PATTERN.fullmatch(name):
        raise DependencyError("Имена тестовых пакетов должны состоять из A-Z.")


def _test_dependencies(
    repository: dict[str, list[str]], package: str
) -> list[str]:
    """Получить зависимости из проверенного тестового графа."""
    if package not in repository:
        raise DependencyError(f"Пакет {package} отсутствует в тестовом JSON.")
    return repository[package]
