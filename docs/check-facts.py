#!/usr/bin/env python3
"""Check that versioned facts stated in the skills match docs/versioned-facts.md.

Each ```facts block in versioned-facts.md declares a canonical `value` and a
`pattern` (regex). The checker scans every .md file in the repo for pattern
matches and reports matches that differ from the canonical value — the signal
that a skill went stale after an upstream bump (image tag, version, height).

It also warns when a fact's `verified` date is older than STALE_DAYS — a prompt
to re-verify, not a failure. Facts without a local `pattern` can still define
an upstream oracle; otherwise only their verification date is checked.

A fact may set `kind: forbid` — then ANY pattern match in a doc is a
contradiction. Use it for stale claims of absence ("X has no idempotency key")
where upstream later added the thing; a value-check cannot express that.

A fact may also name an oracle: `upstream` (a raw file URL) and `extract` (a
regex whose first group is the value upstream states). With --upstream the
checker fetches each oracle and reports facts whose `value` no longer matches.
A fetch or extraction that fails leaves verification incomplete. An `upstream`
must be an https URL on ORACLE_HOSTS; other hosts are never fetched.

Run from anywhere:  python3 docs/check-facts.py [--upstream]
Exit 0 = requested checks completed without contradictions (date warnings may remain);
exit 1 = contradictions or invalid definitions; exit 2 = incomplete upstream verification.
Without --upstream, exit 0 establishes local consistency only.
"""
import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(ROOT, "docs", "versioned-facts.md")
STALE_DAYS = 90
FETCH_TIMEOUT = 20
FETCH_MAX_BYTES = 2_000_000

# Hosts an `upstream` oracle may point at. verify-claims.py reads the sources an
# author links from the same list.
ORACLE_HOSTS = frozenset({
    "raw.githubusercontent.com",
    "github.com",
    "zips.z.cash",
    "zcash.readthedocs.io",
    "z.cash",
})
# Every host fetch() will connect to, redirects included: the oracle hosts plus
# GitHub's tarball and search endpoints that verify-claims.py calls itself.
FETCH_HOSTS = ORACLE_HOSTS | {"codeload.github.com", "api.github.com"}


class UpstreamError(Exception):
    """The oracle could not be read: fetch failed or `extract` found nothing."""


class HostNotAllowed(UpstreamError):
    """A URL outside the allowlist; it was not fetched."""


class ExtractError(UpstreamError):
    """The oracle was fetched but `extract` matched nothing — the upstream
    format changed, which is a different failure than an unreachable file."""


