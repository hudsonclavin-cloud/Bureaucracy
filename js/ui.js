import { createGovernmentGraph } from "./graph.js?v=20260327a";
import { loadMergedGraphData } from "./graphLoader.js?v=20260326d";
import { createVrMode } from "./vrMode.js?v=20260324vr2";

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
  buildBadge: document.getElementById("build-badge"),
  statsTotal: document.getElementById("stats-total"),
  statsLoaded: document.getElementById("stats-loaded"),
  statsDepth: document.getElementById("stats-depth"),
  statsCost: document.getElementById("stats-cost"),
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
  btnVr: document.getElementById("btn-vr"),
  btnHome: document.getElementById("btn-home"),
  btnResetCamera: document.getElementById("btn-reset-camera"),
  btnFitBranch: document.getElementById("btn-fit-branch"),
  btnCollapseAll: document.getElementById("btn-collapse-all"),
  btnCopyShareLink: document.getElementById("btn-copy-share-link"),
  btnExportJson: document.getElementById("btn-export-json"),
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
  costTabEl: null,
};

const state = {
  graph: null,
  searchIndex: [],
  expandCancelled: false,
  expandFrame: 0,
  loaderTimer: null,
  tracedNodeId: null,
  vrMode: null,
};

const COST_STATUS_LABELS = {
  root_total: "Treasury Total",
  official: "Official Rollup",
  scaled_official: "Official Rollup (Scaled)",
  allocated: "Estimated Allocation",
  unavailable: "Cost Unavailable",
};

const COST_BASIS_LABELS = {
  treasury_total_outlays: "Treasury total outlays",
  treasury_rollup: "Treasury rollup",
  subtree_weight: "Subtree-size weighting",
  employee_weight: "Employee weighting",
  budget_weight: "Budget weighting",
};

const COST_VALIDATION_LABELS = {
  verified_with_treasury_total: "Verified with Treasury total",
  matched_official_rollup: "Matched official rollup",
  estimated_from_parent: "Estimated from parent total",
  scaled_to_parent_total: "Scaled to parent total",
  missing_cost: "Missing cost",
  summed_from_child_totals: "Summed from child totals",
};

const AMOUNT_KIND_LABELS = {
  fytd_net_outlays: "Partial-year net outlays (FYTD)",
};

/**
 * Returns FYTD context for a budget summary, including an annualized estimate.
 * US fiscal year starts October 1.
 */
function getBudgetFytdContext(budgetSummary) {
  if (!budgetSummary || budgetSummary.amount_kind !== "fytd_net_outlays") {
    return null;
  }
  const amount = Number(budgetSummary.government_total_outlay_amount);
  const recordDate = String(budgetSummary.record_date || "");
  const fiscalYear = String(budgetSummary.fiscal_year || "");
  if (!amount || !recordDate) {
    return null;
  }
  const [yr, mo] = recordDate.split("-").map(Number);
  if (!yr || !mo) {
    return null;
  }
  // Months elapsed since Oct 1 of the fiscal year start
  const fyStartYear = mo >= 10 ? yr : yr - 1;
  const monthsElapsed = mo >= 10 ? mo - 9 : mo + 3;
  if (monthsElapsed <= 0) {
    return null;
  }
  const annualized = amount * (12 / monthsElapsed);
  return { amount, annualized, recordDate, fiscalYear, monthsElapsed };
}

function setText(element, value) {
  if (element.textContent !== value) {
    element.textContent = value;
  }
}

function formatCurrency(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) {
    return "$0";
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(numeric);
}

function truncateLabel(value, maxLength = 32) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function uniqueStrings(values) {
  const result = [];
  const seen = new Set();
  for (const value of values || []) {
    const normalized = String(value || "").trim();
    if (!normalized) {
      continue;
    }
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(normalized);
  }
  return result;
}

function getNodeSourceUrls(data) {
  return uniqueStrings([
    ...(Array.isArray(data?.sourceUrls) ? data.sourceUrls : []),
    ...(data?.official_website ? [data.official_website] : []),
  ]);
}

function getNodeVerificationEvidence(data) {
  const meta = data?.__meta || {};
  const directSourceUrls = getNodeSourceUrls(data);
  const directSourceCount = Math.max(
    Number(data?.sourceCount || 0),
    Number(meta.directSourceCount || 0),
    directSourceUrls.length,
  );
  const branchSourceCount = Math.max(Number(meta.subtreeSourceCount || 0), directSourceCount);
  const branchEvidenceNodeCount = Math.max(
    Number(meta.subtreeEvidenceNodeCount || 0),
    directSourceCount > 0 ? 1 : 0,
  );
  const branchVerifiedNodeCount = Math.max(Number(meta.subtreeVerifiedNodeCount || 0), 0);
  const branchSourceUrls = uniqueStrings([
    ...directSourceUrls,
    ...(Array.isArray(meta.subtreeSourceUrlSamples) ? meta.subtreeSourceUrlSamples : []),
  ]);
  const inheritedEvidenceNodeCount = Math.max(0, branchEvidenceNodeCount - (directSourceCount > 0 ? 1 : 0));
  const inheritedSourceCount = Math.max(0, branchSourceCount - directSourceCount);
  return {
    directSourceUrls,
    directSourceCount,
    branchSourceCount,
    branchEvidenceNodeCount,
    branchVerifiedNodeCount,
    branchSourceUrls,
    inheritedEvidenceNodeCount,
    inheritedSourceCount,
    hasDirectEvidence: directSourceCount > 0,
    hasInheritedEvidence: inheritedEvidenceNodeCount > 0 || inheritedSourceCount > 0,
  };
}

function getDirectCostLabel(data) {
  if (Number.isFinite(Number(data?.direct_outlay_amount)) && Number(data.direct_outlay_amount) > 0) {
    return formatCurrency(data.direct_outlay_amount);
  }
  if (data?.amount_kind === "fytd_net_outlays" && Number.isFinite(Number(data?.rollup_total_amount))) {
    return null;
  }
  if (data?.budget) {
    return data.budget;
  }
  if (data?.annual_budget) {
    return data.annual_budget;
  }
  const directCost = Number(data?.__meta?.directCost || 0);
  return directCost > 0 ? formatCurrency(directCost) : null;
}

