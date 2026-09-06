import { createGovernmentGraph } from "./graph.js?v=20260906a";
import { loadMergedGraphData } from "./graphLoader.js?v=20260906a";

const shouldBootUi = (() => {
  if (typeof window === "undefined") {
    return true;
  }
  if (window.__bureaucracy_ui_loaded__) {
    console.warn("ui.js loaded twice - preventing duplicate initialization.");
    return false;
  }
  window.__bureaucracy_ui_loaded__ = true;
  return true;
})();

const dom = {
  loading: document.getElementById("loading"),
  loadStatus: document.getElementById("load-status"),
  infoPanel: document.getElementById("info-panel"),
  infoName: document.getElementById("info-name"),
  infoType: document.getElementById("info-type"),
  infoDesc: document.getElementById("info-desc"),
  infoStats: document.getElementById("info-stats"),
  childrenLabel: document.getElementById("info-children-label"),
  childrenList: document.getElementById("info-children-list"),
  breadcrumb: document.getElementById("bc-items"),
  nodeCounter: document.getElementById("node-counter"),
  statsTotal: document.getElementById("stats-total"),
  statsLoaded: document.getElementById("stats-loaded"),
  statsDepth: document.getElementById("stats-depth"),
  statsPanel: document.getElementById("stats"),
  legend: document.getElementById("legend"),
  depthCtrl: document.getElementById("depth-ctrl"),
  expandLoader: document.getElementById("expand-loader"),
  btnExpand: document.getElementById("btn-expand"),
  btnExpandAll: document.getElementById("btn-expand-all"),
  btnCancelExpand: document.getElementById("btn-cancel-expand"),
  btnFocus: document.getElementById("btn-focus"),
  btnFlyMode: document.getElementById("btn-fly-mode"),
  btnCollapse: document.getElementById("btn-collapse"),
  searchInput: document.getElementById("search-input"),
  searchResults: document.getElementById("search-results"),
  tooltip: document.getElementById("tooltip"),
  canvas: document.getElementById("canvas"),
  btnTraceOrigin: null,
  originWrap: null,
  originList: null,
  verificationWrap: null,
  verificationStatus: null,
  verificationConfidence: null,
  verificationSources: null,
  verificationLastVerified: null,
  verificationBadge: null,
  togglesWrap: null,
  toggleUnverified: null,
  toggleCandidates: null,
};

const state = {
  graph: null,
  searchIndex: [],
  expandCancelled: false,
  expandFrame: 0,
  loaderTimer: null,
  tracedNodeId: null,
  revealFrame: 0,
  loadFailed: false,
};

function setText(element, value) {
  if (element.textContent !== value) {
    element.textContent = value;
  }
}

function showLoader(label) {
  clearTimeout(state.loaderTimer);
  setText(dom.expandLoader, label);
  dom.expandLoader.style.display = "block";
}

function hideLoader(delay = 200) {
  clearTimeout(state.loaderTimer);
  state.loaderTimer = window.setTimeout(() => {
    dom.expandLoader.style.display = "none";
  }, delay);
}

function updateStats(stats) {
  const candidateCount = Number(stats.candidateNodeCount || 0);
  // With the candidate toggle on, the review queue is on screen too and the
  // denominator says so; with it off, the count is the published graph alone.
  const denominator = stats.showCandidateNodes ? stats.totalNodeCount + candidateCount : stats.totalNodeCount;
  setText(dom.nodeCounter, `${stats.visibleNodeCount.toLocaleString()} / ${denominator.toLocaleString()} nodes rendered`);
  setText(
    dom.statsTotal,
    candidateCount > 0
      ? `${stats.totalNodeCount.toLocaleString()} published nodes · ${candidateCount.toLocaleString()} unreviewed candidates`
      : `${stats.totalNodeCount.toLocaleString()} total nodes`,
  );
  setText(
    dom.statsLoaded,
    `${stats.visibleNodeCount.toLocaleString()} currently loaded | ${stats.lodLabel || "Universe View"} | ${(stats.densityHiddenNodeCount || 0).toLocaleString()} density-hidden`,
  );
  setText(
    dom.statsDepth,
    `LOD ${stats.lodLevel ?? "?"}: ${stats.lodLabel || "Unknown"} | depth ${Number.isFinite(stats.maxVisibleDepth) ? stats.maxVisibleDepth : "All"} | queue ${stats.pendingExpansions ?? 0}`,
  );
}

function hideLoadingOverlay(delay = 600) {
  if (!dom.loading || state.loadFailed) {
    return;
  }
  dom.loading.style.opacity = "0";
  window.setTimeout(() => {
    if (dom.loading?.parentElement && !state.loadFailed) {
      dom.loading.remove();
    }
  }, delay);
}

function showLoadFailure(message) {
  state.loadFailed = true;
  if (!dom.loading || !dom.loading.parentElement) {
    return;
  }
  dom.loading.style.opacity = "1";
  const loadFill = dom.loading.querySelector(".load-fill");
  if (loadFill) {
    loadFill.style.animation = "none";
    loadFill.style.background = "#c85a4a";
  }
  setText(dom.loadStatus, message);
  dom.loadStatus.style.color = "#e09090";

  if (!dom.loading.querySelector("[data-reload-button='true']")) {
    const reloadButton = document.createElement("button");
    reloadButton.dataset.reloadButton = "true";
    reloadButton.className = "btn btn-expand";
    reloadButton.textContent = "Reload";
    reloadButton.style.width = "auto";
    reloadButton.style.marginTop = "16px";
    reloadButton.style.padding = "8px 22px";
    reloadButton.addEventListener("click", () => window.location.reload());
    dom.loading.appendChild(reloadButton);
  }
}

function handleUiFailure(error, message = "UI failed to initialize. Open browser console for details.") {
  console.error(message, error);
  showLoadFailure(message);
}

