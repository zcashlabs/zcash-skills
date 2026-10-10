#!/usr/bin/env python3
"""Fact-check the lines a pull request adds to the skills.

    python3 docs/verify-claims.py --base origin/add-initial-skills
    python3 docs/verify-claims.py --diff pr.diff --body pr-body.md --report out.md

Every added line in `SKILL.md`, `skills/**/*.md` or `docs/versioned-facts.md`
is a claim. Its checkable values are numbers of four or more digits, versions,
hex IDs and backticked names. Each claim goes through three steps:

1. Facts. A line matching a fact's `pattern` must agree with the fact's `value`
   and, when the fact has an `upstream` oracle, with the value upstream states
   today. Disagreement is a contradiction (❌). The facts always come from the
   base branch, never from the PR. Lines a PR adds to versioned-facts.md are
   claims like any other, and a changed fact definition (`id:`, `pattern:`,
   `upstream:`, ...) is left for a human: it only counts once it is merged.
2. Sources the author linked in the PR description.
3. The canonical set, whether or not the author linked anything: the ZIPs the
   line cites; zcashlabs/thus-spoke-zakura and zakura-core/zakura source (one
   tarball each), where a backticked name must appear and a backticked path
   must exist; every ZIP in zcash/zips (one tarball); the z.cash/learn
   articles; the zcash.readthedocs.io search API;
   and GitHub code search over the zodl-inc org (needs GITHUB_TOKEN or
   GH_TOKEN, and is rate limited, so it is capped per run).

A claim is verified (✅) when every checkable value in it was confirmed by a
fact oracle or appears in a fetched source. Otherwise it is unverified (⚠️) and
the report names the sources it was looked for in, plus any it could not
consult. Every verdict is an exact string match; nothing here guesses. Network
failures only ever produce ⚠️.

Everything taken from the PR (diff, description, file paths) is either a claim
to check or an inert string. None of it is run or compiled as a regex, and
every fetch is https to a host in check_facts.FETCH_HOSTS.

Exit 1 only when there is a contradiction. Standard library only.
"""
import argparse
import html
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location("check_facts", os.path.join(ROOT, "docs", "check-facts.py"))
check_facts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_facts)
UpstreamError = check_facts.UpstreamError

MARKER = "<!-- zcash-skills-fact-check -->"
COMMENT_LIMIT = 60_000
FACTS_PATH = "docs/versioned-facts.md"

# Author-supplied links on these hosts are fetched; others are listed in the
# report but not fetched.
ALLOWED_HOSTS = check_facts.ORACLE_HOSTS
CANONICAL_REPOS = [
    ("zcashlabs/thus-spoke-zakura", "main"),
    ("zakura-core/zakura", "main"),
]
ARCHIVE_MAX_BYTES = 50_000_000
ARCHIVE_TIMEOUT = 60
SOURCE_FILE_MAX_BYTES = 1_000_000
ZIPS_REPO = ("zcash/zips", "main")
TEXT_EXTENSIONS = (".rs", ".toml", ".md", ".rst", ".ts", ".tsx", ".js", ".yml", ".yaml", ".sh", ".json", ".sql", ".proto")

# A line longer than this is not parsed at all: no value extraction and no fact
# pattern runs over it. It is left for a human.
MAX_CLAIM_CHARS = 2000

LEARN_INDEX = "https://z.cash/learn/"
LEARN_MAX_INDEXES = 5
LEARN_MAX_ARTICLES = 60
RTD_SEARCH = "https://zcash.readthedocs.io/_/api/v3/search/?q="
RTD_MAX_QUERIES = 40
CODE_SEARCH = "https://api.github.com/search/code?q="
CODE_SEARCH_MAX = 20
CODE_SEARCH_INTERVAL = 6.5  # the code search API allows 10 requests a minute

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
HEX_RE = re.compile(r"\b0x[0-9A-Fa-f]{6,}\b")
VERSION_RE = re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?(?![\w])")
NUMBER_RE = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d{4,})(?![\w]|[.,]\d)")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
ZIP_RE = re.compile(r"\bZIPs? ?-?(\d{1,4})\b|zip-(\d{4})", re.I)
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
URL_RE = re.compile(r"https?://[^\s)>\]\"'`]+")
HREF_RE = re.compile(r"""href=["']([^"'#?]+)""")
LEARN_LINK_RE = re.compile(r"^https://z\.cash/learn/(?:page/\d+/|[a-z0-9-]+/)$")
PATH_EXT_RE = re.compile(r"\.(?:rs|toml|md|ts|tsx|yml|yaml|sh|json)$")
DIRECTIVE_RE = re.compile(r"^\s*(?:```|(?:id|pattern|kind|source|verified|upstream|extract)\s*:)")
PLACEHOLDER_CHARS = set("{}[]*…<>")


