const MAX_GENERATION = 6;

const atlas = document.getElementById("atlas");
const columns = document.getElementById("atlas-columns");
const detail = document.getElementById("atlas-detail");
const search = document.getElementById("atlas-search");
const results = document.getElementById("atlas-search-results");
const title = document.getElementById("atlas-path-title");
const coverage = document.getElementById("atlas-coverage");

const state = {
  root: null,
  nodes: new Map(),
  parents: new Map(),
  depths: new Map(),
  path: [],
  maxGeneration: MAX_GENERATION,
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function walk(node, parent = null, depth = 0) {
  if (!node || typeof node !== "object") return;
  state.nodes.set(node.id, node);
  state.depths.set(node.id, depth);
  if (parent) state.parents.set(node.id, parent.id);
  for (const child of node.children || []) walk(child, node, depth + 1);
}

function evidenceStatus(node) {
  const status = String(node.verificationStatus || "unverified").toLowerCase();
  if (status === "verified") return "verified";
  if (status === "partial") return "partial";
  return "unverified";
}

function formatMoney(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return null;
  const absolute = Math.abs(amount);
  const compact = new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2,
  }).format(absolute);
  return amount < 0 ? `−${compact}` : compact;
}

function pathTo(node) {
  const path = [];
  let current = node;
  while (current) {
    path.unshift(current);
    current = state.nodes.get(state.parents.get(current.id));
  }
  return path;
}

function card(node, selectedId) {
  const status = evidenceStatus(node);
  const childCount = (node.children || []).length;
  return `<button class="entity-card${selectedId === node.id ? " selected" : ""}" data-node-id="${escapeHtml(node.id)}">
    <strong>${escapeHtml(node.name)}</strong>
    <small><span class="evidence-dot ${status}"></span>${escapeHtml(node.type || "Entity")} · ${status === "unverified" ? "no source" : status}</small>
    ${childCount ? `<span class="child-count" aria-label="${childCount} children">${childCount} →</span>` : ""}
  </button>`;
}

function renderColumns() {
  if (!state.root) return;
  const selectedPath = state.path.length ? state.path : [state.root];
  const generations = [];
  const rootSelection = selectedPath[1]?.id || null;
  generations.push({ label: "Generation 1", parent: state.root, nodes: state.root.children || [], selectedId: rootSelection });

  for (let index = 1; index < selectedPath.length && generations.length < state.maxGeneration; index += 1) {
    const parent = selectedPath[index];
    if (!(parent.children || []).length) break;
    generations.push({
      label: `Generation ${index + 1}`,
      parent,
      nodes: parent.children,
      selectedId: selectedPath[index + 1]?.id || null,
    });
  }

  columns.innerHTML = generations.map((generation) => `<section class="atlas-generation">
    <header class="generation-head"><span>${generation.label}</span><span>${generation.nodes.length} entries</span></header>
    <div class="generation-list">${generation.nodes.map((node) => card(node, generation.selectedId)).join("") || "<p>No child entities recorded.</p>"}</div>
  </section>`).join("");
  title.textContent = selectedPath.map((node) => node.name).slice(-2).join(" / ");
  requestAnimationFrame(() => { columns.scrollLeft = columns.scrollWidth; });
}

function sourceLink(node) {
  const url = (node.sourceUrls || [])[0];
  if (!url) return "No source recorded";
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">Open primary evidence ↗</a>`;
}

function renderDetail(node) {
  if (!node) return;
  const measured = node.cost_status === "official" || node.cost_status === "reported";
  const amount = measured ? formatMoney(node.resolved_total_amount ?? node.cost) : null;
  const route = pathTo(node);
  detail.innerHTML = `<div>
      <div class="detail-type">${escapeHtml(node.type || "Federal entity")}</div>
      <h2 class="detail-title">${escapeHtml(node.name)}</h2>
      <p class="detail-desc">${escapeHtml(node.desc || "No description has been recorded for this entity.")}</p>
    </div>
    <dl class="detail-meta">
      <div class="detail-row"><dt>Evidence</dt><dd>${evidenceStatus(node) === "unverified" ? "No source recorded" : escapeHtml(evidenceStatus(node))}</dd></div>
      <div class="detail-row"><dt>Placement</dt><dd>${escapeHtml(route.slice(0, -1).map((item) => item.name).join(" → ") || "Root")}</dd></div>
      <div class="detail-row"><dt>Children</dt><dd>${(node.children || []).length.toLocaleString()} recorded</dd></div>
      <div class="detail-row"><dt>Finance</dt><dd>${amount ? `${amount} · measured` : "No directly reported figure shown"}</dd></div>
      <div class="detail-row"><dt>Period</dt><dd>${escapeHtml(node.cost_period_label || node.costPeriod || "Not reported")}</dd></div>
      <div class="detail-row"><dt>Source</dt><dd>${sourceLink(node)}</dd></div>
    </dl>`;
  detail.classList.add("open");
}

