import { createGovernmentGraph } from "./graph.js?v=20260312c";
import { loadMergedGraphData } from "./graphLoader.js?v=20260312c";

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
  const loadedCount = Number.isFinite(stats.loadedDisplayNodeCount) ? stats.loadedDisplayNodeCount : stats.visibleNodeCount;
  const eligibleTotal = Number.isFinite(stats.eligibleTotalNodeCount) ? stats.eligibleTotalNodeCount : stats.totalNodeCount;
  setText(dom.nodeCounter, `${loadedCount.toLocaleString()} / ${eligibleTotal.toLocaleString()} nodes loaded`);
  setText(dom.statsTotal, `${stats.totalNodeCount.toLocaleString()} total nodes`);
  setText(
    dom.statsLoaded,
    `${loadedCount.toLocaleString()} eligible under current filters | ${stats.visibleNodeCount.toLocaleString()} loaded in memory | ${(stats.hiddenCandidateCount || 0).toLocaleString()} candidate nodes hidden | ${stats.lodLabel || "Universe View"} | ${(stats.densityHiddenNodeCount || 0).toLocaleString()} density-hidden`,
  );
  setText(
    dom.statsDepth,
    `LOD ${stats.lodLevel ?? "?"}: ${stats.lodLabel || "Unknown"} | depth ${Number.isFinite(stats.maxVisibleDepth) ? stats.maxVisibleDepth : "All"} | queue ${stats.pendingExpansions ?? 0}`,
  );
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

  dom.infoPanel.appendChild(verificationWrap);
  dom.verificationWrap = verificationWrap;
  dom.verificationBadge = badge;
  dom.verificationStatus = status;
  dom.verificationConfidence = confidence;
  dom.verificationSources = sources;
  dom.verificationLastVerified = lastVerified;
}

function getVerificationBadgeConfig(data) {
  if (data.isCandidate) {
    return { label: "CANDIDATE", bg: "rgba(155,139,189,0.18)", border: "#9b8bbd", color: "#d6caef" };
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
  wrap.style.top = "130px";
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
  const toggleCandidates = makeToggle("Show Candidate Nodes");
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

  const status = data.isCandidate ? "CANDIDATE" : String(data.verificationStatus || "unverified").toUpperCase();
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
  const statRows = [];
  if (data.employees) {
    statRows.push(["EMPLOYEES", data.employees]);
  }
  if (data.budget) {
    statRows.push(["BUDGET", data.budget]);
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
      const finalStats = state.graph.getStats();
      if ((finalStats.hiddenCandidateCount || 0) > 0 && !finalStats.showCandidateNodes) {
        showLoader(`All hierarchy nodes loaded. ${finalStats.hiddenCandidateCount.toLocaleString()} candidate nodes are hidden.`);
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

function initUI() {
  ensureOriginUi();
  ensureVerificationUi();
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
    onSelect: (nodeObj) => safeUiCall("renderInfoPanel", renderInfoPanel, nodeObj),
    onHover: (payload) => safeUiCall("updateTooltip", updateTooltip, payload),
    onCountsChange: (stats) => safeUiCall("updateStats", updateStats, stats),
  });

  const data = await loadMergedGraphData({
    baseUrl: window.GRAPH_DATA_SOURCES?.base || "./data/federal_gov_complete_1.json",
    corporateUrl: window.GRAPH_DATA_SOURCES?.corporate || "./data_expansion/corporate_expansion.json",
    onStatus: (message) => setText(dom.loadStatus, message),
  });
  state.graph.loadData(data);
  state.searchIndex = state.graph.getSearchIndex();
  safeInitUI();
  hideLoadingOverlay();
}

if (shouldBootUi) {
  initGraphApp().catch((error) => {
    console.error(error);
    setText(dom.loadStatus, "Failed to load explorer data.");
    hideLoadingOverlay();
  });
}
