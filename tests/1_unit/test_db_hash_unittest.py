import unittest

from app.db import _hash_password


class HashPasswordTests(unittest.TestCase):
    def test_hash_matches_expected_output(self):
        # Fester Input -> fester, erwarteter Hash.
        password = "secret123"
        salt = "0123456789abcdef0123456789abcdef"

        result = _hash_password(password, salt)

        self.assertEqual(
            result,
            "4689e246f51699ea635ebd435c58d7cf812bbd0468fe402a911ed65842630c9f",
        )

    def test_hash_changes_with_salt(self):
        # Gleiches Passwort, anderer Salt -> anderer Hash; Länge bleibt 64 Hex-Zeichen.
        password = "secret123"
        salt_a = "0123456789abcdef0123456789abcdef"
        salt_b = "abcdef0123456789abcdef0123456789"

        hash_a = _hash_password(password, salt_a)
        hash_b = _hash_password(password, salt_b)

        self.assertNotEqual(hash_a, hash_b)
        self.assertEqual(len(hash_a), 64)
        self.assertEqual(len(hash_b), 64)

    def test_hash_raises_with_invalid_salt(self):
        # Ungültiger Salt muss Fehler werfen.
        password = "secret123"
        salt = "this-is-not-hex"

        with self.assertRaises(ValueError):
            _hash_password(password, salt)


if __name__ == "__main__":
    unittest.main()
