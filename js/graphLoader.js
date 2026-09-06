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
    // Already a child of this parent — record the relationship so later
    // passes (e.g. attach-to-root) never see the node as unparented.
    parentMap.set(childNode.id, parentNode.id);
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
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const sourceUrls = Array.isArray(rawCandidate?.sourceUrls)
    ? rawCandidate.sourceUrls.map((value) => String(value))
    : rawCandidate?.sourceUrl
      ? [String(rawCandidate.sourceUrl)]
      : [];
  const sourceTypes = Array.isArray(rawCandidate?.sourceTypes) && rawCandidate.sourceTypes.length > 0
    ? rawCandidate.sourceTypes.map((value) => String(value))
    : ["candidate_discovery"];
  return normalizeNode({
    id: String(rawCandidate?.id || `candidate-${slug || "node"}`),
    name,
    type: String(rawCandidate?.type || "Candidate"),
    desc: String(rawCandidate?.desc || `Candidate node discovered via ${rawCandidate?.discoveryMethod || "automated discovery"}.`),
    color: typeof rawCandidate?.color === "string" ? rawCandidate.color : "#9b8bbd",
    sourceUrls,
    sourceTypes,
    confidenceScore: Number(rawCandidate?.confidenceScore ?? rawCandidate?.confidenceEstimate ?? 0),
    verificationStatus: String(rawCandidate?.verificationStatus || "unverified"),
    lastVerified: rawCandidate?.lastVerified || null,
    sourceCount: rawCandidate?.sourceCount != null && Number.isFinite(Number(rawCandidate.sourceCount))
      ? Number(rawCandidate.sourceCount)
      : sourceUrls.length,
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
    // Always walk the expansion subtree itself: mergeExpansionTree resolves
    // each id against the base map, so an already-existing root has its
    // expansion children grafted on instead of being silently skipped.
    mergeExpansionTree(baseNodeMap, parentMap, treeRoot);
  }

  for (const node of flatNodes.values()) {
    if (!parentMap.has(node.id) && node.id !== baseRoot.id && shouldAttachToRoot(node)) {
      const attachTarget = baseNodeMap.get(node.id);
      safeAddChild(baseRoot, attachTarget, parentMap);
    }
  }

  // Merge, never replace: graph.json carries the exporter's relationships and
  // the corporate overlay always loads, so an assignment here dropped every
  // pipeline edge whenever expanded_edges.json was stale or missing.
  const existingRelationships = Array.isArray(baseRoot.relationships) ? baseRoot.relationships : [];
  const seenEdges = new Set();
  const mergedRelationships = [];
  for (const edge of [...existingRelationships, ...rawEdges]) {
    if (!edge || !edge.source || !edge.target) {
      continue;
    }
    const normalized = {
      source: String(edge.source),
      target: String(edge.target),
      type: String(edge.type || edge.relationship || "relationship"),
    };
    const key = `${normalized.source}::${normalized.target}::${normalized.type}`;
    if (seenEdges.has(key)) {
      continue;
    }
    seenEdges.add(key);
    mergedRelationships.push(normalized);
  }
  baseRoot.relationships = mergedRelationships;

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
  const response = await fetch(url);
  if (!response.ok) {
    const error = new Error(`Failed to load ${url}: ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function optionalFetchFallback(url, fallbackValue) {
  return (error) => {
    if (error.status !== 404) {
      console.warn(`Optional data file ${url} failed to load - continuing without it.`, error);
    }
    return fallbackValue;
  };
}

export async function loadMergedGraphData({
  baseUrl,
  fallbackBaseUrl = "./data/federal_gov_complete_1.json",
  corporateUrl,
  expandedNodesUrl = "./output/expanded_nodes.json",
  expandedEdgesUrl = "./output/expanded_edges.json",
  candidateNodesUrl = "./output/candidate_nodes.json",
  onStatus = () => {},
} = {}) {
  onStatus("Fetching federal hierarchy…");
  // fetchJson has no catch of its own, so without this a missing or malformed
  // pipeline artefact is a blank screen rather than a degraded one. Degrade to
  // the curated hierarchy instead, and say so.
  let loadSource = "primary";
  const basePromise =
    fallbackBaseUrl && fallbackBaseUrl !== baseUrl
      ? fetchJson(baseUrl).catch(() => {
          onStatus("Pipeline graph unavailable — falling back to the base hierarchy…");
          loadSource = "fallback";
          return fetchJson(fallbackBaseUrl);
        })
      : fetchJson(baseUrl);
  onStatus("Fetching corporate expansion…");
  const corporatePromise = corporateUrl
    ? fetchJson(corporateUrl).catch(optionalFetchFallback(corporateUrl, null))
    : Promise.resolve(null);
  onStatus("Fetching pipeline-expanded nodes…");
  const expandedNodesPromise = fetchJson(expandedNodesUrl).catch(optionalFetchFallback(expandedNodesUrl, []));
  onStatus("Fetching pipeline-expanded edges…");
  const expandedEdgesPromise = fetchJson(expandedEdgesUrl).catch(optionalFetchFallback(expandedEdgesUrl, []));
  const candidateNodesPromise = fetchJson(candidateNodesUrl).catch(optionalFetchFallback(candidateNodesUrl, []));

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
  trimDepth(mergedGraph);

  // Drop candidates whose id already exists in the merged tree (or earlier in the
  // candidate list) so they cannot alias/overwrite real graph nodes downstream.
  const mergedNodeIds = new Set();
  walkTree(mergedGraph, (node) => mergedNodeIds.add(node.id));
  mergedGraph.candidateNodes = [];
  for (const rawCandidate of candidateNodes) {
    const candidateNode = normalizeCandidateNode(rawCandidate);
    if (mergedNodeIds.has(candidateNode.id)) {
      continue;
    }
    mergedNodeIds.add(candidateNode.id);
    mergedGraph.candidateNodes.push(candidateNode);
  }

  // The status line that announced the fallback is overwritten in the same
  // tick; the flag lets the page say so where the visitor can read it.
  mergedGraph.__loadSource = loadSource;
  onStatus("Indexing hierarchy and preparing GPU batches…");
  return mergedGraph;
}
