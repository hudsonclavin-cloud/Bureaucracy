#!/usr/bin/env node
/**
 * Boot the explorer in headless Chromium and assert the honesty-bearing text.
 *
 * The frontend has no other tests. This one serves the repository root over
 * HTTP (rewriting the unpkg Three.js import to a local copy so it runs without
 * the network), loads index.html, and checks what a visitor is told: the
 * published-node count excludes the review queue, hidden candidates are not
 * searchable, hiding "unverified" nodes does not blank the curated graph, a
 * curated node reads "NO SOURCE RECORDED", and the cost block carries its
 * period line and an Estimate badge.
 *
 * Not part of the pytest suite: it needs Node, `playwright-core` (with a
 * Chromium it can launch) and a local `three` package.
 *
 *   npm install --no-save playwright-core three
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
const threeModule = MODULE_PATHS.map((dir) => path.join(dir, "node_modules", "three", "build", "three.module.js")).find((file) => fs.existsSync(file));
let chromium;
try {
  if (!threeModule) throw new Error("three not found");
  ({ chromium } = require(resolveModule("playwright-core")));
} catch (error) {
  console.error("Install the two dependencies locally first: npm install --no-save three playwright-core");
  console.error(`(or point --modules at a directory containing node_modules; looked in ${MODULE_PATHS.join(", ")})`);
  process.exit(2);
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css" };
const server = http.createServer((req, res) => {
  let pathname = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (pathname === "/vendor/three.module.js") {
    res.writeHead(200, { "content-type": "text/javascript" });
    return fs.createReadStream(threeModule).pipe(res);
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

  await page.fill("#search-input", "United States Senate");
  await page.waitForTimeout(500);
  const rowLabel = await text("#search-results .sr-item .sr-type");
  check("search rows use the never-checked badge", /NO SOURCE RECORDED/.test(rowLabel), rowLabel);
  await page.locator("#search-results .sr-item").first().click();
  await page.waitForTimeout(2000);
  const info = await text("#info-stats");
  check("estimate is labelled", /ESTIMATE/.test(info), info);
  check("period line is printed", /through|As of/.test(info), info);
  const panel = await text("#info-panel");
  check("curated node reads no source recorded", /NO SOURCE RECORDED/.test(panel), panel.slice(0, 200));
  check("no page errors", pageErrors.length === 0, pageErrors.join(" | "));
  await browser.close();
} catch (error) {
  failures.push(`harness: ${error && error.stack ? error.stack : error}`);
} finally {
  server.close();
}
console.log(JSON.stringify({ ok: failures.length === 0, failures }, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
