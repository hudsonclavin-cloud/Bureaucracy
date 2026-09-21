import { createGovernmentGraph } from "./graph.js?v=20260921b";
import { loadMergedGraphData } from "./graphLoader.js?v=20260921b";

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
  verificationPlacement: null,
  verificationBadge: null,
  togglesWrap: null,
  toggleUnverified: null,
  toggleCandidates: null,
  toggleExactCosts: null,
  toggleSuperseded: null,
};

const state = {
  // On by default since 2026-09-09, by the owner's decision: an apportioned
  // share is not a cost this project knows, and a number nobody measured must
  // not be the thing a reader sees first. 2.6% of nodes carry a cost a record
  // names for them — those cover 98.4% of the anchor — and a position may
  // additionally show a rate of basic pay an official source reports. Every
  // other node shows no figure at all until the reader asks for the estimate
  // by name.
  exactCostsOnly: true,
  graph: null,
  searchIndex: [],
  expandCancelled: false,
  expandFrame: 0,
  loaderTimer: null,
  tracedNodeId: null,
  revealFrame: 0,
  loadFailed: false,
};

// Per-viewer convenience only — never a source of truth. A reload used to
// lose the depth filter, both toggles and the selected node every time,
// which is why "share this view" was never possible. localStorage can throw
// (private browsing, blocked site data) and must never break the page for
// that; every call here is wrapped so a failure degrades to "nothing was
// remembered," not a broken load.
const STORAGE_KEY = "bureaucracy-view-prefs-v1";

function readStoredPrefs() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    return {};
  }
}

function writeStoredPrefs(patch) {
  try {
    const current = readStoredPrefs();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...patch }));
  } catch (error) {
    // Storage unavailable or full: the view still works, it just is not
    // remembered for next time.
  }
}

// The node id lives in the URL hash, not localStorage, because it is the
// one piece of state worth sharing with someone else, not just recalling for
// the same viewer later.
function setNodeHash(id) {
  try {
    const target = id ? `#node=${encodeURIComponent(id)}` : " ";
    window.history.replaceState(null, "", id ? target : window.location.pathname + window.location.search);
  } catch (error) {
    // A sandboxed iframe or an unusual embed can refuse history writes;
    // the selection still works, it just will not survive a reload.
  }
}

function getNodeIdFromHash() {
  const match = /^#node=(.+)$/.exec(window.location.hash);
  return match ? decodeURIComponent(match[1]) : null;
}

function setText(element, value) {
  if (element.textContent !== value) {
    element.textContent = value;
  }
}

// The breadcrumb, the children list and search results are all built as
// plain <div>/<span> elements with a click handler — real for a mouse, but
// invisible to a keyboard: nothing here got a tab stop or an Enter/Space
// handler, and none carried an accessible name beyond its own visible text
// (which a screen reader announces flatly, with no indication it is
// interactive or what clicking it does). This makes one such element behave
// like the real button it visually is, without changing how it looks.
function makeInteractiveRow(element, label, onActivate) {
  element.setAttribute("role", "button");
  element.setAttribute("tabindex", "0");
  element.setAttribute("aria-label", label);
  element.addEventListener("click", onActivate);
  element.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      onActivate(event);
    }
  });
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
  // Loaded is not drawn: the LOD tier draws only the depths it covers and
  // the density cap hides the rest, so "5,402 / 5,402 nodes rendered" was
  // printed over a screen showing depth 3. Both numbers, each named.
  const drawn = Number.isFinite(stats.drawnNodeCount) ? stats.drawnNodeCount : null;
  setText(
    dom.nodeCounter,
    `${stats.visibleNodeCount.toLocaleString()} / ${denominator.toLocaleString()} nodes loaded` +
      (drawn === null ? "" : ` · ${drawn.toLocaleString()} drawn at this view`),
  );
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
  updateDepthButtonAvailability(stats.maxDataDepth);
}

// The depth buttons are a fixed HTML list (1, 2, 3, ... 12) that does not
// know how deep the loaded tree actually goes. A button past the real depth
// used to sit there offering a level that does not exist and doing nothing
// when pressed — the control claiming more than the data supports, which is
// the one thing this project's own standing rule refuses everywhere else.
// This disables any such button instead of trimming the list by hand, so it
// self-corrects if the tree's depth ever changes on a future build.
function updateDepthButtonAvailability(maxDataDepth) {
  if (!Number.isFinite(maxDataDepth) || maxDataDepth <= 0) {
    return;
  }
  document.querySelectorAll(".depth-btn, .depth-expand-btn").forEach((button) => {
    const raw = button.dataset.depth ?? button.dataset.target;
    if (raw === "all" || raw === undefined) {
      return;
    }
    const value = Number(raw);
    if (!Number.isFinite(value)) {
      return;
    }
    // The original title is captured once so repeated calls (every stats
    // update) never compound an appended note onto itself.
    if (button.dataset.baseTitle === undefined) {
      button.dataset.baseTitle = button.title;
    }
    const exceedsData = value > maxDataDepth;
    button.disabled = exceedsData;
    button.classList.toggle("depth-btn-unavailable", exceedsData);
    button.title = exceedsData
      ? `${button.dataset.baseTitle} — this graph is only ${maxDataDepth} levels deep`
      : button.dataset.baseTitle;
  });
}

// The line every visitor reads first. It used to be a hardcoded string in
// index.html saying "Structure hand-compiled · costs are estimates
// apportioned from the Treasury total". Both halves went stale: 55 costs are
// now measured from the Monthly Treasury Statement, and nothing in the
// repository records where the hierarchy or its 5,170 descriptions came
// from, so "hand-compiled" asserts more than is known. Computing it from the
// graph means it cannot drift from the data again.
// One walk of the tree, two readers. The provenance line below and the
// "How to read this" card both describe the same graph, and the card exists
// precisely because the line is too compressed to be read cold — so they must
// never be able to disagree. Counting once and formatting twice is what makes
// that structural rather than a thing to remember.
function summariseGraph(root) {
  const count = {
    nodes: 0, measured: 0, capped: 0, receipts: 0, sourced: 0,
    placed: 0, orgEdges: 0, unreachable: 0, posts: 0, paidPosts: 0,
    allocated: 0, noFigure: 0, postsWithoutFigure: 0,
    orgs: 0, orgsSourced: 0, orgsUnread: 0, orgsHostRefuses: 0,
  };
  const stack = [root];
  while (stack.length) {
    const node = stack.pop();
    if (!node || typeof node !== "object") continue;
    count.nodes += 1;
    const status = String(node.cost_status || "");
    if (String(node.synthetic || "") === "treasury_receipts") count.receipts += 1;
    else if (status === "official" || status === "root_total") count.measured += 1;
    else if (status === "scaled_official") count.capped += 1;
    // Counted, not inferred by subtraction. "Everything that is not measured
    // is an estimate being withheld" was the old arithmetic here, and it was
    // false by a factor of seven: 650 nodes carry an apportioned share, while
    // 4,615 carry no figure at all and never will — 4,441 of them posts,
    // which have no budget to apportion, and the rest beneath a Treasury pool
    // that nets below zero. Ticking the estimates box reveals the first group
    // and does nothing for the second, so the line a visitor reads must not
    // promise 5,265 hidden numbers that do not exist.
    if (status === "allocated") count.allocated += 1;
    if (status === "unavailable" || (!status && node !== root)) count.noFigure += 1;
    if (Array.isArray(node.sourceUrls) && node.sourceUrls.length) count.sourced += 1;
    // Numerator and denominator must count the same population. The line
    // below says "organisation placements", and the denominator has always
    // excluded positions — but the numerator did not, so the 126 positions
    // the PLUM archive files under an organisation were counted in it. The
    // site published "335 of 812" where the release gate, which scopes both
    // to organisations, reported 209. Counting a position in a total
    // labelled "organisation" is the kind of quiet inflation this project
    // exists to refuse, so the type test now gates both.
    const isPost = /position/i.test(String(node.type || ""));
    if (isPost) {
      count.posts += 1;
      if (String(node.cost_validation || "") === "post_is_not_a_budget_unit") count.postsWithoutFigure += 1;
      if (reportedPayOf(node) || node.positionPayRate || node.positionStatutoryPay || node.positionReportedPay
        || gradePayOf(node)) {
        count.paidPosts += 1;
      }
    }
    if (node !== root && !isPost) {
      count.orgEdges += 1;
      if (String(node.synthetic || "") !== "treasury_receipts" && !/treasury accounting line/i.test(String(node.type || ""))) {
        // An organisation whose queued page went unread, and why. Counted
        // only where no method confirmed it by another route, so the card's
        // "could not be read" never overlaps its "carry a source".
        count.orgs += 1;
        if (Array.isArray(node.sourceUrls) && node.sourceUrls.length) count.orgsSourced += 1;
        const unread = node.verificationUnread;
        if (unread && typeof unread === "object" && !node.verificationMethod) {
          count.orgsUnread += 1;
          if (String(unread.kind || "") === "host_refuses_crawler") count.orgsHostRefuses += 1;
        }
      }
      if (node.placementVerified === true) count.placed += 1;
      if (node.placementCheckable === false) count.unreachable += 1;
    }
    for (const child of node.children || []) stack.push(child);
  }
  return count;
}

function describeProvenance(count) {
  return [
    `${(count.measured + count.receipts).toLocaleString()} costs measured from the Monthly Treasury Statement${
      count.receipts ? ` (${count.receipts.toLocaleString()} of them its own receipts lines, carried explicitly)` : ""
    }`,
    `${count.capped.toLocaleString()} capped to fit an estimated parent`,
    // The estimates are no longer shown by default, and the line a visitor
    // reads first must say so rather than counting them as if they were on
    // screen.
    `${count.allocated.toLocaleString()} apportioned estimates, withheld unless asked for`,
    `${count.noFigure.toLocaleString()} with no figure at all, ${count.postsWithoutFigure.toLocaleString()} of them posts, which have no budget to divide`,
    `${count.sourced.toLocaleString()} of ${count.nodes.toLocaleString()} nodes carry a source`,
    `${count.placed.toLocaleString()} of ${count.orgEdges.toLocaleString()} organisation placements evidenced by the parent's official page (${count.unreachable.toLocaleString()} unreachable: parent has no page)`,
    "the descriptions carry no citation",
  ].join(" · ");
}

