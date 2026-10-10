"""Tests for docs/check-facts.py and docs/verify-claims.py. No network.

    python3 -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "docs", filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vc = load("verify_claims", "verify-claims.py")
cf = vc.check_facts  # one copy, so both modules share UpstreamError

FACTS = [
    {"id": "zakura-image", "value": "zakuracore/zakura:1.6.0", "pattern": r"zakuracore/zakura:[0-9a-zA-Z.\-]+",
     "upstream": "https://raw.githubusercontent.com/o/r/main/runtime.rs", "extract": r'const ZAKURA_IMAGE: &str = "([^"]+)"'},
    {"id": "faucet", "kind": "forbid", "pattern": r"faucet has no idempotency", "source": "api.rs"},
    {"id": "ths-version", "value": "ths 0.3.0", "pattern": r"ths \d+\.\d+\.\d+"},
]
RUNTIME_RS = 'const ZAKURA_IMAGE: &str = "zakuracore/zakura:1.6.0";\n'
ZIP_259 = "CONSENSUS_BRANCH_ID\n: `0x77190AD9`\n\nACTIVATION_HEIGHT (NU7)\n: Testnet: 4465026\n: Mainnet: TBD\n"
REPO = {"crates/ths-server/src/db.rs": "fn claim_address_faucet() {}\n", "Cargo.toml": '[workspace.package]\nversion = "0.3.0"\n'}
LEARN_INDEX_HTML = (
    '<html><a href="/learn/what-is-zcash/">a</a> <a href="https://z.cash/learn/what-are-zk-snarks/?x=1">b</a> '
    '<a href="https://z.cash/learn/feed/">feed</a> <a href="https://z.cash/learn/page/2/">2</a> '
    '<a href="https://evil.example/learn/x/">x</a></html>'
)
LEARN = {
    "https://z.cash/learn/": LEARN_INDEX_HTML,
    "https://z.cash/learn/page/2/": '<html><a href="/learn/run-a-zcash-full-node/">c</a></html>',
    "https://z.cash/learn/what-is-zcash/": "<html><p>Zcash launched in 2016.</p></html>",
    "https://z.cash/learn/what-are-zk-snarks/": "<html><p>Halo 2 removed the trusted setup.</p></html>",
    "https://z.cash/learn/run-a-zcash-full-node/": "<html><p>Run <code>zebrad</code> &amp; sync.</p></html>",
}


def fake_fetch(pages, calls=None):
    """Exact URLs map to text; a key ending in * matches by prefix and maps to a function of the URL."""
    def fetch(url, headers=None):
        if calls is not None:
            calls.append((url, headers))
        for key, page in pages.items():
            if key.endswith("*") and url.startswith(key[:-1]):
                return page(url)
        if pages.get(url) is None:
            raise cf.UpstreamError(f"{url}: HTTP Error 404: Not Found")
        return pages[url]
    return fetch


ZIPS = {"zips/zip-0259.md": ZIP_259, "zips/zip-0032.rst": "Hardened derivation uses 2^31.\n", "README.rst": "0x5BA81B19\n"}


def fake_archive(url):
    if "thus-spoke-zakura" in url:
        return REPO
    if "zcash/zips" in url:
        return ZIPS
    raise cf.UpstreamError(f"{url}: unreachable")


def diff_for(path, *lines, start=10):
    added = "".join(f"+{line}\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -{start},1 +{start},{len(lines) + 1} @@\n context\n{added}"


def run(lines, links=(), pages=None, path="skills/zakura/SKILL.md", facts=FACTS, diff=None, token=None, calls=None, sleep=None):
    pages = {FACTS[0]["upstream"]: RUNTIME_RS, **(pages or {})}
    diff = diff if diff is not None else diff_for(path, *lines)
    results, _, sources = vc.verify(vc.parse_diff(diff), facts, list(links), fake_fetch(pages, calls), fake_archive,
                                    token=token, sleep=sleep or (lambda s: None))
    return results, sources


def run_full(lines):
    results, sources = run(lines)
    return results, [], sources


def rtd_response(*blocks, path="/en/latest/rtd_pages/zig.html"):
    return lambda url: json.dumps({"count": 1, "results": [{"path": path, "blocks": [{"content": b} for b in blocks]}]})


def code_response(*fragments, repo="zodl-inc/zcash-android-wallet-sdk", path="sdk/Foo.kt"):
    return lambda url: json.dumps({"total_count": 1, "items": [
        {"path": path, "html_url": f"https://github.com/{repo}/blob/main/{path}", "repository": {"full_name": repo},
         "text_matches": [{"fragment": f} for f in fragments]}]})


class ParseTests(unittest.TestCase):
    def test_added_lines_get_new_file_line_numbers(self):
        claims = vc.parse_diff(diff_for("skills/zakura/SKILL.md", "first", "second", start=40))
        self.assertEqual(claims, [("skills/zakura/SKILL.md", 41, "first"), ("skills/zakura/SKILL.md", 42, "second")])

    def test_only_skill_files_are_in_scope(self):
        for path in ("README.md", "docs/check-facts.py", "index.html"):
            self.assertEqual(vc.parse_diff(diff_for(path, "x")), [])
        for path in ("SKILL.md", "skills/zcash/SKILL.md", "docs/versioned-facts.md"):
            self.assertEqual(len(vc.parse_diff(diff_for(path, "x"))), 1)

    def test_every_versioned_facts_line_is_a_claim(self):
        path = "docs/versioned-facts.md"
        for line in ("| Pinned node image | `zakuracore/zakura:1.6.0` |", "value: 0x77190AD9", "pattern: 0x77190AD9",
                     "upstream: https://example.com/x", "extract: (.*)", "kind: forbid", "```facts", "A block may set `kind`"):
            with self.subTest(line):
                self.assertTrue(vc.is_claim(path, line))
        self.assertFalse(vc.is_claim(path, "   "))
        self.assertFalse(vc.is_claim(path, "| --- | --- |"))
        self.assertFalse(vc.is_claim("skills/zcash/SKILL.md", "```bash"))

    def test_directives_are_fact_definition_lines_other_than_value(self):
        path = "docs/versioned-facts.md"
        for line in ("id: x", "pattern: y", "upstream: z", "extract: (.)", "kind: forbid", "source: a", "verified: 2026-10-10", "```"):
            self.assertTrue(vc.is_directive(path, line), line)
        for line in ("value: 1.6.0", "| Fact | Value |", "Each block maps a `pattern`"):
            self.assertFalse(vc.is_directive(path, line), line)
        self.assertFalse(vc.is_directive("skills/zakura/SKILL.md", "pattern: y"))

    def test_values_skip_dates_zip_numbers_links_and_placeholders(self):
        line = ("NU7 Testnet height 4,465,026 (2026-10-06), see ZIP 2003 and [ZIP 259](https://zips.z.cash/zip-0259); "
                "image `zakuracore/zakura:1.6.0`, `ths:send:{json}`, `zakura-*`, `regtest_network()`, v1.2.0, `0x77190AD9`")
        self.assertEqual(vc.values_in(line), ["zakuracore/zakura:1.6.0", "regtest_network", "0x77190AD9", "v1.2.0", "4,465,026"])

    def test_template_example_links_are_not_sources(self):
        body = "Fix.\n\nSource(s) of truth:\n<!-- e.g. https://zips.z.cash/zip-0259 -->\n- https://zips.z.cash/zip-0258.\n"
        self.assertEqual(vc.source_links(body), ["https://zips.z.cash/zip-0258"])

    def test_unclosed_comment_hides_the_rest_in_linear_time(self):
        self.assertEqual(vc.source_links("https://zips.z.cash/zip-0258 <!-- https://zips.z.cash/zip-0259"), ["https://zips.z.cash/zip-0258"])
        started = time.monotonic()
        vc.source_links("<!--" * 50_000)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_quoted_diff_paths_are_decoded(self):
        # git C-quotes paths containing quotes, backslashes, controls or non-ASCII.
        diff = ('diff --git "a/skills/na\\303\\257ve/SKILL.md" "b/skills/na\\303\\257ve/SKILL.md"\n'
                '--- "a/skills/na\\303\\257ve/SKILL.md"\n'
                '+++ "b/skills/na\\303\\257ve/SKILL.md"\n'
                "@@ -0,0 +1,1 @@\n"
                "+claim\n")
        self.assertEqual(vc.parse_diff(diff), [("skills/naïve/SKILL.md", 1, "claim")])
        quoted = '+++ "b/skills/we\\"ird/SKILL.md"\n@@ -0,0 +1,1 @@\n+claim\n'
        self.assertEqual(vc.parse_diff(quoted), [("skills/we\"ird/SKILL.md", 1, "claim")])

    def test_undecodable_quoted_diff_paths_are_skipped(self):
        for header in ('+++ "b/skills/unclosed/SKILL.md\n', '+++ "b/skills/bad\\x99utf8/SKILL.md"\n'):
            diff = f"{header}@@ -0,0 +1,1 @@\n+claim\n"
            self.assertEqual(vc.parse_diff(diff), [])

    def test_search_terms_cannot_break_the_quoted_query(self):
        self.assertEqual(vc.search_term('foo"bar'), "foobar")
        self.assertEqual(vc.search_term('"'), "")
        calls = []
        run(["Use `foo\"bar` to send."], pages={vc.RTD_SEARCH + "*": rtd_response("nothing")}, token="t",
            calls=calls, sleep=lambda s: None)
        search_urls = [u for u, _ in calls if u.startswith(vc.RTD_SEARCH)]
        self.assertTrue(search_urls)
        self.assertIn(urllib.parse.quote('project:zcash "foobar"'), search_urls[0])
        self.assertNotIn('"foo"', search_urls[0])


class TrustBoundaryTests(unittest.TestCase):
    """Review of #4: verdicts never depend on anything the PR controls."""

    def verdicts(self, results):
        return {r["text"]: r["verdict"] for r in results}

    def test_pr_cannot_mint_verified_by_editing_the_facts_file(self):
        # The PR rewrites the fact and its oracle, then claims the new value.
        facts_diff = diff_for("docs/versioned-facts.md", "value: zakuracore/zakura:9.9.9", "pattern: .*",
                              "upstream: https://evil.example/runtime.rs")
        skill_diff = diff_for("skills/zakura/SKILL.md", "THS pins `zakuracore/zakura:9.9.9`.")
        calls = []
        results, _ = run([], diff=facts_diff + skill_diff, calls=calls)
        v = self.verdicts(results)
        self.assertEqual(v["THS pins `zakuracore/zakura:9.9.9`."], "❌")  # the base oracle still says 1.6.0
        self.assertEqual(v["value: zakuracore/zakura:9.9.9"], "❌")
        self.assertEqual(v["pattern: .*"], "⚠️")
        self.assertEqual(v["upstream: https://evil.example/runtime.rs"], "⚠️")
        self.assertFalse(any("evil.example" in url for url, _ in calls))

    def test_directive_lines_are_left_for_review_and_not_parsed(self):
        results, _ = run(["kind: forbid", "pattern: zakuracore/zakura:1.5.0", "extract: (.*)"], path="docs/versioned-facts.md")
        self.assertEqual([r["verdict"] for r in results], ["⚠️"] * 3)
        self.assertTrue(all(r.get("directive") for r in results))
        self.assertIn("fact definition", results[0]["evidence"])

    def test_fact_update_without_an_oracle_is_left_for_review(self):
        diff = diff_for("docs/versioned-facts.md", "value: ths 0.4.0") + diff_for("skills/ths/SKILL.md", "Install ths 0.4.0 first.")
        results, _ = run([], diff=diff)
        self.assertEqual(set(self.verdicts(results).values()), {"⚠️"})
        self.assertIn("this PR changes that fact", results[1]["evidence"])

    def test_value_that_disagrees_with_base_fact_fails_when_the_pr_does_not_change_it(self):
        results, _ = run(["Install ths 0.4.0 first."])
        self.assertEqual(results[0]["verdict"], "❌")
        self.assertIn("ths-version", results[0]["evidence"])

    def test_bump_that_matches_the_base_oracle_is_verified_with_a_note(self):
        moved = {FACTS[0]["upstream"]: 'const ZAKURA_IMAGE: &str = "zakuracore/zakura:1.7.0";'}
        results, _ = run(["THS pins `zakuracore/zakura:1.7.0`."], pages=moved)
        self.assertEqual(results[0]["verdict"], "✅")
        self.assertIn("still says", results[0]["evidence"])

    def test_non_allowlisted_oracle_is_never_fetched(self):
        facts = [dict(FACTS[0], upstream="https://evil.example/runtime.rs")]
        calls = []
        results, _ = run(["THS pins `zakuracore/zakura:1.6.0`."], facts=facts, calls=calls)
        self.assertEqual(results[0]["verdict"], "⚠️")
        self.assertIn("oracle host not allowed", results[0]["evidence"])
        self.assertFalse(any("evil.example" in url for url, _ in calls))

    def test_long_lines_are_not_parsed(self):
        line = "THS pins `zakuracore/zakura:1.5.0`. " + "a" * vc.MAX_CLAIM_CHARS
        calls = []
        results, _ = run([line], calls=calls)
        self.assertEqual(results[0]["verdict"], "⚠️")  # would be ❌ if the pattern had run
        self.assertTrue(results[0].get("prose"))
        self.assertEqual(calls, [])

    def test_workflow_reads_facts_from_the_base_checkout_only(self):
        with open(os.path.join(ROOT, ".github", "workflows", "fact-check.yml"), encoding="utf-8") as fh:
            wf = fh.read()
        for banned in ("refs/pull", "FETCH_HEAD", "--facts", "git show"):
            self.assertNotIn(banned, wf)
        self.assertRegex(wf, r"(?m)^\s+issues: write\b")
        self.assertRegex(wf, r"(?m)^\s+pull-requests: write\b")
        self.assertIn("persist-credentials: false", wf)


