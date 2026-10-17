#!/usr/bin/env python3
"""Prepare paired skill evaluations, capture Codex runs, and validate review scores."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import tarfile
import time


ROOT = Path(__file__).resolve().parents[1]
SUITE = Path(__file__).with_name("cases.json")
ARMS = ("without-skill", "with-skill")
SOURCE_PATHS = (
    "AGENTS.md", "README.md", "CONTRIBUTING.md", "RELEASING.md", "Cargo.toml",
    "Cargo.lock", "rust-toolchain.toml", "crates", "web", "book", "docker",
    "Dockerfile", "install.sh", "tests", ".github",
)
COMMON = """Work only inside this evaluation workspace. Read AGENTS.md when present.
Use local source inspection tools. Do not access network services, installed skills,
other checkouts, parent directories, or evaluation rubrics. Do not edit files or run
builds, package managers, Docker, or tests. Return a concise, source-grounded answer
with paths/symbols and proposed validation, clearly separating observations from
unexecuted tests. Do not ask follow-up questions.
"""


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def digest_tree(path, exclude=()):
    digest = hashlib.sha256()
    for item in sorted(Path(path).rglob("*")):
        if item.is_file() and item.relative_to(path).parts[0] not in exclude:
            digest.update(item.relative_to(path).as_posix().encode() + b"\0")
            digest.update(item.read_bytes() + b"\0")
    return digest.hexdigest()


def skill_catalog(skills):
    entries = []
    for path in sorted(Path(skills).glob("*/SKILL.md")):
        frontmatter = path.read_text().split("---", 2)[1]
        fields = dict(line.split(":", 1) for line in frontmatter.splitlines() if ":" in line)
        entries.append({key: fields[key].strip() for key in ("name", "description")})
    return entries


def task_prompt(task, arm):
    prompt = COMMON + "\n" + task["prompt"] + "\n"
    if arm == "with-skill":
        prompt += "\nBefore investigating, read these candidate skills and follow their relevant references:\n"
        prompt += "\n".join(f"candidate-skills/{name}/SKILL.md" for name in task["skills"]) + "\n"
    return prompt


def prepare(source, out, suite=None, skills=None):
    suite = suite if suite is not None else read_json(SUITE)
    skills = Path(skills) if skills is not None else ROOT / "skills"
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    revision = suite["source_revision"]
    tracked = subprocess.check_output([
        "git", "-C", str(source), "ls-tree", "--name-only", revision,
    ], text=True).splitlines()
    included = [path for path in SOURCE_PATHS if path in tracked]
    if not included:
        raise ValueError("No evaluation source paths found at the pinned revision")
    archive = subprocess.check_output([
        "git", "-C", str(source), "archive", "--format=tar", revision, "--", *included,
    ])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            parts = PurePosixPath(member.name).parts
            if member.name.startswith("/") or ".." in parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
        source_tree = out / "source"
        source_tree.mkdir()
        tar.extractall(source_tree)
    source_hash = digest_tree(source_tree)
    skill_hash = digest_tree(skills)
    for task in suite["tasks"]:
        for arm in ARMS:
            workspace = out / task["id"] / arm
            shutil.copytree(source_tree, workspace)
            prompt = task_prompt(task, arm)
            if arm == "with-skill":
                shutil.copytree(skills, workspace / "candidate-skills")
            (workspace / "TASK.txt").write_text(prompt)
            write_json(workspace / "manifest.json", {
                "case": task["id"], "arm": arm, "source_revision": revision,
                "source_sha256": source_hash,
                "skills_sha256": skill_hash if arm == "with-skill" else None,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            })
    routing = out / "routing"
    routing.mkdir()
    prompt = (
        "Select the smallest useful set of skills from this name/description catalog for each request. "
        "Use [] when none applies. Judge the actual task, not isolated keyword matches. "
        "Do not inspect files or use tools. Return JSON only: "
        '{"selections":[{"id":"request-id","skills":["skill-name"]}]}.\n\n'
        + json.dumps({"catalog": skill_catalog(skills), "requests": [
            {"id": case["id"], "prompt": case["prompt"]} for case in suite["triggers"]
        ]}, indent=2)
    )
    (routing / "TASK.txt").write_text(prompt)
    write_json(routing / "manifest.json", {
        "case": "routing", "arm": "catalog-only", "skills_sha256": skill_hash,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    })
    write_json(out / "suite.json", {**suite, "skills_sha256": skill_hash,
                                    "routing_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
    shutil.rmtree(source_tree)
    return out


def score_routing(cases, response):
    selections = response.get("selections", [])
    ids = [item.get("id") for item in selections]
    expected = {case["id"] for case in cases}
    valid = len(ids) == len(set(ids)) and set(ids) == expected
    results = {}
    for case in cases:
        matching = [item for item in selections if item.get("id") == case["id"]]
        skills = matching[0].get("skills") if len(matching) == 1 else None
        passed = (len(matching) == 1 and isinstance(skills, list)
                  and all(isinstance(name, str) for name in skills)
                  and len(skills) == len(set(skills))
                  and set(case["required"]) <= set(skills) <= set(case["allowed"]))
        results[case["id"]] = passed
    return {"passed": sum(results.values()), "total": len(cases),
            "complete_pass": valid and all(results.values()), "cases": results}


def score_checks(checks, grades):
    if set(checks) != set(grades):
        raise ValueError("Every rubric check must be graded exactly once")
    for grade in grades.values():
        if (type(grade.get("pass")) is not bool
                or not isinstance(grade.get("evidence"), str) or not grade["evidence"].strip()):
            raise ValueError("Each grade requires a boolean pass and nonempty review evidence")
    passed = sum(grade["pass"] for grade in grades.values())
    return {"passed": passed, "total": len(checks), "complete_pass": passed == len(checks)}


def capture(workspace, artifact, model, effort, timeout):
    workspace, artifact = Path(workspace).resolve(), Path(artifact).resolve()
    artifact.mkdir(parents=True, exist_ok=False)
    command = [
        "codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "read-only", "-c", "skills.max_context_tokens=1",
        "-c", "project_doc_max_bytes=0", "-c", "web_search=\"disabled\"",
        "--model", model, "-c", f'model_reasoning_effort="{effort}"',
        "--json", "--color", "never", "-C", str(workspace),
        "-o", str(artifact / "answer.txt"), "-",
    ]
    prompt = (workspace / "TASK.txt").read_text()
    manifest = read_json(workspace / "manifest.json")
    shutil.copyfile(workspace / "manifest.json", artifact / "manifest.json")
    shutil.copyfile(workspace / "TASK.txt", artifact / "TASK.txt")
    if hashlib.sha256(prompt.encode()).hexdigest() != manifest["prompt_sha256"]:
        raise ValueError("Task prompt changed after preparation")
    if "source_sha256" in manifest:
        if digest_tree(workspace, ("TASK.txt", "manifest.json", "candidate-skills")) != manifest["source_sha256"]:
            raise ValueError("Source changed after preparation")
        candidates = workspace / "candidate-skills"
        if manifest["skills_sha256"] is None:
            if candidates.exists():
                raise ValueError("Baseline contains candidate skills")
        elif digest_tree(candidates) != manifest["skills_sha256"]:
            raise ValueError("Candidate skills changed after preparation")
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    status = "error"
    with (artifact / "trace.jsonl").open("w") as trace, (artifact / "stderr.txt").open("w") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=trace, stderr=errors,
                                   text=True, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            status = "timeout"
    events = []
    for line in (artifact / "trace.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    completed = [event for event in events if event.get("type") == "turn.completed"]
    answer = artifact / "answer.txt"
    if process.returncode == 0 and completed and answer.exists() and answer.read_text().strip():
        status = "completed"
    receipt = {
        **manifest, "status": status, "exit_code": process.returncode,
        "model": model, "reasoning_effort": effort,
        "cli_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
        "started_at": started_at,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "usage": completed[-1].get("usage") if completed else None,
        "answer_sha256": hashlib.sha256(answer.read_bytes()).hexdigest() if answer.exists() else None,
        "command": command,
    }
    write_json(artifact / "receipt.json", receipt)
    print(f'{manifest["case"]}/{manifest["arm"]}: {status}', flush=True)
    return receipt


def checked_receipt(artifact, case, arm):
    artifact = Path(artifact)
    receipt = read_json(artifact / "receipt.json")
    manifest = read_json(artifact / "manifest.json")
    if manifest["case"] != case or manifest["arm"] != arm:
        raise ValueError(f"{case}/{arm}: unexpected manifest identity")
    if any(receipt.get(key) != value for key, value in manifest.items()):
        raise ValueError(f"{case}/{arm}: receipt differs from prepared manifest")
    if receipt["status"] != "completed":
        raise ValueError(f"{case}/{arm}: run incomplete ({receipt['status']}); cannot score as clean")
    if hashlib.sha256((artifact / "answer.txt").read_bytes()).hexdigest() != receipt["answer_sha256"]:
        raise ValueError(f"{case}/{arm}: answer changed after capture")
    if hashlib.sha256((artifact / "TASK.txt").read_bytes()).hexdigest() != receipt["prompt_sha256"]:
        raise ValueError(f"{case}/{arm}: task changed after capture")
    return receipt


def score_tasks(results, grades):
    results = Path(results)
    suite = read_json(results / "suite.json")
    expected = {f'{task["id"]}/{arm}' for task in suite["tasks"] for arm in ARMS}
    if set(grades) != expected:
        raise ValueError("Grade every case and arm exactly once")
    scores = {}
    for task in suite["tasks"]:
        paired_receipts = []
        for arm in ARMS:
            key = f'{task["id"]}/{arm}'
            artifact = results / key
            receipt = checked_receipt(artifact, task["id"], arm)
            if receipt["source_revision"] != suite["source_revision"]:
                raise ValueError(f"{key}: unexpected source revision")
            if receipt["prompt_sha256"] != hashlib.sha256(task_prompt(task, arm).encode()).hexdigest():
                raise ValueError(f"{key}: prompt differs from frozen suite")
            expected_skills = suite["skills_sha256"] if arm == "with-skill" else None
            if receipt["skills_sha256"] != expected_skills:
                raise ValueError(f"{key}: unexpected candidate skills")
            if grades[key]["answer_sha256"] != receipt["answer_sha256"]:
                raise ValueError(f"{key}: grades belong to another answer")
            paired_receipts.append(receipt)
            scores[key] = score_checks(task["checks"], grades[key]["checks"])
        for field in ("model", "reasoning_effort", "cli_version", "source_revision", "source_sha256"):
            if paired_receipts[0][field] != paired_receipts[1][field]:
                raise ValueError(f'{task["id"]}: paired runs differ in {field}')
    return {"scores": scores, "with_minus_without": {
        task["id"]: scores[f'{task["id"]}/with-skill']["passed"]
        - scores[f'{task["id"]}/without-skill']["passed"] for task in suite["tasks"]
    }}


def score_routing_run(results):
    results = Path(results)
    suite = read_json(results / "suite.json")
    receipt = checked_receipt(results / "routing", "routing", "catalog-only")
    if (receipt["skills_sha256"] != suite["skills_sha256"]
            or receipt["prompt_sha256"] != suite["routing_prompt_sha256"]):
        raise ValueError("Routing catalog or requests differ from frozen suite")
    return score_routing(suite["triggers"], read_json(results / "routing/answer.txt"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--prepared", type=Path, required=True)
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--effort", choices=("low", "medium", "high", "xhigh"), default="high")
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument("--case", help="Run one case, or routing; default is all cases")
    score = sub.add_parser("score-routing")
    score.add_argument("--results", type=Path, required=True)
    tasks = sub.add_parser("score-tasks")
    tasks.add_argument("--results", type=Path, required=True)
    tasks.add_argument("--grades", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.source, args.out))
    elif args.command == "score-routing":
        result = score_routing_run(args.results)
        print(json.dumps(result, indent=2))
        return 0 if result["complete_pass"] else 1
    elif args.command == "score-tasks":
        result = score_tasks(args.results, read_json(args.grades))
        print(json.dumps(result, indent=2))
        return 0 if all(score["complete_pass"] for score in result["scores"].values()) else 1
    else:
        suite = read_json(args.prepared / "suite.json")
        args.results.mkdir(parents=True, exist_ok=True)
        snapshot = args.results / "suite.json"
        if snapshot.exists() and read_json(snapshot) != suite:
            raise ValueError("Results belong to a different suite")
        write_json(snapshot, suite)
        jobs = [(task["id"], arm) for task in suite["tasks"] for arm in ARMS]
        jobs += [("routing", None)]
        if args.case:
            jobs = [job for job in jobs if job[0] == args.case]
            if not jobs:
                parser.error("Unknown case")
        failed = False
        for case, arm in jobs:
            relative = Path(case) / arm if arm else Path(case)
            receipt = capture(args.prepared / relative, args.results / relative,
                              args.model, args.effort, args.timeout)
            failed |= receipt["status"] != "completed"
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
