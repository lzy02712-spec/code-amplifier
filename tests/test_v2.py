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

import benchmark
import generate_evals
import hidden_grader
import progress
import report
import soft_verifier


def git(root: Path, *args: str) -> str:
    cp = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=True)
    return cp.stdout.strip()


def init_history_repo(root: Path) -> tuple[str, str]:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_existing.py").write_text(textwrap.dedent("""
        import unittest
        import app

        class ExistingTests(unittest.TestCase):
            def test_value_is_positive(self):
                self.assertGreater(app.VALUE, 0)
    """).strip() + "\n", encoding="utf-8")
    (root / ".coding-amplifier.json").write_text(json.dumps({
        "commands": {
            "compile": [sys.executable, "-m", "compileall", "-q", "."],
            "test": [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            "lint": None,
            "typecheck": None,
        }
    }), encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    parent = git(root, "rev-parse", "HEAD")

    (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "tests" / "test_value.py").write_text(textwrap.dedent("""
        import unittest
        import app

        class ValueTests(unittest.TestCase):
            def test_value(self):
                self.assertEqual(app.VALUE, 2)
    """).strip() + "\n", encoding="utf-8")
    git(root, "add", "app.py", "tests/test_value.py")
    git(root, "commit", "-m", "fix: return the correct value")
    head = git(root, "rev-parse", "HEAD")
    return parent, head


class EvalGeneratorTests(unittest.TestCase):
    def test_generates_hidden_history_eval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, head = init_history_repo(root)
            rows = generate_evals.history_evals(root, limit=1, require_hidden_tests=True)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["base_ref"], parent)
            self.assertEqual(rows[0]["oracle"]["target_ref"], head)
            self.assertIn("correct value", rows[0]["prompt"])
            self.assertNotIn(head, rows[0]["prompt"])
            self.assertEqual(rows[0]["oracle"]["grader"]["hidden_test_files"], ["tests/test_value.py"])

    def test_require_hidden_tests_filters_non_test_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "config", "user.email", "test@example.com")
            git(root, "config", "user.name", "Test")
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            git(root, "add", "app.py")
            git(root, "commit", "-m", "initial")
            (root / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
            git(root, "add", "app.py")
            git(root, "commit", "-m", "fix: value")
            self.assertEqual(generate_evals.history_evals(root, limit=1, require_hidden_tests=True), [])


class HiddenGraderTests(unittest.TestCase):
    def test_oracle_must_fail_on_base_and_pass_on_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, _ = init_history_repo(root)
            task = generate_evals.history_evals(root, limit=1, require_hidden_tests=True)[0]
            validation = hidden_grader.validate_oracle(root, task, timeout=30)
            self.assertEqual(validation["status"], "VALID")
            self.assertEqual(validation["base_status"], "FAIL")
            self.assertEqual(validation["target_status"], "PASS")

            with tempfile.TemporaryDirectory() as work:
                ws = Path(work) / "workspace"
                git(root, "worktree", "add", "--detach", str(ws), parent)
                try:
                    (ws / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
                    grade = hidden_grader.grade_workspace(root, ws, task, validation, timeout=30)
                    self.assertEqual(grade["status"], "PASS")
                finally:
                    subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(ws)], check=False)
                    subprocess.run(["git", "-C", str(root), "worktree", "prune"], check=False)


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
    def test_summarizes_paired_strict_results(self):
        s = report.summarize([
            {"task_id": "a", "mode": "direct", "gradable": True, "success": False, "provisional_success": True, "elapsed_seconds": 1, "soft_score": 0.8},
            {"task_id": "a", "mode": "amplified", "gradable": True, "success": True, "provisional_success": True, "elapsed_seconds": 2, "soft_score": 0.9},
        ])
        self.assertEqual(s["direct"]["pass_rate"], 0.0)
        self.assertEqual(s["amplified"]["pass_rate"], 1.0)
        self.assertEqual(s["improvement"]["absolute_pass_rate"], 1.0)
        self.assertEqual(s["paired"]["amplifier_wins"], 1)

    def test_ungradable_runs_do_not_enter_strict_denominator(self):
        s = report.summarize([
            {"task_id": "a", "mode": "direct", "gradable": False, "success": None, "provisional_success": True, "elapsed_seconds": 1, "soft_score": 0.8},
        ])
        self.assertEqual(s["direct"]["gradable_runs"], 0)
        self.assertEqual(s["direct"]["ungradable_runs"], 1)
        self.assertEqual(s["direct"]["pass_rate"], 0.0)


class BenchmarkSmokeTests(unittest.TestCase):
    def test_runs_strict_hidden_grader_for_direct_and_amplified(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_history_repo(repo)
            task = generate_evals.history_evals(repo, limit=1, require_hidden_tests=True)[0]

            fake = base / "fake_agent.py"
            fake.write_text(textwrap.dedent("""
                from pathlib import Path
                import sys
                root = Path(sys.argv[1])
                (root / 'app.py').write_text('VALUE = 2\\n', encoding='utf-8')
                print('tests verified')
            """), encoding="utf-8")
            result = benchmark.run_benchmark(
                repo,
                [task],
                [sys.executable, str(fake), "{workspace}"],
                timeout=30,
                verify_timeout=30,
                soft_threshold=0.5,
            )
            self.assertEqual(len(result["runs"]), 2)
            self.assertTrue(all(r["gradable"] for r in result["runs"]))
            self.assertTrue(all(r["success"] for r in result["runs"]))
            self.assertTrue(all(r["hidden_status"] == "PASS" for r in result["runs"]))
            self.assertEqual({r["mode"] for r in result["runs"]}, {"direct", "amplified"})


if __name__ == "__main__":
    unittest.main()
