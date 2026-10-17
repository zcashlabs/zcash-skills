# Skill evaluations

These evaluations measure agent answers to development tasks, separately from the
fact-checker unit tests. [cases.json](cases.json) defines three source-investigation
tasks, four review criteria per task, and twelve catalog-routing requests: six
positive cases and six near misses. The first tasks cover THS resource ownership,
faucet recovery after a lost response, and stale dashboard balances.

Keep generated run artifacts outside the repository, as in the commands below.
The local `evals/results/` directory is also ignored by Git.

The source revision is pinned in the case file. Update it and recheck every oracle
when deliberately refreshing the suite. Do not silently evaluate against the
latest checkout or change a rubric after inspecting results.

## Paired task protocol

`run.py prepare` exports tracked public source from the pinned Git commit. It
ignores dirty and untracked checkout files and excludes installed agent skills and
agent configuration. Each task gets two independent copies of the same source.
Only the treatment copy receives `candidate-skills/`, including sibling references;
its prompt explicitly loads the selected specialist. The baseline receives neither
the candidate catalog nor skill bodies. Rubrics stay outside both workspaces.

Each arm starts a fresh, read-only `codex exec` session with the same explicit model
and reasoning effort. Automatic skill catalogs are suppressed with
`skills.max_context_tokens=1`; automatic AGENTS injection is suppressed with
`project_doc_max_bytes=0`, and both arms are instructed to read the copied project
`AGENTS.md`. User configuration is ignored and web search is disabled. The prompt
restricts reads to the workspace and prohibits builds, tests, Docker, and edits.

This is an **explicit skill-loading ablation**, not a native automatic-invocation
test. The baseline still has its pretrained knowledge and the target project's
instructions. The read-only sandbox does not make filesystem reads hermetic: audit
command traces for out-of-workspace access and invalidate a contaminated run.
Verify the effective prompt/catalog settings with your installed Codex version
before comparing a new environment; these settings were verified with CLI 0.162.0.

```console
git clone --no-checkout https://github.com/zcashlabs/thus-spoke-zakura.git /tmp/ths-eval-source
python3 evals/run.py prepare --source /tmp/ths-eval-source --out /tmp/zcash-eval-work
python3 evals/run.py run --prepared /tmp/zcash-eval-work --results /tmp/zcash-eval-results --model gpt-6.1-sol --effort high
```

Model runs use the locally authenticated Codex CLI and consume model usage. They
are opt-in and are not part of ordinary CI. `--case foreign-resource` selects one
paired task; `--case routing` selects the routing batch. A timeout or CLI failure
produces an incomplete receipt and a nonzero exit. Use a new results directory for
a retry; preserve failed attempts. Existing artifacts are never overwritten.

Results contain the frozen suite, prepared manifests/prompts, full JSONL command
traces, final answers, and receipts with source/skill/prompt/answer hashes, model,
effort, CLI version, elapsed time, token usage, and completion status. Source and
skills are checked for changes before execution. Audit the traces to confirm the
treatment actually read its selected skill and relevant reference and that neither
arm ran prohibited commands or read hidden rubrics. A final answer alone cannot
establish skill use.

## Review and scoring

Review both answers against the **predeclared** rubric and pinned oracle source.
Each criterion is binary; all four are required for task success. Record a concrete
answer passage or omission and supporting source evidence for each decision. Do
not grade by keyword presence, let the task agent score itself, or count a proposed
test as an executed test. Independent or blinded human review is preferable; label
model-assisted reviews honestly. Keep failed checks when an answer sounds plausible.

Create a review template, then fill every `pass` and `evidence` field:

```sh
python3 - /tmp/zcash-eval-results > /tmp/zcash-eval-grades.json <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
suite = json.loads((root / 'suite.json').read_text())
grades = {}
for task in suite['tasks']:
    for arm in ('without-skill', 'with-skill'):
        key = f"{task['id']}/{arm}"
        receipt = json.loads((root / key / 'receipt.json').read_text())
        grades[key] = {'answer_sha256': receipt['answer_sha256'], 'checks': {
            name: {'pass': None, 'evidence': ''} for name in task['checks']}}
print(json.dumps(grades, indent=2))
PY
python3 evals/run.py score-tasks --results /tmp/zcash-eval-results --grades /tmp/zcash-eval-grades.json
python3 evals/run.py score-routing --results /tmp/zcash-eval-results
```

Scoring rejects incomplete runs, mismatched case/arm/source/model/CLI provenance,
changed answers, reused answer grades, and missing review criteria. A task scorer
exits nonzero when any arm misses a criterion; this is an observed quality failure,
not a harness failure. Inspect the per-arm scores and deltas.

## Triggering and near misses

The routing batch exposes only the twelve candidate names/descriptions and request
texts with neutral IDs. Expected selections, case kinds, and skill bodies are
hidden. Scoring requires each positive case's specialist, permits only declared
optional neighbors, and requires an explicit empty list for every near miss.
Missing, duplicate, extra, and malformed decisions cannot yield a clean pass.

This checks catalog selection in one batch. It does not prove that a host discovers,
opens, or follows the chosen skill during a real task. Keep these scores separate
from task completion. Future coverage should add natural automatic invocation,
ambiguous prompts, other specialists, code-editing tasks, and repeated paired runs
with counterbalanced order. One pair per task cannot establish a reliable skill
effect; report ties, regressions, and unresolved criteria alongside improvements.

The approach follows [OpenAI's skill-evaluation guide](https://developers.openai.com/blog/eval-skills).
Offline harness tests run with `python3 -m unittest discover -s tests`; they check
isolation and scoring behavior and are not themselves agent-quality evidence.