class HostAllowlistTests(unittest.TestCase):
    def test_host_allowed(self):
        self.assertTrue(cf.host_allowed("https://raw.githubusercontent.com/a/b/main/c.rs"))
        self.assertTrue(cf.host_allowed("https://api.github.com/search/code?q=x"))
        for url in ("http://raw.githubusercontent.com/a", "https://evil.example/", "https://raw.githubusercontent.com:8443/a",
                    "https://raw.githubusercontent.com@evil.example/a", "https://user@zips.z.cash/", "https://zips.z.cash:bad/",
                    "file:///etc/passwd", "https://z.cash.evil.example/"):
            self.assertFalse(cf.host_allowed(url), url)
        self.assertFalse(cf.host_allowed("https://api.github.com/x", cf.ORACLE_HOSTS))

    def test_fetch_refuses_hosts_off_the_allowlist_without_connecting(self):
        with self.assertRaises(cf.HostNotAllowed):
            cf.fetch("https://evil.example/")

    def test_redirects_off_the_allowlist_are_refused(self):
        handler = cf._AllowlistRedirects()
        req = urllib.request.Request("https://raw.githubusercontent.com/a/b/main/c.rs")
        with self.assertRaises(cf.HostNotAllowed):
            handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/c.rs")

    def test_authorization_is_not_forwarded_on_redirect(self):
        handler = cf._AllowlistRedirects()
        req = urllib.request.Request("https://api.github.com/search/code?q=x")
        req.add_unredirected_header("Authorization", "Bearer t")
        new = handler.redirect_request(req, None, 302, "Found", {}, "https://raw.githubusercontent.com/a")
        self.assertIsNone(new.get_header("Authorization"))

    def test_upstream_value_refuses_disallowed_oracles(self):
        called = []
        with self.assertRaises(cf.HostNotAllowed):
            cf.upstream_value({"upstream": "https://evil.example/x", "extract": "(.*)"}, fetch=lambda u: called.append(u))
        self.assertEqual(called, [])

    def test_check_facts_rejects_bad_oracle_definitions(self):
        self.assertEqual(cf.definition_errors({"id": "a", "value": "1"}), [])
        self.assertIn("no `extract`", cf.definition_errors({"id": "a", "upstream": "https://zips.z.cash/x"})[0])
        self.assertIn("not https on an allowed host", cf.definition_errors({"id": "a", "upstream": "https://evil.example/x", "extract": "(.)"})[0])
        self.assertEqual(cf.definition_errors({"id": "a", "upstream": "https://zips.z.cash/x", "extract": "(.)"}), [])

    def test_disallowed_pr_source_is_listed_not_fetched(self):
        fetched = []

        def fetch(url, headers=None):
            fetched.append(url)
            return RUNTIME_RS
        _, provided, _ = vc.verify(vc.parse_diff(diff_for("SKILL.md", "x")), FACTS,
                                   ["https://example.com/post", "http://zips.z.cash/zip-0259"], fetch, fake_archive)
        self.assertEqual(fetched, [])
        self.assertEqual([p[1] for p in provided], [None, None])


