import { createGovernmentGraph } from "./graph.js?v=20261007f";
import { loadMergedGraphData } from "./graphLoader.js?v=20261007f";

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
    sourcedFigure: 0, sourcedFigureFileA: 0, sourcedFigureOmb: 0, sourcedFigureAudited: 0,
    sourcedFigureWithEstimate: 0, sourcedFigureNoFigure: 0,
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
      // Every pay field, the same list the panel's headline reads: the two
      // the Code supplies (a schedule level, a rate set by reference) were
      // missing here until 2026-10-05, so the card under-counted the posts
      // that show a salary by a few hundred.
      if (costStandInOf(node)) {
        count.paidPosts += 1;
      }
    }
    // An organisation whose headline, in the default view, is a sourced
    // figure of another kind (since 2026-10-07). A group of its own, never
    // counted as measured: some carry a withheld estimate as well, the rest
    // sit beneath a negative Treasury pool and carry no cost figure at all.
    const sourced = node !== root ? sourcedFigureOf(node) : null;
    if (sourced) {
      count.sourcedFigure += 1;
      if (sourced.kind === "fileA") count.sourcedFigureFileA += 1;
      else if (sourced.kind === "omb") count.sourcedFigureOmb += 1;
      else if (sourced.kind === "audited") count.sourcedFigureAudited += 1;
      if (status === "allocated" || status === "scaled_official") count.sourcedFigureWithEstimate += 1;
      if (status === "unavailable" || !status) count.sourcedFigureNoFigure += 1;
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
    `${count.noFigure.toLocaleString()} with no cost figure at all, ${count.postsWithoutFigure.toLocaleString()} of them posts, which have no budget to divide`,
    // Its own clause, never folded into the measured count: a figure of
    // another kind, headed as what it is.
    `${count.sourcedFigure.toLocaleString()} organisations without a measured cost headed instead by a sourced figure of another kind (${count.sourcedFigureFileA.toLocaleString()} File A gross outlays, ${count.sourcedFigureOmb.toLocaleString()} OMB completed-year outlays, ${count.sourcedFigureAudited.toLocaleString()} audited net cost)`,
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
      + `The remaining ${count.noFigure.toLocaleString()} have no cost figure at all and never will; ticking `
      + `the box does not reveal a number for them, because there is none to reveal. `
      + `${count.sourcedFigure.toLocaleString()} organisations without a measured cost show, at the top of their `
      + `panel, a figure of another kind that a named source publishes for them — gross outlays from `
      + `USAspending (${count.sourcedFigureFileA.toLocaleString()}), the sum of OMB's budget accounts for a `
      + `completed year (${count.sourcedFigureOmb.toLocaleString()}), or the Treasury's audited net cost `
      + `(${count.sourcedFigureAudited.toLocaleString()}). Each is headed as what it is, with its year and `
      + `its basis, and none is the cost or counted as measured; `
      + `${count.sourcedFigureWithEstimate.toLocaleString()} of them still hold an estimate behind the box, and `
      + `${count.sourcedFigureNoFigure.toLocaleString()} are among the ones with no cost figure.`,
    ],
    [
      "A job is not a budget",
      `The Department of Defense spends money; the Secretary of Defense has no budget of their own. `
      + `So no position is given a share of an agency's outlays — that share is not a quantity that `
      + `exists, and it is why ${count.postsWithoutFigure.toLocaleString()} of the `
      + `${count.posts.toLocaleString()} posts show nothing under cost. `
      + `${count.paidPosts.toLocaleString()} show a salary instead — a rate, or a base-pay range — as the figure `
      + `at the top of their panel, and only where an official document states one. A salary is not a budget `
      + `either, and it is headed as pay, never as cost.`,
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
// What a chamber paid out for a committee's account, from its own report:
// the House's quarterly Statement of Disbursements or the Senate's semiannual
// Report of the Secretary. Its report's name and period head the row, because
// the two chambers' figures cover different stretches of time and neither is
// the Treasury's year to date.
function disbursementReportLabel(block) {
  return block.chamber === "senate"
    ? "Report of the Secretary of the Senate"
    : "House Statement of Disbursements";
}

function disbursementPeriodLabel(block) {
  const period = block.period || {};
  const fmt = (iso) => {
    const date = new Date(`${iso}T00:00:00Z`);
    return Number.isNaN(date.getTime())
      ? String(iso || "")
      : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
  };
  return `${fmt(period.start)} – ${fmt(period.end)}`;
}

function disbursementSentence(block) {
  const chamber = block.chamber === "senate" ? "the Senate" : "the House";
  const report = block.chamber === "senate"
    ? "the Report of the Secretary of the Senate"
    : "the House's Statement of Disbursements";
  const names = (block.listedNames || []).map((name) => `"${name}"`).join(" and ");
  const parts = [];
  parts.push(`This is what ${chamber} paid out for the committee's office over ${disbursementPeriodLabel(block)}: `);
  parts.push(`$${Math.round(block.amount).toLocaleString()}, from ${report}, which lists the committee as ${names}. `);
  const count = Number(block.componentCount) || 0;
  if (count > 1) {
    const unit = block.chamber === "senate" ? "funding resolution" : "office and program";
    parts.push(`The report prints no single total for the committee; the figure is the sum of the ${count} totals it prints, one per ${unit}, which this project added up. `);
  }
  if (block.matchRule === "reviewed_row" && block.matchBasis) {
    parts.push(`The report's name for the committee differs from the graph's; the identification is a reviewed one: ${block.matchBasis} `);
  }
  if (block.signConvention && (block.components || []).some((c) => typeof c.amount === "number" && c.amount < 0)) {
    parts.push(`${block.signConvention} `);
  }
  if (block.caveat) parts.push(`${block.caveat} `);
  parts.push("It is cash paid out for the committee's account over that period — not the Treasury's net outlays, not the estimate above, and not the cost. ");
  return parts.join("");
}

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
  const disbursed = data.committeeDisbursements;
  if (disbursed && typeof disbursed === "object" && typeof disbursed.amount === "number") {
    add(disbursementSentence(disbursed));
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
  // The table rate and the range hang off the document that supplied the
  // level. Where that was the current export, they are printed in its block
  // below; a node the archive never listed would otherwise lose them.
  if (!levelSourceIsCurrent(data.positionPayRate)) renderTableRate(data, add);
  if (!levelSourceIsCurrent(data.positionGradePay) && !levelSourceIsVacancy(data.positionGradePay)) renderGradePay(data, add);
  renderTierPay(data, add);
}

// A range whose grade comes from USAJOBS vacancy announcements
// (positionVacancyListing) is printed in that listing's own block.
function levelSourceIsVacancy(block) {
  if (!block || typeof block !== "object") return false;
  return Boolean(block.listingSource && block.listingSource.source === "usajobs_vacancy_announcements");
}

function levelSourceIsCurrent(block) {
  if (!block || typeof block !== "object") return false;
  const source = (block.levelSource && block.levelSource.source) || (block.listingSource && block.listingSource.source) || "";
  return source === "opm_plum_current_export";
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

// A pay-schedule TIER band. Same shape as a grade range and a different
// claim: the VA's Title 38 schedule names the job title outright and states
// the bounds within which an appointment may be set, so the sentence has to
// say "range" and has to say that the schedule publishes no rate for anyone.
function tierPayOf(node) {
  const pay = node.positionTierPay;
  if (!pay || typeof pay !== "object") return null;
  return typeof pay.minimum === "number" && typeof pay.maximum === "number" ? pay : null;
}

function renderTierPay(data, add) {
  const pay = tierPayOf(data);
  if (!pay) return;
  const range = `$${Math.round(pay.minimum).toLocaleString()} – $${Math.round(pay.maximum).toLocaleString()}`;
  add(` Separately, ${pay.sourceLabel || "an official pay schedule"} place "${pay.coverageTitle}" in tier ${pay.tier}, ${range} a year (${pay.effectiveText || pay.effective}).`);
  add(" That is a RANGE, not a rate: the schedule states the bounds within which an appointment may be set and does not publish what any holder is paid. It is not this unit's cost.");
  if (pay.matchRule === "office_scoped_to_its_own_parent") {
    add(` This post is matched to that title by its own name and the network it sits under, not by the schedule naming this node; the schedule names the title only.`);
  } else {
    add(` This post is matched to that title by its own name and the parent it sits under, not by the schedule naming this node; the schedule names the title only.`);
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  if (pay.quote) add(` The schedule's own words: "${String(pay.quote).trim()}"`);
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
  const planFromCurrent = pay.listingSource && pay.listingSource.source === "opm_plum_current_export";
  if (levelSourceIsVacancy(pay)) {
    // The grade comes from USAJOBS vacancy announcements for the title
    // family, not from a report of this post; the block's own sentence says
    // how many, and that the range is nobody's pay.
    if (pay.vacancyStatement) add(` ${pay.vacancyStatement}`);
    add(" The grade is what the announcements state for vacancies of this title at other facilities; none names this post, and their own salaries, which carry a duty station's locality pay, are not shown.");
  } else {
    add(planFromCurrent
      ? " Two documents, not one: the pay plan is the current PLUM export's listing of this post as it stands, and the range is from OPM's salary table for that pay plan; the export prints no rate for this row."
      : " Two documents, not one: the pay plan is the archive's record of a period that ended, and the range is from a table that took effect afterwards.");
  }
  add(payDocumentsSentence(pay));
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
  // either. Neither half is allowed to be read as the other. Which document
  // supplied the level is the record's own `levelSource.source`: the
  // archive of a period that ended, or the current export.
  const levelFromCurrent = rate.levelSource && rate.levelSource.source === "opm_plum_current_export";
  add(levelFromCurrent
    ? " That is two documents, not one — the level is the current PLUM export's listing of this post as it stands, and the rate is from OPM's salary table for that level; the export itself prints no rate for this row, so this is a table's figure for a rank, not a figure for the post."
    : " That is two documents, not one — the level is the archive's record of a period that ended, and the rate is from a table that took effect afterwards, so neither says what this post pays whoever holds it now.");
  add(" A rate of basic pay is also not this unit's cost: it excludes benefits, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  add(payDocumentsSentence(rate));
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
  // A reviewed identification: the Code's title is not this node's name and
  // no matcher could join them, so a second statute says why they are one
  // office. The panel prints the basis and the sentence it rests on, because
  // "Members, Board of Governors" beside a node called "Vice Chair for
  // Supervision" is otherwise a figure with no visible reason.
  const identification = pay.identification && typeof pay.identification === "object" ? pay.identification : null;
  const counted = pay.countedClass && typeof pay.countedClass === "object" ? pay.countedClass : null;
  if (counted) {
    // One office of a COUNTED class: the Code places N offices at one level
    // and names none of them, so the panel says exactly what ties this node
    // to the class — its own name and placement, reviewed — and how many of
    // the N this graph names, and whether a second statute composes the
    // class or names this office itself.
    add(` The Code places that as a class of ${counted.statedPosts} offices at one level and names none of them; this post is priced as one of them because its own name is the class's singular office, "${counted.singular}", and it sits inside ${counted.scopeName || counted.scopeId} — a reviewed membership, re-checked on every build, and this graph names ${counted.membersInGraph} of the ${counted.statedPosts} the Code counts.`);
    if (identification && identification.basisCitation) {
      add(` ${identification.basisCitation} composes the class: "${identification.basisQuote || ""}"${identification.basisCheckedAt ? ` (read ${formatFetchDate(identification.basisCheckedAt)})` : ""}.`);
      if (counted.namedAs) add(` The same section names this office itself: "${counted.namedAs}".`);
      add(" Three documents: the Code places the class and counts it, the composing statute creates the offices, and the table sets the rate.");
    } else {
      add(` No statute composing the class has been read here${identification && identification.basis ? ` (${identification.basis})` : ""}, so this rests on two documents: the Code places the class and counts it, and the table sets the rate.`);
    }
    add(" A statutory rate of basic pay, not what the holder receives: it excludes benefits, any freeze the table notes below, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  } else if (identification && identification.basisInstrument && typeof identification.basisInstrument === "object") {
    // The basis is an instrument the Code prints outside its sections (a
    // Reorganization Plan), read as that one instrument and nothing around it.
    const instrument = identification.basisInstrument;
    add(` That title is not this node's name, and no name match joined them: this is a reviewed identification — ${identification.basis || "recorded without a stated basis"}. The basis is ${instrument.name || "an instrument"}, issued by ${instrument.issuer || "its issuer"} on ${instrument.date || "an unrecorded date"} and printed in ${instrument.printedIn || "the Code"} — ${instrument.kindWords || "not a section of the Code"}. It prints "${identification.basisQuote || ""}"${identification.basisCheckedAt ? ` (read ${formatFetchDate(identification.basisCheckedAt)})` : ""}; the sentence is re-found inside that one instrument on every build.`);
    add(" Three documents: the instrument says which office this post is, the Executive Schedule sets that office's level, and the table sets the rate. It does not depend on who holds the office — but it is a statutory rate of basic pay, not what the holder receives: it excludes benefits, any freeze the table notes below, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  } else if (identification) {
    add(` That title is not this node's name, and no name match joined them: this is a reviewed identification — ${identification.basis || "recorded without a stated basis"}. ${identification.basisCitation || "The basis statute"} prints "${identification.basisQuote || ""}" in its operative text${identification.basisCheckedAt ? ` (read ${formatFetchDate(identification.basisCheckedAt)})` : ""}, and it is re-checked on every build.`);
    add(" Three documents: the basis statute says which office this post is, the Executive Schedule sets that office's level, and the table sets the rate. Current law names the office, so this does not depend on who holds it — but it is a statutory rate of basic pay, not what the holder receives: it excludes benefits, any freeze the table notes below, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  } else {
    add(" Two documents: the statute sets the level and the table sets the rate. Current law names the office, so this does not depend on who holds it — but it is a statutory rate of basic pay, not what the holder receives: it excludes benefits, any freeze the table notes below, and it is not a share of federal outlays, which is what every other figure in this graph means.");
  }
  // Two nodes carry BOTH this block and the archive-derived one above, and
  // both agree. Printed as two silent paragraphs they read as two separate
  // figures; saying it is the same level reached twice is what they are.
  const archive = data.positionPayRate;
  if (archive && typeof archive === "object" && archive.payLevel === pay.payLevel) {
    add(` The block above reaches the same level independently: OPM's archive reported this post at level ${pay.payLevel} during the previous administration, and the Code places it there now. That is one level corroborated by two records, not two separate figures.`);
  }
  // A bench priced from the Code's class title ("Members, Federal Trade
  // Commission"): the level is every member's, and the sweep stamped
  // `holders` from the node's own "(×N)". Without this sentence a Level IV
  // rate beside "Commissioner (×4)" reads as one commissioner's pay.
  if (pay.classTitle === true) {
    add(` The Code's title here is a class title: it places every member of the body at that level, so the figure is not one appointment's.`);
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
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
  const seat = pay.memberSeat && typeof pay.memberSeat === "object" ? pay.memberSeat : null;
  if (seat) {
    // An office a Member of Congress holds -- a committee chair or ranking
    // member, a whip, a conference chair -- priced at the SEAT rate of its
    // chamber's row, never at a row naming the office. The basis is the
    // reviewed rule in the pipeline's own words, and the block says the
    // identification is a rule, not a document naming this post.
    add(`PRICED AS A MEMBER'S SEAT, NOT FOR THE OFFICE — ${pay.sourceLabel || "Schedule 6"}${on ? ` (checked ${on})` : ""} prints ${printed} on its row "${seat.row || pay.amountScope || "Members"}"${pay.year ? ` for ${pay.year}` : ""}. `);
    add(seat.basis || "The holder of this office is a Member of the chamber and Schedule 6 prints no separate rate for it.");
    add(" It is not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
  } else if (pay.statesTheOffice === true) {
    // A section of the Code that names the office itself and states its
    // salary (3 U.S.C. 102, the President). Stronger than a tier row, and
    // still a reviewed identification of which node that office is.
    add(`${pay.sourceLabel || "A section of the United States Code"}${on ? ` (checked ${on})` : ""} states that ${pay.office || pay.amountScope || "the office"} receives ${printed}.`);
    add(" The section names the office itself; which node of this graph that office is remains a reviewed identification, so the claim is graded a proxy. It is not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
    if (pay.notPublished) add(` ${String(pay.notPublished).trim()}`);
  } else {
    add(`${pay.sourceLabel || "A primary official source"}${on ? ` (checked ${on})` : ""} states that ${pay.amountScope || "this tier"} is paid ${printed}${pay.year ? ` for ${pay.year}` : ""}.`);
    add(" That names a tier or a group of roles, not this specific post by name, so it is one source's own account of what the tier pays — not a second, independent confirmation, and not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  const quote = String(pay.quote || "").trim();
  if (quote) add(` The source's own words: "${quote}"`);
}

// A figure NO document states. A statutory parity provision names the tier
// this court's judges are paid at; the Judicial Compensation table states what
// that tier pays. Rendered as its own block, and deliberately led by the fact
// that it is a derivation rather than a quotation — every other pay block on
// this site prints a number somebody published, and this one does not.
//
// The owner asked for the level of verification as a percentage saying how
// many documents verify a claim. That is `pay.verification`, and it is printed
// beside `documentsStatingTheFigure` on purpose: two official documents score
// 80% on this project's own source arithmetic, and neither of them states the
// number, which is exactly what a bare percentage would hide.
function derivedPayOf(node) {
  const pay = node.positionDerivedPay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") return null;
  return pay;
}

function tierReferencePayOf(node) {
  const pay = node.positionTierReferencePay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") return null;
  return pay;
}

function militaryPayOf(node) {
  const pay = node.positionMilitaryPay;
  if (!pay || typeof pay !== "object" || typeof pay.amount !== "number") return null;
  return pay;
}

// A statute that sets the post's pay BY REFERENCE to an Executive Schedule
// level the post is not itself placed at -- 31 U.S.C. 703(f) for the GAO's
// officers, 5 U.S.C. 403(e) for an establishment's Inspector General -- joined
// to OPM's table for the level. No document states the figure for the post,
// and an Inspector General's is arithmetic on a printed one (Level III plus 3
// percent), so the block carries that arithmetic and the panel prints it as a
// computation, never as a quotation.
function renderTierReferencePay(data) {
  let line = document.getElementById("info-tier-reference-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-tier-reference-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = tierReferencePayOf(data);
  if (!pay) {
    if (line) line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const documents = Array.isArray(pay.documents) ? pay.documents : [];
  const arithmetic = pay.arithmetic && typeof pay.arithmetic === "object" ? pay.arithmetic : null;
  const identification = pay.identification && typeof pay.identification === "object" ? pay.identification : {};
  add(`PAY SET BY REFERENCE TO A LEVEL — no document states this figure for this post. ${printed}${pay.effectiveText ? `, ${String(pay.effectiveText).replace(/^Effective\b/, "effective")}` : ""}.`);
  if (arithmetic && arithmetic.operation === "minus_dollars") {
    // A stated number of dollars below another officer whose own pay is set
    // by reference to a level (2 U.S.C. 1808(c)(3) and three more): the
    // subtraction is this project's, printed as a computation.
    const ref = pay.referencedOfficer && typeof pay.referencedOfficer === "object" ? pay.referencedOfficer : {};
    const refOffice = arithmetic.baseOffice || ref.office || "another officer";
    add(` ${pay.statute || "The statute"} sets this post's basic pay at ${arithmetic.minusDollarsText || `$${arithmetic.minusDollars}`} less than the ${refOffice}'s; ${ref.statute || "another statute"}${ref.viaStatute ? `, through ${ref.viaStatute},` : ""} sets the ${refOffice}'s at the rate for Executive Schedule ${pay.levelText || `Level ${pay.level}`}, and OPM's ${pay.table || "table"} prints ${arithmetic.baseText || pay.levelRateText} for that level. ${arithmetic.baseText || pay.levelRateText} − ${arithmetic.minusDollarsText || `$${arithmetic.minusDollars}`} = ${arithmetic.resultText || printed} — arithmetic this project performed, printed by no document. The figure is published only while the ${refOffice}'s own figure is.`);
  } else if (arithmetic) {
    add(` ${pay.statute || "The statute"} sets ${identification.kind === "reviewed_row" ? `the ${pay.office || "post"}'s` : "an Inspector General's"} basic pay at the rate for Executive Schedule ${pay.levelText || `Level ${pay.level}`} plus ${arithmetic.percent} percent; OPM's ${pay.table || "table"} prints ${arithmetic.baseText || pay.levelRateText} for that level. ${arithmetic.baseText || pay.levelRateText} + ${arithmetic.percent}% = ${arithmetic.resultText || printed} — arithmetic this project performed, printed by no document.`);
    if (identification.establishment) {
      add(` It applies here because 5 U.S.C. 401(1) lists ${identification.establishment} as an establishment whose Inspector General that section covers, and this post sits directly under it.`);
    }
  } else {
    if (pay.viaStatute) {
      add(` ${pay.statute || "The statute"} sets the ${pay.office || "post"}'s pay equal to a rate ${pay.viaStatute} sets at Executive Schedule ${pay.levelText || `Level ${pay.level}`}; OPM's ${pay.table || "table"} prints ${pay.levelRateText || printed} for that level. The post is not itself on the Schedule — its pay reaches one of the Schedule's tiers through two statutes.`);
    } else {
      add(` ${pay.statute || "The statute"} sets the ${pay.office || "post"}'s pay equal to the rate for Executive Schedule ${pay.levelText || `Level ${pay.level}`}; OPM's ${pay.table || "table"} prints ${pay.levelRateText || printed} for that level. The post is not itself on the Schedule — its pay is set by reference to one of the Schedule's tiers.`);
    }
    if (identification.statuteIdentifies) {
      add(` The graph's title for this post is a template; the same section says which office stands under it: "${String(identification.statuteIdentifies).trim()}"`);
    }
  }
  // Since 2026-10-07: an instrument the Code prints outside its sections --
  // a Reorganization Plan, or a chamber's pay order reprinted in a Statutory
  // Note -- sets the pay. Say which instrument, who issued it and when, and,
  // for a pay order, that a later order may have changed it.
  const instrument = pay.instrument && typeof pay.instrument === "object" ? pay.instrument : null;
  if (instrument) {
    add(` That is not a section of the Code: it is ${instrument.name || "an instrument"}, issued by ${instrument.issuer || "its issuer"} on ${instrument.date || "an unrecorded date"} — ${instrument.kindWords || "an instrument printed outside the Code's sections"} (${instrument.printedIn || "the Code"}). The sentence was read from that one instrument and nothing printed around it.`);
    if (identification.instrumentDefines) {
      add(` The same instrument defines the term: "${String(identification.instrumentDefines).trim()}"`);
    }
    if (instrument.laterOrderCaution) add(` ${String(instrument.laterOrderCaution).trim()}`);
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  for (const document of documents) {
    if (!document || typeof document !== "object") continue;
    add(` ${document.citation || "A document"} — ${document.role || "supplies part of the figure"}: "${String(document.quote || "").trim()}"`);
  }
  add(" It names a level, not this post by name, so it is never a verification that the post exists. It is not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
  const notes = Array.isArray(pay.footnotes) ? pay.footnotes.filter((n) => String(n || "").trim()) : [];
  for (const note of notes) add(` The table's own note: "${String(note).trim()}"`);
}

// Military basic pay, from Schedule 8 of the annual pay-adjustment order --
// the uniformed services' basic-pay table, which prints its rates BY THE
// MONTH -- reached two ways. A Title 10 or Title 14 section fixes the post's
// grade in so many words, 37 U.S.C. 201(a)(1) assigns that grade a pay grade,
// and the schedule's row for the pay grade prints one figure in every
// populated column; or the schedule's own enlisted footnote names the post by
// title at a stated monthly rate. Either way the annual figure is twelve
// times the monthly one, arithmetic this project performed and no document
// prints, so the block leads with the monthly figure as the schedule prints
// it and the multiplication in the open -- the treatment the Inspector
// General Act's 3 percent gets above. The officer footnote's Level II ceiling
// differs from the O-10 row by $100; it is quoted beside the figure and not
// reconciled.
function renderMilitaryPay(data) {
  let line = document.getElementById("info-military-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-military-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = militaryPayOf(data);
  if (!pay) {
    if (line) line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const documents = Array.isArray(pay.documents) ? pay.documents : [];
  const identification = pay.identification && typeof pay.identification === "object" ? pay.identification : {};
  const monthly = pay.monthly && typeof pay.monthly === "object" ? pay.monthly : {};
  const schedule = pay.schedule && typeof pay.schedule === "object" ? pay.schedule : {};
  const scheduleRow = pay.scheduleRow && typeof pay.scheduleRow === "object" ? pay.scheduleRow : null;
  const footnote = pay.footnote && typeof pay.footnote === "object" ? pay.footnote : null;
  const capFootnote = pay.capFootnote && typeof pay.capFootnote === "object" ? pay.capFootnote : null;
  const byGrade = identification.kind === "grade_fixed_by_statute";
  const monthlyText = monthly.text || (typeof monthly.amount === "number" ? `$${monthly.amount.toLocaleString()} per month` : "a monthly rate");
  const scheduleName = `${schedule.label || "Schedule 8 — Pay of the Uniformed Services"}${schedule.effective ? ` ${schedule.effective}` : ""}`;
  const payGrade = pay.payGrade || identification.payGrade || "";
  add(`MILITARY BASIC PAY — ${scheduleName} prints ${monthlyText} for ${byGrade ? `pay grade ${payGrade || "?"}` : "the post by title"}; ${printed} a year is twelve times that, arithmetic this project performed and no document prints.`);
  if (byGrade) {
    add(` ${pay.statute || "A statute"} fixes the post's grade: "${String(pay.statuteQuote || identification.statuteQuote || "").trim()}"`);
    if (identification.officeQuote) {
      add(` The grade sentence names the office only by its title; the same section says which: "${String(identification.officeQuote).trim()}"`);
    }
    add(` ${identification.mappingCitation || "37 U.S.C. 201(a)(1)"} assigns the grade of ${pay.grade || identification.grade || "general or admiral"} to pay grade ${payGrade || "O-10"} for the purpose of computing basic pay: "${String(identification.mappingQuote || "").trim()}"`);
    if (identification.spaceForceMapping) {
      add(` 37 U.S.C. 201(a)(2), for the Space Force: "${String(identification.spaceForceMapping).trim()}"`);
    }
    if (scheduleRow && scheduleRow.note) add(` ${String(scheduleRow.note).trim()}`);
    if (capFootnote && capFootnote.note) {
      add(` ${String(capFootnote.note).trim()}`);
      if (capFootnote.text) add(` The footnote's own words: "${String(capFootnote.text).trim()}"`);
    }
  } else {
    if (footnote && footnote.text) add(` The schedule's enlisted footnote names the post: "${String(footnote.text).trim()}"`);
    if (identification.readsTwoOffices === true) {
      const item = (footnote && footnote.printedItem) || identification.printedItem || "";
      add(` The printed item "${item}" names two offices at once, and this post is one of them.`);
    }
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  for (const document of documents) {
    if (!document || typeof document !== "object") continue;
    add(` ${document.citation || "A document"} — ${document.role || "supplies part of the figure"}: "${String(document.quote || "").trim()}"`);
  }
  add(" It is a pay schedule's figure for a grade or a title, not this post as the graph draws it, so it is never a verification that the post exists. It is not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
}

function renderDerivedPay(data) {
  let line = document.getElementById("info-derived-pay");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-derived-pay";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const pay = derivedPayOf(data);
  if (!pay) {
    if (line) line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const printed = pay.rateText || `$${pay.amount.toLocaleString()}`;
  const documents = Array.isArray(pay.documents) ? pay.documents : [];
  const verification = (pay.verification && typeof pay.verification === "object") ? pay.verification : {};
  const count = Number(verification.documents || documents.length || 0);
  const percent = Number(verification.percent || 0);
  const stating = Number(verification.documentsStatingTheFigure || 0);

  add(`DERIVED PAY — no single document states this figure. ${printed}${pay.year ? ` for ${pay.year}` : ""}.`);
  const subject = pay.subject || `every judge of ${pay.court || "this court"}`;
  if (pay.arithmetic && typeof pay.arithmetic === "object" && pay.arithmetic.operation === "percent_of") {
    // A percentage, of the tier itself or of another office's pay that is in
    // turn set at the tier (the special trial judges, the two Deputies): the
    // chain, if any, is named, and the multiplication is printed as this
    // project's arithmetic and never as a quotation.
    const arithmetic = pay.arithmetic;
    const ofWhat = pay.percentOfWhat || `the salary of ${arithmetic.baseTier || "a judicial tier"}`;
    const via = pay.viaStatute ? ` ${pay.viaStatute} is the statute that puts that office at the rate of ${arithmetic.baseTier || "the tier"}.` : "";
    add(` ${pay.statute || "A statutory provision"} states that ${subject} is paid ${arithmetic.percent} percent of ${ofWhat}.${via} The U.S. Courts' Judicial Compensation table prints ${arithmetic.baseText || "a figure"} for ${arithmetic.baseTier || "that tier"}. ${arithmetic.baseText || "That figure"} × ${arithmetic.percent}% = ${printed} — arithmetic this project performed, printed by no document.`);
    // A statute that states a CEILING ("up to" 92 percent, 28 U.S.C. 634(a))
    // prices nothing by itself; the same compensation page prints, beneath its
    // table, the sentence saying what the Judicial Conference fixed under it,
    // and the block carries that sentence with the reading in words.
    if (pay.ceilingBasis && typeof pay.ceilingBasis === "object" && pay.ceilingBasis.quote) {
      add(` ${pay.statute || "That statute"} states a CEILING ("up to" that percentage), not a rate. The same Judicial Compensation page prints beneath its table: "${String(pay.ceilingBasis.quote).trim()}" — the document that says what the Judicial Conference fixed under the ceiling. ${pay.ceilingBasis.reading ? String(pay.ceilingBasis.reading).trim() : ""}`);
    }
  } else if (pay.viaStatute) {
    add(` ${pay.statute || "A statutory parity provision"} states that ${subject} is paid what another office is paid; ${pay.viaStatute} states that that office is paid at the rate of ${pay.amountScope || "a judicial tier"}; the U.S. Courts' Judicial Compensation table states what that tier pays. The figure is the join of the three.`);
  } else {
    add(` ${pay.statute || "A statutory parity provision"} states that ${subject} is paid at the rate of ${pay.amountScope || "another court's judges"}; the U.S. Courts' Judicial Compensation table states what that tier pays. The figure is the join of the two.`);
  }
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  for (const document of documents) {
    if (!document || typeof document !== "object") continue;
    add(` ${document.citation || "A document"} — ${document.role || "supplies part of the figure"}: "${String(document.quote || "").trim()}"`);
  }
  add(" It names a tier, not this post by name, so it is a reviewed identification and never a verification. It is not this unit's cost: basic pay excludes benefits and is not a share of federal outlays.");
}

// How many documents a pay figure rests on, and what that count is worth on
// this project's own source arithmetic — the same 0.4 / +0.3 / +0.1 scale the
// verification box prints for a node's own sources, so the two percentages on
// one panel mean the same thing rather than two different things wearing the
// same "%". `documentsStatingTheFigure` rides beside it because on one field
// it is ZERO — a derived rate's two documents between them imply a number
// neither prints — and a bare percentage would hide exactly that.
// A pay figure on a node that stands for several posts. The sweep keeps an
// office-rate claim on such a node -- a statutory tier rate, a parity-derived
// rate, a Title 38 band -- and stamps `holders` from the node's own stated
// multiplicity, because the figure is the tier's and holds for each holder
// alike. This sentence is what stops it reading as one person's pay or as the
// group's combined pay. A roster figure carries `holders.uniformRate` only
// when the report listed every holder at one identical rate.
function holdersSentence(block) {
  const holders = block && typeof block === "object" ? block.holders : null;
  if (!holders || typeof holders !== "object") return "";
  const text = String(holders.text || "").trim();
  const count = Number.isInteger(holders.count) ? holders.count : null;
  const who = count !== null ? `${count} posts` : text ? `several posts (${text})` : "several posts";
  if (holders.uniformRate === true) {
    return ` This node stands for ${who}, and the report lists every one of them at this same rate: the figure is each listed person's pay, not one person's and not the group's combined pay.`;
  }
  return ` This node stands for ${who}. The figure is the rate the source states for the office or tier and applies to each holder alike; it is not one person's pay and not the group's combined pay.`;
}

function payDocumentsSentence(block) {
  const verification = block && typeof block === "object" ? block.verification : null;
  if (!verification || typeof verification !== "object") return "";
  const count = Number(verification.documents || 0);
  if (!count) return "";
  const stating = Number(verification.documentsStatingTheFigure || 0);
  const states =
    stating === 0
      ? "none of them states the figure itself"
      : stating === count
        ? count === 1
          ? "it states the figure itself"
          : "all of them state the figure itself"
        : `${stating} of them states the figure itself`;
  return ` ${count} official document${count === 1 ? " verifies" : "s verify"} this — ${Number(verification.percent || 0)}% on this project's own source scale (0.4 for the first, +0.3 for an official site, +0.1 each further one), and ${states}. That measures how much official documentation the figure rests on, not the chance that it is right.`;
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
      `${on ? ` (checked ${on})` : ""} lists ${pay.holders && pay.holders.uniformRate === true && Number.isInteger(pay.holders.count) ? `${pay.holders.count} people` : "one person"} under "${pay.reportedTitle || "this title"}"` +
      `${pay.asOf ? `, as of ${pay.asOf}` : ""}, paid ${printed}${pay.payBasis ? ` ${String(pay.payBasis).toLowerCase()}` : ""}.`,
  );
  add(pay.holders && pay.holders.uniformRate === true
    ? " That is what each person listed under this title is paid — the report states each individual's own rate, and here every one of them is the same figure — not what the post pays whoever holds it."
    : " That is what the one person listed under this title is paid, not what the post pays whoever holds it: the report states each individual's own rate, and two people can share a title at different salaries.");
  if (pay.titleFolded) {
    add(" The report spells the title with its White House rank in front; that prefix is set aside to match this unit.");
  }
  add(" It is not this unit's cost — basic pay excludes benefits and is not a share of federal outlays — and it is not evidence that this post exists as the graph draws it.");
  add(holdersSentence(pay));
  add(payDocumentsSentence(pay));
  const quote = String(pay.quote || "").trim();
  if (quote) add(` The report's own row: "${quote}"`);
}

// OPM's CURRENT PLUM export — the live counterpart of the archive above. A
// second, independent document: it says the post is listed now (Filled or
// Vacant), under which organisation, on which pay plan, and on ES rows what
// the one row under the title is paid. A row is an incumbency, so the rate
// is deliberately the row's figure and never "what the post pays". Its own
// element, drawn whatever the estimates toggle says, headed CURRENT PLUM
// BOOK so a reader can tell it from the archive's record of a period that
// ended.
function currentPayOf(node) {
  const pay = node.positionCurrentPay;
  if (!pay || typeof pay !== "object") return null;
  return typeof pay.amount === "number" && pay.amount > 0 ? pay : null;
}

function formatFetchDate(stamp) {
  return stamp
    ? new Date(stamp).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
    : null;
}

function renderCurrentListing(data) {
  let line = document.getElementById("info-current-listing");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-current-listing";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const listing = data.positionCurrentListing;
  if (!listing || typeof listing !== "object") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const on = formatFetchDate(listing.exportFetchedAt);
  add(`CURRENT PLUM BOOK: OPM's PLUM Reporting export${on ? `, fetched ${on},` : ""} lists "${listing.listedTitle}"`);
  if (listing.organization) add(` under ${listing.organization}`);
  if (listing.agency && listing.agency !== listing.organization) add(` (${listing.agency})`);
  if (listing.scopeRule === "office_named_for_the_post") {
    // The export files the title under a unit named for the post itself —
    // "Office of the General Counsel" / "General Counsel" — that this graph
    // draws no node for; the post sits directly under the agency here.
    add(" — a unit named for this very post, which this graph has no node for; the post is drawn directly under the agency here");
  }
  if (listing.positionStatus) {
    add(`, ${String(listing.positionStatus).toLowerCase()}`);
  } else if (listing.positionStatusCounts && typeof listing.positionStatusCounts === "object") {
    // The two statuses this listing can carry are a closed set (the module
    // reads no Historical row), so they are named rather than enumerated:
    // js/ never enumerates node keys, which is what lets the viewer copy be
    // pruned safely.
    const counts = listing.positionStatusCounts;
    const parts = ["Filled", "Vacant"].filter((k) => counts[k]).map((k) => `${counts[k]} ${k.toLowerCase()}`);
    if (parts.length) add(`, ${parts.join(" and ")}`);
  }
  const rows = Number(listing.rowsListed) || 0;
  if (rows > 1) add(` (${rows} rows under this title)`);
  add(". ");
  if (listing.appointmentType) add(`Appointment type ${listing.appointmentType}. `);
  if (listing.payPlan) add(`Pay plan ${listing.payPlan}`);
  if (listing.payLevel) {
    add(`${listing.payPlan ? ", " : ""}${listing.payPlan === "EX" ? "Executive Schedule level" : "level or grade"} ${listing.payLevel}`);
    add(". The export gives the rank, not a rate of pay. ");
  } else if (listing.payPlan) {
    add(". ");
  }
  if (typeof listing.reportedPay === "number" && listing.reportedPay > 0) {
    add(`It prints basic pay of ${listing.reportedPayText || `$${listing.reportedPay.toLocaleString()}`} for the one row listed under this title — what that listing is paid, not what the post pays whoever holds it, and not this unit's cost. `);
  }
  add("A Vacant row is still a listed position. This says nothing about who holds the post: the export's name columns are never read.");
  if (levelSourceIsCurrent(data.positionPayRate)) renderTableRate(data, add);
  if (levelSourceIsCurrent(data.positionGradePay)) renderGradePay(data, add);
}

// USAJOBS vacancy announcements listing a title family at a pay plan and
// grade. A listing of the TITLE, not of this post: each announcement is one
// vacancy at one facility, none names this node, and the identification of
// the family is reviewed. It verifies nothing, and no announcement's salary
// is shown -- the range beneath it is OPM's base range for the grade.
function renderVacancyListing(data) {
  let line = document.getElementById("info-vacancy-listing");
  if (!line && dom.infoStats) {
    line = document.createElement("div");
    line.id = "info-vacancy-listing";
    line.style.fontSize = "9px";
    line.style.color = "#8f7a5d";
    line.style.letterSpacing = "0.06em";
    line.style.margin = "2px 0 8px";
    dom.infoStats.insertAdjacentElement("afterend", line);
  }
  if (!line) return;
  const listing = data.positionVacancyListing;
  if (!listing || typeof listing !== "object") {
    line.replaceChildren();
    return;
  }
  line.replaceChildren();
  const add = (text) => line.appendChild(document.createTextNode(text));
  const announcements = Array.isArray(listing.announcements) ? listing.announcements : [];
  const on = formatFetchDate(listing.checkedAt);
  add(`VACANCY ANNOUNCEMENTS: ${announcements.length} USAJOBS announcements${on ? `, fetched by ${on},` : ""} list a post of this title family at ${listing.payPlan}-${listing.payLevel}`);
  const places = announcements
    .filter((a) => a && typeof a === "object")
    .map((a) => `${a.hiringOrganization}${Array.isArray(a.locations) && a.locations.length ? ` (${a.locations.join(", ")})` : ""}, opened ${a.openDate}, "${a.title}"`);
  if (places.length) add(`: ${places.join("; ")}`);
  add(". Each states the pay plan and grade of one vacancy at one facility. None names this post; that this node is the title they advertise is a reviewed identification, so the listing says nothing about whether this post exists or who holds it. Their own salaries include a duty station's locality pay and are not shown.");
  if (levelSourceIsVacancy(data.positionGradePay)) renderGradePay(data, add);
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
    // Led by the percentage and by how many documents produced it, because
    // that is what the number actually is: verify_node_sources scores 0.4 for
    // the first official document, +0.3 where one is an official site, and
    // +0.1 for each further one. "Sources: 1" said the count and left the
    // reader to guess what turned it into 0.70. A derived pay figure prints
    // the same scale in its own block, so the two are comparable.
    const documents = linkableSources.length;
    setText(
      dom.verificationConfidence,
      `Verification: ${Math.round(confidence * 100)}% — ${documents} official document${documents === 1 ? "" : "s"}`
      + ` (${confidence.toFixed(2)}: 0.4 for the first, +0.3 for an official site, +0.1 each further one)`,
    );
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
      // The Manual's TOP-LEVEL entry for the office itself, rather than an
      // agency's entry listing one of its officers. Two nodes carry it: the
      // President and the Vice President, neither of which any other route
      // in this project can reach.
      listed_as_its_own_entry_in_us_government_manual:
        "The United States Government Manual carries an entry for the office itself",
      // Worded as what was read and when. Every rule and notice ends with a
      // signature block naming the signing official and their title; this is
      // the title, never the name. The document and its date follow below,
      // because a signature is a fact about one moment and not about now.
      signed_a_federal_register_document:
        "An official signing a published Federal Register document stated this title",
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
    // The Manual's top-level entry FOR an office. A different claim again:
    // not an agency's entry listing an officer, but an entry whose subject
    // IS the office. No placement is ever claimed from it — one entry was
    // read and it yields one observation.
    const govmanOffice = data.govmanOfficeEntry;
    if (govmanOffice && typeof govmanOffice === "object") {
      const alreadyOffice = String(data.verificationMethod || "") === "listed_as_its_own_entry_in_us_government_manual";
      const heading = govmanOffice.listedName ? ` headed "${govmanOffice.listedName}"` : "";
      const printedAs =
        govmanOffice.matchedName && govmanOffice.matchedName !== govmanOffice.listedName
          ? `, which prints the office as "${govmanOffice.matchedName}"`
          : "";
      const officeEdition = govmanOffice.edition ? ` (${govmanOffice.edition} edition)` : "";
      checkLine += alreadyOffice
        ? `${heading}${printedAs}${officeEdition}`
        : ` · the United States Government Manual also carries a top-level entry for the office${heading}${printedAs}${officeEdition}`;
    }
    // A Federal Register signature, beside any other claim or as the claim
    // itself. The document and its publication date are printed because that
    // is the whole of what a signature establishes: the post existed and was
    // filled on that day. The signer is never named — the name line of the
    // block is read only so as to be excluded — so the sentence must not read
    // as a statement about who holds the post now.
    const signature = data.federalRegisterSignature;
    if (signature && typeof signature === "object") {
      const already = String(data.verificationMethod || "") === "signed_a_federal_register_document";
      const quoted = signature.listedTitle ? ` as "${signature.listedTitle}"` : "";
      const kind = String(signature.documentType || "document").toLowerCase();
      const asDate = (value) =>
        value ? new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }) : "";
      // The Register states a signing date on some documents and not others.
      // Where it does not, the only date that can be cited is the day it was
      // published, and the signature is necessarily on or before it.
      const signed = asDate(signature.signingDate);
      const published = asDate(signature.publicationDate);
      const when = signed ? `, signed ${signed}` : published ? `, published ${published}` : "";
      const doc = `${kind} ${signature.documentNumber}${when}`;
      checkLine += already
        ? `${quoted} on ${doc}`
        : ` · an official signing Federal Register ${doc} stated this title${quoted}`;
      if (signature.occurrences > 1) checkLine += ` (${signature.occurrences} of the documents read carry it)`;
      checkLine += signed
        ? ` — the office was filled on that day`
        : ` — the office was filled when that document was signed, on or before the day it was published`;
      checkLine += `; the signer's name is not read, and this says nothing about who holds it now`;
    }
    // Both facts, where both are true: a directory lists it, and its own
    // page was read and did not name it. Withdrawing the badge is right —
    // the node has a source — but the read still happened.
    // The whole point of the alternative-names table, said in words: the page
    // or the entry did NOT print the name above. Both names are quoted — the
    // graph's and the source's — with the basis the reviewed table states for
    // taking them to be one unit, and the sentence says plainly when a claim
    // resting only on this is held at "partial". An organisation-scoped match
    // says whose name it was, because the post's own title matched outright
    // and only its agency needed the table.
    const aliasMatch = data.verificationAliasMatch;
    if (aliasMatch && typeof aliasMatch === "object" && aliasMatch.alias) {
      checkLine +=
        aliasMatch.scope === "organisation"
          ? ` · the source files it under its organisation by a different recorded name, "${aliasMatch.alias}", which is not what this graph calls that unit`
          : ` · the source names it "${aliasMatch.alias}", not "${data.name || ""}", and that alternative is a reviewed entry in this project's own table`;
      if (aliasMatch.basis) checkLine += ` — the reviewed basis for treating the two as one unit: ${aliasMatch.basis}`;
      if (aliasMatch.gradedAtMost === "partial") {
        checkLine += " · nothing else names this unit, so the check is graded no higher than partial";
      }
    }
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

  // The full root-to-node path, every step by its whole name, each row a
  // real button. This list was once removed as a duplicate of the breadcrumb;
  // the owner asked for it back (2026-09-23), and the breadcrumb is not the
  // same thing: it truncates any name past 28 characters, so on a deep post
  // ("Chief — Environmental Management" under a VISN under the VHA) the
  // breadcrumb shows six ellipses and this list shows six names. The glowing
  // path through the 3D scene (graph.js's pathGlowPool) is what the button
  // also switches on, and the line beneath the list says so.
  const fragment = document.createDocumentFragment();
  originTrace.forEach((item, index) => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "flex-start";
    row.style.gap = "8px";
    row.style.color = item.data.color || "#d4c4a1";
    row.style.paddingLeft = `${index * 10}px`;
    row.style.lineHeight = "1.4";

    const marker = document.createElement("span");
    marker.textContent = index === 0 ? "•" : "→";
    marker.style.color = "rgba(220, 210, 180, 0.75)";
    marker.style.flex = "0 0 auto";
    row.appendChild(marker);

    const label = document.createElement("span");
    label.textContent = item.data.name;
    row.appendChild(label);

    if (index === originTrace.length - 1) {
      const here = document.createElement("span");
      here.textContent = "(this node)";
      here.style.color = "#9a8a6a";
      here.style.fontSize = "9px";
      here.style.marginLeft = "4px";
      row.appendChild(here);
    }

    makeInteractiveRow(row, `Go to ${item.data.name}`, () => state.graph.setSelectedNode(item));
    fragment.appendChild(row);
  });
  dom.originList.appendChild(fragment);

  const confirmation = document.createElement("div");
  confirmation.style.color = "#9a8a6a";
  confirmation.style.fontSize = "9px";
  confirmation.style.lineHeight = "1.5";
  confirmation.style.marginTop = "4px";
  confirmation.textContent = `${originTrace.length} step${originTrace.length === 1 ? "" : "s"} from the root; the same path is highlighted in the scene above.`;
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
// figure at all: the pay an official document states for the post. Ten
// fields can carry one (nine until Schedule 8's military basic pay landed on
// 2026-10-06), and until 2026-10-05 only three of them reached this
// headline (the current export's printed rate, the archive's, a table's
// range): a post priced from the Executive Schedule, from a statute, from the
// White House roster or from a parity provision read "No cost known for this
// node" above a nine-pixel line stating its salary — which is how the
// President of the United States was published at "Not available" with
// $400,000 a year printed beneath. Every field reaches it now, in the order
// below: a figure a document states for the OFFICE first, then one it states
// for an incumbency, then a figure this project derived from two documents,
// then a range. Each is headed as the claim it is, never as COST, and the
// block beneath says what the figure is and is not. Never beside a measured
// cost, and null where there is nothing to stand in.
const PAY_STAND_IN_ORDER = [
  ["statutory", (node) => positiveAmountBlock(node.positionStatutoryPay)],
  ["schedule", (node) => positiveAmountBlock(node.positionSchedulePay)],
  ["tierReference", (node) => tierReferencePayOf(node)],
  ["derived", (node) => derivedPayOf(node)],
  ["military", (node) => militaryPayOf(node)],
  ["reported", (node) => positiveAmountBlock(node.positionReportedPay)],
  ["current", (node) => currentPayOf(node)],
  ["pay", (node) => reportedPayOf(node)],
  ["tableRate", (node) => positiveAmountBlock(node.positionPayRate)],
  ["range", (node) => gradePayOf(node)],
  ["tier", (node) => tierPayOf(node)],
];

// A post whose employer committed documents say is not the federal
// government (employment_status.py, since 2026-10-07): a post of one of
// DOE's sixteen contractor-operated laboratories. Only where no pay document
// prices the post and no cost is measured for it; the gate refuses the block
// beside either, and this reads it the same way so a stale copy never wins.
function employerOf(node) {
  const block = node && node.positionEmployer;
  if (!block || typeof block !== "object") return null;
  if (block.federallyPaid !== false || block.kind !== "contractor_operated_laboratory") return null;
  if (isCostIdentifiedForTheNode(node)) return null;
  for (const [, read] of PAY_STAND_IN_ORDER) {
    if (read(node)) return null;
  }
  return block;
}

function buildEmployerLines(block) {
  const host = document.createElement("div");
  host.id = "info-employer";
  host.className = "info-cost-note";
  const head = document.createElement("strong");
  head.textContent = String(block.headline || "");
  host.appendChild(head);
  host.appendChild(document.createTextNode(` ${String(block.notEstablished || "").trim()}`));
  // What the documents establish, in their own words rather than a
  // paraphrase: each one linked, then its quotes verbatim (a CFR quote with
  // the section it sits in).
  const docs = Array.isArray(block.documents) ? block.documents.filter((d) => d && typeof d.url === "string" && /^https:\/\//.test(d.url)) : [];
  if (docs.length) {
    host.appendChild(document.createTextNode(` The ${docs.length} documents, in their own words:`));
    for (const doc of docs) {
      host.appendChild(document.createTextNode(" "));
      const link = document.createElement("a");
      link.href = doc.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `${doc.title || doc.url}${doc.dated ? ` (${doc.dated})` : ""}`;
      host.appendChild(link);
      const quotes = Array.isArray(doc.quotes) ? doc.quotes.filter((q) => q && typeof q.text === "string") : [];
      host.appendChild(document.createTextNode(`: ${quotes.map((q) => `${q.section ? `§${q.section} ` : ""}"${q.text}"`).join("; ")}.`));
    }
    host.appendChild(document.createTextNode(" None of them names this post, and none is a source of its existence."));
  }
  return host;
}

function positiveAmountBlock(block) {
  return block && typeof block === "object" && typeof block.amount === "number" && block.amount > 0 ? block : null;
}

// The same mechanism one level up, by the owner's decision of 2026-10-07: an
// ORGANISATION with no measured cost of its own may carry a sourced figure of
// another kind under its own heading below the cost block — USAspending's
// File A gross outlays, the sum of OMB's account rows for a completed year,
// Treasury's audited net cost — and until now its headline read "Not
// available" above them. Where it carries one, that figure is the headline
// instead, headed as the kind of figure it is and never as COST.
//
// The order is declared, and it is the anchor's two coordinates. The anchor
// is the Monthly Treasury Statement's NET OUTLAYS for the CURRENT fiscal year
// TO DATE (`__budgetSummary.amount_kind: fytd_net_outlays`), so the figure
// that stands in for it should sit as near as possible on both clocks:
//
//   1. File A gross outlays — the same fiscal year, to date (as of a date
//      weeks from the anchor's), and cash out of the door like the anchor;
//      the basis differs only in being GROSS, before the offsetting
//      collections the statement nets off.
//   2. OMB's outlays — the same basis as the anchor (net of offsetting
//      collections; OMB's guide calls its totals "generally consistent with"
//      the statement), but for a COMPLETED year, and a sum of account rows
//      OMB never totals itself.
//   3. Audited net cost — a completed year AND an accrual basis, gross cost
//      less earned revenue: the furthest from net outlays on both counts.
//
// Between the first two the trade is clock against basis, and it was
// measured rather than argued: on the 9 measured nodes that carry both File A
// and OMB beside their Treasury line, File A's figure sits a median 7.7% from
// the measured one and OMB's 18.4% (6 of 9 within 10% against 3 of 9). Same
// year beats same basis here, because a unit's year-on-year change is usually
// larger than its offsetting collections. A sample of nine is small, so the
// reason is the clock and the measurement only agrees with it.
//
// A post never uses this path (the pay order above is its headline), nor a
// measured node, a Treasury accounting line or a replaced unit. A unit beneath
// a negative Treasury pool may: it has no estimate, and these figures are
// about it rather than apportioned to it. Zero is never a headline.
const SOURCED_FIGURE_STAND_IN_ORDER = [
  ["fileA", (node) => nonZeroBlock(node.usaspendingOutlays, "amount")],
  ["omb", (node) => nonZeroBlock(node.ombBudget, "outlays")],
  ["audited", (node) => nonZeroBlock(node.auditedNetCost, "netCostUsd")],
];

const SOURCED_FIGURE_KINDS = new Set(SOURCED_FIGURE_STAND_IN_ORDER.map(([name]) => name));

// A figure below zero is published as the source prints it (OMB's FDIC,
// Treasury's audited FDIC); only zero, which no source here publishes as a
// measurement, and a missing figure are refused.
function nonZeroBlock(block, field) {
  if (!block || typeof block !== "object") return null;
  const amount = block[field];
  return typeof amount === "number" && Number.isFinite(amount) && amount !== 0 ? block : null;
}

// The pipeline's own POST_TYPE_KEYWORDS (position, role, office holder): a
// post is not a budget unit and never takes an organisation's figure.
function isPostType(node) {
  return /position|\brole\b|office holder/i.test(String(node.type || ""));
}

function canTakeSourcedFigure(node) {
  if (isPostType(node)) return false;
  if (String(node.synthetic || "") || /treasury accounting line/i.test(String(node.type || ""))) return false;
  if (String(node.lifecycle || "") === "superseded" || String(node.cost_validation || "") === "unit_superseded") return false;
  return true;
}

// Which sourced figure this organisation's headline would show when no
// estimate is on screen, by the declared order — independent of the
// estimates toggle, so the reading guide can count the same thing the panel
// shows in the default view.
function sourcedFigureOf(node) {
  if (isCostIdentifiedForTheNode(node) || !canTakeSourcedFigure(node)) return null;
  for (const [name, read] of SOURCED_FIGURE_STAND_IN_ORDER) {
    const block = read(node);
    if (block) return { kind: name, block };
  }
  return null;
}

function costStandInOf(node) {
  if (isCostIdentifiedForTheNode(node)) {
    return null;
  }
  let kind = null;
  let block = null;
  for (const [name, read] of PAY_STAND_IN_ORDER) {
    block = read(node);
    if (block) {
      kind = name;
      break;
    }
  }
  if (!block) {
    const sourced = sourcedFigureOf(node);
    if (sourced) {
      ({ kind, block } = sourced);
    }
  }
  if (!block) {
    return null;
  }
  const status = String(node.cost_status || "").toLowerCase();
  const nothingElse = !status || status === "unavailable" || toFiniteAmount(node.resolved_total_amount) === null || isBelowPrecision(node);
  if (!(hasWithheldEstimate(node) || nothingElse)) {
    return null;
  }
  // The three named keys are kept for the callers that read them: the
  // multi-post sentence asks whether the archive's one-post rate is what is
  // shown, and nothing else should start asking by kind through them.
  return {
    kind,
    block,
    sourced: SOURCED_FIGURE_KINDS.has(kind),
    current: kind === "current" ? block : null,
    pay: kind === "pay" ? block : null,
    range: kind === "range" ? block : null,
  };
}

function showsCurrentPayInsteadOfCost(node) {
  const standIn = costStandInOf(node);
  return Boolean(standIn && standIn.current);
}

function showsPayInsteadOfCost(node) {
  const standIn = costStandInOf(node);
  return Boolean(standIn && standIn.pay);
}

function showsRangeInsteadOfCost(node) {
  const standIn = costStandInOf(node);
  return Boolean(standIn && standIn.range);
}

function lowerEffective(text) {
  return String(text || "").replace(/^Effective\b/, "effective");
}

// The figure as the document prints it: a rate's own text, a range's two
// bounds. Never one figure for a range.
function standInAmountText(standIn) {
  const block = standIn.block;
  switch (standIn.kind) {
    case "pay":
      return block.reportedPayText || `$${Math.round(block.reportedPay).toLocaleString()}`;
    case "range":
    case "tier":
      return formatGradeRange(block);
    case "fileA":
      return formatSignedWholeDollars(block.amount);
    case "omb":
      return formatSignedWholeDollars(block.outlays);
    case "audited":
      return formatSignedWholeDollars(block.netCostUsd);
    default:
      return block.rateText || `$${Math.round(block.amount).toLocaleString()}`;
  }
}

// A sourced figure as the block carries it, to the dollar, the sign leading:
// OMB's FDIC nets below zero and is printed so, not as "$-31…".
function formatSignedWholeDollars(amount) {
  return `${amount < 0 ? "-" : ""}$${Math.round(Math.abs(amount)).toLocaleString()}`;
}

// The year a block names, or words saying it names none — never a year this
// code supplies.
function blockFiscalYear(value) {
  const text = String(value ?? "").trim();
  return text ? `FY${text}` : "a fiscal year the record does not state";
}

// The heading drawn where COST would be, and the line beneath it that says
// which document and that it is not a cost. The heading is the first thing a
// reader takes as the claim, so none of them is the word COST and each names
// the kind of claim: a statute's rate, a schedule level, a roster's figure, a
// derivation, a range.
function standInHeading(standIn) {
  const block = standIn.block;
  const fetched = formatFetchDate(block.exportFetchedAt);
  switch (standIn.kind) {
    case "statutory": {
      const seat = block.memberSeat && typeof block.memberSeat === "object";
      return {
        label: seat ? "PAY — A MEMBER'S SEAT, NOT THE OFFICE" : block.statesTheOffice === true ? "PAY — STATED BY THE U.S. CODE" : "PAY — STATUTORY RATE",
        period: `${block.sourceLabel || "a primary official source"}${block.year ? `, ${block.year}` : ""} — a rate of basic pay, not a cost`,
      };
    }
    case "schedule":
      return {
        label: "PAY — EXECUTIVE SCHEDULE",
        period: `${block.citation || "5 U.S.C. 5312–5316"} sets the level; OPM's ${block.table || "salary table"}${block.effectiveText ? `, ${lowerEffective(block.effectiveText)}` : ""}, prices it — a rate of basic pay, not a cost`,
      };
    case "tierReference":
      return {
        label: "PAY — SET BY REFERENCE TO A LEVEL",
        period: `${block.statute || "a statute"} names Executive Schedule ${block.levelText || `level ${block.level}`}${block.percent ? ` plus ${block.percent} percent` : ""}; no document states this figure for the post`,
      };
    case "derived":
      return {
        label: "PAY — DERIVED, STATED BY NO DOCUMENT",
        period: `${block.statute || "a statutory provision"} joined to the U.S. Courts' compensation table${block.year ? `, ${block.year}` : ""} — a rate of basic pay, not a cost`,
      };
    case "military": {
      const schedule = block.schedule && typeof block.schedule === "object" ? block.schedule : {};
      const byGrade = block.identification && typeof block.identification === "object" && block.identification.kind === "grade_fixed_by_statute";
      return {
        label: "PAY — MILITARY BASIC PAY, 12 × THE MONTHLY RATE",
        period: `${schedule.label || "Schedule 8 — Pay of the Uniformed Services"}${schedule.effective ? `, ${lowerEffective(String(schedule.effective).replace(/^\(|\)$/g, ""))}` : ""}; ${byGrade ? `${block.statute || "a statute"} fixes the grade` : "its own footnote names the post"} — a rate of basic pay, not a cost`,
      };
    }
    case "reported":
      return {
        label: "PAY — WHITE HOUSE STAFF REPORT",
        period: `the White House Office's annual report to Congress${block.asOf ? `, as of ${block.asOf}` : ""} — the listed person's rate of basic pay, not a cost`,
      };
    case "current":
      return {
        label: "PAY — CURRENT PLUM BOOK",
        period: `OPM's current Plum Book export${fetched ? `, fetched ${fetched}` : ""} — one row's rate of basic pay, not a cost`,
      };
    case "pay":
      return { label: "REPORTED RATE OF BASIC PAY", period: null };
    case "tableRate":
      return {
        label: "PAY — RATE FOR THE LISTED LEVEL",
        period: `OPM's ${block.table || "salary table"}${block.effectiveText ? `, ${lowerEffective(block.effectiveText)}` : ""}, for ${block.amountScope || "the level"} a PLUM listing reports — a table's rate for a rank, not a cost`,
      };
    case "range":
      return { label: block.kind === "general_schedule_grade" ? "BASE PAY RANGE, BEFORE LOCALITY" : "PAY SYSTEM RANGE", period: null };
    case "tier":
      return {
        label: "TITLE 38 PAY RANGE, NOT A RATE",
        period: `the VA's ${block.table || "Title 38 pay table"}${block.effectiveText ? `, ${lowerEffective(block.effectiveText)}` : ""} — bounds for an appointment, not a rate and not a cost`,
      };
    // An organisation's sourced figure of another kind. The label names the
    // measure and the publisher; the period line, read off the block, says
    // which year and in what sense, and that it is not the cost. The audited
    // statement's measure is called "net cost" by its publisher, and its
    // label keeps that name rather than renaming the figure — the period line
    // says it is accrual and not outlays.
    case "fileA":
      return {
        label: "GROSS OUTLAYS — USASPENDING FILE A",
        period: `${blockFiscalYear(block.fiscalYear)} to ${block.periodAsOf || "an unstated date"}, fiscal year to date — gross, before offsetting collections; not the cost`,
      };
    case "omb":
      return {
        label: "OUTLAYS — OMB PUBLIC BUDGET DATABASE",
        period: `${blockFiscalYear(block.fiscalYear)}, a completed year — the sum of ${Number.isInteger(block.outlayAccountRows) ? `${block.outlayAccountRows.toLocaleString()} account rows` : "the account rows"} OMB files under this unit, not a figure OMB prints, and not the cost`,
      };
    case "audited":
      return {
        label: "AUDITED NET COST — TREASURY STATEMENT OF NET COST",
        period: `${blockFiscalYear(block.fiscalYear)}${block.statementDate ? `, ended ${block.statementDate}` : ""} — accrual, not outlays; not the cost`,
      };
    default:
      return { label: "PAY", period: null };
  }
}

function standInBadgeLabel(standIn) {
  switch (standIn.kind) {
    case "statutory":
      return standIn.block.memberSeat ? "No cost known; the Member's seat rate is shown" : "No cost known; the statutory rate of pay is shown";
    case "schedule":
      return "No cost known; the Executive Schedule rate is shown";
    case "tierReference":
      return "No cost known; a rate set by reference to a level is shown";
    case "derived":
      return "No cost known; a derived rate of pay is shown";
    case "military":
      return "No cost known; twelve months of the schedule's monthly basic pay are shown";
    case "reported":
      return "No cost known; the staff report's rate of pay is shown";
    case "current":
      return "No cost known; the current Plum Book's rate of pay is shown";
    case "pay":
      return "No cost known; a reported rate of pay is shown";
    case "tableRate":
      return "No cost known; the table's rate for the listed level is shown";
    case "range":
      return "No cost known; a base-pay range is shown";
    case "tier":
      return "No cost known; a Title 38 pay range is shown";
    case "fileA":
    case "omb":
    case "audited":
      return "No measured cost; a sourced figure of another kind is shown";
    default:
      return "No cost known; a rate of pay is shown";
  }
}

// The sentence appended to the cost note saying what the headline figure IS,
// per kind — the detailed block each pay field renders below carries the
// documents, the quote and the document count; this says only enough that a
// reader who stops at the badge is not misled about what the number means.
function standInNote(standIn) {
  const block = standIn.block;
  const printed = standInAmountText(standIn);
  let note = "";
  switch (standIn.kind) {
    case "statutory": {
      const seat = block.memberSeat && typeof block.memberSeat === "object" ? block.memberSeat : null;
      note = seat
        ? ` What is shown instead is a Member's pay: ${block.sourceLabel || "Schedule 6"} prints ${printed} on its row "${seat.row || block.amountScope || "Members"}"${block.year ? ` for ${block.year}` : ""}, and the holder of this office is a Member of the chamber, for whom no separate rate is printed. That is a salary, not what this unit costs.`
        : block.statesTheOffice === true
          ? ` What is shown instead is the salary ${block.sourceLabel || "a section of the United States Code"} states for ${block.office || block.amountScope || "the office"}: ${printed}. A salary is not what this unit costs.`
          : ` What is shown instead is a statutory rate of basic pay: ${block.sourceLabel || "a primary official source"} states ${printed} for ${block.amountScope || "this tier"}${block.year ? ` for ${block.year}` : ""}. It names a tier or a group of roles rather than this post by name, and a salary is not what this unit costs.`;
      break;
    }
    case "schedule":
      note = ` What is shown instead is the Executive Schedule rate: ${block.citation || "the United States Code"} places "${block.statutoryTitle || "this office"}" at level ${block.payLevel || "?"}, and OPM's ${block.table || "salary table"} pays ${printed} for that level. A statutory rate of basic pay, not what the holder receives and not what this unit costs.`;
      break;
    case "tierReference": {
      const minus = block.arithmetic && typeof block.arithmetic === "object" && block.arithmetic.operation === "minus_dollars" ? block.arithmetic : null;
      note = minus
        ? ` What is shown instead is pay a statute sets by reference: ${block.statute || "a statute"} pays this post ${minus.minusDollarsText || `$${minus.minusDollars}`} less than the ${minus.baseOffice || "officer it names"}, whose pay is tied to Executive Schedule ${block.levelText || `level ${block.level}`}, and OPM's table prices that level; the subtraction is arithmetic this project performed. No document states ${printed} for the post itself, and it is not what this unit costs.`
        : ` What is shown instead is pay a statute sets by reference: ${block.statute || "a statute"} ties this post${block.viaStatute ? `, through ${block.viaStatute},` : ""} to Executive Schedule ${block.levelText || `level ${block.level}`}${block.percent ? ` plus ${block.percent} percent` : ""}, and OPM's table prices that level${block.percent ? "; the result is arithmetic this project performed" : ""}. No document states ${printed} for the post itself, and it is not what this unit costs.`;
      break;
    }
    case "derived":
      note = ` What is shown instead is a figure no document states: ${block.statute || "a statutory provision"} sets the pay at ${block.amountScope || "another tier's rate"}, the U.S. Courts' Judicial Compensation table prices that tier, and ${printed} is the join${block.arithmetic && typeof block.arithmetic === "object" ? ", with the statute's percentage applied" : ""}. Not what this unit costs.`;
      break;
    case "military": {
      const monthly = block.monthly && typeof block.monthly === "object" ? block.monthly : {};
      const schedule = block.schedule && typeof block.schedule === "object" ? block.schedule : {};
      const byGrade = block.identification && typeof block.identification === "object" && block.identification.kind === "grade_fixed_by_statute";
      note = ` What is shown instead is twelve months of military basic pay: ${schedule.label || "Schedule 8 — Pay of the Uniformed Services"} prints ${monthly.text || "a monthly rate"} for ${byGrade ? `pay grade ${block.payGrade || "?"}, the grade ${block.statute || "a statute"} fixes for this post` : "this post, which its own footnote names by title"}, and ${printed} is twelve times that — arithmetic this project performed, which no document prints, and not what this unit costs.`;
      break;
    }
    case "reported":
      note = ` What is shown instead is the rate the White House Office's own annual report to Congress lists under "${block.reportedTitle || "this title"}"${block.asOf ? ` (as of ${block.asOf})` : ""}: ${printed}. That is what the listed person is paid, not what the post pays whoever holds it, and not what this unit costs.`;
      break;
    case "current":
      note = ` What is shown instead is a rate of basic pay: OPM's current PLUM Reporting export` +
        `${formatFetchDate(block.exportFetchedAt) ? ` (fetched ${formatFetchDate(block.exportFetchedAt)})` : ""}` +
        ` prints ${block.rateText} for the one row listed under "${block.listedTitle}". That is what that listing is paid, a row being an incumbency; not what the post pays whoever holds it, and not what this unit costs.` +
        payDocumentsSentence(block);
      break;
    case "pay":
      note = ` What is shown instead is a rate of basic pay: OPM's PLUM archive reports ${block.reportedPayText} for this post` +
        `${block.edition ? ` (${block.edition})` : ""}. That is compensation for one post, not what this unit costs.`;
      break;
    case "tableRate": {
      const levelFromCurrent = block.levelSource && block.levelSource.source === "opm_plum_current_export";
      note = ` What is shown instead is OPM's ${block.table || "salary table"} rate for ${block.amountScope || "the level"} ${levelFromCurrent ? "the current PLUM export" : "OPM's PLUM archive"} lists this post at: two documents, a rank and a table, and neither says what this post pays whoever holds it now. Not what this unit costs.`;
      break;
    }
    case "range":
      note = block.kind === "general_schedule_grade"
        ? ` What is shown instead is the base General Schedule range for grade ${block.grade} in ${String(block.effective || "").slice(0, 4)}, before locality pay, from OPM's ${block.table}; not this unit's cost and not necessarily what the post pays now.`
        : ` What is shown instead is the range OPM's ${block.table} states for the pay system the listing files this post on; not this unit's cost and not necessarily what the post pays now.`;
      break;
    case "tier":
      note = ` What is shown instead is a Title 38 pay RANGE: the VA's ${block.table || "pay table"}${block.effectiveText ? ` (${lowerEffective(block.effectiveText)})` : ""} names "${block.coverageTitle || "this title"}" at Tier ${block.tier} and bounds an appointment between ${printed}. The schedule publishes no rate for anybody, and the range is not what this unit costs.`;
      break;
    case "fileA": {
      const alias = block.nameAlias && typeof block.nameAlias === "object" ? block.nameAlias : null;
      note = ` What is shown instead is a sourced figure of another kind: USAspending's File A reports gross outlays of ${printed} for "${block.apiName || block.toptierName || "this unit"}", ${blockFiscalYear(block.fiscalYear)} to date as of ${block.periodAsOf || "an unstated date"}.` +
        " Gross outlays are counted before the offsetting collections the Monthly Treasury Statement nets off, and they come from the agencies' DATA Act submissions rather than from the statement, so the figure is not this unit's net outlays and not its cost." +
        (alias ? ` USAspending names the unit "${alias.apiName || block.apiName}"; that the two names denote one unit is a recorded alias, so the figure is held to the weaker grade.` : "");
      break;
    }
    case "omb": {
      const listed = block.level === "bureau" && block.listedBureau
        ? `"${block.listedBureau}", which OMB files under "${block.listedAgency}"`
        : `"${block.listedAgency || "this unit"}"`;
      const rows = Number.isInteger(block.outlayAccountRows) ? `${block.outlayAccountRows.toLocaleString()} account rows` : "account rows";
      const precision = String(block.precisionNote || "").includes("detail below millions is not available")
        ? ` The file is in thousands of dollars and, in OMB's words, "detail below millions is not available".`
        : "";
      note = ` What is shown instead is a sourced figure of another kind: OMB's outlays for ${listed}, ${blockFiscalYear(block.fiscalYear)}, a year that has ended — ${printed}, the sum this project performed over the ${rows} OMB's Public Budget Database files under the unit; OMB prints no total for it.` +
        (block.outlays < 0
          ? ` The figure is below zero as the database gives it: "${String(block.netQuote || "").trim()}" A unit that collects more than it spends nets below zero.`
          : (block.netQuote ? ` "${String(block.netQuote).trim()}"` : "")) +
        (block.treasuryQuote ? ` OMB's guide: "${String(block.treasuryQuote).trim()}" — generally consistent, not the same, and for a completed year where this graph measures the current one to date.` : " It is for a completed year where this graph measures the current one to date.") +
        precision +
        " Not this unit's cost.";
      break;
    }
    case "audited": {
      const parts = typeof block.grossCostUsd === "number" && typeof block.earnedRevenueUsd === "number"
        ? ` (gross cost ${formatSignedWholeDollars(block.grossCostUsd)} less earned revenue ${formatSignedWholeDollars(block.earnedRevenueUsd)})`
        : "";
      note = ` What is shown instead is a sourced figure of another kind: Treasury's audited Statement of Net Cost reports a net cost of ${printed} for "${block.agencyName || "this unit"}", ${blockFiscalYear(block.fiscalYear)}${block.statementDate ? `, ended ${block.statementDate}` : ""}${parts}.` +
        (block.netCostUsd < 0 ? " A net cost below zero means the unit's earned revenue exceeded its gross cost for the year." : "") +
        (block.basisNote ? ` ${String(block.basisNote).trim()}` : " It is accrual accounting for a completed year, not outlays, and not this unit's cost.");
      break;
    }
    default:
      note = "";
  }
  // A figure kept on a node that stands for several posts is each holder's,
  // by the statute's or the roster's own words; the sweep that stamps
  // `holders` has already refused the incumbency-shaped claims, so what is
  // here is a rate for each, and never the group's total.
  const holders = block.holders && typeof block.holders === "object" ? block.holders : null;
  if (holders) {
    note += Number.isInteger(holders.count)
      ? ` The figure is for each of the ${holders.count} holders this node stands for, not the group's total.`
      : ` The figure is for each holder this node stands for (${String(holders.text || "several").trim()}), not the group's total.`;
  }
  return note;
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
    // beside it, in the order PAY_STAND_IN_ORDER sets.
    return standInAmountText(standIn);
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

// The sentence the pipeline generated for a header-sum node, with a leading
// space so it can follow another sentence, or "" where the node carries none.
// Only the stamp AND the sentence together count: a sentence without the
// stamp is nothing the gate accepted.
function headerSumSentence(node) {
  if (node.treasury_header_sum !== true) return "";
  const sentence = String(node.treasury_header_sum_note || "").trim();
  return sentence ? ` ${sentence}` : "";
}

// The sentence the pipeline generated for a printed line that is also one of
// another node's header-sum lines (COPS's, inside the Office of Justice
// Programs' sum): the money is measured, already inside that node's figure,
// and kept out of the parent's arithmetic. Stamp and sentence together, as
// for the header sum itself; "" otherwise.
function countedInHeaderSumSentence(node) {
  if (!String(node.treasury_counted_in_header_sum || "").trim()) return "";
  const sentence = String(node.treasury_counted_in_header_sum_note || "").trim();
  return sentence ? ` ${sentence}` : "";
}

// The lines the statement prints beneath a header-sum unit, by printed name
// and exact amount, in the statement's print order. Rendered only where the
// stamp is present; the receipts lines carry the same field and keep their
// description instead.
function buildHeaderSumLines(node) {
  if (node.treasury_header_sum !== true || !Array.isArray(node.treasury_component_rows) || !node.treasury_component_rows.length) {
    return null;
  }
  const list = document.createElement("ul");
  list.id = "info-cost-components";
  list.className = "info-cost-components";
  list.setAttribute("aria-label", "The lines the statement prints beneath this unit's header");
  list.style.listStyle = "none";
  list.style.margin = "4px 0 0";
  list.style.padding = "0 0 0 10px";
  list.style.borderLeft = "1px solid rgba(154,138,106,0.35)";
  list.style.fontSize = "9px";
  list.style.lineHeight = "1.6";
  list.style.color = "#9a8a6a";
  for (const component of node.treasury_component_rows) {
    const item = document.createElement("li");
    const amount = toFiniteAmount(component.amount);
    const exact = amount === null ? "amount not stated" : `${amount < 0 ? "-" : ""}$${Math.round(Math.abs(amount)).toLocaleString("en-US")}`;
    item.textContent = `${String(component.name || "unnamed line")} — ${exact}`;
    list.appendChild(item);
  }
  return list;
}

function describeCost(node) {
  const standIn = costStandInOf(node);
  const payNote = standIn ? standInNote(standIn) : "";
  const payLabel = standIn ? standInBadgeLabel(standIn) : null;
  // Only a node that actually holds an apportioned share is told the box
  // would reveal one. A post, or a unit beneath a negative Treasury pool,
  // has nothing to reveal, and "tick to see it" about a figure that does not
  // exist is a promise the data cannot keep.
  if (hasWithheldEstimate(node)) {
    return {
      label: payLabel || "No cost known for this node",
      // A sourced figure of another kind is drawn hollow and dashed, the
      // badge every unmeasured figure wears: never the filled measured one.
      tone: standIn && standIn.sourced ? "none" : "unavailable",
      note:
        "No record names this node's own cost. The figure this graph could otherwise show is its share of an ancestor's " +
        "measured total, divided among siblings by budget, headcount or subtree size — a number nobody measured, so it is " +
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
          "The unit above it publishes the Treasury's net figure, and the measured lines beneath that unit already reach or exceed it \u2014 its net outlays are negative, or a line this graph has no node for is. Nothing remains to apportion to its unmeasured parts, so no estimate is shown rather than a guess. There is no estimate for this node to reveal, whatever the estimates box says." +
          payNote,
      };
    }
    if (validation === "post_is_not_a_budget_unit" && employerOf(node)) {
      return {
        ...unavailable,
        label: "No cost known; not on a federal pay schedule",
        note:
          "This is a post, not a unit of government, so no budget figure is shown for it. No federal pay document prices it either, and the documents below say why: the laboratory it sits in is operated by a contractor.",
      };
    }
    if (validation === "post_is_not_a_budget_unit") {
      return {
        ...unavailable,
        note:
          "This is a post, not a unit of government. No federal financial system reports spending for an individual post, and a share of the organisation's budget above it would not be a cost this post incurred \u2014 so no figure is shown, and there is no estimate to reveal." +
          (payNote
            || " Where an official document states what the post is paid, that rate appears below instead, and a salary is not the same thing as a budget."),
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
  // A unit the statement prints lines beneath and totals nowhere. The figure
  // is the sum of those lines — the statement's own arithmetic, performed
  // here — and the sentence saying so is the pipeline's own, printed
  // verbatim, so the panel never calls it a line the Treasury prints. The
  // lines themselves are listed under the note by buildCostBlock.
  const headerSumNote = headerSumSentence(node);
  const countedNote = countedInHeaderSumSentence(node);
  if (status === "official" && amount < 0) {
    return {
      ...COST_STATUS_COPY.official,
      note: `Net outlays below zero for the period: the Monthly Treasury Statement (Table 5) reports more receipts than spending for this unit.${headerSumNote}${
        node.treasury_external_section ? ` The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.` : ""
      }${countedNote}`,
    };
  }
  if (status === "official" && node.treasury_external_section) {
    return {
      ...COST_STATUS_COPY.official,
      note: `${headerSumNote ? `U.S. Treasury outlays, from the Monthly Treasury Statement (Table 5).${headerSumNote}` : COST_STATUS_COPY.official.note} The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.${countedNote}`,
    };
  }
  if (status === "official" && countedNote) {
    return {
      ...COST_STATUS_COPY.official,
      note: `${COST_STATUS_COPY.official.note}${countedNote}`,
    };
  }
  if (status === "official" && headerSumNote) {
    return {
      ...COST_STATUS_COPY.official,
      note: `U.S. Treasury outlays, from the Monthly Treasury Statement (Table 5).${headerSumNote}`,
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
  // claim. The period line below is the Treasury anchor's and is replaced for
  // the same reason by a line naming the pay document, where there is one.
  const standIn = costStandInOf(node);
  const heading = standIn ? standInHeading(standIn) : null;
  // A post DOE's documents say a contractor's laboratory employs: no pay
  // document prices it and none ever will, so the headline says why rather
  // than "Not available", and the heading is PAY because that is the claim.
  const employer = standIn ? null : employerOf(node);
  const period = heading ? { label: heading.period, amountKind: null } : getCostPeriod(node);
  const label = document.createElement("span");
  label.className = "info-cost-label";
  label.textContent = heading ? heading.label : employer ? "PAY" : coversFullYear(period.amountKind) ? "ANNUAL COST" : "COST";
  head.appendChild(label);

  const amountText = formatCostAmount(node);
  const amount = document.createElement("span");
  amount.className = "info-cost-amount";
  amount.textContent = amountText === null ? (employer ? "Not on a federal pay schedule" : "Not available") : amountText;
  // A measured figure is printed exact — sixteen digits for the root — and
  // that stays the primary reading. Above a billion dollars a compact form is
  // set beneath it so the magnitude can be read at a glance: the same number
  // to three figures, never a different claim. Estimates are untouched; they
  // were always rounded and marked ≈.
  const exactAmount = toFiniteAmount(node.resolved_total_amount);
  if (amountText !== null && !standIn && isCostIdentifiedForTheNode(node) && exactAmount !== null && Math.abs(exactAmount) >= 1e9) {
    const compact = document.createElement("span");
    compact.className = "info-cost-compact";
    compact.textContent = `${formatApproximateCost(exactAmount)}, to three figures`;
    compact.title = "The same measured figure, rounded for reading; the exact figure above it is the claim.";
    amount.appendChild(compact);
  }
  // A sourced figure of another kind gets the same reading aid: its own
  // number, to three figures, never a different claim.
  const sourcedAmount = standIn && standIn.sourced ? toFiniteAmount(standIn.block[{ fileA: "amount", omb: "outlays", audited: "netCostUsd" }[standIn.kind]]) : null;
  if (sourcedAmount !== null && Math.abs(sourcedAmount) >= 1e9) {
    const compact = document.createElement("span");
    compact.className = "info-cost-compact";
    compact.textContent = `${formatApproximateCost(sourcedAmount)}, to three figures`;
    compact.title = "The same sourced figure, rounded for reading; the exact figure above it is what the source gives.";
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

  // "listed below" in the header-sum sentence means here: every line the
  // statement prints beneath the unit's header, by printed name and amount.
  const headerSumLines = buildHeaderSumLines(node);
  if (headerSumLines) block.appendChild(headerSumLines);
  if (employer && amountText === null) block.appendChild(buildEmployerLines(employer));

  // The estimate was always one tick away, and since 2026-10-05 the tick is
  // here too. The owner read "the costs have been disappearing" off a panel
  // whose figure sat behind a checkbox in the other column; the data had not
  // changed — 693 nodes carry an apportioned share and the default view has
  // withheld every one of them since 2026-09-09, by the owner's own decision
  // — so the control that reveals it now sits beside the sentence saying it
  // is withheld. It is the same checkbox: one click here turns the estimates
  // on for every node, and the box in the column reflects it.
  if (hasWithheldEstimate(node) && dom.toggleExactCosts) {
    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.className = "info-cost-reveal";
    reveal.textContent = "Show the estimate";
    reveal.title = "Turns on \u201cAlso show estimated shares of a parent's total\u201d for every node";
    reveal.addEventListener("click", () => {
      if (!dom.toggleExactCosts.checked) dom.toggleExactCosts.click();
    });
    block.appendChild(reveal);
  }

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
  renderCurrentListing(data);
  renderVacancyListing(data);
  renderStatutoryPay(data);
  renderDerivedPay(data);
  renderTierReferencePay(data);
  renderMilitaryPay(data);
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
  // What the chamber paid out for the committee's account, under its own
  // heading: the chamber's report and its period, never the word COST alone.
  const disbursedRow = data.committeeDisbursements;
  if (disbursedRow && typeof disbursedRow === "object" && typeof disbursedRow.amount === "number") {
    statRows.push([
      `DISBURSEMENTS — ${disbursementReportLabel(disbursedRow)}, ${disbursementPeriodLabel(disbursedRow)} (not the cost)`,
      `$${Math.round(disbursedRow.amount).toLocaleString()}`,
    ]);
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
  document.getElementById("view-switcher")?.classList.add("panel-open");
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
      // Only when the expansion was scoped to a node: a depth button expands
      // the whole tree and has no brood to frame.
      if (scopeObj) {
        state.graph.frameBroodOf(scopeObj);
      }
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
      // Pressing Expand is a request to SEE the children, so the camera is
      // allowed to pull back far enough to hold them -- which plain
      // selection is not. Without this the White House Office's 249
      // children were placed on a shell 374 units across and drawn as a fan
      // of edges leaving the frame on every side.
      state.graph.frameBroodOf(selected);
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
  // The renderer's drawn-node set, for the regression check that a still
  // camera draws a still picture. Read-only, and nothing in the page uses it.
  window.__bureaucracy_drawn_node_ids__ = () => state.graph?.getDrawnNodeIds?.() || [];
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