function humanizeMetadataValue(value, labelMap = {}) {
  const key = String(value || "").trim();
  if (!key) {
    return "";
  }
  if (labelMap[key]) {
    return labelMap[key];
  }
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function getCostTypeDetails(data) {
  const directOutlayAmount = Number(data?.direct_outlay_amount);
  if (Number.isFinite(directOutlayAmount) && directOutlayAmount !== 0) {
    return {
      label: "Direct Cost",
      detail: "Recorded directly on this node.",
    };
  }

  const status = String(data?.cost_status || "").toLowerCase();
  if (status === "root_total") {
    const budgetSummary = state.graph?.getStats?.()?.budgetSummary;
    const fytd = getBudgetFytdContext(budgetSummary);
    const detail = fytd
      ? `Treasury net outlays through ${fytd.recordDate} (${fytd.monthsElapsed} of 12 months of FY${fytd.fiscalYear}). Estimated full-year: ${formatCurrency(fytd.annualized)}.`
      : "Verified top-line Treasury outlays for the whole government.";
    return { label: COST_STATUS_LABELS.root_total, detail };
  }
  if (status === "official") {
    return {
      label: COST_STATUS_LABELS.official,
      detail: "Matched an official Treasury rollup for this organization.",
    };
  }
  if (status === "scaled_official") {
    return {
      label: COST_STATUS_LABELS.scaled_official,
      detail: "Official rollup scaled to fit inside the parent total without double counting.",
    };
  }
  if (status === "allocated") {
    const basis = String(data?.cost_basis || "").toLowerCase();
    const detail =
      basis === "employee_weight"
        ? "Estimated from parent totals using employee weighting."
        : basis === "budget_weight"
          ? "Estimated from parent totals using known budget weighting."
          : basis === "subtree_weight"
            ? "Estimated from parent totals using subtree-size weighting."
            : "Estimated from parent totals so every node has a value.";
    return {
      label: COST_STATUS_LABELS.allocated,
      detail,
    };
  }
  if (Number.isFinite(Number(data?.rollup_total_amount)) && Number(data.rollup_total_amount) !== 0) {
    return {
      label: COST_STATUS_LABELS.official,
      detail: "Using the matched rollup total on this node.",
    };
  }
  if (Number.isFinite(Number(data?.resolved_total_amount)) && Number(data.resolved_total_amount) !== 0) {
    return {
      label: "Resolved Cost",
      detail: "Computed final cost for display.",
    };
  }
  return {
    label: COST_STATUS_LABELS.unavailable,
    detail: "No resolved cost is currently assigned to this node.",
  };
}

function getBudgetBasisLabel(data) {
  return [
    data.source_system || data.budget_source,
    humanizeMetadataValue(data.amount_kind, AMOUNT_KIND_LABELS),
    data.budget_year,
    data.budget_as_of,
    humanizeMetadataValue(data.cost_basis, COST_BASIS_LABELS),
    humanizeMetadataValue(data.cost_validation, COST_VALIDATION_LABELS),
  ].filter(Boolean).join(" | ");
}

function getNodeSelectionCostContext(nodeObj) {
  if (!nodeObj?.data) {
    return null;
  }

  const selectedTotal = Number(nodeObj.data.__meta?.subtreeCost || 0);
  if (Number.isFinite(selectedTotal) && selectedTotal !== 0) {
    return {
      amount: selectedTotal,
      inherited: false,
      nodeName: nodeObj.data.name,
      label: "selected total",
    };
  }

  let cursor = nodeObj.parent;
  while (cursor) {
    const explicitRollup = Number(cursor.data?.__meta?.explicitRollupCost || 0);
    const directCost = Number(cursor.data?.__meta?.directCost || 0);
    const ancestorAmount = explicitRollup !== 0 ? explicitRollup : directCost;
    if (Number.isFinite(ancestorAmount) && ancestorAmount !== 0) {
      return {
        amount: ancestorAmount,
        inherited: true,
        nodeName: cursor.data?.name || "Parent branch",
        label: "nearest funded branch",
      };
    }
    cursor = cursor.parent;
  }

  return null;
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

function updateBuildBadge(stats = state.graph?.getStats?.()) {
  if (!dom.buildBadge) {
    return;
  }

  const version = window.APP_BUILD_INFO?.version || "dev";
  const label = window.APP_BUILD_INFO?.label || "active build";
  const totalNodes = Number.isFinite(stats?.totalNodeCount) ? stats.totalNodeCount.toLocaleString() : "loading";
  const totalCost = Number.isFinite(Number(stats?.totalBudgetCost)) && Number(stats.totalBudgetCost) !== 0
    ? formatCurrency(stats.totalBudgetCost)
    : "cost pending";
  setText(dom.buildBadge, `Build ${version} | ${totalNodes} nodes | ${totalCost} | ${label}`);
}

function updateStats(stats) {
  updateBuildBadge(stats);
  const loadedCount = Number.isFinite(stats.visibleNodeCount) ? stats.visibleNodeCount : 0;
  const totalCount = Number.isFinite(stats.totalNodeCount) ? stats.totalNodeCount : loadedCount;
  setText(dom.nodeCounter, `${loadedCount.toLocaleString()} / ${totalCount.toLocaleString()} nodes loaded`);
  setText(
    dom.statsTotal,
    `${stats.totalNodeCount.toLocaleString()} total nodes${stats.candidateNodeCount ? ` | ${stats.candidateNodeCount.toLocaleString()} candidates` : ""}`,
  );
  const fullExpandLabel = stats.fullExpandRenderMode ? " | full-expansion render active" : "";
  setText(
    dom.statsLoaded,
    `${loadedCount.toLocaleString()} eligible under current filters | ${stats.visibleNodeCount.toLocaleString()} loaded in memory | ${(stats.hiddenCandidateCount || 0).toLocaleString()} candidate nodes hidden | ${stats.lodLabel || "Universe View"} | ${(stats.densityHiddenNodeCount || 0).toLocaleString()} density-hidden${fullExpandLabel}`,
  );
  setText(
    dom.statsDepth,
    `LOD ${stats.lodLevel ?? "?"}: ${stats.lodLabel || "Unknown"} | depth ${Number.isFinite(stats.maxVisibleDepth) ? stats.maxVisibleDepth : "All"} | queue ${stats.pendingExpansions ?? 0}`,
  );
  if (dom.statsCost) {
    const fytd = getBudgetFytdContext(stats.budgetSummary);
    const operationSummary = fytd
      ? `${formatCurrency(stats.totalBudgetCost)} FYTD through ${fytd.recordDate} | est. ${formatCurrency(fytd.annualized)}/yr`
      : `${formatCurrency(stats.totalBudgetCost)} ${stats.totalBudgetLabel || "total cost"}`;
    const selectedContext = getNodeSelectionCostContext(state.graph?.getSelectedNode?.());
    if (selectedContext?.amount && Number.isFinite(selectedContext.amount)) {
      const selectionSummary = selectedContext.inherited
        ? `selection inherits ${formatCurrency(selectedContext.amount)} from ${truncateLabel(selectedContext.nodeName)}`
        : `selection total ${formatCurrency(selectedContext.amount)}`;
      setText(dom.statsCost, `${operationSummary} | ${selectionSummary}`);
    } else {
      setText(dom.statsCost, `${operationSummary} | selection cost unavailable`);
    }
  }
}

function hideLoadingOverlay(delay = 600) {
  if (!dom.loading) {
    return;
  }
  dom.loading.style.opacity = "0";
  window.setTimeout(() => {
    if (dom.loading?.parentElement) {
      dom.loading.remove();
    }
  }, delay);
}

function handleUiFailure(error, message = "UI failed to initialize. Open browser console for details.") {
  console.error(message, error);
  setText(dom.loadStatus, message);
  hideLoadingOverlay();
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

  const tabSources = document.getElementById("tab-sources");
  (tabSources || dom.infoPanel).appendChild(verificationWrap);
  dom.verificationWrap = verificationWrap;
  dom.verificationBadge = badge;
  dom.verificationStatus = status;
  dom.verificationConfidence = confidence;
  dom.verificationSources = sources;
  dom.verificationLastVerified = lastVerified;

  // Tab switching
  dom.infoPanel.querySelectorAll(".info-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      dom.infoPanel.querySelectorAll(".info-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      const detailsEl = document.getElementById("tab-details");
      const costEl = document.getElementById("tab-cost");
      const sourcesEl = document.getElementById("tab-sources");
      if (detailsEl) detailsEl.style.display = tab === "details" ? "" : "none";
      if (costEl) costEl.style.display = tab === "cost" ? "" : "none";
      if (sourcesEl) sourcesEl.style.display = tab === "sources" ? "" : "none";
    });
  });
}

