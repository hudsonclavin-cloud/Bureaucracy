// The directory view: the same published graph the 3D universe draws, laid
// out as six generations of cards. It makes no claim the info panel in
// ui.js does not make, and it words each claim the same way — the evidence
// line, the description label, the placement line, the cost and the pay
// block are each ported from the panel rather than paraphrased, because a
// second view that hedges less is a second site that claims more.
const MAX_GENERATION = 6;

const atlas = document.getElementById("atlas");
const columns = document.getElementById("atlas-columns");
const detail = document.getElementById("atlas-detail");
const search = document.getElementById("atlas-search");
const results = document.getElementById("atlas-search-results");
const title = document.getElementById("atlas-path-title");
const coverage = document.getElementById("atlas-coverage");
const supersededToggle = document.getElementById("atlas-show-superseded");

const state = {
  root: null,
  nodes: new Map(),
  parents: new Map(),
  depths: new Map(),
  path: [],
  maxGeneration: MAX_GENERATION,
  // The default view is the government as it stands: a unit the government
  // has replaced is kept in the data with everything it earned, and hidden
  // here until the reader asks for it — the rule the 3D view follows.
  showSuperseded: false,
  budgetSummary: null,
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function isHttpUrl(value) {
  try {
    const parsed = new URL(String(value));
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch (_error) {
    return false;
  }
}

function hostnameOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (_error) {
    return String(url || "");
  }
}

function link(url, label) {
  if (!isHttpUrl(url)) return escapeHtml(label || url || "");
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label || hostnameOf(url))} ↗</a>`;
}

function isPost(node) {
  return /position/i.test(String(node?.type || ""));
}

function isReceiptsLine(node) {
  return String(node?.synthetic || "") === "treasury_receipts";
}

function isSuperseded(node) {
  return String(node?.lifecycle || "") === "superseded";
}

function isVisible(node) {
  return state.showSuperseded || !isSuperseded(node);
}

function visibleChildren(node) {
  return (node?.children || []).filter(isVisible);
}

function walk(node, parent = null, depth = 0) {
  if (!node || typeof node !== "object") return;
  state.nodes.set(node.id, node);
  state.depths.set(node.id, depth);
  if (parent) state.parents.set(node.id, parent.id);
  for (const child of node.children || []) walk(child, node, depth + 1);
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

// ---------------------------------------------------------------------------
// Existence evidence. The same distinctions the panel draws: checked and
// confirmed (by which method, on which page), checked and failed (against
// which page or list), a page that could not be read (and why: a fact about
// the host, never about the unit), and never checked at all. Only the last
// is "no source recorded".
// ---------------------------------------------------------------------------

const METHOD_TEXT = {
  name_labelled_on_own_official_page: "Its own official page names it",
  name_labelled_on_parent_official_page: "Its parent's official page lists it",
  name_labelled_on_its_organisations_official_page: "Its organisation's own official page names it",
  listed_in_federal_register_agency_directory: "The Federal Register's agency directory lists it",
  listed_in_us_government_manual: "The United States Government Manual carries an entry for it",
  listed_in_senate_committee_list: "The Senate's official committee list carries it",
  listed_in_house_clerk_committee_list: "The House Clerk's official committee list carries it",
  listed_in_its_organisations_us_government_manual_entry: "The United States Government Manual lists it in its organisation's entry",
  // The panel prints this one from the listing block rather than the method
  // map; the claim is the same, and it is the previous administration's
  // archive, which says nothing about who holds the post now.
  listed_in_opm_plum_archive: "OPM's PLUM archive, the previous administration's reported positions, lists a post of this title under its organisation",
  // A top-level Manual entry whose subject IS the office, rather than an
  // agency's entry listing one of its officers.
  listed_as_its_own_entry_in_us_government_manual: "The United States Government Manual carries an entry for the office itself",
  signed_a_federal_register_document: "An official signing a published Federal Register document stated this title",
};

const SOURCE_TEXT = {
  federal_register_agency_directory: "the Federal Register's agency directory",
  senate_committee_list: "the Senate's official committee list",
  house_clerk_committee_list: "the House Clerk's official committee list",
  us_government_manual: "the United States Government Manual",
};

function unreadText(unread) {
  const when = formatDate(unread.checkedAt);
  const on = when ? ` on ${when}` : "";
  const host = unread.host || hostnameOf(unread.url) || "its queued page";
  const UNREAD_TEXT = {
    host_refuses_crawler: `Not verified: ${host} refuses this crawler${on} (401/403 to the project's User-Agent), so the page queued for it could not be read — a fact about the host, not about the unit`,
    robots_unreachable: `Not verified: ${host}'s robots.txt could not be reached${on}; the crawl standard treats that as a complete disallow, so the page was not read`,
    page_not_found: `Not verified: the page queued for it (${host}) answered 404${on}; it has moved or gone, and no other page has been proposed`,
    page_below_readable_floor: `Not verified: the page queued for it (${host}) served under 400 characters of readable text${on} — a script shell — so nothing could be read`,
    site_failing: `Not verified: ${host} answered a server error${on}; refused until the site recovers`,
    network_error: `Not verified: ${host} could not be reached${on} (network error); the page was not read`,
    other: `Not verified: the page queued for it (${host}) could not be read${on}`,
  };
  return UNREAD_TEXT[String(unread.kind || "")] || UNREAD_TEXT.other;
}

