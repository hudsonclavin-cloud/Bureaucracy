const DEFAULT_NODE = {
  id: "",
  name: "Unnamed Node",
  type: "Unknown",
  desc: "",
  employees: null,
  budget: null,
  color: "#666666",
  sourceUrls: [],
  sourceTypes: [],
  confidenceScore: 0,
  verificationStatus: "unverified",
  lastVerified: null,
  sourceCount: 0,
  budget_as_of: null,
  source_system: null,
  amount_kind: null,
  allocation_basis: null,
  direct_outlay_amount: null,
  rollup_total_amount: null,
  resolved_total_amount: null,
  cost_status: null,
  cost_basis: null,
  cost_validation: null,
  isCandidate: false,
  possibleParent: null,
  discoveryMethod: null,
  children: [],
};

const MAX_DEPTH = 20;

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}

function normalizeNode(rawNode) {
  const node = {
    ...DEFAULT_NODE,
    ...rawNode,
  };
  node.id = String(node.id || "");
  node.name = String(node.name || DEFAULT_NODE.name);
  node.type = String(node.type || DEFAULT_NODE.type);
  node.desc = typeof node.desc === "string" ? node.desc : "";
  node.employees = node.employees ?? null;
  node.budget = node.budget ?? null;
  node.color = typeof node.color === "string" ? node.color : DEFAULT_NODE.color;
  node.sourceUrls = Array.isArray(node.sourceUrls) ? node.sourceUrls.map((value) => String(value)) : [];
  node.sourceTypes = Array.isArray(node.sourceTypes) ? node.sourceTypes.map((value) => String(value)) : [];
  node.confidenceScore = Number.isFinite(Number(node.confidenceScore)) ? Number(node.confidenceScore) : 0;
  node.verificationStatus = String(node.verificationStatus || DEFAULT_NODE.verificationStatus);
  node.lastVerified = node.lastVerified ? String(node.lastVerified) : null;
  node.sourceCount = Number.isFinite(Number(node.sourceCount)) ? Number(node.sourceCount) : node.sourceUrls.length;
  node.budget_as_of = node.budget_as_of ? String(node.budget_as_of) : null;
  node.source_system = node.source_system ? String(node.source_system) : null;
  node.amount_kind = node.amount_kind ? String(node.amount_kind) : null;
  node.allocation_basis = node.allocation_basis ? String(node.allocation_basis) : null;
  node.direct_outlay_amount = Number.isFinite(Number(node.direct_outlay_amount)) ? Number(node.direct_outlay_amount) : null;
  node.rollup_total_amount = Number.isFinite(Number(node.rollup_total_amount)) ? Number(node.rollup_total_amount) : null;
  node.resolved_total_amount = Number.isFinite(Number(node.resolved_total_amount)) ? Number(node.resolved_total_amount) : null;
  node.cost_status = node.cost_status ? String(node.cost_status) : null;
  node.cost_basis = node.cost_basis ? String(node.cost_basis) : null;
  node.cost_validation = node.cost_validation ? String(node.cost_validation) : null;
  node.isCandidate = Boolean(node.isCandidate);
  node.possibleParent = node.possibleParent ? String(node.possibleParent) : null;
  node.discoveryMethod = node.discoveryMethod ? String(node.discoveryMethod) : null;
  node.children = Array.isArray(node.children) ? node.children.map(normalizeNode) : [];
  return node;
}

function walkTree(node, visit, parent = null) {
  visit(node, parent);
  for (const child of node.children) {
    walkTree(child, visit, node);
  }
}

function trimDepth(node, depth = 0) {
  if (depth >= MAX_DEPTH) {
    node.children = [];
    return;
  }
  for (const child of node.children) {
    trimDepth(child, depth + 1);
  }
}

function buildNodeIndex(rootNode) {
  const nodeMap = new Map();
  const parentMap = new Map();
  walkTree(rootNode, (node, parent) => {
    nodeMap.set(node.id, node);
    if (parent) {
      parentMap.set(node.id, parent.id);
    }
  });
  return { nodeMap, parentMap };
}

