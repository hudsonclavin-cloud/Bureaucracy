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
  await page.fill("#search-input", "Senate Leadership");
  await page.waitForTimeout(500);
  const rowLabel = await text("#search-results .sr-item .sr-type");
  check("search rows use the never-checked badge", /NO SOURCE RECORDED/.test(rowLabel), rowLabel);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const info = await text("#info-stats");
  check("estimate is labelled", /ESTIMATE/.test(info), info);
  check("period line is printed", /through|As of/.test(info), info);
  check("an apportioned share is not called measured", !/MEASURED/.test(info), info);
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
  const graphJson = JSON.parse(fs.readFileSync(path.join(ROOT, "output", "graph.json"), "utf8"));
  const allNodes = [];
  const walk = (node) => {
    if (!node || typeof node !== "object") return;
    allNodes.push(node);
    for (const child of node.children || []) walk(child);
  };
  walk(graphJson);
  const byId = (id) => allNodes.find((n) => n.id === id);
  const openByName = async (name) => {
    await page.fill("#search-input", name);
    await page.waitForTimeout(500);
    await page.locator("#search-results .sr-item", { hasText: name }).first().click();
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

  // A share nobody can estimate is published as unavailable, never as $0.00
  // — below a cent, or beneath a unit whose net outlays are negative.
  const belowPrecision = allNodes.find((n) => n.cost_validation === "allocation_below_precision" && !/position/i.test(n.type || ""))
    || allNodes.find((n) => n.cost_validation === "allocation_below_precision");
  const poolNegative = allNodes.find((n) => n.cost_validation === "treasury_pool_negative");
  const unavailableNode = belowPrecision || poolNegative;
  check("some node is published unavailable for a stated reason", Boolean(unavailableNode), "none");
  if (unavailableNode) {
    await openByName(unavailableNode.name);
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
  await page.fill("#search-input", "Senate Leadership");
  await page.waitForTimeout(500);
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
  // A cluster's text is written by this UI, so no label there. On a real
  // leaf the description is prose nobody has checked, and must say so.
  const clusterNote = await text("#info-desc-provenance");
  check("a cluster's generated text carries no citation label", clusterNote === "", clusterNote);
  await page.fill("#search-input", "President of the United States");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const descNote = await text("#info-desc-provenance");
  check("a description is labelled as uncited", /uncited prose/i.test(descNote), descNote);
  check("provenance does not call every cost an estimate", !/^costs are estimates/.test(provenance), provenance);

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
