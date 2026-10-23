"""Загрузка шести параметров первого этапа из XML-файла."""

from dataclasses import dataclass, fields
from pathlib import Path
from xml.etree import ElementTree

from src.validation import (
    ConfigError,
    parse_boolean,
    validate_filter,
    validate_output,
    validate_package,
    validate_repository,
)


@dataclass(frozen=True)
class Config:
    """Проверенные настройки приложения, неизменяемые после загрузки."""

    package: str
    repository: str
    test_mode: bool
    output_file: str
    ascii_tree: bool
    filter_substring: str


FIELD_NAMES = tuple(field.name for field in fields(Config))


def load_config(path: Path) -> Config:
    """Прочитать XML и проверить параметры относительно его каталога."""
    try:
        path = path.resolve()
        root = ElementTree.parse(path).getroot()
        values = _read_fields(root)
        return _build_config(values, path.parent)
    except ConfigError:
        raise
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        message = f"Не удалось прочитать конфигурацию: {error}"
        raise ConfigError(message) from error
    except ElementTree.ParseError as error:
        raise ConfigError(f"Некорректный XML: {error}") from error


def _read_fields(root: ElementTree.Element) -> dict[str, str]:
    """Проверить структуру XML, обязательные и повторяющиеся поля."""
    _validate_root(root)
    values = {}
    for element in root:
        name = element.tag
        if name not in FIELD_NAMES:
            raise ConfigError(f"Неизвестный параметр: {name}.")
        if name in values:
            raise ConfigError(f"{name}: параметр указан повторно.")
        _validate_element(element)
        values[name] = (element.text or "").strip()
    missing = [name for name in FIELD_NAMES if name not in values]
    if missing:
        raise ConfigError(f"Отсутствуют параметры: {', '.join(missing)}.")
    return values


def _validate_root(root: ElementTree.Element) -> None:
    """Проверить имя корневого элемента и отсутствие лишнего текста."""
    if root.tag != "config" or root.attrib:
        raise ConfigError("Нужен корневой элемент <config> без атрибутов.")
    if root.text and root.text.strip():
        raise ConfigError("Внутри <config> допустимы только параметры.")


def _validate_element(element: ElementTree.Element) -> None:
    """Запретить вложенные элементы, атрибуты и лишний текст."""
    if element.attrib or len(element):
        raise ConfigError(f"{element.tag}: нужен текст без атрибутов и тегов.")
    if element.tail and element.tail.strip():
        raise ConfigError(f"{element.tag}: лишний текст после параметра.")


def _build_config(values: dict[str, str], base_path: Path) -> Config:
    """Преобразовать строки в проверенные настройки."""
    test_mode = parse_boolean(values["test_mode"], "test_mode")
    return Config(
        package=validate_package(values["package"]),
        repository=validate_repository(
            values["repository"], test_mode, base_path
        ),
        test_mode=test_mode,
        output_file=validate_output(values["output_file"], base_path),
        ascii_tree=parse_boolean(values["ascii_tree"], "ascii_tree"),
        filter_substring=validate_filter(values["filter_substring"]),
    )
