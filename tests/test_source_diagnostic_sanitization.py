"""Security regression tests for bounded, single-line parser diagnostics."""
import unittest
from src.source_adapters import _safe_diagnostic_path, _safe_diagnostic_token


class DiagnosticSanitizationTests(unittest.TestCase):
    def test_hostile_source_and_parser_are_single_line_and_bounded(self):
        for raw in ('OEM\n::error::spoof', 'dealer\r\nsecret=abc', 'evil\x1b[31m', 'x' * 500):
            result = _safe_diagnostic_token(raw)
            self.assertLessEqual(len(result), 80)
            self.assertRegex(result, r'^[A-Za-z0-9._-]+$')
            self.assertNotIn('\n', result)
            self.assertNotIn('\r', result)

    def test_url_path_excludes_secrets_and_bounds_hostile_paths(self):
        url = 'https://user:password@example.com/' + 'a' * 400 + '?token=secret#fragment'
        result = _safe_diagnostic_path(url)
        self.assertLessEqual(len(result), 120)
        self.assertTrue(result.startswith('/'))
        for secret in ('password', 'example.com', 'token', 'secret', 'fragment'):
            self.assertNotIn(secret, result)

    def test_encoded_control_characters_cannot_inject_logs(self):
        result = _safe_diagnostic_path('https://example.com/%0A%0D::error::injected')
        self.assertRegex(result, r'^[A-Za-z0-9/_-]*$')
        self.assertNotIn('%', result)

    def test_invalid_url_does_not_crash_diagnostics(self):
        self.assertEqual(_safe_diagnostic_path('http://[invalid'), '[invalid_url]')


if __name__ == '__main__':
    unittest.main()
