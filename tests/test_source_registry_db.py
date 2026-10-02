import os
import unittest
from unittest.mock import patch

from src.source_registry_db import source_key


class SourceRegistryDbTests(unittest.TestCase):
    def test_source_key_is_stable(self):
        self.assertEqual(source_key({"name": "BMW Premium Selection"}), "bmw_premium_selection")

    def test_database_url_prefers_source_specific_variable(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://generic",
                                     "SOURCE_INTELLIGENCE_DATABASE_URL": "postgres://source"}):
            from src.source_registry_db import database_url
            self.assertEqual(database_url(), "postgres://source")

    def test_database_url_falls_back_to_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://generic"}, clear=True):
            from src.source_registry_db import database_url
            self.assertEqual(database_url(), "postgres://generic")

    def test_database_disabled_without_connection_variable(self):
        with patch.dict(os.environ, {}, clear=True):
            from src.source_registry_db import enabled
            self.assertFalse(enabled())

    def test_source_key_uses_url_when_name_is_missing(self):
        self.assertEqual(source_key({"url": "https://www.example.com/cars"}), "www.example.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)