function getVerificationBadgeConfig(data, evidence = getNodeVerificationEvidence(data)) {
  if (data.isCandidate) {
    return { label: "CANDIDATE", bg: "rgba(155,139,189,0.18)", border: "#9b8bbd", color: "#d6caef" };
  }
  if (!evidence.hasDirectEvidence && evidence.hasInheritedEvidence) {
    return { label: "INHERITED", bg: "rgba(217,181,94,0.18)", border: "#d9b55e", color: "#f2deb3" };
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

  const wrap = document.createElement("div");
  wrap.style.position = "fixed";
  wrap.style.top = "315px";
  wrap.style.left = "32px";
  wrap.style.zIndex = "20";
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "6px";

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
  const toggleCandidates = makeToggle("Show Unconfirmed Nodes (candidates)");
  toggleCandidates.checked = false;

  document.body.appendChild(wrap);
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

  const baseStatus = String(data.verificationStatus || "unverified").toUpperCase();
  const status = data.isCandidate ? `CANDIDATE · ${baseStatus}` : baseStatus;
  const confidence = Number(data.confidenceScore || 0);
  const sourceUrls = Array.isArray(data.sourceUrls) ? data.sourceUrls : [];
  const sourceTypes = Array.isArray(data.sourceTypes) ? data.sourceTypes : [];
  const badge = getVerificationBadgeConfig(data);

  setText(dom.verificationBadge, badge.label);
  dom.verificationBadge.style.background = badge.bg;
  dom.verificationBadge.style.border = `1px solid ${badge.border}`;
  dom.verificationBadge.style.color = badge.color;

  setText(dom.verificationStatus, `Verification Status: ${status}`);
  setText(dom.verificationConfidence, `Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) · Sources: ${Number(data.sourceCount || sourceUrls.length)}`);
  setText(
    dom.verificationLastVerified,
    `Last Verified: ${data.lastVerified ? new Date(data.lastVerified).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Not yet verified"}`,
  );

  dom.verificationSources.replaceChildren();
  const sourcesLabel = document.createElement("div");
  sourcesLabel.textContent = "Sources";
  sourcesLabel.style.marginTop = "6px";
  sourcesLabel.style.color = "#d4c4a1";
  dom.verificationSources.appendChild(sourcesLabel);

  if (sourceUrls.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "No confirming sources recorded.";
    empty.style.color = "#8f7a5d";
    dom.verificationSources.appendChild(empty);
    return;
  }

  sourceUrls.forEach((url, index) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    let host = url;
    try {
      host = new URL(url).hostname;
    } catch (_error) {
      host = url;
    }
    link.textContent = `• ${host}${sourceTypes[index] ? ` (${sourceTypes[index]})` : ""}`;
    link.style.color = "#d4c4a1";
    dom.verificationSources.appendChild(link);
  });
}