// The panel's rule, not keyed on verificationStatus: that string is stamped
// "unverified" on every node the normaliser touches, so it is a default, not
// a finding. Zero sources and no timestamp means nothing was checked.
function isNeverChecked(node) {
  const sourceCount = Number(node.sourceCount || (Array.isArray(node.sourceUrls) ? node.sourceUrls.length : 0));
  return sourceCount === 0 && !node.lastVerified;
}

// Which of the node's URLs is the cost's, not the existence claim's. The
// FiscalData URL is stamped by the Treasury stage beside the measured cost;
// it says the statement names the unit's outlays, not that the unit exists
// as drawn, and the two rows below keep them apart.
function isCostSourceUrl(url) {
  return /fiscaldata\.treasury\.gov/i.test(String(url || ""));
}

function describeEvidence(node) {
  const checkedOn = formatDate(node.lastVerified);
  const failureSource = node.verificationFailureSource;
  const status = String(node.verificationStatus || "unverified").toLowerCase();
  if (node.verificationFailure === "not_in_official_list" && failureSource && typeof failureSource === "object") {
    return {
      status: "failed",
      short: "checked · not in the official list",
      text: `Checked${checkedOn ? ` ${checkedOn}` : ""} against ${SOURCE_TEXT[failureSource.source] || "an official list"}: it carries no unit of this name under "${failureSource.listedUnder}"`,
    };
  }
  if (node.verificationFailure === "not_found") {
    const failedOn = failureSource && typeof failureSource === "object" ? hostnameOf(failureSource.url) : "";
    const where = failedOn ? ` (${failedOn})` : "";
    return {
      status: "failed",
      short: "checked · page does not name it",
      text: checkedOn
        ? `Checked ${checkedOn}: its official page${where} does not name it as a heading or link`
        : `Its official page${where} does not name it as a heading or link`,
    };
  }
  const unread = node.verificationUnread;
  if (!node.verificationMethod && unread && typeof unread === "object") {
    return { status: "unread", short: "page could not be read", text: unreadText(unread) };
  }
  if (isNeverChecked(node)) {
    const headcount = node.employeesOfficial !== undefined && node.employeesOfficial !== null;
    return {
      status: "none",
      short: "no source recorded",
      text: headcount
        ? "No source recorded for its existence. This entry comes from the hand-compiled base graph; OPM's employment table names a unit of this name — evidence about its staffing, not about whether it exists as drawn."
        : "No source recorded. This entry comes from the hand-compiled base graph, and no source URL has been attached to it yet.",
    };
  }
  let text = "Not yet verified";
  const how = METHOD_TEXT[String(node.verificationMethod || "")];
  if (how) {
    const where = node.verificationMatchedIn === "navigation" ? " (in the site-wide navigation)" : "";
    const folded =
      node.verificationMatchRule === "committee_scaffolding_folded" && node.verificationMatchedText
        ? ` as "${node.verificationMatchedText}" (the graph's "Committee on" / "Subcommittee on" prefix set aside)`
        : "";
    const quoted =
      !folded && String(node.verificationMethod || "") === "name_labelled_on_its_organisations_official_page" && node.verificationMatchedText
        ? ` as "${node.verificationMatchedText}"`
        : "";
    text = `${how}${where}${folded}${quoted}${checkedOn ? ` · checked ${checkedOn}` : ""}`;
  } else if (checkedOn) {
    text = `Last checked: ${checkedOn}`;
  }
  const listing = node.directoryListing;
  const listingIsTheMethod = listing && typeof listing === "object" && /^listed_in_/.test(String(node.verificationMethod || ""));
  if (listing && typeof listing === "object" && !listingIsTheMethod) {
    text += ` · also listed in ${SOURCE_TEXT[listing.source] || "an official directory"} as "${listing.listedName}"${listing.parentListedName ? ` under "${listing.parentListedName}"` : ""}`;
  } else if (listing && typeof listing === "object") {
    text += ` as "${listing.listedName}"${listing.parentListedName ? ` under "${listing.parentListedName}"` : ""}`;
  }
  const govman = node.govmanListing;
  if (govman && typeof govman === "object") {
    const already = /government_manual/.test(String(node.verificationMethod || ""));
    const quoted = govman.listedTitle ? ` as "${govman.listedTitle}"` : "";
    const under = govman.listedUnder ? ` under "${govman.listedUnder}"` : "";
    text += already ? `${quoted}${under}` : ` · also listed in the United States Government Manual${quoted}${under}`;
    if (govman.edition) text += ` (${govman.edition} edition)`;
    if (govman.tableFooter) text += ` — the Manual says of that table: "${govman.tableFooter}"`;
  }
  const entry = node.govmanEntry;
  if (entry && typeof entry === "object") {
    const alreadyEntry = String(node.verificationMethod || "") === "listed_in_us_government_manual";
    const asName = entry.listedName ? ` as "${entry.listedName}"` : "";
    const filed = entry.parentListedName ? `, filed under "${entry.parentListedName}"` : ", as a top-level entry";
    const edition = entry.edition ? ` (${entry.edition} edition)` : "";
    text += alreadyEntry ? `${asName}${filed}${edition}` : ` · the United States Government Manual also carries an entry for it${asName}${filed}${edition}`;
  }
  // The Manual's top-level entry FOR an office (the President, the Vice
  // President): not an agency's entry listing an officer, and never a
  // placement. Same block as the panel's.
  const office = node.govmanOfficeEntry;
  if (office && typeof office === "object") {
    const alreadyOffice = String(node.verificationMethod || "") === "listed_as_its_own_entry_in_us_government_manual";
    const heading = office.listedName ? ` headed "${office.listedName}"` : "";
    const printedAs =
      office.matchedName && office.matchedName !== office.listedName
        ? `, which prints the office as "${office.matchedName}"`
        : "";
    const officeEdition = office.edition ? ` (${office.edition} edition)` : "";
    text += alreadyOffice
      ? `${heading}${printedAs}${officeEdition}`
      : ` · the United States Government Manual also carries a top-level entry for the office${heading}${printedAs}${officeEdition}`;
  }
  // A claim reached through the reviewed alternative-names table, said as
  // the weaker claim it is: both names quoted, the basis printed, and the
  // grading cap stated where nothing else names the unit. The same block as
  // the panel's.
  const aliasMatch = node.verificationAliasMatch;
  if (aliasMatch && typeof aliasMatch === "object" && aliasMatch.alias) {
    text +=
      aliasMatch.scope === "organisation"
        ? ` · the source files it under its organisation by a different recorded name, "${aliasMatch.alias}", which is not what this graph calls that unit`
        : ` · the source names it "${aliasMatch.alias}", not "${node.name || ""}", and that alternative is a reviewed entry in this project's own table`;
    if (aliasMatch.basis) text += ` — the reviewed basis for treating the two as one unit: ${aliasMatch.basis}`;
    if (aliasMatch.gradedAtMost === "partial") {
      text += " · nothing else names this unit, so the check is graded no higher than partial";
    }
  }
  // The same signature sentence the panel prints: the document, its date,
  // and that the office was filled when it was signed. The signer's name is
  // never read, so this can never be a statement about who holds it now.
  const signature = node.federalRegisterSignature;
  if (signature && typeof signature === "object") {
    const already = String(node.verificationMethod || "") === "signed_a_federal_register_document";
    const quoted = signature.listedTitle ? ` as "${signature.listedTitle}"` : "";
    const kind = String(signature.documentType || "document").toLowerCase();
    const signed = formatDate(signature.signingDate);
    const published = formatDate(signature.publicationDate);
    const when = signed ? `, signed ${signed}` : published ? `, published ${published}` : "";
    const doc = `${kind} ${signature.documentNumber}${when}`;
    text += already
      ? `${quoted} on ${doc}`
      : ` · an official signing Federal Register ${doc} stated this title${quoted}`;
    if (signature.occurrences > 1) text += ` (${signature.occurrences} of the documents read carry it)`;
    text += signed
      ? ` — the office was filled on that day`
      : ` — the office was filled when that document was signed, on or before the day it was published`;
    text += `; the signer's name is not read, and this says nothing about who holds it now`;
  }
  const readNotNamed = node.pageReadNotNamed;
  if (readNotNamed && typeof readNotNamed === "object" && readNotNamed.url) {
    const on = formatDate(readNotNamed.checkedAt);
    text += ` · its own page (${hostnameOf(readNotNamed.url)}) was read${on ? ` ${on}` : ""} and does not name it`;
  }
  const short = status === "verified" ? "verified" : status === "partial" ? "partial" : "unverified";
  return { status: short, short, text };
}