function safeUiCall(label, callback, ...args) {
  try {
    return callback(...args);
  } catch (error) {
    console.error(`UI callback failed: ${label}`, error);
    return undefined;
  }
}

function renderBreadcrumb(nodeObj) {
  const path = [];
  let cursor = nodeObj;
  while (cursor) {
    path.unshift(cursor);
    cursor = cursor.parent;
  }

  dom.breadcrumb.replaceChildren();
  const fragment = document.createDocumentFragment();
  path.forEach((item, index) => {
    if (index > 0) {
      const separator = document.createElement("span");
      separator.className = "bc-sep";
      separator.textContent = "›";
      fragment.appendChild(separator);
    }

    const crumb = document.createElement("span");
    crumb.className = "bc-item";
    crumb.textContent = item.data.name.length > 28 ? `${item.data.name.slice(0, 26)}…` : item.data.name;
    crumb.addEventListener("click", () => state.graph.setSelectedNode(item));
    fragment.appendChild(crumb);
  });
  dom.breadcrumb.appendChild(fragment);
}

function ensureOriginUi() {
  if (dom.btnTraceOrigin && dom.originWrap && dom.originList) {
    return;
  }

  const actionRow = dom.btnFocus.parentElement;
  const traceButton = document.createElement("button");
  traceButton.className = "btn btn-focus";
  traceButton.id = "btn-trace-origin";
  traceButton.textContent = "Trace Origin";
  actionRow.insertBefore(traceButton, dom.btnCollapse);

  const originWrap = document.createElement("div");
  originWrap.style.display = "none";
  originWrap.style.marginTop = "10px";

  const originLabel = document.createElement("div");
  originLabel.textContent = "ORIGIN PATH";
  originLabel.style.fontSize = "10px";
  originLabel.style.letterSpacing = "0.12em";
  originLabel.style.color = "#8f7a5d";
  originLabel.style.marginBottom = "6px";
  originWrap.appendChild(originLabel);

  const originList = document.createElement("div");
  originList.style.display = "flex";
  originList.style.flexDirection = "column";
  originList.style.gap = "4px";
  originList.style.padding = "8px 10px";
  originList.style.border = "1px solid rgba(200,168,74,0.14)";
  originList.style.background = "rgba(20,16,12,0.72)";
  originList.style.borderRadius = "10px";
  originWrap.appendChild(originList);

  dom.childrenList.insertAdjacentElement("afterend", originWrap);

  dom.btnTraceOrigin = traceButton;
  dom.originWrap = originWrap;
  dom.originList = originList;
}

function ensureVerificationUi() {
  if (
    dom.verificationWrap &&
    dom.verificationStatus &&
    dom.verificationConfidence &&
    dom.verificationSources &&
    dom.verificationLastVerified
  ) {
    return;
  }

  const verificationWrap = document.createElement("div");
  verificationWrap.style.marginTop = "10px";
  verificationWrap.style.padding = "10px";
  // Every other line in the panel is 8-10px; without this the status,
  // confidence and source lines inherit the browser's 16px default.
  verificationWrap.style.fontSize = "9px";
  verificationWrap.style.lineHeight = "1.6";
  verificationWrap.style.color = "#9a8a6a";
  verificationWrap.style.border = "1px solid rgba(200,168,74,0.14)";
  verificationWrap.style.background = "rgba(20,16,12,0.72)";
  verificationWrap.style.borderRadius = "10px";

  const title = document.createElement("div");
  title.textContent = "DATA VERIFICATION";
  title.style.fontSize = "10px";
  title.style.letterSpacing = "0.12em";
  title.style.color = "#8f7a5d";
  title.style.marginBottom = "8px";
  verificationWrap.appendChild(title);

  const status = document.createElement("div");
  const badge = document.createElement("span");
  badge.style.display = "inline-block";
  badge.style.padding = "2px 6px";
  badge.style.marginBottom = "6px";
  badge.style.borderRadius = "999px";
  badge.style.fontSize = "9px";
  badge.style.letterSpacing = "0.08em";
  badge.style.fontWeight = "600";
  const confidence = document.createElement("div");
  const sources = document.createElement("div");
  const lastVerified = document.createElement("div");
  sources.style.display = "flex";
  sources.style.flexDirection = "column";
  sources.style.gap = "4px";
  sources.style.marginTop = "8px";
  verificationWrap.appendChild(badge);
  verificationWrap.appendChild(status);
  verificationWrap.appendChild(confidence);
  verificationWrap.appendChild(sources);
  verificationWrap.appendChild(lastVerified);

  dom.infoPanel.appendChild(verificationWrap);
  dom.verificationWrap = verificationWrap;
  dom.verificationBadge = badge;
  dom.verificationStatus = status;
  dom.verificationConfidence = confidence;
  dom.verificationSources = sources;
  dom.verificationLastVerified = lastVerified;
}

// A node with no sources AND no verification timestamp was never checked at all.
// That is a different claim from "checked and found wanting", and the harsher
// wording is the misleading one: every node in the hand-compiled base graph —
// the Constitution included — carries no sourceUrls, so all 5,170 of them read
// as UNVERIFIED. Overstating doubt is an accuracy problem in the same way
// overstating confidence is.
function isNeverChecked(data) {
  if (data.isCandidate) {
    return false;
  }
  // Deliberately not keyed on verificationStatus: verify_node_sources stamps
  // 'unverified' on every node it touches, so requiring the field to be absent
  // meant this could never fire after a pipeline run. A node recorded with zero
  // sources and no verification timestamp was not checked — that status string
  // is a default, not a finding.
  const sourceCount = Number(data.sourceCount || (Array.isArray(data.sourceUrls) ? data.sourceUrls.length : 0));
  return sourceCount === 0 && !data.lastVerified;
}