// The same graph, said once in sentences. Every number is taken from
// `summariseGraph` rather than written here, so this card cannot claim a
// coverage the data does not have — the failure mode that made the old
// hardcoded provenance line ("costs are estimates apportioned from the
// Treasury total") wrong the day the first Treasury line landed.
function readingGuidePoints(count) {
  const others = Math.max(count.nodes - count.posts, 0);
  return [
    [
      "What you are looking at",
      `Every box is one piece of the U.S. federal government — a branch, a department, `
      + `an office, or a single job — drawn beneath whatever it sits under. `
      + `${count.nodes.toLocaleString()} in all, of which ${count.posts.toLocaleString()} are individual `
      + `posts rather than bodies with a budget, and ${others.toLocaleString()} are organisations, `
      + `committees and groupings. Click one to open its panel on the right.`,
    ],
    [
      "Most of it carries no dollar figure, and that is the point",
      `${(count.measured + count.receipts).toLocaleString()} figures here were measured: the Treasury's own `
      + `Monthly Treasury Statement names those units and states what they spent. `
      + `${count.allocated.toLocaleString()} more could be shown as a share worked out by splitting a `
      + `parent's total among its children — arithmetic, not a number anyone published — and those stay `
      + `hidden until you ask for them, with "Also show estimated shares of a parent's total" on the left. `
      + `The remaining ${count.noFigure.toLocaleString()} have no figure at all and never will; ticking `
      + `the box does not reveal a number for them, because there is none to reveal.`,
    ],
    [
      "A job is not a budget",
      `The Department of Defense spends money; the Secretary of Defense has no budget of their own. `
      + `So no position is given a share of an agency's outlays — that share is not a quantity that `
      + `exists, and it is why ${count.postsWithoutFigure.toLocaleString()} of the `
      + `${count.posts.toLocaleString()} posts show nothing under cost. `
      + `${count.paidPosts.toLocaleString()} show a rate or a base-pay range instead, and only where an official `
      + `document states one. A salary is not a budget either, and is labelled separately.`,
    ],
    [
      "“No source recorded” is the usual answer, not a glitch",
      `${count.sourced.toLocaleString()} of the ${count.nodes.toLocaleString()} entries carry a link to `
      + `a source. ${count.posts.toLocaleString()} of the entries are posts, and a post is confirmed only when `
      + `its own organisation's official page names it as a heading — most pages name no staff at all — so `
      + `"no source recorded" on a post is this site declining to claim what it cannot show, not a check `
      + `that was skipped. Of the ${count.orgs.toLocaleString()} organisations, ${count.orgsSourced.toLocaleString()} `
      + `carry a source and ${count.orgsUnread.toLocaleString()} have a page queued that could not be read`
      + `${count.orgsHostRefuses ? ` — for ${count.orgsHostRefuses.toLocaleString()} of them because the host refuses this crawler outright, which is a fact about the host and not about the unit` : ""}; `
      + `each panel says which. The written descriptions carry no citation at all, and are labelled that way `
      + `wherever they appear.`,
    ],
    [
      "Reading a panel",
      `On a cost, a solid badge means measured and an outlined one means estimated — filled against `
      + `hollow, so the difference survives colourblindness. A box's colour is the branch it belongs `
      + `to; the key is bottom-right. "Placement" is a separate line, because "this page lists it" and `
      + `"this thing exists" are different claims.`,
    ],
  ];
}

function renderReadingGuide(count) {
  const body = document.getElementById("reading-guide-body");
  const foot = document.getElementById("reading-guide-foot");
  if (!body) return;
  body.textContent = "";
  for (const [title, text] of readingGuidePoints(count)) {
    const block = document.createElement("div");
    block.className = "rg-point";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    block.appendChild(heading);
    block.appendChild(paragraph);
    body.appendChild(block);
  }
  if (foot) {
    foot.textContent =
      "Drag to orbit · scroll to zoom · click a box to select it · search at the top. "
      + "Reopen this any time with “How to read this”, under the title.";
  }
}

// Shown on a first visit and remembered as dismissed after that. The
// remembering is a per-viewer convenience like the depth filter: if
// localStorage is unavailable the card simply appears every time, which is
// the harmless failure.
function setReadingGuideOpen(open) {
  const wrap = document.getElementById("reading-guide");
  if (!wrap) return;
  wrap.classList.toggle("open", open);
  wrap.setAttribute("aria-hidden", open ? "false" : "true");
  if (open) {
    const close = document.getElementById("btn-reading-guide-close");
    if (close) close.focus();
  } else {
    writeStoredPrefs({ readingGuideDismissed: true });
    const opener = document.getElementById("btn-reading-guide");
    if (opener) opener.focus();
  }
}