function renderVerificationPanelWithEvidence(data) {
  if (!dom.verificationWrap) {
    return;
  }

  const evidence = getNodeVerificationEvidence(data);
  const baseStatus = String(data.verificationStatus || "unverified").toUpperCase();
  const status = data.isCandidate
    ? `CANDIDATE Â· ${baseStatus}`
    : !evidence.hasDirectEvidence && evidence.hasInheritedEvidence
      ? `INHERITED EVIDENCE Â· ${evidence.inheritedEvidenceNodeCount.toLocaleString()} sourced descendants`
      : baseStatus;
  const confidence = Number(data.confidenceScore || 0);
  const sourceUrls = evidence.hasDirectEvidence ? evidence.directSourceUrls : evidence.branchSourceUrls;
  const sourceTypes = Array.isArray(data.sourceTypes) ? data.sourceTypes : [];
  const badge = getVerificationBadgeConfig(data, evidence);

  setText(dom.verificationBadge, badge.label);
  dom.verificationBadge.style.background = badge.bg;
  dom.verificationBadge.style.border = `1px solid ${badge.border}`;
  dom.verificationBadge.style.color = badge.color;

  setText(dom.verificationStatus, `Verification Status: ${status}`);
  setText(
    dom.verificationConfidence,
    evidence.hasDirectEvidence
      ? `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) Â· Direct Sources: ${evidence.directSourceCount.toLocaleString()} Â· Branch Evidence: ${evidence.branchSourceCount.toLocaleString()} refs across ${evidence.branchEvidenceNodeCount.toLocaleString()} nodes`
      : evidence.hasInheritedEvidence
        ? `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) Â· Inherited Evidence: ${evidence.inheritedSourceCount.toLocaleString()} refs across ${evidence.inheritedEvidenceNodeCount.toLocaleString()} descendants Â· Verified in Branch: ${evidence.branchVerifiedNodeCount.toLocaleString()}`
        : `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) Â· Direct Sources: 0`,
  );
  setText(
    dom.verificationLastVerified,
    `Last Verified: ${data.lastVerified ? new Date(data.lastVerified).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Not yet verified"}`,
  );

  dom.verificationSources.replaceChildren();
  const sourcesLabel = document.createElement("div");
  sourcesLabel.textContent = evidence.hasDirectEvidence ? "Direct Sources" : evidence.hasInheritedEvidence ? "Branch Evidence" : "Sources";
  sourcesLabel.style.marginTop = "6px";
  sourcesLabel.style.color = "#d4c4a1";
  dom.verificationSources.appendChild(sourcesLabel);

  if (sourceUrls.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = evidence.hasInheritedEvidence
      ? "No direct sources on this node. Branch evidence exists but no sample links were available."
      : "No confirming sources recorded.";
    empty.style.color = "#8f7a5d";
    dom.verificationSources.appendChild(empty);
    return;
  }

  sourceUrls.forEach((url, index) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    let host = url;
    try {
      host = new URL(url).hostname;
    } catch (_error) {
      host = url;
    }
    const sourceTypeLabel = evidence.hasDirectEvidence ? sourceTypes[index] : "branch evidence";
    link.textContent = `â€¢ ${host}${sourceTypeLabel ? ` (${sourceTypeLabel})` : ""}`;
    link.style.color = "#d4c4a1";
    dom.verificationSources.appendChild(link);
  });
}

function renderVerificationPanelWithEvidenceClean(data) {
  if (!dom.verificationWrap) {
    return;
  }

  const evidence = getNodeVerificationEvidence(data);
  const baseStatus = String(data.verificationStatus || "unverified").toUpperCase();
  const status = data.isCandidate
    ? `CANDIDATE - ${baseStatus}`
    : !evidence.hasDirectEvidence && evidence.hasInheritedEvidence
      ? `INHERITED EVIDENCE - ${evidence.inheritedEvidenceNodeCount.toLocaleString()} sourced descendants`
      : baseStatus;
  const confidence = Number(data.confidenceScore || 0);
  const sourceUrls = evidence.hasDirectEvidence ? evidence.directSourceUrls : evidence.branchSourceUrls;
  const sourceTypes = Array.isArray(data.sourceTypes) ? data.sourceTypes : [];
  const badge = getVerificationBadgeConfig(data, evidence);

  setText(dom.verificationBadge, badge.label);
  dom.verificationBadge.style.background = badge.bg;
  dom.verificationBadge.style.border = `1px solid ${badge.border}`;
  dom.verificationBadge.style.color = badge.color;

  setText(dom.verificationStatus, `Verification Status: ${status}`);
  setText(
    dom.verificationConfidence,
    evidence.hasDirectEvidence
      ? `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) | Direct Sources: ${evidence.directSourceCount.toLocaleString()} | Branch Evidence: ${evidence.branchSourceCount.toLocaleString()} refs across ${evidence.branchEvidenceNodeCount.toLocaleString()} nodes`
      : evidence.hasInheritedEvidence
        ? `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) | Inherited Evidence: ${evidence.inheritedSourceCount.toLocaleString()} refs across ${evidence.inheritedEvidenceNodeCount.toLocaleString()} descendants | Verified in Branch: ${evidence.branchVerifiedNodeCount.toLocaleString()}`
        : `Direct Confidence: ${confidence.toFixed(2)} (${Math.round(confidence * 100)}%) | Direct Sources: 0`,
  );
  setText(
    dom.verificationLastVerified,
    `Last Verified: ${data.lastVerified ? new Date(data.lastVerified).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Not yet verified"}`,
  );

  dom.verificationSources.replaceChildren();
  const sourcesLabel = document.createElement("div");
  sourcesLabel.textContent = evidence.hasDirectEvidence ? "Direct Sources" : evidence.hasInheritedEvidence ? "Branch Evidence" : "Sources";
  sourcesLabel.style.marginTop = "6px";
  sourcesLabel.style.color = "#d4c4a1";
  dom.verificationSources.appendChild(sourcesLabel);

  if (sourceUrls.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = evidence.hasInheritedEvidence
      ? "No direct sources on this node. Branch evidence exists but no sample links were available."
      : "No confirming sources recorded.";
    empty.style.color = "#8f7a5d";
    dom.verificationSources.appendChild(empty);
    return;
  }

  const SOURCE_TYPE_LABELS = {
    official_directory: "Official Website",
    wikidata: "Wikidata",
    federal_register: "Federal Register",
    usaspending: "USAspending.gov",
    treasury: "Treasury Fiscal Data",
    enrichment: "Pipeline Enrichment",
  };

  sourceUrls.forEach((url, index) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    let host = url;
    try {
      host = new URL(url).hostname;
    } catch (_error) {
      host = url;
    }
    const rawType = evidence.hasDirectEvidence ? sourceTypes[index] : "branch evidence";
    const sourceTypeLabel = SOURCE_TYPE_LABELS[rawType] || rawType;
    const lastVerifiedStr =
      index === 0 && data.lastVerified
        ? ` · ${new Date(data.lastVerified).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}`
        : "";
    link.textContent = `* ${host}${sourceTypeLabel ? ` (${sourceTypeLabel})` : ""}${lastVerifiedStr}`;
    link.style.color = "#d4c4a1";
    dom.verificationSources.appendChild(link);
  });
}