def host_allowed(url, hosts=FETCH_HOSTS):
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:  # a malformed port or netloc
        return False
    return parsed.scheme == "https" and (parsed.hostname or "") in hosts and port in (None, 443) and parsed.username is None


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_allowed(newurl):
            raise HostNotAllowed(f"{req.full_url}: redirect to {newurl} is off the allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_AllowlistRedirects)


def fetch_bytes(url, headers=None, max_bytes=FETCH_MAX_BYTES, timeout=FETCH_TIMEOUT):
    """GET an allowlisted https URL. `Authorization` is never sent on after a redirect."""
    if not host_allowed(url):
        raise HostNotAllowed(f"{url}: host not allowed")
    headers = dict(headers or {})
    auth = headers.pop("Authorization", None)
    req = urllib.request.Request(url, headers={"User-Agent": "zcash-skills-check-facts", **headers})
    if auth:
        req.add_unredirected_header("Authorization", auth)
    try:
        with _opener.open(req, timeout=timeout) as resp:
            return resp.read(max_bytes)
    except OSError as e:  # URLError, HTTPError and timeouts are all OSError
        raise UpstreamError(f"{url}: {e}") from e


def fetch(url, headers=None):
    return fetch_bytes(url, headers).decode("utf-8", "replace")


def norm_value(text):
    """Compare values ignoring backticks, digit-group commas, spaces and case."""
    return re.sub(r"[`,\s]", "", text).lower()


def oracle_allowed(fact):
    return host_allowed(fact["upstream"], ORACLE_HOSTS)


def upstream_value(fact, fetch=fetch):
    if not oracle_allowed(fact):
        raise HostNotAllowed(f"{fact['upstream']}: oracle host not allowed")
    text = fetch(fact["upstream"])
    if "coverage" in fact:
        scopes = list(re.finditer(fact["coverage"], text, re.M))
        matches = []
        if not scopes:
            raise ExtractError(f"{fact['upstream']}: coverage pattern matched nothing")
        for scope in scopes:
            captured = list(re.finditer(fact["extract"], scope.group(0), re.M))
            if len(captured) != 1:
                raise ExtractError(f"{fact['upstream']}: unrecognized or ambiguous selector within coverage")
            matches.extend(captured)
    else:
        matches = list(re.finditer(fact["extract"], text, re.M))
    if not matches or any(not match.group(1) for match in matches):
        raise ExtractError(f"{fact['upstream']}: extract pattern matched nothing")
    if fact.get("extract_all") == "true":
        return ", ".join(sorted({match.group(1) for match in matches}))
    return matches[0].group(1)


def agrees(fact, current):
    """True when the value upstream states is exactly the one the fact records.
    Exact normalised equality — a truncated oracle match ("1.6" vs "1.6.0") is
    not agreement. extract_all compares comma-separated sets without ordering."""
    if fact.get("extract_all") == "true":
        return {norm_value(value) for value in current.split(",")} == {
            norm_value(value) for value in fact["value"].split(",")}
    return norm_value(current) == norm_value(fact["value"])


def value_in_hit(fact, hit):
    """True when the fact's normalised value appears inside a pattern match.

    A match that is one whitespace-free token must BE the value: a tag like
    ``zakuracore/zakura:1.6.0-rc1`` or ``1.6.0.1`` is a different claim, not a
    loose container of the pinned tag. Only a prose span (a match containing
    whitespace, e.g. "NU7 ... Testnet ... 4,465,026") may carry the value as a
    substring — and even then digits must not be glued to more digits."""
    val, hay = norm_value(fact["value"]), norm_value(hit)
    if not val:
        return False
    if not re.search(r"\s", hit):
        return hay == val
    i = hay.find(val)
    while i != -1:
        before = hay[i - 1] if i else ""
        after = hay[i + len(val)] if i + len(val) < len(hay) else ""
        bad = (val[0].isdigit() and before.isdigit()) or (val[-1].isdigit() and after.isdigit())
        if not bad:
            return True
        i = hay.find(val, i + 1)
    return False


NEGATION_RE = re.compile(r"(?i)\b(?:no longer|not|never|without|isn't|is not|doesn't|does not|do not|don't|nor|no)\b")


def negated(line, start, end):
    """True when a negation cue appears in the sentence containing [start, end).

    Only the sentence segment is considered — a negation in a neighbouring
    sentence must not excuse a positive stale claim."""
    seg = line.rfind(".", 0, start)
    for c in ";:!":
        seg = max(seg, line.rfind(c, 0, start))
    return NEGATION_RE.search(line[seg + 1 : end]) is not None


def load_facts(path=FACTS):
    with open(path, encoding="utf-8") as fh:
        return parse_facts(fh.read())


def parse_facts(text):
    facts = []
    for block in re.findall(r"```facts\n(.*?)```", text, re.S):
        f = dict(re.findall(r"^(\w+):\s*(.+)$", block, re.M))
        if "id" in f:
            facts.append(f)
    return facts


def definition_errors(fact):
    """Problems with how a fact is written, found without the network."""
    if fact.get("kind", "value") not in ("value", "forbid"):
        return [f"{fact['id']} has unknown kind {fact['kind']}"]
    if fact.get("kind") == "forbid" and "pattern" not in fact:
        return [f"{fact['id']} forbid fact needs a pattern"]
    for field in ("pattern", "coverage"):
        if field in fact:
            try:
                re.compile(fact[field])
            except re.error as error:
                return [f"{fact['id']} invalid {field} regex: {error}"]
    if "verified" in fact:
        try:
            date.fromisoformat(fact["verified"])
        except ValueError:
            return [f"{fact['id']} verified date must be YYYY-MM-DD"]
    if ("pattern" in fact and fact.get("kind") != "forbid" and "value" not in fact):
        return [f"{fact['id']} value fact needs a value"]
    if "upstream" not in fact:
        return []
    if "extract" not in fact:
        return [f"{fact['id']} has `upstream` but no `extract` regex"]
    try:
        if re.compile(fact["extract"]).groups < 1:
            return [f"{fact['id']} extract regex needs a capturing group"]
    except re.error as error:
        return [f"{fact['id']} invalid extract regex: {error}"]
    if fact.get("extract_all", "false") not in ("true", "false"):
        return [f"{fact['id']} extract_all must be true or false"]
    if not oracle_allowed(fact):
        return [f"{fact['id']} upstream {fact['upstream']} is not https on an allowed host ({', '.join(sorted(ORACLE_HOSTS))})"]
    if "value" not in fact:
        return [f"{fact['id']} upstream oracle needs a value"]
    return []


def md_files():
    for dirpath, _, names in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if ".git" in rel.split(os.sep):
            continue
        for name in names:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def main():
    parser = argparse.ArgumentParser(description="Check skill text against docs/versioned-facts.md.")
    parser.add_argument("--upstream", action="store_true", help="also compare each fact with its upstream oracle (network)")
    args = parser.parse_args()

    facts = load_facts()
    mismatches, warnings = [], []
    oracles = oracles_compared = 0
    today = date.today()

    for f in facts:
        errors = definition_errors(f)
        if errors:
            mismatches += [f"docs/versioned-facts.md: {e}" for e in errors]
            continue
        age = (today - date.fromisoformat(f["verified"])).days if "verified" in f else None
        if age is not None and age > STALE_DAYS:
            warnings.append(f"{f['id']}: verified {f.get('verified')} is {age}d old — re-check source")
        if "upstream" in f:
            oracles += 1
        if args.upstream and "upstream" in f:
            try:
                current = upstream_value(f)
            except ExtractError as e:
                warnings.append(f"{f['id']}: oracle fetched but extract failed ({e}) — upstream format may have moved")
            except UpstreamError as e:
                warnings.append(f"{f['id']}: could not fetch upstream ({e})")
            else:
                oracles_compared += 1
                if not agrees(f, current):
                    mismatches.append(f"docs/versioned-facts.md: {f['id']} = '{f['value']}' but {f['upstream']} now says '{current}'")
        if "pattern" not in f:
            continue
        rx = re.compile(f["pattern"])
        for path in md_files():
            if os.path.abspath(path) == FACTS:
                continue
            for i, line in enumerate(open(path), 1):
                for m in rx.finditer(line):
                    rel = os.path.relpath(path, ROOT)
                    if f.get("kind") == "forbid":
                        if f.get("negation") == "true" and negated(line, m.start(), m.end()):
                            continue
                        mismatches.append(
                            f"{rel}:{i}: '{m.group(0)}' is a stale claim — {f['id']} ({f.get('source', 'see versioned-facts.md')})"
                        )
                    elif not value_in_hit(f, m.group(0)):
                        mismatches.append(
                            f"{rel}:{i}: '{m.group(0)}' conflicts with {f['id']} = '{f['value']}'"
                        )

    for w in warnings:
        print(f"WARN  {w}")
    for m in mismatches:
        print(f"STALE {m}")
    summary = f"{len(facts)} facts checked"
    if args.upstream:
        summary += f", {oracles_compared}/{oracles} upstream oracles compared"
    summary += f", {len(warnings)} warning(s)"
    if mismatches:
        print(f"FAILED: {summary}; {len(mismatches)} possible stale reference(s); update the file or versioned-facts.md")
        return 1
    if args.upstream and (oracles_compared != oracles or oracles == 0):
        print(f"INCOMPLETE: {summary}; upstream verification incomplete; no contradictions found in completed checks")
        return 2
    if args.upstream:
        print(f"{summary}; upstream verification complete, no contradictions")
    else:
        print(f"{summary}; local claims consistent; upstream verification not requested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