function bindReadingGuide(count) {
  renderReadingGuide(count);
  const wrap = document.getElementById("reading-guide");
  const opener = document.getElementById("btn-reading-guide");
  const close = document.getElementById("btn-reading-guide-close");
  if (opener) opener.addEventListener("click", () => setReadingGuideOpen(true));
  if (close) close.addEventListener("click", () => setReadingGuideOpen(false));
  if (wrap) {
    // The backdrop closes it; a click inside the card must not.
    wrap.addEventListener("click", (event) => {
      if (event.target === wrap) setReadingGuideOpen(false);
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && wrap && wrap.classList.contains("open")) {
      event.preventDefault();
      setReadingGuideOpen(false);
    }
  });
  // Opened after the loading overlay is gone, not while it still covers the
  // screen: the card would otherwise take focus behind an opaque layer, and
  // a keyboard visitor would be typing into something they cannot see.
  if (!readStoredPrefs().readingGuideDismissed) {
    window.setTimeout(() => setReadingGuideOpen(true), 900);
  }
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
    makeInteractiveRow(crumb, `Go to ${item.data.name}`, () => state.graph.setSelectedNode(item));
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
  // Placement is a claim about the EDGE above this node, separate from
  // whether the node itself exists. It gets its own line so the two cannot be
  // read as one.
  const placement = lastVerified.cloneNode(false);
  placement.id = "verification-placement";
  placement.textContent = "";
  lastVerified.insertAdjacentElement("afterend", placement);
  dom.verificationPlacement = placement;
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
  if (dom.togglesWrap && dom.toggleUnverified && dom.toggleCandidates && dom.toggleSuperseded) {
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
  // Worded as opting *in* to the estimates: the default is the honest view,
  // and turning this on is a request to see a derived number, not a setting
  // that hides something the reader was entitled to.
  const toggleExactCosts = makeToggle("Also show estimated shares of a parent's total");
  toggleExactCosts.checked = false;
  // Governments reorganise, and nothing here is ever deleted when they do: a
  // replaced unit keeps its id, its description and its sources. The default
  // view is the government as it stands, and this opts in to the ones it has
  // replaced — the same wording logic as the estimates toggle above.
  const toggleSuperseded = makeToggle("Also show units the government has replaced");
  toggleSuperseded.checked = false;

  (depthExpandCtrl || document.body).appendChild(wrap);
  dom.togglesWrap = wrap;
  dom.toggleUnverified = toggleUnverified;
  dom.toggleCandidates = toggleCandidates;
  dom.toggleExactCosts = toggleExactCosts;
  dom.toggleSuperseded = toggleSuperseded;
}

function ensureVerificationLegend() {
  if (!dom.legend || dom.legend.querySelector("[data-verification-legend='true']")) {
    return;
  }

  const title = document.createElement("div");
  title.id = "legend-verification-label";
  title.dataset.verificationLegend = "true";
  title.textContent = "Verification";
  title.style.fontSize = "10px";
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

// "The parent's official page lists it" is exactly the claim, and no more:
// a page can list partner agencies too, so this never says "reports to".
// Every one of the 5,170 descriptions is prose from the base graph with no
// citation behind it. It reads as fact, so it has to say what it is — the
// same way a cost says "estimate" and a source box says "no source
// recorded". A cluster's text is written by this UI and is not a claim; a
// candidate's text came from a crawler record and is labelled there.
// What OPM's number is, and is not. The coverage sentence is the data
// dictionary's own; the disagreement line exists because the two figures are
// usually measuring different populations, not because one is wrong.
function renderHeadcountProvenance(data) {
  let line = document.getElementById("info-headcount-provenance");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-headcount-provenance";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const source = data.employeesOfficialSource;
  const hasHeadcount = source && typeof source === "object" && typeof data.employeesOfficial === "number";
  const fileA = data.usaspendingOutlays;
  const hasFileA = fileA && typeof fileA === "object" && typeof fileA.amount === "number";
  const audited = data.auditedNetCost;
  const hasAudited = audited && typeof audited === "object" && typeof audited.netCostUsd === "number";
  const omb = data.ombBudget;
  const hasOmb = omb && typeof omb === "object"
    && (typeof omb.outlays === "number" || typeof omb.budgetAuthority === "number");
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  if (hasAudited) {
    // The only figure in this project an auditor outside the reporting agency
    // has checked — and still not this unit's cost. Accrual, for a year that
    // has ENDED, where the cost above is cash for the year to date. Both dates
    // are printed rather than one, so the two cannot be read as the same thing.
    add(`Treasury's audited Statement of Net Cost reports a net cost of $${Math.round(audited.netCostUsd).toLocaleString()} for "${audited.agencyName}" for fiscal year ${audited.fiscalYear}, ended ${audited.statementDate}`);
    if (typeof audited.grossCostUsd === "number" && typeof audited.earnedRevenueUsd === "number") {
      add(` (gross cost $${Math.round(audited.grossCostUsd).toLocaleString()} less earned revenue $${Math.round(audited.earnedRevenueUsd).toLocaleString()})`);
    }
    add(". That is accrual accounting for a completed year — what the unit's programmes cost to run — and the figure above it is cash out of the door for the year to date. Different basis, different period; neither is the other. ");
  }
  if (hasOmb) {
    // Two things a reader must know before reading these figures, and the
    // publisher says both: the year is the last one that has FINISHED (the
    // later columns of that file are the President's request, which this
    // project never publishes), and OMB's totals are only "generally
    // consistent with" the Treasury statement the cost above comes from.
    const unit = omb.level === "bureau"
      ? `"${omb.listedBureau}", the bureau OMB files under "${omb.listedAgency}"`
      : `"${omb.listedAgency}"`;
    const rows = (omb.outlayAccountRows || 0) + (omb.budgetAuthorityAccountRows || 0);
    // OMB prints NO total row in this database: every row is a budget account.
    // So this figure is not something the publisher states about the unit, it
    // is a sum over the rows it files under it, and saying so — with the row
    // count — is the difference between a citation and an attribution.
    add(`These are not figures OMB prints for ${unit}: that database has no total row, so each is the sum of the ${rows ? rows.toLocaleString() + " " : ""}account rows OMB files under it, for fiscal year ${omb.fiscalYear} — the last completed year in the package. The later years in it are the President's request and are not published here. `);
    if (omb.netQuote) add(`OMB reports these "${omb.netQuote.replace(/^Budget authority and outlay amounts are /, "")}" `);
    if (typeof omb.outlays === "number" && omb.outlays < 0) {
      add(`— which is why the figure is negative here: this unit collects more than it spends. `);
    }
    if (omb.treasuryQuote) add(`OMB says of its own totals: "${omb.treasuryQuote}", and that the two differ by reporting and classification corrections made after the Treasury published, and by conceptual differences between the two. `);
    if (omb.rowSelection) add(`The sum is over ${omb.rowSelection}. `);
    if (omb.precisionNote) add(`The figures are the publisher's thousands; OMB states that "detail below millions is not available", so they are exact to the million and no further. `);
  }
  if (hasFileA) {
    // A different measure from the cost above it, and said so in the same
    // breath: File A is gross, before the offsetting collections the Treasury
    // statement nets off, and year-to-date rather than a period the Treasury
    // line reports. The figure is the API's own, for the name it prints.
    const fetched = fileA.retrievedAt
      ? new Date(fileA.retrievedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
      : null;
    const where = fileA.level === "bureau"
      ? `bureau "${fileA.bureauId}" of toptier ${fileA.toptierCode}`
      : `toptier ${fileA.toptierCode}`;
    add(`USAspending's File A reports gross outlays of $${Math.round(fileA.amount).toLocaleString()} for "${fileA.apiName}" (${where}) for FY${fileA.fiscalYear} through ${fileA.periodAsOf}`);
    if (fetched) add(`, fetched ${fetched}`);
    add(". ");
    // When the API spells the unit differently, say so rather than leaving a
    // reader to wonder why the quoted name is not the one above it. The basis
    // is the recorded reason the two names are taken to be one unit.
    if (fileA.nameAlias && typeof fileA.nameAlias === "object") {
      add(`USAspending spells this unit differently from the graph — "${fileA.nameAlias.apiName}" against "${fileA.nameAlias.graphName}". ${fileA.nameAlias.basis} Because that match rests on a recorded alias rather than on the two names agreeing, this figure is held to the weaker grade. `);
    }
    add("This is a gross, year-to-date figure from a different system than the Treasury statement's net line; it is shown beside the cost and is not the cost. ");
  }
  if (!hasHeadcount) return;
  const on = source.checkedAt
    ? new Date(source.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
  add(`OPM's FedScope employment file lists ${data.employeesOfficial.toLocaleString()} for "${source.listedName}"`);
  if (source.level === "subagency" && source.agencyCode) add(` (a sub-agency of ${source.agencyCode})`);
  if (on) add(`, fetched ${on}`);
  add(". ");
  if (source.coverage) add(`Coverage: ${source.coverage} `);
  if (source.components && source.components.length > 1) {
    add(`The figure is the sum of ${source.components.length} rows the file lists under this agency. `);
  }
  if (source.outsideStatedCoverage) {
    add("This unit sits outside the Executive Branch the file says it covers, so the number may not describe it at all. ");
  }
  if (source.subtreeRecordsExceedIt) {
    add(`Units beneath this one already account for ${source.subtreeRecordsExceedIt.toLocaleString()} in the same file, so this figure does not cover its own subtree. `);
  }
  if (data.employees) {
    add(`The figure above it is prose from the base graph with no citation, and the two often count different populations — OPM counts federal civilians in an active pay status, not uniformed members or contractors. Neither is corrected against the other.`);
  }
}

function renderCountProvenance(data) {
  let line = document.getElementById("info-count-provenance");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-count-provenance";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  if (data.childrenIncomplete) {
    const missing = Number(data.statedChildCount) - Number(data.carriedChildCount);
    add(
      `This node's own name states ${Number(data.statedChildCount).toLocaleString()}; the graph carries ` +
      `${Number(data.carriedChildCount).toLocaleString()}. The other ${missing.toLocaleString()} are not in this graph at all, ` +
      "so every figure beneath is for the ones shown and nothing here estimates the rest.",
    );
    return;
  }
  const represents = data.representsPosts;
  if (represents && typeof represents === "object") {
    if (represents.kind === "exact") {
      add(`Its name states that it stands for ${represents.count} posts of this title, drawn as one node. `);
    } else if (represents.kind === "range") {
      add(`Its name states that it stands for ${represents.low} to ${represents.high} posts of this title, drawn as one node. `);
    } else {
      add(`Its name states that it stands for several posts of this title ("${represents.as_written}") without saying how many, and no number is invented here. `);
    }
    // What the figure above actually is decides this sentence. An apportioned
    // share or a measured total is the group's; a rate of basic pay is one
    // post's, and calling that "for the group" is false in the other
    // direction. Nine published nodes said exactly that — five State
    // department offices, the Deputy Solicitor General (×4) and two Deputy
    // Assistant Attorney General nodes — each printing a single archive
    // rate under a sentence calling it the group's.
    const perPost = showsPayInsteadOfCost(data);
    if (perPost) {
      // Only what was actually read. An earlier version of this sentence said
      // "each of the 2 to 4 would be paid separately", which the archive does
      // not state: for the Western Hemisphere Affairs Deputy Assistant
      // Secretary it carries four rows at three different figures, and the
      // rate shown is the one its standing listings agree on. What the other
      // posts are paid is not in the file.
      const listing = data.positionListing || {};
      const rows = Number(listing.incumbencies) || 0;
      const from = listing.valuesFrom === "standing_listings"
        ? "the listings still standing when it closed"
        : "a past incumbency";
      add(
        "The rate above is one post's rather than the group's: it is what " +
        `the archive reports for ${from}` +
        (rows ? ` (${rows} row${rows === 1 ? "" : "s"} under this title here)` : "") +
        ", and it does not say what the other posts of this title are paid.",
      );
    } else {
      add("Any figure above is for the group, not for one holder.");
    }
  }
}

function renderPositionListing(data) {
  let line = document.getElementById("info-position-listing");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-position-listing";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const listing = data.positionListing;
  if (!listing || typeof listing !== "object") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const on = listing.checkedAt
    ? new Date(listing.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
  add(`OPM's PLUM archive — ${listing.edition}${on ? `, fetched ${on}` : ""} — lists "${listing.listedTitle}"`);
  if (listing.listedOrganization) add(` under ${listing.listedOrganization}`);
  if (listing.status) add(`, recorded as ${String(listing.status).toLowerCase()} when the archive closed`);
  add(". ");
  if (listing.appointmentType) add(`Appointment type ${listing.appointmentType}. `);
  // Pay, as the archive states it and no further. The column it comes from
  // holds two different things — a rank ("IV", "15") and, for 983 rows, a
  // rate of basic pay ("$225,700") — so a dollar figure is never printed as
  // a level. The archive itself never converts a level into a rate; where
  // the block below shows one, it comes from a second document and says so.
  if (listing.payPlan) add(`Pay plan ${listing.payPlan}`);
  if (listing.payLevel) {
    add(`${listing.payPlan ? ", " : ""}${listing.payPlan === "EX" ? "Executive Schedule level" : "level or grade"} ${listing.payLevel}`);
    add(". The archive gives the rank, not a rate of pay. ");
  } else if (listing.payPlan) {
    add(". ");
  }
  if (typeof listing.reportedPay === "number") {
    add(`It reports basic pay of ${listing.reportedPayText || `$${listing.reportedPay.toLocaleString()}`} for that period — not this unit's cost, and not necessarily what the post pays now. `);
  }
  if (listing.valuesFrom === "past_incumbencies") {
    add("Those details come from a past incumbency, not a standing listing. ");
  }
  add("It is a record of that period and says nothing about who holds this post now.");
  renderTableRate(data, add);
  renderGradePay(data, add);
}

// The base-pay RANGE a salary table states for the pay plan or grade the
// archive reports: a General Schedule grade's step 1 to step 10, or the SES /
// SL-ST pay system's minimum and maximum. Rendered inside the listing block,
// beside the pay plan it was looked up for, exactly as the table rate above
// is. A range is never a rate: the sentence says which grade, which year,
// that it is base pay before locality, and that it is neither the unit's
// cost nor necessarily what the post pays now.
function gradePayOf(node) {
  const pay = node.positionGradePay;
  if (!pay || typeof pay !== "object") return null;
  return typeof pay.minimum === "number" && typeof pay.maximum === "number" ? pay : null;
}

function formatGradeRange(pay) {
  return `$${Math.round(pay.minimum).toLocaleString()} – $${Math.round(pay.maximum).toLocaleString()}`;
}

function renderGradePay(data, add) {
  const pay = gradePayOf(data);
  if (!pay) return;
  const year = pay.effective ? String(pay.effective).slice(0, 4) : "";
  if (pay.kind === "general_schedule_grade") {
    add(` Separately, OPM's ${pay.table} states ${formatGradeRange(pay)} as the base General Schedule range for grade ${pay.grade} in ${year}, before locality pay; not this unit's cost and not necessarily what the post pays now.`);
    add(" That is a range, not a rate: the table prints ten steps for the grade and does not say which step this post is at, and every General Schedule employee in the fifty states receives a locality adjustment on top of the base rate that this table does not state.");
  } else {
    const system = pay.kind === "senior_executive_service" ? "Senior Executive Service" : "Senior-Level / Scientific or Professional";
    add(` Separately, OPM's ${pay.table} states the ${system} pay system's range for ${year} as ${formatGradeRange(pay)}; not this unit's cost and not necessarily what the post pays now.`);
    const rows = Array.isArray(pay.rows) ? pay.rows : [];
    for (const row of rows) {
      if (row && typeof row.minimum === "number" && typeof row.maximum === "number") {
        add(` The table's own row: "${row.label}" — $${Math.round(row.minimum).toLocaleString()} to $${Math.round(row.maximum).toLocaleString()}.`);
      }
    }
    add(" The archive does not say which kind of agency employs the post, so both rows are shown; a band is not a rate, and the table names no post.");
  }
  add(" Two documents, not one: the pay plan is the archive's record of a period that ended, and the range is from a table that took effect afterwards.");
  const notes = Array.isArray(pay.footnotes) ? pay.footnotes.filter((n) => String(n || "").trim()) : [];
  for (const note of notes) add(` The table's own note: "${String(note).trim()}"`);
}

// The salary table's rate for the level the archive reports. Deliberately
// rendered here, inside the listing block, rather than only in the cost block:
// this element is drawn whatever the estimates toggle says, and the claim only
// makes sense beside the level it was looked up from. Text nodes throughout —
// the footnote is verbatim text from a fetched OPM page, and this file has no
// escaping helper (its convention is replaceChildren + createTextNode).
function renderTableRate(data, add) {
  const rate = data.positionPayRate;
  if (!rate || typeof rate !== "object" || typeof rate.amount !== "number") return;
  const printed = rate.rateText || `$${rate.amount.toLocaleString()}`;
  // Only the leading "Effective" is lowercased to join the sentence; the month
  // keeps the capitalisation the page prints, because this is quoted text.
  const when = rate.effectiveText ? `, ${String(rate.effectiveText).replace(/^Effective\b/, "effective")}` : "";
  add(` Separately, OPM's ${rate.table}${when}, pays ${printed} for ${rate.amountScope}.`);
  // The whole point of the module: two documents, and the join is weaker than
  // either. Neither half is allowed to be read as the other.
  add(" That is two documents, not one — the level is the archive's record of a period that ended, and the rate is from a table that took effect afterwards, so neither says what this post pays whoever holds it now.");
  add(" A rate of basic pay is also not this unit's cost: it excludes benefits, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  const notes = Array.isArray(rate.footnotes) ? rate.footnotes.filter((n) => String(n || "").trim()) : [];
  for (const note of notes) add(` The table's own note: "${String(note).trim()}"`);
}

// The Executive Schedule rate CURRENT LAW sets for this post. Its own block,
// because it needs no PLUM listing to hang off: 5 U.S.C. 5312-5316 names the
// office itself, so this is published on nodes the archive never reported —
// the Secretary of State, the Attorney General, the Secretary of Defense, none
// of which carried any pay evidence before 2026-09-18.
//
// It is still two documents, and the sentence says so. What is different from
// the block above is which document supplies the level: current law naming an
// office, rather than an archive recording who held it between 2021 and 2025.
function renderSchedulePay(data) {
  let line = document.getElementById("info-schedule-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-schedule-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = data.positionSchedulePay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const when = pay.effectiveText ? `, ${String(pay.effectiveText).replace(/^Effective\b/, "effective")}` : "";
  add(`${pay.citation || "The United States Code"} places this post at Executive Schedule level ${pay.payLevel}, naming it "${pay.statutoryTitle}". OPM's ${pay.table}${when}, pays ${printed} for ${pay.amountScope}.`);
  // Which office in which body. Not decoration: the Code writes "General
  // Counsel of the Department of Agriculture" where this graph writes
  // "General Counsel", and 84 nodes here carry that name. The organisation is
  // half of what says which one the statute meant, so the panel prints it and
  // never lets the reader assume the title alone picked this node.
  if (pay.scopedOffice && pay.scopedOrganisation) {
    add(` The Code writes that as one title; this graph splits it, so the figure was matched to "${pay.scopedOffice}" as the post of that name directly under ${pay.scopedOrganisation} — the organisation is half of what identifies it, because that title is not unique in this graph.`);
  }
  add(" Two documents: the statute sets the level and the table sets the rate. Current law names the office, so this does not depend on who holds it — but it is a statutory rate of basic pay, not what the holder receives: it excludes benefits, any freeze the table notes below, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  // Two nodes carry BOTH this block and the archive-derived one above, and
  // both agree. Printed as two silent paragraphs they read as two separate
  // figures; saying it is the same level reached twice is what they are.
  const archive = data.positionPayRate;
  if (archive && typeof archive === "object" && archive.payLevel === pay.payLevel) {
    add(` The block above reaches the same level independently: OPM's archive reported this post at level ${pay.payLevel} during the previous administration, and the Code places it there now. That is one level corroborated by two records, not two separate figures.`);
  }
  const notes = Array.isArray(pay.footnotes) ? pay.footnotes.filter((n) => String(n || "").trim()) : [];
  for (const note of notes) add(` The table's own note: "${String(note).trim()}"`);
}

// A single primary source that names a judicial or congressional seat
// directly and states what it pays — no PLUM-style archive to join it to,
// unlike positionPayRate above. Rendered as its own block so it appears
// whatever the estimates toggle says and whether or not the node also
// carries a PLUM listing (it never does: the archive covers the executive
// branch only).
function renderStatutoryPay(data) {
  let line = document.getElementById("info-statutory-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-statutory-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = data.positionStatutoryPay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const on = pay.checkedAt
    ? new Date(pay.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
  add(`${pay.sourceLabel || "A primary official source"}${on ? ` (checked ${on})` : ""} states that ${pay.amountScope || "this tier"} is paid ${printed}${pay.year ? ` for ${pay.year}` : ""}.`);
  add(" That names a tier or a group of roles, not this specific post by name, so it is one source's own account of what the tier pays — not a second, independent confirmation, and not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
  const quote = String(pay.quote || "").trim();
  if (quote) add(` The source's own words: "${quote}"`);
}

function renderReportedPay(data) {
  let line = document.getElementById("info-reported-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-reported-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = data.positionReportedPay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const on = pay.checkedAt
    ? new Date(pay.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
  // The claim is deliberately about the person the roster lists, not about
  // the post: the report is person-level by statute, and two people can hold
  // one title at different salaries.
  add(
    `${pay.sourceLabel || "The White House Office's own annual report to Congress"}` +
      `${on ? ` (checked ${on})` : ""} lists one person under "${pay.reportedTitle || "this title"}"` +
      `${pay.asOf ? `, as of ${pay.asOf}` : ""}, paid ${printed}${pay.payBasis ? ` ${String(pay.payBasis).toLowerCase()}` : ""}.`,
  );
  add(" That is what the one person listed under this title is paid, not what the post pays whoever holds it: the report states each individual's own rate, and two people can share a title at different salaries.");
  if (pay.titleFolded) {
    add(" The report spells the title with its White House rank in front; that prefix is set aside to match this unit.");
  }
  add(" It is not this unit's cost — basic pay excludes benefits and is not a share of federal outlays — and it is not evidence that this post exists as the graph draws it.");
  const quote = String(pay.quote || "").trim();
  if (quote) add(` The report's own row: "${quote}"`);
}

function renderDescriptionProvenance(data, isClusteredView) {
  let line = document.getElementById("info-desc-provenance");
  if (!line && dom.infoDesc) {
    line = document.createElement("div");
    line.id = "info-desc-provenance";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.08em";
    line.style.margin = "4px 0 8px";
    dom.infoDesc.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  if (data.isCandidate) {
    line.textContent = data.desc
      ? `DESCRIPTION: from the notice that surfaced this candidate (${data.discoveryMethod || "automated discovery"}) — not yet reviewed`
      : "";
    return;
  }
  if (isClusteredView || !data.desc) {
    line.textContent = "";
    return;
  }
  if (String(data.descriptionSource || "") === "generated_from_the_monthly_treasury_statement") {
    line.textContent = "DESCRIPTION: generated from the Monthly Treasury Statement, which names this unit — nothing further about it has been read";
    return;
  }
  if (String(data.descriptionSource || "") === "generated_from_its_official_page") {
    line.textContent = "DESCRIPTION: generated from the official page that names this unit — nothing further about it has been read";
    return;
  }
  if (String(data.descriptionSource || "") === "generated_from_treasury_lines") {
    line.textContent = "DESCRIPTION: generated from the Monthly Treasury Statement lines it names";
    return;
  }
  if (String(data.descriptionSource || "") === "generated_from_the_us_government_manual") {
    // A sourced description, not curated prose. The Manual is the government's
    // own handbook of itself and it states both the unit's name and where it
    // files it; nothing else about the unit has been read.
    line.textContent = "DESCRIPTION: generated from the United States Government Manual, the government's own handbook, which names this unit and files it where the graph puts it — nothing further about it has been read";
    return;
  }
  if (String(data.descriptionSource || "") === "generated_from_whitehouse_staff_report") {
    line.textContent = "DESCRIPTION: generated from the White House Office's own annual report to Congress — the title and rate are the report's, the duties are not described";
    return;
  }
  line.textContent = "DESCRIPTION: uncited prose from the base graph — not checked against any source";
}

// The United States Government Manual's own description of the unit, printed
// BESIDE the curated prose and never in its place: the curated text above
// keeps its "uncited" label exactly as it was, and this block says which
// element of the Manual's entry the words came from — its mission statement,
// or the opening of its entry, cut at a sentence boundary where the record
// says so — quoted verbatim, dated by the edition and linked to the granule.
function renderOfficialDescription(data, isClusteredView) {
  let host = document.getElementById("info-desc-official");
  if (!host) {
    const anchor = document.getElementById("info-desc-provenance") || dom.infoDesc;
    if (!anchor) return;
    host = document.createElement("div");
    host.id = "info-desc-official";
    host.style.fontSize = "10px";
    host.style.color = "#9a8a6a";
    host.style.lineHeight = "1.7";
    host.style.margin = "0 0 12px";
    anchor.insertAdjacentElement("afterend", host);
  }
  host.textContent = "";
  const block = data && data.descriptionOfficial;
  if (isClusteredView || !data || data.isCandidate || !block || typeof block !== "object" || !block.text
      || String(block.source || "") !== "us_government_manual") {
    host.style.display = "none";
    return;
  }
  host.style.display = "";
  const heading = document.createElement("div");
  heading.style.fontSize = "9px";
  heading.style.color = "#8f7a5d";
  heading.style.letterSpacing = "0.08em";
  heading.style.margin = "0 0 4px";
  heading.textContent = `OFFICIAL DESCRIPTION — U.S. Government Manual, ${block.edition || "edition not stated"}`;
  host.appendChild(heading);
  const quote = document.createElement("div");
  quote.className = "info-desc-official-text";
  quote.textContent = block.text;
  host.appendChild(quote);
  const note = document.createElement("div");
  note.style.fontSize = "9px";
  note.style.color = "#8f7a5d";
  note.style.margin = "4px 0 0";
  const which = block.kind === "mission_statement"
    ? "the Manual's own mission statement for this unit"
    : block.truncated
      ? `the opening of the Manual's entry for this unit, cut at a sentence boundary after ${String(block.text).length} of ${block.fullLength || "its"} characters`
      : "the opening paragraph of the Manual's entry for this unit";
  note.appendChild(document.createTextNode(`Quoted verbatim: ${which}. The curated description above is unchanged and remains uncited. `));
  if (block.url) {
    const link = document.createElement("a");
    link.href = block.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Read the entry";
    link.setAttribute("aria-label", `Read the Government Manual entry for ${block.listedName || data.name || "this unit"}`);
    note.appendChild(link);
  }
  host.appendChild(note);
}

// A unit the government has replaced. The node is still here, with everything
// it ever earned; what the panel must not do is let a reader take it for part
// of the government as it stands. The claim is quoted, dated and linked,
// because "this no longer exists" is a positive claim like any other.
function renderSupersededNotice(data) {
  const host = dom.infoPanel && dom.infoPanel.querySelector("#info-superseded");
  const existing = host || document.createElement("div");
  existing.id = "info-superseded";
  if (!data || String(data.lifecycle || "") !== "superseded") {
    existing.textContent = "";
    existing.style.display = "none";
    return;
  }
  const source = data.supersededSource || {};
  const replacements = Array.isArray(data.supersededBy) ? data.supersededBy : [];
  const by = replacements.length
    ? ` Its work is carried by ${replacements.length} unit${replacements.length === 1 ? "" : "s"} now in the graph.`
    : " No successor unit is recorded.";
  const quote = String(source.quote || "");
  existing.textContent =
    `REPLACED — the government no longer has this unit as drawn (as of ${String(data.supersededOn || "an unstated date")}).` +
    by +
    (quote ? ` ${hostnameOf(source.url)} says: "${quote}"` : "") +
    " It is kept, with its sources, as a record of what the government used to be.";
  existing.style.display = "block";
  existing.style.fontSize = "9px";
  existing.style.lineHeight = "1.5";
  existing.style.color = "#d99a6c";
  existing.style.margin = "6px 0";
  if (!host && dom.infoPanel && dom.infoPanel.firstChild) {
    dom.infoPanel.insertBefore(existing, dom.infoPanel.firstChild.nextSibling);
  }
}

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (error) {
    return String(url);
  }
}

function renderPlacementLine(data, isRoot = false) {
  if (!dom.verificationPlacement) return;
  if (isRoot) {
    // There is no edge above the root to have evidence for. "No evidence
    // recorded for where this sits" read as a gap on the Constitution.
    setText(dom.verificationPlacement, "Placement: the root of the graph — nothing sits above it, so there is no edge here to evidence");
    return;
  }
  if (data.isCandidate) {
    // Not a placement claim — nothing has verified this belongs anywhere.
    // It is the discovery crawler's own guess at a parent, shown so a
    // reviewer isn't left to wonder why an unreviewed record floats near
    // the root with no visible reason: this is that reason.
    setText(
      dom.verificationPlacement,
      data.possibleParent
        ? `POSSIBLE PARENT (unverified guess, not yet placed): ${data.possibleParent}`
        : "No possible parent was identified for this candidate.",
    );
    return;
  }
  const isPosition = /position/i.test(String(data.type || ""));
  const checked = data.placementVerifiedAt
    ? new Date(data.placementVerifiedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
  dom.verificationPlacement.replaceChildren();
  const add = (text) => dom.verificationPlacement.appendChild(document.createTextNode(text));
  if (String(data.synthetic || "") === "treasury_receipts") {
    add("Placement: a Treasury accounting line, placed beneath the unit whose published total it reconciles; not an organisation and not checked against any page");
    return;
  }
  const disagreement = data.placementDirectoryDisagreement;
  const ancestorListing = data.placementDirectoryAncestor;
  // Which directory is speaking. The Federal Register's list and the
  // Government Manual both print a hierarchy, and a disagreement is only
  // auditable if the panel says whose it is.
  const directoryName = (source) =>
    String(source || "") === "us_government_manual" ? "The United States Government Manual" : "The Federal Register's agency directory";
  const addDisagreement = () => {
    if (ancestorListing && typeof ancestorListing === "object") {
      dom.verificationPlacement.appendChild(document.createElement("br"));
      add(`${directoryName(ancestorListing.source)} files it under "${ancestorListing.listedUnder}", an ancestor here; the grouping between is curated, and the directory says nothing about it`);
    }
    if (!disagreement || typeof disagreement !== "object") return;
    dom.verificationPlacement.appendChild(document.createElement("br"));
    add(`${directoryName(disagreement.source)} files it under "${disagreement.listedUnder}", not under its parent here — the two sources disagree, and neither is resolved`);
  };
  const directoryPlacement = {
    listed_under_parent_in_federal_register_agency_directory: "the Federal Register's agency directory files it under its parent here",
    listed_under_parent_in_us_government_manual: "the United States Government Manual files it under its parent here",
    listed_under_organization_in_opm_plum_archive: "OPM's PLUM archive, the previous administration's reported positions, files a post of this title under its organisation here",
    listed_under_committee_in_senate_committee_list: "the Senate's official committee list carries it under its committee here",
    listed_under_committee_in_house_clerk_committee_list: "the House Clerk's official committee list carries it under its committee here",
  }[String(data.placementMethod || "")];
  if (data.placementVerified === true && directoryPlacement) {
    add(`Placement: ${directoryPlacement}, as "${data.placementMatchedText || ""}" on `);
    if (isHttpUrl(data.placementUrl)) {
      const link = document.createElement("a");
      link.href = data.placementUrl;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = hostnameOf(data.placementUrl);
      dom.verificationPlacement.appendChild(link);
    }
    if (checked) add(` · list fetched ${checked}`);
    addDisagreement();
    return;
  }
  if (data.placementVerified === true) {
    // The claim carries its own audit trail: the page, and the label on it.
    // When it is the same page and the same read as the existence line above,
    // say so — one fetch must not read as two independent checks.
    const sameRead =
      Array.isArray(data.sourceUrls) && data.sourceUrls.includes(data.placementUrl) && data.lastVerified === data.placementVerifiedAt;
    const foldedNote =
      data.placementMatchRule === "committee_scaffolding_folded" ? ` (the graph's "Committee on" / "Subcommittee on" prefix set aside)` : "";
    const label = data.placementMatchedText ? ` as "${data.placementMatchedText}"${foldedNote}` : "";
    // A listing in the site-wide navigation (nav, header, footer) holds for
    // every page of the parent's site: real evidence, but not the page's own
    // account of itself, and the panel says which.
    const where = data.placementMatchedIn === "navigation" ? " in its site-wide navigation" : "";
    add(sameRead ? `Placement: the same page read above lists it${where}${label} on ` : `Placement: its parent's official page lists it${where}${label} on `);
    if (isHttpUrl(data.placementUrl)) {
      const link = document.createElement("a");
      link.href = data.placementUrl;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = hostnameOf(data.placementUrl);
      dom.verificationPlacement.appendChild(link);
    } else {
      add("an official page");
    }
    if (checked) add(` · checked ${checked}`);
  } else if (data.placementVerified === false) {
    add(`Placement: its parent's official page was read${checked ? ` ${checked}` : ""} and does not list it as a heading or link — no claim either way`);
  } else if (isPosition) {
    // Positions ARE checked against a page now — their organisation's — but
    // that read is published above as the post's existence and is never
    // repeated here as separate evidence for the edge. Saying "not checked"
    // would be false; saying it was checked would imply a second finding.
    add(
      "Placement: not claimed separately — the page that names a post is its organisation's own,"
      + " and that one reading is shown above as evidence the post exists, not a second time as evidence of where it sits",
    );
  } else if (data.placementCheckable === false) {
    add("Placement: could not be checked — its parent is a curated grouping with no official page of its own");
  } else {
    add("Placement: no evidence recorded for where this sits in the hierarchy");
  }
  addDisagreement();
}

// The page queued for a node went unread, and the record says why. Said as
// a fact about the host or the page, never as a finding about the unit: 67 of
// 68 such hosts refuse the page exactly as they refuse robots.txt
// (docs/NETWORK_ACCESS.md §11), and "Not yet verified" read as though nobody
// had tried. Null where no such record exists or a method confirmed the node
// by another route.
function describeUnreadPage(data) {
  const u = data.verificationUnread;
  if (data.verificationMethod || !u || typeof u !== "object") {
    return null;
  }
  const when = u.checkedAt ? new Date(u.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "";
  const on = when ? ` on ${when}` : "";
  const host = u.host || hostnameOf(u.url) || "its queued page";
  const UNREAD_TEXT = {
    host_refuses_crawler: `Not verified: ${host} refuses this crawler${on} (401/403 to the project's User-Agent), so the page queued for it could not be read — a fact about the host, not about the unit`,
    robots_unreachable: `Not verified: ${host}'s robots.txt could not be reached${on}; the crawl standard treats that as a complete disallow, so the page was not read`,
    page_not_found: `Not verified: the page queued for it (${host}) answered 404${on}; it has moved or gone, and no other page has been proposed`,
    page_below_readable_floor: `Not verified: the page queued for it (${host}) served under 400 characters of readable text${on} — a script shell — so nothing could be read`,
    site_failing: `Not verified: ${host} answered a server error${on}; refused until the site recovers`,
    network_error: `Not verified: ${host} could not be reached${on} (network error); the page was not read`,
    other: `Not verified: the page queued for it (${host}) could not be read${on}`,
  };
  return UNREAD_TEXT[String(u.kind || "")] || UNREAD_TEXT.other;
}

function renderVerificationPanel(data, isRoot = false) {
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
    //
    // "No source URL has been attached to it yet" was flatly false on the
    // fourteen nodes that carry an OPM headcount: the provenance block
    // directly below this one shows an opm.gov URL. The two are not the same
    // claim — OPM's employment table is evidence about how many civilians
    // work in a unit of this name, not that this unit exists as the graph
    // draws it — so the panel says which one is missing rather than denying
    // the one it has.
    setText(
      dom.verificationConfidence,
      data.employeesOfficial === undefined || data.employeesOfficial === null
        ? "No source URL has been attached to it yet."
        : "No source has been attached for its existence. OPM's employment table, linked below, names a unit of this name — evidence about its staffing, not about whether it exists as drawn."
    );
    // A never-checked node can still have a page queued that went unread;
    // that is the line a reader most needs, and it was never printed here.
    setText(dom.verificationLastVerified, describeUnreadPage(data) || "");
    renderPlacementLine(data, isRoot);
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
      // Worded as what was read, not as what it proves. The page belongs to
      // the organisation that carries the post, so this is that organisation's
      // own account of its own leadership — which is evidence the post exists,
      // and is not evidence about who holds it or what it does.
      name_labelled_on_its_organisations_official_page: "Its organisation's own official page names it",
      listed_in_federal_register_agency_directory: "The Federal Register's agency directory lists it",
      // The archive is the previous administration's reported positions,
      // so this is a record of that period; the listing block below says so
      // and names the edition. The title is quoted where the archive gives
      // one, for the reason a post's page label is.
      listed_in_opm_plum_archive: "OPM's PLUM archive, the previous administration's reported positions, lists a post of this title under its organisation",
      listed_in_us_government_manual: "The United States Government Manual carries an entry for it",
      listed_in_senate_committee_list: "The Senate's official committee list carries it",
      listed_in_house_clerk_committee_list: "The House Clerk's official committee list carries it",
      // The Manual is the government's own handbook of itself, and each
      // agency's entry carries that agency's own leadership table. Worded as
      // what was read: the entry lists a post of this name. It says nothing
      // about who holds it — the office holder's name is never read — and the
      // table's own "updated" date follows below, because some are years
      // older than the edition.
      listed_in_its_organisations_us_government_manual_entry:
        "The United States Government Manual lists it in its organisation's entry",
    };
    const SOURCE_TEXT = {
      federal_register_agency_directory: "the Federal Register's agency directory",
      senate_committee_list: "the Senate's official committee list",
      house_clerk_committee_list: "the House Clerk's official committee list",
      us_government_manual: "the United States Government Manual",
    };
    let checkLine = "Not yet verified";
    const failureSource = data.verificationFailureSource;
    if (data.verificationFailure === "not_in_official_list" && failureSource && typeof failureSource === "object") {
      checkLine = `Checked${checkedOn ? ` ${checkedOn}` : ""} against ${SOURCE_TEXT[failureSource.source] || "an official list"}: it carries no unit of this name under "${failureSource.listedUnder}"`;
    } else if (data.verificationFailure === "not_found") {
      // Name the page. A negative a reader cannot check is worth no more
      // than a positive without a URL, and every positive here carries one.
      const failedOn = failureSource && typeof failureSource === "object" ? hostnameOf(failureSource.url) : "";
      const where = failedOn ? ` (${failedOn})` : "";
      checkLine = checkedOn
        ? `Checked ${checkedOn}: its official page${where} does not name it as a heading or link`
        : `Its official page${where} does not name it as a heading or link`;
    } else if (describeUnreadPage(data)) {
      checkLine = describeUnreadPage(data);
    } else if (checkedOn) {
      const how = METHOD_TEXT[String(data.verificationMethod || "")];
      const where = data.verificationMatchedIn === "navigation" ? " (in the site-wide navigation)" : "";
      // A committee matched with the graph's "Committee on" / "Subcommittee
      // on" prefix set aside quotes the page's own label, so the reader sees
      // what the page says and what the graph adds.
      const folded =
        data.verificationMatchRule === "committee_scaffolding_folded" && data.verificationMatchedText
          ? ` as "${data.verificationMatchedText}" (the graph's "Committee on" / "Subcommittee on" prefix set aside)`
          : "";
      // A post quotes its label unconditionally. "General Counsel" is the
      // name of 84 nodes in this graph and "Inspector General" of 72, so the
      // page and the words on it are the only things that tie a confirmation
      // to this post rather than another — showing the badge without them
      // would ask the reader to take the match on trust.
      const plumListing = data.positionListing && typeof data.positionListing === "object" ? data.positionListing : null;
      const quoted =
        !folded
        && String(data.verificationMethod || "") === "name_labelled_on_its_organisations_official_page"
        && data.verificationMatchedText
          ? ` as "${data.verificationMatchedText}"`
          : String(data.verificationMethod || "") === "listed_in_opm_plum_archive" && plumListing && plumListing.listedTitle
            ? ` as "${plumListing.listedTitle}"${plumListing.listedOrganization ? ` under "${plumListing.listedOrganization}"` : ""}`
            : "";
      checkLine = how ? `${how}${where}${folded}${quoted} · checked ${checkedOn}` : `Last checked: ${checkedOn}`;
    }
    // A directory listing beside a page claim: a second, weaker claim, said
    // as itself, with the name and the parent exactly as the directory has them.
    const listing = data.directoryListing;
    const listingIsTheMethod = listing && typeof listing === "object" && /^listed_in_/.test(String(data.verificationMethod || ""));
    if (listing && typeof listing === "object" && !listingIsTheMethod) {
      checkLine += ` · also listed in ${SOURCE_TEXT[listing.source] || "an official directory"} as "${listing.listedName}"${
        listing.parentListedName ? ` under "${listing.parentListedName}"` : ""
      }`;
    } else if (listing && typeof listing === "object") {
      checkLine += ` as "${listing.listedName}"${listing.parentListedName ? ` under "${listing.parentListedName}"` : ""}`;
    }
    // The Government Manual, beside a page claim or as the claim itself. The
    // title it prints is quoted for the reason a post's page label is: this
    // graph carries "General Counsel" 84 times and "Inspector General" 72,
    // so the agency and the exact words are what tie the listing to this
    // post. The leadership table's own "Sources of Information were updated"
    // footer is printed verbatim where the Manual gives one — GAO's says
    // 2-2019 against a 2025-12-31 edition, and a reader is entitled to know
    // that before reading the badge as current.
    const govman = data.govmanListing;
    if (govman && typeof govman === "object") {
      const already = /government_manual/.test(String(data.verificationMethod || ""));
      const quoted = govman.listedTitle ? ` as "${govman.listedTitle}"` : "";
      const under = govman.listedUnder ? ` under "${govman.listedUnder}"` : "";
      checkLine += already
        ? `${quoted}${under}`
        : ` · also listed in the United States Government Manual${quoted}${under}`;
      if (govman.edition) checkLine += ` (${govman.edition} edition)`;
      if (govman.tableFooter) checkLine += ` — the Manual says of that table: "${govman.tableFooter}"`;
    }
    // The Manual's entry for the unit ITSELF (the organisation route), as
    // distinct from a leadership-table row naming a post. Says the name as
    // the Manual prints it and where the Manual files it, because the
    // hierarchy is the claim the placement line then checks against the tree.
    const govmanEntry = data.govmanEntry;
    if (govmanEntry && typeof govmanEntry === "object") {
      const alreadyEntry = String(data.verificationMethod || "") === "listed_in_us_government_manual";
      const asName = govmanEntry.listedName ? ` as "${govmanEntry.listedName}"` : "";
      const filed = govmanEntry.parentListedName ? `, filed under "${govmanEntry.parentListedName}"` : ", as a top-level entry";
      const edition = govmanEntry.edition ? ` (${govmanEntry.edition} edition)` : "";
      checkLine += alreadyEntry
        ? `${asName}${filed}${edition}`
        : ` · the United States Government Manual also carries an entry for it${asName}${filed}${edition}`;
    }
    // Both facts, where both are true: a directory lists it, and its own
    // page was read and did not name it. Withdrawing the badge is right —
    // the node has a source — but the read still happened.
    const readNotNamed = data.pageReadNotNamed;
    if (readNotNamed && typeof readNotNamed === "object" && readNotNamed.url) {
      const on = readNotNamed.checkedAt
        ? new Date(readNotNamed.checkedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
        : null;
      checkLine += ` · its own page (${hostnameOf(readNotNamed.url)}) was read${on ? ` ${on}` : ""} and does not name it`;
    }
    setText(dom.verificationLastVerified, checkLine);
  }
  renderPlacementLine(data, isRoot);
  renderSupersededNotice(data);

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

  // The root-to-node path is already the breadcrumb below the title, in the
  // same order, each step also clickable — so this does not repeat it as a
  // second list. What this button adds beyond the breadcrumb is the glowing
  // path drawn through the 3D scene itself (see graph.js's pathGlowPool);
  // this line only confirms that is now on.
  const confirmation = document.createElement("div");
  confirmation.style.color = "#9a8a6a";
  confirmation.style.lineHeight = "1.5";
  confirmation.textContent = `Path from the root highlighted in the scene above (${originTrace.length} step${originTrace.length === 1 ? "" : "s"} — see the breadcrumb for the names).`;
  dom.originList.appendChild(confirmation);

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
// Is this figure the node's own, or its share of an ancestor's total? Only a
// Treasury line naming the node, and the root's anchor, are the node's own.
function isCostIdentifiedForTheNode(node) {
  return ["official", "root_total"].includes(String(node.cost_status || "").toLowerCase());
}

// True only where a figure exists to withhold: an apportioned share (or a
// capped Treasury line, which is an estimate too) that the exact-costs view
// keeps back. This used to fire for every node whose cost was not measured —
// posts and the units beneath a negative Treasury pool included — so 4,441
// posts were told to tick "Also show estimated shares" to see a figure the
// data does not hold for them. Those nodes have no estimate, and describeCost
// routes them to their own copy instead.
function hasWithheldEstimate(node) {
  if (!state.exactCostsOnly || isCostIdentifiedForTheNode(node)) {
    return false;
  }
  const status = String(node.cost_status || "").toLowerCase();
  if (status !== "allocated" && status !== "scaled_official") {
    return false;
  }
  return toFiniteAmount(node.resolved_total_amount) !== null && !isBelowPrecision(node);
}

// What stands in for the cost wherever the node has no measured cost of its
// own and no estimate is on show — the estimate withheld, or, for a post, no
// figure at all: a reported rate of basic pay, else a base-pay range a table
// states for the listing's grade. Never beside a measured cost, and null
// where there is nothing to stand in.
function costStandInOf(node) {
  if (isCostIdentifiedForTheNode(node)) {
    return null;
  }
  const pay = reportedPayOf(node);
  const range = pay ? null : gradePayOf(node);
  if (!pay && !range) {
    return null;
  }
  const status = String(node.cost_status || "").toLowerCase();
  const nothingElse = !status || status === "unavailable" || toFiniteAmount(node.resolved_total_amount) === null || isBelowPrecision(node);
  return hasWithheldEstimate(node) || nothingElse ? { pay, range } : null;
}

function showsPayInsteadOfCost(node) {
  const standIn = costStandInOf(node);
  return Boolean(standIn && standIn.pay);
}

function showsRangeInsteadOfCost(node) {
  const standIn = costStandInOf(node);
  return Boolean(standIn && standIn.range);
}

// A rate of basic pay an official source reports for this post. Not the
// node's cost and never presented as one — it is what the archive says the
// post was paid, and it is the one figure a position node can honestly show
// when its apportioned share is withheld.
function reportedPayOf(node) {
  const listing = node.positionListing;
  if (!listing || typeof listing !== "object") return null;
  const pay = listing.reportedPay;
  return typeof pay === "number" && pay > 0 ? listing : null;
}

function formatCostAmount(node) {
  const standIn = costStandInOf(node);
  if (standIn) {
    // The estimate is withheld, or there is none; a real salary or a stated
    // range is shown, headed as pay rather than as a cost by the head drawn
    // beside it.
    if (standIn.pay) {
      return standIn.pay.reportedPayText || `$${Math.round(standIn.pay.reportedPay).toLocaleString()}`;
    }
    // A base-pay RANGE, where a table states one for the listing's pay plan
    // and the archive states no rate. Two bounds, never one figure.
    return formatGradeRange(standIn.range);
  }
  if (hasWithheldEstimate(node)) {
    return null;
  }
  const amount = toFiniteAmount(node.resolved_total_amount);
  if (amount === null || isBelowPrecision(node)) {
    return null;
  }
  if (String(node.costVerificationStatus || "").toLowerCase() === "verified") {
    // A Treasury line can be below zero (net receipts); the sign leads.
    const whole = Math.round(Math.abs(amount)).toLocaleString();
    return `${amount < 0 ? "-" : ""}$${whole}`;
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
  const standIn = costStandInOf(node);
  const pay = standIn ? standIn.pay : null;
  const range = standIn ? standIn.range : null;
  const payNote = pay
    ? ` What is shown instead is a rate of basic pay: OPM's PLUM archive reports ${pay.reportedPayText} for this post` +
      `${pay.edition ? ` (${pay.edition})` : ""}. That is compensation for one post, not what this unit costs.`
    : range
      ? (range.kind === "general_schedule_grade"
        ? ` What is shown instead is the base General Schedule range for grade ${range.grade} in ${String(range.effective || "").slice(0, 4)}, before locality pay, from OPM's ${range.table}; not this unit's cost and not necessarily what the post pays now.`
        : ` What is shown instead is the range OPM's ${range.table} states for the pay system the archive files this post on; not this unit's cost and not necessarily what the post pays now.`)
      : "";
  const payLabel = pay
    ? "No cost known; a reported rate of pay is shown"
    : range
      ? "No cost known; a base-pay range is shown"
      : null;
  // Only a node that actually holds an apportioned share is told the box
  // would reveal one. A post, or a unit beneath a negative Treasury pool,
  // has nothing to reveal, and "tick to see it" about a figure that does not
  // exist is a promise the data cannot keep.
  if (hasWithheldEstimate(node)) {
    return {
      label: payLabel || "No cost known for this node",
      tone: "unavailable",
      note:
        "No record names this node's own cost. The figure this graph could otherwise show is its share of an ancestor's " +
        "measured total, divided among siblings by budget, headcount or subtree size \u2014 a number nobody measured, so it is " +
        "not shown here. Tick \u201cAlso show estimated shares of a parent's total\u201d to see it, labelled as the estimate it is." +
        payNote,
    };
  }
  const status = String(node.cost_status || "").toLowerCase();
  const amount = toFiniteAmount(node.resolved_total_amount);
  const validation = String(node.cost_validation || "").toLowerCase();
  if (!status || status === "unavailable" || amount === null || isBelowPrecision(node)) {
    const unavailable = { ...COST_STATUS_COPY.unavailable, label: payLabel || COST_STATUS_COPY.unavailable.label };
    if (isBelowPrecision(node)) {
      return {
        ...unavailable,
        note: "Its share of the estimate above it rounds to less than one cent (or an ancestor's did), so no figure is shown rather than $0." + payNote,
      };
    }
    if (validation === "treasury_pool_negative") {
      return {
        ...unavailable,
        note:
          "The unit above it publishes the Treasury's net figure, and the measured lines beneath that unit already reach or exceed it \u2014 its net outlays are negative, or a line this graph has no node for is. Nothing remains to apportion to its unmeasured parts, so no figure is shown rather than a guess. There is no estimate for this node to reveal, whatever the estimates box says." +
          payNote,
      };
    }
    if (validation === "post_is_not_a_budget_unit") {
      return {
        ...unavailable,
        note:
          "This is a post, not a unit of government. No federal financial system reports spending for an individual post, and a share of the organisation's budget above it would not be a cost this post incurred \u2014 so no figure is shown, and there is no estimate to reveal." +
          (pay
            ? payNote
            : " Where an official document states what the post is paid, that rate appears below instead, and a salary is not the same thing as a budget."),
      };
    }
    return { ...unavailable, note: COST_STATUS_COPY.unavailable.note + payNote };
  }
  if (String(node.synthetic || "") === "treasury_receipts") {
    return {
      label: "Measured (Treasury accounting line)",
      tone: "measured",
      note: "Not an organisation. The receipts and transfers the Treasury nets inside the published total above, carried here as the statement prints them so the units above sum to that figure to the cent.",
    };
  }
  if (status === "official" && amount < 0) {
    return {
      ...COST_STATUS_COPY.official,
      note: `Net outlays below zero for the period: the Monthly Treasury Statement (Table 5) reports more receipts than spending for this unit.${
        node.treasury_external_section ? ` The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.` : ""
      }`,
    };
  }
  if (status === "official" && node.treasury_external_section) {
    return {
      ...COST_STATUS_COPY.official,
      note: `${COST_STATUS_COPY.official.note} The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.`,
    };
  }
  if (status === "allocated" && amount < 0) {
    const net = toFiniteAmount(node.measured_net_beneath);
    return {
      ...COST_STATUS_COPY.allocated,
      note: `Its measured members' Treasury lines net below zero (${net === null ? "receipts exceeded spending" : formatApproximateCost(net)}); the estimate for its unmeasured members is added to that, and the total stays negative.`,
    };
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
    // A reader looking at the money has no way to see that the headcount it
    // was divided by is contradicted by OPM's own count of the same unit.
    // The share is not moved — the curated figures are uncited, so nothing
    // here can tell a wrong number from a different population (the Coast
    // Guard's 55,000 uniformed against FedScope's 9,583 civilians) — but the
    // disagreement is a fact and belongs beside the figure it produced.
    const dispute = node.cost_weight_dispute;
    let caveat = "";
    if (dispute && typeof dispute === "object" && typeof dispute.officialEmployees === "number") {
      const period = dispute.period ? ` (${dispute.period})` : "";
      caveat =
        ` The headcount used is the base graph's uncited ${Number(dispute.curatedEmployeesParsed).toLocaleString()};` +
        ` OPM's employment file${period} reports ${dispute.officialEmployees.toLocaleString()} for the same unit.` +
        " The share was not recomputed from OPM's number: the two can count different populations, and neither figure is corrected against the other.";
    }
    return {
      ...copy,
      note: `Not a measured budget. Derived by dividing the parent's total, weighted by ${phrase}.${caveat}`,
    };
  }
  return copy;
}

function buildCostBlock(node) {
  const block = document.createElement("div");
  block.className = "info-cost";

  const head = document.createElement("div");
  head.className = "info-cost-head";

  // When the estimate is withheld and a salary is shown in its place, the
  // heading must not read COST: a rate of basic pay for one post is not what
  // a unit costs, and the label is the first thing a reader takes as the
  // claim. The period line below is the Treasury anchor's and is suppressed
  // for the same reason.
  const showingPay = showsPayInsteadOfCost(node);
  // A base-pay RANGE shown in the estimate's place is headed as a range, and
  // as base pay before locality where it is the General Schedule's: the two
  // bounds are the table's and the word COST would make them the unit's.
  const showingRange = showsRangeInsteadOfCost(node);
  const period = showingPay || showingRange ? { label: null, amountKind: null } : getCostPeriod(node);
  const label = document.createElement("span");
  label.className = "info-cost-label";
  label.textContent = showingPay
    ? "REPORTED RATE OF BASIC PAY"
    : showingRange
      ? (gradePayOf(node).kind === "general_schedule_grade" ? "BASE PAY RANGE, BEFORE LOCALITY" : "PAY SYSTEM RANGE")
      : coversFullYear(period.amountKind) ? "ANNUAL COST" : "COST";
  head.appendChild(label);

  const amountText = formatCostAmount(node);
  const amount = document.createElement("span");
  amount.className = "info-cost-amount";
  amount.textContent = amountText === null ? "Not available" : amountText;
  // A measured figure is printed exact — sixteen digits for the root — and
  // that stays the primary reading. Above a billion dollars a compact form is
  // set beneath it so the magnitude can be read at a glance: the same number
  // to three figures, never a different claim. Estimates are untouched; they
  // were always rounded and marked ≈.
  const exactAmount = toFiniteAmount(node.resolved_total_amount);
  if (amountText !== null && !showingPay && !showingRange && isCostIdentifiedForTheNode(node) && exactAmount !== null && Math.abs(exactAmount) >= 1e9) {
    const compact = document.createElement("span");
    compact.className = "info-cost-compact";
    compact.textContent = `${formatApproximateCost(exactAmount)}, to three figures`;
    compact.title = "The same measured figure, rounded for reading; the exact figure above it is the claim.";
    amount.appendChild(compact);
  }
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

// The first eight children, then a row that opens the rest. The old "+ 241
// more" was a dead div: the White House Office carries 249 children and 241
// of them could not be reached from the panel at all. The list scrolls.
const CHILD_LIST_PREVIEW = 8;

function renderChildrenList(nodeObj, children, showAll) {
  dom.childrenList.replaceChildren();
  if (children.length === 0) {
    dom.childrenLabel.style.display = "none";
    return;
  }
  dom.childrenLabel.style.display = "block";
  const fragment = document.createDocumentFragment();
  const shown = showAll ? children : children.slice(0, CHILD_LIST_PREVIEW);
  for (const child of shown) {
    const item = document.createElement("div");
    item.className = "child-item";

    const dot = document.createElement("div");
    dot.className = "child-dot";
    dot.style.background = child.color || "#666";
    item.appendChild(dot);

    const label = document.createElement("span");
    label.textContent = child.name;
    item.appendChild(label);

    makeInteractiveRow(item, `Open ${child.name}`, () => {
      const childObj = state.graph.getNodeById(child.id);
      if (childObj) {
        selectAndFocus(childObj);
        return;
      }
      state.graph.expandNode(nodeObj, true);
      pollForRevealedNode(child.id);
    });

    fragment.appendChild(item);
  }

  if (!showAll && children.length > CHILD_LIST_PREVIEW) {
    const more = document.createElement("div");
    more.className = "child-item child-item-more";
    more.id = "info-children-more";
    const dot = document.createElement("div");
    dot.className = "child-dot";
    dot.style.background = "#555";
    more.appendChild(dot);
    const label = document.createElement("span");
    const rest = children.length - CHILD_LIST_PREVIEW;
    label.textContent = `+ ${rest.toLocaleString()} more — show all ${children.length.toLocaleString()}`;
    more.appendChild(label);
    makeInteractiveRow(more, `Show all ${children.length} sub-units`, () => {
      renderChildrenList(nodeObj, children, true);
      const first = dom.childrenList.children[CHILD_LIST_PREVIEW];
      if (first && typeof first.focus === "function") first.focus();
    });
    fragment.appendChild(more);
  }

  dom.childrenList.appendChild(fragment);
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
  renderDescriptionProvenance(data, isClusteredView);
  renderOfficialDescription(data, isClusteredView);
  renderHeadcountProvenance(data);
  renderPositionListing(data);
  renderStatutoryPay(data);
  renderSchedulePay(data);
  renderReportedPay(data);
  renderCountProvenance(data);

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
  // The curated figure is uncited and mixes populations (civilians, uniformed
  // members, contractors); OPM's is sourced, dated, and civilians only. Both
  // are shown, each labelled for what it is, and where they disagree the panel
  // says so rather than picking one.
  const official = data.employeesOfficialSource;
  if (data.employees) {
    statRows.push([official ? "EMPLOYEES (uncited, from the base graph)" : "EMPLOYEES", data.employees]);
  }
  if (typeof data.employeesOfficial === "number" && official && typeof official === "object") {
    const period = official.period ? ` (${official.period})` : "";
    statRows.push([`EMPLOYEES — OPM FedScope${period}`, data.employeesOfficial.toLocaleString()]);
  }
  // USAspending File A, under its own heading so it can never read as the
  // cost: gross outlays, fiscal-year-to-date, from a different system.
  const auditedRow = data.auditedNetCost;
  if (auditedRow && typeof auditedRow === "object" && typeof auditedRow.netCostUsd === "number") {
    statRows.push([
      `AUDITED NET COST — Treasury Statement of Net Cost (FY${auditedRow.fiscalYear}, ended ${auditedRow.statementDate}; not the cost)`,
      `$${Math.round(auditedRow.netCostUsd).toLocaleString()}`,
    ]);
  }
  const fileA = data.usaspendingOutlays;
  if (fileA && typeof fileA === "object" && typeof fileA.amount === "number") {
    statRows.push([
      `GROSS OUTLAYS — USAspending File A (FY${fileA.fiscalYear} to ${fileA.periodAsOf}; not the cost)`,
      `$${Math.round(fileA.amount).toLocaleString()}`,
    ]);
  }
  // OMB's Public Budget Database, under its own heading for the same reason:
  // a COMPLETED fiscal year on OMB's basis, where the cost above is the
  // current year to date on the Treasury's. Both figures the package reports
  // are shown, because budget authority and outlays are different quantities
  // and showing one alone invites the reader to treat it as the other.
  const omb = data.ombBudget;
  if (omb && typeof omb === "object") {
    if (typeof omb.outlays === "number") {
      statRows.push([
        `OUTLAYS — OMB Public Budget Database (FY${omb.fiscalYear} actual; not the cost)`,
        `$${Math.round(omb.outlays).toLocaleString()}`,
      ]);
    }
    if (typeof omb.budgetAuthority === "number") {
      statRows.push([
        `BUDGET AUTHORITY — OMB Public Budget Database (FY${omb.fiscalYear} actual)`,
        `$${Math.round(omb.budgetAuthority).toLocaleString()}`,
      ]);
    }
  }
  if (data.budget) {
    // A hand-typed note in the curated file, not a sourced figure. Unlabelled it
    // read as a second, contradictory cost beneath the estimate.
    statRows.push(["BUDGET NOTE (hand-compiled)", data.budget]);
  }
  if ((data.children || []).length > 0) {
    // A name that states a count is a claim about how many there are. Where
    // the graph carries fewer, the row says so: "Individual Senator Offices
    // (100)" carries eighteen, and a reader who expands it would otherwise
    // have nothing telling them the other eighty-two are absent.
    statRows.push([
      data.childrenIncomplete ? `SUB-UNITS (of the ${data.statedChildCount} its name states)` : "SUB-UNITS",
      String(data.children.length),
    ]);
  }
  // A position node whose name stands for several posts is drawn as one.
  const represents = data.representsPosts;
  if (represents && typeof represents === "object") {
    const value =
      represents.kind === "exact"
        ? String(represents.count)
        : represents.kind === "range"
          ? `${represents.low}–${represents.high}`
          : `unstated (\u201c${represents.as_written}\u201d)`;
    statRows.push(["POSTS THIS NODE STANDS FOR", value]);
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

  const children = data.children || [];
  renderChildrenList(nodeObj, children, false);

  if (children.length > 0 && !nodeObj.expanded) {
    dom.btnExpand.disabled = false;
    dom.btnExpand.style.display = "block";
    setText(dom.btnExpand, `Expand — ${children.length} nodes`);
    dom.btnExpandAll.disabled = false;
    dom.btnExpandAll.style.display = "block";
    setText(dom.btnExpandAll, "Expand All Below");
    if (isClusteredView) {
      setText(dom.btnExpand, `Open Cluster - ${children.length} nodes`);
      setText(dom.btnExpandAll, "Open Full Branch");
    }
    dom.btnCollapse.style.display = "none";
  } else if (nodeObj.expanded) {
    dom.btnExpand.disabled = true;
    dom.btnExpand.style.display = "block";
    setText(dom.btnExpand, "Already Expanded");
    dom.btnExpandAll.disabled = false;
    dom.btnExpandAll.style.display = "block";
    setText(dom.btnExpandAll, "Expand All Below");
    dom.btnCollapse.style.display = "block";
  } else {
    // A leaf carries nothing "Expand All Below" would add beyond what
    // "No Sub-nodes" already says, so it is hidden rather than shown a
    // second time disabled with identical text.
    dom.btnExpand.disabled = true;
    dom.btnExpand.style.display = "block";
    setText(dom.btnExpand, "No Sub-nodes");
    dom.btnExpandAll.style.display = "none";
    dom.btnCollapse.style.display = "none";
  }

  dom.infoPanel.classList.add("open");
  dom.depthCtrl.classList.add("panel-open");
  // Fixed bottom-right, the key sat inside the open panel, which spans the
  // viewport's height at 1400x900; it shifts left with the depth control.
  if (dom.legend) dom.legend.classList.add("panel-open");
  dom.statsPanel.classList.remove("panel-closed");
  setText(dom.btnFlyMode, state.graph?.isFlyMode() ? "Disable Fly Mode" : "Enable Fly Mode");
  if (dom.btnTraceOrigin) {
    renderOriginTrace(nodeObj);
  }
  renderVerificationPanel(data, !nodeObj.isCluster && !data.isCandidate && nodeObj === state.graph.getRootNode());
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

    makeInteractiveRow(row, `${match.name}${match.pathStr ? `, ${match.pathStr}` : ""}`, () => {
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
      selectAndFocus(revealed);
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

// A manual depth filter below the node's own depth would draw the node
// alone — it is exempt as the selection — with every ancestor above it
// hidden. Revealing a node is an explicit request to see it, so the filter
// is lifted to "all", through the same button a hand would press, so the
// control and the stored preference agree with what is on screen.
function ensureDepthFilterCovers(depth) {
  const active = document.querySelector(".depth-btn.active");
  const current = active && active.dataset.depth !== "all" ? Number(active.dataset.depth) : Infinity;
  if (Number.isFinite(current) && current < depth) {
    const all = document.querySelector('.depth-btn[data-depth="all"]');
    if (all) all.click();
  }
}

// Select the node and fly the camera to it, close enough that its LOD tier
// draws its level (graph.focusNode) — selection alone re-centred the camera
// at whatever distance it was, so a depth-8 node reached by search sat at
// "Agency View | depth 3" with its ancestors between depths 4 and 7 undrawn.
function selectAndFocus(nodeObj) {
  if (!nodeObj) return;
  ensureDepthFilterCovers(nodeObj.depth);
  state.graph.setSelectedNode(nodeObj);
  state.graph.focusNode(nodeObj);
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
  selectAndFocus(revealed);
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

// `scopeObj` confines the expansion to one node's subtree — what "Expand All
// Below" promises. Without it the frontier was every loaded node, and the
// button on the Department of the Interior opened all 5,402. The depth
// buttons pass no scope, because they are about the whole graph.
function expandProgressively(targetDepth, scopeObj = null) {
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

    const frontier = state.graph.getFrontier(targetDepth, scopeObj);
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
      writeStoredPrefs({ showUnverified: dom.toggleUnverified.checked });
    });
  }

  if (dom.toggleSuperseded) {
    dom.toggleSuperseded.addEventListener("change", () => {
      // An open results list may hold rows the toggle now hides.
      closeSearch();
      state.graph.setShowSupersededNodes(dom.toggleSuperseded.checked);
      updateStats(state.graph.getStats());
      writeStoredPrefs({ showSuperseded: dom.toggleSuperseded.checked });
    });
  }

  if (dom.toggleExactCosts) {
    dom.toggleExactCosts.addEventListener("change", () => {
      state.exactCostsOnly = !dom.toggleExactCosts.checked;
      // Re-render the open panel so the figure changes with the switch.
      const selected = state.graph.getSelectedNode();
      if (selected) {
        renderInfoPanel(selected);
      }
      writeStoredPrefs({ showEstimates: dom.toggleExactCosts.checked });
    });
  }

  if (dom.toggleCandidates) {
    dom.toggleCandidates.addEventListener("change", () => {
    // An open results list may hold candidate rows the toggle now hides.
    closeSearch();
      state.graph.setShowCandidateNodes(dom.toggleCandidates.checked);
      updateStats(state.graph.getStats());
      writeStoredPrefs({ showCandidates: dom.toggleCandidates.checked });
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
    const selected = state.graph.getSelectedNode();
    if (!selected) {
      return;
    }
    // A cluster stands for its source node's hidden descendants; "below" it
    // means below that node.
    expandProgressively(Infinity, selected.isCluster ? selected.sourceNode || null : selected);
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
      writeStoredPrefs({ depthFilter: button.dataset.depth });
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

// Applies whatever a previous visit (or the URL someone shared) left behind.
// Runs after safeInitUI, since that is what creates the toggle checkboxes
// and binds the depth buttons in the first place — nothing here exists to
// restore state into until that has run. Setting a checkbox's `.checked`
// does not fire its own `change` handler, so each restored toggle calls the
// same graph method its handler would rather than relying on that event.
function restorePersistedState(requestedNodeId) {
  const prefs = readStoredPrefs();

  if (typeof prefs.showSuperseded === "boolean" && dom.toggleSuperseded) {
    dom.toggleSuperseded.checked = prefs.showSuperseded;
    state.graph.setShowSupersededNodes(prefs.showSuperseded);
  }
  if (typeof prefs.showUnverified === "boolean" && dom.toggleUnverified) {
    dom.toggleUnverified.checked = prefs.showUnverified;
    state.graph.setShowUnverifiedNodes(prefs.showUnverified);
  }
  if (typeof prefs.showEstimates === "boolean" && dom.toggleExactCosts) {
    dom.toggleExactCosts.checked = prefs.showEstimates;
    state.exactCostsOnly = !prefs.showEstimates;
  }
  if (typeof prefs.showCandidates === "boolean" && dom.toggleCandidates) {
    dom.toggleCandidates.checked = prefs.showCandidates;
    state.graph.setShowCandidateNodes(prefs.showCandidates);
  }
  if (prefs.depthFilter) {
    const button = document.querySelector(`.depth-btn[data-depth="${prefs.depthFilter}"]`);
    if (button && !button.disabled) {
      document.querySelectorAll(".depth-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.graph.setDepthFilter(prefs.depthFilter === "all" ? Infinity : Number(prefs.depthFilter));
    }
  }
  updateStats(state.graph.getStats());

  // The id is the one the URL carried when the page opened, not what the
  // hash says now: loadData selects the root, onSelect writes the root's id
  // into the hash, and reading the hash at this point returned the root
  // every time — a link to any other node landed on the Constitution.
  if (requestedNodeId) {
    revealAndSelect(requestedNodeId);
  }
}

// Editing the hash by hand, or the browser's back button restoring an
// earlier one, is the same request as arriving with it. replaceState does
// not fire this, so the selection's own hash writes never loop back in.
function bindHashNavigation() {
  window.addEventListener("hashchange", () => {
    const id = getNodeIdFromHash();
    if (!id || !state.graph) return;
    const selected = state.graph.getSelectedNode();
    if (selected && !selected.isCluster && selected.data?.id === id) return;
    revealAndSelect(id);
  });
}

async function initGraphApp() {
  const requestedNodeId = getNodeIdFromHash();
  state.graph = createGovernmentGraph({
    canvas: dom.canvas,
    onSelect: (nodeObj) => {
      cancelRevealLoop();
      safeUiCall("renderInfoPanel", renderInfoPanel, nodeObj);
      // A cluster's id is a stand-in for "whatever the LOD collapsed right
      // now", not a fixed target — reloading later with the LOD in a
      // different state would not resolve it to the same thing, so only a
      // real node's selection is written into the shareable URL.
      if (!nodeObj?.isCluster && nodeObj?.data?.id) {
        setNodeHash(nodeObj.data.id);
      }
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
    expandedNodesUrl:
      window.GRAPH_DATA_SOURCES && "expandedNodes" in window.GRAPH_DATA_SOURCES
        ? window.GRAPH_DATA_SOURCES.expandedNodes
        : "./output/expanded_nodes.json",
    expandedEdgesUrl:
      window.GRAPH_DATA_SOURCES && "expandedEdges" in window.GRAPH_DATA_SOURCES
        ? window.GRAPH_DATA_SOURCES.expandedEdges
        : "./output/expanded_edges.json",
    onStatus: (message) => setText(dom.loadStatus, message),
  });
  setGraphBudgetSummary(data && data.__budgetSummary);
  const summary = summariseGraph(data);
  const provenance = document.getElementById("data-provenance");
  if (provenance) {
    provenance.textContent =
      data && data.__loadSource === "fallback"
        ? "Pipeline graph unavailable — showing the uncited hierarchy, with no cost data at all"
        : describeProvenance(summary);
  }
  safeUiCall("bindReadingGuide", bindReadingGuide, summary);
  state.graph.loadData(data);
  state.searchIndex = state.graph.getSearchIndex();
  safeInitUI();
  safeUiCall("restorePersistedState", restorePersistedState, requestedNodeId);
  safeUiCall("bindHashNavigation", bindHashNavigation);
  hideLoadingOverlay();
}

if (shouldBootUi) {
  initGraphApp().catch((error) => {
    console.error(error);
    showLoadFailure("Failed to load explorer data. Check your connection, then reload.");
  });
}
