#!/usr/bin/env python3
"""Check that versioned facts stated in the skills match docs/versioned-facts.md.

Each ```facts block in versioned-facts.md declares a canonical `value` and a
`pattern` (regex). The checker scans every .md file in the repo for pattern
matches and reports matches that differ from the canonical value — the signal
that a skill went stale after an upstream bump (image tag, version, height).

It also warns when a fact's `verified` date is older than STALE_DAYS — a prompt
to re-verify, not a failure. Facts without a `pattern` are date-only.

A fact may set `kind: forbid` — then ANY pattern match in a doc is a
contradiction. Use it for stale claims of absence ("X has no idempotency key")
where upstream later added the thing; a value-check cannot express that.

A fact may also name an oracle: `upstream` (a raw file URL) and `extract` (a
regex whose first group is the value upstream states). With --upstream the
checker fetches each oracle and reports facts whose `value` no longer matches.
A fetch that fails is a warning, never a failure. An `upstream` must be an
https URL on ORACLE_HOSTS; any other host is an error and is never fetched.

Run from anywhere:  python3 docs/check-facts.py [--upstream]
Exit 0 = clean (or only warnings); exit 1 = contradictory values.
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
    m = re.search(fact["extract"], text, re.M)
    if not m:
        raise UpstreamError(f"{fact['upstream']}: extract pattern matched nothing")
    return m.group(1)


def agrees(fact, current):
    """True when the value upstream states is the one the fact records."""
    return norm_value(current) in norm_value(fact["value"])


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
    if "upstream" not in fact:
        return []
    if "extract" not in fact:
        return [f"{fact['id']} has `upstream` but no `extract` regex"]
    if not oracle_allowed(fact):
        return [f"{fact['id']} upstream {fact['upstream']} is not https on an allowed host ({', '.join(sorted(ORACLE_HOSTS))})"]
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
    today = date.today()

    for f in facts:
        age = (today - date.fromisoformat(f["verified"])).days if "verified" in f else None
        if age is not None and age > STALE_DAYS:
            warnings.append(f"{f['id']}: verified {f.get('verified')} is {age}d old — re-check source")
        errors = definition_errors(f)
        if errors:
            mismatches += [f"docs/versioned-facts.md: {e}" for e in errors]
            continue
        if args.upstream and "upstream" in f:
            try:
                current = upstream_value(f)
            except UpstreamError as e:
                warnings.append(f"{f['id']}: could not read upstream ({e})")
            else:
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
                        mismatches.append(
                            f"{rel}:{i}: '{m.group(0)}' is a stale claim — {f['id']} ({f.get('source', 'see versioned-facts.md')})"
                        )
                    elif f["value"] not in m.group(0) and m.group(0) not in f["value"]:
                        mismatches.append(
                            f"{rel}:{i}: '{m.group(0)}' conflicts with {f['id']} = '{f['value']}'"
                        )

    for w in warnings:
        print(f"WARN  {w}")
    for m in mismatches:
        print(f"STALE {m}")
    if mismatches:
        print(f"\n{len(mismatches)} possible stale reference(s); update the file or versioned-facts.md")
        return 1
    print(f"{len(facts)} facts checked, {len(warnings)} age warning(s), no contradictions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