function copyShareLink(nodeId) {
  const url = new URL(window.location.href);
  url.searchParams.set("node", nodeId);
  navigator.clipboard.writeText(url.toString()).then(() => {
    if (dom.btnCopyShareLink) {
      const orig = dom.btnCopyShareLink.textContent;
      setText(dom.btnCopyShareLink, "Copied!");
      window.setTimeout(() => setText(dom.btnCopyShareLink, orig), 1800);
    }
  }).catch(() => {
    // Fallback: show the URL in a prompt so user can copy manually
    window.prompt("Share link (copy manually):", url.toString());
  });
}

function parseShareLink() {
  const params = new URLSearchParams(window.location.search);
  const nodeId = params.get("node");
  if (nodeId) {
    // Defer until graph is ready
    window.requestAnimationFrame(function tryReveal() {
      if (!state.graph) {
        window.requestAnimationFrame(tryReveal);
        return;
      }
      revealAndSelect(nodeId);
    });
  }
}

function getNodeCostBreakdown(nodeObj) {
  if (!nodeObj?.data) {
    return null;
  }
  const data = nodeObj.data;
  const resolvedTotal = Number(data.__meta?.subtreeCost || data.resolved_total_amount || 0);
  const directOutlay = Number(data.direct_outlay_amount || 0);
  const rollupTotal = Number(data.rollup_total_amount || 0);
  const directMetaCost = Number(data.__meta?.directCost || 0);
  const operationTotal = Number(state.graph?.getStats?.().totalBudgetCost || 0);
  const share = operationTotal > 0 && resolvedTotal > 0
    ? (resolvedTotal / operationTotal) * 100
    : null;
  const costType = getCostTypeDetails(data);
  const budgetBasis = getBudgetBasisLabel(data);
  return {
    resolvedTotal,
    directOutlay,
    rollupTotal,
    directMetaCost,
    operationTotal,
    share,
    costType,
    budgetBasis,
    costStatus: data.cost_status || null,
    costBasis: data.cost_basis || null,
    costValidation: data.cost_validation || null,
    budgetSource: data.budget_source || data.source_system || null,
    budgetYear: data.budget_year || null,
    amountKind: data.amount_kind || null,
    budgetSummary: state.graph?.getStats?.()?.budgetSummary || null,
  };
}