function safeAddChild(parentNode, childNode, parentMap) {
  if (!parentNode || !childNode || parentNode.id === childNode.id) {
    return false;
  }
  const existingParentId = parentMap.get(childNode.id);
  if (existingParentId && existingParentId !== parentNode.id) {
    return false;
  }
  if (parentNode.children.some((child) => child.id === childNode.id)) {
    return false;
  }

  let cursorId = parentNode.id;
  while (cursorId) {
    if (cursorId === childNode.id) {
      return false;
    }
    cursorId = parentMap.get(cursorId) || null;
  }

  parentNode.children.push(childNode);
  parentMap.set(childNode.id, parentNode.id);
  return true;
}

function mergeNodeData(targetNode, sourceNode) {
  const statusRank = { unverified: 0, partial: 1, verified: 2 };
  targetNode.name = sourceNode.name || targetNode.name;
  targetNode.type = sourceNode.type || targetNode.type;
  targetNode.desc = sourceNode.desc || targetNode.desc;
  targetNode.employees = sourceNode.employees ?? targetNode.employees;
  targetNode.budget = sourceNode.budget ?? targetNode.budget;
  targetNode.annual_budget = sourceNode.annual_budget ?? targetNode.annual_budget;
  targetNode.budget_source = sourceNode.budget_source || targetNode.budget_source;
  targetNode.budget_year = sourceNode.budget_year || targetNode.budget_year;
  targetNode.budget_as_of = sourceNode.budget_as_of || targetNode.budget_as_of;
  targetNode.source_system = sourceNode.source_system || targetNode.source_system;
  targetNode.amount_kind = sourceNode.amount_kind || targetNode.amount_kind;
  targetNode.allocation_basis = sourceNode.allocation_basis || targetNode.allocation_basis;
  targetNode.direct_outlay_amount = sourceNode.direct_outlay_amount ?? targetNode.direct_outlay_amount;
  targetNode.rollup_total_amount = sourceNode.rollup_total_amount ?? targetNode.rollup_total_amount;
  targetNode.resolved_total_amount = sourceNode.resolved_total_amount ?? targetNode.resolved_total_amount;
  targetNode.cost_status = sourceNode.cost_status || targetNode.cost_status;
  targetNode.cost_basis = sourceNode.cost_basis || targetNode.cost_basis;
  targetNode.cost_validation = sourceNode.cost_validation || targetNode.cost_validation;
  targetNode.official_website = sourceNode.official_website || targetNode.official_website;
  targetNode.color = sourceNode.color || targetNode.color;
  targetNode.sourceUrls = Array.from(new Set([...(targetNode.sourceUrls || []), ...(sourceNode.sourceUrls || [])]));
  targetNode.sourceTypes = Array.from(new Set([...(targetNode.sourceTypes || []), ...(sourceNode.sourceTypes || [])]));
  targetNode.sourceCount = Math.max(targetNode.sourceCount || 0, sourceNode.sourceCount || 0, targetNode.sourceUrls.length);
  targetNode.confidenceScore = Math.max(targetNode.confidenceScore || 0, sourceNode.confidenceScore || 0);
  targetNode.verificationStatus =
    statusRank[sourceNode.verificationStatus] >= statusRank[targetNode.verificationStatus]
      ? sourceNode.verificationStatus
      : targetNode.verificationStatus;
  targetNode.lastVerified = sourceNode.lastVerified || targetNode.lastVerified;
  targetNode.isCandidate = Boolean(targetNode.isCandidate || sourceNode.isCandidate);
  targetNode.possibleParent = targetNode.possibleParent || sourceNode.possibleParent || null;
  targetNode.discoveryMethod = targetNode.discoveryMethod || sourceNode.discoveryMethod || null;
}