// ---------------------------------------------------------------------------
// Placement: evidence for the edge above the node, which is a different
// claim from the node existing. The tree path is shown as "Filed under" —
// what this graph says — and the placement line says what, if anything,
// supports it. Ported from the panel's renderPlacementLine.
// ---------------------------------------------------------------------------

function describePlacement(node) {
  const checked = formatDate(node.placementVerifiedAt);
  if (isReceiptsLine(node)) {
    return "A Treasury accounting line, placed beneath the unit whose published total it reconciles; not an organisation and not checked against any page";
  }
  const directoryName = (source) =>
    String(source || "") === "us_government_manual" ? "The United States Government Manual" : "The Federal Register's agency directory";
  const extras = [];
  const ancestorListing = node.placementDirectoryAncestor;
  if (ancestorListing && typeof ancestorListing === "object") {
    extras.push(`${directoryName(ancestorListing.source)} files it under "${ancestorListing.listedUnder}", an ancestor here; the grouping between is curated, and the directory says nothing about it`);
  }
  const disagreement = node.placementDirectoryDisagreement;
  if (disagreement && typeof disagreement === "object") {
    extras.push(`${directoryName(disagreement.source)} files it under "${disagreement.listedUnder}", not under its parent here — the two sources disagree, and neither is resolved`);
  }
  const directoryPlacement = {
    listed_under_parent_in_federal_register_agency_directory: "the Federal Register's agency directory files it under its parent here",
    listed_under_parent_in_us_government_manual: "the United States Government Manual files it under its parent here",
    listed_under_committee_in_senate_committee_list: "the Senate's official committee list carries it under its committee here",
    listed_under_committee_in_house_clerk_committee_list: "the House Clerk's official committee list carries it under its committee here",
    listed_under_organization_in_opm_plum_archive: "OPM's PLUM archive, the previous administration's reported positions, files a post of this title under its organisation here",
  }[String(node.placementMethod || "")];
  let main;
  if (node.placementVerified === true && directoryPlacement) {
    main = `${escapeHtml(directoryPlacement)}${node.placementMatchedText ? escapeHtml(`, as "${node.placementMatchedText}"`) : ""}${isHttpUrl(node.placementUrl) ? ` on ${link(node.placementUrl)}` : ""}${checked ? escapeHtml(` · list fetched ${checked}`) : ""}`;
  } else if (node.placementVerified === true) {
    const sameRead = Array.isArray(node.sourceUrls) && node.sourceUrls.includes(node.placementUrl) && node.lastVerified === node.placementVerifiedAt;
    const foldedNote = node.placementMatchRule === "committee_scaffolding_folded" ? ` (the graph's "Committee on" / "Subcommittee on" prefix set aside)` : "";
    const label = node.placementMatchedText ? ` as "${node.placementMatchedText}"${foldedNote}` : "";
    const where = node.placementMatchedIn === "navigation" ? " in its site-wide navigation" : "";
    main = `${escapeHtml(sameRead ? `The same page read for its existence lists it${where}${label}` : `Its parent's official page lists it${where}${label}`)} on ${isHttpUrl(node.placementUrl) ? link(node.placementUrl) : "an official page"}${checked ? escapeHtml(` · checked ${checked}`) : ""}`;
  } else if (node.placementVerified === false) {
    main = escapeHtml(`Its parent's official page was read${checked ? ` ${checked}` : ""} and does not list it as a heading or link — no claim either way`);
  } else if (isPost(node)) {
    main = escapeHtml("Not claimed separately — the page that names a post is its organisation's own, and that one reading is shown above as evidence the post exists, not a second time as evidence of where it sits");
  } else if (node.placementCheckable === false) {
    main = escapeHtml("Could not be checked — its parent is a curated grouping with no official page of its own");
  } else {
    main = escapeHtml("No evidence recorded for where this sits in the hierarchy");
  }
  return [main, ...extras.map(escapeHtml)].join("<br>");
}

