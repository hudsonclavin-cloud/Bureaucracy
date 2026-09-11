"""Seeding candidate pages from a directory: a candidate is something for the
verifier to fetch, never evidence, and every URL it adds is marked as seeded.

Each rule is tested in both directions: an admissible URL is added with its
provenance; an inadmissible one — http, a .org host, a node already in the
file, a URL already in the file — is refused and reported under its
category; a dry run writes nothing.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import urlparse

from data_pipeline.verification.evidence import load_official_sites
from scripts import seed_official_sites
from scripts.seed_official_sites import (
    PROVENANCE_NOTE_SENTENCE,
    SKIP_HAS_ENTRY,
    SKIP_HOST,
    SKIP_NOT_HTTPS,
    SKIP_ONE_PER_NODE,
    SKIP_PRESENT,
    apply_proposals,
    note_with_provenance_sentence,
)

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR = "federal_register_agency_directory"
FETCHED = "2026-09-08T19:19:15Z"
SITES = {
    "_note": "Candidate official pages, keyed by node id. A URL here is something to check, not evidence.",
    "exec-dept-doe": ["https://www.energy.gov/about-us"],
    "exec-eop-ondcp": ["https://www.whitehouse.gov/ondcp/"],
}


def fr_record(listed_name: str, agency_url: str | None) -> dict:
    return {
        "source": FR, "status": "listed", "entryId": 1, "listedName": listed_name,
        "url": "https://www.federalregister.gov/agencies/x", "agencyUrl": agency_url,
        "directoryUrl": "https://www.federalregister.gov/api/v1/agencies.json", "checkedAt": FETCHED,
    }


EVIDENCE = {
    "_note": "test",
    "nodes": {
        "exec-dept-usda-fs": fr_record("Forest Service", "https://www.fs.usda.gov"),
        "exec-dept-defense-agency-nga": fr_record("National Geospatial-Intelligence Agency", "https://www.nga.mil/"),
        "exec-ind-misc-cpb": fr_record("Corporation for Public Broadcasting", "https://www.cpb.org/"),
        "exec-dept-doc": fr_record("Commerce Department", "http://www.commerce.gov/"),
        "exec-dept-doe": fr_record("Energy Department", "https://www.energy.gov"),
        "exec-eop-ondcp-twin": fr_record("Drug Control Policy Office", "https://www.whitehouse.gov/ondcp"),
        "exec-eop-onadm": fr_record("Administration Office", None),
        "leg-senate-committee-x": {"source": "senate_committee_list", "status": "listed", "url": "https://www.senate.gov/x", "checkedAt": FETCHED},
    },
}


class ApplyProposalsTests(unittest.TestCase):
    """The importable core, driven with proposals shaped {node_id: [urls]}."""

    def _apply(self, proposals, sites=None, provenance=None, names=None):
        sites = json.loads(json.dumps(SITES)) if sites is None else sites
        provenance = {} if provenance is None else provenance
        outcome = apply_proposals(sites, proposals, source=FR, provenance=provenance, fetched_at=FETCHED, listed_names=names or {})
        return sites, provenance, outcome

    def test_an_https_gov_url_for_a_node_without_an_entry_is_added_with_provenance(self) -> None:
        sites, provenance, outcome = self._apply({"exec-dept-usda-fs": ["https://www.fs.usda.gov"]}, names={"exec-dept-usda-fs": "Forest Service"})
        self.assertEqual(outcome["added"], [("exec-dept-usda-fs", "https://www.fs.usda.gov")])
        self.assertEqual(sites["exec-dept-usda-fs"], ["https://www.fs.usda.gov"])
        self.assertEqual(provenance, {"exec-dept-usda-fs": {
            "url": "https://www.fs.usda.gov", "source": FR, "listedName": "Forest Service", "directoryFetchedAt": FETCHED,
        }})
        # The verifier's own loader reads the result as a candidate for that node.
        self.assertEqual(load_official_sites_from(sites)["exec-dept-usda-fs"], ["https://www.fs.usda.gov"])

    def test_a_mil_host_is_official_and_the_url_is_written_as_listed(self) -> None:
        sites, _, outcome = self._apply({"exec-dept-defense-agency-nga": ["https://www.nga.mil/"]})
        self.assertEqual(outcome["added"], [("exec-dept-defense-agency-nga", "https://www.nga.mil/")])
        self.assertEqual(sites["exec-dept-defense-agency-nga"], ["https://www.nga.mil/"])  # the trailing slash is kept

    def test_an_org_host_is_refused_and_reported(self) -> None:
        sites, provenance, outcome = self._apply({"exec-ind-misc-cpb": ["https://www.cpb.org/"]})
        self.assertEqual(outcome["added"], [])
        self.assertEqual(outcome["skipped"][SKIP_HOST], [("exec-ind-misc-cpb", "https://www.cpb.org/")])
        self.assertNotIn("exec-ind-misc-cpb", sites)
        self.assertEqual(provenance, {})

    def test_the_host_rule_is_on_the_host_not_the_string(self) -> None:
        """A .gov inside the path or a .gov-prefixed commercial host is not official."""
        _, _, outcome = self._apply({
            "a": ["https://example.com/.gov"], "b": ["https://www.gov.example.com/"], "c": ["https://usps.com/"],
            "d": ["https://si.edu/about"],
        })
        self.assertEqual(outcome["added"], [])
        self.assertEqual(sorted(n for n, _ in outcome["skipped"][SKIP_HOST]), ["a", "b", "c", "d"])

    def test_an_http_gov_url_is_upgraded_and_the_listed_url_kept_beside_it(self) -> None:
        """The directory lists 92 of 102 sites as http; every .gov is HSTS-
        preloaded by mandate, so the scheme is transport, not a claim."""
        sites, provenance, outcome = self._apply({"exec-dept-doc": ["http://www.commerce.gov/"]})
        self.assertEqual(sites["exec-dept-doc"], ["https://www.commerce.gov/"])
        self.assertEqual(outcome["added"], [("exec-dept-doc", "https://www.commerce.gov/")])
        self.assertEqual(provenance["exec-dept-doc"]["listedUrl"], "http://www.commerce.gov/")
        self.assertIs(provenance["exec-dept-doc"]["schemeUpgraded"], True)
        self.assertEqual(outcome["skipped"][SKIP_NOT_HTTPS], [])

    def test_an_http_url_on_any_other_host_is_still_refused(self) -> None:
        sites, _, outcome = self._apply({"x": ["http://www.usps.com/"], "y": ["http://example.org/"]})
        self.assertEqual(outcome["added"], [])
        self.assertNotIn("x", sites)
        self.assertEqual({n for n, _ in outcome["skipped"][SKIP_NOT_HTTPS]}, {"x", "y"})

    def test_an_existing_entry_is_left_exactly_as_it_was(self) -> None:
        sites, provenance, outcome = self._apply({"exec-dept-doe": ["https://www.energy.gov"]})
        self.assertEqual(sites["exec-dept-doe"], ["https://www.energy.gov/about-us"])
        self.assertEqual(outcome["skipped"][SKIP_HAS_ENTRY], [("exec-dept-doe", "https://www.energy.gov")])
        self.assertEqual(provenance, {})  # no provenance for what was never seeded

    def test_a_url_already_in_the_file_under_another_node_is_not_added_again(self) -> None:
        """Compared after whitespace and one trailing slash; nothing else."""
        sites, _, outcome = self._apply({"exec-eop-ondcp-twin": [" https://www.whitehouse.gov/ondcp "]})
        self.assertEqual(outcome["skipped"][SKIP_PRESENT], [("exec-eop-ondcp-twin", "https://www.whitehouse.gov/ondcp")])
        self.assertNotIn("exec-eop-ondcp-twin", sites)
        # A different path on the same host is a different page, and is added.
        sites, _, outcome = self._apply({"exec-eop-ondcp-twin": ["https://www.whitehouse.gov/ondcp/about/"]})
        self.assertEqual(outcome["added"], [("exec-eop-ondcp-twin", "https://www.whitehouse.gov/ondcp/about/")])

    def test_the_same_url_proposed_for_two_nodes_is_added_once(self) -> None:
        sites, provenance, outcome = self._apply({"b-node": ["https://www.ncua.gov"], "a-node": ["https://www.ncua.gov/"]})
        self.assertEqual(outcome["added"], [("a-node", "https://www.ncua.gov/")])  # first by node id
        self.assertEqual(outcome["skipped"][SKIP_PRESENT], [("b-node", "https://www.ncua.gov")])
        self.assertEqual(set(provenance), {"a-node"})

    def test_one_candidate_per_node_per_run(self) -> None:
        sites, provenance, outcome = self._apply({"n": ["https://www.ncua.gov", "https://www.ncua.gov/about"]})
        self.assertEqual(sites["n"], ["https://www.ncua.gov"])
        self.assertEqual(outcome["skipped"][SKIP_ONE_PER_NODE], [("n", "https://www.ncua.gov/about")])
        self.assertEqual(provenance["n"]["url"], "https://www.ncua.gov")

    def test_the_note_sentence_is_appended_once(self) -> None:
        once = note_with_provenance_sentence(SITES["_note"])
        self.assertTrue(once.startswith(SITES["_note"]))
        self.assertIn(PROVENANCE_NOTE_SENTENCE, once)
        self.assertEqual(note_with_provenance_sentence(once), once)


def load_official_sites_from(sites: dict) -> dict[str, list[str]]:
    """Round the in-memory file through the verifier's own loader."""
    tmp = TEST_TMP_ROOT / f"seed-load-{uuid.uuid4().hex}.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(json.dumps(sites), encoding="utf-8")
        return load_official_sites(tmp)
    finally:
        tmp.unlink(missing_ok=True)


class SeedScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"seed-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.sites = self.tmp / "official_sites.json"
        self.sites.write_text(json.dumps(SITES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.evidence = self.tmp / "directory_evidence.json"
        self.evidence.write_text(json.dumps(EVIDENCE), encoding="utf-8")
        self.provenance = self.tmp / "official_sites_provenance.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = seed_official_sites.main(["seed", "--sites", str(self.sites), "--provenance", str(self.provenance),
                                             "--directory-evidence", str(self.evidence), "--source", "federal-register", *extra])
        return code, out.getvalue()

    def test_dry_run_reports_and_writes_nothing(self) -> None:
        before = self.sites.read_bytes()
        code, text = self._run("--dry-run")
        self.assertEqual(code, 0, text)
        self.assertIn("added 3", text)
        self.assertIn("+ exec-dept-usda-fs  https://www.fs.usda.gov  (Forest Service)", text)
        self.assertIn("host_not_gov_or_mil (1)", text)
        self.assertIn("exec-ind-misc-cpb  https://www.cpb.org/", text)
        self.assertNotIn("not_https (", text, "an http .gov listing is upgraded, not skipped")
        self.assertIn("dry run: nothing written", text)
        self.assertEqual(self.sites.read_bytes(), before)
        self.assertFalse(self.provenance.exists())

    def test_a_real_run_adds_the_admissible_candidates_and_marks_them(self) -> None:
        code, text = self._run()
        self.assertEqual(code, 0, text)
        sites = json.loads(self.sites.read_text(encoding="utf-8"))
        self.assertEqual(list(sites)[0], "_note")
        self.assertIn(PROVENANCE_NOTE_SENTENCE, sites["_note"])
        self.assertTrue(sites["_note"].startswith(SITES["_note"]))
        self.assertEqual(sites["exec-dept-usda-fs"], ["https://www.fs.usda.gov"])
        self.assertEqual(sites["exec-dept-defense-agency-nga"], ["https://www.nga.mil/"])
        self.assertEqual(sites["exec-dept-doe"], SITES["exec-dept-doe"])          # untouched
        self.assertEqual(sites["exec-eop-ondcp"], SITES["exec-eop-ondcp"])        # untouched
        for absent in ("exec-ind-misc-cpb", "exec-eop-ondcp-twin", "exec-eop-onadm", "leg-senate-committee-x"):
            self.assertNotIn(absent, sites)
        # Listed as http by the directory; used as https, with the listing kept beside it.
        self.assertEqual(sites["exec-dept-doc"], ["https://www.commerce.gov/"])
        provenance = json.loads(self.provenance.read_text(encoding="utf-8"))
        self.assertEqual(provenance, {
            "exec-dept-defense-agency-nga": {"url": "https://www.nga.mil/", "source": FR,
                                             "listedName": "National Geospatial-Intelligence Agency", "directoryFetchedAt": FETCHED},
            "exec-dept-doc": {"url": "https://www.commerce.gov/", "source": FR, "listedName": "Commerce Department", "directoryFetchedAt": FETCHED,
                              "listedUrl": "http://www.commerce.gov/", "schemeUpgraded": True},
            "exec-dept-usda-fs": {"url": "https://www.fs.usda.gov", "source": FR, "listedName": "Forest Service", "directoryFetchedAt": FETCHED},
        })
        # The evidence file is read, never written.
        self.assertEqual(json.loads(self.evidence.read_text(encoding="utf-8")), EVIDENCE)

    def test_a_second_run_changes_nothing(self) -> None:
        self._run()
        sites_after_first = self.sites.read_bytes()
        provenance_after_first = self.provenance.read_bytes()
        code, text = self._run()
        self.assertEqual(code, 0)
        self.assertIn("added 0", text)
        self.assertIn("nothing to add; files unchanged", text)
        self.assertEqual(self.sites.read_bytes(), sites_after_first)
        self.assertEqual(self.provenance.read_bytes(), provenance_after_first)
        self.assertEqual(json.loads(self.sites.read_text(encoding="utf-8"))["_note"].count(PROVENANCE_NOTE_SENTENCE), 1)

    def test_a_missing_sites_file_is_an_error_not_a_new_file(self) -> None:
        self.sites.unlink()
        code, _ = self._run()
        self.assertEqual(code, 1)
        self.assertFalse(self.sites.exists())
        self.assertFalse(self.provenance.exists())