function normalizeCandidateNode(rawCandidate) {
  const name = String(rawCandidate?.name || "Unnamed Candidate");
  const sourceUrls = Array.isArray(rawCandidate?.sourceUrls)
    ? rawCandidate.sourceUrls.map((value) => String(value))
    : rawCandidate?.sourceUrl
      ? [String(rawCandidate.sourceUrl)]
      : [];
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return normalizeNode({
    id: String(rawCandidate?.id || `candidate-${slug || "node"}`),
    name,
    type: String(rawCandidate?.type || "Candidate"),
    desc: String(rawCandidate?.desc || `Candidate node discovered via ${rawCandidate?.discoveryMethod || "automated discovery"}.`),
    budget: rawCandidate?.budget ?? null,
    color: typeof rawCandidate?.color === "string" ? rawCandidate.color : "#9b8bbd",
    sourceUrls,
    sourceTypes: Array.isArray(rawCandidate?.sourceTypes)
      ? rawCandidate.sourceTypes
      : ["candidate_discovery"],
    confidenceScore: Number((rawCandidate?.confidenceScore ?? rawCandidate?.confidenceEstimate) || 0),
    verificationStatus: String(rawCandidate?.verificationStatus || "unverified"),
    lastVerified: rawCandidate?.lastVerified ? String(rawCandidate.lastVerified) : null,
    sourceCount: Number(rawCandidate?.sourceCount || sourceUrls.length),
    isCandidate: true,
    possibleParent: rawCandidate?.possibleParent || null,
    discoveryMethod: rawCandidate?.discoveryMethod || null,
  });
}

function extractExplicitParentId(rawNode) {
  return rawNode.parentId || rawNode.parent || rawNode.attachTo || rawNode.attachToId || rawNode.source || null;
}

function shouldAttachToRoot(rawNode) {
  return Boolean(rawNode && rawNode.attachToRoot);
}

function extractExpansionNodes(expansionData) {
  if (!expansionData) {
    return [];
  }
  if (Array.isArray(expansionData)) {
    return expansionData;
  }
  if (Array.isArray(expansionData.nodes)) {
    return expansionData.nodes;
  }
  if (Array.isArray(expansionData.children)) {
    return expansionData.children;
  }
  if (expansionData.root && typeof expansionData.root === "object") {
    return [expansionData.root];
  }
  if (expansionData.data && typeof expansionData.data === "object") {
    return [expansionData.data];
  }
  if (typeof expansionData === "object" && expansionData.id) {
    return [expansionData];
  }
  return [];
}

function extractExpansionEdges(expansionData) {
  if (!expansionData) {
    return [];
  }
  if (Array.isArray(expansionData)) {
    return expansionData;
  }
  return Array.isArray(expansionData.edges) ? expansionData.edges : [];
}

function flattenExpansionNodes(rawNodes, flatNodes, treeRoots) {
  for (const rawNode of rawNodes) {
    if (!rawNode || typeof rawNode !== "object") {
      continue;
    }

    const normalizedNode = normalizeNode(rawNode);
    flatNodes.set(normalizedNode.id, normalizedNode);

    if (Array.isArray(rawNode.children) && rawNode.children.length > 0) {
      treeRoots.push(normalizedNode);
    }

    for (const child of rawNode.children || []) {
      flattenExpansionNodes([child], flatNodes, treeRoots);
    }
  }
}

function mergeExpansionTree(baseNodeMap, parentMap, expansionRoot) {
  const stack = [{ source: expansionRoot, parentId: null }];
  while (stack.length > 0) {
    const { source, parentId } = stack.pop();
    const existingNode = baseNodeMap.get(source.id);
    const targetNode = existingNode || normalizeNode({ ...source, children: [] });

    if (existingNode) {
      mergeNodeData(existingNode, source);
    } else {
      baseNodeMap.set(targetNode.id, targetNode);
    }

    if (parentId) {
      const parentNode = baseNodeMap.get(parentId);
      safeAddChild(parentNode, targetNode, parentMap);
    }

    for (const child of source.children || []) {
      stack.push({ source: child, parentId: targetNode.id });
    }
  }
}

