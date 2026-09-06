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
  // A capped line is the subtlest claim on the page: the figure shown is
  // BELOW the one the Treasury reported, because it did not fit inside an
  // estimated parent. 27 top-most nodes publish $259B less than their own
  // lines. If this text ever regresses to a plain "ESTIMATE" the site
  // understates measured spending without saying so.
  await page.fill("#search-input", "Department of Energy");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const capped = await text("#info-stats");
  check("a capped Treasury line says it is capped", /TREASURY LINE CAPPED/.test(capped), capped);
  check("a capped node names the figure the Treasury reported", /Treasury reported \$/.test(capped), capped);
  check("a capped figure is not called measured", !/\bMEASURED\b/.test(capped), capped);
  const cappedPanel = await text("#info-panel");
  check(
    "an existence-verified node says which page named it",
    /official page names it|official page lists it/i.test(cappedPanel),
    cappedPanel.slice(0, 300),
  );

  // A share that rounds below a cent is published as unavailable, never as
  // $0.00 — a zero would read as "this costs nothing".
  await page.fill("#search-input", "President of the United States");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const unavailable = await text("#info-stats");
  check("a sub-cent share reads as unavailable", /Not available|NOT AVAILABLE/.test(unavailable), unavailable);
  // The COST VALUE must not be a zero. The explanation below it is allowed to
  // say the words "rather than $0" — that sentence is the honesty, not a bug.
  check(
    "a sub-cent share is never rendered as a zero cost",
    !/COST\s*[\n\r]*\s*[≈~]?\s*\$0(\.00)?\b/.test(unavailable),
    unavailable,
  );
  check("a sub-cent share explains itself", /less than one cent/i.test(unavailable), unavailable);

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
  check("an evidenced placement says the parent's page lists it", /Placement: its parent's official page lists it/.test(placed), placed);
  check("an evidenced placement never says 'reports to'", !/reports to/i.test(placed), placed);
  await page.fill("#search-input", "Senate Leadership");
  await page.waitForTimeout(500);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const unplaced = await text("#verification-placement");
  check("an unchecked placement says no evidence is recorded", /Placement: no evidence recorded/.test(unplaced), unplaced);
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
