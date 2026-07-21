from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from reference_policy import validate_record


class ReferencePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.proof = self.root / "proof.png"
        self.proof.write_bytes(b"proof")
        self.record_path = self.root / "reference.yaml"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self, **overrides):
        data = {
            "source_url": "https://example.com/article",
            "source_title": "这10句话，水象一直没说出口",
            "read_count": 100000,
            "proof": str(self.proof),
            "verified_at": "2026-07-21",
            "keep_title": True,
        }
        data.update(overrides)
        return data

    def test_verified_100k_title_is_allowed(self) -> None:
        errors = validate_record(
            self.record(),
            self.record_path,
            expected_title="这10句话，水象一直没说出口",
            check_url=False,
        )
        self.assertEqual(errors, [])

    def test_99999_is_rejected(self) -> None:
        errors = validate_record(self.record(read_count=99999), self.record_path, check_url=False)
        self.assertTrue(any("低于原标题保留线" in item for item in errors))

    def test_missing_proof_is_rejected(self) -> None:
        errors = validate_record(
            self.record(proof=str(self.root / "missing.png")),
            self.record_path,
            check_url=False,
        )
        self.assertTrue(any("证明不存在" in item for item in errors))

    def test_mismatched_title_is_rejected(self) -> None:
        errors = validate_record(
            self.record(),
            self.record_path,
            expected_title="另一个标题",
            check_url=False,
        )
        self.assertTrue(any("标题与参考记录" in item for item in errors))

    def test_non_retained_title_does_not_need_proof(self) -> None:
        errors = validate_record(
            self.record(read_count=17000, proof="", keep_title=False),
            self.record_path,
            check_url=False,
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
