"""Проверка структуры, README, файлов Git и веток по заданию."""

import ast
import re
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
MAX_FILE_LINES = 1000
MAX_TEXT_LINE = 120
STAGE_COUNT = 5
REQUIRED = ("README.md", ".gitignore", "src", "tests", "run.sh", "Makefile")
README_ASSETS = {
    Path("docs/graphs") / f"{name}.{extension}"
    for name in ("test_graph", "express") for extension in ("d2", "svg")
}
FORBIDDEN_SUFFIXES = {
    ".zip", ".tar", ".gz", ".7z", ".rar", ".pyc", ".pyo", ".so", ".dylib",
    ".exe", ".pdf", ".png", ".jpg", ".svg", ".d2",
}
FORBIDDEN_PARTS = {
    "__pycache__", "build", "dist", "node_modules", ".venv", "venv",
    ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def _git(*arguments: str) -> str:
    """Прочитать сведения Git без изменения репозитория."""
    return subprocess.check_output(
        ["git", *arguments], cwd=PROJECT_DIR, text=True, encoding="utf-8"
    )


def _check_text(path: Path) -> list[str]:
    """Отклонить бинарные файлы, длинные файлы и строки."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError:
        return [f"{path.name}: бинарный файл"]
    problems = []
    lines = text.splitlines()
    if "\x00" in text:
        problems.append(f"{path.name}: бинарные данные")
    if len(lines) > MAX_FILE_LINES:
        problems.append(f"{path.name}: больше 1000 строк")
    if any(len(line) > MAX_TEXT_LINE for line in lines):
        problems.append(f"{path.name}: строка длиннее 120 символов")
    return problems


def _check_files() -> list[str]:
    """Проверить файлы Git и новые неигнорируемые файлы."""
    filenames = _git("ls-files", "-z", "--cached", "--others",
                     "--exclude-standard").split("\x00")
    problems = []
    for filename in filter(None, filenames):
        path = Path(filename)
        if path in README_ASSETS:
            continue
        forbidden = path.suffix.lower() in FORBIDDEN_SUFFIXES
        forbidden = forbidden or bool(set(path.parts) & FORBIDDEN_PARTS)
        if forbidden or path.name == ".DS_Store":
            problems.append(f"{filename}: запрещённый тип файла")
        problems.extend(_check_text(PROJECT_DIR / path))
    return problems


def _documented_names(tree: ast.Module) -> list[str]:
    """Перечислить функции, классы и методы для сверки с README."""
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        if isinstance(node, ast.ClassDef):
            names.extend(
                f"{node.name}.{method.name}" for method in node.body
                if isinstance(method, ast.FunctionDef)
            )
    return names


def _check_documentation() -> list[str]:
    """Проверить описание каждой явно объявленной функции и класса."""
    readme = (PROJECT_DIR / "README.md").read_text(encoding="utf-8")
    problems = []
    for directory in ("src", "tests", "tools"):
        for path in sorted((PROJECT_DIR / directory).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = _documented_names(tree)
            heading = f"### `{path.relative_to(PROJECT_DIR)}`"
            section = readme.split(heading, 1)[-1].split("\n### ", 1)[0]
            for name in names:
                if heading not in readme or f"`{name}`" not in section:
                    problems.append(f"README: не описана {path.name}:{name}")
    return problems


def _check_stages() -> list[str]:
    """Проверить ветку и подробный scoped-коммит каждого этапа."""
    problems = []
    for stage in range(1, STAGE_COUNT + 1):
        branch = f"stage-{stage}"
        message = _git("log", "-1", "--format=%B", branch)
        title, _, body = message.partition("\n")
        if not re.fullmatch(rf"feat\(stage-{stage}\): .+", title):
            problems.append(f"{branch}: неверный заголовок коммита")
        if not body.strip():
            problems.append(f"{branch}: нет подробного сообщения")
    return problems


def main() -> int:
    """Выполнить проверки общих требований оформления репозитория."""
    problems = [f"Нет {name}" for name in REQUIRED
                if not (PROJECT_DIR / name).exists()]
    problems.extend(_check_files())
    problems.extend(_check_documentation())
    problems.extend(_check_stages())
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("Структура, файлы Git, README и ветки пяти этапов: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