# ------------------------------------------------------------------- inputs

def in_scope(path):
    return path.endswith(".md") and (path == "SKILL.md" or path.startswith("skills/") or path == FACTS_PATH)


def unquote_path(target):
    """Decode git's C-quoted diff path ("b/we\\303\\251rd.md") to plain text, or
    None when it can't be decoded. Unquoted targets pass through unchanged."""
    if not target.startswith('"'):
        return target
    try:
        quoted = target[1 : target.rindex('"')]
        raw = bytes(quoted, "utf-8").decode("unicode_escape")
        return raw.encode("latin-1").decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def parse_diff(diff):
    """Return [(path, line_no, text)] for lines the diff adds to in-scope files."""
    claims, path, line_no = [], None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            target = unquote_path(raw[4:].strip())
            path = target[2:] if target and target.startswith("b/") else None
            continue
        if raw.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
            continue
        if path is None or raw.startswith(("--- ", "diff ", "index ")):
            continue
        if raw.startswith("+"):
            if in_scope(path):
                claims.append((path, line_no, raw[1:]))
            line_no += 1
        elif raw.startswith(" "):
            line_no += 1
    return claims


def is_claim(path, text):
    s = text.strip()
    if not s or set(s) <= set("|-: "):
        return False
    # In versioned-facts.md every line counts, fences included: they delimit facts.
    return path == FACTS_PATH or not s.startswith("```")


def is_directive(path, text):
    """A line of a fact definition other than its `value`."""
    return path == FACTS_PATH and DIRECTIVE_RE.match(text) is not None


def is_path(value):
    return "/" in value or PATH_EXT_RE.search(value) is not None