class VerdictTests(unittest.TestCase):
    def verdicts(self, results):
        return [r["verdict"] for r in results]

    def test_value_that_disagrees_with_a_fact_is_a_contradiction(self):
        results, _ = run(["THS pins `zakuracore/zakura:1.5.0`."])
        self.assertEqual(self.verdicts(results), ["❌"])
        self.assertIn("zakura-image", results[0]["evidence"])

    def test_fact_that_upstream_moved_past_is_a_contradiction(self):
        moved = {FACTS[0]["upstream"]: 'const ZAKURA_IMAGE: &str = "zakuracore/zakura:1.7.0";'}
        results, _ = run(["THS pins `zakuracore/zakura:1.6.0`."], pages=moved)
        self.assertEqual(self.verdicts(results), ["❌"])
        self.assertIn("now says `zakuracore/zakura:1.7.0`", results[0]["evidence"])

    def test_fact_confirmed_upstream_is_verified(self):
        results, _ = run(["THS pins `zakuracore/zakura:1.6.0`."])
        self.assertEqual(self.verdicts(results), ["✅"])

    def test_unreachable_upstream_never_fails(self):
        results, _ = run(["THS pins `zakuracore/zakura:1.6.0`."], pages={FACTS[0]["upstream"]: None})
        self.assertEqual(self.verdicts(results), ["⚠️"])  # not re-verified, so left for review
        self.assertIn("upstream unreachable", results[0]["evidence"])

    def test_forbidden_claim_is_a_contradiction(self):
        results, _ = run(["The address faucet has no idempotency key."])
        self.assertEqual(self.verdicts(results), ["❌"])

    def test_linked_source_verifies_its_values(self):
        url = "https://github.com/zcash/zips/blob/main/zips/zip-0259.md"
        raw = "https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0259.md"
        results, _ = run(["NU7 uses branch ID `0x77190AD9`."], links=[url], pages={raw: ZIP_259})
        self.assertEqual(self.verdicts(results), ["✅"])
        self.assertIn("PR source", results[0]["evidence"])

    def test_cited_zip_is_fetched_with_rst_fallback(self):
        rst = "https://raw.githubusercontent.com/zcash/zips/main/zips/zip-0316.rst"
        results, sources = run(["ZIP 316 caps an encoding at 1024 bytes."], pages={rst: "... at most 1024 bytes ..."})
        self.assertEqual(self.verdicts(results), ["✅"])
        self.assertIn("zip-0316.rst", results[0]["evidence"])
        self.assertEqual(sources.failures, [])  # the .md miss is expected, not a failure

    def test_names_and_paths_are_found_in_upstream_source(self):
        results, _ = run(["`claim_address_faucet` lives in `crates/ths-server/src/db.rs`."])
        self.assertEqual(self.verdicts(results), ["✅"])
        self.assertIn("thus-spoke-zakura/crates/ths-server/src/db.rs", results[0]["evidence"])

    def test_unknown_name_is_left_for_review_and_says_what_was_not_consulted(self):
        results, _ = run(["Call `list_accounts_for_ui` first."])
        self.assertEqual(self.verdicts(results), ["⚠️"])
        ev = results[0]["evidence"]
        self.assertIn("`list_accounts_for_ui` not found in THS/Zakura source", ev)
        self.assertIn("zodl-inc code search (no GITHUB_TOKEN)", ev)
        self.assertIn("z.cash/learn (unreachable)", ev)

    def test_line_with_nothing_to_match_is_prose(self):
        results, _ = run(["Prefer evidence over memory."])
        self.assertTrue(results[0].get("prose"))


