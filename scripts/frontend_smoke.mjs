#!/usr/bin/env node
/**
 * Boot the explorer in headless Chromium and assert the honesty-bearing text.
 *
 * The frontend has no other tests. This one serves the repository root over
 * HTTP (rewriting the unpkg Three.js import to a local copy so it runs without
 * the network), loads index.html, and checks what a visitor is told: the
 * published-node count excludes the review queue, hidden candidates are not
 * searchable, hiding "unverified" nodes does not blank the curated graph, a
 * curated node without a source reads "NO SOURCE RECORDED" over an Estimate
 * badge, and a node the Monthly Treasury Statement names reads Measured over
 * the statement it came from. Both are asserted: a badge that cannot tell the
 * two apart is the failure this guards against.
 *
 * Not part of the pytest suite: it needs Node, `playwright-core` (with a
 * Chromium it can launch) and a local `three` package.
 *
 * Install the Three.js version js/graph.js imports, not the latest: the page
 * pins one and the vendored copy has to match it.
 *
 *   npm install --no-save playwright-core three@0.160.1
 *   node scripts/frontend_smoke.mjs [--chromium /path/to/chrome] [--port 8123]
 *
 * Exit code 0 when every assertion holds, 1 otherwise; the findings are
 * printed as JSON.
 */

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const PORT = Number(arg("--port", "8123"));
const CHROMIUM = arg("--chromium", process.env.CHROMIUM_PATH || undefined);
// Where to find playwright-core and three: the repo, the cwd, --modules, NODE_PATH.
const MODULE_PATHS = [
  ROOT,
  process.cwd(),
  ...(arg("--modules", "") ? [path.resolve(arg("--modules", ""))] : []),
  ...(process.env.NODE_PATH || "").split(path.delimiter).filter(Boolean).map((dir) => path.resolve(dir, "..")),
];