class CommittedFilesTests(unittest.TestCase):
    """The committed provenance file agrees with the committed sites file:
    every seeded URL is the candidate the sites file carries for that node,
    and every one passes the rules the seeder applies."""

    def test_every_provenance_record_matches_the_sites_file_and_the_rules(self) -> None:
        sites_path = PROJECT_ROOT / "data" / "verification" / "official_sites.json"
        provenance_path = PROJECT_ROOT / "data" / "verification" / "official_sites_provenance.json"
        if not provenance_path.exists():
            self.skipTest("no seeded candidates committed")
        sites = json.loads(sites_path.read_text(encoding="utf-8"))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        self.assertTrue(provenance)
        self.assertIn(PROVENANCE_NOTE_SENTENCE, sites["_note"])
        for node_id, record in provenance.items():
            self.assertIn(node_id, sites, node_id)
            self.assertIn(record["url"], sites[node_id], node_id)
            self.assertIsNone(seed_official_sites.refusal(record["url"]), record["url"])
            self.assertEqual(urlparse(record["url"]).scheme, "https")
            self.assertIn(record["source"], (FR, "congress_committee_pages", "agent_nomination"), node_id)
            if record.get("schemeUpgraded"):
                # The directory's own listing is kept beside the URL used, and differs only in scheme.
                self.assertEqual(record["listedUrl"], "http://" + record["url"][len("https://"):], node_id)
            if record["source"] == "agent_nomination":
                # A page `nominate.py promote` queued. It is a different kind of
                # candidate from a directory listing and carries a different
                # provenance: no directory named this unit, so what must be
                # recorded instead is who proposed it, when, on what basis, and
                # how sure they were — plus, in the record itself, that none of
                # that is evidence. The verifier decides by reading the page.
                self.assertTrue(record["basis"], node_id)
                self.assertIn(record["confidence"], ("speculative", "likely", "certain"), node_id)
                self.assertTrue(record["nominatedAt"], node_id)
                self.assertTrue(record["run"], node_id)
                self.assertIn("Not evidence", record["note"], node_id)
                self.assertNotIn("listedName", record, node_id)
            else:
                self.assertTrue(record["directoryFetchedAt"], node_id)
                self.assertTrue(record["listedName"], node_id)
        # No seeded URL duplicates a curated one.
        seeded = {r["url"].rstrip("/") for r in provenance.values()}
        curated = [u.rstrip("/") for k, v in sites.items() if k != "_note" and k not in provenance for u in v]
        self.assertEqual(seeded & set(curated), set())