class ContainsTests(unittest.TestCase):
    def test_word_tokens_need_a_whole_word(self):
        self.assertFalse(vc.contains("networking stack", "network"))
        self.assertFalse(vc.contains("fn test_main() {}", "test"))
        self.assertFalse(vc.contains("mainnet", "main"))
        self.assertTrue(vc.contains("the network upgrade", "network"))
        self.assertTrue(vc.contains("(regtest_network)", "regtest_network"))

    def test_punctuated_tokens_match_as_substrings(self):
        self.assertTrue(vc.contains('image = "zakuracore/zakura:1.6.0";', "zakuracore/zakura:1.6.0"))
        self.assertTrue(vc.contains("see crates/ths-server/src/db.rs:10", "ths-server/src/db.rs"))

    def test_numbers_ignore_digit_grouping_but_not_neighbouring_digits(self):
        self.assertTrue(vc.contains("height 4465026.", "4,465,026"))
        self.assertFalse(vc.contains("height 44650260", "4465026"))

    def test_hex_ids_match_in_either_case_but_not_inside_longer_hex(self):
        self.assertTrue(vc.contains("branch id ``0xc2d6d0b4``", "0xC2D6D0B4"))
        self.assertFalse(vc.contains("0xC2D6D0B4FF", "0xC2D6D0B4"))

    def test_upstream_name_search_uses_whole_words(self):
        results, _ = run(["Use `ths` here."])  # "ths" only appears inside ths-server
        self.assertEqual(results[0]["verdict"], "⚠️")


