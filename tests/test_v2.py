from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_evals
import progress
import report
import soft_verifier
import benchmark


def git(root: Path, *args: str) -> str:
    cp = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=True)
    return cp.stdout.strip()


class EvalGeneratorTests(unittest.TestCase):
    def test_generates_hidden_history_eval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "config", "user.email", "test@example.com")
            git(root, "config", "user.name", "Test")
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            git(root, "add", "app.py")
            git(root, "commit", "-m", "initial")
            parent = git(root, "rev-parse", "HEAD")
            (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
            git(root, "add", "app.py")
            git(root, "commit", "-m", "fix: return the correct value")
            head = git(root, "rev-parse", "HEAD")

            rows = generate_evals.history_evals(root, limit=1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["base_ref"], parent)
            self.assertEqual(rows[0]["oracle"]["target_ref"], head)
            self.assertIn("correct value", rows[0]["prompt"])
            self.assertNotIn(head, rows[0]["prompt"])


class SoftVerifierTests(unittest.TestCase):
    def test_hard_failure_caps_soft_signal(self):
        out = soft_verifier.heuristic_score(
            "fix bug",
            "All tests passed and verified",
            {"overall_status": "FAIL"},
        )
        self.assertLess(out["score"], 0.5)

    def test_hard_pass_and_evidence_scores_higher(self):
        low = soft_verifier.heuristic_score("fix bug", "", {"overall_status": "UNKNOWN"})
        high = soft_verifier.heuristic_score("fix bug", "tests passed; git diff verified", {"overall_status": "PASS"})
        self.assertGreater(high["score"], low["score"])


class ProgressPolicyTests(unittest.TestCase):
    def test_done_requires_hard_pass_and_high_soft_score(self):
        self.assertEqual(progress.decide([0.91], "PASS")["action"], "DONE")
        self.assertNotEqual(progress.decide([0.91], "UNKNOWN")["action"], "DONE")

    def test_repeated_hard_failure_replans(self):
        self.assertEqual(progress.decide([0.4], "FAIL", repeated_failure_count=3)["action"], "REPLAN")

    def test_plateau_resamples(self):
        self.assertEqual(progress.decide([0.5, 0.51, 0.505], "PASS")["action"], "RESAMPLE")


class ReportTests(unittest.TestCase):
    def test_summarizes_paired_results(self):
        s = report.summarize([
            {"task_id": "a", "mode": "direct", "success": False, "elapsed_seconds": 1, "soft_score": 0.5},
            {"task_id": "a", "mode": "amplified", "success": True, "elapsed_seconds": 2, "soft_score": 0.9},
        ])
        self.assertEqual(s["direct"]["pass_rate"], 0.0)
        self.assertEqual(s["amplified"]["pass_rate"], 1.0)
        self.assertEqual(s["improvement"]["absolute_pass_rate"], 1.0)


class BenchmarkSmokeTests(unittest.TestCase):
    def test_runs_isolated_direct_and_amplified_worktrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (repo / ".coding-amplifier.json").write_text(json.dumps({"commands": {"compile": [sys.executable, "-m", "compileall", "-q", "."], "test": None, "lint": None, "typecheck": None}}), encoding="utf-8")
            git(repo, "add", "app.py", ".coding-amplifier.json")
            git(repo, "commit", "-m", "base")
            ref = git(repo, "rev-parse", "HEAD")

            fake = base / "fake_agent.py"
            fake.write_text(textwrap.dedent("""
                from pathlib import Path
                import sys
                root = Path(sys.argv[1])
                (root / 'app.py').write_text('VALUE = 2\\n', encoding='utf-8')
                print('tests verified')
            """), encoding="utf-8")
            task = {
                "id": "smoke",
                "prompt": "change value to 2",
                "base_ref": ref,
                "criteria": [{"id": "correctness", "name": "Correctness"}],
                "oracle": {"changed_files": ["app.py"]},
            }
            result = benchmark.run_benchmark(
                repo,
                [task],
                [sys.executable, str(fake), "{workspace}"],
                timeout=30,
                verify_timeout=30,
                soft_threshold=0.5,
            )
            self.assertEqual(len(result["runs"]), 2)
            self.assertTrue(all(r["success"] for r in result["runs"]))
            self.assertEqual({r["mode"] for r in result["runs"]}, {"direct", "amplified"})


if __name__ == "__main__":
    unittest.main()
