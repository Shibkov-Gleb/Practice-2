"""Демонстрация трёх SVG и сравнение с npm, отдельно от приложения."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.config import load_config
from src.graph import build_dependency_graph
from src.presentation import present_graph
from src.repository import create_dependency_loader


PROJECT_DIR = Path(__file__).resolve().parents[1]
SUCCESS = 0
COMMAND_TIMEOUT = 60
CASES = ("visual_is_number.xml", "visual_is_odd.xml", "visual_types_node.xml")


def _npm(arguments: list[str], directory: Path) -> str:
    """Вызвать npm только для независимого сравнения результатов."""
    executable = os.environ.get("NPM_BIN", "npm")
    result = subprocess.run(
        [executable, *arguments], cwd=directory, capture_output=True,
        text=True, encoding="utf-8", timeout=COMMAND_TIMEOUT, check=False,
    )
    if result.returncode != SUCCESS:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def _native_tree(package: str, directory: Path) -> tuple[dict, str]:
    """Построить lockfile без скриптов и получить штатное дерево npm."""
    manifest = {
        "name": "practice2-comparison", "version": "1.0.0", "private": True,
        "dependencies": {package: "latest"},
    }
    (directory / "package.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    _npm([
        "install", "--package-lock-only", "--ignore-scripts",
        "--no-audit", "--no-fund", "--registry=https://registry.npmjs.org",
    ], directory)
    arguments = ["ls", "--all", "--package-lock-only", "--omit=dev"]
    tree = json.loads(_npm([*arguments, "--json"], directory))
    display = _npm([*arguments, "--unicode=false"], directory)
    return tree["dependencies"][package], display


def _tree_edges(package: str, tree: dict) -> tuple[set, set, dict]:
    """Свести логическое дерево npm к именам и направленным рёбрам."""
    nodes = set()
    edges = set()
    versions = {}
    stack = [(package, tree)]
    while stack:
        name, current = stack.pop()
        nodes.add(name)
        versions.setdefault(name, set()).add(current.get("version", "?"))
        for dependency, child in current.get("dependencies", {}).items():
            edges.add((name, dependency))
            stack.append((dependency, child))
    return nodes, edges, versions


def _compare_case(filename: str, directory: Path) -> list[str]:
    """Создать D2/SVG, показать дерево и сравнить узлы и рёбра."""
    path = PROJECT_DIR / "examples" / filename
    config = load_config(path)
    graph = build_dependency_graph(
        config.package, create_dependency_loader(config, path),
        config.filter_substring,
    )
    print(present_graph(config, path, graph), flush=True)
    native, display = _native_tree(config.package, directory)
    nodes, edges, versions = _tree_edges(config.package, native)
    own_edges = {(name, dep) for name, deps in graph.items() for dep in deps}
    same = set(graph) == nodes and own_edges == edges
    print(display, flush=True)
    print(f"Совпадение имён и рёбер: {same}", flush=True)
    return [
        f"## {config.package}", "", "```text", display, "```", "",
        f"Граф приложения: {len(graph)} узлов, {len(own_edges)} рёбер.",
        f"Совпадение имён и рёбер с npm: `{same}`.", "",
        "Версии в npm: " + json.dumps(
            {name: sorted(values) for name, values in versions.items()}
        ), "",
        "Только в приложении: " + repr(sorted(own_edges - edges)),
        "Только в npm: " + repr(sorted(edges - own_edges)), "",
        f"Файлы: `output/{Path(config.output_file).name}` "
        "и соответствующий D2.",
        "",
    ]


def main() -> int:
    """Сравнить три графа и сохранить локальный протокол."""
    output = PROJECT_DIR / "output"
    output.mkdir(exist_ok=True)
    try:
        version = _npm(["--version"], PROJECT_DIR)
        report = ["# Фактическое сравнение с npm", "", f"npm: {version}", ""]
        for filename in CASES:
            with tempfile.TemporaryDirectory() as directory:
                report.extend(_compare_case(filename, Path(directory)))
        (output / "comparison.md").write_text(
            "\n".join(report), encoding="utf-8"
        )
    except (
        OSError, ValueError, RuntimeError, subprocess.SubprocessError
    ) as error:
        print(f"Ошибка демонстрации: {error}", file=sys.stderr)
        return 1
    return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