class CanonicalSetTests(unittest.TestCase):
    """Item 3 of the review: the canonical set is consulted without author links."""

    def test_learn_articles_are_crawled_once_and_searched(self):
        calls = []
        results, sources = run(["`zebrad` syncs the chain.", "Since 2016 `zebrad` runs."], pages=LEARN, calls=calls)
        self.assertEqual(results[0]["verdict"], "✅")
        self.assertIn("learn/run-a-zcash-full-node", results[0]["evidence"])
        fetched = [u for u, _ in calls if "z.cash" in u]
        self.assertEqual(len(fetched), len(set(fetched)))  # one fetch per page per run
        self.assertNotIn("https://z.cash/learn/feed/", fetched)
        self.assertFalse(any("evil.example" in u for u, _ in calls))
        self.assertEqual(sources.learn_articles, 3)

    def test_uncited_values_are_checked_against_every_zip(self):
        results, sources = run(["NU7 uses branch ID `0x77190AD9`."])  # no ZIP cited, no PR source
        self.assertEqual(results[0]["verdict"], "✅")
        self.assertIn("[zip-0259.md](https://zips.z.cash/zip-0259)", results[0]["evidence"])
        results, _ = run(["Sapling uses `0x5BA81B19`."])  # only outside zips/, so not a ZIP
        self.assertEqual(results[0]["verdict"], "⚠️")
        self.assertIn("the ZIP index", results[0]["evidence"])
        self.assertIn("the ZIP index", vc.render(*run_full(["NU7 uses branch ID `0x77190AD9`."])))

    def test_learn_index_without_articles_is_reported_as_such(self):
        results, _ = run(["`zebrad` syncs."], pages={"https://z.cash/learn/": "<html>redesigned</html>"})
        self.assertIn("z.cash/learn (no articles found)", results[0]["evidence"])

    def test_readthedocs_search_confirms_exact_matches_only(self):
        pages = {vc.RTD_SEARCH + "*": rtd_response("This API can send through the z_sendmany call.")}
        results, sources = run(["Use `z_sendmany` to send."], pages=pages)
        self.assertEqual(results[0]["verdict"], "✅")
        self.assertIn("readthedocs zig.html", results[0]["evidence"])
        self.assertIn("https://zcash.readthedocs.io/en/latest/rtd_pages/zig.html", results[0]["evidence"])
        results, _ = run(["Use `z_send` to send."], pages=pages)  # only a prefix of z_sendmany
        self.assertEqual(results[0]["verdict"], "⚠️")
        self.assertIn("zcash.readthedocs.io", results[0]["evidence"])

    def test_readthedocs_query_uses_the_project_filter(self):
        calls = []
        run(["Height 7,777,777."], pages={vc.RTD_SEARCH + "*": rtd_response("nothing")}, calls=calls)
        q = next(u for u, _ in calls if u.startswith(vc.RTD_SEARCH))
        self.assertEqual(urllib.parse.unquote(q[len(vc.RTD_SEARCH):]), 'project:zcash "7777777"')

    def test_readthedocs_is_capped_per_run(self):
        names = [f"`name_{i}`" for i in range(vc.RTD_MAX_QUERIES + 3)]
        calls = []
        results, sources = run([" ".join(names)], pages={vc.RTD_SEARCH + "*": rtd_response("nothing")}, calls=calls)
        self.assertEqual(sources.rtd_queries, vc.RTD_MAX_QUERIES)
        self.assertIn("per-run cap", results[0]["evidence"])

    def test_zodl_code_search_with_token(self):
        calls, slept = [], []
        pages = {vc.CODE_SEARCH + "*": code_response("val accountUuid = AccountUuid(bytes)")}
        results, sources = run(["`AccountUuid` and `accountUuid` are wallet ids."], pages=pages, token="t0k", calls=calls,
                               sleep=slept.append)
        self.assertEqual(results[0]["verdict"], "✅")
        self.assertIn("zodl-inc/zcash-android-wallet-sdk/sdk/Foo.kt", results[0]["evidence"])
        searches = [(u, h) for u, h in calls if u.startswith(vc.CODE_SEARCH)]
        self.assertEqual(len(searches), 2)
        self.assertEqual(searches[0][1]["Authorization"], "Bearer t0k")
        self.assertIn(urllib.parse.quote('org:zodl-inc "AccountUuid"'), searches[0][0])
        self.assertEqual(slept, [vc.CODE_SEARCH_INTERVAL])  # spaced out, not before the first call
        self.assertTrue(all(h is None or "Authorization" not in h for u, h in calls if not u.startswith(vc.CODE_SEARCH)))

    def test_zodl_code_search_stops_after_a_rate_limit(self):
        def limited(url):
            raise cf.UpstreamError(f"{url}: HTTP Error 403: rate limit exceeded")
        calls = []
        results, sources = run(["`first_name` then `second_name`."], pages={vc.CODE_SEARCH + "*": limited}, token="t", calls=calls)
        self.assertEqual(len([u for u, _ in calls if u.startswith(vc.CODE_SEARCH)]), 1)
        self.assertIn("zodl-inc code search (search failed)", results[0]["evidence"])
        self.assertEqual(sources.code_stopped, "rate limited")

    def test_zodl_code_search_is_capped_per_run(self):
        names = " ".join(f"`name_{i}`" for i in range(vc.CODE_SEARCH_MAX + 2))
        _, sources = run([names], pages={vc.CODE_SEARCH + "*": code_response("nothing")}, token="t")
        self.assertEqual(sources.code_queries, vc.CODE_SEARCH_MAX)

    def test_odd_search_payloads_do_not_crash(self):
        for payload in ("[]", '{"results": 3}', '{"results": [1, {"blocks": "x"}]}', "not json"):
            with self.subTest(payload):
                results, _ = run(["Use `z_sendmany`."], pages={vc.RTD_SEARCH + "*": lambda url, p=payload: p})
                self.assertEqual(results[0]["verdict"], "⚠️")