if __name__ == "__main__":
    unittest.main()


class CongressSourceTests(unittest.TestCase):
    """The chambers' own committee pages as a second source: the House prints
    https links, the Senate http; both seed, the Senate's with the listing
    kept beside the upgraded URL."""

    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"seed-congress-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.sites = self.tmp / "sites.json"
        self.sites.write_text(json.dumps({"_note": "test", "leg-senate-cmte-judiciary": ["https://www.judiciary.senate.gov/about"]}), encoding="utf-8")
        self.provenance = self.tmp / "provenance.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_real_committee_pages_seed_both_chambers(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = seed_official_sites.main(["seed", "--source", "congress", "--sites", str(self.sites), "--provenance", str(self.provenance)])
        self.assertEqual(code, 0, out.getvalue())
        sites = json.loads(self.sites.read_text(encoding="utf-8"))
        provenance = json.loads(self.provenance.read_text(encoding="utf-8"))
        self.assertEqual(sites["leg-house-cmte-judiciary"], ["https://judiciary.house.gov/"])
        self.assertEqual(sites["leg-senate-cmte-agriculture-nutrition-and-forestry"], ["https://www.agriculture.senate.gov/"])
        self.assertEqual(provenance["leg-senate-cmte-agriculture-nutrition-and-forestry"]["listedUrl"], "http://www.agriculture.senate.gov/")
        self.assertIs(provenance["leg-senate-cmte-agriculture-nutrition-and-forestry"]["schemeUpgraded"], True)
        self.assertEqual(provenance["leg-house-cmte-judiciary"]["source"], "congress_committee_pages")
        self.assertNotIn("schemeUpgraded", provenance["leg-house-cmte-judiciary"])
        self.assertEqual(sites["leg-senate-cmte-judiciary"], ["https://www.judiciary.senate.gov/about"], "an existing entry is never replaced")
        added = sum(1 for k in sites if k.startswith("leg-"))
        self.assertGreaterEqual(added, 37, "18 House sites, 20 Senate sites less the one that already had an entry")
        self.assertTrue(all(json.loads(json.dumps(u)).startswith("https://") and (".house.gov" in u or ".senate.gov" in u or ".gov/" in u) for v in sites.values() if isinstance(v, list) for u in v))
