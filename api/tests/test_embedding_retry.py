import unittest

from services.embedding_retry import compute_retry_delay_seconds


class EmbeddingRetryTests(unittest.TestCase):
    def test_exponential_growth(self) -> None:
        self.assertEqual(compute_retry_delay_seconds(1, 60), 60)
        self.assertEqual(compute_retry_delay_seconds(2, 60), 120)
        self.assertEqual(compute_retry_delay_seconds(3, 60), 240)

    def test_delay_cap(self) -> None:
        self.assertEqual(compute_retry_delay_seconds(10, 60, max_seconds=3600), 3600)


if __name__ == "__main__":
    unittest.main()