function renderCostTab(nodeObj) {
  const el = document.getElementById("tab-cost");
  if (!el) {
    return;
  }
  dom.costTabEl = el;
  el.replaceChildren();

  if (!nodeObj?.data) {
    const empty = document.createElement("div");
    empty.textContent = "Select a node to see cost details.";
    empty.style.color = "#6a5a3a";
    empty.style.fontSize = "10px";
    el.appendChild(empty);
    return;
  }

  const breakdown = getNodeCostBreakdown(nodeObj);
  if (!breakdown) {
    return;
  }

  const frag = document.createDocumentFragment();

  // Cost confidence badge
  const costBadgeConfig = {
    root_total: { label: "TREASURY TOTAL", bg: "rgba(111,207,151,0.18)", border: "#6fcf97", color: "#c8f2d7" },
    official: { label: "OFFICIAL ROLLUP", bg: "rgba(111,207,151,0.18)", border: "#6fcf97", color: "#c8f2d7" },
    scaled_official: { label: "OFFICIAL (SCALED)", bg: "rgba(217,181,94,0.18)", border: "#d9b55e", color: "#f2deb3" },
    allocated: { label: "ESTIMATED", bg: "rgba(142,125,98,0.18)", border: "#8e7d62", color: "#d6c7af" },
    unavailable: { label: "UNAVAILABLE", bg: "rgba(80,60,60,0.18)", border: "#6a4040", color: "#a08080" },
  };
  const badgeCfg = costBadgeConfig[breakdown.costStatus] || costBadgeConfig.unavailable;
  const badge = document.createElement("span");
  badge.className = "cost-badge";
  badge.textContent = badgeCfg.label;
  badge.style.background = badgeCfg.bg;
  badge.style.border = `1px solid ${badgeCfg.border}`;
  badge.style.color = badgeCfg.color;
  frag.appendChild(badge);

  const makeRow = (label, value) => {
    const row = document.createElement("div");
    row.className = "info-stat";
    const lbl = document.createElement("span");
    lbl.className = "info-stat-label";
    lbl.textContent = label;
    const val = document.createElement("span");
    val.className = "info-stat-val";
    val.textContent = value;
    row.appendChild(lbl);
    row.appendChild(val);
    return row;
  };

  // Cost type and description
  frag.appendChild(makeRow("COST TYPE", breakdown.costType.label));

  // Main cost figures
  if (breakdown.resolvedTotal) {
    frag.appendChild(makeRow("TOTAL (SUBTREE)", formatCurrency(breakdown.resolvedTotal)));
  }
  if (breakdown.directOutlay) {
    frag.appendChild(makeRow("DIRECT OUTLAY", formatCurrency(breakdown.directOutlay)));
  }
  if (breakdown.rollupTotal) {
    frag.appendChild(makeRow("OFFICIAL ROLLUP", formatCurrency(breakdown.rollupTotal)));
  }
  if (breakdown.directMetaCost && breakdown.directMetaCost !== breakdown.directOutlay) {
    frag.appendChild(makeRow("DIRECT COST (COMPUTED)", formatCurrency(breakdown.directMetaCost)));
  }

  // Share of government
  if (breakdown.share !== null) {
    frag.appendChild(makeRow("SHARE OF TOTAL", `${breakdown.share.toFixed(breakdown.share < 0.01 ? 4 : 2)}%`));

    // Bar
    const barWrap = document.createElement("div");
    barWrap.className = "cost-bar";
    const barFill = document.createElement("div");
    barFill.className = "cost-bar-fill";
    barFill.style.width = `${Math.min(100, breakdown.share)}%`;
    barFill.style.background = badgeCfg.border;
    barWrap.appendChild(barFill);
    frag.appendChild(barWrap);
  }

  // Methodology
  const methodTitle = document.createElement("div");
  methodTitle.className = "cost-section-title";
  methodTitle.style.marginTop = "12px";
  methodTitle.textContent = "COST METHODOLOGY";
  frag.appendChild(methodTitle);

  frag.appendChild(makeRow("METHODOLOGY", breakdown.costType.detail || "—"));
  if (breakdown.costBasis) {
    frag.appendChild(makeRow("ALLOCATION BASIS", humanizeMetadataValue(breakdown.costBasis, COST_BASIS_LABELS)));
  }
  if (breakdown.costValidation) {
    frag.appendChild(makeRow("VALIDATION", humanizeMetadataValue(breakdown.costValidation, COST_VALIDATION_LABELS)));
  }

  // Source metadata
  const sourceTitle = document.createElement("div");
  sourceTitle.className = "cost-section-title";
  sourceTitle.style.marginTop = "12px";
  sourceTitle.textContent = "SOURCE";
  frag.appendChild(sourceTitle);

  if (breakdown.budgetSource) {
    frag.appendChild(makeRow("SOURCE SYSTEM", breakdown.budgetSource));
  }
  if (breakdown.budgetYear) {
    frag.appendChild(makeRow("FISCAL YEAR", String(breakdown.budgetYear)));
  }
  if (breakdown.amountKind) {
    frag.appendChild(makeRow("AMOUNT KIND", humanizeMetadataValue(breakdown.amountKind, AMOUNT_KIND_LABELS)));
  }

  // FYTD context
  const fytd = getBudgetFytdContext(breakdown.budgetSummary);
  if (fytd) {
    frag.appendChild(makeRow("FYTD RECORD DATE", fytd.recordDate));
    frag.appendChild(makeRow("MONTHS ELAPSED", `${fytd.monthsElapsed} / 12`));
    frag.appendChild(makeRow("ANNUALIZED EST.", formatCurrency(fytd.annualized)));
  }

  el.appendChild(frag);
}