function selectNode(node) {
  if (!node) return;
  state.path = pathTo(node).slice(0, state.maxGeneration + 1);
  renderColumns();
  renderDetail(node);
  results.innerHTML = "";
}

function renderCoverage() {
  const counts = { verified: 0, partial: 0, unverified: 0, measured: 0 };
  for (const node of state.nodes.values()) {
    counts[evidenceStatus(node)] += 1;
    if (node.cost_status === "official" || node.cost_status === "reported") counts.measured += 1;
  }
  coverage.innerHTML = [
    [state.nodes.size, "published entities"],
    [counts.verified, "verified records"],
    [counts.partial, "partially supported"],
    [counts.measured, "reported financial figures"],
  ].map(([value, label]) => `<div class="coverage-stat"><strong>${Number(value).toLocaleString()}</strong><span>${label}</span></div>`).join("");
}

function searchNodes(query) {
  const normalized = query.trim().toLowerCase();
  if (normalized.length < 2) return [];
  return [...state.nodes.values()]
    .filter((node) => (state.depths.get(node.id) || 0) <= MAX_GENERATION)
    .map((node) => {
      const name = String(node.name || "").toLowerCase();
      const type = String(node.type || "").toLowerCase();
      const score = name === normalized ? 0 : name.startsWith(normalized) ? 1 : name.includes(normalized) ? 2 : type.includes(normalized) ? 3 : 99;
      return { node, score };
    })
    .filter((entry) => entry.score < 99)
    .sort((a, b) => a.score - b.score || a.node.name.localeCompare(b.node.name))
    .slice(0, 10);
}

search?.addEventListener("input", () => {
  results.innerHTML = searchNodes(search.value).map(({ node }) => {
    const route = pathTo(node).slice(-3, -1).map((item) => item.name).join(" → ");
    return `<button class="atlas-result" role="option" data-result-id="${escapeHtml(node.id)}"><span><strong>${escapeHtml(node.name)}</strong><small>${escapeHtml(route || "Federal government")}</small></span><small>${escapeHtml(node.type || "Entity")}</small></button>`;
  }).join("");
});

atlas?.addEventListener("click", (event) => {
  const target = event.target.closest("[data-node-id], [data-result-id]");
  if (!target) return;
  selectNode(state.nodes.get(target.dataset.nodeId || target.dataset.resultId));
});

document.querySelectorAll("[data-atlas-depth]").forEach((button) => {
  button.addEventListener("click", () => {
    state.maxGeneration = Math.min(MAX_GENERATION, Number(button.dataset.atlasDepth));
    document.querySelectorAll("[data-atlas-depth]").forEach((item) => item.classList.toggle("active", item === button));
    state.path = state.path.slice(0, state.maxGeneration + 1);
    renderColumns();
  });
});

function setView(view) {
  const isAtlas = view === "atlas";
  document.body.classList.toggle("atlas-mode", isAtlas);
  document.querySelectorAll(".view-switch").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (isAtlas) search?.focus({ preventScroll: true });
}

document.querySelectorAll(".view-switch").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));

async function initAtlas() {
  const source = window.GRAPH_DATA_SOURCES?.primary || "./output/graph.min.json";
  const response = await fetch(source);
  if (!response.ok) throw new Error(`Directory data failed with ${response.status}`);
  state.root = await response.json();
  walk(state.root);
  state.path = [state.root];
  renderCoverage();
  renderColumns();
}

initAtlas().catch((error) => {
  console.error(error);
  if (columns) columns.innerHTML = '<p class="atlas-error">The directory could not be loaded. Switch to the 3D universe or reload the page.</p>';
});