class ReportTests(unittest.TestCase):
    def test_missing_sources_asks_the_author(self):
        results, sources = run(["Prefer evidence over memory."])
        report = vc.render(results, [], sources)
        self.assertTrue(report.startswith(vc.MARKER))
        self.assertIn("No sources in the PR description", report)

    def test_pipes_in_claims_do_not_break_the_table(self):
        self.assertEqual(vc.cell("a | b"), "a \\| b")

    def test_cell_escapes_links_html_code_and_mentions(self):
        out = vc.cell("[x](https://evil.example) ![i](u) <img src=x onerror=alert(1)> `c` \\| @someone &amp;")
        for ch in "[]<>`":
            self.assertNotIn(ch, out)
        self.assertNotIn("@someone", out)
        self.assertNotIn("\\\\|", out)  # a PR backslash cannot unescape our pipe escape
        self.assertIn("&amp;amp;", out)

    def test_report_has_no_markup_from_the_pr(self):
        line = "See [docs](https://evil.example) <details open> `<img src=x>` and `a|b` @maintainer"
        path = "skills/x<b>`y`.md"
        results, sources = run([line], path=path)
        report = vc.render(results, [], sources)
        body = report.split("\n", 1)[1]
        self.assertNotIn("<img", body)
        self.assertNotIn("<b>", body)
        self.assertNotIn("<details open>", body)
        self.assertNotIn("](https://evil.example", body)
        self.assertNotIn("@maintainer", body)
        table = [l for l in body.splitlines() if l.startswith("| ") and "---" not in l][1:]
        for row in table:
            self.assertEqual(len(re.findall(r"(?<!\\)\|", row)), 5, row)

    def test_bare_urls_in_claims_are_not_autolinked(self):
        out = vc.cell("see https://evil.example and www.evil.example or HTTP://x.example")
        self.assertNotIn("https://", out)
        self.assertNotIn("www.", out)
        self.assertNotIn("HTTP://", out)

    def test_link_targets_are_percent_encoded(self):
        self.assertEqual(vc.link("x", "https://z.cash/learn/a(b)/<c>"), "[x](https://z.cash/learn/a%28b%29/%3Cc%3E)")

    def test_footer_states_what_was_consulted(self):
        results, sources = run(["`zebrad` syncs."], pages=LEARN)
        report = vc.render(results, [], sources)
        self.assertIn("z.cash/learn (3 articles)", report)
        self.assertIn("base branch's `docs/versioned-facts.md`", report)


