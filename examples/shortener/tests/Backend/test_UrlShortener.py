import unittest

from Backend.CodeGenerator import CodeGenerator
from Backend.UrlShortener import UrlShortener


class SequentialCodeGenerator(CodeGenerator):
    """Deterministic generator for tests: returns codes in a fixed sequence."""

    def __init__(self, codes):
        self._codes = iter(codes)

    def generate(self):
        return next(self._codes)


class UrlShortenerTests(unittest.TestCase):
    # should return the same code when called twice with the same URL
    def test_shortening_same_url_twice_returns_same_code(self):
        shortener = UrlShortener(CodeGenerator())
        url = "https://example.com/a"
        code1 = shortener.create_short_code(url)
        code2 = shortener.create_short_code(url)
        self.assertEqual(code1, code2)

    # should return not found for an unknown short code
    def test_unknown_code_returns_not_found(self):
        shortener = UrlShortener(CodeGenerator())
        self.assertIsNone(shortener.get_url("nope00"))

    # should return the original URL for a code that was previously created
    def test_shortened_code_resolves_to_original_url(self):
        shortener = UrlShortener(CodeGenerator())
        url = "https://example.com/b"
        code = shortener.create_short_code(url)
        self.assertEqual(shortener.get_url(code), url)

    # generated codes must be unique per URL
    def test_collision_falls_back_to_a_new_code(self):
        generator = SequentialCodeGenerator(["aaaaaa", "aaaaaa", "bbbbbb"])
        shortener = UrlShortener(generator)
        code1 = shortener.create_short_code("https://example.com/one")
        code2 = shortener.create_short_code("https://example.com/two")
        self.assertNotEqual(code1, code2)
        self.assertEqual(shortener.get_url(code1), "https://example.com/one")
        self.assertEqual(shortener.get_url(code2), "https://example.com/two")


if __name__ == "__main__":
    unittest.main()