// ---------------------------------------------------------------------------
// Descriptions. Every one of the base graph's descriptions reads as fact and
// carries no citation, so the label says what it is; the generated ones say
// which document they were generated from. Same strings as the panel.
// ---------------------------------------------------------------------------

const DESCRIPTION_SOURCE_TEXT = {
  generated_from_the_monthly_treasury_statement: "generated from the Monthly Treasury Statement, which names this unit — nothing further about it has been read",
  generated_from_its_official_page: "generated from the official page that names this unit — nothing further about it has been read",
  generated_from_treasury_lines: "generated from the Monthly Treasury Statement lines it names",
  generated_from_the_us_government_manual: "generated from the United States Government Manual, the government's own handbook, which names this unit and files it where the graph puts it — nothing further about it has been read",
  generated_from_whitehouse_staff_report: "generated from the White House Office's own annual report to Congress — the title and rate are the report's, the duties are not described",
};

function describeDescription(node) {
  if (!node.desc) return { text: "No description has been recorded for this entity.", label: "" };
  const label = DESCRIPTION_SOURCE_TEXT[String(node.descriptionSource || "")] || "uncited prose from the base graph — not checked against any source";
  return { text: String(node.desc), label: `Description: ${label}` };
}

// ---------------------------------------------------------------------------
// Cost. Measured means the Treasury names the node — cost_status official
// or root_total with the cost verified — and only that is printed as a
// figure. An apportioned share is never shown here: it is a number nobody
// measured, and the panel withholds it until asked. A post has no budget
// to divide and says so in the panel's words.
// ---------------------------------------------------------------------------

const ESTIMATE_WITHHELD_NOTE =
  "No record names this node's own cost. The figure this graph could otherwise show is its share of an ancestor's measured total, " +
  "divided among siblings by budget, headcount or subtree size — a number nobody measured, so it is not shown here. " +
  "The 3D universe can show it on request, labelled as the estimate it is.";

const POST_NOTE =
  "This is a post, not a unit of government. No federal financial system reports spending for an individual post, and a share of the " +
  "organisation's budget above it would not be a cost this post incurred — so no figure is shown. Where an official document states " +
  "what the post is paid, that rate appears below instead, and a salary is not the same thing as a budget.";