function getVerificationBadgeConfig(data) {
  if (data.isCandidate) {
    return { label: "CANDIDATE", bg: "rgba(155,139,189,0.18)", border: "#9b8bbd", color: "#d6caef" };
  }
  if (isNeverChecked(data)) {
    return { label: "NO SOURCE RECORDED", bg: "transparent", border: "#6a5a3a", color: "#9a8a6a" };
  }
  const status = String(data.verificationStatus || "unverified").toLowerCase();
  if (status === "verified") {
    return { label: "VERIFIED", bg: "rgba(111,207,151,0.18)", border: "#6fcf97", color: "#c8f2d7" };
  }
  if (status === "partial") {
    return { label: "PARTIAL", bg: "rgba(217,181,94,0.18)", border: "#d9b55e", color: "#f2deb3" };
  }
  return { label: "UNVERIFIED", bg: "rgba(142,125,98,0.18)", border: "#8e7d62", color: "#d6c7af" };
}

function ensureVerificationToggles() {
  if (dom.togglesWrap && dom.toggleUnverified && dom.toggleCandidates) {
    return;
  }

  // Lives inside the depth control so it flows below the buttons. A fixed
  // position at top:130px was the same coordinate the depth control occupies,
  // so the two checkboxes sat on top of the depth 1-5 buttons and hid them.
  const wrap = document.createElement("div");
  wrap.id = "verification-toggles";
  const depthExpandCtrl = document.getElementById("depth-expand-ctrl");
  if (!depthExpandCtrl) {
    wrap.style.position = "fixed";
    wrap.style.top = "180px";
    wrap.style.left = "32px";
    wrap.style.zIndex = "20";
    wrap.style.display = "flex";
    wrap.style.flexDirection = "column";
    wrap.style.gap = "6px";
  }

  const makeToggle = (labelText) => {
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.gap = "8px";
    label.style.fontSize = "10px";
    label.style.color = "#d4c4a1";
    label.style.pointerEvents = "auto";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    label.appendChild(checkbox);

    const text = document.createElement("span");
    text.textContent = labelText;
    label.appendChild(text);
    wrap.appendChild(label);
    return checkbox;
  };

  const toggleUnverified = makeToggle("Show Unverified Nodes");
  const toggleCandidates = makeToggle("Show Candidate Nodes");
  toggleCandidates.checked = false;

  (depthExpandCtrl || document.body).appendChild(wrap);
  dom.togglesWrap = wrap;
  dom.toggleUnverified = toggleUnverified;
  dom.toggleCandidates = toggleCandidates;
}

function ensureVerificationLegend() {
  if (!dom.legend || dom.legend.querySelector("[data-verification-legend='true']")) {
    return;
  }

  const title = document.createElement("div");
  title.id = "legend-verification-label";
  title.dataset.verificationLegend = "true";
  title.textContent = "Verification";
  title.style.fontSize = "8px";
  title.style.color = "#8f7a5d";
  title.style.letterSpacing = "0.2em";
  title.style.textTransform = "uppercase";
  title.style.margin = "10px 0 5px";
  dom.legend.appendChild(title);

  const items = [
    ["Verified", "#6fcf97"],
    ["Partial", "#d9b55e"],
    ["Unverified", "#8e7d62"],
    ["Candidate", "#9b8bbd"],
  ];
  items.forEach(([labelText, color]) => {
    const row = document.createElement("div");
    row.className = "leg-item";
    row.dataset.verificationLegend = "true";
    row.innerHTML = `<span>${labelText}</span><div class="leg-dot" style="background:${color}"></div>`;
    dom.legend.appendChild(row);
  });
}

function renderVerificationPanel(data) {
  if (!dom.verificationWrap) {
    return;
  }

  const neverChecked = isNeverChecked(data);
  const status = data.isCandidate ? "CANDIDATE" : String(data.verificationStatus || "unverified").toUpperCase();
  const confidence = Number(data.confidenceScore || 0);
  const sourceUrls = Array.isArray(data.sourceUrls) ? data.sourceUrls : [];
  const sourceTypes = Array.isArray(data.sourceTypes) ? data.sourceTypes : [];
  // A generated:// placeholder is not a source; it must not be counted or listed.
  const linkableSources = sourceUrls.filter((url) => isHttpUrl(url));
  const badge = getVerificationBadgeConfig(data);

  setText(dom.verificationBadge, badge.label);
  dom.verificationBadge.style.background = badge.bg;
  dom.verificationBadge.style.border = `1px solid ${badge.border}`;
  dom.verificationBadge.style.color = badge.color;

  if (neverChecked) {
    setText(dom.verificationStatus, "This entry comes from the hand-compiled base graph.");
    // No confidence line: a score of 0.00 on something that was never scored is
    // a number impersonating a measurement.
    setText(dom.verificationConfidence, "No source URL has been attached to it yet.");
    setText(dom.verificationLastVerified, "");
  } else {
    setText(dom.verificationStatus, `Verification Status: ${status}`);
    setText(dom.verificationConfidence, `Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) · Sources: ${linkableSources.length}`);
    // What kind of check this was, not just when. "Its own official page
    // names it" and "its parent's page lists it" are different claims, and a
    // failed check is a third; the panel must not collapse them into a date.
    const checkedOn = data.lastVerified
      ? new Date(data.lastVerified).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
      : null;
    const METHOD_TEXT = {
      name_labelled_on_own_official_page: "Its own official page names it",
      name_labelled_on_parent_official_page: "Its parent's official page lists it",
    };
    let checkLine = "Not yet verified";
    if (data.verificationFailure === "not_found") {
      checkLine = checkedOn
        ? `Checked ${checkedOn}: its official page does not name it as a heading or link`
        : "Its official page does not name it as a heading or link";
    } else if (checkedOn) {
      const how = METHOD_TEXT[String(data.verificationMethod || "")];
      checkLine = how ? `${how} · checked ${checkedOn}` : `Last checked: ${checkedOn}`;
    }
    setText(dom.verificationLastVerified, checkLine);
  }

  dom.verificationSources.replaceChildren();
  const sourcesLabel = document.createElement("div");
  sourcesLabel.textContent = "Sources";
  sourcesLabel.style.marginTop = "6px";
  sourcesLabel.style.color = "#d4c4a1";
  dom.verificationSources.appendChild(sourcesLabel);

  if (linkableSources.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "No confirming sources recorded.";
    empty.style.color = "#8f7a5d";
    dom.verificationSources.appendChild(empty);
    return;
  }

  for (const url of linkableSources) {
    const parsed = new URL(url);
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    link.textContent = `• ${parsed.hostname}`;
    link.style.color = "#d4c4a1";
    dom.verificationSources.appendChild(link);
  }
  // sourceTypes is a set of labels, not a list parallel to sourceUrls.
  const typeLabels = sourceTypes.filter((label) => label && label !== "candidate_discovery" && label !== "unknown");
  if (typeLabels.length > 0) {
    const types = document.createElement("div");
    types.textContent = `Source types: ${typeLabels.join(", ")}`;
    types.style.color = "#8f7a5d";
    dom.verificationSources.appendChild(types);
  }
}

