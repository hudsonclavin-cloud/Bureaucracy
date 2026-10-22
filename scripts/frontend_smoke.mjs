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
// Figures worth printing whether or not their check passed: a count that
// sits near its bar is only legible as a number, and a passing run that
// printed nothing left the next investigator with "it passed" and no way to
// tell 235 from 151.
const measurements = {};
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
  // Each node is stamped with its depth (a harness-side field, never
  // published) so the deep-link checks below can say what they expect.
  const walkGraph = (node, depth = 0, branch = null) => {
    node.__depth = depth;
    // The root's own child above the node: the Whole sphere's relief is per
    // branch, and the check below samples leaves branch by branch.
    node.__branch = depth === 1 ? node.id : branch;
    allNodes.push(node);
    for (const child of node.children || []) walkGraph(child, depth + 1, node.__branch);
  };
  walkGraph(graphJson);
  const subtreeSizeOf = (node) => {
    let n = 0;
    const count = (item) => { n += 1; for (const child of item.children || []) count(child); };
    count(node);
    return n;
  };

  // Which sourced figure of another kind heads an unmeasured organisation's
  // panel, recomputed here from the served graph in the order js/ui.js
  // declares (SOURCED_FIGURE_STAND_IN_ORDER) so the checks below hold the
  // page to the data rather than to itself.
  const SOURCED_FIGURE_KINDS = ["fileA", "combined", "omb", "audited", "disbursed"];
  const SOURCED_FIGURE_FIELDS = { fileA: ["usaspendingOutlays", "amount"], combined: ["combinedStatementOutlays", "amount"], omb: ["ombBudget", "outlays"], audited: ["auditedNetCost", "netCostUsd"], disbursed: ["committeeDisbursements", "amount"] };
  const sourcedFigureAmountOf = (n, kind) => {
    const [field, amountField] = SOURCED_FIGURE_FIELDS[kind];
    const block = n[field];
    const amount = block && typeof block === "object" ? block[amountField] : null;
    return typeof amount === "number" && Number.isFinite(amount) && amount !== 0 ? amount : null;
  };
  const sourcedKindOf = (n) => {
    if (["official", "root_total"].includes(String(n.cost_status || ""))) return null;
    if (/position|\brole\b|office holder/i.test(String(n.type || ""))) return null;
    if (String(n.synthetic || "")) return null;
    if (String(n.lifecycle || "") === "superseded" || String(n.cost_validation || "") === "unit_superseded") return null;
    // A curated accounting line from the Combined Statement is one account and
    // takes that chapter's figure for it, nothing else (js/ui.js).
    if (/treasury accounting line/i.test(String(n.type || ""))) return sourcedFigureAmountOf(n, "combined") !== null ? "combined" : null;
    return SOURCED_FIGURE_KINDS.find((kind) => sourcedFigureAmountOf(n, kind) !== null) || null;
  };
  const signedDollars = (amount) => `${amount < 0 ? "-" : ""}$${Math.round(Math.abs(amount)).toLocaleString("en-US")}`;
  const hasSourcedFigureBlock = (n) => Boolean(n.usaspendingOutlays || n.combinedStatementOutlays || n.ombBudget || n.auditedNetCost || n.committeeDisbursements);

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
  check("the guide says the withheld box reveals nothing for the rest", /have no cost figure at all and never will/.test(guideText), guideText.slice(0, 600));
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
  await page.waitForFunction(() => window.__atlas_loaded__ === true, null, { timeout: 30000 });
  // The stylesheet upper-cases the strip, and innerText reports the rendered
  // text, so every match here is case-insensitive. The counts are held to
  // the same definitions the provenance line uses, recomputed from the
  // served graph: measured is official/root_total plus the receipts lines,
  // sourced is a non-empty sourceUrls, and the estimates are the nodes that
  // carry an apportioned share.
  const coverageText = (await text("#atlas-coverage")).replace(/\s+/g, " ");
  check(
    "the directory exposes evidence coverage",
    /costs measured from the monthly treasury statement/i.test(coverageText) && /nodes carry a source/i.test(coverageText) && /apportioned estimates, withheld/i.test(coverageText),
    coverageText,
  );
  check("the directory does not call a figure reported", !/reported financial figures|verified records/i.test(coverageText), coverageText);
  const directoryMeasured = /([\d,]+) costs measured/i.exec(coverageText);
  const expectedDirectoryMeasured = allNodes.filter((n) => String(n.synthetic || "") === "treasury_receipts" || ["official", "root_total"].includes(String(n.cost_status || ""))).length;
  check(
    "the directory's measured count is the graph's own",
    Boolean(directoryMeasured) && Number(directoryMeasured[1].replace(/,/g, "")) === expectedDirectoryMeasured,
    `${directoryMeasured ? directoryMeasured[1] : "absent"} shown, ${expectedDirectoryMeasured} in the served graph`,
  );
  const directorySourced = /([\d,]+) of [\d,]+ nodes carry a source/i.exec(coverageText);
  const expectedDirectorySourced = allNodes.filter((n) => Array.isArray(n.sourceUrls) && n.sourceUrls.length).length;
  check(
    "the directory's sourced count is the graph's own",
    Boolean(directorySourced) && Number(directorySourced[1].replace(/,/g, "")) === expectedDirectorySourced,
    `${directorySourced ? directorySourced[1] : "absent"} shown, ${expectedDirectorySourced} in the served graph`,
  );
  const directoryAllocated = /([\d,]+) apportioned estimates, withheld/i.exec(coverageText);
  const expectedDirectoryAllocated = allNodes.filter((n) => String(n.cost_status || "") === "allocated").length;
  check(
    "the directory's estimate count is the graph's own",
    Boolean(directoryAllocated) && Number(directoryAllocated[1].replace(/,/g, "")) === expectedDirectoryAllocated,
    `${directoryAllocated ? directoryAllocated[1] : "absent"} shown, ${expectedDirectoryAllocated} allocated in the served graph`,
  );
  check("the first organizational generation is rendered", await page.locator("#atlas-columns .atlas-generation").count() >= 1, "no generation column");
  await page.fill("#atlas-search", "Bureau of Prisons");
  await page.waitForTimeout(250);
  check("directory search finds a published entity", await page.locator("#atlas-search-results .atlas-result").count() >= 1, "no directory result");
  await page.fill("#atlas-search", "");

  // Examples are chosen from the served graph, never named: a node reachable
  // in the directory sits within six generations, is not a replaced unit,
  // and has a name no other node shares, so the search result carrying its
  // own id is the one clicked.
  const depthById = new Map();
  const walkDepth = (node, depth) => {
    depthById.set(node.id, depth);
    for (const child of node.children || []) walkDepth(child, depth + 1);
  };
  walkDepth(graphJson, 0);
  const directoryNameCounts = new Map();
  for (const n of allNodes) directoryNameCounts.set(n.name, (directoryNameCounts.get(n.name) || 0) + 1);
  const reachable = (n) => depthById.get(n.id) <= 6 && directoryNameCounts.get(n.name) === 1 && String(n.lifecycle || "") !== "superseded";
  const openInDirectory = async (node) => {
    await page.fill("#atlas-search", node.name);
    await page.waitForTimeout(250);
    const result = page.locator(`#atlas-search-results .atlas-result[data-result-id="${node.id}"]`);
    if (!(await result.count())) return false;
    await result.first().click();
    await page.waitForTimeout(150);
    return true;
  };
  const rowText = async (selector) => (await page.locator(`#atlas-detail ${selector}`).first().innerText()).replace(/\s+/g, " ").trim();
  const isPostNode = (n) => /position/i.test(String(n.type || ""));

  // A post: the panel's sentence, no dollar figure under cost, and where an
  // official document states a rate, that rate under PAY and never COST.
  const directoryPost =
    allNodes.find((n) => isPostNode(n) && n.cost_validation === "post_is_not_a_budget_unit" && n.positionSchedulePay && n.desc && !n.descriptionSource && reachable(n))
    || allNodes.find((n) => isPostNode(n) && n.cost_validation === "post_is_not_a_budget_unit" && reachable(n));
  check("a post is reachable in the directory", Boolean(directoryPost), "none");
  if (directoryPost) {
    check("the directory opens a post", await openInDirectory(directoryPost), directoryPost.name);
    const costRow = await rowText(".cost-row");
    check("the directory says a post is not a budget unit", /This is a post, not a unit of government/.test(costRow), costRow);
    check("the directory shows no dollar cost for a post", !/\$\s?[\d,]+/.test(costRow), costRow);
    check("the directory does not call a post's cost measured", !/measured/i.test(costRow), costRow);
    if (directoryPost.positionSchedulePay) {
      const payHead = await rowText(".pay-row dt");
      const payRow = await rowText(".pay-row dd");
      check("a post's pay is headed pay, not cost", /^pay$/i.test(payHead), payHead);
      check("a post's Executive Schedule rate is shown under pay", /Executive Schedule level/.test(payRow) && /\$[\d,]+/.test(payRow), payRow);
      check("a rate of pay says it is not the unit's cost", /not a share of federal outlays/.test(payRow), payRow);
    }
    if (directoryPost.desc && !directoryPost.descriptionSource) {
      const descLabel = await rowText(".detail-desc-label");
      check("a base-graph description is labelled uncited in the directory", /uncited prose from the base graph/i.test(descLabel), descLabel);
    }
  }

  // A post priced from Schedule 8's monthly basic pay: the directory's pay
  // row carries the military block under its own heading. Skipped with a
  // note when the served graph carries no such node (see the universe-view
  // check further down for why), never failed on the absence of data.
  const directoryMilitary = allNodes.find((n) => isPostNode(n) && n.positionMilitaryPay && typeof n.positionMilitaryPay.amount === "number" && reachable(n));
  if (directoryMilitary) {
    check("the directory opens a post priced from Schedule 8", await openInDirectory(directoryMilitary), directoryMilitary.name);
    const militaryPayHead = await rowText(".pay-row dt");
    const militaryPayRow = await rowText(".pay-row dd");
    check("the directory heads military basic pay as pay, not cost", /^pay$/i.test(militaryPayHead), militaryPayHead);
    check("the directory prints the military basic pay heading", /Military basic pay — twelve months of a printed monthly rate/i.test(militaryPayRow), militaryPayRow);
    check("the directory prints the monthly figure the schedule states", militaryPayRow.includes(directoryMilitary.positionMilitaryPay.monthly.text), militaryPayRow);
    check("the directory says the annual figure is this project's arithmetic", /twelve times that, arithmetic this project performed and no document prints/.test(militaryPayRow), militaryPayRow);
  } else if (!allNodes.some((n) => n.positionMilitaryPay)) {
    measurements.directoryMilitaryPay = "skipped: no node in the served graph carries positionMilitaryPay";
  }

  // An organisation whose queued page could not be read: the directory says
  // why, as a fact about the host, and never "no source recorded".
  const unreadOrg = allNodes.find((n) => !isPostNode(n) && n.verificationUnread && !n.verificationMethod && !n.verificationFailure && reachable(n));
  check("an unread organisation is reachable in the directory", Boolean(unreadOrg), "none");
  if (unreadOrg) {
    check("the directory opens an unread organisation", await openInDirectory(unreadOrg), unreadOrg.name);
    const evidenceRow = await rowText(".detail-row:first-child dd");
    check("an unread page is not called no source recorded", !/no source recorded/i.test(evidenceRow), evidenceRow);
    check("an unread page says why it went unread", /^Not verified: /.test(evidenceRow) && /(could not be read|was not read|answered 404|refused until|could not be reached)/.test(evidenceRow), evidenceRow);
  }

  // An organisation with a recorded reason no page could be named: the
  // directory says the reason, never "no source recorded".
  const noDocumentDirOrg = allNodes.find((n) => !isPostNode(n) && n.verificationNoDocument && !n.verificationMethod && !n.verificationUnread && !n.verificationFailure && reachable(n));
  check("a no-document organisation is reachable in the directory", Boolean(noDocumentDirOrg), "none");
  if (noDocumentDirOrg) {
    check("the directory opens a no-document organisation", await openInDirectory(noDocumentDirOrg), noDocumentDirOrg.name);
    const evidenceRow = await rowText(".detail-row:first-child dd");
    check("a recorded reason is not called no source recorded in the directory", !/no source recorded/i.test(evidenceRow), evidenceRow);
    check("the directory says why no page could be named", /^Not verified: /.test(evidenceRow), evidenceRow);
  }

  // A checked-and-failed node says what was tested and against what.
  const failedNode = allNodes.find((n) => n.verificationFailure && reachable(n));
  if (failedNode) {
    check("the directory opens a failed check", await openInDirectory(failedNode), failedNode.name);
    const evidenceRow = await rowText(".detail-row:first-child dd");
    check("a failed check is not called no source recorded", !/no source recorded/i.test(evidenceRow), evidenceRow);
    check("a failed check says what was tested", /(does not name it as a heading or link|it carries no unit of this name under)/.test(evidenceRow), evidenceRow);
  }

  // A measured organisation: the Treasury's exact figure labelled measured,
  // the existence method in words, and the cost's source on its own row —
  // never offered as evidence the unit exists.
  const measuredOrg = allNodes.find((n) => !isPostNode(n) && ["official", "root_total"].includes(String(n.cost_status || "")) && n.costVerificationStatus === "verified" && n.verificationMethod && reachable(n));
  check("a measured organisation with an existence method is reachable", Boolean(measuredOrg), "none");
  if (measuredOrg) {
    check("the directory opens a measured organisation", await openInDirectory(measuredOrg), measuredOrg.name);
    const costRow = await rowText(".cost-row");
    const exact = `$${Math.round(Math.abs(Number(measuredOrg.resolved_total_amount))).toLocaleString("en-US")}`;
    check("a measured cost is shown exactly and labelled measured", costRow.includes(exact) && /Measured/.test(costRow) && /Monthly Treasury Statement/.test(costRow), costRow);
    check("a measured cost is not called an estimate", !/estimate/i.test(costRow), costRow);
    const evidenceRow = await rowText(".detail-row:first-child dd");
    check("a measured organisation's evidence line names the method", /(names it|lists it|carries it|carries an entry for it|lists a post of this name)/.test(evidenceRow), evidenceRow);
    check("the cost's source is not offered as existence evidence", !/fiscaldata/i.test(evidenceRow) && (await page.locator('#atlas-detail .detail-row:nth-child(2) a[href*="fiscaldata.treasury.gov"]').count()) === 0, evidenceRow);
    check("the cost's source has its own row", (await page.locator('#atlas-detail a[href*="fiscaldata.treasury.gov"]').count()) >= 1 && /Evidence of the cost, not of the unit's existence/.test(await text("#atlas-detail")), "no cost-source row");
    check("the directory has no 'open primary evidence' link", !/Open primary evidence/i.test(await text("#atlas-detail")), "link present");
  }

  // An organisation with no measured cost headed by a sourced figure of
  // another kind (the owner's decision of 2026-10-07): the directory's row is
  // named for the measure, never "Cost", carries the block's own figure and
  // year, and its source sits on a row of its own.
  // The stylesheet upper-cases the term and innerText reports the rendered
  // text, so the match is case-insensitive.
  const directorySourcedTerms = { fileA: /^Gross outlays — USAspending File A$/i, combined: /^Net outlays — Treasury Combined Statement$/i, omb: /^Outlays — OMB Public Budget Database$/i, audited: /^Audited net cost — Treasury Statement of Net Cost$/i, disbursed: /^Paid out — (House Statement of Disbursements|Senate Secretary's report)$/i };
  for (const kind of SOURCED_FIGURE_KINDS) {
    const node = allNodes.find((n) => sourcedKindOf(n) === kind && reachable(n));
    if (!node) {
      measurements[`directorySourcedFigure_${kind}`] = "skipped: no reachable organisation in the served graph is headed by this kind";
      continue;
    }
    check(`the directory opens an organisation headed by a sourced figure (${kind})`, await openInDirectory(node), node.name);
    const term = await rowText(".cost-row dt");
    const costRow = await rowText(".cost-row dd");
    const figure = sourcedFigureAmountOf(node, kind);
    check(`the directory names the measure, not Cost (${kind})`, directorySourcedTerms[kind].test(term) && !/^cost$/i.test(term), term);
    check(`the directory prints the block's own figure (${kind})`, costRow.includes(signedDollars(figure).replace(/^-/, "−")), `${costRow} / ${signedDollars(figure)}`);
    check(`the directory badge says a sourced figure of another kind is shown (${kind})`, /No measured cost; a sourced figure of another kind is shown/.test(costRow), costRow);
    check(`the directory does not call the figure measured (${kind})`, !/\bMeasured\b/.test(costRow), costRow);
    check(`the directory gives the figure's source its own row (${kind})`, /Evidence of this figure, which is not the unit's cost/.test(await text("#atlas-detail")), "no figure-source row");
  }

  // A replaced unit is hidden until asked for, and labelled when shown.
  const replacedNode = allNodes.find((n) => String(n.lifecycle || "") === "superseded" && depthById.get(n.id) <= 6 && directoryNameCounts.get(n.name) === 1);
  if (replacedNode) {
    await page.fill("#atlas-search", replacedNode.name);
    await page.waitForTimeout(250);
    check("a replaced unit is hidden from the directory by default", (await page.locator(`#atlas-search-results .atlas-result[data-result-id="${replacedNode.id}"]`).count()) === 0, replacedNode.name);
    await page.check("#atlas-show-superseded");
    await page.fill("#atlas-search", replacedNode.name);
    await page.waitForTimeout(250);
    const shown = page.locator(`#atlas-search-results .atlas-result[data-result-id="${replacedNode.id}"]`);
    check("a replaced unit appears when asked for", (await shown.count()) === 1, replacedNode.name);
    if (await shown.count()) {
      await shown.first().click();
      await page.waitForTimeout(150);
      check("a replaced unit is labelled as replaced", /REPLACED — the government no longer has this unit as drawn/.test(await text("#atlas-detail")), (await text("#atlas-detail")).slice(0, 300));
    }
    await page.uncheck("#atlas-show-superseded");
  }
  await page.fill("#atlas-search", "");

  await page.locator('.view-switch[data-view="universe"]').click();
  await page.waitForTimeout(100);
  check("the 3D universe remains available", await page.locator("body.atlas-mode").count() === 0, "universe did not open");

  // A still camera must draw a still picture. The density cap is recomputed
  // every frame from screen-tile membership, and when its ranking is unstable
  // nodes blink in and out with nothing moving — the symptom reported on
  // 2026-09-21. Membership is compared, not the count: the count can hold
  // steady while which nodes are drawn churns underneath it.
  const drawnSamples = [];
  for (let i = 0; i < 8; i += 1) {
    drawnSamples.push(await page.evaluate(() => window.__bureaucracy_drawn_node_ids__?.() || []));
    await page.waitForTimeout(140);
  }
  check("the renderer exposes its drawn set for this check", drawnSamples[0].length > 0, "no ids returned");
  let drawnChurn = 0;
  for (let i = 1; i < drawnSamples.length; i += 1) {
    const prev = new Set(drawnSamples[i - 1]);
    const cur = new Set(drawnSamples[i]);
    for (const id of cur) if (!prev.has(id)) drawnChurn += 1;
    for (const id of prev) if (!cur.has(id)) drawnChurn += 1;
  }
  check("a still camera draws a still set of nodes", drawnChurn === 0,
    `${drawnChurn} visibility change(s) across ${drawnSamples.length} frames with the camera untouched`);

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

  // Where an agency's money goes: the FY2025 object-class breakdown, staff pay
  // first, under its own heading and never as the cost.
  const withSpending = allNodes.find((n) => n.spendingByKind && n.spendingByKind.staffPay
    && typeof n.spendingByKind.staffPay.amount === "number");
  check("some agency carries an object-class breakdown", Boolean(withSpending), "none");
  if (withSpending) {
    await openByName(withSpending.name);
    const section = await text("#info-spending-by-kind");
    check("the breakdown is headed WHERE THE MONEY GOES with its fiscal year",
      /WHERE THE MONEY GOES — FY2025/.test(section), section.slice(0, 400));
    const staff = Math.round(withSpending.spendingByKind.staffPay.amount).toLocaleString("en-US");
    check("the staff-pay line names the served figure and its share of obligations",
      section.includes(`Pay and benefits of staff: $${staff} (`) && /% of obligations\)/.test(section), section.slice(0, 400));
    check("the breakdown says it is not the cost", /not the Treasury's net outlays shown as cost/.test(section), section.slice(0, 900));
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
    // The sentence sits in the block of whichever listing supplied the level.
    const listing = `${await text("#info-position-listing")}\n${await text("#info-current-listing")}`;
    check("the table rate names the table it came from", /Salary Table No\. \d{4}-EX/.test(listing), listing);
    check("the table rate names the level it prices", /pays \$[\d,]+ for Level [IVX]+/.test(listing), listing);
    check("the panel says it is two documents, not one", /two documents, not one/.test(listing), listing);
    check("the panel disclaims the current holder", /neither says what this post pays whoever holds it now|a table's figure for a rank, not a figure for the post/.test(listing), listing);
    check("the panel says a rate of pay is not the unit's cost", /not this unit's cost/.test(listing), listing);
    check("the pay-freeze note is carried through", /The table's own note: "/.test(listing), listing);
    check("the freeze note names what it covers", /freeze on the payable pay rates/.test(listing), listing);
    // The rate must never be dressed as a measured cost of the unit.
    const stats = await text("#info-stats");
    check("the table rate is not headed as a cost", !/\bCOST\b[^A-Z]*\$[\d,]+/.test(stats) || !/Salary Table/.test(stats), stats);
  }

  // A base-pay RANGE for the pay plan or grade the archive reports — two
  // bounds from a salary table, never a rate, and for the General Schedule
  // base pay before locality. Its own field, rendered in the listing block
  // beside the pay plan it was looked up for, and shown in the cost block
  // under a heading that is not the word COST.
  const withRange = allNodes.find((n) => n.positionGradePay && typeof n.positionGradePay.minimum === "number" && unique(n));
  check("some position carries a base-pay range from a salary table", Boolean(withRange), "none");
  if (withRange) {
    await openByName(withRange.name);
    const listing = `${await text("#info-position-listing")}\n${await text("#info-current-listing")}`;
    check("the range names the table it came from", /Salary Table (No\. )?\d{4}-(GS|ES|SL\/ST)/.test(listing), listing);
    check("the range is two bounds, not one figure", /\$[\d,]+ – \$[\d,]+/.test(listing), listing);
    check("the panel says a range is not a rate or the unit's cost", /not this unit's cost and not necessarily what the post pays now/.test(listing), listing);
    if (withRange.positionGradePay.kind === "general_schedule_grade") {
      check("a General Schedule range says it is base pay before locality",
        new RegExp(`base General Schedule range for grade ${withRange.positionGradePay.grade} in \\d{4}, before locality pay`).test(listing), listing);
    }
    const stats = await text("#info-stats");
    check("the range is not headed as a cost", !/^COST|ANNUAL COST/m.test(stats.split("RANGE")[0]) || !/RANGE/.test(stats), stats.slice(0, 400));
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
    // Since 2026-10-05 the statutory rate is the post's HEADLINE figure, where
    // "Not available" used to sit above a nine-pixel line stating it: the
    // President read "No cost known for this node" with $400,000 a year
    // printed beneath. The headline is headed PAY, never COST, and the badge
    // says a rate of pay is shown in the cost's place.
    const statutoryHead = await text("#info-stats .info-cost-label");
    const statutoryAmount = await text("#info-stats .info-cost-amount");
    check("a statutory rate is the post's headline figure", new RegExp(withStatutoryPay.positionStatutoryPay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(statutoryAmount), statutoryAmount);
    check("the headline is headed PAY, not COST", /^PAY/.test(statutoryHead) && !/COST/.test(statutoryHead), statutoryHead);
    check("the badge says a rate of pay stands in for the cost", /No cost known; .*rate.* is shown/i.test(statutoryStats), statutoryStats.slice(0, 400));
    check("the headline is not called Not available", !/Not available/.test(statutoryAmount), statutoryAmount);
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
    const reportedHead = await text("#info-stats .info-cost-label");
    check("a roster-priced post heads its figure as pay", /^PAY/.test(reportedHead), reportedHead);
    if (!withReportedPay.positionStatutoryPay && !withReportedPay.positionSchedulePay && !withReportedPay.positionTierReferencePay && !withReportedPay.positionDerivedPay && !withReportedPay.positionMilitaryPay) {
      const reportedAmount = await text("#info-stats .info-cost-amount");
      check("the roster's rate is the post's headline figure", new RegExp(withReportedPay.positionReportedPay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(reportedAmount), reportedAmount);
      check("the headline names the staff report", /WHITE HOUSE STAFF REPORT/.test(reportedHead), reportedHead);
    }
  }

  // The exact-costs-only view: with it on, an apportioned share is not shown
  // as a figure at all, and the panel says why.
  // Not one headed by a sourced figure of another kind: that node's badge
  // names the figure it shows, and is checked on its own below.
  const allocatedNode = allNodes.find((n) => n.cost_status === "allocated" && n.resolved_total_amount > 1e6
    && !n.positionListing && !hasSourcedFigureBlock(n) && nameCounts.get(n.name) === 1);
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
    // Since 2026-10-05 the opt-in is one click away inside the cost block
    // too: a button beside the sentence that says the figure is withheld,
    // wired to the same checkbox, so the column's box reflects it.
    const revealButton = page.locator("#info-stats .info-cost-reveal");
    check("the withheld estimate offers a button to show it", (await revealButton.count()) === 1, `${await revealButton.count()} buttons`);
    if ((await revealButton.count()) === 1) {
      await revealButton.first().click();
      await page.waitForTimeout(300);
      const revealed = await text("#info-stats");
      check("the button shows the estimate, labelled", /≈\s*\$/.test(revealed) && /ESTIMATE/.test(revealed), revealed.slice(0, 400));
      const boxOn = await page.evaluate(() => {
        const label = [...document.querySelectorAll("#verification-toggles label")].find((l) => /Also show estimated shares/i.test(l.textContent || ""));
        return label ? label.querySelector("input").checked : null;
      });
      check("the button turned the column's own checkbox on", boxOn === true, String(boxOn));
      check("the button is gone once the estimate is shown", (await page.locator("#info-stats .info-cost-reveal").count()) === 0, "still offered");
      await setEstimatesShown(false);
      await page.waitForTimeout(200);
    }
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

  // Since 2026-10-07 an organisation with no measured cost that carries a
  // sourced figure of another kind — File A's gross outlays, OMB's sum of
  // account rows for a completed year, Treasury's audited net cost — is
  // headed by it, in the order js/ui.js declares, under a heading naming the
  // measure and never COST (the audited statement's own measure is "net
  // cost", and that name is the only COST its label may carry). One node of
  // each kind the served graph has; a kind no node is headed by is recorded
  // under `measurements` rather than failed on the absence of data.
  const sourcedHeads = {
    fileA: /^GROSS OUTLAYS — USASPENDING FILE A$/,
    combined: /^NET OUTLAYS — TREASURY COMBINED STATEMENT$/,
    omb: /^OUTLAYS — OMB PUBLIC BUDGET DATABASE$/,
    audited: /^AUDITED NET COST — TREASURY STATEMENT OF NET COST$/,
    disbursed: /^PAID OUT — (HOUSE STATEMENT OF DISBURSEMENTS|SENATE SECRETARY'S REPORT)$/,
  };
  const sourcedCounts = {};
  for (const kind of SOURCED_FIGURE_KINDS) sourcedCounts[kind] = allNodes.filter((n) => sourcedKindOf(n) === kind).length;
  measurements.sourcedFigureHeadlines = sourcedCounts;
  for (const kind of SOURCED_FIGURE_KINDS) {
    // Prefer a node that also carries a withheld estimate, so the reveal
    // button can be checked beside the new headline.
    const candidates = allNodes.filter((n) => sourcedKindOf(n) === kind && unique(n));
    const node = candidates.find((n) => n.cost_status === "allocated") || candidates[0];
    if (!node) {
      measurements[`sourcedFigure_${kind}`] = "skipped: no organisation in the served graph is headed by this kind";
      continue;
    }
    const figure = sourcedFigureAmountOf(node, kind);
    await openByName(node.name);
    const head = await text("#info-stats .info-cost-label");
    const amount = await text("#info-stats .info-cost-amount");
    const stats = await text("#info-stats .info-cost");
    measurements[`sourcedFigure_${kind}`] = { id: node.id, head, amount: amount.split("\n")[0] };
    check(`a sourced figure is the organisation's headline (${kind})`, amount.split("\n")[0] === signedDollars(figure), `${amount} / ${signedDollars(figure)}`);
    check(`the headline names the measure (${kind})`, sourcedHeads[kind].test(head), head);
    check(`the headline is never headed COST (${kind})`, !/COST/.test(head.replace(/NET COST/g, "")) && !/^(ANNUAL )?COST$/.test(head), head);
    check(`the badge says a sourced figure of another kind is shown (${kind})`, /No measured cost; a sourced figure of another kind is shown/i.test(stats), stats.slice(0, 400));
    check(`the badge is not the measured one (${kind})`, (await page.locator("#info-stats .info-cost-badge.is-measured").count()) === 0, "measured badge drawn");
    check(`the headline is not called Not available (${kind})`, !/Not available/.test(amount), amount);
    const period = await text("#info-stats .info-cost-period");
    const block = node[SOURCED_FIGURE_FIELDS[kind][0]];
    check(`the period line is read off the block (${kind})`, (kind === "disbursed" ? period.includes(String(block.period.start).slice(0, 4)) : period.includes(`FY${block.fiscalYear}`)) && (kind !== "fileA" || period.includes(block.periodAsOf)) && (kind !== "audited" || period.includes(block.statementDate)), period);
    check(`the period line says it is not the cost (${kind})`, /not the cost/.test(period), period);
    if (kind === "combined") {
      check("the Combined Statement headline says it is a completed year, not this year's", /a completed year/.test(period) && /not this year's/.test(period), period);
    }
    if (kind === "omb") {
      check("the OMB headline says the figure is a sum of account rows OMB never prints", period.includes(`the sum of ${block.outlayAccountRows.toLocaleString("en-US")} account rows`) && /not a figure OMB prints/.test(period), period);
    }
    if (node.cost_status === "allocated") {
      check(`the estimate stays withheld beside the sourced headline (${kind})`, /share of an ancestor's measured total/.test(stats) && !/≈\s*\$/.test(stats), stats.slice(0, 600));
      const reveal = page.locator("#info-stats .info-cost-reveal");
      check(`the reveal button stays beside the sourced headline (${kind})`, (await reveal.count()) === 1, `${await reveal.count()} buttons`);
      if ((await reveal.count()) === 1) {
        await reveal.first().click();
        await page.waitForTimeout(300);
        const revealed = await text("#info-stats .info-cost");
        check(`the button shows the estimate in the headline's place (${kind})`, /≈\s*\$/.test(revealed) && /ESTIMATE/i.test(revealed), revealed.slice(0, 300));
        await setEstimatesShown(false);
        await page.waitForTimeout(200);
      }
    }
  }

  // A Combined Statement figure the Treasury files under another section than
  // the graph gives the unit says so (CURATION.md Sec 22.8), and one filed
  // where the graph files it does not.
  const filedElsewhere = allNodes.find((n) => sourcedKindOf(n) === "combined" && n.combinedStatementOutlays.treasurySection
    && n.combinedStatementOutlays.treasurySection.filedInAnotherSection === true && unique(n));
  if (filedElsewhere) {
    await openByName(filedElsewhere.name);
    const panel = await text("#info-stats");
    check("a Combined Statement figure filed under another section says so", /files this account under the Legislative Branch chapter/.test(panel), panel.slice(0, 600));
    measurements.combinedFiledElsewhere = filedElsewhere.id;
    const filedHere = allNodes.find((n) => sourcedKindOf(n) === "combined" && n.combinedStatementOutlays.treasurySection
      && n.combinedStatementOutlays.treasurySection.filedInAnotherSection === false && unique(n));
    if (filedHere) {
      await openByName(filedHere.name);
      check("a Combined Statement figure filed where the graph files it says nothing of another section", !/files this account under/.test(await text("#info-stats")), filedHere.name);
    }
  } else {
    measurements.combinedFiledElsewhere = "skipped: no organisation headed by a Combined Statement figure filed elsewhere";
  }

  // An appropriation account carried as its own Treasury accounting line
  // (CURATION.md Sec 22.9) is headed by the chapter's figure for it, and its
  // description says the statement is where the node comes from.
  const accountLine = allNodes.find((n) => /treasury accounting line/i.test(String(n.type || "")) && !n.synthetic
    && n.combinedStatementOutlays && unique(n));
  if (accountLine) {
    await openByName(accountLine.name);
    const head = await text("#info-stats .info-cost-label");
    const amount = (await text("#info-stats .info-cost-amount")).split("\n")[0];
    measurements.combinedAccountLine = { id: accountLine.id, head, amount };
    check("an account line is headed by the chapter's figure for its account", sourcedHeads.combined.test(head)
      && amount === signedDollars(accountLine.combinedStatementOutlays.amount), `${head} ${amount}`);
    const desc = await text("#info-desc-provenance");
    check("an account line's description says the Combined Statement prints the account", /Combined Statement, which prints this account/.test(desc), desc);
  } else {
    measurements.combinedAccountLine = "skipped: no account line in the served graph";
  }

  // An organisation left with only an estimate says which held money
  // documents were checked for its name (criterion 1's explained blank), and
  // one a held document names says which row it prints.
  const blankOrg = allNodes.find((n) => n.costNoDocument && n.costNoDocument.kind === "no_held_document_names_it" && unique(n));
  check("some organisation carries an explained blank", Boolean(blankOrg), "none");
  if (blankOrg) {
    await openByName(blankOrg.name);
    const blankPanel = await text("#info-stats");
    check("an explained blank names the documents checked", /No document this project holds prints a figure for this unit/.test(blankPanel) && /documents checked for a row carrying this unit's name: Monthly Treasury Statement/.test(blankPanel), blankPanel.slice(0, 900));
    measurements.explainedBlank = blankOrg.id;
  }
  const namedOrg = allNodes.find((n) => n.costNoDocument && n.costNoDocument.kind === "named_in_a_held_document_without_a_licensed_figure" && unique(n));
  if (namedOrg) {
    await openByName(namedOrg.name);
    const namedPanel = await text("#info-stats");
    check("a unit a held document names says which row it prints", /A held document does print this unit's name/.test(namedPanel) && new RegExp(namedOrg.costNoDocument.namedIn[0].printed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(namedPanel), namedPanel.slice(0, 900));
    measurements.namedBlank = namedOrg.id;
  } else {
    measurements.namedBlank = "skipped: no organisation a held document names without a licensed figure";
  }
  const subcommittee = allNodes.find((n) => /^subcommittee$/i.test(String(n.type || "")) && n.cost_status === "allocated" && unique(n));
  if (subcommittee) {
    await openByName(subcommittee.name);
    check("a subcommittee says it is funded through its committee", /funded through its committee/.test(await text("#info-stats")), subcommittee.name);
  }

  // Freshness (criterion 6): the panel lists the sources behind a node and
  // marks one overdue when the reader's date is past the registry's
  // overdueAfter. The expected status is recomputed here from the served
  // root block with the same date arithmetic, and the page must agree.
  const registry = graphJson.__sourceRegistry;
  check("the served graph's root carries the source registry", Boolean(registry && Array.isArray(registry.sources) && registry.sources.length > 10), JSON.stringify(registry && registry.counts));
  if (registry && Array.isArray(registry.sources)) {
    const today = new Date().toISOString().slice(0, 10);
    const statusOf = (entry) => {
      const kind = String((entry.cadence || {}).kind || "");
      const e = entry.expected || {};
      if (kind === "closed_record") return "closed_record";
      if (kind === "on_republication") return !e.recheckDue ? "copy_date_unknown" : today > e.recheckDue ? "recheck_due" : "current";
      if (!(entry.copy || {}).date || !e.expectedBy) return "copy_date_unknown";
      return today <= e.expectedBy ? "current" : today <= e.overdueAfter ? "newer_edition_expected" : "overdue";
    };
    const mts = registry.sources.find((s) => s.id === "monthly_treasury_statement");
    const measured = allNodes.find((n) => n.cost_status === "official" && !n.synthetic && unique(n) && /^Department of/.test(n.name));
    check("a measured node and the Treasury statement's registry row exist", Boolean(mts && measured), `${Boolean(mts)} ${Boolean(measured)}`);
    if (mts && measured) {
      await openByName(measured.name);
      const freshText = await text("#info-freshness");
      const mtsLine = await page.$eval('#info-freshness li[data-source="monthly_treasury_statement"]', (el) => ({ text: el.textContent, status: el.dataset.status })).catch(() => null);
      check("a measured node's panel lists the Treasury statement among its sources", Boolean(mtsLine) && mtsLine.text.includes(mts.label), freshText.slice(0, 400));
      check("the panel's status for the statement is the registry's dates read against today", Boolean(mtsLine) && mtsLine.status === statusOf(mts) && (statusOf(mts) !== "overdue" || /^OVERDUE/.test(mtsLine.text)), mtsLine ? `${mtsLine.status} vs ${statusOf(mts)}` : "no line");
      check("the panel names the copy in use by its date", Boolean(mtsLine) && mtsLine.text.includes(String(mts.copy.date)), mtsLine ? mtsLine.text : "");
      measurements.freshness = { node: measured.id, statement: statusOf(mts), counts: registry.counts };
    }
    const overdue = registry.sources.filter((s) => statusOf(s) === "overdue");
    const overdueNode = overdue.length
      ? allNodes.find((n) => unique(n) && !/position/i.test(String(n.type || "")) && overdue.some((s) => (s.graphFields || []).some((spec) => typeof spec === "string" ? Boolean(n[spec] && typeof n[spec] === "object") : spec && spec.field && n[spec.field] && typeof n[spec.field] === "object" && (spec.where || []).every(([k, v]) => String(n[spec.field][k]) === String(v)))))
      : null;
    if (overdueNode) {
      await openByName(overdueNode.name);
      const overdueText = await text("#info-freshness");
      check("a node fed by an overdue source says OVERDUE and counts it in the heading", /OVERDUE — /.test(overdueText) && /of \d+ overdue:/.test(overdueText), overdueText.slice(0, 400));
      measurements.freshnessOverdue = { node: overdueNode.id, sources: overdue.map((s) => s.id) };
    } else {
      measurements.freshnessOverdue = overdue.length ? "skipped: no reachable organisation carries an overdue source's fields" : "skipped: no source is overdue today";
    }
  }

  // What changed (Part 2): the card shows the latest recorded build's own
  // summary and budget verdict from output/change_history.json, which the
  // check reads for itself.
  const historyPath = path.join(ROOT, "output", "change_history.json");
  if (fs.existsSync(historyPath)) {
    const history = JSON.parse(fs.readFileSync(historyPath, "utf8"));
    const latest = Array.isArray(history) && history.length ? history[0] : null;
    check("the change history has a latest entry", Boolean(latest && latest.summary), "none");
    if (latest) {
      await page.click("#btn-change-history");
      await page.waitForTimeout(400);
      const open = await page.$eval("#change-history", (el) => el.classList.contains("open") && el.getAttribute("aria-hidden") === "false");
      check("the What changed card opens", open, String(open));
      const body = await text("#change-history-body");
      check("the card prints the latest entry's own summary", body.includes(latest.summary.slice(0, 80)), body.slice(0, 300));
      check("the card states the budget verdict", latest.budget && latest.budget.held ? /HELD by the change budget/.test(body) : /Within the change budget/.test(body), body.slice(0, 120));
      const foot = await text("#change-history-foot");
      check("the card names the review queue and its open count", /review queue/.test(foot) && (typeof latest.reviewQueueOpen !== "number" || foot.includes(String(latest.reviewQueueOpen))), foot);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
      check("Escape closes the card", await page.$eval("#change-history", (el) => !el.classList.contains("open")), "still open");
      measurements.changeHistory = { builtAt: latest.builtAt, held: Boolean(latest.budget && latest.budget.held), touched: (latest.touched || []).length };
    }
  } else {
    measurements.changeHistory = "skipped: no output/change_history.json";
  }

  // Download (Part 2): the card lists the files the page names, each a link
  // the server actually serves, the CSV among them.
  await page.click("#btn-download");
  await page.waitForTimeout(600);
  const downloadLinks = await page.$$eval("#download-body a", (els) => els.map((a) => ({ href: a.getAttribute("href"), name: a.textContent })));
  check("the Download card lists the graph, the CSV and the registry", downloadLinks.some((l) => l.name === "graph.json") && downloadLinks.some((l) => l.name === "nodes.csv") && downloadLinks.some((l) => l.name === "source_registry.json"), JSON.stringify(downloadLinks));
  let served = 0;
  for (const link of downloadLinks) {
    const response = await page.request.fetch(new URL(link.href, page.url()).toString(), { method: "HEAD" }).catch(() => null);
    if (response && response.ok()) served += 1;
  }
  check("every file the Download card offers is served", served === downloadLinks.length, `${served} of ${downloadLinks.length}`);
  const sizes = await page.$$eval("#download-body .dl-size", (els) => els.map((e) => e.textContent));
  check("the card shows each file's size", sizes.length === downloadLinks.length && sizes.every((s) => /\d/.test(s)), JSON.stringify(sizes));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  measurements.downloads = downloadLinks.map((l) => l.name);

  // A measured unit's total adds up visibly (criterion 4(b)): the panel lists
  // every part the statement prints beneath its header, which node each landed
  // on, what reaches no node and is divided among the estimated children, and
  // says the parts sum to the total.
  const sumNode = allNodes.find((n) => n.id === "exec-dept-va" && n.treasury_sum) || allNodes.find((n) => n.treasury_sum && n.treasury_sum.toNoNode && n.treasury_sum.estimatedChildren.length && unique(n));
  check("some measured unit carries a treasury_sum block", Boolean(sumNode), "none");
  if (sumNode) {
    await openByName(sumNode.name);
    const sumText = await text("#info-cost-sum");
    const noNodePart = sumNode.treasury_sum.parts.find((p) => p.where === "none");
    const childPart = sumNode.treasury_sum.parts.find((p) => p.where === "child" && p.kind !== "receipts");
    check("the sum block names a part that reaches no node and says so", noNodePart ? sumText.includes(noNodePart.name) && /no node here/.test(sumText) : true, sumText.slice(0, 600));
    check("the sum block names the child a part landed on", childPart ? sumText.includes(childPart.nodeName) : true, sumText.slice(0, 600));
    check("the sum block names the estimated children that divide the no-node money, or says the lines are the unit's own",
      sumNode.treasury_sum.estimatedChildren.length
        ? sumNode.treasury_sum.estimatedChildren.every((c) => sumText.includes(c.name)) && /divided among/.test(sumText) && /an apportionment, not a measurement/.test(sumText)
        : /not subdivided further/.test(sumText),
      sumText.slice(0, 900));
    check("the sum block says the parts sum to the total exactly", Math.abs(sumNode.treasury_sum.notAttributed) > 0.005 ? /Not attributed/.test(sumText) : /sum to the total exactly/.test(sumText), sumText.slice(-200));
    measurements.treasurySum = { node: sumNode.id, parts: sumNode.treasury_sum.parts.length };
  }

  // A post no pay document prices and no employer block explains says which
  // held title-listing pay documents were checked for its title (criterion
  // 2's explained blank), and one whose title a held document prints says so.
  const blankPost = allNodes.find((n) => n.payNoDocument && n.payNoDocument.kind === "no_held_pay_document_prints_the_title" && n.payNoDocument.reason === "unreached" && unique(n));
  check("some post carries an explained pay blank", Boolean(blankPost), "none");
  if (blankPost) {
    await openByName(blankPost.name);
    const blankText = await text("#info-pay-blank");
    check("a post's pay blank names the documents checked and says none prints the title",
      /Why no pay figure:/.test(blankText) && /no pay document this project has read names this title under this organisation/.test(blankText)
        && /title-listing pay documents this project holds were checked for the title: 5 U\.S\.C/.test(blankText) && /None of them prints this title\./.test(blankText)
        && /an explained blank, not a document saying the post is unpaid/.test(blankText),
      blankText.slice(0, 900));
    const blankHead = await text("#info-stats .info-cost-amount");
    check("a post's headline still reads Not available: the blank is not a figure", /Not available/.test(blankHead), blankHead);
    measurements.payBlank = blankPost.id;
  }
  const namedPost = allNodes.find((n) => n.payNoDocument && n.payNoDocument.kind === "title_printed_in_a_held_pay_document_without_a_row_reaching_this_post" && unique(n));
  if (namedPost) {
    await openByName(namedPost.name);
    const namedText = await text("#info-pay-blank");
    check("a post whose title a held document prints says so and which document",
      /A held document does print this title/.test(namedText) && new RegExp(namedPost.payNoDocument.namedIn[0].printed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(namedText) && /no reviewed rule ties to this post/.test(namedText),
      namedText.slice(0, 900));
    measurements.payBlankNamed = namedPost.id;
  } else {
    measurements.payBlankNamed = "skipped: no post whose title a held pay document prints";
  }
  const pricedPost = allNodes.find((n) => n.positionStatutoryPay && !n.payNoDocument && unique(n));
  if (pricedPost) {
    await openByName(pricedPost.name);
    check("a priced post carries no pay blank line", !(await page.$("#info-pay-blank")), pricedPost.id);
  }

  // A negative OMB figure is shown as the database gives it, with OMB's own
  // sentence saying amounts are net of offsetting collections.
  const negativeOmb = allNodes.find((n) => sourcedKindOf(n) === "omb" && n.ombBudget.outlays < 0 && unique(n));
  if (negativeOmb) {
    await openByName(negativeOmb.name);
    const amount = await text("#info-stats .info-cost-amount");
    const note = await text("#info-stats .info-cost-note");
    check("a negative OMB figure is the headline as given, sign leading", amount.split("\n")[0] === signedDollars(negativeOmb.ombBudget.outlays), amount);
    check("a negative OMB figure carries OMB's net-of-collections sentence", note.includes(String(negativeOmb.ombBudget.netQuote).trim()), note);
    measurements.sourcedFigureNegativeOmb = negativeOmb.id;
  } else {
    measurements.sourcedFigureNegativeOmb = "skipped: no organisation headed by OMB nets below zero";
  }

  // A unit beneath a negative Treasury pool has no estimate and may take a
  // sourced figure; it is offered no reveal button, because there is
  // nothing to reveal.
  const poolNegativeSourced = allNodes.find((n) => sourcedKindOf(n) && n.cost_validation === "treasury_pool_negative" && unique(n));
  if (poolNegativeSourced) {
    await openByName(poolNegativeSourced.name);
    const amount = await text("#info-stats .info-cost-amount");
    const kind = sourcedKindOf(poolNegativeSourced);
    check("a unit beneath a negative pool is headed by its sourced figure", amount.split("\n")[0] === signedDollars(sourcedFigureAmountOf(poolNegativeSourced, kind)), amount);
    check("a unit beneath a negative pool is offered no estimate", (await page.locator("#info-stats .info-cost-reveal").count()) === 0, "reveal button drawn");
  } else {
    measurements.sourcedFigurePoolNegative = "skipped: no unit beneath a negative pool carries a sourced figure";
  }

  // A measured node carrying the same blocks keeps the Treasury's figure as
  // its headline: the sourced figure never displaces a measurement.
  const measuredWithBlocks = allNodes.find((n) => n.cost_status === "official" && n.costVerificationStatus === "verified"
    && !n.synthetic && n.ombBudget && unique(n));
  check("some measured node carries an OMB figure beside it", Boolean(measuredWithBlocks), "none");
  if (measuredWithBlocks) {
    await openByName(measuredWithBlocks.name);
    const head = await text("#info-stats .info-cost-label");
    const amount = await text("#info-stats .info-cost-amount");
    check("a measured node's headline is still its Treasury figure", amount.split("\n")[0] === signedDollars(Number(measuredWithBlocks.resolved_total_amount)), amount);
    check("a measured node is still headed as a cost", /^(ANNUAL )?COST$/.test(head), head);
    check("a measured node still wears the measured badge", (await page.locator("#info-stats .info-cost-badge.is-measured").count()) === 1, "no measured badge");
  }

  // A post never takes an organisation's figure, whatever it carries.
  const postsWithBlocks = allNodes.filter((n) => /position/i.test(String(n.type || "")) && hasSourcedFigureBlock(n)).length;
  measurements.postsCarryingSourcedFigureBlocks = postsWithBlocks;

  // A position with a real reported rate of pay shows it in place of the
  // withheld estimate, under a heading that is not the word COST.
  // A node whose ONLY pay claim is the archive's printed rate: the headline
  // prefers a statute's, a schedule's, a derivation's, the roster's and the
  // current export's figure to it, so a node carrying any of those would be
  // headed by that one instead.
  const paid = allNodes.find((n) => n.positionListing && typeof n.positionListing.reportedPay === "number"
    && !n.positionStatutoryPay && !n.positionSchedulePay && !n.positionTierReferencePay && !n.positionDerivedPay && !n.positionMilitaryPay
    && !n.positionReportedPay && !n.positionCurrentPay
    && nameCounts.get(n.name) === 1);
  check("some position carries a reported rate of pay", Boolean(paid), "none");
  if (paid) {
    await openByName(paid.name);
    const stats = await text("#info-stats");
    check("the rate of pay is shown by default", /REPORTED RATE OF BASIC PAY/.test(stats), stats.slice(0, 400));
    check("the rate is not headed as a cost", !/^COST|ANNUAL COST/m.test(stats.split("REPORTED")[0]), stats.slice(0, 400));
    check("the panel says a salary is not the unit's cost", /compensation for one post, not what this unit costs/.test(stats), stats.slice(0, 700));
  }

  // A post priced from the Executive Schedule and nothing above it in the
  // order: the Code's level, priced by OPM's table, is the headline.
  const scheduled = allNodes.find((n) => n.positionSchedulePay && typeof n.positionSchedulePay.amount === "number"
    && !n.positionStatutoryPay && unique(n));
  check("some position is priced from the Executive Schedule alone", Boolean(scheduled), "none");
  if (scheduled) {
    await openByName(scheduled.name);
    const scheduledHead = await text("#info-stats .info-cost-label");
    const scheduledAmount = await text("#info-stats .info-cost-amount");
    check("an Executive Schedule rate is the headline figure", new RegExp(scheduled.positionSchedulePay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(scheduledAmount), scheduledAmount);
    check("the headline names the Executive Schedule", /EXECUTIVE SCHEDULE/.test(scheduledHead), scheduledHead);
  }

  // A bench priced for each holder keeps the figure and says whose it is.
  const bench = allNodes.find((n) => n.positionDerivedPay && n.positionDerivedPay.holders && Number.isInteger(n.positionDerivedPay.holders.count) && unique(n));
  check("some bench carries a derived rate for each holder", Boolean(bench), "none");
  if (bench) {
    await openByName(bench.name);
    const benchStats = await text("#info-stats");
    const benchHead = await text("#info-stats .info-cost-label");
    check("a bench's derived rate is its headline figure", new RegExp(bench.positionDerivedPay.rateText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(await text("#info-stats .info-cost-amount")), benchHead);
    check("the headline says no document states a derived figure", /DERIVED, STATED BY NO DOCUMENT/.test(benchHead), benchHead);
    check("the bench's figure is said to be each holder's, not the group's", new RegExp(`for each of the ${bench.positionDerivedPay.holders.count} holders`).test(benchStats), benchStats.slice(0, 900));
  }

  // Military basic pay: Schedule 8 of the pay-adjustment order prints the
  // uniformed services' basic pay BY THE MONTH, and the headline is twelve
  // times it -- arithmetic this project performed and no document prints.
  // One node of each route, picked from the served graph: a grade a statute
  // fixes (the Chairman of the Joint Chiefs' "general or admiral", pay grade
  // O-10) and a post the enlisted footnote names by title (the Sergeant
  // Major of the Army). The field lands on the graph only when it is next
  // regenerated, so when NO node carries it the check is skipped with a
  // note under `measurements` rather than failing on the absence of data;
  // once any node carries it, both routes must be present and must render.
  const militaryNodes = allNodes.filter((n) => n.positionMilitaryPay && typeof n.positionMilitaryPay.amount === "number" && unique(n));
  const militaryKind = (n) => (n.positionMilitaryPay.identification && n.positionMilitaryPay.identification.kind) || "";
  const militaryByGrade = militaryNodes.find((n) => militaryKind(n) === "grade_fixed_by_statute");
  const militaryByFootnote = militaryNodes.find((n) => militaryKind(n) === "named_in_footnote");
  if (!allNodes.some((n) => n.positionMilitaryPay)) {
    measurements.militaryPay = "skipped: no node in the served graph carries positionMilitaryPay (regenerate the graph to land it)";
  } else {
    check("some position is priced from Schedule 8 by a grade a statute fixes", Boolean(militaryByGrade), "none");
    check("some position is priced from Schedule 8's own footnote naming it", Boolean(militaryByFootnote), "none");
    for (const [route, node] of [["grade", militaryByGrade], ["footnote", militaryByFootnote]]) {
      if (!node) continue;
      const block = node.positionMilitaryPay;
      await openByName(node.name);
      const head = await text("#info-stats .info-cost-label");
      const amount = await text("#info-stats .info-cost-amount");
      const stats = await text("#info-stats");
      const military = await text("#info-military-pay");
      check(`a military rate is the headline figure (${route} route)`, amount.includes(block.rateText), amount);
      check(`the headline names military basic pay, not COST (${route} route)`, /MILITARY BASIC PAY/.test(head) && !/COST/.test(head), head);
      check(`the badge says twelve months of monthly basic pay stand in for the cost (${route} route)`, /twelve months|monthly basic pay/i.test(stats), stats.slice(0, 400));
      check(`the military block prints the monthly figure as the schedule does (${route} route)`, military.includes(block.monthly.text), military);
      check(`the military block says the annual figure is arithmetic no document prints (${route} route)`, /twelve times that, arithmetic this project performed and no document prints/.test(military), military);
      check(`the military block says a rate of pay is not the unit's cost (${route} route)`, /not this unit's cost/.test(military), military);
      check(`the military block says it is never a verification the post exists (${route} route)`, /never a verification that the post exists/.test(military), military);
      if (route === "grade") {
        // The officer footnote's Level II ceiling ($18,899.90) differs from
        // the O-10 row ($18,999.90) by $100; the panel prints the discrepancy
        // rather than reconciling it, so both figures must be on screen.
        check("the grade route prints the footnote's $18,899.90 ceiling beside the row's figure", military.includes("$18,899.90") && military.includes(block.monthly.text), military);
        check("the grade route names the statute fixing the grade", Boolean(block.statute) && military.includes(block.statute), military);
      } else {
        check("the footnote route quotes the footnote naming the post", Boolean(block.footnote && block.footnote.text) && military.includes(block.footnote.text), military);
      }
    }
    measurements.militaryPay = `${militaryNodes.length} nodes carry positionMilitaryPay; checked ${[militaryByGrade, militaryByFootnote].filter(Boolean).map((n) => n.id).join(", ")}`;
  }

  // A post of one of DOE's sixteen contractor-operated laboratories
  // (employment_status.py, since 2026-10-07): the headline reads "Not
  // federally paid" under PAY, the panel prints the sentence naming the
  // laboratory and the NETL page, and the qualifier saying what no document
  // here establishes. NETL's own posts are federal and must not show it.
  // Skipped with a note when the served graph carries no such block.
  const employerNodes = allNodes.filter((n) => n.positionEmployer && n.positionEmployer.federallyPaid === false);
  if (!employerNodes.length) {
    measurements.employer = "skipped: no node in the served graph carries positionEmployer (regenerate the graph to land it)";
  } else {
    const employerNode = employerNodes.find((n) => unique(n));
    check("a contractor-laboratory post with a unique name is in the served graph", Boolean(employerNode), employerNodes.length);
    if (employerNode) {
      await openByName(employerNode.name);
      const stats = await text("#info-stats");
      const head = await text("#info-stats .info-cost-label");
      const amount = await text("#info-stats .info-cost-amount");
      const employerText = await text("#info-employer");
      const lab = employerNode.positionEmployer.laboratoryName;
      check("a contractor-laboratory post's headline reads Not on a federal pay schedule", /Not on a federal pay schedule/.test(amount) && !/Not available/.test(amount), amount);
      check("the headline is headed PAY, not COST", /^PAY/.test(head) && !/COST/.test(head), head);
      check(
        "the panel says the laboratory is one of the 16 DOE laboratories a contractor operates, citing the NETL page",
        employerText.includes(`Not on a federal pay schedule: ${lab} is one of the 16 DOE laboratories operated by a contractor (DOE, NETL page, May 22, 2023).`),
        employerText,
      );
      check("the panel says what no document here establishes", /No document here names who holds this post/.test(employerText) && /the money is DOE's, through the contract/.test(employerText), employerText);
      check("the employer sentence sits in the cost block", stats.includes("Not on a federal pay schedule"), stats.slice(0, 600));
      check(
        "the panel prints the regulation's own words, with its section",
        employerText.includes("§970.3102-370 \"The contracts are totally financed by DOE advance payments\""),
        employerText,
      );
      measurements.employer = { node: employerNode.id, posts: employerNodes.length };
    }
    const netlPost = allNodes.find((n) => n.name === "Laboratory Director, National Energy Technology Laboratory");
    if (netlPost) {
      check("NETL's posts carry no employer block in the served graph", !netlPost.positionEmployer, netlPost.id);
      await openByName(netlPost.name);
      const netlStats = await text("#info-stats");
      check("NETL's Laboratory Director is not called not federally paid", !/Not federally paid|Not on a federal pay schedule/.test(netlStats), netlStats.slice(0, 400));
    }
  }

  // A unit the statement prints lines beneath and totals nowhere: the panel
  // reads MEASURED over the exact sum, prints the pipeline's own sentence
  // saying the figure is that sum and never a line the Treasury prints, and
  // lists every line by printed name and amount. Picked from the served graph
  // (the Veterans Health Administration on the 2026-08-31 statement, but
  // whichever node carries the stamp); the field lands only when the graph is
  // regenerated from a statement, so with NO such node the check is skipped
  // with a note under `measurements` rather than failing on absent data.
  const headerSumNodes = allNodes.filter((n) => n.treasury_header_sum === true);
  const headerSumNode = headerSumNodes.find((n) => unique(n));
  if (!headerSumNodes.length) {
    measurements.treasuryHeaderSum = "skipped: no node in the served graph carries treasury_header_sum (regenerate the graph from a statement to land it)";
  } else {
    check("a header-sum unit with a unique name is in the served graph", Boolean(headerSumNode), headerSumNodes.map((n) => n.id).join(", "));
    if (headerSumNode) {
      await openByName(headerSumNode.name);
      const stats = await text("#info-stats");
      check("a header-sum unit reads MEASURED", /\bMEASURED\b/.test(stats), stats);
      check("a header-sum unit shows the exact sum of the statement's lines", stats.includes(exactDollars(headerSumNode.resolved_total_amount)), stats);
      check(
        "a header-sum unit prints the pipeline's own sentence",
        stats.includes(String(headerSumNode.treasury_header_sum_note)) && /prints no total line for this unit/.test(stats),
        stats,
      );
      check("a header-sum unit is never called a line the Treasury reports for it", !/reported for this unit in the Monthly Treasury Statement/.test(stats), stats);
      check("a header-sum unit is not called an estimate", !/\bESTIMATE\b|CAPPED/.test(stats), stats);
      const lineCount = await page.locator("#info-cost-components li").count();
      check(
        "a header-sum unit lists every line the statement prints beneath its header",
        lineCount === headerSumNode.treasury_component_rows.length,
        `${lineCount} listed, ${headerSumNode.treasury_component_rows.length} in the served graph`,
      );
      const listed = await text("#info-cost-components");
      for (const component of headerSumNode.treasury_component_rows) {
        check(
          `the listed lines carry "${component.name}" with its exact amount`,
          listed.includes(String(component.name)) && listed.includes(exactDollars(component.amount)),
          listed,
        );
      }
    }
    measurements.treasuryHeaderSum = `${headerSumNodes.length} nodes carry treasury_header_sum; checked ${headerSumNode ? headerSumNode.id : "none"}`;
  }

  // A printed line that is also one of another node's header-sum lines,
  // applied to a unit that node does not contain (the Office of Community
  // Oriented Policing Services, whose line the statement prints beneath the
  // Office of Justice Programs' header): the panel reads MEASURED over the
  // exact line and prints the pipeline's own sentence saying the money is
  // already inside that node's figure and kept out of the parent's
  // arithmetic. Picked from the served graph; skipped with a note when no
  // node carries the stamp.
  const countedNodes = allNodes.filter(
    (n) => String(n.treasury_counted_in_header_sum || "").trim() && String(n.treasury_counted_in_header_sum_note || "").trim(),
  );
  const countedNode = countedNodes.find((n) => unique(n));
  if (!countedNodes.length) {
    measurements.treasuryCountedInHeaderSum = "skipped: no node in the served graph carries treasury_counted_in_header_sum (regenerate the graph from a statement to land it)";
  } else {
    check("a line counted in a header sum, on a node with a unique name, is in the served graph", Boolean(countedNode), countedNodes.map((n) => n.id).join(", "));
    if (countedNode) {
      await openByName(countedNode.name);
      const stats = await text("#info-stats");
      check("a line counted in a header sum reads MEASURED", /\bMEASURED\b/.test(stats), stats);
      check("a line counted in a header sum shows the exact line", stats.includes(exactDollars(countedNode.resolved_total_amount)), stats);
      check(
        "a line counted in a header sum prints the pipeline's own sentence",
        stats.includes(String(countedNode.treasury_counted_in_header_sum_note)) && /never counted twice/.test(stats),
        stats,
      );
      check("a line counted in a header sum is not called an estimate", !/\bESTIMATE\b|CAPPED/.test(stats), stats);
    }
    measurements.treasuryCountedInHeaderSum = `${countedNodes.length} nodes carry treasury_counted_in_header_sum; checked ${countedNode ? countedNode.id : "none"}`;
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
  // Not one headed by a sourced figure of another kind (checked on its own above).
  const poolNegative = allNodes.find((n) => n.cost_validation === "treasury_pool_negative" && !sourcedKindOf(n));
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
  // Never the root: it has no parent, so its placement line says it is the
  // root rather than naming one of the three unevidenced states.
  const unplacedNode = allNodes.find((n) =>
    n !== graphJson
    && nameCount.get(n.name) === 1 && n.placementVerified !== true
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
    // The panel renders after the selection's fly-in; on a slow renderer
    // 800ms was not always enough and this check once failed on an empty
    // line (2026-09-30). Wait for the line to carry text, up to five seconds.
    const provenanceWaitStart = Date.now();
    await page.waitForFunction(
      () => (document.getElementById("info-desc-provenance")?.textContent || "").trim().length > 0,
      null, { timeout: 15000 },
    ).catch(() => {});
    measurements.sourcedDescriptionWait = `${Date.now() - provenanceWaitStart}ms for ${generated.id}; panel shows ${JSON.stringify(await text("#info-name"))} / ${JSON.stringify(await text("#info-type"))}; ${JSON.stringify(await page.evaluate(() => ({ camera: window.__bureaucracy_camera__?.(), prefs: window.localStorage.getItem("bureaucracy-view-prefs-v1"), depth: document.querySelector(".depth-btn.active")?.dataset.depth })))}`;
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
  // The Government Manual's own description, printed BESIDE the curated
  // prose. Picked from the served graph, because whether any node carries one
  // depends on the last build having applied govman_evidence.json: until the
  // next regenerate none is published, and an assertion that named a node
  // would fail on the absence of data rather than on a defect. So the check
  // is conditional and says so — and when a block IS published, three things
  // must hold at once: the heading names the Manual and its edition, the text
  // on screen is the block's text verbatim, and the curated prose above it is
  // still labelled uncited, since the official text sits beside it and never
  // replaces it.
  const official = allNodes.find((n) => n.descriptionOfficial && n.descriptionOfficial.text
    && !n.descriptionSource && n.desc && nameCount.get(n.name) === 1);
  if (official) {
    await openByName(official.name);
    const officialBlock = await text("#info-desc-official");
    check("an official description names the Manual and its edition",
      officialBlock.includes(`OFFICIAL DESCRIPTION — U.S. Government Manual, ${official.descriptionOfficial.edition}`), officialBlock.slice(0, 200));
    check("an official description shows the Manual's text verbatim",
      officialBlock.includes(official.descriptionOfficial.text), officialBlock.slice(0, 300));
    check("an official description says which element it was read from",
      official.descriptionOfficial.kind === "mission_statement"
        ? /the Manual's own mission statement/.test(officialBlock)
        : /the opening (of the Manual's entry|paragraph of the Manual's entry)/.test(officialBlock), officialBlock.slice(0, 300));
    const curatedNote = await text("#info-desc-provenance");
    check("the curated prose beside an official description is still labelled uncited",
      /uncited prose from the base graph/.test(curatedNote), curatedNote);
    const curatedText = await text("#info-desc");
    check("the curated prose beside an official description is the curated text, not the Manual's",
      curatedText === String(official.desc).trim(), curatedText.slice(0, 200));
  } else {
    // Asserted conditionally: no published node carries one yet. The block
    // element must still exist in the page's script so the assertion above is
    // live the moment a build publishes a block, not silently absent.
    const rendererPresent = fs.readFileSync(path.join(ROOT, "js", "ui.js"), "utf8").includes("info-desc-official");
    check("no official description is published yet, and the panel is ready to show one (conditional)", rendererPresent,
      "js/ui.js does not render #info-desc-official");
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
  // The organisations headed by a sourced figure of another kind are a group
  // of their own in both the line and the card, never counted as measured.
  const expectedSourced = allNodes.filter((n) => n !== graphJson && sourcedKindOf(n)).length;
  const lineSourced = /([\d,]+) organisations without a measured cost headed instead by a sourced figure of another kind/.exec(provenanceLine);
  check("the provenance line counts the sourced-figure headlines as their own group",
    Boolean(lineSourced) && Number(lineSourced[1].replace(/,/g, "")) === expectedSourced,
    `${lineSourced ? lineSourced[1] : "absent"} shown, ${expectedSourced} in the served graph`);
  const guideSourced = /([\d,]+) organisations without a measured cost show, at the top of their panel, a figure of another kind/.exec(guideText.replace(/\s+/g, " "));
  check("the guide counts the same sourced-figure headlines",
    Boolean(guideSourced) && Number(guideSourced[1].replace(/,/g, "")) === expectedSourced,
    `${guideSourced ? guideSourced[1] : "absent"} in the card, ${expectedSourced} in the served graph`);
  measurements.sourcedFigureHeadlineTotal = expectedSourced;
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
  // A whole-name or scoped row: a reviewed identification prints a different
  // sentence (three documents), and is checked on its own below.
  const withSchedulePay = allNodes.find((n) => n.positionSchedulePay && typeof n.positionSchedulePay.amount === "number"
    && !n.positionSchedulePay.identification);
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

  // ---- Presentation and navigation, 2026-09-21. --------------------------
  // Each of these was a verified defect: read what the page does, not what
  // the code says it does.

  // The legend is fixed bottom-right; the open panel spans the viewport's
  // height at 1400x900, so the key was drawn inside the panel. Measured with
  // getBoundingClientRect, with the panel open, which it is by now.
  const boxes = await page.evaluate(() => {
    const rect = (id) => {
      const el = document.getElementById(id);
      const b = el.getBoundingClientRect();
      return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, open: el.classList.contains("open") };
    };
    return { legend: rect("legend"), panel: rect("info-panel"), depth: rect("depth-ctrl"), hint: rect("controls-hint"), crumbs: rect("breadcrumb"), switcher: rect("view-switcher"), stats: rect("stats"), search: rect("search-wrap") };
  });
  const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  check("the info panel is open for the overlap check", boxes.panel.open, JSON.stringify(boxes.panel));
  check("the legend never sits under the open info panel", !overlaps(boxes.legend, boxes.panel), JSON.stringify(boxes));
  check("the legend does not sit under the depth control either", !overlaps(boxes.legend, boxes.depth), JSON.stringify(boxes));
  // Moved left of the panel, the legend shared a row with the controls hint.
  check("the legend does not collide with the controls hint", !overlaps(boxes.legend, boxes.hint), JSON.stringify(boxes));
  check("the legend does not collide with the breadcrumb", !overlaps(boxes.legend, boxes.crumbs), JSON.stringify(boxes));
  // The Directory / 3D-universe switcher shared the top-right corner with the
  // panel's title; it moves left of the open panel and the stats block sits
  // beneath it.
  check("the view switcher never sits over the open info panel", !overlaps(boxes.switcher, boxes.panel), JSON.stringify(boxes));
  check("the view switcher does not cover the stats block", !overlaps(boxes.switcher, boxes.stats), JSON.stringify(boxes));
  check("the view switcher does not cover the search box", !overlaps(boxes.switcher, boxes.search), JSON.stringify(boxes));

  // The counter names both numbers: loaded is not drawn, and "5,402 / 5,402
  // nodes rendered" was printed while the Agency tier drew depth 3.
  check("the counter says loaded and drawn separately", /nodes loaded · [\d,]+ drawn/.test(await text("#node-counter")), await text("#node-counter"));

  // The root has no parent, so "no evidence recorded for where this sits"
  // was a gap that does not exist.
  // Opened by name rather than through the breadcrumb: with the candidate
  // toggle on, the selection may be a candidate, which has no ancestors and
  // a one-crumb trail.
  await openByName(graphJson.name);
  const rootName = await text("#info-name");
  check("the root opens from the search", rootName === graphJson.name, rootName);
  const rootPlacement = await text("#verification-placement");
  check("the root's placement line says it is the root", /root of the graph/.test(rootPlacement), rootPlacement);
  check("the root is not told no placement evidence was recorded", !/no evidence recorded/.test(rootPlacement), rootPlacement);
  // The root's measured figure is exact and, above a billion, also readable.
  const rootStats = await text("#info-stats");
  check("the root's exact figure is the primary reading", rootStats.includes(exactDollars(graphJson.resolved_total_amount)), rootStats.slice(0, 200));
  check("a measured figure above $1B carries a compact reading", /\$\d+(\.\d+)? (billion|trillion), to three figures/.test(rootStats), rootStats.slice(0, 200));

  // Only a node holding an apportioned share is told the estimates box would
  // reveal one. A post and a unit beneath a negative Treasury pool have no
  // estimate, and were told to tick a box that reveals nothing for them.
  await setEstimatesShown(false);
  const plainPost = allNodes.find((n) => n.cost_validation === "post_is_not_a_budget_unit" && !n.positionListing && unique(n));
  check("some post has no figure and no pay listing", Boolean(plainPost), "none");
  if (plainPost) {
    await openByName(plainPost.name);
    const postStats = await text("#info-stats");
    check("a post is never told to tick the estimates box", !/Tick/.test(postStats), postStats.slice(0, 500));
    check("a post says it is a post, with nothing to reveal", /This is a post/.test(postStats) && /no estimate to reveal/.test(postStats), postStats.slice(0, 500));
  }
  if (paid) {
    await openByName(paid.name);
    const paidStats = await text("#info-stats");
    check("a paid post is never told to tick the estimates box", !/Tick/.test(paidStats), paidStats.slice(0, 500));
    check("a paid post still heads its figure as pay", /REPORTED RATE OF BASIC PAY/.test(paidStats), paidStats.slice(0, 300));
  }
  if (poolNegative && unique(poolNegative)) {
    await openByName(poolNegative.name);
    const poolStats = await text("#info-stats");
    check("a node beneath a negative pool is never told to tick the estimates box", !/Tick/.test(poolStats), poolStats.slice(0, 600));
    check("a node beneath a negative pool explains itself in the default view", /Nothing remains to apportion/.test(poolStats), poolStats.slice(0, 600));
  }
  if (allocatedNode) {
    await openByName(allocatedNode.name);
    const stillWithheld = await text("#info-stats");
    check("an apportioned share is still told the box reveals it", /Tick/.test(stillWithheld), stillWithheld.slice(0, 500));
    await setEstimatesShown(true);
    const shownEstimate = await text("#info-stats");
    check("an estimate keeps its own rounded form and gets no compact line", /≈\s*\$/.test(shownEstimate) && !/to three figures/.test(shownEstimate), shownEstimate.slice(0, 300));
    await setEstimatesShown(false);
  }

  // A node whose queued page went unread, and which carries no source and no
  // date — 924 of the 931 such nodes. The unread sentence lived only in the
  // branch a never-checked node cannot reach, so the panel said "hand-compiled
  // base graph" while the guide counted a page that could not be read.
  const unreadNeverChecked = allNodes.find((n) =>
    n.verificationUnread && typeof n.verificationUnread === "object" && !n.verificationMethod
    && !(n.sourceUrls || []).length && !n.lastVerified && unique(n));
  check("some never-checked node has a queued page that went unread", Boolean(unreadNeverChecked), "none");
  if (unreadNeverChecked) {
    await openByName(unreadNeverChecked.name);
    const unreadPanel = await text("#info-panel");
    check("a never-checked node with an unread page says the page went unread", /Not verified: .*(could not be read|nothing could be read|refuses this crawler|answered 404|could not be reached|server error)/.test(unreadPanel), unreadPanel.slice(-700));
    check("an unread page is described as a fact about the page or host, not the unit", !/Not yet verified/.test(unreadPanel), unreadPanel.slice(0, 700));
  }
  // An organisation for which no page was ever queued, and the record says
  // why — the verifier's name floor or the nomination ledger's decline. The
  // panel prints the reason where it said "hand-compiled base graph", and
  // never calls it a finding about the unit.
  const noDocumentNode = allNodes.find((n) =>
    n.verificationNoDocument && typeof n.verificationNoDocument === "object" && !n.verificationMethod
    && !n.verificationUnread && !n.verificationFailure && !(n.sourceUrls || []).length && unique(n));
  check("some organisation carries a recorded reason no document can be read", Boolean(noDocumentNode), "none");
  if (noDocumentNode) {
    await openByName(noDocumentNode.name);
    const noDocPanel = await text("#info-panel");
    check("a unit with a recorded reason says why no page could be named", /Not verified: .*(count label|one common word|graph's own grouping|no page of its own|could name no official page|not on a \.gov or \.mil host|refuses this crawler|does not carry this graph's name)/.test(noDocPanel), noDocPanel.slice(-900));
    check("a recorded reason is not described as a page that was never looked for", !/No source URL has been attached to it yet/.test(noDocPanel), noDocPanel.slice(0, 700));
    measurements.noDocumentKind = noDocumentNode.verificationNoDocument.kind;
  }
  // OPM's PLUM archive as the method that confirmed a post and placed it:
  // 125 and 129 nodes, which the wording maps did not know, so the panel
  // fell to "Last checked: <date>" and "no evidence recorded".
  const plumMethod = allNodes.find((n) => n.verificationMethod === "listed_in_opm_plum_archive"
    && n.placementMethod === "listed_under_organization_in_opm_plum_archive" && unique(n));
  check("some post is confirmed and placed by the PLUM archive", Boolean(plumMethod), "none");
  if (plumMethod) {
    await openByName(plumMethod.name);
    const plumPanel = await text("#info-panel");
    check("a PLUM-confirmed post names the archive as its method", /OPM's PLUM archive, the previous administration's reported positions, lists a post of this title/.test(plumPanel), plumPanel.slice(0, 900));
    check("a PLUM-confirmed post does not fall back to a bare date", !/Last checked:/.test(plumPanel), plumPanel.slice(0, 900));
    const plumPlacement = await text("#verification-placement");
    check("a PLUM placement names the archive", /Placement: OPM's PLUM archive, the previous administration's reported positions, files a post of this title under its organisation here/.test(plumPlacement), plumPlacement);
    check("a PLUM placement is not reported as no evidence", !/no evidence recorded/.test(plumPlacement), plumPlacement);
  }

  // Every child in the data must be reachable from the panel. The White
  // House Office carries 249 children; the list showed eight and a dead
  // "+ 241 more".
  const widest = allNodes.filter((n) => unique(n)).sort((a, b) => (b.children || []).length - (a.children || []).length)[0];
  if (widest && (widest.children || []).length > 8) {
    await openByName(widest.name);
    const moreRow = page.locator("#info-children-more");
    check("a long children list offers to show the rest", (await moreRow.count()) === 1, `${await moreRow.count()} such rows`);
    if (await moreRow.count()) {
      const moreAttrs = await moreRow.evaluate((el) => ({ role: el.getAttribute("role"), tabindex: el.getAttribute("tabindex") }));
      check("the show-all row is keyboard-reachable", moreAttrs.role === "button" && moreAttrs.tabindex === "0", JSON.stringify(moreAttrs));
      await moreRow.click();
      await page.waitForTimeout(300);
      const rowCount = await page.locator("#info-children-list > *").count();
      check("showing all lists every child in the data", rowCount === widest.children.length, `${rowCount} rows for ${widest.children.length} children`);
      const last = widest.children[widest.children.length - 1];
      await page.locator("#info-children-list > *").last().click();
      await page.waitForTimeout(2500);
      const opened = await text("#info-name");
      check("the last child in the list opens when clicked", opened === last.name, `${opened} opened, wanted ${last.name}`);
    }
  }

  // A click selects; it never opens anything, and what a reader opened stays
  // laid out (2026-10-21). Clicking the Executive Branch only to read its
  // panel used to load 123 nodes under 15 parents through the auto-expansion
  // that followed every selection, and clicking one department of an
  // expanded Cabinet folded the other fourteen into group rings (22 drawn ->
  // 7). Both are measured here with real mouse clicks on a fresh load.
  {
    await page.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => window.__bureaucracy_ui_loaded__ && (() => { const el = document.getElementById("loading"); return !el || getComputedStyle(el).opacity === "0"; })(),
      null,
      { timeout: 90000 },
    );
    await page.evaluate(() => document.getElementById("btn-reading-guide-close")?.click());
    const drain = async () => {
      await page.waitForTimeout(1500);
      await page.waitForFunction(() => (window.__bureaucracy_pending_expansions__?.() ?? 0) === 0, null, { timeout: 90000 });
      await page.waitForTimeout(5000);
    };
    await drain();
    const loadedIds = () => page.evaluate(() => window.__bureaucracy_loaded_node_ids__());
    const clickById = async (id) => {
      const where = await page.evaluate((nodeId) => window.__bureaucracy_node_screen__(nodeId), id);
      if (!where || !where.drawn) return false;
      await page.mouse.click(where.screen.x, where.screen.y);
      await drain();
      return true;
    };
    const execBranch = allNodes.find((n) => n.__depth === 1 && n.name === "Executive Branch");
    const cabinet = execBranch && (execBranch.children || []).find((n) => /^The Cabinet/.test(n.name));
    const before = new Set(await loadedIds());
    const clickedExec = execBranch && (await clickById(execBranch.id));
    const opened = (await loadedIds()).filter((id) => !before.has(id));
    check("a click on a node selects it", clickedExec && (await text("#info-name")) === execBranch.name, `panel reads ${await text("#info-name")}`);
    check("a click opens nothing", opened.length === 0, `${opened.length} nodes loaded by a click, e.g. ${opened.slice(0, 5).join(", ")}`);
    measurements.nodesLoadedByAClick = opened.length;
    if (clickedExec && cabinet) {
      await page.click("#btn-expand");
      await drain();
      const clickedCabinet = await clickById(cabinet.id);
      await page.click("#btn-expand");
      await drain();
      const departments = (cabinet.children || []).map((n) => n.id);
      const foldedNow = () => page.evaluate((ids) => ids.filter((id) => { const w = window.__bureaucracy_node_screen__(id); return w && !w.drawn; }).length, departments);
      const foldedBefore = await foldedNow();
      const first = departments[0];
      const clickedDept = clickedCabinet && (await clickById(first));
      const foldedAfter = await foldedNow();
      measurements.cabinetDepartmentsHiddenAfterClickingOne = { before: foldedBefore, after: foldedAfter, of: departments.length };
      check(
        "clicking one department of an opened Cabinet keeps the others laid out",
        clickedDept && foldedAfter <= foldedBefore + 1,
        `${foldedAfter} of ${departments.length} departments not drawn after the click, ${foldedBefore} before`,
      );
    } else {
      check("the click test found the Executive Branch and the Cabinet", false, "missing from the served graph or not drawn at boot");
    }
  }

  // "Expand All Below" is scoped to the selection's subtree: on the
  // Department of the Interior it used to open all 5,402 nodes.
  const interior = byId("exec-dept-doi");
  if (interior) {
    const subtreeSize = subtreeSizeOf(interior);
    // On a fresh load, so the count is not the residue of everything opened
    // above (nothing unloads), and with the four-second auto-expansion window
    // that follows a selection left to close before the button is pressed.
    await page.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => window.__bureaucracy_ui_loaded__ && (() => { const el = document.getElementById("loading"); return !el || getComputedStyle(el).opacity === "0"; })(),
      null,
      { timeout: 90000 },
    );
    await page.waitForTimeout(1500);
    await openByName(interior.name);
    await page.waitForTimeout(4500);
    const loadedNow = async () => Number((/^([\d,]+) \//.exec(await text("#node-counter")) || [])[1]?.replace(/,/g, "") || 0);
    // The boot expansion and the auto-expansion that follows a selection
    // both run in batches with pauses between them, and on a slow renderer
    // the counter is still climbing at 4.5 s (63 loaded at the selection,
    // 904 a few seconds later, 999 at rest); a `before` read mid-climb
    // counts the rest of it as the button's doing — 161 added against a
    // 93-node subtree, measured on both HEAD and the working tree on
    // 2026-10-14. Read it once the count has held still for three seconds.
    // (A still counter is not enough either: with 186 loaded the queue
    // held still for three seconds and the button then finished the boot
    // expansion's own queue, 879 nodes. So wait for the queue to drain.)
    const pending = () => page.evaluate(() => window.__bureaucracy_pending_expansions__?.() ?? 0);
    const waitStart = Date.now();
    while (Date.now() - waitStart < 120000 && (await pending()) > 0) {
      await page.waitForTimeout(1000);
    }
    let before = await loadedNow();
    let held = 0;
    for (let i = 0; i < 60 && held < 3; i += 1) {
      await page.waitForTimeout(1000);
      const next = await loadedNow();
      held = next === before ? held + 1 : 0;
      before = next;
    }
    const loadedBefore = new Set(await page.evaluate(() => window.__bureaucracy_loaded_node_ids__?.() || []));
    measurements.interiorLoadedBeforeExpandAll = `${before} loaded, ${await pending()} expansions still queued, after ${Math.round((Date.now() - waitStart) / 1000)}s`;
    await page.locator("#btn-expand-all").click();
    await page.waitForFunction(() => document.getElementById("btn-expand-all").textContent === "Expand All Below", null, { timeout: 60000 });
    await page.waitForTimeout(500);
    const after = await loadedNow();
    check("Expand All Below loads the selection's whole subtree", after >= subtreeSize, `${after} loaded, subtree is ${subtreeSize}`);
    // Exact rather than counted: the ids the button added, against the ids
    // in the selection's subtree. A count hides which side a stray node is
    // on; on 2026-10-14 the counter's steady state after the selection was
    // 904 on one run and 999 on another, and the difference read as 68
    // nodes the button had opened outside the subtree.
    const subtreeIds = new Set();
    const collectIds = (item) => { subtreeIds.add(String(item.id)); for (const child of item.children || []) collectIds(child); };
    collectIds(interior);
    const loadedAfter = await page.evaluate(() => window.__bureaucracy_loaded_node_ids__?.() || []);
    const strays = loadedAfter.filter((id) => !subtreeIds.has(id) && !loadedBefore.has(id));
    measurements.interiorExpandAllStrays = strays.slice(0, 12);
    check("Expand All Below opens no more than the selection's subtree", strays.length === 0, `${strays.length} nodes added outside the subtree (${after - before} added, subtree is ${subtreeSize}): ${strays.slice(0, 6).join(", ")}`);
    check("Expand All Below does not open the rest of the graph", after < allNodes.length * 0.6, `${after} loaded of ${allNodes.length}`);
  }

  // A deep link to a node outside the initial load. loadData selected the
  // root and the selection wrote the root's id over the hash before it was
  // read, so every shared link landed on the Constitution.
  const deepLinked = allNodes.find((n) => n.id === "exec-dept-doi-chief-of-staff") || allNodes.find((n) => n.cost_validation === "post_is_not_a_budget_unit");
  const deepest = allNodes.reduce((best, n) => ((n.__depth || 0) > (best.__depth || 0) ? n : best), allNodes[0]);
  for (const target of [deepLinked, deepest].filter(Boolean)) {
    await page.goto(`http://127.0.0.1:${PORT}/index.html#node=${encodeURIComponent(target.id)}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(
      () => window.__bureaucracy_ui_loaded__ && (() => { const el = document.getElementById("loading"); return !el || getComputedStyle(el).opacity === "0"; })(),
      null,
      { timeout: 90000 },
    );
    await page.waitForTimeout(2500);
    const linkedName = await text("#info-name");
    check(`a deep link to ${target.id} opens that node`, linkedName === target.name, `${linkedName} opened`);
    const linkedHash = await page.evaluate(() => window.location.hash);
    check("the deep link's hash survives the boot selection", linkedHash === `#node=${encodeURIComponent(target.id)}`, linkedHash);
    const crumbs = await page.locator("#bc-items .bc-item").count();
    check("the deep-linked node's ancestor path is expanded", crumbs === (target.__depth || 0) + 1, `${crumbs} crumbs for depth ${target.__depth}`);
    // Flown to: the camera has come close enough that the LOD tier draws the
    // node's own depth, so its ancestors are on screen and not just the node.
    await page.waitForFunction(
      (depth) => {
        const m = /depth (\d+)/.exec(document.getElementById("stats-depth").textContent || "");
        return m && Number(m[1]) >= depth;
      },
      target.__depth || 0,
      { timeout: 20000 },
    ).catch(() => {});
    const depthLine = await text("#stats-depth");
    const shownDepth = Number((/depth (\d+)/.exec(depthLine) || [])[1] || 0);
    check(`the camera flies close enough to draw depth ${target.__depth}`, shownDepth >= (target.__depth || 0), depthLine);
  }

  // Expanding a node has to put that node's children on screen. Two rules
  // work together and each one alone makes it worse, so both are measured
  // here on the widest brood in the graph (the White House Office's 249):
  // the camera pulls back to hold the brood, and the brood is exempt from
  // the distance-driven LOD tier that pulling back would otherwise drop it
  // below. Measured 2026-09-22 at 1400x900, by expanding that node and
  // counting how many of ITS OWN child ids are in the drawn set:
  //
  //   before          4 of 249     (a fan of edges and nothing at the end)
  //   camera only    11 of 249     (pulled back past the tier that draws them)
  //   both          235 of 249
  //
  // The bar is 60%, not 90%, and the gap is the screen-tile density cap
  // doing its job: 249 nodes in one frame is more than some tiles will hold,
  // and how many it trims depends on where the camera happens to sit. The
  // same expansion run at the end of this file's sequence rather than alone
  // drew 183. Either is the fix working; 4 is not.
  {
    // The brood's OWN ids in the drawn set, not the drawn total: ancestors,
    // clusters and whatever else the camera happens to hold are not what
    // this is asking about, and counting them made the figure depend on
    // where the earlier checks left the view. The unverified toggle is
    // re-checked first, since a toggle left off would correctly withhold
    // most of this brood and the check would be measuring that instead.
    await page.locator("#verification-toggles input").nth(0).check();
    // ...and the depth filter is returned to "all", since the brood's
    // exemption from the LOD tier is deliberately subordinate to an explicit
    // depth filter: a reader who says "depth 4" is saying how deep to go, and
    // an earlier check in this file leaves one set.
    await page.locator('.depth-btn[data-depth="all"]').click();
    await page.waitForTimeout(400);
    await page.fill("#search-input", "White House Office");
    await page.waitForTimeout(700);
    await page.locator("#search-results .sr-item").first().click({ force: true });
    await page.waitForTimeout(1200);
    await page.click("#btn-expand-all");
    const brood = (allNodes.find((node) => node.id === "exec-eop-who")?.children || []).map((child) => child.id);
    // The SETTLED count, not a snapshot. This used to sample once at six
    // seconds, and on 2026-09-30 that turned out to measure a transient
    // twice over: on a slow renderer the brood was still being admitted at
    // six seconds (48 at two, 163 at six, 239 at twenty), and the 235 the
    // fix was measured at on 2026-09-22 sat inside the density cap's hold
    // (80 frames), after which the cap at the pulled-back tier trimmed the
    // brood to 26 of 249. So: wait for the expansion to finish (the button
    // reads "Expand All Below" again), then thirty seconds for any hold to
    // expire on a renderer of any speed, then poll until three consecutive
    // samples agree. Every sample is printed with the result.
    const countDrawn = async () => {
      const ids = new Set(await page.evaluate(() => window.__bureaucracy_drawn_node_ids__?.() || []));
      return brood.filter((id) => ids.has(id)).length;
    };
    const t0 = Date.now();
    const samples = [];
    for (let i = 0; i < 30; i += 1) {
      await page.waitForTimeout(1000);
      const label = await page.evaluate(() => (document.getElementById("btn-expand-all")?.textContent || "").trim());
      if (label === "Expand All Below") break;
    }
    samples.push(`expansion done +${Date.now() - t0}ms: ${await countDrawn()}`);
    await page.waitForTimeout(30000);
    let broodDrawn = await countDrawn();
    samples.push(`+${Date.now() - t0}ms: ${broodDrawn}`);
    let agreed = 1;
    for (let i = 0; i < 20 && agreed < 3; i += 1) {
      await page.waitForTimeout(2000);
      const next = await countDrawn();
      agreed = next === broodDrawn ? agreed + 1 : 1;
      broodDrawn = next;
      samples.push(`+${Date.now() - t0}ms: ${broodDrawn}`);
    }
    measurements.whiteHouseOfficeBroodDrawn = `${broodDrawn} of ${brood.length}, settled`;
    measurements.whiteHouseOfficeBroodSamples = samples;
    check("the graph still carries the wide brood this check is measured on", brood.length > 200, `${brood.length} children`);
    check("expanding a node draws its children", broodDrawn >= brood.length * 0.6,
      `${broodDrawn} of ${brood.length} children drawn after expanding their parent, once settled`);
    await page.fill("#search-input", "");
    await page.waitForTimeout(300);
  }

  // The lenses (slice 5). Each recolours the picture from one published
  // field; the check reads the verdict the renderer drew a node from and
  // compares it with that field in the served graph, so the picture cannot
  // claim something the data does not say. The examples are picked FROM the
  // data, as above.
  {
    const verdictOf = (id) => page.evaluate((nodeId) => window.__bureaucracy_lens_verdict__?.(nodeId) || null, id);
    const activeLens = () => page.evaluate(() => document.querySelector(".lens-btn.active")?.dataset.lens || null);
    const legendLabel = async () => (await text("#legend-label")).toLowerCase();
    check("the lens control offers the five lenses", (await page.locator(".lens-btn").count()) === 5, `${await page.locator(".lens-btn").count()} buttons`);
    check("Structure is the default lens", (await activeLens()) === "structure", String(await activeLens()));

    const isPost = (n) => /position|\brole\b|office holder/i.test(String(n.type || ""));
    const measuredOrg = allNodes.find((n) => n.cost_status === "official" && !isPost(n) && !n.synthetic && Number(n.resolved_total_amount) > 1e9 && n.__depth > 0);
    const verifiedOrg = allNodes.find((n) => n.verificationStatus === "verified" && (n.sourceUrls || []).length >= 2 && !isPost(n));
    const unsourced = allNodes.find((n) => !n.lastVerified && !(n.sourceUrls || []).length && !n.verificationUnread && !n.verificationNoDocument && !n.synthetic);
    const noDocumentOrg = allNodes.find((n) => !isPost(n) && n.verificationNoDocument && !n.verificationMethod && !n.verificationUnread && !n.verificationFailure);
    const statutoryPost = allNodes.find((n) => isPost(n) && n.positionStatutoryPay && Number(n.positionStatutoryPay.amount) > 0 && !n.representsPosts);
    const unpricedPost = allNodes.find((n) => isPost(n) && !n.positionStatutoryPay && !n.positionSchedulePay && !n.positionTierReferencePay && !n.positionDerivedPay && !n.positionMilitaryPay && !n.positionReportedPay && !n.positionCurrentPay && !n.positionPayRate && !n.positionGradePay && !n.positionTierPay && !n.positionEmployer);
    const estimateOrg = allNodes.find((n) => n.cost_status === "allocated" && !isPost(n) && Number(n.resolved_total_amount) > 0);

    await page.click('.lens-btn[data-lens="evidence"]');
    await page.waitForTimeout(600);
    check("the Evidence button takes the lens", (await activeLens()) === "evidence", String(await activeLens()));
    check("the key swaps to the Evidence key", (await legendLabel()) === "evidence", await legendLabel());
    if (verifiedOrg) {
      const v = await verdictOf(verifiedOrg.id);
      check("under Evidence a verified unit draws as verified", v && v.key === "verified" && v.color === "#4FBF8C", JSON.stringify(v));
    }
    if (noDocumentOrg) {
      const v = await verdictOf(noDocumentOrg.id);
      check("under Evidence a unit with a recorded reason draws as no page could be named, never as unsourced", v && v.key === "noDocument" && /no page could be named/.test(v.text), JSON.stringify(v));
    }
    if (unsourced) {
      const v = await verdictOf(unsourced.id);
      check("under Evidence an unsourced node says no source recorded", v && v.key === "unsourced" && /no source recorded/.test(v.text), JSON.stringify(v));
    }

    await page.keyboard.press("Digit4");
    await page.waitForTimeout(600);
    check("key 4 takes the Pay lens", (await activeLens()) === "pay", String(await activeLens()));
    if (statutoryPost) {
      const v = await verdictOf(statutoryPost.id);
      const amount = Number(statutoryPost.positionStatutoryPay.amount);
      check("under Pay a statutory rate draws as an office-rate claim with its figure", v && v.key === "office" && v.amount === amount && /statute/.test(v.text), JSON.stringify(v));
    }
    if (unpricedPost) {
      const v = await verdictOf(unpricedPost.id);
      check("under Pay an unpriced post says no held pay document prints the title, or that one prints it under a filing no rule ties to the post",
        v && v.key === "unpriced" && (unpricedPost.payNoDocument
          ? (unpricedPost.payNoDocument.namedIn && unpricedPost.payNoDocument.namedIn.length ? /a held document prints the title/.test(v.text) : /no held pay document prints the title \(\d+ checked\)/.test(v.text))
          : /no document names the title/.test(v.text)), JSON.stringify(v));
    }
    if (measuredOrg) {
      const v = await verdictOf(measuredOrg.id);
      check("under Pay a unit takes no salary", v && v.key === "unit" && v.scale === 1, JSON.stringify(v));
    }

    await page.keyboard.press("Digit2");
    await page.waitForTimeout(600);
    check("key 2 takes the Money lens", (await activeLens()) === "money", String(await activeLens()));
    const estimatesOn = await page.evaluate(() => {
      const box = [...document.querySelectorAll("#verification-toggles input")].find((i) => /estimated/i.test(i.parentElement.textContent));
      return box ? box.checked : null;
    });
    if (measuredOrg) {
      const v = await verdictOf(measuredOrg.id);
      const amount = Number(measuredOrg.resolved_total_amount);
      check("under Money a measured unit draws from its measured figure, larger than a bare node", v && v.key === "measured" && v.amount === amount && v.scale > 1, JSON.stringify(v));
      measurements.moneyLensMeasuredExample = `${measuredOrg.name}: scale ${v && v.scale}`;
    }
    if (estimateOrg && estimatesOn === false) {
      const v = await verdictOf(estimateOrg.id);
      check("under Money an estimate stays withheld until the estimates box is ticked", v && v.key === "none" && v.scale < 1 && /withheld/.test(v.text), JSON.stringify(v));
    }
    if (unpricedPost) {
      const v = await verdictOf(unpricedPost.id);
      check("under Money a post has no figure and never a size", v && v.key === "none" && v.scale < 1, JSON.stringify(v));
    }
    // Whole (key 5): every node drawn at once, the camera pulled back to
    // hold all of it, and a branch's caption carrying this graph's own
    // counts beneath it and its measured figure. Measured on the served
    // graph, and the drawn count read once the camera has settled, since on
    // a software renderer the pull-back takes most of a minute.
    await page.keyboard.press("Digit5");
    await page.waitForTimeout(500);
    check("key 5 takes the Whole lens", (await activeLens()) === "whole", String(await activeLens()));
    await page.waitForFunction(() => document.getElementById("btn-expand-all")?.textContent === "Expand All Below", null, { timeout: 180000 });
    const wholeStart = Date.now();
    let cam = null;
    while (Date.now() - wholeStart < 180000) {
      cam = await page.evaluate(() => window.__bureaucracy_camera__?.() || null);
      if (cam && cam.targetZoom < 0.3 && Math.abs(cam.zoom - cam.targetZoom) < 0.01) break;
      await page.waitForTimeout(2000);
    }
    await page.waitForTimeout(4000);
    cam = await page.evaluate(() => window.__bureaucracy_camera__?.() || null);
    const wholeLoaded = await page.evaluate(() => (window.__bureaucracy_loaded_node_ids__?.() || []).length);
    measurements.wholeLens = { ...cam, loaded: wholeLoaded, total: allNodes.length, settledAfterMs: Date.now() - wholeStart };
    // At least: the candidate toggle, when on, adds its unreviewed nodes.
    check("Whole loads the entire graph", wholeLoaded >= allNodes.length, `${wholeLoaded} of ${allNodes.length}`);
    // The Whole lens lays the tree out as one globe: every leaf on its
    // branch's crust, the root at the centre, and the crust in relief — the
    // branch with the most leaves at the full radius, the others drawn in by
    // their share. Sampled from the served graph's leaves, branch by branch:
    // within a branch every leaf sits at one radius, and the largest
    // branch's radius is the largest.
    {
      const leafNodes = allNodes.filter((n) => n.__branch && !(n.children || []).length && String(n.lifecycle || "") !== "superseded");
      const leafCountByBranch = new Map();
      for (const leaf of leafNodes) leafCountByBranch.set(leaf.__branch, (leafCountByBranch.get(leaf.__branch) || 0) + 1);
      const sample = leafNodes.filter((_, i) => i % Math.max(1, Math.floor(leafNodes.length / 48)) === 0).slice(0, 48);
      const radiiByBranch = new Map();
      for (const leaf of sample) {
        const at = await page.evaluate((i) => window.__bureaucracy_node_screen__?.(i), leaf.id);
        if (!at) continue;
        if (!radiiByBranch.has(leaf.__branch)) radiiByBranch.set(leaf.__branch, []);
        radiiByBranch.get(leaf.__branch).push(Math.hypot(at.world.x, at.world.y, at.world.z));
      }
      const root = await page.evaluate(() => window.__bureaucracy_node_screen__?.("the-constitution-of-the-united-states"));
      const shells = {};
      let sampled = 0;
      let worstSpread = 0;
      for (const [branch, radii] of radiiByBranch) {
        sampled += radii.length;
        worstSpread = Math.max(worstSpread, Math.max(...radii) - Math.min(...radii));
        shells[branch] = { leaves: leafCountByBranch.get(branch), radius: Math.round(Math.min(...radii)) };
      }
      const ordered = Object.values(shells).sort((a, b) => b.leaves - a.leaves);
      const reliefHolds = ordered.length >= 2 && ordered.every((shell, i) => i === 0 || shell.radius <= ordered[i - 1].radius) && ordered[0].radius > ordered[ordered.length - 1].radius;
      measurements.wholeSphere = { sampled, worstSpread: Math.round(worstSpread * 10) / 10, shells, root: root && root.world };
      check("Whole lays every sampled leaf on its branch's shell", sampled >= 20 && worstSpread < 5, JSON.stringify(measurements.wholeSphere));
      check("Whole's relief follows each branch's leaf count", reliefHolds, JSON.stringify(shells));
      check("Whole puts the Constitution at the sphere's centre", root && Math.hypot(root.world.x, root.world.y, root.world.z) < 1, JSON.stringify(root));
    }
    check("Whole reports its own tier", cam && cam.lodLabel === "Whole Government", JSON.stringify(cam));
    check("Whole pulls the camera back past the ordinary floor", cam && cam.targetZoom < 0.28, JSON.stringify(cam));
    check("Whole draws nearly every node at once", cam && cam.drawn >= allNodes.length * 0.9, `${cam && cam.drawn} drawn of ${allNodes.length}`);
    const executive = allNodes.find((n) => n.__depth === 1 && /executive/i.test(String(n.name)) && /branch/i.test(String(n.type)));
    if (executive) {
      let units = 0;
      let posts = 0;
      const countWalk = (item) => {
        for (const child of item.children || []) {
          // The Executive's two sectors are captioned as masses of their own.
          if (child.id === "exec-independent" || child.id === "exec-regulatory") continue;
          if (isPost(child)) posts += 1;
          else if (!child.synthetic && !/treasury accounting line/i.test(String(child.type || ""))) units += 1;
          countWalk(child);
        }
      };
      countWalk(executive);
      const caption = await verdictOf(executive.id);
      const expected = `${units.toLocaleString("en-US")} units · ${posts.toLocaleString("en-US")} posts in this graph`;
      check("the Executive's caption carries this graph's own counts", caption && caption.text.startsWith(expected), `${caption && caption.text} — expected to start with ${expected}`);
      measurements.wholeExecutiveCaption = caption && caption.text;
    }
    await page.keyboard.press("Digit1");
    await page.waitForTimeout(3000);
    const backCam = await page.evaluate(() => window.__bureaucracy_camera__?.() || null);
    check("leaving Whole restores the distance tiers", backCam && backCam.lodLabel !== "Whole Government", JSON.stringify(backCam));
    check("leaving Whole lets the tiers thin the far view again", backCam && backCam.drawn < allNodes.length * 0.5, JSON.stringify(backCam));
    // Back in Structure the sphere is undone: the independent establishments
    // return to their own sector, out of the branches' plane on the
    // Executive's side, and drawn in the independent green.
    await page.waitForTimeout(1500);
    const independent = await page.evaluate(() => window.__bureaucracy_node_screen__?.("exec-independent"));
    measurements.independentSector = independent && independent.world;
    check("leaving Whole restores the expansion layout", independent && Math.hypot(independent.world.x, independent.world.y, independent.world.z) < 400, JSON.stringify(independent));
    check("the independent establishments sit out of the branches' plane, toward the viewer, on the Executive's side",
      independent && independent.world.z > 60 && independent.world.x > 0, JSON.stringify(independent));
    const storedLens = await page.evaluate(() => { try { return JSON.parse(window.localStorage.getItem("bureaucracy-view-prefs-v1") || "{}").lens; } catch (e) { return null; } });
    check("Whole is never the remembered lens", storedLens !== "whole", String(storedLens));

    // Typing a digit into the search box must not change the lens.
    await page.fill("#search-input", "");
    await page.locator("#search-input").focus();
    await page.keyboard.press("Digit3");
    await page.waitForTimeout(300);
    check("a digit typed into the search box does not switch the lens", (await activeLens()) === "structure", String(await activeLens()));
    await page.fill("#search-input", "");
    await page.keyboard.press("Escape");
    await page.click('.lens-btn[data-lens="structure"]');
    await page.waitForTimeout(600);
    check("Structure restores the branch key", (await legendLabel()) === "branch", await legendLabel());
    const branchRowsVisible = await page.evaluate(() => {
      const row = [...document.querySelectorAll("#legend .leg-item")].find((el) => /Treasury accounting line/.test(el.textContent));
      return row ? getComputedStyle(row).display !== "none" && !row.closest("[hidden]") : false;
    });
    check("the branch key's rows are visible again under Structure", branchRowsVisible, "hidden");
  }

  await page.fill("#search-input", "");
  check("no page errors", pageErrors.length === 0, pageErrors.join(" | "));
  await browser.close();
} catch (error) {
  failures.push(`harness: ${error && error.stack ? error.stack : error}`);
} finally {
  server.close();
}
console.log(JSON.stringify({ ok: failures.length === 0, failures, measurements }, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