function toFiniteAmount(value) {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : null;
}

function formatExactMoney(amount) {
  const whole = Math.round(Math.abs(amount)).toLocaleString("en-US");
  return `${amount < 0 ? "−" : ""}$${whole}`;
}

function isMeasured(node) {
  const status = String(node.cost_status || "").toLowerCase();
  return (status === "official" || status === "root_total") && String(node.costVerificationStatus || "").toLowerCase() === "verified";
}

function costPeriodLabel(node) {
  const summary = state.budgetSummary;
  const asOf = node.budget_as_of;
  return String(summary?.label || "").trim() || (asOf ? `As of ${String(asOf).trim()}` : "");
}

function describeCost(node) {
  const status = String(node.cost_status || "").toLowerCase();
  const validation = String(node.cost_validation || "").toLowerCase();
  const amount = toFiniteAmount(node.resolved_total_amount);
  if (isMeasured(node) && amount !== null) {
    const sourceUrl = (node.sourceUrls || []).find(isCostSourceUrl) || (status === "root_total" ? state.budgetSummary?.source_url : null);
    let label = "Measured";
    let note = status === "root_total"
      ? "U.S. Treasury outlays, from the Monthly Treasury Statement."
      : "U.S. Treasury outlays reported for this unit in the Monthly Treasury Statement (Table 5).";
    if (isReceiptsLine(node)) {
      label = "Measured (Treasury accounting line)";
      note = "Not an organisation. The receipts and transfers the Treasury nets inside the published total above, carried here as the statement prints them so the units above sum to that figure to the cent.";
    } else if (amount < 0) {
      note = `Net outlays below zero for the period: the Monthly Treasury Statement (Table 5) reports more receipts than spending for this unit.${
        node.treasury_external_section ? ` The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.` : ""
      }`;
    } else if (node.treasury_external_section) {
      note += ` The Treasury files this line under its "${node.treasury_section}" section, so it is measured but not part of its parent's total here.`;
    }
    return { amount: formatExactMoney(amount), label, note, period: costPeriodLabel(node), sourceUrl };
  }
  if (validation === "post_is_not_a_budget_unit") {
    return { amount: null, label: "Not available", note: POST_NOTE, period: "", sourceUrl: null };
  }
  if (status === "allocated") {
    return { amount: null, label: "Estimate withheld", note: ESTIMATE_WITHHELD_NOTE, period: "", sourceUrl: null };
  }
  if (validation === "allocation_below_precision") {
    return { amount: null, label: "Not available", note: "Its share of the estimate above it rounds to less than one cent (or an ancestor's did), so no figure is shown rather than $0.", period: "", sourceUrl: null };
  }
  if (validation === "treasury_pool_negative") {
    return {
      amount: null,
      label: "Not available",
      note: "The unit above it publishes the Treasury's net figure, and the measured lines beneath that unit already reach or exceed it — its net outlays are negative, or a line this graph has no node for is. Nothing remains to apportion to its unmeasured parts, so no figure is shown rather than a guess.",
      period: "",
      sourceUrl: null,
    };
  }
  if (status === "scaled_official") {
    // The figure is the parent's cap, not the Treasury's, so it is an
    // estimate and is withheld with the others.
    return { amount: null, label: "Estimate withheld (Treasury line capped)", note: `The Treasury reported more than fits within the parent's estimated share. ${ESTIMATE_WITHHELD_NOTE}`, period: "", sourceUrl: null };
  }
  return { amount: null, label: "Not available", note: "No cost figure could be traced to a source.", period: "", sourceUrl: null };
}

// ---------------------------------------------------------------------------
// Pay. A rate of basic pay an official document states for a post — under
// its own heading, never under COST: it excludes benefits and is not a share
// of federal outlays, which is what every other figure in this graph means.
// Each block is the panel's, shortened to its claim and its caveat.
// ---------------------------------------------------------------------------