function isHttpUrl(value) {
  try {
    const parsed = new URL(String(value));
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch (_error) {
    return false;
  }
}

function renderOriginTrace(nodeObj) {
  const originTrace = state.graph?.getOriginTrace?.() || [];
  const traceMatchesSelected =
    originTrace.length > 0 && originTrace[originTrace.length - 1]?.data?.id === nodeObj.data.id;

  if (!traceMatchesSelected && state.tracedNodeId && state.tracedNodeId !== nodeObj.data.id) {
    state.graph.clearOriginTrace();
    state.tracedNodeId = null;
  }

  if (!traceMatchesSelected) {
    dom.originWrap.style.display = "none";
    dom.originList.replaceChildren();
    setText(dom.btnTraceOrigin, "Trace Origin");
    dom.btnTraceOrigin.disabled = Boolean(nodeObj.isCluster);
    return;
  }

  state.tracedNodeId = nodeObj.data.id;
  dom.originWrap.style.display = "block";
  dom.originList.replaceChildren();

  const fragment = document.createDocumentFragment();
  originTrace.forEach((item, index) => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "8px";
    row.style.color = item.data.color || "#d4c4a1";
    row.style.cursor = "pointer";
    row.style.paddingLeft = `${index * 10}px`;

    const arrow = document.createElement("span");
    arrow.textContent = index === 0 ? "•" : "→";
    arrow.style.color = "rgba(220, 210, 180, 0.75)";
    row.appendChild(arrow);

    const label = document.createElement("span");
    label.textContent = item.data.name;
    row.appendChild(label);

    row.addEventListener("click", () => state.graph.setSelectedNode(item));
    fragment.appendChild(row);
  });

  dom.originList.appendChild(fragment);
  setText(dom.btnTraceOrigin, "Hide Origin");
  dom.btnTraceOrigin.disabled = false;
}

const COST_MAGNITUDES = [
  [1e12, "trillion"],
  [1e9, "billion"],
  [1e6, "million"],
  [1e3, "thousand"],
];

const COST_BASIS_PHRASES = {
  subtree_weight: "how many units sit beneath it",
  employee_weight: "staff count",
  budget_weight: "reported budget",
  annual_budget_weight: "reported annual budget",
  direct_outlay_weight: "reported outlays",
  implied_budget_weight: "a budget implied from its siblings' reported budgets and its size",
  implied_employee_weight: "a staff count implied from its siblings' reported staff and its size",
};

const COST_STATUS_COPY = {
  root_total: {
    label: "Measured",
    tone: "measured",
    // Deliberately does not name a period: the anchor may be year-to-date, and
    // the period line above this carries the actual timeframe.
    note: "U.S. Treasury outlays, from the Monthly Treasury Statement.",
  },
  official: {
    label: "Measured",
    tone: "measured",
    note: "U.S. Treasury outlays reported for this unit in the Monthly Treasury Statement (Table 5).",
  },
  scaled_official: {
    // The figure shown is the parent's cap, not the Treasury figure, so it is
    // an estimate; the note carries the measured number.
    label: "Estimate (Treasury line capped)",
    tone: "estimate",
    note: "The Treasury reported more than fits within the parent's estimated share; the figure shown is that cap.",
  },
  allocated: { label: "Estimate", tone: "estimate", note: "" },
  unavailable: {
    label: "Not available",
    tone: "none",
    note: "No cost figure could be traced to a source.",
  },
};

// The Treasury anchor's period lives on the graph root's __budgetSummary, not on
// each node — but every figure below the root is apportioned from that same
// total, so the period applies to all of them.
let graphBudgetSummary = null;

function setGraphBudgetSummary(summary) {
  graphBudgetSummary = summary && typeof summary === "object" ? summary : null;
}

function getCostPeriod(node) {
  const source =
    (node && typeof node.__budgetSummary === "object" && node.__budgetSummary) ||
    (node && (node.amount_kind || node.label || node.record_date) ? node : null) ||
    graphBudgetSummary;
  if (!source) {
    return { label: "", amountKind: "" };
  }
  // A Treasury line stamped on a node carries budget_as_of rather than a
  // record_date; without this fallback a measured agency showed no period.
  const asOf = source.record_date || source.budget_as_of;
  const label =
    String(source.label || "").trim() ||
    (asOf ? `As of ${String(asOf).trim()}` : "") ||
    (graphBudgetSummary && graphBudgetSummary !== source ? String(graphBudgetSummary.label || "").trim() : "");
  return { label, amountKind: String(source.amount_kind || "").trim().toLowerCase() };
}