function mergeExpansionGraph(baseRoot, expansionData) {
  const { nodeMap: baseNodeMap, parentMap } = buildNodeIndex(baseRoot);
  const rawNodes = extractExpansionNodes(expansionData);
  const rawEdges = extractExpansionEdges(expansionData);
  const flatNodes = new Map();
  const treeRoots = [];

  flattenExpansionNodes(rawNodes, flatNodes, treeRoots);

  for (const [nodeId, node] of flatNodes) {
    const existingNode = baseNodeMap.get(nodeId);
    if (existingNode) {
      mergeNodeData(existingNode, node);
    } else {
      baseNodeMap.set(nodeId, node);
    }
  }

  for (const rawNode of rawNodes) {
    const parentId = extractExplicitParentId(rawNode);
    if (!parentId) {
      continue;
    }
    const parentNode = baseNodeMap.get(parentId);
    const childNode = baseNodeMap.get(String(rawNode.id || ""));
    safeAddChild(parentNode, childNode, parentMap);
  }

  for (const treeRoot of treeRoots) {
    const existingRoot = baseNodeMap.get(treeRoot.id);
    mergeExpansionTree(baseNodeMap, parentMap, existingRoot || treeRoot);
  }

  for (const node of flatNodes.values()) {
    if (!parentMap.has(node.id) && node.id !== baseRoot.id && shouldAttachToRoot(node)) {
      const attachTarget = baseNodeMap.get(node.id);
      safeAddChild(baseRoot, attachTarget, parentMap);
    }
  }

  const mappedEdges = rawEdges
    .filter((edge) => edge && edge.source && edge.target)
    .map((edge) => ({
      source: String(edge.source),
      target: String(edge.target),
      type: String(edge.type || edge.relationship || "relationship"),
    }));
  if (mappedEdges.length > 0) {
    baseRoot.relationships = mappedEdges;
  }

  return baseRoot;
}

function combineExpansionPayloads(...payloads) {
  const nodes = [];
  const edges = [];
  const candidateNodes = [];

  for (const payload of payloads) {
    if (!payload) {
      continue;
    }
    nodes.push(...extractExpansionNodes(payload));
    edges.push(...extractExpansionEdges(payload));
    if (Array.isArray(payload.candidateNodes)) {
      candidateNodes.push(...payload.candidateNodes);
    }
  }

  return {
    nodes,
    edges,
    candidateNodes,
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    const error = new Error(`Failed to load ${url}: ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function loadMergedGraphData({
  baseUrl,
  corporateUrl,
  expandedNodesUrl = "./output/expanded_nodes.json",
  expandedEdgesUrl = "./output/expanded_edges.json",
  candidateNodesUrl = "./output/candidate_nodes.json",
  onStatus = () => {},
} = {}) {
  onStatus("Fetching federal hierarchy…");
  const basePromise = fetchJson(baseUrl);
  onStatus("Fetching corporate expansion…");
  const corporatePromise = fetchJson(corporateUrl).catch((error) => {
    if (error.status === 404) {
      return null;
    }
    throw error;
  });
  onStatus("Fetching pipeline-expanded nodes…");
  const expandedNodesPromise = fetchJson(expandedNodesUrl).catch((error) => {
    if (error.status === 404) {
      return [];
    }
    throw error;
  });
  onStatus("Fetching pipeline-expanded edges…");
  const expandedEdgesPromise = fetchJson(expandedEdgesUrl).catch((error) => {
    if (error.status === 404) {
      return [];
    }
    throw error;
  });
  const candidateNodesPromise = fetchJson(candidateNodesUrl).catch((error) => {
    if (error.status === 404) {
      return [];
    }
    throw error;
  });

  const [baseRaw, corporateData, expandedNodes, expandedEdges, candidateNodes] = await Promise.all([
    basePromise,
    corporatePromise,
    expandedNodesPromise,
    expandedEdgesPromise,
    candidateNodesPromise,
  ]);
  const baseData = normalizeNode(baseRaw);

  onStatus("Merging federal and corporate structures…");
  const mergedPayload = combineExpansionPayloads(
    corporateData,
    expandedNodes.length > 0 || expandedEdges.length > 0
      ? {
          nodes: expandedNodes,
          edges: expandedEdges,
          candidateNodes: candidateNodes.map(normalizeCandidateNode),
        }
      : null,
  );
  const mergedGraph = mergedPayload.nodes.length > 0 || mergedPayload.edges.length > 0
    ? mergeExpansionGraph(baseData, cloneValue(mergedPayload))
    : baseData;
  mergedGraph.candidateNodes = candidateNodes.map(normalizeCandidateNode);
  trimDepth(mergedGraph);

  onStatus("Indexing hierarchy and preparing GPU batches…");
  return mergedGraph;
}
