import unittest

from lang.type_system import TypeSyntaxError, format_type, is_known_type, parse_type


class TypeSystemTests(unittest.TestCase):
    def test_parses_optional_unions_and_nested_generics(self):
        for source, expected in (
            ("int?", "int | none"),
            ("int|string", "int | string"),
            ("dict[string,list[int | none]]", "dict[string, list[int | none]]"),
            ("tuple[int, string]", "tuple[int, string]"),
        ):
            with self.subTest(source=source):
                self.assertEqual(format_type(parse_type(source)), expected)

    def test_parses_function_types_with_nested_parameters(self):
        self.assertEqual(
            format_type(parse_type("(int, (string)->bool)->float")),
            "(int, (string) -> bool) -> float",
        )
        self.assertEqual(format_type(parse_type("()->none")), "() -> none")

    def test_checks_generic_arities_and_unknown_nested_types(self):
        for source in ("list[int, string]", "dict[int]", "list[Missing]", "tuple[]"):
            with self.subTest(source=source):
                try:
                    spec = parse_type(source)
                except TypeSyntaxError:
                    continue
                self.assertFalse(is_known_type(spec, set()))

    def test_rejects_malformed_types(self):
        for source in ("", "int |", "list[int", "(int, string)", "int??"):
            with self.subTest(source=source), self.assertRaises(TypeSyntaxError):
                parse_type(source)


if __name__ == "__main__":
    unittest.main()