// Full-year only when nothing says otherwise, or when it says so explicitly.
// Anything year-to-date is not a year, whatever else the string contains.
function coversFullYear(amountKind) {
  if (!amountKind) {
    return true;
  }
  if (/ytd/.test(amountKind)) {
    return false;
  }
  return /annual|full[_\s-]?year|fiscal[_\s-]?year[_\s-]?total|fy[_\s-]?total/.test(amountKind);
}

function toFiniteAmount(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : null;
}

function roundToSignificant(value, digits) {
  if (!value) {
    return 0;
  }
  const magnitude = Math.floor(Math.log10(Math.abs(value)));
  const factor = 10 ** (digits - 1 - magnitude);
  return Math.round(value * factor) / factor;
}

// Rounded before the unit is chosen, so 999.9 million reads as $1.00 billion
// rather than $1000 million.
function formatApproximateCost(amount) {
  const rounded = roundToSignificant(amount, 3);
  const sign = rounded < 0 ? "-" : "";
  const size = Math.abs(rounded);
  for (const [unit, word] of COST_MAGNITUDES) {
    if (size >= unit) {
      const scaled = size / unit;
      const decimals = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
      return `${sign}$${scaled.toFixed(decimals)} ${word}`;
    }
  }
  return `${sign}$${Math.round(size).toLocaleString()}`;
}

// Only a verified figure is printed in full. Everything else is a division
// result, so it is rounded and marked approximate — printing it to the cent
// would claim ten significant figures for a number that has about one.
function formatCostAmount(node) {
  const amount = toFiniteAmount(node.resolved_total_amount);
  if (amount === null || isBelowPrecision(node)) {
    return null;
  }
  if (String(node.costVerificationStatus || "").toLowerCase() === "verified") {
    return `$${Math.round(amount).toLocaleString()}`;
  }
  return `≈ ${formatApproximateCost(amount)}`;
}

function isBelowPrecision(node) {
  const amount = toFiniteAmount(node.resolved_total_amount);
  const status = String(node.cost_status || "").toLowerCase();
  return (
    String(node.cost_validation || "").toLowerCase() === "allocation_below_precision" ||
    (status === "allocated" && amount !== null && Math.abs(amount) < 0.5)
  );
}

function describeCost(node) {
  const status = String(node.cost_status || "").toLowerCase();
  if (!status || status === "unavailable" || toFiniteAmount(node.resolved_total_amount) === null || isBelowPrecision(node)) {
    if (isBelowPrecision(node)) {
      return {
        ...COST_STATUS_COPY.unavailable,
        note: "Its share of the estimate above it rounds to less than one cent (or an ancestor's did), so no figure is shown rather than $0.",
      };
    }
    return COST_STATUS_COPY.unavailable;
  }

  const copy = COST_STATUS_COPY[status];
  if (!copy) {
    // An enum the pipeline grew and this map never learned. Show it rather than
    // falling back to something reassuring and wrong.
    return {
      label: status,
      tone: "estimate",
      note: `Unrecognised cost basis reported by the pipeline: ${status}.`,
    };
  }

  if (status === "scaled_official") {
    const reported = toFiniteAmount(node.rollup_total_amount);
    return {
      ...copy,
      note: reported === null
        ? copy.note
        : `The Treasury reported ${formatApproximateCost(reported)} for this unit, more than fits within the parent's estimated share; the figure shown is that cap.`,
    };
  }
  if (status === "allocated") {
    const basis = String(node.cost_basis || "").toLowerCase();
    const phrase =
      COST_BASIS_PHRASES[basis] || (node.cost_basis ? String(node.cost_basis) : "an unspecified weighting");
    return {
      ...copy,
      note: `Not a measured budget. Derived by dividing the parent's total, weighted by ${phrase}.`,
    };
  }
  return copy;
}

function buildCostBlock(node) {
  const block = document.createElement("div");
  block.className = "info-cost";

  const head = document.createElement("div");
  head.className = "info-cost-head";

  const period = getCostPeriod(node);
  const label = document.createElement("span");
  label.className = "info-cost-label";
  label.textContent = coversFullYear(period.amountKind) ? "ANNUAL COST" : "COST";
  head.appendChild(label);

  const amountText = formatCostAmount(node);
  const amount = document.createElement("span");
  amount.className = "info-cost-amount";
  amount.textContent = amountText === null ? "Not available" : amountText;
  head.appendChild(amount);
  block.appendChild(head);

  // Rendered verbatim, including a label this code does not recognise: an
  // unmapped period must be visible rather than quietly dropped.
  if (period.label && amountText !== null) {
    const periodLine = document.createElement("div");
    periodLine.className = "info-cost-period";
    periodLine.style.fontSize = "9px";
    periodLine.style.color = "#9a8a6a";
    periodLine.style.lineHeight = "1.6";
    periodLine.style.marginTop = "3px";
    periodLine.textContent = period.label;
    block.appendChild(periodLine);
  }

  const copy = describeCost(node);
  const badge = document.createElement("span");
  badge.className = `info-cost-badge is-${copy.tone}`;
  badge.textContent = copy.label;
  block.appendChild(badge);

  const note = document.createElement("div");
  note.className = "info-cost-note";
  note.textContent = copy.note;
  block.appendChild(note);

  return block;
}

