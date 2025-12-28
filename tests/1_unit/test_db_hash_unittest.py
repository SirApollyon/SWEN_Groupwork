import unittest
from app.db import _hash_password


class HashPasswordTests(unittest.TestCase):
    def test_hash_matches_expected_output(self):
        password = "secret123"
        salt = "0123456789abcdef0123456789abcdef"

        result = _hash_password(password, salt)

        self.assertEqual(
            result,
            "4689e246f51699ea635ebd435c58d7cf812bbd0468fe402a911ed65842630c9f",
        )

    def test_hash_changes_with_salt(self):
        password = "secret123"
        salt_a = "0123456789abcdef0123456789abcdef"
        salt_b = "abcdef0123456789abcdef0123456789"

        hash_a = _hash_password(password, salt_a)
        hash_b = _hash_password(password, salt_b)

        self.assertNotEqual(hash_a, hash_b)
        self.assertEqual(len(hash_a), 64)
        self.assertEqual(len(hash_b), 64)

    def test_hash_raises_with_invalid_salt(self):
        with self.assertRaises(ValueError):
            _hash_password("secret123", "this-is-not-hex")

    def test_hash_raises_with_non_ascii_password(self):
        with self.assertRaises(ValueError):
            _hash_password("passwort漢字", "0123456789abcdef0123456789abcdef")

    def test_hash_raises_with_various_non_ascii_passwords(self):
        samples = ["漢字", "ひらがな", "привет", "🙂"]
        for sample in samples:
            with self.subTest(sample=sample):
                with self.assertRaises(ValueError):
                    _hash_password(f"pass{sample}word", "0123456789abcdef0123456789abcdef")


if __name__ == "__main__":
    unittest.main()
