from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

from dser import Disposition
from dser.cli import main as cli_main
from dser.local import demo_payloads, run_local_decision


class LocalInterfaceTests(unittest.TestCase):
    def test_clean_scenario_acts_and_runs_the_safe_local_action(self) -> None:
        result = run_local_decision(demo_payloads()["clean"])

        self.assertEqual(result["decision"]["disposition"], Disposition.ACT.value)
        self.assertEqual(result["decision"]["selected_claim"]["value"], "shipped")
        self.assertIsNotNone(result["action"])
        self.assertFalse(result["verification_used"])
        self.assertTrue(result["memory_written"])

    def test_conflict_scenario_uses_verification_before_acting(self) -> None:
        result = run_local_decision(demo_payloads()["conflict"])

        self.assertEqual(result["decision"]["disposition"], Disposition.ACT.value)
        self.assertEqual(result["decision"]["selected_claim"]["value"], "sms")
        self.assertTrue(result["verification_used"])
        self.assertGreaterEqual(len(result["decision"]["conflicts"]), 2)
        self.assertTrue(result["memory_written"])

    def test_uncertain_scenario_asks_and_does_not_execute_or_retain(self) -> None:
        result = run_local_decision(demo_payloads()["uncertain"])

        self.assertEqual(result["decision"]["disposition"], Disposition.ASK.value)
        self.assertIsNone(result["action"])
        self.assertFalse(result["memory_written"])

    def test_memory_value_is_required_when_memory_is_enabled(self) -> None:
        payload = demo_payloads()["clean"]
        payload["include_memory"] = True
        payload["memory_value"] = ""

        with self.assertRaisesRegex(ValueError, "memory_value"):
            run_local_decision(payload)

    def test_cli_noninteractive_json_scenario_returns_success(self) -> None:
        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = cli_main(["--scenario", "clean", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"disposition": "act"', buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