function renderInfoPanel(nodeObj) {
  if (!nodeObj) {
    return;
  }

  const data = nodeObj.data;
  const activeCluster = nodeObj.isCluster ? nodeObj : nodeObj.clusterRef || null;
  const clusterCount =
    activeCluster?.count ||
    activeCluster?.data?.count ||
    Math.max(0, (data.__meta?.subtreeCount || 1) - 1);
  const isClusteredView = Boolean(activeCluster);
  const clusterReason = activeCluster?.data?.clusterReason || "";
  const clusterTierLabel = activeCluster?.data?.clusterTierLabel || "Current View";
  const loadedBranchCount = activeCluster?.data?.loadedBranchCount || 0;
  setText(dom.infoName, data.name);
  setText(dom.infoType, data.type || "—");
  setText(dom.infoDesc, data.desc || "—");

  if (isClusteredView) {
    setText(dom.infoType, `${data.type || "Group"} Cluster`);
    setText(
      dom.infoDesc,
      `${clusterReason} Represents ${clusterCount.toLocaleString()} descendants across ${loadedBranchCount.toLocaleString()} loaded sub-branches.`,
    );
  }
  if (data.isCandidate) {
    setText(dom.infoType, `${data.type || "Candidate"} Candidate`);
  }

  const statsFragment = document.createDocumentFragment();
  statsFragment.appendChild(buildCostBlock(data));
  const statRows = [];
  if (data.employees) {
    statRows.push(["EMPLOYEES", data.employees]);
  }
  if (data.budget) {
    // A hand-typed note in the curated file, not a sourced figure. Unlabelled it
    // read as a second, contradictory cost beneath the estimate.
    statRows.push(["BUDGET NOTE (hand-compiled)", data.budget]);
  }
  if ((data.children || []).length > 0) {
    statRows.push(["SUB-UNITS", String(data.children.length)]);
  }
  if (isClusteredView) {
    statRows.push(["CLUSTER SIZE", clusterCount.toLocaleString()]);
    statRows.push(["CLUSTER TIER", clusterTierLabel]);
    statRows.push(["LOADED BRANCHES", loadedBranchCount.toLocaleString()]);
  }
  statRows.push(["DEPTH", String(nodeObj.depth)]);

  for (const [label, value] of statRows) {
    const row = document.createElement("div");
    row.className = "info-stat";

    const labelSpan = document.createElement("span");
    labelSpan.className = "info-stat-label";
    labelSpan.textContent = label;
    row.appendChild(labelSpan);

    const valueSpan = document.createElement("span");
    valueSpan.className = "info-stat-val";
    valueSpan.textContent = value;
    row.appendChild(valueSpan);

    statsFragment.appendChild(row);
  }
  dom.infoStats.replaceChildren(statsFragment);

  dom.childrenList.replaceChildren();
  const children = data.children || [];
  if (children.length > 0) {
    dom.childrenLabel.style.display = "block";
    const fragment = document.createDocumentFragment();
    for (const child of children.slice(0, 8)) {
      const item = document.createElement("div");
      item.className = "child-item";

      const dot = document.createElement("div");
      dot.className = "child-dot";
      dot.style.background = child.color || "#666";
      item.appendChild(dot);

      const label = document.createElement("span");
      label.textContent = child.name;
      item.appendChild(label);

      item.addEventListener("click", () => {
        const childObj = state.graph.getNodeById(child.id);
        if (childObj) {
          state.graph.setSelectedNode(childObj);
          return;
        }
        state.graph.expandNode(nodeObj, true);
        pollForRevealedNode(child.id);
      });

      fragment.appendChild(item);
    }

    if (children.length > 8) {
      const more = document.createElement("div");
      more.className = "child-item";
      more.style.color = "#5a4a3a";
      more.innerHTML = `<div class="child-dot" style="background:#333"></div><span>+ ${children.length - 8} more</span>`;
      fragment.appendChild(more);
    }

    dom.childrenList.appendChild(fragment);
  } else {
    dom.childrenLabel.style.display = "none";
  }

  if (children.length > 0 && !nodeObj.expanded) {
    dom.btnExpand.disabled = false;
    setText(dom.btnExpand, `Expand — ${children.length} nodes`);
    dom.btnExpandAll.disabled = false;
    setText(dom.btnExpandAll, "Expand All Below");
    if (isClusteredView) {
      setText(dom.btnExpand, `Open Cluster - ${children.length} nodes`);
      setText(dom.btnExpandAll, "Open Full Branch");
    }
    dom.btnCollapse.style.display = "none";
  } else if (nodeObj.expanded) {
    dom.btnExpand.disabled = true;
    setText(dom.btnExpand, "Already Expanded");
    dom.btnExpandAll.disabled = false;
    setText(dom.btnExpandAll, "Expand All Below");
    dom.btnCollapse.style.display = "block";
  } else {
    dom.btnExpand.disabled = true;
    setText(dom.btnExpand, "No Sub-nodes");
    dom.btnExpandAll.disabled = true;
    setText(dom.btnExpandAll, "No Sub-nodes");
    dom.btnCollapse.style.display = "none";
  }

  dom.infoPanel.classList.add("open");
  dom.depthCtrl.classList.add("panel-open");
  dom.statsPanel.classList.remove("panel-closed");
  setText(dom.btnFlyMode, state.graph?.isFlyMode() ? "Disable Fly Mode" : "Enable Fly Mode");
  if (dom.btnTraceOrigin) {
    renderOriginTrace(nodeObj);
  }
  renderVerificationPanel(data);
  renderBreadcrumb(nodeObj);
}

function updateTooltip(payload) {
  if (!payload) {
    dom.tooltip.style.display = "none";
    return;
  }

  dom.tooltip.style.display = "block";
  dom.tooltip.style.left = `${payload.x + 14}px`;
  dom.tooltip.style.top = `${payload.y - 10}px`;
  setText(dom.tooltip, payload.node.data.name);
}

function closeSearch() {
  dom.searchResults.style.display = "none";
  dom.searchResults.replaceChildren();
}