const resolveModule = (name) => require.resolve(name, { paths: MODULE_PATHS });
// three's package "exports" forbids deep requires, so find the file on disk.
const threeBuild = MODULE_PATHS.map((dir) => path.join(dir, "node_modules", "three", "build")).find((dir) => fs.existsSync(path.join(dir, "three.module.js")));
let chromium;
try {
  if (!threeBuild) throw new Error("three not found");
  ({ chromium } = require(resolveModule("playwright-core")));
} catch (error) {
  console.error("Install the two dependencies locally first: npm install --no-save playwright-core three@0.160.1");
  console.error(`(or point --modules at a directory containing node_modules; looked in ${MODULE_PATHS.join(", ")})`);
  process.exit(2);
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css" };
const server = http.createServer((req, res) => {
  let pathname = decodeURIComponent(new URL(req.url, "http://x").pathname);
  // The whole build directory is served, not just three.module.js: since
  // r163 that file is a shim that imports ./three.core.js beside it, so
  // serving one file alone leaves the page waiting on a 404 for ever.
  if (pathname.startsWith("/vendor/")) {
    const vendored = path.join(threeBuild, path.basename(pathname));
    if (!fs.existsSync(vendored)) {
      res.writeHead(404);
      return res.end("not found");
    }
    res.writeHead(200, { "content-type": "text/javascript" });
    return fs.createReadStream(vendored).pipe(res);
  }
  if (pathname === "/") pathname = "/index.html";
  const file = path.join(ROOT, pathname);
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404);
    return res.end("not found");
  }
  const ext = path.extname(file);
  if (ext === ".js") {
    const source = fs.readFileSync(file, "utf8").replace(/https:\/\/unpkg\.com\/three@[0-9.]+\/build\/three\.module\.js/g, "/vendor/three.module.js");
    res.writeHead(200, { "content-type": "text/javascript" });
    return res.end(source);
  }
  res.writeHead(200, { "content-type": MIME[ext] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});

await new Promise((resolve) => server.listen(PORT, "127.0.0.1", resolve));
const failures = [];
const check = (name, ok, detail) => {
  if (!ok) failures.push(`${name}: ${detail}`);
};
try {
  const browser = await chromium.launch({
    executablePath: CHROMIUM,
    headless: true,
    args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => window.__bureaucracy_ui_loaded__ && (() => { const el = document.getElementById("loading"); return !el || getComputedStyle(el).opacity === "0"; })(),
    null,
    { timeout: 90000 },
  );
  await page.waitForTimeout(1500);
  const text = async (selector) => (await page.locator(selector).first().innerText()).trim();

  // The served graph, read once and early: several checks below have to pick
  // their example FROM THE DATA rather than naming a node. Every hardcoded
  // example here has eventually become the thing it was chosen for not being
  // — "Senate Leadership" was the unsourced node until the 2026-09-18
  // verification pass gave it a source, and the check then failed on
  // progress.
  const graphJson = JSON.parse(fs.readFileSync(path.join(ROOT, "output", "graph.json"), "utf8"));
  const allNodes = [];
  const walkGraph = (node) => {
    allNodes.push(node);
    for (const child of node.children || []) walkGraph(child);
  };
  walkGraph(graphJson);

  // "How to read this" — the first-visit explainer. A fresh browser context
  // has an empty localStorage, so this is exactly the state a first-time
  // visitor arrives in, and it must be on screen before anything else is
  // touched. Its numbers are checked against the served graph further down;
  // here it is only asserted to exist, to say the four things the site would
  // otherwise leave to be inferred, and to close when dismissed — a modal
  // that cannot be dismissed would lock the page for every new visitor.
  const guideOpenFirstVisit = await page.locator("#reading-guide.open").count();
  check("the reading guide greets a first-time visitor", guideOpenFirstVisit === 1, `${guideOpenFirstVisit} open`);
  const guideText = await text("#reading-guide-card");
  check("the guide says why most nodes show no figure", /Monthly Treasury Statement/.test(guideText), guideText.slice(0, 200));
  check("the guide says the estimates are withheld", /stay\s+hidden until you ask for them/.test(guideText), guideText.slice(0, 400));
  check("the guide says the withheld box reveals nothing for the rest", /have no figure at all and never will/.test(guideText), guideText.slice(0, 600));
  check("the guide says a post gets no share of outlays", /no position is given a share/.test(guideText), guideText.slice(0, 600));
  check("the guide says most entries carry no source", /entries carry a link to a source/.test(guideText.replace(/\s+/g, " ")), guideText.slice(0, 900));
  check("the guide says why a post carries no source", /declining to claim what it cannot show/.test(guideText.replace(/\s+/g, " ")), guideText.slice(0, 1200));
  check("the guide says how many organisation pages went unread", /have a page queued that could not be read/.test(guideText.replace(/\s+/g, " ")), guideText.slice(0, 1400));
  await page.locator("#btn-reading-guide-close").click();
  await page.waitForTimeout(200);
  check("the reading guide closes when dismissed", (await page.locator("#reading-guide.open").count()) === 0, "still open after dismissal");

  // The WebGL universe remains the main simulation. The evidence-first
  // directory is explicitly available from the persistent view switcher.
  check("the 3D universe is the default view", await page.locator("body.atlas-mode").count() === 0, "directory unexpectedly opened");
  await page.locator('.view-switch[data-view="atlas"]').click();
  await page.waitForTimeout(100);
  check("the directory opens from the view switcher", await page.locator("body.atlas-mode").count() === 1, "directory did not open");
  check("the directory limits itself to six generations", await page.locator('[data-atlas-depth="6"].active').count() === 1, "depth six is not active");
  const coverageText = await text("#atlas-coverage");
  check("the directory exposes evidence coverage", /verified records/.test(coverageText) && /reported financial figures/.test(coverageText), coverageText);
  check("the first organizational generation is rendered", await page.locator("#atlas-columns .atlas-generation").count() >= 1, "no generation column");
  await page.fill("#atlas-search", "Bureau of Prisons");
  await page.waitForTimeout(250);
  check("directory search finds a published entity", await page.locator("#atlas-search-results .atlas-result").count() >= 1, "no directory result");
  await page.fill("#atlas-search", "");

  await page.locator('.view-switch[data-view="universe"]').click();
  await page.waitForTimeout(100);
  check("the 3D universe remains available", await page.locator("body.atlas-mode").count() === 0, "universe did not open");

  const statsTotal = await text("#stats-total");
  check("published count excludes the review queue", /published nodes · [\d,]+ unreviewed candidates|total nodes/.test(statsTotal), statsTotal);
  check("published count is the tree, not tree plus queue", !/9,0\d\d/.test(statsTotal), statsTotal);

  await page.fill("#search-input", "ministry");
  await page.waitForTimeout(500);
  check("hidden candidates are not searchable", (await page.locator("#search-results .sr-item").count()) === 0, "candidate rows shown with the toggle off");
  await page.fill("#search-input", "");

  const toggles = page.locator("#verification-toggles input");
  await toggles.nth(0).uncheck();
  await page.waitForTimeout(1200);
  const counterHidden = await text("#node-counter");
  check("hiding unverified nodes keeps the curated graph", !/^0 \//.test(counterHidden), counterHidden);
  await toggles.nth(0).check();

  // A node with no source of its own. The Senate used to serve here, but the
  // Treasury statement names it, so it is measured now; the unsourced state
  // has to be read off a node that really lacks one or the check passes on
  // nothing. Both states are asserted below, which is the point: the badge
  // must distinguish them.
  // Estimates are withheld by default now, so any assertion about how an
  // estimate reads has to opt in first and opt back out after. The helper is
  // defined once, here, because the first such assertion is only a few lines
  // below.
  const setEstimatesShown = (shown) =>
    page.evaluate((want) => {
      const label = [...document.querySelectorAll("#verification-toggles label")]
        .find((l) => /Also show estimated shares/i.test(l.textContent || ""));
      if (!label) return false;
      const box = label.querySelector("input");
      if (box.checked !== want) box.click();
      return true;
    }, shown);

  // A node that genuinely has no source, chosen from the served graph rather
  // than named: 4,800-odd nodes qualify, and which ones do changes on every
  // verification pass. It also has to be findable by search, so the name must
  // be unique, and it must carry no measured cost (that block reads
  // differently).
  const nameCount = new Map();
  for (const n of allNodes) nameCount.set(n.name, (nameCount.get(n.name) || 0) + 1);
  // It must also be an ORGANISATION carrying an apportioned share: the
  // checks immediately below read the estimate block and its period line,
  // and a post shows "this is a post, not a unit of government" instead.
  // The first data-driven pick found a post and failed on exactly that.
  const unsourced = allNodes.find((n) =>
    nameCount.get(n.name) === 1
    && !(n.sourceUrls || []).length
    && !n.lastVerified
    && !n.synthetic
    && String(n.name || "").length > 8
    && !/position/i.test(String(n.type || ""))
    && String(n.cost_status || "") === "allocated");
  check("the graph still carries a node with no source at all", Boolean(unsourced), "none");
  await page.fill("#search-input", (unsourced ? unsourced.name : "Senate Leadership").slice(0, 30));
  await page.waitForTimeout(600);
  const rowLabel = await text("#search-results .sr-item .sr-type");
  check("search rows use the never-checked badge", /NO SOURCE RECORDED/.test(rowLabel), rowLabel);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const withheld = await text("#info-stats");
  check("an estimate is withheld until asked for", /no cost known/i.test(withheld), withheld.slice(0, 300));
  await setEstimatesShown(true);
  const info = await text("#info-stats");
  check("estimate is labelled", /ESTIMATE/.test(info), info);
  check("period line is printed", /through|As of/.test(info), info);
  check("an apportioned share is not called measured", !/MEASURED/.test(info), info);
  await setEstimatesShown(false);
  const panel = await text("#info-panel");
  check("curated node reads no source recorded", /NO SOURCE RECORDED/.test(panel), panel.slice(0, 200));

  // The other direction: a node the Monthly Treasury Statement names carries
  // a measured cost and says where it came from. If this ever reads ESTIMATE
  // the Treasury lines have stopped reaching the graph.
  await page.fill("#search-input", "Bureau of Prisons");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const measured = await text("#info-stats");
  check("a Treasury line is labelled measured", /MEASURED/.test(measured), measured);
  check("a measured cost is not also called an estimate", !/ESTIMATE/.test(measured), measured);
  check("the measured cost names its statement", /Monthly Treasury Statement/.test(measured), measured);
  const measuredPanel = await text("#info-panel");
  check("a measured node does not read no source recorded", !/NO SOURCE RECORDED/.test(measuredPanel), measuredPanel.slice(0, 200));
  // The figures are read off the served graph, not hard-coded: the day the
  // cap was removed, a fixed "Department of Energy reads capped" assertion
  // would have failed for the right reason and taught nothing.
  const byId = (id) => allNodes.find((n) => n.id === id);
  const openByName = async (name) => {
    await page.fill("#search-input", name);
    await page.waitForTimeout(500);
    // The result whose name IS the name, not one that contains it: searching
    // "Subcommittee on Defense" also lists "Chair, Subcommittee on Defense",
    // and a substring match opened the position instead of the committee.
    const exact = page.locator("#search-results .sr-item").filter({
      has: page.locator(".sr-name", { hasText: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`) }),
    });
    if (await exact.count()) {
      await exact.first().click();
    } else {
      await page.locator("#search-results .sr-item", { hasText: name }).first().click();
    }
    await page.waitForTimeout(2000);
  };
  const exactDollars = (amount) => `${amount < 0 ? "-" : ""}$${Math.round(Math.abs(amount)).toLocaleString("en-US")}`;

  // A measured department publishes the Treasury's own net figure, exact.
  const energy = byId("exec-dept-doe");
  check("the Department of Energy carries a Treasury line", Boolean(energy && energy.cost_status === "official"), JSON.stringify(energy && energy.cost_status));
  if (energy && energy.cost_status === "official") {
    await openByName(energy.name);
    const measuredDept = await text("#info-stats");
    check("a measured department reads MEASURED", /\bMEASURED\b/.test(measuredDept), measuredDept);
    check("a measured department shows the Treasury's exact figure", measuredDept.includes(exactDollars(energy.resolved_total_amount)), measuredDept);
    check("a measured department is not called capped or an estimate", !/CAPPED|\bESTIMATE\b/.test(measuredDept), measuredDept);
    const cappedPanel = await text("#info-panel");
    check(
      "an existence-verified node says which page named it",
      /official page names it|official page lists it/i.test(cappedPanel),
      cappedPanel.slice(0, 300),
    );
    const cabinetPlacement = await text("#verification-placement");
    check(
      "a unit under a curated grouping says its placement could not be checked",
      /Placement: could not be checked — its parent is a curated grouping with no official page of its own/.test(cabinetPlacement),
      cabinetPlacement,
    );
  }
  // If anything is still capped, its panel must say so; nothing is today.
  const cappedNode = allNodes.find((n) => n.cost_status === "scaled_official");
  if (cappedNode) {
    await openByName(cappedNode.name);
    const capped = await text("#info-stats");
    check("a capped Treasury line says it is capped", /TREASURY LINE CAPPED/.test(capped), capped);
    check("a capped node names the figure the Treasury reported", /Treasury reported \$/.test(capped), capped);
  }

  // A negative Treasury line is published as the statement prints it, with
  // the sign leading and the reason stated — never rounded up to zero.
  const negativeLine = allNodes.find((n) => n.cost_status === "official" && !n.synthetic && n.resolved_total_amount < 0 && n.id === "exec-dept-treasury-mint") || allNodes.find((n) => n.cost_status === "official" && !n.synthetic && n.resolved_total_amount < 0);
  check("a negative measured line exists in the graph", Boolean(negativeLine), "none");
  if (negativeLine) {
    await openByName(negativeLine.name);
    const negative = await text("#info-stats");
    check("a negative line shows its sign and exact figure", negative.includes(exactDollars(negativeLine.resolved_total_amount)), negative);
    check("a negative line reads MEASURED", /\bMEASURED\b/.test(negative), negative);
    check("a negative line says receipts exceeded spending", /Net outlays below zero/.test(negative), negative);
  }

  // The receipts the Treasury nets inside a section are an explicit line,
  // labelled as an accounting line and never as an organisation.
  const receiptsLine = allNodes.find((n) => n.synthetic === "treasury_receipts" && n.parentId === "exec-dept-hhs") || allNodes.find((n) => n.synthetic === "treasury_receipts" && n.id !== "treasury-undistributed-offsetting-receipts");
  check("a receipts line exists beneath a netted department", Boolean(receiptsLine), "none");
  if (receiptsLine) {
    await openByName(receiptsLine.name);
    const receipts = await text("#info-stats");
    check("a receipts line is labelled a Treasury accounting line", /Treasury accounting line/i.test(receipts), receipts);
    check("a receipts line says it is not an organisation", /Not an organisation/.test(receipts), receipts);
    const receiptsDesc = await text("#info-desc-provenance");
    check("a receipts line's description says it was generated from the statement", /generated from the Monthly Treasury Statement/.test(receiptsDesc), receiptsDesc);
    const receiptsPlacement = await text("#verification-placement");
    check("a receipts line's placement says it reconciles a total, not an org chart", /reconciles/.test(receiptsPlacement), receiptsPlacement);
  }
  const governmentWide = byId("treasury-undistributed-offsetting-receipts");
  check("the government-wide receipts sit beside the three branches", Boolean(governmentWide) && graphJson.children.length === 4, JSON.stringify(graphJson.children.map((c) => c.id)));
  if (governmentWide) {
    await openByName(governmentWide.name);
    const gov = await text("#info-stats");
    check("the government-wide line shows its exact negative figure", gov.includes(exactDollars(governmentWide.resolved_total_amount)), gov);
  }

  // The government's own lists, said as themselves: a directory listing is a
  // weaker claim than a page and is worded as one; a complete list's
  // absence is a checked negative naming the list.
  const directoryPlaced = allNodes.find((n) => n.placementMethod === "listed_under_parent_in_federal_register_agency_directory");
  check("some placement comes from the Federal Register's directory", Boolean(directoryPlaced), "none");
  if (directoryPlaced) {
    await openByName(directoryPlaced.name);
    const line = await text("#verification-placement");
    check("a directory placement names the directory, not a page", /Federal Register's agency directory files it under its parent here/.test(line), line);
    check("a directory placement never claims a page lists it", !/official page lists it/.test(line), line);
  }
  const senateListed = allNodes.find((n) => n.placementMethod === "listed_under_committee_in_senate_committee_list");
  check("some subcommittee is placed by the Senate's list", Boolean(senateListed), "none");
  if (senateListed) {
    await openByName(senateListed.name);
    const line = await text("#verification-placement");
    check("a Senate-list placement names the list", /Senate's official committee list carries it under its committee here/.test(line), line);
    const existence = await text("#info-panel");
    check("a Senate-list existence line names the list", /Senate's official committee list carries it/.test(existence), existence);
  }
  // A committee confirmed with the graph's type words set aside quotes the
  // page's own label and says the prefix was set aside — never the plain claim.
  const folded = allNodes.find((n) => n.verificationMatchRule === "committee_scaffolding_folded");
  check("some committee is confirmed with its type words set aside", Boolean(folded), "none");
  if (folded) {
    await openByName(folded.name);
    const existence = await text("#info-panel");
    check("a folded confirmation quotes the page's label", existence.includes(`as "${folded.verificationMatchedText}"`), existence);
    check("a folded confirmation says the prefix was set aside", /prefix set aside/.test(existence), existence);
  }
  const staleName = allNodes.find((n) => n.verificationFailure === "not_in_official_list" && n.verificationFailureSource?.source === "senate_committee_list");
  check("some curated name is checked against the Senate's list and absent", Boolean(staleName), "none");
  if (staleName) {
    await openByName(staleName.name);
    const existence = await text("#info-panel");
    check("an absence from a complete list says which list and which committee", /against the Senate's official committee list: it carries no unit of this name under "/.test(existence), existence);
  }
  // The House Clerk's list, the other chamber's complete list, said as itself.
  const houseListed = allNodes.find((n) => n.placementMethod === "listed_under_committee_in_house_clerk_committee_list");
  check("some subcommittee is placed by the House Clerk's list", Boolean(houseListed), "none");
  if (houseListed) {
    await openByName(houseListed.name);
    const line = await text("#verification-placement");
    check("a House-list placement names the Clerk's list", /House Clerk's official committee list carries it under its committee here/.test(line), line);
    const existence = await text("#info-panel");
    check("a House-list existence line names the Clerk's list", /House Clerk's official committee list carries it/.test(existence), existence);
  }
  const houseStale = allNodes.find((n) => n.verificationFailure === "not_in_official_list" && n.verificationFailureSource?.source === "house_clerk_committee_list");
  check("some curated name is checked against the House Clerk's list and absent", Boolean(houseStale), "none");
  if (houseStale) {
    await openByName(houseStale.name);
    const existence = await text("#info-panel");
    check("an absence from the Clerk's list says which list and which committee", /against the House Clerk's official committee list: it carries no unit of this name under "/.test(existence), existence);
  }

  // OPM's own numbers, each said as itself: a sourced headcount beside an
  // uncited one, and a position listing that is a record of a past period.
  const withOfficial = allNodes.find((n) => typeof n.employeesOfficial === "number" && n.employees)
    || allNodes.find((n) => typeof n.employeesOfficial === "number");
  check("some node carries an official headcount", Boolean(withOfficial), "none");
  if (withOfficial) {
    await openByName(withOfficial.name);
    const stats = await text("#info-stats");
    check("the official headcount is shown and named as OPM's", /EMPLOYEES — OPM FedScope/.test(stats), stats.slice(0, 400));
    const note = await text("#info-headcount-provenance");
    check("the headcount names the file and its coverage", /OPM's FedScope employment file lists .* Coverage: /.test(note), note);
    if (withOfficial.employees) {
      check("the curated figure is labelled uncited beside it", /EMPLOYEES \(uncited, from the base graph\)/.test(stats), stats.slice(0, 400));
      check("the panel says the two count different populations", /count different populations/.test(note), note);
    }
  }
  // USAspending File A, under its own heading and never as the cost: the
  // row names the system and the period and says in the heading itself that
  // it is not the cost; the sentence beneath says which system it came from.
  const withFileA = allNodes.find((n) => n.usaspendingOutlays && typeof n.usaspendingOutlays.amount === "number");
  check("some node carries a File A gross outlay", Boolean(withFileA), "none");
  if (withFileA) {
    await openByName(withFileA.name);
    const stats = await text("#info-stats");
    check("the File A figure is shown under its own heading, dated, and says it is not the cost",
      /GROSS OUTLAYS — USAspending File A \(FY\d{4} to \d{4}-\d{2}-\d{2}; not the cost\)/.test(stats), stats.slice(0, 500));
    const note = await text("#info-headcount-provenance");
    check("the File A sentence names the system, the API's own name for the unit, and says it is not the cost",
      /USAspending's File A reports gross outlays of \$[\d,]+ for ".+" \((toptier|bureau ".+" of toptier) \S+\) for FY\d{4} through \d{4}-\d{2}-\d{2}.* and is not the cost\./.test(note), note);
  }

  // A node with an OPM figure and nothing else must not be told it has no
  // source at all: the provenance block right below shows an opm.gov URL.
  const officialNoSources = allNodes.find(
    (n) => typeof n.employeesOfficial === "number" && !(n.sourceUrls || []).length && !n.lastVerified,
  );
  if (officialNoSources) {
    await openByName(officialNoSources.name);
    const panel = await text("#info-panel");
    check("a node with only an OPM figure is not told it has no source", !/No source URL has been attached to it yet/.test(panel), panel.slice(0, 600));
    check("the panel says which claim is the one missing", /No source has been attached for its existence/.test(panel), panel.slice(0, 600));
  }

  // The headcount an estimate was divided by, where OPM contradicts it.
  const disputed = allNodes.find((n) => n.cost_weight_dispute && typeof n.cost_weight_dispute === "object");
  check("some estimate was weighted by a headcount OPM contradicts", Boolean(disputed), "none");
  if (disputed) {
    await openByName(disputed.name);
    await setEstimatesShown(true);
    const stats = await text("#info-stats");
    check("the estimate names both headcounts", /The headcount used is the base graph's uncited .*OPM's employment file.*reports/s.test(stats), stats.slice(0, 900));
    check("the estimate says the share was not recomputed", /The share was not recomputed from OPM's number/.test(stats), stats.slice(0, 900));
    await setEstimatesShown(false);
  }

  const withListing = allNodes.find((n) => n.positionListing && typeof n.positionListing === "object");
  check("some position carries a PLUM archive listing", Boolean(withListing), "none");
  if (withListing) {
    await openByName(withListing.name);
    const listing = await text("#info-position-listing");
    check("the listing names the archive and its edition", /OPM's PLUM archive — /.test(listing), listing);
    check("the listing disclaims any current holder", /says nothing about who holds this post now/.test(listing), listing);
    check("the listing never names an incumbent", !/incumbent/i.test(listing), listing);
  }

  // Pay, as the archive states it: a rank is never printed as a rate, and a
  // rate is never presented as this unit's cost or as current.
  // Pick a uniquely named one: 80 nodes are called "Inspector General", and
  // opening by name would land on somebody else's.
  const nameCounts = new Map();
  for (const n of allNodes) nameCounts.set(n.name, (nameCounts.get(n.name) || 0) + 1);
  const unique = (n) => nameCounts.get(n.name) === 1;
  const withRate = allNodes.find((n) => n.positionListing && typeof n.positionListing.reportedPay === "number" && unique(n));
  check("some position carries the pay the archive reports", Boolean(withRate), "none");
  if (withRate) {
    await openByName(withRate.name);
    const listing = await text("#info-position-listing");
    check("the reported rate is shown as the archive prints it", /It reports basic pay of \$[\d,]+ for that period/.test(listing), listing);
    check("the rate is not presented as the unit's cost", /not this unit's cost/.test(listing), listing);
  }
  const withLevel = allNodes.find((n) => n.positionListing && n.positionListing.payLevel && unique(n));
  check("some position carries a level rather than a rate", Boolean(withLevel), "none");
  if (withLevel) {
    await openByName(withLevel.name);
    const listing = await text("#info-position-listing");
    // This used to assert !/level [^.]*\$/i — that no dollar figure appeared
    // anywhere near the word "level". That was the right invariant while the
    // archive was the only source: it had no rate for a level, so any dollar
    // figure beside one would have been invented. Since 2026-09-11 a second
    // document, OPM's salary table, does state a rate for a level, so the
    // blanket form now tests the wrong thing. The invariant that still holds
    // — and the one that matters — is that the ARCHIVE's level is never
    // presented as a rate, and that any rate shown is attributed to the table
    // it came from. Rewritten rather than deleted, deliberately.
    check("the panel says a level is not a rate", /gives the rank, not a rate of pay/.test(listing), listing);
    // Scoped to the archive's own clause. A first rewrite keyed on "level or
    // grade", which ui.js only emits when payPlan !== "EX" — so it could not
    // fire on any of the 29 Executive Schedule nodes, the exact ones a table
    // rate reaches. An assertion that cannot fail where it matters is worse
    // than none, because its name claims it did.
    const archiveClause = (listing.match(/Pay plan [\s\S]*?The archive gives the rank/) || [""])[0];
    check("the archive's own clause states a rank and never a rate",
      Boolean(archiveClause) && !archiveClause.includes("$"), archiveClause || listing);
  }

  // The salary table's rate, which is a join of two documents and has to read
  // as one: the level from the archive, the rate from the table, and neither
  // saying what the post pays now.
  const withTableRate = allNodes.find((n) => n.positionPayRate && typeof n.positionPayRate.amount === "number" && unique(n));
  check("some position is priced from the salary table", Boolean(withTableRate), "none");
  if (withTableRate) {
    await openByName(withTableRate.name);
    const listing = await text("#info-position-listing");
    check("the table rate names the table it came from", /Salary Table No\. \d{4}-EX/.test(listing), listing);
    check("the table rate names the level it prices", /pays \$[\d,]+ for Level [IVX]+/.test(listing), listing);
    check("the panel says it is two documents, not one", /two documents, not one/.test(listing), listing);
    check("the panel disclaims the current holder", /neither says what this post pays whoever holds it now/.test(listing), listing);
    check("the panel says a rate of pay is not the unit's cost", /not this unit's cost/.test(listing), listing);
    check("the pay-freeze note is carried through", /The table's own note: "/.test(listing), listing);
    check("the freeze note names what it covers", /freeze on the payable pay rates/.test(listing), listing);
    // The rate must never be dressed as a measured cost of the unit.
    const stats = await text("#info-stats");
    check("the table rate is not headed as a cost", !/\bCOST\b[^A-Z]*\$[\d,]+/.test(stats) || !/Salary Table/.test(stats), stats);
  }

  // A single-source statutory rate — judicial or congressional — a
  // different field from positionPayRate above, with its own rendering
  // and no PLUM archive beneath it.
  const withStatutoryPay = allNodes.find((n) => n.positionStatutoryPay && typeof n.positionStatutoryPay.amount === "number" && unique(n));
  check("some position is priced from a single primary statutory source", Boolean(withStatutoryPay), "none");
  if (withStatutoryPay) {
    await openByName(withStatutoryPay.name);
    const statutory = await text("#info-statutory-pay");
    check("the statutory rate names the amount it prices", new RegExp(withStatutoryPay.positionStatutoryPay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(statutory), statutory);
    check("the panel says it is one source's own account, not a second confirmation", /one source's own account/.test(statutory), statutory);
    check("the panel says a rate of pay is not the unit's cost", /not this unit's cost/.test(statutory), statutory);
    check("the source's own quoted words are shown", /The source's own words: "/.test(statutory), statutory);
    const statutoryStats = await text("#info-stats");
    check("the statutory rate is not headed as a cost", !/\bCOST\b[^A-Z]*\$[\d,]+/.test(statutoryStats), statutoryStats);
  }

  // A reported rate from the White House Office's statutory personnel report:
  // a third field again, and the one whose wording must not slip into saying
  // the post pays this, because the roster is person-level by statute.
  const withReportedPay = allNodes.find((n) => n.positionReportedPay && typeof n.positionReportedPay.amount === "number" && unique(n));
  check("some position is priced from the White House Office roster", Boolean(withReportedPay), "none");
  if (withReportedPay) {
    await openByName(withReportedPay.name);
    const reported = await text("#info-reported-pay");
    check("the reported rate names the amount it prices", new RegExp(withReportedPay.positionReportedPay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(reported), reported);
    check("the panel says it is the listed person's pay, not the post's", /not what the post pays whoever holds it/.test(reported), reported);
    check("the panel says two people can share a title at different salaries", /share a title at different salaries/.test(reported), reported);
    check("the panel says a reported rate is not the unit's cost", /not this unit's cost/.test(reported), reported);
    check("the panel says it is not evidence the post exists", /not evidence that this post exists/.test(reported), reported);
    check("the report's own quoted row is shown", /The report's own row: "/.test(reported), reported);
    check("no roster name is rendered", !/\b[A-Z][A-Z.'\-]{1,}, +[A-Z][A-Z.'\-]*\b/.test(reported.replace(withReportedPay.positionReportedPay.reportedTitle || "", "")), reported);
    const reportedStats = await text("#info-stats");
    check("the reported rate is not headed as a cost", !/\bCOST\b[^A-Z]*\$[\d,]+/.test(reportedStats), reportedStats);
  }

  // The exact-costs-only view: with it on, an apportioned share is not shown
  // as a figure at all, and the panel says why.
  const allocatedNode = allNodes.find((n) => n.cost_status === "allocated" && n.resolved_total_amount > 1e6
    && !n.positionListing && nameCounts.get(n.name) === 1);
  check("some node carries an apportioned share", Boolean(allocatedNode), "none");
  const clickEstimateToggle = () => setEstimatesShown(true);
  if (allocatedNode) {
    await openByName(allocatedNode.name);
    const before = await text("#info-stats");
    // The default is the honest view: an estimate is not the first thing shown.
    check("an estimate is withheld by default", /no cost known for this node/i.test(before), before.slice(0, 400));
    check("no dollar figure is shown by default", !/≈\s*\$/.test(before), before.slice(0, 400));
    check("the panel says what the withheld figure would have been", /share of an ancestor's measured total/.test(before), before.slice(0, 600));
    check("the panel names the opt-in rather than blaming a hidden setting", /Also show estimated shares/.test(before), before.slice(0, 600));
    const toggled = await clickEstimateToggle();
    check("the estimate opt-in exists", toggled, "no such toggle");
    if (toggled) {
      const after = await text("#info-stats");
      check("opting in shows the estimate, labelled", /≈\s*\$/.test(after), after.slice(0, 400));
      check("the estimate still reads as derived", /Not a measured budget/.test(after), after.slice(0, 500));
      await setEstimatesShown(false);
    }
  }

  // A measured cost is unaffected by the default: it is the node's own.
  const measuredNode = allNodes.find((n) => n.cost_status === "official" && nameCounts.get(n.name) === 1);
  check("some node carries a measured cost", Boolean(measuredNode), "none");
  if (measuredNode) {
    await openByName(measuredNode.name);
    const stats = await text("#info-stats");
    check("a measured cost is shown by default", /\$[\d,]+/.test(stats), stats.slice(0, 300));
    check("a measured cost is not withheld", !/no cost known/i.test(stats), stats.slice(0, 300));
  }

  // A position with a real reported rate of pay shows it in place of the
  // withheld estimate, under a heading that is not the word COST.
  const paid = allNodes.find((n) => n.positionListing && typeof n.positionListing.reportedPay === "number"
    && nameCounts.get(n.name) === 1);
  check("some position carries a reported rate of pay", Boolean(paid), "none");
  if (paid) {
    await openByName(paid.name);
    const stats = await text("#info-stats");
    check("the rate of pay is shown by default", /REPORTED RATE OF BASIC PAY/.test(stats), stats.slice(0, 400));
    check("the rate is not headed as a cost", !/^COST|ANNUAL COST/m.test(stats.split("REPORTED")[0]), stats.slice(0, 400));
    check("the panel says a salary is not the unit's cost", /compensation for one post, not what this unit costs/.test(stats), stats.slice(0, 700));
  }

  // A node whose name states a count says how many it actually carries.
  const short = allNodes.find((n) => n.childrenIncomplete);
  check("some grouping carries fewer than its name states", Boolean(short), "none");
  if (short) {
    await openByName(short.name);
    const stats = await text("#info-stats");
    const note = await text("#info-count-provenance");
    check("the sub-unit row names the stated count", /SUB-UNITS \(of the \d+ its name states\)/.test(stats), stats.slice(0, 400));
    check("the panel says the rest are absent from the graph", /are not in this graph at all/.test(note), note);
  }
  const several = allNodes.find((n) => n.representsPosts && n.representsPosts.kind === "exact" && nameCounts.get(n.name) === 1)
    || allNodes.find((n) => n.representsPosts && nameCounts.get(n.name) === 1);
  check("some position stands for several posts", Boolean(several), "none");
  if (several) {
    await openByName(several.name);
    const note = await text("#info-count-provenance");
    check("the panel says it stands for more than one post", /stands for/.test(note), note);
    check("the panel says the figure is for the group", /for the group, not for one holder/.test(note), note);
  }

  // A share nobody can estimate is published as unavailable, never as $0.00
  // — below a cent, or beneath a unit whose net outlays are negative.
  const belowPrecision = allNodes.find((n) => n.cost_validation === "allocation_below_precision" && !/position/i.test(n.type || ""))
    || allNodes.find((n) => n.cost_validation === "allocation_below_precision");
  const poolNegative = allNodes.find((n) => n.cost_validation === "treasury_pool_negative");
  const unavailableNode = belowPrecision || poolNegative;
  check("some node is published unavailable for a stated reason", Boolean(unavailableNode), "none");
  if (unavailableNode) {
    await openByName(unavailableNode.name);
    await setEstimatesShown(true);
    const unavailable = await text("#info-stats");
    check("an unapportionable share reads as unavailable", /Not available|NOT AVAILABLE/.test(unavailable), unavailable);
    // The COST VALUE must not be a zero. The explanation below it is allowed to
    // say the words "rather than $0" — that sentence is the honesty, not a bug.
    check(
      "an unapportionable share is never rendered as a zero cost",
      !/COST\s*[\n\r]*\s*[≈~]?\s*-?\$0(\.00)?\b/.test(unavailable),
      unavailable,
    );
    check(
      "an unapportionable share explains itself",
      unavailableNode === belowPrecision ? /less than one cent/i.test(unavailable) : /Nothing remains to apportion/i.test(unavailable),
      unavailable,
    );
    await setEstimatesShown(false);
  }

  // The first line a visitor reads. It was hardcoded and both halves went
  // stale — it called every cost an estimate after 55 became measured, and
  // called the hierarchy "hand-compiled" when nothing records its origin.
  const provenance = await text("#data-provenance");
  check("provenance line is computed, not the old hardcoded string", !/Structure hand-compiled/.test(provenance), provenance);
  check("provenance counts the measured costs", /\d+ costs measured from the Monthly Treasury Statement/.test(provenance), provenance);
  check("provenance counts evidenced placements", /\d+ of [\d,]+ organisation placements evidenced/.test(provenance), provenance);
  check("provenance says the descriptions are uncited", /descriptions carry no citation/.test(provenance), provenance);

  // Placement is a claim about the edge, separate from existence. The Science
  // Mission Directorate was confirmed on NASA's own About page, which is the
  // parent's page naming the child: evidenced. A unit nobody has checked
  // against its parent's page must say so, not stay silent.
  await page.fill("#search-input", "Science Mission Directorate");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const placed = await text("#verification-placement");
  // Either wording: a separate read of the parent's page, or the same read
  // that confirmed existence (one fetch must not present as two checks).
  // A listing from the site-wide navigation says so between the verb and the label.
  check("an evidenced placement says the parent's page lists it", /Placement: (its parent's official page|the same page read above) lists it( in its site-wide navigation)? as "/.test(placed), placed);
  check("an evidenced placement quotes the label and links the page", /lists it( in its site-wide navigation)? as "[^"]+" on [a-z0-9.-]+\.(gov|mil)/.test(placed), placed);
  check("an evidenced placement never says 'reports to'", !/reports to/i.test(placed), placed);
  // Likewise chosen from the data: a node whose placement is not evidenced.
  const unplacedNode = allNodes.find((n) =>
    nameCount.get(n.name) === 1 && n.placementVerified !== true
    && !n.synthetic && String(n.name || "").length > 8
    && !/position/i.test(String(n.type || "")));
  check("the graph still carries an organisation with no evidenced placement", Boolean(unplacedNode), "none");
  await page.fill("#search-input", (unplacedNode ? unplacedNode.name : "Senate Leadership").slice(0, 30));
  await page.waitForTimeout(600);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const unplaced = await text("#verification-placement");
  // Which of the three non-evidenced states this node is in depends on the
  // last live run (the Senate's page has been read and does not list this
  // grouping); what must hold is that the panel names one of them, and
  // never claims a listing.
  check(
    "a placement without evidence names its state — unchecked, unreachable, or read and not listed",
    /Placement: (no evidence recorded|its parent's official page was read .*does not list it as a heading or link — no claim either way|could not be checked)/.test(unplaced),
    unplaced,
  );
  check("a placement without evidence never claims the page lists it", !/lists it/.test(unplaced), unplaced);
  // The description label, asserted from the data rather than from whichever
  // node happened to be on screen. This check used to read the panel after an
  // unrelated selection and require the line to be EMPTY -- true only while
  // the LOD had folded that node into a cluster, which is not something a
  // test can rely on, and it broke the moment the selection above stopped
  // being hardcoded. What is actually being claimed is a pair:
  //   base-graph prose  -> "uncited prose ... not checked against any source"
  //   a sourced structure -> its own generated label, and never that one
  const generated = allNodes.find((n) => n.descriptionSource === "generated_from_whitehouse_staff_report"
    && nameCount.get(n.name) === 1 && n.desc);
  check("some node's description is sourced rather than curated", Boolean(generated), "none");
  if (generated) {
    await page.fill("#search-input", generated.name.slice(0, 30));
    await page.waitForTimeout(600);
    await page.locator("#search-results .sr-item").first().click();
    await page.waitForTimeout(800);
    const note = await text("#info-desc-provenance");
    check("a sourced description says which document it came from",
      /generated from the White House Office's own annual report/.test(note), note);
    check("a sourced description is never labelled uncited prose", !/uncited prose/.test(note), note);
  }
  const curated = allNodes.find((n) => !n.descriptionSource && n.desc && nameCount.get(n.name) === 1
    && !n.synthetic && String(n.name || "").length > 8);
  check("the graph still carries an uncited curated description", Boolean(curated), "none");
  if (curated) {
    await page.fill("#search-input", curated.name.slice(0, 30));
    await page.waitForTimeout(600);
    await page.locator("#search-results .sr-item").first().click();
    await page.waitForTimeout(800);
    const note = await text("#info-desc-provenance");
    check("curated prose says it was never checked against a source",
      /uncited prose from the base graph/.test(note), note);
  }
  await page.fill("#search-input", "President of the United States");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const descNote = await text("#info-desc-provenance");
  check("a description is labelled as uncited", /uncited prose/i.test(descNote), descNote);
  check("provenance does not call every cost an estimate", !/^costs are estimates/.test(provenance), provenance);

  // A post confirmed on its own organisation's page. The claim is narrower
  // than an organisation's and the panel has to say so: it names the page as
  // the organisation's, quotes the label found (84 nodes are called "General
  // Counsel", so the words are what tie the badge to this node), and never
  // publishes the same reading a second time as evidence for the edge.
  // Pick one confirmed on a SINGLE page. That is the case the confidence
  // arithmetic has to get right: 0.4 for having a source plus 0.3 for it
  // being official is 0.70, which is "partial". A post named on two official
  // pages reaches 0.80 and is "verified" — 4 of the 20 are, legitimately, so
  // asserting "a post is never verified" would be asserting something false.
  const confirmedPost = allNodes.find(
    (n) => n.verificationMethod === "name_labelled_on_its_organisations_official_page"
      && nameCounts.get(n.name) === 1 && (n.sourceUrls || []).length === 1,
  );
  check("some position is confirmed by its organisation's own page", Boolean(confirmedPost), "none");
  if (confirmedPost) {
    await openByName(confirmedPost.name);
    const posPanel = await text("#info-panel");
    check("a confirmed post says whose page named it", /Its organisation's own official page names it/.test(posPanel), posPanel.slice(0, 400));
    check("a confirmed post quotes the label the page carries",
      posPanel.includes(`as "${confirmedPost.verificationMatchedText}"`), posPanel.slice(0, 400));
    check("a post confirmed on one page reads partial, not verified", /PARTIAL/.test(posPanel) && !/\bVERIFIED\b/.test(posPanel), posPanel.slice(0, 300));
    check("a confirmed post no longer reads no source recorded", !/NO SOURCE RECORDED/.test(posPanel), posPanel.slice(0, 300));
    const posPlacement = await text("#verification-placement");
    check("a post's placement is not claimed as a second finding", /not claimed separately/.test(posPlacement), posPlacement);
    check("a post's placement never claims a page lists it", !/official page lists it/.test(posPlacement), posPlacement);
    // Confirmed from the page's body, never from its site-wide furniture.
    check("a post is never confirmed from the site-wide navigation", !/in the site-wide navigation/.test(posPlacement), posPlacement);
  }
  // The numerator and the denominator of the placement line must count the
  // same population: it says "organisation placements", and the 126 positions
  // the PLUM archive files under an organisation were being counted in it.
  const provenanceLine = await text("#data-provenance");
  const placementCounts = /([\d,]+) of ([\d,]+) organisation placements/.exec(provenanceLine);
  check("the provenance line reports organisation placements", Boolean(placementCounts), provenanceLine);
  if (placementCounts) {
    const isOrgEdge = (n) => n !== graphJson && !/position/i.test(String(n.type || ""));
    const expected = allNodes.filter((n) => isOrgEdge(n) && n.placementVerified === true).length;
    check(
      "the placement numerator counts organisations only, as its own label says",
      Number(placementCounts[1].replace(/,/g, "")) === expected,
      `${placementCounts[1]} shown, ${expected} organisation edges actually placed`,
    );
  }

  // The guide's counts come from the same tree walk as the provenance line,
  // and both must agree with the graph actually served. A card that said
  // "137 measured" over a graph carrying some other number would be the
  // hardcoded-provenance failure this project already made once.
  const guideMeasured = /([\d,]+) figures here were measured/.exec(guideText.replace(/\s+/g, " "));
  check("the guide states how many costs are measured", Boolean(guideMeasured), guideText.slice(0, 300));
  if (guideMeasured) {
    const expectedMeasured = allNodes.filter((n) => ["official", "root_total"].includes(String(n.cost_status || ""))).length;
    check(
      "the guide's measured count is the graph's own",
      Number(guideMeasured[1].replace(/,/g, "")) === expectedMeasured,
      `${guideMeasured[1]} shown, ${expectedMeasured} in the served graph`,
    );
  }
  const guidePosts = /of the ([\d,]+) posts show nothing under cost/.exec(guideText.replace(/\s+/g, " "));
  check("the guide states how many posts there are", Boolean(guidePosts), guideText.slice(0, 700));
  if (guidePosts) {
    const expectedPosts = allNodes.filter((n) => /position/i.test(String(n.type || ""))).length;
    check(
      "the guide's post count is the graph's own",
      Number(guidePosts[1].replace(/,/g, "")) === expectedPosts,
      `${guidePosts[1]} shown, ${expectedPosts} in the served graph`,
    );
  }

  // "Apportioned estimates, withheld unless asked for" once counted every
  // node that was not measured — 5,265 of them, where only 650 carry an
  // apportioned share at all. The other 4,615 have no figure in the data,
  // so ticking the estimates box reveals nothing for them. Both the line and
  // the card must count the nodes that actually hold a share.
  const estimateCounts = /([\d,]+) apportioned estimates/.exec(provenanceLine);
  check("the provenance line counts apportioned estimates", Boolean(estimateCounts), provenanceLine);
  if (estimateCounts) {
    const expectedAllocated = allNodes.filter((n) => String(n.cost_status || "") === "allocated").length;
    check(
      "the estimate count is the nodes that carry a share, not every unmeasured node",
      Number(estimateCounts[1].replace(/,/g, "")) === expectedAllocated,
      `${estimateCounts[1]} shown, ${expectedAllocated} allocated in the served graph`,
    );
    const guideAllocated = /([\d,]+) more could be shown as a share/.exec(guideText.replace(/\s+/g, " "));
    check("the guide counts the same apportioned estimates", Boolean(guideAllocated)
      && Number(guideAllocated[1].replace(/,/g, "")) === expectedAllocated,
      `${guideAllocated ? guideAllocated[1] : "absent"} in the card, ${expectedAllocated} allocated`);
  }

  // The key must name what it colours. A receipts line took the position grey
  // from the node defaults, so the swatch labelled "Position / Office" was
  // standing for 25 Treasury accounting lines as well as 4,589 posts.
  const legendSlate = await page.evaluate(() => {
    const row = [...document.querySelectorAll("#legend .leg-item")]
      .find((item) => /Treasury accounting line/.test(item.textContent || ""));
    const dot = row && row.querySelector(".leg-dot");
    return dot ? getComputedStyle(dot).backgroundColor : null;
  });
  check("the legend names the Treasury accounting lines", Boolean(legendSlate), "no such legend row");
  // Two kinds of node are Treasury accounting lines and both must carry the
  // colour: the receipts lines the exporter creates, marked `synthetic`, and a
  // line a curator added because the statement reports money under a heading
  // naming no organisation ("Interest on the Public Debt"). This check keyed on
  // `synthetic` alone until 2026-09-19 and failed on the second kind — the same
  // narrowness the exporter's own colour guard had.
  const isTreasuryLine = (n) => String(n.synthetic || "") === "treasury_receipts"
    || String(n.type || "") === "Treasury accounting line";
  const lineColours = [...new Set(allNodes.filter(isTreasuryLine).map((n) => n.color))];
  check("every Treasury accounting line carries one colour of its own", lineColours.length === 1 && lineColours[0] === "#8aa0b0", JSON.stringify(lineColours));
  check(
    "the legend swatch is the colour those lines actually carry",
    legendSlate === "rgb(138, 160, 176)",
    `${legendSlate} in the key, ${lineColours[0]} in the graph`,
  );
  const slateImposters = allNodes.filter((n) => n.color === "#8aa0b0" && !isTreasuryLine(n));
  check("nothing else is drawn in that colour", slateImposters.length === 0, slateImposters.slice(0, 3).map((n) => n.id).join(", "));

  // The Executive Schedule rate current law sets. The most recognisable posts
  // in the government carried no pay evidence at all before this: the panel
  // must print the statute's citation and its own title for the office, since
  // fifteen nodes share the identical Level I figure and the citation is the
  // only thing tying a figure to this post rather than another's.
  const withSchedulePay = allNodes.find((n) => n.positionSchedulePay && typeof n.positionSchedulePay.amount === "number");
  check("some position is priced at the level the U.S. Code sets", Boolean(withSchedulePay), "none");
  if (withSchedulePay) {
    await page.fill("#search-input", withSchedulePay.name.slice(0, 28));
    await page.waitForTimeout(600);
    await page.locator("#search-results .sr-item").first().click();
    await page.waitForTimeout(700);
    const sched = await text("#info-panel");
    check("the panel cites the section of the Code", /5 U\.S\.C\. §53\d\d/.test(sched), sched.slice(0, 400));
    check("the panel names the office as the Code names it", sched.includes(withSchedulePay.positionSchedulePay.statutoryTitle), sched.slice(0, 400));
    check("the panel says it is two documents", /statute sets the level and the table sets the rate/.test(sched), sched.slice(0, 600));
    check("a statutory rate is never called this unit's cost", /not a share of federal outlays/.test(sched), sched.slice(0, 900));
    // The 2026-09-11 failure, checked from the served graph rather than trusted.
    // The scoped half: a shared title ("General Counsel", 84 nodes) is only
    // identified by the body above it, and the panel must say so.
    const scopedAll = allNodes.filter((n) => n.positionSchedulePay && n.positionSchedulePay.scopedOrganisation);
    check("some position is priced as an office inside a named organisation", scopedAll.length > 0, "none");
    // Search finds a node by name, and the whole point of the scoped route is
    // that these names are NOT unique -- 84 nodes are called "General
    // Counsel". So the assertion is driven from one whose name happens to be
    // unique, which is the only way a search can land on a known node.
    const nameCounts = new Map();
    for (const n of allNodes) nameCounts.set(n.name, (nameCounts.get(n.name) || 0) + 1);
    const scopedNode = scopedAll.find((n) => nameCounts.get(n.name) === 1);
    check("at least one scoped position has a name a search can resolve", Boolean(scopedNode),
      `${scopedAll.length} scoped, none with a unique name`);
    if (scopedNode) {
      await page.fill("#search-input", scopedNode.name.slice(0, 30));
      await page.waitForTimeout(700);
      await page.locator("#search-results .sr-item").first().click();
      await page.waitForTimeout(800);
      const scopedPanel = await text("#info-panel");
      check("the panel names the organisation the title was scoped to",
        scopedPanel.includes(scopedNode.positionSchedulePay.scopedOrganisation), scopedPanel.slice(0, 500));
      check("the panel says the title alone did not identify it",
        /half of what identifies it/.test(scopedPanel), scopedPanel.slice(0, 700));
    }

    // Where the archive and the Code reach the same level, the panel must say
    // it is one level corroborated twice rather than print two silent
    // paragraphs a reader would take for two figures.
    const bothSources = allNodes.find((n) => n.positionSchedulePay && n.positionPayRate
      && n.positionSchedulePay.payLevel === n.positionPayRate.payLevel
      && nameCount.get(n.name) === 1);
    if (bothSources) {
      await page.fill("#search-input", bothSources.name.slice(0, 30));
      await page.waitForTimeout(600);
      await page.locator("#search-results .sr-item").first().click();
      await page.waitForTimeout(800);
      const bothPanel = await text("#info-panel");
      check("two records agreeing on a level are not printed as two figures",
        /one level corroborated by two records, not two separate figures/.test(bothPanel),
        bothPanel.slice(0, 500));
    }

    check("a statutory rate did not make the post verified",
      !(withSchedulePay.sourceUrls || []).some((u) => String(u).includes("uscode.house.gov")),
      JSON.stringify(withSchedulePay.sourceUrls || []));
  }

  // The depth buttons are a fixed HTML list (1..12) that does not know how
  // deep the loaded tree actually is (MAX_DEPTH=20 caps it further still).
  // A button past the real depth must be disabled and say why, not sit there
  // promising a jump the data cannot make.
  const computedMaxDepth = (() => {
    let max = 0;
    const walkDepth = (node, depth) => {
      max = Math.max(max, depth);
      for (const child of node.children || []) walkDepth(child, depth + 1);
    };
    walkDepth(graphJson, 0);
    return max;
  })();
  const depthButtonState = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll(".depth-btn[data-depth]")]
      .filter((b) => b.dataset.depth !== "all")
      .map((b) => ({ depth: Number(b.dataset.depth), disabled: b.disabled, title: b.title }));
    return buttons;
  });
  const overDepth = depthButtonState.find((b) => b.depth > computedMaxDepth);
  check("a depth button says its own list goes deeper than the graph does when true", computedMaxDepth < 12, `graph depth ${computedMaxDepth}, expected < 12 for this assertion to be meaningful`);
  if (overDepth) {
    check(`the depth ${overDepth.depth} button is disabled past the real data depth (${computedMaxDepth})`, overDepth.disabled === true, JSON.stringify(overDepth));
    check("the disabled depth button explains why in its title", new RegExp(`only ${computedMaxDepth} levels deep`).test(overDepth.title), overDepth.title);
  }
  const withinDepth = depthButtonState.find((b) => b.depth <= computedMaxDepth);
  if (withinDepth) {
    check(`the depth ${withinDepth.depth} button stays enabled within the real data depth`, withinDepth.disabled === false, JSON.stringify(withinDepth));
  }

  // Rows that were only click targets before now expose role=button,
  // tabindex and an aria-label, and respond to a keyboard Enter the same
  // way a click does — a screen-reader or keyboard-only visitor could not
  // reach a single node before this.
  await page.fill("#search-input", "Department of Energy");
  await page.waitForTimeout(500);
  const searchRow = page.locator("#search-results .sr-item").first();
  const searchRowAttrs = await searchRow.evaluate((el) => ({
    role: el.getAttribute("role"),
    tabindex: el.getAttribute("tabindex"),
    ariaLabel: el.getAttribute("aria-label"),
  }));
  check("a search result row is a focusable button for assistive tech", searchRowAttrs.role === "button" && searchRowAttrs.tabindex === "0", JSON.stringify(searchRowAttrs));
  check("a search result row has a real label, not just visual text", Boolean(searchRowAttrs.ariaLabel && searchRowAttrs.ariaLabel.length > 0), JSON.stringify(searchRowAttrs));
  await searchRow.focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1500);
  const openedByKeyboard = await text("#info-name");
  check("Enter on a focused search row opens it, same as a click", openedByKeyboard.length > 0, openedByKeyboard);
  await page.fill("#search-input", "");

  const breadcrumbRow = page.locator("#bc-items > *").first();
  if (await breadcrumbRow.count()) {
    const bcAttrs = await breadcrumbRow.evaluate((el) => ({ role: el.getAttribute("role"), tabindex: el.getAttribute("tabindex") }));
    check("a breadcrumb crumb is keyboard-focusable", bcAttrs.role === "button" && bcAttrs.tabindex === "0", JSON.stringify(bcAttrs));
  }
  const childRow = page.locator("#info-children-list > *").first();
  if (await childRow.count()) {
    const childAttrs = await childRow.evaluate((el) => ({ role: el.getAttribute("role"), tabindex: el.getAttribute("tabindex") }));
    check("a children-list row is keyboard-focusable", childAttrs.role === "button" && childAttrs.tabindex === "0", JSON.stringify(childAttrs));
  }

  // State a viewer sets is remembered across a reload: the depth filter, the
  // three toggles, and which node was open (via the URL hash, so it is also
  // a link worth sharing) — not just recalled silently, but recalled AND
  // reflected back into the visible controls and the open panel.
  await page.evaluate(() => {
    const box = document.querySelector("#verification-toggles input");
    if (box && box.checked) box.click();
  });
  await page.waitForTimeout(300);
  await openByName(energy && energy.cost_status === "official" ? energy.name : "Department of Energy");
  const hashBeforeReload = await page.evaluate(() => window.location.hash);
  check("selecting a node writes its id into the URL hash", /^#node=/.test(hashBeforeReload), hashBeforeReload);
  const storedPrefs = await page.evaluate(() => {
    try {
      return JSON.parse(window.localStorage.getItem("bureaucracy-view-prefs-v1") || "{}");
    } catch (e) {
      return null;
    }
  });
  check("a toggle change is persisted to localStorage", storedPrefs && typeof storedPrefs.showUnverified === "boolean", JSON.stringify(storedPrefs));

  await page.goto(`http://127.0.0.1:${PORT}/index.html${hashBeforeReload}`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => window.__bureaucracy_ui_loaded__ && (() => { const el = document.getElementById("loading"); return !el || getComputedStyle(el).opacity === "0"; })(),
    null,
    { timeout: 90000 },
  );
  await page.waitForTimeout(2000);
  const toggleAfterReload = await page.locator("#verification-toggles input").first().isChecked();
  check("the unverified-nodes toggle survives a reload", toggleAfterReload === false, String(toggleAfterReload));
  const nameAfterReload = await text("#info-name");
  check("the previously-selected node reopens from the URL hash on reload", nameAfterReload.length > 0 && nameAfterReload !== "—", nameAfterReload);
  await page.evaluate(() => {
    const box = document.querySelector("#verification-toggles input");
    if (box && !box.checked) box.click();
  });
  await page.waitForTimeout(300);

  // A candidate node — unreviewed, never placed by anything but a crawler's
  // own guess — must say that plainly rather than showing a blank
  // description or placement line, which used to read as "nothing is known"
  // instead of "nothing has been checked yet."
  const candidatesPath = path.join(ROOT, "output", "candidate_nodes.json");
  if (fs.existsSync(candidatesPath)) {
    const candidates = JSON.parse(fs.readFileSync(candidatesPath, "utf8"));
    const candidateList = Array.isArray(candidates) ? candidates : candidates.candidates || [];
    const candidateWithParent = candidateList.find((c) => c.possibleParentId || c.possibleParent);
    check("some candidate carries a possible-parent guess", Boolean(candidateWithParent), "none");
    await page.evaluate(() => {
      const label = [...document.querySelectorAll("#verification-toggles label")].find((l) => /candidate/i.test(l.textContent || ""));
      const box = label && label.querySelector("input");
      if (box && !box.checked) box.click();
    });
    await page.waitForTimeout(500);
    if (candidateWithParent) {
      await openByName(candidateWithParent.name);
      const candidatePlacement = await text("#verification-placement");
      check("a candidate's possible parent is shown, labelled as an unverified guess", /POSSIBLE PARENT \(unverified guess, not yet placed\)/.test(candidatePlacement), candidatePlacement);
      const candidateDesc = await text("#info-desc-provenance");
      check("a candidate's description says it comes from the discovery notice", /from the notice that surfaced this candidate/.test(candidateDesc), candidateDesc);
    }
    const candidateNoParent = candidateList.find((c) => !c.possibleParentId && !c.possibleParent);
    if (candidateNoParent) {
      await openByName(candidateNoParent.name);
      const noParentPlacement = await text("#verification-placement");
      check("a candidate with no parent guess says so", /No possible parent was identified/.test(noParentPlacement), noParentPlacement);
    }
  }

  await page.fill("#search-input", "");
  check("no page errors", pageErrors.length === 0, pageErrors.join(" | "));
  await browser.close();
} catch (error) {
  failures.push(`harness: ${error && error.stack ? error.stack : error}`);
} finally {
  server.close();
}
console.log(JSON.stringify({ ok: failures.length === 0, failures }, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
