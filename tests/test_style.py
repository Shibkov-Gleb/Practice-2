"""Регрессионные проверки ограничений оформления из задания."""

import ast
import tempfile
import unittest
from pathlib import Path

from tools.check_style import (
    MAX_DOCSTRING_LENGTH,
    MAX_LINE_LENGTH,
    check_comments,
    check_file,
    check_lines,
    check_numeric_comparisons,
)


class StyleTests(unittest.TestCase):
    """Проверить обнаружение нарушений и пограничные случаи."""

    def test_line_length_boundary(self) -> None:
        """Разрешить 79 символов и отклонить более длинную строку."""
        self.assertEqual(check_lines(["x" * MAX_LINE_LENGTH]), [])
        self.assertTrue(check_lines(["x" * (MAX_LINE_LENGTH + 1)]))

    def test_whitespace(self) -> None:
        """Отклонить табуляцию и пробелы в конце строки."""
        self.assertTrue(check_lines(["value = 1 "]))
        self.assertTrue(check_lines(["\tvalue = 1"]))

    def test_comment_length_boundary(self) -> None:
        """Применить к комментариям отдельный предел 72 символа."""
        comment = "# " + "x" * (MAX_DOCSTRING_LENGTH - 2)
        self.assertEqual(check_comments(comment + "\n"), [])
        self.assertTrue(check_comments(comment + "x\n"))

    def test_hash_inside_string(self) -> None:
        """Не принимать решётку внутри строки за комментарий."""
        source = 'value = "#' + "x" * MAX_DOCSTRING_LENGTH + '"\n'
        self.assertEqual(check_comments(source), [])

    def test_numeric_comparisons(self) -> None:
        """Находить положительные, отрицательные и вложенные числа."""
        sources = ("value > 2", "value == -1", "value + 1 < limit")
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(check_numeric_comparisons(ast.parse(source)))

    def test_named_limits_and_singletons(self) -> None:
        """Разрешить именованные пределы, булевы значения и None."""
        source = "value > LIMIT\nvalue is None\nvalue is True\nvalue == '2'"
        self.assertEqual(check_numeric_comparisons(ast.parse(source)), [])

    def test_file_check_includes_magic_numbers(self) -> None:
        """Проверка целого файла должна применять правило М1."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text('"""Example."""\nvalue = count > 2\n')
            self.assertIn("строка 2: число в сравнении", check_file(path))

    def test_valid_file(self) -> None:
        """Принять документированный файл без нарушений ограничений."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text('"""Example."""\nLIMIT = 2\n')
            self.assertEqual(check_file(path), [])
