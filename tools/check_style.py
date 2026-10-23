"""Автономные проверки оформления и ограничений из задания."""

import ast
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
MAX_LINE_LENGTH = 79
MAX_DOCSTRING_LENGTH = 72
MAX_FILE_LINES = 1000
MAX_FUNCTION_LINES = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10
SOURCE_DIRECTORIES = ("src", "tests", "tools")
DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
BRANCH_TYPES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
    ast.IfExp, ast.comprehension,
)


def check_lines(lines: list[str]) -> list[str]:
    """Найти длинные строки, табуляцию и пробелы в конце строк."""
    problems = []
    if len(lines) > MAX_FILE_LINES:
        problems.append("файл длиннее 1000 строк")
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE_LENGTH:
            problems.append(f"строка {number}: больше 79 символов")
        if line != line.rstrip():
            problems.append(f"строка {number}: пробелы в конце")
        if "\t" in line:
            problems.append(f"строка {number}: табуляция")
    return problems


def estimate_complexity(node: ast.AST) -> int:
    """Посчитать ветвления, включая булевы операции и генераторы."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, BRANCH_TYPES):
            complexity += 1
        if isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def check_function(node: ast.FunctionDef) -> list[str]:
    """Проверить длину, число аргументов и оценку сложности функции."""
    problems = []
    length = node.end_lineno - node.lineno + 1
    arguments = node.args
    count = len(arguments.posonlyargs + arguments.args + arguments.kwonlyargs)
    count += int(arguments.vararg is not None)
    count += int(arguments.kwarg is not None)
    if length > MAX_FUNCTION_LINES:
        problems.append(f"{node.name}: больше 40 строк")
    if count > MAX_ARGUMENTS:
        problems.append(f"{node.name}: больше 7 аргументов")
    complexity = estimate_complexity(node)
    if complexity > MAX_COMPLEXITY:
        problems.append(f"{node.name}: оценка сложности {complexity} > 10")
    return problems


def check_docstring(node: ast.AST, lines: list[str]) -> list[str]:
    """Проверить наличие документации и длину строк docstring."""
    if ast.get_docstring(node) is None:
        name = getattr(node, "name", "модуль")
        return [f"{name}: отсутствует docstring"]
    expression = node.body[0]
    start = expression.lineno - 1
    end = expression.end_lineno
    if any(len(line) > MAX_DOCSTRING_LENGTH for line in lines[start:end]):
        return [f"строка {expression.lineno}: docstring длиннее 72 символов"]
    return []


def check_file(path: Path) -> list[str]:
    """Проверить один Python-файл средствами стандартной библиотеки."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    problems = check_lines(lines)
    if not source.endswith("\n"):
        problems.append("отсутствует перевод строки в конце файла")
    tree = ast.parse(source, filename=str(path))
    problems.extend(check_docstring(tree, lines))
    for node in ast.walk(tree):
        if isinstance(node, DEFINITION_TYPES):
            problems.extend(check_docstring(node, lines))
        if isinstance(node, FUNCTION_TYPES):
            problems.extend(check_function(node))
    return problems


def main() -> int:
    """Проверить все Python-файлы проекта без зависимостей."""
    problems = []
    for directory in SOURCE_DIRECTORIES:
        for path in sorted((PROJECT_DIR / directory).rglob("*.py")):
            relative = path.relative_to(PROJECT_DIR)
            problems.extend(
                f"{relative}: {problem}" for problem in check_file(path)
            )
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("Длина строк, docstring и ограничения задания: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