class CheckFactsTests(unittest.TestCase):
    def test_agrees_ignores_commas_backticks_and_case(self):
        self.assertTrue(cf.agrees({"value": "4,465,026"}, "4465026"))
        self.assertTrue(cf.agrees({"value": "Rust 1.98.0"}, "1.98.0"))
        self.assertTrue(cf.agrees({"value": "0x77190AD9"}, "0x77190ad9"))
        self.assertFalse(cf.agrees({"value": "4,465,026"}, "4465027"))

    def test_repo_oracles_extract_from_upstream_formats(self):
        facts = {f["id"]: f for f in cf.load_facts()}
        samples = {
            "nu7-testnet-height": (ZIP_259, "4465026"),
            "nu7-branch-id": (ZIP_259, "0x77190AD9"),
            "nu63-branch-id": ("CONSENSUS_BRANCH_ID\n: 0x37A5165B\n", "0x37A5165B"),
            "nu63-mainnet-height": ("ACTIVATION_HEIGHT (NU6.3)\n: Testnet: 4134000\n: Mainnet: 3428143\n", "3428143"),
            "ths-workspace-version": ('[workspace]\nresolver = "2"\n\n[workspace.package]\nversion = "0.3.0"\n', "0.3.0"),
            "ths-rust-toolchain": ('[toolchain]\nchannel = "1.98.0"\n', "1.98.0"),
            "zakura-image": (RUNTIME_RS, "zakuracore/zakura:1.6.0"),
        }
        for fid, (text, want) in samples.items():
            with self.subTest(fid):
                got = cf.upstream_value(facts[fid], fetch=lambda url, text=text: text)
                self.assertEqual(got, want)
                self.assertTrue(cf.agrees(facts[fid], got))

    def test_repo_oracles_are_all_allowlisted(self):
        for f in cf.load_facts():
            self.assertEqual(cf.definition_errors(f), [], f["id"])

    def test_nu7_height_pattern_catches_comma_grouped_heights(self):
        fact = {f["id"]: f for f in cf.load_facts()}["nu7-testnet-height"]
        hit = re.search(fact["pattern"], "NU7 activated on Testnet at height 4,465,027.").group(0)
        self.assertNotIn(fact["value"], hit)

    def test_repo_is_clean_offline(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "docs", "check-facts.py")], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout)


