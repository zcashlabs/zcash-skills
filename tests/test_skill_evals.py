import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_evals", ROOT / "evals/run.py")
evals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evals)


class SkillEvalTests(unittest.TestCase):
    def test_paired_workspaces_share_source_but_baseline_has_no_skill_or_rubric(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            (source / "README.md").write_text("Tracked public source\n")
            installed = source / ".agents/skills/leak"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("Installed skill contamination\n")
            rubric = source / "evals"
            rubric.mkdir()
            (rubric / "rubric.json").write_text('{"answer": "HIDDEN ANSWER"}\n')
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run([
                "git", "-C", str(source), "-c", "user.name=Eval Test",
                "-c", "user.email=eval@example.invalid", "commit", "-qm", "fixture",
            ], check=True)
            revision = subprocess.check_output([
                "git", "-C", str(source), "rev-parse", "HEAD",
            ], text=True).strip()
            (source / "README.md").write_text("Uncommitted contamination\n")
            (source / "secret.txt").write_text("Untracked contamination\n")
            skills = root / "skills" / "example"
            skills.mkdir(parents=True)
            (skills / "SKILL.md").write_text(
                "---\nname: example\ndescription: Use when testing.\n---\nCandidate instructions\n"
            )
            suite = {
                "source_revision": revision,
                "tasks": [{"id": "case", "prompt": "Investigate the problem.",
                           "skills": ["example"], "checks": {"hidden": "HIDDEN ANSWER"}}],
                "triggers": [],
            }
            out = root / "out"
            evals.prepare(source, out, suite, skills.parent)
            baseline = out / "case/without-skill"
            treatment = out / "case/with-skill"
            for workspace in (baseline, treatment):
                self.assertEqual((workspace / "README.md").read_text(), "Tracked public source\n")
                self.assertFalse((workspace / "secret.txt").exists())
                self.assertFalse((workspace / ".agents").exists())
                self.assertFalse((workspace / "evals").exists())
                self.assertNotIn("HIDDEN ANSWER", (workspace / "TASK.txt").read_text())
            self.assertFalse((baseline / "candidate-skills").exists())
            self.assertTrue((treatment / "candidate-skills/example/SKILL.md").is_file())
            self.assertNotIn("Candidate instructions", (baseline / "TASK.txt").read_text())
            self.assertEqual(
                json.loads((baseline / "manifest.json").read_text())["source_sha256"],
                json.loads((treatment / "manifest.json").read_text())["source_sha256"],
            )
            with self.assertRaises(FileExistsError):
                evals.prepare(source, out, suite, skills.parent)

    def test_routing_counts_missing_duplicate_extra_and_near_miss_selections_as_failures(self):
        cases = [
            {"id": "positive", "required": ["ths-runtime"], "allowed": ["ths-runtime", "ths"]},
            {"id": "near-miss", "required": [], "allowed": []},
        ]
        self.assertEqual(evals.score_routing(cases, {"selections": [
            {"id": "positive", "skills": ["ths-runtime"]},
            {"id": "near-miss", "skills": []},
        ]})["passed"], 2)
        for response in (
            {"selections": [{"id": "positive", "skills": []}, {"id": "near-miss", "skills": ["ths"]}]},
            {"selections": []},
            {"selections": [{"id": "positive", "skills": ["ths-runtime"]}] * 2},
            {"selections": [{"id": "unknown", "skills": []}]},
            {"selections": [{"id": "positive", "skills": ["ths-runtime"]}, {"id": "near-miss"}]},
        ):
            self.assertFalse(evals.score_routing(cases, response)["complete_pass"])

    def test_manual_grades_require_every_check_and_review_evidence(self):
        checks = {"identity": "Preserves the original operation", "oracle": "Names an observable oracle"}
        self.assertEqual(evals.score_checks(checks, {
            "identity": {"pass": True, "evidence": "answer lines 2-3"},
            "oracle": {"pass": False, "evidence": "answer omits chain inclusion"},
        }), {"passed": 1, "total": 2, "complete_pass": False})
        for grades in ({}, {"identity": {"pass": True, "evidence": ""}},
                       {"identity": {"pass": "true", "evidence": "line 2"}},
                       {"identity": {"pass": True, "evidence": None},
                        "oracle": {"pass": True, "evidence": "line 3"}}):
            with self.assertRaises(ValueError):
                evals.score_checks(checks, grades)

    def test_comparison_rejects_incomplete_tampered_or_unmatched_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = {"id": "case", "prompt": "Inspect source.", "skills": ["example"],
                    "checks": {"identity": "Preserve identity"}}
            evals.write_json(root / "suite.json", {"tasks": [task],
                             "source_revision": "same-revision", "skills_sha256": "candidate-tree"})
            grades = {}
            for arm in ("without-skill", "with-skill"):
                artifact = root / "case" / arm
                artifact.mkdir(parents=True)
                (artifact / "answer.txt").write_text("Observed answer\n")
                prompt = evals.task_prompt(task, arm)
                (artifact / "TASK.txt").write_text(prompt)
                manifest = {
                    "case": "case", "arm": arm, "source_revision": "same-revision",
                    "source_sha256": "same-tree", "skills_sha256": "candidate-tree" if arm == "with-skill" else None,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                }
                evals.write_json(artifact / "manifest.json", manifest)
                evals.write_json(artifact / "receipt.json", {
                    **manifest,
                    "status": "completed", "model": "same-model", "reasoning_effort": "high",
                    "cli_version": "same-cli",
                    "answer_sha256": hashlib.sha256(b"Observed answer\n").hexdigest(),
                })
                grades[f"case/{arm}"] = {
                    "answer_sha256": hashlib.sha256(b"Observed answer\n").hexdigest(),
                    "checks": {"identity": {"pass": True, "evidence": "answer line 1"}},
                }
            receipt_path = root / "case/with-skill/receipt.json"
            self.assertEqual(evals.score_tasks(root, grades)["with_minus_without"], {"case": 0})
            receipt = evals.read_json(receipt_path)
            for changed in ({"status": "timeout"}, {"model": "different-model"},
                            {"answer_sha256": "changed"}, {"case": "wrong-case"}, {"arm": "wrong-arm"},
                            {"source_revision": "wrong-revision"}):
                evals.write_json(receipt_path, {**receipt, **changed})
                with self.assertRaises(ValueError):
                    evals.score_tasks(root, grades)
            evals.write_json(receipt_path, receipt)
            grades["case/with-skill"]["answer_sha256"] = "older-answer"
            with self.assertRaises(ValueError):
                evals.score_tasks(root, grades)

    def test_routing_capture_is_bound_to_the_frozen_request_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "routing"
            artifact.mkdir()
            prompt = "Choose skills for this frozen request."
            answer = '{"selections":[{"id":"route-01","skills":[]}]}'
            manifest = {"case": "routing", "arm": "catalog-only", "skills_sha256": "same-skills",
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
            (artifact / "TASK.txt").write_text(prompt)
            (artifact / "answer.txt").write_text(answer)
            evals.write_json(artifact / "manifest.json", manifest)
            evals.write_json(artifact / "receipt.json", {**manifest, "status": "completed",
                             "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()})
            suite = {"skills_sha256": "same-skills", "routing_prompt_sha256": manifest["prompt_sha256"],
                     "triggers": [{"id": "route-01", "required": [], "allowed": []}]}
            evals.write_json(root / "suite.json", suite)
            self.assertTrue(evals.score_routing_run(root)["complete_pass"])
            evals.write_json(root / "suite.json", {**suite, "routing_prompt_sha256": "different-requests"})
            with self.assertRaises(ValueError):
                evals.score_routing_run(root)


if __name__ == "__main__":
    unittest.main()