function describePay(node) {
  const blocks = [];
  const listing = node.positionListing;
  if (listing && typeof listing === "object" && typeof listing.reportedPay === "number" && listing.reportedPay > 0) {
    blocks.push({
      heading: "Reported rate of basic pay",
      text: `OPM's PLUM archive${listing.edition ? ` (${listing.edition})` : ""} reports basic pay of ${listing.reportedPayText || `$${listing.reportedPay.toLocaleString("en-US")}`} for this post — not this unit's cost, not necessarily what the post pays now, and a record of that period that says nothing about who holds it now.`,
    });
  }
  // The current Plum Book's own printed rate: the panel's sentence, and
  // the same caveat — a row is an incumbency, so this is one listing's
  // figure, headed as pay and never as cost.
  const current = node.positionCurrentPay;
  if (current && typeof current === "object" && typeof current.amount === "number" && current.amount > 0) {
    const printed = current.rateText || `$${current.amount.toLocaleString("en-US")}`;
    const on = formatDate(current.exportFetchedAt);
    blocks.push({
      heading: "Pay — current Plum Book",
      text: `OPM's current PLUM Reporting export${on ? ` (fetched ${on})` : ""} prints ${printed} for the one row listed under "${current.listedTitle || "this title"}". That is what that listing is paid, a row being an incumbency; not what the post pays whoever holds it, and not this unit's cost.${payDocuments(current)}`,
    });
  }
  const rate = node.positionPayRate;
  if (rate && typeof rate === "object" && typeof rate.amount === "number") {
    const printed = rate.rateText || `$${rate.amount.toLocaleString("en-US")}`;
    const when = rate.effectiveText ? `, ${String(rate.effectiveText).replace(/^Effective\b/, "effective")}` : "";
    const levelFromCurrent = rate.levelSource && rate.levelSource.source === "opm_plum_current_export";
    blocks.push({
      heading: levelFromCurrent ? "Rate for the current export's level" : "Rate for the archive's level",
      text: levelFromCurrent
        ? `OPM's ${rate.table}${when}, pays ${printed} for ${rate.amountScope}. That is two documents, not one — the level is the current PLUM export's listing of this post, and the rate is a table's figure for that rank; the export prints no rate for this row, so this is not a figure for the post.`
        : `OPM's ${rate.table}${when}, pays ${printed} for ${rate.amountScope}. That is two documents, not one — the level is the archive's record of a period that ended, and the rate is from a table that took effect afterwards, so neither says what this post pays whoever holds it now.`,
    });
    blocks[blocks.length - 1].text += payDocuments(rate);
  }
  const schedule = node.positionSchedulePay;
  if (schedule && typeof schedule === "object" && typeof schedule.amount === "number") {
    const printed = schedule.rateText || `$${schedule.amount.toLocaleString("en-US")}`;
    const when = schedule.effectiveText ? `, ${String(schedule.effectiveText).replace(/^Effective\b/, "effective")}` : "";
    blocks.push({
      heading: "Executive Schedule rate",
      text: `${schedule.citation || "The United States Code"} places this post at Executive Schedule level ${schedule.payLevel}, naming it "${schedule.statutoryTitle}". OPM's ${schedule.table}${when}, pays ${printed} for ${schedule.amountScope}.${
        schedule.scopedOffice && schedule.scopedOrganisation ? ` Matched to "${schedule.scopedOffice}" as the post of that name directly under ${schedule.scopedOrganisation}.` : ""
      } A statutory rate of basic pay, not what the holder receives.${payDocuments(schedule)}`,
    });
  }
  const statutory = node.positionStatutoryPay;
  if (statutory && typeof statutory === "object" && typeof statutory.amount === "number") {
    const printed = statutory.rateText || `$${statutory.amount.toLocaleString("en-US")}`;
    const on = formatDate(statutory.checkedAt);
    blocks.push({
      heading: "Statutory pay",
      text: `${statutory.sourceLabel || "A primary official source"}${on ? ` (checked ${on})` : ""} states that ${statutory.amountScope || "this tier"} is paid ${printed}${statutory.year ? ` for ${statutory.year}` : ""}. That names a tier or a group of roles, not this specific post by name.${payDocuments(statutory)}`,
    });
  }
  const derived = node.positionDerivedPay;
  if (derived && typeof derived === "object" && typeof derived.amount === "number") {
    const printed = derived.rateText || `$${derived.amount.toLocaleString("en-US")}`;
    const verification = (derived.verification && typeof derived.verification === "object") ? derived.verification : {};
    const documents = Array.isArray(derived.documents) ? derived.documents : [];
    const count = Number(verification.documents || documents.length || 0);
    const stating = Number(verification.documentsStatingTheFigure || 0);
    blocks.push({
      heading: "Derived pay — no single document states it",
      text: `${derived.statute || "A statutory parity provision"} states that every judge of ${derived.court || "this court"} is paid at the rate of ${derived.amountScope || "another court's judges"}; the U.S. Courts' Judicial Compensation table states that tier pays ${printed}${derived.year ? ` for ${derived.year}` : ""}. ${count} official document${count === 1 ? "" : "s"} verify it — ${Number(verification.percent || 0)}% on this project's own source scale — and ${stating === 0 ? "neither states the figure" : `${stating} state${stating === 1 ? "s" : ""} the figure`}. The percentage measures how much official documentation the claim rests on, not the chance that it is right.`,
    });
  }
  const reported = node.positionReportedPay;
  if (reported && typeof reported === "object" && typeof reported.amount === "number") {
    const printed = reported.rateText || `$${reported.amount.toLocaleString("en-US")}`;
    const on = formatDate(reported.checkedAt);
    blocks.push({
      heading: "Reported pay",
      text: `${reported.sourceLabel || "The White House Office's own annual report to Congress"}${on ? ` (checked ${on})` : ""} lists one person under "${reported.reportedTitle || "this title"}"${reported.asOf ? `, as of ${reported.asOf}` : ""}, paid ${printed}${reported.payBasis ? ` ${String(reported.payBasis).toLowerCase()}` : ""}. That is what the one person listed is paid, not what the post pays whoever holds it.${payDocuments(reported)}`,
    });
  }
  return blocks;
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

// The document count and what it is worth, appended to every pay block here
// as `ui.js` appends it to every pay block in the panel. One sentence, the
// same scale, so a reader comparing two rows in this view is comparing the
// same thing.
function payDocuments(block) {
  const verification = block && typeof block === "object" ? block.verification : null;
  if (!verification || typeof verification !== "object") return "";
  const count = Number(verification.documents || 0);
  if (!count) return "";
  const stating = Number(verification.documentsStatingTheFigure || 0);
  return ` ${count} official document${count === 1 ? "" : "s"} verify this — ${Number(verification.percent || 0)}% on this project's own source scale — and ${stating === 0 ? "none of them states the figure itself" : stating === count ? (count === 1 ? "it states the figure itself" : "all of them state the figure itself") : `${stating} of them states the figure itself`}.`;
}

function card(node, selectedId) {
  const evidence = describeEvidence(node);
  const childCount = visibleChildren(node).length;
  const replaced = isSuperseded(node) ? ` <span class="replaced-tag">replaced</span>` : "";
  return `<button class="entity-card${selectedId === node.id ? " selected" : ""}${isSuperseded(node) ? " superseded" : ""}" data-node-id="${escapeHtml(node.id)}">
    <strong>${escapeHtml(node.name)}</strong>
    <small><span class="evidence-dot ${evidence.status}"></span>${escapeHtml(node.type || "Entity")} · ${escapeHtml(evidence.short)}${replaced}</small>
    ${childCount ? `<span class="child-count" aria-label="${childCount} children">${childCount} →</span>` : ""}
  </button>`;
}

function renderColumns() {
  if (!state.root) return;
  const selectedPath = state.path.length ? state.path : [state.root];
  const generations = [];
  const rootSelection = selectedPath[1]?.id || null;
  generations.push({ label: "Generation 1", parent: state.root, nodes: visibleChildren(state.root), selectedId: rootSelection });

  for (let index = 1; index < selectedPath.length && generations.length < state.maxGeneration; index += 1) {
    const parent = selectedPath[index];
    const children = visibleChildren(parent);
    if (!children.length) break;
    generations.push({
      label: `Generation ${index + 1}`,
      parent,
      nodes: children,
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

function supersededNotice(node) {
  if (!isSuperseded(node)) return "";
  const source = node.supersededSource && typeof node.supersededSource === "object" ? node.supersededSource : {};
  const replacements = Array.isArray(node.supersededBy) ? node.supersededBy : [];
  const by = replacements.length
    ? ` Its work is carried by ${replacements.length} unit${replacements.length === 1 ? "" : "s"} now in the graph.`
    : " No successor unit is recorded.";
  const quote = String(source.quote || "");
  return `<p class="detail-superseded">${escapeHtml(
    `REPLACED — the government no longer has this unit as drawn (as of ${String(node.supersededOn || "an unstated date")}).${by}${quote ? ` ${hostnameOf(source.url)} says: "${quote}"` : ""} It is kept, with its sources, as a record of what the government used to be.`,
  )}</p>`;
}

function renderDetail(node) {
  if (!node) return;
  const route = pathTo(node);
  const evidence = describeEvidence(node);
  const description = describeDescription(node);
  const cost = describeCost(node);
  const pay = describePay(node);
  const existenceSources = (node.sourceUrls || []).filter((url) => isHttpUrl(url) && !isCostSourceUrl(url));
  const hiddenChildren = (node.children || []).length - visibleChildren(node).length;
  const childrenText = `${visibleChildren(node).length.toLocaleString("en-US")} recorded${hiddenChildren ? ` (${hiddenChildren.toLocaleString("en-US")} replaced, hidden)` : ""}`;
  const row = (term, body, className = "") => `<div class="detail-row${className ? ` ${className}` : ""}"><dt>${escapeHtml(term)}</dt><dd>${body}</dd></div>`;
  const costBody = `${cost.amount ? `<strong class="detail-amount">${escapeHtml(cost.amount)}</strong> · ${escapeHtml(cost.label)}${cost.period ? ` · ${escapeHtml(cost.period)}` : ""}` : escapeHtml(cost.label)}<span class="detail-note">${escapeHtml(cost.note)}</span>`;
  const rows = [
    row("Evidence", `<span class="evidence-dot ${evidence.status}"></span>${escapeHtml(evidence.text)}`, `evidence-${evidence.status}`),
    row("Sources", existenceSources.length ? existenceSources.map((url) => link(url)).join(" · ") : "No confirming sources recorded."),
    row("Filed under", escapeHtml(route.slice(0, -1).map((item) => item.name).join(" → ") || "Root")),
    row("Placement", describePlacement(node)),
    row("Children", childrenText),
    row("Cost", costBody, "cost-row"),
  ];
  if (cost.sourceUrl) rows.push(row("Cost source", `${link(cost.sourceUrl, "Monthly Treasury Statement, Table 5 (fiscaldata.treasury.gov)")}<span class="detail-note">Evidence of the cost, not of the unit's existence.</span>`));
  if (pay.length) {
    rows.push(row("Pay", `${pay.map((block) => `<span class="detail-pay"><em>${escapeHtml(block.heading)}:</em> ${escapeHtml(block.text)}</span>`).join("")}<span class="detail-note">A rate of basic pay is not this unit's cost: it excludes benefits and is not a share of federal outlays, which is what every other figure in this graph means.</span>`, "pay-row"));
  }
  detail.innerHTML = `<div>
      <div class="detail-type">${escapeHtml(node.type || "Federal entity")}${isSuperseded(node) ? " · replaced" : ""}</div>
      <h2 class="detail-title">${escapeHtml(node.name)}</h2>
      ${supersededNotice(node)}
      <p class="detail-desc">${escapeHtml(description.text)}</p>
      ${description.label ? `<p class="detail-desc-label">${escapeHtml(description.label)}</p>` : ""}
    </div>
    <dl class="detail-meta">${rows.join("")}</dl>`;
  detail.classList.add("open");
}

function selectNode(node) {
  if (!node) return;
  state.path = pathTo(node).slice(0, state.maxGeneration + 1);
  renderColumns();
  renderDetail(node);
  results.innerHTML = "";
}

// The same definitions the 3D view's summariseGraph uses, and no others:
// measured is cost_status official/root_total (the receipts lines counted
// with them, as the provenance line counts them), sourced is a non-empty
// sourceUrls, allocated is cost_status allocated. The smoke check recomputes
// each from the served graph and holds this strip to it.
function summariseDirectory(root) {
  const count = { nodes: 0, measured: 0, receipts: 0, sourced: 0, allocated: 0, noFigure: 0, posts: 0 };
  const stack = [root];
  while (stack.length) {
    const node = stack.pop();
    if (!node || typeof node !== "object") continue;
    count.nodes += 1;
    const status = String(node.cost_status || "");
    if (isReceiptsLine(node)) count.receipts += 1;
    else if (status === "official" || status === "root_total") count.measured += 1;
    if (status === "allocated") count.allocated += 1;
    if (status === "unavailable" || (!status && node !== root)) count.noFigure += 1;
    if (Array.isArray(node.sourceUrls) && node.sourceUrls.length) count.sourced += 1;
    if (isPost(node)) count.posts += 1;
    for (const child of node.children || []) stack.push(child);
  }
  return count;
}

function renderCoverage() {
  const count = summariseDirectory(state.root);
  coverage.innerHTML = [
    [count.nodes, "published nodes"],
    [count.measured + count.receipts, "costs measured from the Monthly Treasury Statement"],
    [count.sourced, `of ${count.nodes.toLocaleString("en-US")} nodes carry a source`],
    [count.allocated, "apportioned estimates, withheld"],
  ].map(([value, label]) => `<div class="coverage-stat"><strong>${Number(value).toLocaleString("en-US")}</strong><span>${escapeHtml(label)}</span></div>`).join("");
}

function searchNodes(query) {
  const normalized = query.trim().toLowerCase();
  if (normalized.length < 2) return [];
  return [...state.nodes.values()]
    .filter((node) => (state.depths.get(node.id) || 0) <= MAX_GENERATION && isVisible(node))
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
    return `<button class="atlas-result" role="option" data-result-id="${escapeHtml(node.id)}"><span><strong>${escapeHtml(node.name)}</strong><small>${escapeHtml(route || "Federal government")}</small></span><small>${escapeHtml(node.type || "Entity")}${isSuperseded(node) ? " · replaced" : ""}</small></button>`;
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

supersededToggle?.addEventListener("change", () => {
  state.showSuperseded = Boolean(supersededToggle.checked);
  // A selection inside a subtree that is now hidden would leave the columns
  // showing a path the reader cannot reach; fall back to the last visible
  // ancestor.
  while (state.path.length > 1 && !isVisible(state.path[state.path.length - 1])) state.path.pop();
  renderColumns();
  const selected = state.path[state.path.length - 1];
  if (selected && selected !== state.root && detail.classList.contains("open")) renderDetail(selected);
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
  // The pruned viewer copy only: it carries no review-queue candidates, so
  // nothing here ever has to hide or label one.
  const source = window.GRAPH_DATA_SOURCES?.primary || "./output/graph.min.json";
  const response = await fetch(source);
  if (!response.ok) throw new Error(`Directory data failed with ${response.status}`);
  state.root = await response.json();
  state.budgetSummary = state.root && typeof state.root.__budgetSummary === "object" ? state.root.__budgetSummary : null;
  walk(state.root);
  state.path = [state.root];
  renderCoverage();
  renderColumns();
  window.__atlas_loaded__ = true;
}

initAtlas().catch((error) => {
  console.error(error);
  if (columns) columns.innerHTML = '<p class="atlas-error">The directory could not be loaded. Switch to the 3D universe or reload the page.</p>';
});