class CliTests(unittest.TestCase):
    def test_out_of_scope_diff_exits_zero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as fh:
            fh.write(diff_for("README.md", "anything"))
        try:
            out = subprocess.run([sys.executable, os.path.join(ROOT, "docs", "verify-claims.py"), "--diff", fh.name], capture_output=True, text=True)
        finally:
            os.unlink(fh.name)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("No added lines", out.stdout)

    def test_base_mode_takes_facts_from_the_base_ref_not_the_branch(self):
        # A throwaway repo: the base pins 1.6.0. The branch rewrites the fact's pattern so
        # nothing matches, then claims 9.9.9. Only the base's fact can catch that.
        facts = "```facts\nid: img\nvalue: zakuracore/zakura:1.6.0\npattern: zakuracore/zakura:[0-9.]+\n```\n"
        with tempfile.TemporaryDirectory() as repo:
            def git(*args):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                               cwd=repo, check=True, capture_output=True)

            def write(rel, text):
                os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
                with open(os.path.join(repo, rel), "w", encoding="utf-8") as fh:
                    fh.write(text)
            git("init", "-q", "-b", "base")
            write("docs/versioned-facts.md", facts)
            write("skills/a.md", "x\n")
            git("add", "-A")
            git("commit", "-qm", "base")
            git("checkout", "-qb", "pr")
            write("docs/versioned-facts.md", facts.replace("pattern: zakuracore/zakura:[0-9.]+", "pattern: matches-nothing"))
            write("skills/a.md", "x\nPins `zakuracore/zakura:9.9.9`.\n")
            git("commit", "-qam", "pr")

            out = io.StringIO()
            saved = (vc.ROOT, vc.check_facts.fetch, vc.fetch_archive, sys.argv, os.environ.pop("GITHUB_TOKEN", None), os.environ.pop("GH_TOKEN", None))
            vc.ROOT, vc.check_facts.fetch, vc.fetch_archive = repo, fake_fetch({}), fake_archive
            sys.argv = ["verify-claims.py", "--base", "base"]
            try:
                with contextlib.redirect_stdout(out):
                    code = vc.main()
            finally:
                vc.ROOT, vc.check_facts.fetch, vc.fetch_archive, sys.argv = saved[:4]
                for key, value in (("GITHUB_TOKEN", saved[4]), ("GH_TOKEN", saved[5])):
                    if value is not None:
                        os.environ[key] = value
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("conflicts with img = `zakuracore/zakura:1.6.0`", out.getvalue())
        self.assertIn("pattern: matches-nothing", out.getvalue())  # the rewritten pattern is a claim, not config

    def test_facts_cannot_be_supplied_on_the_command_line(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "docs", "verify-claims.py"), "--diff", os.devnull, "--facts", "x"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("unrecognized arguments: --facts", out.stderr)


if __name__ == "__main__":
    unittest.main()