function renderSearchResults(matches) {
  dom.searchResults.replaceChildren();
  if (matches.length === 0) {
    closeSearch();
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const match of matches) {
    const row = document.createElement("div");
    row.className = "sr-item";

    const name = document.createElement("span");
    name.className = "sr-name";
    name.textContent = match.name;
    row.appendChild(name);

    if (match.pathStr) {
      const path = document.createElement("span");
      path.className = "sr-path";
      path.textContent = match.pathStr;
      row.appendChild(path);
    }

    const type = document.createElement("span");
    type.className = "sr-type";
    const status = getVerificationBadgeConfig(match).label;
    type.textContent = `${match.type} — ${status}`;
    type.style.color = match.color || "#666";
    type.style.borderColor = `${match.color || "#666"}40`;
    row.appendChild(type);

    row.addEventListener("click", () => {
      closeSearch();
      dom.searchInput.value = "";
      revealAndSelect(match.id);
    });

    fragment.appendChild(row);
  }

  dom.searchResults.appendChild(fragment);
  dom.searchResults.style.display = "block";
}

const REVEAL_TIMEOUT_MS = 2000;

function cancelRevealLoop() {
  if (state.revealFrame) {
    window.cancelAnimationFrame(state.revealFrame);
    state.revealFrame = 0;
  }
}

function pollForRevealedNode(id, timeoutMs = REVEAL_TIMEOUT_MS) {
  cancelRevealLoop();
  const deadline = performance.now() + timeoutMs;
  const settle = () => {
    state.revealFrame = 0;
    const revealed = state.graph.getNodeById(id);
    if (revealed) {
      state.graph.setSelectedNode(revealed);
      return;
    }
    if (performance.now() >= deadline) {
      console.warn(`Reveal timed out for node "${id}".`);
      return;
    }
    if (!state.graph.hasPendingExpansions()) {
      console.warn(`Node "${id}" never materialized - abandoning reveal.`);
      return;
    }
    state.revealFrame = window.requestAnimationFrame(settle);
  };
  state.revealFrame = window.requestAnimationFrame(settle);
}

function revealAndSelect(id) {
  cancelRevealLoop();
  const revealed = state.graph.revealNodeById(id, true);
  if (!revealed) {
    // graph.js contract: a falsy return is deterministic failure (unknown id or
    // unbuildable ancestor) - never retry it.
    console.warn(`Node "${id}" could not be revealed.`);
    return;
  }
  state.graph.setSelectedNode(revealed);
}

function stopProgressiveExpansion() {
  state.expandCancelled = true;
  if (state.expandFrame) {
    window.cancelAnimationFrame(state.expandFrame);
    state.expandFrame = 0;
  }
  dom.btnCancelExpand.style.display = "none";
  dom.btnExpandAll.disabled = false;
  setText(dom.btnExpandAll, "Expand All Below");
  hideLoader(0);
}

function progressiveRender(frontierNodes, addNode, onComplete) {
  let index = 0;
  const BATCH = 200;

  function step() {
    let count = 0;
    while (index < frontierNodes.length && count < BATCH) {
      addNode(frontierNodes[index]);
      index += 1;
      count += 1;
    }

    updateStats(state.graph.getStats());

    if (index < frontierNodes.length) {
      state.expandFrame = window.requestAnimationFrame(step);
    } else if (onComplete) {
      onComplete();
    }
  }

  step();
}

function waitForExpansionDrain(onDone) {
  if (state.expandCancelled) {
    return;
  }

  updateStats(state.graph.getStats());
  if (state.graph.hasPendingExpansions()) {
    showLoader("Loading queued nodes…");
    state.expandFrame = window.requestAnimationFrame(() => waitForExpansionDrain(onDone));
    return;
  }

  onDone();
}

function expandProgressively(targetDepth) {
  state.expandCancelled = false;
  dom.btnExpandAll.disabled = true;
  setText(dom.btnExpandAll, "Expanding…");
  dom.btnCancelExpand.style.display = "block";

  const totalLevels = Math.min(
    Number.isFinite(targetDepth) ? targetDepth : state.graph.getMaxDataDepth(),
    state.graph.getConfig().MAX_DEPTH,
  );

  const tick = () => {
    if (state.expandCancelled) {
      hideLoader(0);
      return;
    }

    const frontier = state.graph.getFrontier(targetDepth);
    if (frontier.nodes.length === 0) {
      if (state.graph.hasPendingExpansions()) {
        showLoader("Loading queued nodes…");
        state.expandFrame = window.requestAnimationFrame(tick);
        return;
      }
      dom.btnCancelExpand.style.display = "none";
      dom.btnExpandAll.disabled = false;
      setText(dom.btnExpandAll, "Expand All Below");
      hideLoader();
      renderInfoPanel(state.graph.getSelectedNode());
      return;
    }

    const nextCount = state.graph.estimateExpansionSize(frontier.nodes);
    const stats = state.graph.getStats();
    if (stats.visibleNodeCount + nextCount > stats.maxNodes) {
      state.graph.pruneDistantNodes();
    }

    const refreshedStats = state.graph.getStats();
    if (refreshedStats.visibleNodeCount + nextCount > refreshedStats.maxNodes) {
      showLoader(`Node cap reached at level ${frontier.depth + 1}`);
      dom.btnCancelExpand.style.display = "none";
      dom.btnExpandAll.disabled = false;
      setText(dom.btnExpandAll, "Expand All Below");
      hideLoader(900);
      renderInfoPanel(state.graph.getSelectedNode());
      return;
    }

    showLoader(`Loading level ${frontier.depth + 1} of ${totalLevels}…`);
    progressiveRender(frontier.nodes, (nodeObj) => {
      state.graph.expandNodesBatch([nodeObj], true);
    }, () => {
      waitForExpansionDrain(() => {
        renderInfoPanel(state.graph.getSelectedNode());
        state.expandFrame = window.requestAnimationFrame(tick);
      });
    });
  };

  showLoader("Starting expansion…");
  state.expandFrame = window.requestAnimationFrame(tick);
}