def values_in(text):
    """The checkable values in a line, in order, without duplicates."""
    text = LINK_TARGET_RE.sub("]", text)  # link targets are not claims
    text = URL_RE.sub("", text)
    found = []
    for tok in BACKTICK_RE.findall(text):
        tok = tok.strip().removesuffix("()")
        if len(tok) > 2 and " " not in tok and "..." not in tok and not PLACEHOLDER_CHARS & set(tok):
            found.append(tok)
    plain = DATE_RE.sub("", ZIP_RE.sub("", BACKTICK_RE.sub(" ", text)))
    for rx in (HEX_RE, VERSION_RE, NUMBER_RE):
        found += rx.findall(plain)
    seen, out = set(), []
    for tok in found:
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def strip_html_comments(text):
    """Drop <!-- --> comments in one linear pass; an unclosed one hides the rest, as on GitHub."""
    out, i = [], 0
    while True:
        j = text.find("<!--", i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = text.find("-->", j + 4)
        if k < 0:
            break
        i = k + 3
    return "".join(out)


def source_links(body):
    """URLs the author listed in the PR description."""
    body = strip_html_comments(body or "")  # the template's example links
    seen, out = set(), []
    for url in URL_RE.findall(body):
        url = url.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# ------------------------------------------------------------- markdown out
# Claim text, paths and tokens come from the PR. Whatever reaches the comment
# goes through one of these, so it renders as the literal text it is.

_ESCAPES = {
    "\\": "&#92;", "&": "&amp;", "<": "&lt;", ">": "&gt;", "[": "&#91;", "]": "&#93;",
    "`": "&#96;", "|": "\\|", "@": "@\u200b", "\n": " ", "\r": " ",
}


AUTOLINK_RE = re.compile(r"(?i)\b(https?|ftp)://|\b(www)\.")


def esc(text):
    """Plain text for a table cell: no links, HTML, code spans, mentions or column breaks."""
    text = AUTOLINK_RE.sub(lambda m: f"{m.group(1)}:\u200b//" if m.group(1) else f"{m.group(2)}\u200b.", text)
    return "".join(_ESCAPES.get(c, c) for c in text)


def cell(text, limit=140):
    text = text if len(text) <= limit else text[: limit - 1] + "…"
    return esc(text)


def code(value, limit=100):
    """A token as inline code. Code spans render HTML and links literally; only `|` needs care."""
    value = value if len(value) <= limit else value[: limit - 1] + "…"
    if "`" in value:
        return esc(value)
    return "`" + value.replace("|", "\\|").replace("\n", " ") + "`"


def link(label, url):
    """A link to a URL the checker fetched; `label` must already be safe markdown."""
    return f"[{label}]({urllib.parse.quote(url, safe=':/?#&=%+~;,!$*@')})"


def join_capped(parts, limit):
    out, size = [], 0
    for i, part in enumerate(parts):
        if out and size + len(part) > limit:
            out.append(f"and {len(parts) - i} more")
            break
        out.append(part)
        size += len(part) + 2
    return ", ".join(out)


# ------------------------------------------------------------------ sources

def raw_url(url):
    """Map a page URL to something fetchable as text, or None if not allowed."""
    if not check_facts.host_allowed(url, ALLOWED_HOSTS):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname == "github.com":
        m = re.match(r"^/([^/]+)/([^/]+)/blob/(.+)$", parsed.path)
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else None
    return url


def html_to_text(text):
    if "<html" not in text[:2000].lower():
        return text
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def contains(text, value):
    """True when `value` was actually seen in `text`, not just as part of a longer word."""
    if re.fullmatch(r"[\d,]+", value):
        return re.search(rf"(?<!\d){re.escape(value.replace(',', ''))}(?!\d)", text.replace(",", "")) is not None
    if HEX_RE.fullmatch(value):  # hex IDs are written in either case (ZIPs use lowercase)
        return re.search(rf"(?<![0-9A-Za-z]){re.escape(value)}(?![0-9A-Za-z])", text, re.I) is not None
    if re.fullmatch(r"\w+", value):
        return re.search(rf"\b{re.escape(value)}\b", text) is not None
    return value in text


def dicts(data, key):
    """The dict entries of data[key], tolerating whatever shape a search API returns."""
    items = data.get(key) if isinstance(data, dict) else None
    return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []


def search_term(value):
    """A value as a quoted-search term. A `"` would close the query's quoting, so
    it is dropped — the fragment check on each result does the real matching, the
    query only needs to narrow. Returns "" when nothing searchable remains."""
    term = value.replace(",", "") if re.fullmatch(r"[\d,]+", value) else value
    return term.replace('"', "").strip()


def fetch_archive(url):
    """Fetch a .tar.gz and return {path: text} for its source files."""
    data = check_facts.fetch_bytes(url, max_bytes=ARCHIVE_MAX_BYTES, timeout=ARCHIVE_TIMEOUT)
    try:
        files = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar:
                if not member.isfile() or member.size > SOURCE_FILE_MAX_BYTES or not member.name.endswith(TEXT_EXTENSIONS):
                    continue
                path = member.name.split("/", 1)[1]  # drop the "<repo>-<ref>/" prefix
                files[path] = tar.extractfile(member).read().decode("utf-8", "replace")
        return files
    except (OSError, tarfile.TarError, IndexError) as e:
        raise UpstreamError(f"{url}: {e}") from e


class Sources:
    """Fetches and caches source text; records failures instead of raising.

    Each canonical lookup returns (hit, skipped): `hit` is (label, url) or None,
    and `skipped` is why the source could not be consulted, or None if it was."""

    def __init__(self, fetch, fetch_archive=fetch_archive, token=None, sleep=time.sleep):
        self.fetch = fetch
        self.fetch_archive = fetch_archive
        self.token = token
        self.sleep = sleep
        self._raw = {}
        self._repos = {}
        self._learn = None
        self._rtd = {}
        self._code = {}
        self.rtd_queries = 0
        self.code_queries = 0
        self.code_stopped = None
        self.learn_articles = 0
        self.failures = []

    def raw(self, url, record=True):
        if url not in self._raw:
            try:
                self._raw[url] = self.fetch(url)
            except UpstreamError as e:
                self._raw[url] = None
                if record:
                    self.failures.append(str(e))
        return self._raw[url]

    def text(self, url, record=True):
        body = self.raw(url, record)
        return None if body is None else html_to_text(body)

    # ZIPs a line cites

    def zip_text(self, num):
        """A ZIP's source from zcash/zips; newer ZIPs are .md, older ones .rst."""
        base = f"https://raw.githubusercontent.com/zcash/zips/main/zips/zip-{num:04d}"
        for ext in ("md", "rst"):
            body = self.text(f"{base}.{ext}", record=False)
            if body is not None:
                return f"zip-{num:04d}.{ext}", body
        self.failures.append(f"{base}.md / .rst: not found")
        return f"zip-{num:04d}", None

    def zips_for(self, line):
        nums = sorted({int(m.group(1) or m.group(2)) for m in ZIP_RE.finditer(line)})
        return [self.zip_text(n) for n in nums]

    # THS / Zakura source

    def repo(self, name, ref):
        if name not in self._repos:
            url = f"https://codeload.github.com/{name}/tar.gz/{ref}"
            try:
                self._repos[name] = self.fetch_archive(url)
            except UpstreamError as e:
                self._repos[name] = None
                self.failures.append(str(e))
        return self._repos[name]

    def find_upstream(self, value):
        """Where the canonical repos confirm a backticked name or path."""
        repos = [(name, self.repo(name, ref)) for name, ref in CANONICAL_REPOS]
        if all(files is None for _, files in repos):
            return None, "unreachable"
        for name, files in repos:
            files = files or {}
            if is_path(value):
                if value.endswith("/"):  # a directory
                    hits = [p for p in files if p.startswith(value) or ("/" + value) in p]
                else:
                    hits = [p for p in files if p == value or p.endswith("/" + value)]
                if hits:
                    return (f"{name.split('/')[1]}/{min(hits, key=len)}", None), None
        for name, files in repos:  # a name, or a path the code builds at runtime
            for path, body in (files or {}).items():
                if contains(body, value):
                    return (f"{name.split('/')[1]}/{path}", None), None
        return None, None

    # The ZIP index: every ZIP, for values a line doesn't cite a ZIP for

    def zip_index(self, value):
        files = self.repo(*ZIPS_REPO)
        if files is None:
            return None, "unreachable"
        for path in sorted(files):
            m = re.fullmatch(r"zips/(zip-\d{4})\.(?:md|rst)", path)
            if m and contains(files[path], value):
                return (path.split("/")[1], f"https://zips.z.cash/{m.group(1)}"), None
        return None, None

    # z.cash/learn

    def learn_pages(self):
        """Every article linked from the z.cash/learn index pages, fetched once per run."""
        if self._learn is None:
            indexes, seen, articles = [LEARN_INDEX], set(), []
            while indexes and len(seen) < LEARN_MAX_INDEXES:
                index = indexes.pop(0)
                seen.add(index)
                body = self.raw(index)
                for href in HREF_RE.findall(body or ""):
                    url = urllib.parse.urljoin(index, html.unescape(href))
                    if not LEARN_LINK_RE.match(url):
                        continue
                    if "/page/" in url:
                        if url not in seen and url not in indexes:
                            indexes.append(url)
                    elif not url.endswith("/feed/") and url not in articles:
                        articles.append(url)
            pages = [(url, self.text(url)) for url in articles[:LEARN_MAX_ARTICLES]]
            self._learn = [(url, body) for url, body in pages if body is not None]
            self.learn_articles = len(self._learn)
        return self._learn

    def learn(self, value):
        pages = self.learn_pages()
        if not pages:
            return None, "no articles found" if self._raw.get(LEARN_INDEX) else "unreachable"
        for url, body in pages:
            if contains(body, value):
                return (urllib.parse.urlparse(url).path.strip("/"), url), None
        return None, None

    # zcash.readthedocs.io

    def readthedocs(self, value):
        if value in self._rtd:
            return self._rtd[value]
        if self.rtd_queries >= RTD_MAX_QUERIES:
            return None, f"per-run cap of {RTD_MAX_QUERIES} searches reached"
        term = search_term(value)
        if not term:
            self._rtd[value] = (None, "no searchable term")
            return self._rtd[value]
        self.rtd_queries += 1
        query = urllib.parse.quote(f'project:zcash "{term}"')
        try:
            data = json.loads(self.fetch(RTD_SEARCH + query))
        except (UpstreamError, ValueError) as e:
            self.failures.append(f"readthedocs search for {value}: {e}")
            self._rtd[value] = (None, "search failed")
            return self._rtd[value]
        hit = None
        for page in dicts(data, "results"):
            if any(contains(str(block.get("content", "")), value) for block in dicts(page, "blocks")):
                path = str(page.get("path", ""))
                hit = (f"readthedocs {path.rsplit('/', 1)[-1]}", f"https://zcash.readthedocs.io{path}")
                break
        self._rtd[value] = (hit, None)
        return self._rtd[value]

    # zodl-inc code

    def zodl(self, value):
        if value in self._code:
            return self._code[value]
        if not self.token:
            return None, "no GITHUB_TOKEN"
        if self.code_stopped:
            return None, self.code_stopped
        if self.code_queries >= CODE_SEARCH_MAX:
            return None, f"per-run cap of {CODE_SEARCH_MAX} searches reached"
        if self.code_queries:
            self.sleep(CODE_SEARCH_INTERVAL)
        term = search_term(value)
        if not term:
            self._code[value] = (None, "no searchable term")
            return self._code[value]
        self.code_queries += 1
        query = urllib.parse.quote(f'org:zodl-inc "{term}"')
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.text-match+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            data = json.loads(self.fetch(CODE_SEARCH + query + "&per_page=30", headers))
        except (UpstreamError, ValueError) as e:
            self.failures.append(f"zodl-inc code search for {value}: {e}")
            if re.search(r"\b(403|429)\b", str(e)):
                self.code_stopped = "rate limited"
            self._code[value] = (None, "search failed")
            return self._code[value]
        hit = None
        for item in dicts(data, "items"):
            if any(contains(str(m.get("fragment", "")), value) for m in dicts(item, "text_matches")):
                repo = item.get("repository")
                repo = str(repo.get("full_name", "zodl-inc")) if isinstance(repo, dict) else "zodl-inc"
                hit = (f"{repo}/{item.get('path', '')}", str(item.get("html_url", "")) or None)
                break
        self._code[value] = (hit, None)
        return self._code[value]


# ------------------------------------------------------------------ verdicts

def fact_check(line, facts, sources, upstream_cache, pr_fact_lines=()):
    """Check a line against the base branch's versioned facts.

    Returns (contradictions, confirmed_values, notes), all safe markdown except
    the confirmed values. `pr_fact_lines` are the lines this PR adds to
    versioned-facts.md, as plain strings: a value that differs from the base
    fact but that the PR also writes into the facts file is a fact update, so it
    is left for review instead of failing."""
    contradictions, confirmed, notes = [], set(), []
    for f in facts:
        if "pattern" not in f:
            continue
        for m in re.finditer(f["pattern"], line):
            hit = m.group(0)
            fid = esc(f["id"])
            if f.get("kind") == "forbid":
                contradictions.append(f"{code(hit)} is a stale claim ({fid}: {esc(f.get('source', 'see versioned-facts.md'))})")
                continue
            matches_base = f["value"] in hit or hit in f["value"]
            updated_here = not matches_base and any(hit in added for added in pr_fact_lines)
            current, err = None, None
            if "upstream" in f and "extract" not in f:
                err = "oracle has no extract regex"
            elif "upstream" in f:
                if f["id"] not in upstream_cache:
                    try:
                        upstream_cache[f["id"]] = (check_facts.upstream_value(f, fetch=sources.fetch), None)
                    except check_facts.HostNotAllowed:
                        upstream_cache[f["id"]] = (None, "oracle host not allowed")
                    except UpstreamError:
                        upstream_cache[f["id"]] = (None, "upstream unreachable")
                current, err = upstream_cache[f["id"]]
            if current is not None:
                if check_facts.agrees({"value": hit}, current):
                    confirmed.add(hit)
                    if not matches_base:
                        notes.append(f"{fid}: upstream now says {code(current)}; versioned-facts.md on the base branch still says {code(f['value'])}")
                elif matches_base:
                    contradictions.append(f"{code(hit)} matches versioned-facts.md, but {esc(f['upstream'])} now says {code(current)} ({fid})")
                else:
                    contradictions.append(f"{code(hit)} conflicts with {fid}: versioned-facts.md and {esc(f['upstream'])} both say {code(current)}")
                continue
            if err:
                notes.append(f"{fid}: {err}, not re-checked")
            if matches_base:
                if not err:
                    confirmed.add(hit)
            elif updated_here:
                notes.append(f"{code(hit)} differs from {fid} = {code(f['value'])} on the base branch; this PR changes that fact, so confirm it by hand")
            else:
                contradictions.append(f"{code(hit)} conflicts with {fid} = {code(f['value'])} in versioned-facts.md")
    return contradictions, confirmed, notes


def verify(claims, facts, links, fetch, fetch_archive=fetch_archive, token=None, sleep=time.sleep):
    """Return the list of result dicts, the PR's sources and the Sources used."""
    sources = Sources(fetch, fetch_archive, token, sleep)
    provided = []
    for url in links:
        fetchable = raw_url(url)
        provided.append((url, fetchable, sources.text(fetchable) if fetchable else None))
    pr_fact_lines = [text for path, _, text in claims if path == FACTS_PATH]
    upstream_cache, results = {}, []

    for path, line_no, text in claims:
        if not is_claim(path, text):
            continue
        res = {"where": f"{path}:{line_no}", "text": text.strip()}
        if len(text) > MAX_CLAIM_CHARS:
            res.update(verdict="⚠️", evidence=f"longer than {MAX_CLAIM_CHARS} characters, so not parsed", prose=True)
            results.append(res)
            continue
        if is_directive(path, text):
            res.update(verdict="⚠️", evidence="changes a fact definition; review by hand, it only applies once merged", directive=True)
            results.append(res)
            continue
        contradictions, confirmed, notes = fact_check(text, facts, sources, upstream_cache, pr_fact_lines)
        if contradictions:
            res.update(verdict="❌", evidence="; ".join(contradictions))
            results.append(res)
            continue
        values = values_in(text)
        if not values:
            res.update(verdict="⚠️", evidence="; ".join(notes) or "no checkable value", prose=not notes)
            results.append(res)
            continue

        evidence, missing, looked, skipped = [], [], [], {}
        zips = None
        backticked = set(values_in(" ".join(f"`{b}`" for b in BACKTICK_RE.findall(text))))
        for v in values:
            if any(v in c or c in v for c in confirmed):
                evidence.append(f"{code(v)} fact oracle")
                continue
            hit = next((url for url, _, body in provided if body and contains(body, v)), None)
            if hit:
                evidence.append(f"{code(v)} in {link('PR source', hit)}")
                continue
            if zips is None:
                zips = sources.zips_for(text)
            found = next(((name, None) for name, body in zips if body and contains(body, v)), None)
            lookups = [
                ("THS/Zakura source", sources.find_upstream if v in backticked else None),
                ("the ZIP index", sources.zip_index),
                ("z.cash/learn", sources.learn),
                ("zcash.readthedocs.io", sources.readthedocs),
                ("zodl-inc code search", sources.zodl),
            ]
            v_skipped = {}
            for name, lookup in lookups:
                if found or lookup is None:
                    continue
                found, why = lookup(v)
                if why:
                    v_skipped[name] = why
                elif name not in looked:
                    looked.append(name)
            if found:
                label, url = found
                evidence.append(f"{code(v)} in " + (link(esc(label), url) if url else esc(label)))
            else:
                missing.append(v)
                for name, why in v_skipped.items():
                    skipped.setdefault(name, why)
        if missing:
            where = (["the PR's sources"] if provided else []) + [name for name, body in zips or [] if body] + looked
            ev = join_capped([code(v) for v in missing], 200) + " not found in " + (", ".join(where) or "any source")
            not_consulted = [f"{n} ({esc(why)})" for n, why in skipped.items()]
            if not_consulted:
                ev += "; not consulted: " + ", ".join(not_consulted)
            res.update(verdict="⚠️", evidence=ev)
        else:
            res.update(verdict="✅", evidence=join_capped(evidence, 400))
        if notes:
            res["evidence"] += " (" + "; ".join(notes) + ")"
        results.append(res)
    return results, provided, sources


# ------------------------------------------------------------------- report

def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def coverage(sources):
    """Which canonical sources this run actually reached."""
    used = ["the ZIPs each line cites"]
    if any(sources._repos.get(name) is not None for name, _ in CANONICAL_REPOS):
        used.append("THS/Zakura source")
    if sources._repos.get(ZIPS_REPO[0]) is not None:
        used.append("the ZIP index")
    if sources.learn_articles:
        used.append(f"z.cash/learn ({plural(sources.learn_articles, 'article', 'articles')})")
    if sources.rtd_queries:
        used.append(f"zcash.readthedocs.io search ({plural(sources.rtd_queries, 'query', 'queries')})")
    if sources.code_queries:
        used.append(f"zodl-inc code search ({plural(sources.code_queries, 'query', 'queries')})")
    return used


def render(results, provided, sources):
    bad = [r for r in results if r["verdict"] == "❌"]
    good = [r for r in results if r["verdict"] == "✅"]
    prose = [r for r in results if r.get("prose")]
    unverified = [r for r in results if r["verdict"] == "⚠️" and not r.get("prose")]

    out = [MARKER, f"### Fact check: {len(bad)} contradicted, {len(good)} verified, {len(unverified) + len(prose)} for review", ""]
    if not results:
        out.append("No added lines in `SKILL.md`, `skills/` or `docs/versioned-facts.md`.")
        return "\n".join(out) + "\n"
    if provided:
        listed = []
        for url, fetchable, body in provided:
            state = "fetched" if body is not None else ("not fetched: only GitHub file links and the Zcash docs/ZIP sites are read" if fetchable is None else "fetch failed")
            listed.append((link(cell(url, 80), url) if body is not None else cell(url, 80)) + f" ({state})")
        out.append("Sources from the PR description: " + ", ".join(listed) + ".")
    else:
        out.append(
            "**No sources in the PR description.** Under `Source(s) of truth:`, link the upstream files, "
            "ZIPs or docs pages that back these changes. This check runs again when you edit the description."
        )
    out.append("")
    rows = bad + unverified + good
    if rows:
        out += ["| | Line | Claim | Evidence |", "| --- | --- | --- | --- |"]
        out += [f"| {r['verdict']} | {cell(r['where'], 120)} | {cell(r['text'])} | {r['evidence']} |" for r in rows]
        out.append("")
    if prose:
        out.append(f"<details><summary>⚠️ {len(prose)} changed line(s) with no number, version or name to match; review by hand</summary>\n")
        out += [f"- {cell(r['where'], 120)}: {cell(r['text'], 160)}" for r in prose]
        out += ["", "</details>", ""]
    if sources.failures:
        out.append("<details><summary>Fetch failures (advisory, not a failed check)</summary>\n")
        out += [f"- {cell(f, 200)}" for f in sources.failures]
        out += ["", "</details>", ""]
    out.append(
        "_✅ and ❌ are exact matches against the base branch's `docs/versioned-facts.md` and its upstream oracles, "
        "the PR's sources and the canonical set. Consulted this run: " + ", ".join(coverage(sources)) + ". "
        "A ⚠️ row names where it looked and anything it could not consult. "
        "Lines this PR adds to `docs/versioned-facts.md` are checked as claims; the facts change only once merged. "
        "Only ❌ fails the check._"
    )
    report = "\n".join(out) + "\n"
    if len(report) > COMMENT_LIMIT:
        report = report[:COMMENT_LIMIT] + "\n\n_Report truncated; the full report is in the job summary._\n"
    return report


def main():
    parser = argparse.ArgumentParser(description="Fact-check the lines a PR adds to the skills.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--diff", help="unified diff file (e.g. from `gh pr diff`); facts come from this checkout")
    src.add_argument("--base", help="git ref to diff HEAD against (three-dot); facts come from that ref")
    parser.add_argument("--body", help="file holding the PR description")
    parser.add_argument("--report", help="write the markdown report here as well as to stdout")
    args = parser.parse_args()

    if args.diff:
        diff = open(args.diff, encoding="utf-8").read()
        facts = check_facts.load_facts()
    else:
        git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        diff = git("diff", f"{args.base}...HEAD")
        facts = check_facts.parse_facts(git("show", f"{args.base}:{FACTS_PATH}"))
    body = open(args.body, encoding="utf-8").read() if args.body else ""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    results, provided, sources = verify(parse_diff(diff), facts, source_links(body), check_facts.fetch, fetch_archive, token=token)
    report = render(results, provided, sources)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report)
    print(report)
    return 1 if any(r["verdict"] == "❌" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