function exportSubtreeJson(nodeObj) {
  if (!nodeObj?.data) {
    return;
  }

  function collectNodes(obj) {
    const result = [obj.data];
    for (const child of obj.childObjs) {
      result.push(...collectNodes(child));
    }
    return result;
  }

  const nodes = collectNodes(nodeObj);
  const exportData = {
    exportedAt: new Date().toISOString(),
    rootNode: nodeObj.data.id,
    nodeCount: nodes.length,
    nodes,
  };

  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  const safeName = (nodeObj.data.name || nodeObj.data.id || "branch").replace(/[^a-z0-9_-]/gi, "_").toLowerCase().slice(0, 40);
  link.download = `bureaucracy_${safeName}_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
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

function resetInfoTabs() {
  const detailsEl = document.getElementById("tab-details");
  const costEl = document.getElementById("tab-cost");
  const sourcesEl = document.getElementById("tab-sources");
  if (detailsEl) detailsEl.style.display = "";
  if (costEl) costEl.style.display = "none";
  if (sourcesEl) sourcesEl.style.display = "none";
  document.querySelectorAll(".info-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === "details");
  });
}

function renderInfoPanel(nodeObj) {
  if (!nodeObj) {
    return;
  }

  resetInfoTabs();
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
  const statRows = [];
  const costType = getCostTypeDetails(data);
  if (data.employees) {
    statRows.push(["EMPLOYEES", data.employees]);
  }
  if (costType.label) {
    statRows.push(["COST TYPE", costType.label]);
  }
  if (costType.detail) {
    statRows.push(["COST DETAIL", costType.detail]);
  }
  const directCostLabel = getDirectCostLabel(data);
  if (directCostLabel) {
    statRows.push(["DIRECT COST", directCostLabel]);
  }
  if (data.budget_source || data.budget_year || data.source_system || data.budget_as_of || data.amount_kind || data.cost_status || data.cost_basis || data.cost_validation) {
    const budgetBasis = getBudgetBasisLabel(data);
    statRows.push(["BUDGET BASIS", budgetBasis]);
  }
  const totalCost = Number(data.__meta?.subtreeCost || 0);
  const operationCost = Number(state.graph?.getStats?.().totalBudgetCost || 0);
  const selectionCostContext = getNodeSelectionCostContext(nodeObj);
  if (Number.isFinite(totalCost) && totalCost !== 0) {
    statRows.push(["TOTAL COST", formatCurrency(totalCost)]);
  } else if (selectionCostContext?.inherited) {
    statRows.push([
      "NEAREST FUNDED BRANCH",
      `${selectionCostContext.nodeName} | ${formatCurrency(selectionCostContext.amount)}`,
    ]);
  }
  if (operationCost > 0) {
    const share = Number.isFinite(totalCost) && totalCost !== 0
      ? `${((totalCost / operationCost) * 100).toFixed(totalCost === operationCost ? 0 : 2)}%`
      : "0%";
    const budgetSummary = state.graph?.getStats?.()?.budgetSummary;
    const fytd = getBudgetFytdContext(budgetSummary);
    const operationLabel = fytd
      ? `${formatCurrency(operationCost)} FYTD (est. ${formatCurrency(fytd.annualized)}/yr) · ${share}`
      : `${formatCurrency(operationCost)} · ${share}`;
    statRows.push(["WHOLE OPERATION", operationLabel]);
  }
  if (data.budget_source || data.budget_year || data.source_system || data.budget_as_of || data.amount_kind || data.cost_status || data.cost_basis || data.cost_validation) {
    const budgetBasisRow = statRows.find((row) => row[0] === "BUDGET BASIS");
    if (budgetBasisRow) {
      budgetBasisRow[1] = getBudgetBasisLabel(data);
    }
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
        window.setTimeout(() => {
          const revealed = state.graph.getNodeById(child.id);
          if (revealed) {
            state.graph.setSelectedNode(revealed);
          }
        }, 750);
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
  renderVerificationPanelWithEvidenceClean(data);
  renderCostTab(nodeObj);
  renderBreadcrumb(nodeObj);

  // Show export button only when node has loaded children
  if (dom.btnExportJson) {
    dom.btnExportJson.style.display = nodeObj.childObjs && nodeObj.childObjs.length > 0 ? "block" : "none";
  }
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
    const status = match.isCandidate ? "CANDIDATE" : String(match.verificationStatus || "unverified").toUpperCase();
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

function revealAndSelect(id) {
  const nodeObj = state.graph.revealNodeById(id, true);
  const settle = () => {
    const revealed = nodeObj || state.graph.getNodeById(id);
    if (revealed) {
      state.graph.setSelectedNode(revealed);
      return;
    }
    window.requestAnimationFrame(settle);
  };
  window.requestAnimationFrame(settle);
}

function stopProgressiveExpansion() {
  state.expandCancelled = true;
  if (state.expandFrame) {
    window.cancelAnimationFrame(state.expandFrame);
    state.expandFrame = 0;
  }
  state.graph.setFullExpandRenderMode(false);
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
  const vrActive = state.graph.isVrSessionActive?.() || false;
  const selected = state.graph.getSelectedNode();
  const vrExpandDepthLimit = state.graph.getConfig?.().VR_EXPAND_ALL_DEPTH_LIMIT || 4;
  const effectiveTargetDepth = vrActive && !Number.isFinite(targetDepth)
    ? Math.min((selected?.depth || 0) + vrExpandDepthLimit, state.graph.getMaxDataDepth(), state.graph.getConfig().MAX_DEPTH)
    : targetDepth;

  state.graph.setFullExpandRenderMode(!vrActive);
  dom.btnExpandAll.disabled = true;
  setText(dom.btnExpandAll, "Expanding…");
  dom.btnCancelExpand.style.display = "block";

  const totalLevels = Math.min(
    Number.isFinite(effectiveTargetDepth) ? effectiveTargetDepth : state.graph.getMaxDataDepth(),
    state.graph.getConfig().MAX_DEPTH,
  );

  const tick = () => {
    if (state.expandCancelled) {
      hideLoader(0);
      return;
    }

    const frontier = state.graph.getFrontier(effectiveTargetDepth);
    if (frontier.nodes.length === 0) {
      if (state.graph.hasPendingExpansions()) {
        showLoader("Loading queued nodes…");
        state.expandFrame = window.requestAnimationFrame(tick);
        return;
      }
      const finalStats = state.graph.getStats();
      if ((finalStats.hiddenCandidateCount || 0) > 0 && !finalStats.showCandidateNodes) {
        showLoader(`All hierarchy nodes loaded. ${finalStats.hiddenCandidateCount.toLocaleString()} candidate nodes are hidden.`);
      } else {
        showLoader("All eligible hierarchy nodes rendered.");
      }
      dom.btnCancelExpand.style.display = "none";
      dom.btnExpandAll.disabled = false;
      setText(dom.btnExpandAll, "Expand All Below");
      hideLoader((finalStats.hiddenCandidateCount || 0) > 0 && !finalStats.showCandidateNodes ? 1400 : 200);
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
      state.graph.setFullExpandRenderMode(false);
      dom.btnCancelExpand.style.display = "none";
      dom.btnExpandAll.disabled = false;
      setText(dom.btnExpandAll, "Expand All Below");
      hideLoader(900);
      renderInfoPanel(state.graph.getSelectedNode());
      return;
    }

    showLoader(vrActive
      ? `VR expanding level ${frontier.depth + 1} of ${totalLevels}…`
      : `Loading level ${frontier.depth + 1} of ${totalLevels}…`);
    progressiveRender(frontier.nodes, (nodeObj) => {
      state.graph.expandNodesBatch([nodeObj], true);
    }, () => {
      waitForExpansionDrain(() => {
        renderInfoPanel(state.graph.getSelectedNode());
        state.expandFrame = window.requestAnimationFrame(tick);
      });
    });
  };

  if (vrActive && !Number.isFinite(targetDepth)) {
    setText(dom.loadStatus, `VR mode limits Expand All to ${vrExpandDepthLimit} additional levels. Use desktop for full global expansion.`);
    showLoader(`VR mode: expanding ${vrExpandDepthLimit} levels from the selected node…`);
  } else {
    showLoader("Starting expansion…");
  }
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
    // Sync initial state: graph.js defaults showCandidateNodes to false
    state.graph.setShowCandidateNodes(dom.toggleCandidates.checked);
    dom.toggleCandidates.addEventListener("change", () => {
      state.graph.setShowCandidateNodes(dom.toggleCandidates.checked);
      updateStats(state.graph.getStats());
    });
  }

  if (dom.btnTraceOrigin) {
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
  }

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
    const selected = state.graph.getSelectedNode();
    if (!selected) {
      return;
    }
    const stats = state.graph.getStats();
    const unloaded = stats.totalNodeCount - stats.visibleNodeCount;
    if (unloaded > 500) {
      const confirmed = window.confirm(
        `Expand all below "${selected.data?.name || "selected node"}"?\n\n` +
        `~${unloaded.toLocaleString()} nodes are not yet loaded. This may be slow on large branches.\n\n` +
        `Click Cancel Expand at any time to stop.`,
      );
      if (!confirmed) {
        return;
      }
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

  document.addEventListener("pointerlockchange", () => {
    setText(dom.btnFlyMode, state.graph?.isFlyMode() ? "Disable Fly Mode" : "Enable Fly Mode");
  });

  dom.btnCollapse.addEventListener("click", () => {
    const selected = state.graph.getSelectedNode();
    if (!selected) {
      return;
    }
    state.graph.setFullExpandRenderMode(false);
    state.graph.collapseNode(selected, { manual: true });
    renderInfoPanel(selected);
  });

  if (dom.btnHome) {
    dom.btnHome.addEventListener("click", () => {
      state.graph.navigateToRoot();
      setText(dom.btnFlyMode, "Enable Fly Mode");
    });
  }

  if (dom.btnResetCamera) {
    dom.btnResetCamera.addEventListener("click", () => {
      state.graph.resetCamera();
      setText(dom.btnFlyMode, "Enable Fly Mode");
    });
  }

  if (dom.btnFitBranch) {
    dom.btnFitBranch.addEventListener("click", () => {
      const selected = state.graph.getSelectedNode();
      if (selected) {
        state.graph.fitBranch(selected);
      }
    });
  }

  if (dom.btnCollapseAll) {
    dom.btnCollapseAll.addEventListener("click", () => {
      stopProgressiveExpansion();
      state.graph.collapseAll();
      const root = state.graph.getRootNode();
      if (root) {
        state.graph.setSelectedNode(root);
      }
      updateStats(state.graph.getStats());
    });
  }

  if (dom.btnCopyShareLink) {
    dom.btnCopyShareLink.addEventListener("click", () => {
      const selected = state.graph.getSelectedNode();
      if (selected?.data?.id) {
        copyShareLink(selected.data.id);
      } else {
        copyShareLink("the-constitution-of-the-united-states");
      }
    });
  }

  if (dom.btnExportJson) {
    dom.btnExportJson.addEventListener("click", () => {
      const selected = state.graph.getSelectedNode();
      if (selected) {
        exportSubtreeJson(selected);
      }
    });
  }

  // Branch filter buttons
  document.querySelectorAll(".branch-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".branch-btn").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      const branch = button.dataset.branch === "all" ? null : button.dataset.branch;
      state.graph.filterByBranch(branch);
      updateStats(state.graph.getStats());
    });
  });

  document.querySelectorAll(".depth-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".depth-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const depth = button.dataset.depth === "all" ? Infinity : Number(button.dataset.depth);
      if (Number.isFinite(depth)) {
        state.graph.setFullExpandRenderMode(false);
      }
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
    for (const item of state.searchIndex) {
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

const INTRO_KEY = "bureaucracy_intro_v1";
const introOverlay = document.getElementById("intro-overlay");
if (introOverlay && !localStorage.getItem(INTRO_KEY)) {
  introOverlay.style.display = "flex";
}
function dismissIntro(autoExpand) {
  localStorage.setItem(INTRO_KEY, "1");
  if (introOverlay) introOverlay.style.display = "none";
  if (autoExpand && state.graph) {
    const root = state.graph.getNodeById("the-constitution-of-the-united-states");
    if (root) state.graph.expandNode(root, true);
  }
}
document.getElementById("btn-intro-start")?.addEventListener("click", () => dismissIntro(true));
document.getElementById("btn-intro-skip")?.addEventListener("click", () => dismissIntro(false));
if (introOverlay) {
  introOverlay.addEventListener("click", (e) => {
    if (e.target === introOverlay) dismissIntro(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && introOverlay.style.display !== "none") dismissIntro(false);
  });
}

function initUI() {
  updateBuildBadge();
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
      safeUiCall("renderInfoPanel", renderInfoPanel, nodeObj);
      safeUiCall("updateStats", updateStats, state.graph.getStats());
    },
    onHover: (payload) => safeUiCall("updateTooltip", updateTooltip, payload),
    onCountsChange: (stats) => safeUiCall("updateStats", updateStats, stats),
  });

  const data = await loadMergedGraphData({
    baseUrl: window.GRAPH_DATA_SOURCES?.base || "./output/graph.json",
    corporateUrl: window.GRAPH_DATA_SOURCES?.corporate || "./data_expansion/corporate_expansion.json",
    onStatus: (message) => setText(dom.loadStatus, message),
  });
  state.graph.loadData(data);
  state.vrMode = createVrMode({
    graph: state.graph,
    button: dom.btnVr,
    onStatus: (message) => {
      if (message) {
        setText(dom.loadStatus, message);
      }
    },
    onError: (error) => {
      console.error("VR mode failed", error);
      setText(dom.loadStatus, "VR mode unavailable.");
    },
  });
  await state.vrMode.init();
  state.searchIndex = state.graph.getSearchIndex();
  safeInitUI();
  hideLoadingOverlay();
  parseShareLink();
}

if (shouldBootUi) {
  initGraphApp().catch((error) => {
    console.error(error);
    const message = window.location.protocol === "file:"
      ? "Failed to load explorer data. Open this page through a local web server, not file://."
      : "Failed to load explorer data.";
    setText(dom.loadStatus, message);
    hideLoadingOverlay();
  });
}