function bindControls() {
  if (dom.toggleUnverified) {
    dom.toggleUnverified.addEventListener("change", () => {
      state.graph.setShowUnverifiedNodes(dom.toggleUnverified.checked);
      updateStats(state.graph.getStats());
    });
  }

  if (dom.toggleCandidates) {
    dom.toggleCandidates.addEventListener("change", () => {
    // An open results list may hold candidate rows the toggle now hides.
    closeSearch();
      state.graph.setShowCandidateNodes(dom.toggleCandidates.checked);
      updateStats(state.graph.getStats());
    });
  }

  dom.btnTraceOrigin.addEventListener("click", () => {
    const selected = state.graph.getSelectedNode();
    if (!selected || selected.isCluster) {
      return;
    }

    const currentTrace = state.graph.getOriginTrace();
    const traceMatchesSelected =
      currentTrace.length > 0 && currentTrace[currentTrace.length - 1]?.data?.id === selected.data.id;

    if (traceMatchesSelected) {
      state.graph.clearOriginTrace();
      state.tracedNodeId = null;
    } else {
      const originPath = state.graph.traceOrigin(selected);
      state.graph.setOriginTrace(originPath);
      state.tracedNodeId = selected.data.id;
    }

    renderInfoPanel(selected);
  });

  dom.btnExpand.addEventListener("click", () => {
    const selected = state.graph.getSelectedNode();
    if (!selected) {
      return;
    }
    showLoader("Loading branch…");
    state.graph.expandNode(selected, true);
    const settle = () => {
      if (state.graph.hasPendingExpansions()) {
        window.requestAnimationFrame(settle);
        return;
      }
      hideLoader();
      renderInfoPanel(selected);
    };
    window.requestAnimationFrame(settle);
  });

  dom.btnExpandAll.addEventListener("click", () => {
    if (!state.graph.getSelectedNode()) {
      return;
    }
    expandProgressively(Infinity);
  });

  dom.btnCancelExpand.addEventListener("click", stopProgressiveExpansion);

  dom.btnFocus.addEventListener("click", () => {
    state.graph.focusSelectedNode();
  });

  dom.btnFlyMode.addEventListener("click", () => {
    const enabled = state.graph.setFlyMode(!state.graph.isFlyMode());
    setText(dom.btnFlyMode, enabled ? "Disable Fly Mode" : "Enable Fly Mode");
  });

  dom.btnCollapse.addEventListener("click", () => {
    const selected = state.graph.getSelectedNode();
    if (!selected) {
      return;
    }
    state.graph.collapseNode(selected);
    renderInfoPanel(selected);
  });

  document.querySelectorAll(".depth-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".depth-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const depth = button.dataset.depth === "all" ? Infinity : Number(button.dataset.depth);
      state.graph.setDepthFilter(depth);
      updateStats(state.graph.getStats());
    });
  });

  document.querySelectorAll(".depth-expand-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".depth-expand-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      expandProgressively(Number(button.dataset.target));
    });
  });

  dom.searchInput.addEventListener("input", () => {
    const query = dom.searchInput.value.trim().toLowerCase();
    if (query.length < 2) {
      closeSearch();
      return;
    }
    const matches = [];
    const showCandidates = Boolean(dom.toggleCandidates?.checked);
    for (const item of state.searchIndex) {
      if (item.isCandidate && !showCandidates) {
        continue;
      }
      if (
        item.name.toLowerCase().includes(query) ||
        item.type.toLowerCase().includes(query) ||
        item.pathStr.toLowerCase().includes(query)
      ) {
        matches.push(item);
      }
      if (matches.length === 12) {
        break;
      }
    }
    renderSearchResults(matches);
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("#search-wrap")) {
      closeSearch();
    }
  });
}

function initUI() {
  ensureOriginUi();
  ensureVerificationUi();
  ensureVerificationToggles();
  ensureVerificationLegend();
  bindControls();
  safeUiCall("updateStats", updateStats, state.graph.getStats());
}

function safeInitUI() {
  try {
    initUI();
  } catch (error) {
    handleUiFailure(error);
  }
}

async function initGraphApp() {
  state.graph = createGovernmentGraph({
    canvas: dom.canvas,
    onSelect: (nodeObj) => {
      cancelRevealLoop();
      safeUiCall("renderInfoPanel", renderInfoPanel, nodeObj);
    },
    onHover: (payload) => safeUiCall("updateTooltip", updateTooltip, payload),
    onCountsChange: (stats) => safeUiCall("updateStats", updateStats, stats),
  });

  const data = await loadMergedGraphData({
    baseUrl:
      window.GRAPH_DATA_SOURCES?.primary ||
      window.GRAPH_DATA_SOURCES?.base ||
      "./data/federal_gov_complete_1.json",
    fallbackBaseUrl: window.GRAPH_DATA_SOURCES?.base || "./data/federal_gov_complete_1.json",
    // null means "no overlay"; only an undefined key falls back to the default path.
    corporateUrl:
      window.GRAPH_DATA_SOURCES && "corporate" in window.GRAPH_DATA_SOURCES
        ? window.GRAPH_DATA_SOURCES.corporate
        : "./data_expansion/corporate_expansion.json",
    onStatus: (message) => setText(dom.loadStatus, message),
  });
  setGraphBudgetSummary(data && data.__budgetSummary);
  if (data && data.__loadSource === "fallback") {
    const provenance = document.getElementById("data-provenance");
    if (provenance) {
      provenance.textContent = "Pipeline graph unavailable — showing the hand-compiled hierarchy without cost data";
    }
  }
  state.graph.loadData(data);
  state.searchIndex = state.graph.getSearchIndex();
  safeInitUI();
  hideLoadingOverlay();
}

if (shouldBootUi) {
  initGraphApp().catch((error) => {
    console.error(error);
    showLoadFailure("Failed to load explorer data. Check your connection, then reload.");
  });
}
