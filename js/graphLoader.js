const DEFAULT_NODE = {
  id: "",
  name: "Unnamed Node",
  type: "Unknown",
  desc: "",
  employees: null,
  budget: null,
  color: "#666666",
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
  targetNode.name = sourceNode.name || targetNode.name;
  targetNode.type = sourceNode.type || targetNode.type;
  targetNode.desc = sourceNode.desc || targetNode.desc;
  targetNode.employees = sourceNode.employees ?? targetNode.employees;
  targetNode.budget = sourceNode.budget ?? targetNode.budget;
  targetNode.color = sourceNode.color || targetNode.color;
}

function extractExplicitParentId(rawNode) {
  return rawNode.parentId || rawNode.parent || rawNode.attachTo || rawNode.attachToId || rawNode.source || null;
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
    if (!parentMap.has(node.id) && node.id !== baseRoot.id) {
      const attachTarget = baseNodeMap.get(node.id);
      safeAddChild(baseRoot, attachTarget, parentMap);
    }
  }

  baseRoot.relationships = rawEdges
    .filter((edge) => edge && edge.source && edge.target)
    .map((edge) => ({
      source: String(edge.source),
      target: String(edge.target),
      type: String(edge.type || "relationship"),
    }));

  return baseRoot;
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

export async function loadMergedGraphData({
  baseUrl,
  corporateUrl,
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

  const [baseRaw, corporateData] = await Promise.all([basePromise, corporatePromise]);
  const baseData = normalizeNode(baseRaw);

  onStatus("Merging federal and corporate structures…");
  const mergedGraph = corporateData ? mergeExpansionGraph(baseData, cloneValue(corporateData)) : baseData;
  trimDepth(mergedGraph);

  onStatus("Indexing hierarchy and preparing GPU batches…");
  return mergedGraph;
}
