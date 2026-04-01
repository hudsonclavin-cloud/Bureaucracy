const DISTANCE_THRESHOLDS = {
  COSMIC_VIEW: 900,
  BRANCH_VIEW: 500,
  AGENCY_VIEW: 250,
  OFFICE_VIEW: 120,
  POSITION_VIEW: 60,
};

const LEVELS = [
  {
    level: 0,
    label: "Cosmic View",
    maxDepth: 1,
    showHierarchyEdges: true,
    showRelationshipEdges: false,
    showHalos: true,
    clusterHiddenDescendants: false,
    clusterPositionsOnly: false,
    pickRadius: 24,
    nodeScale: 0.2,
    tileSize: 120,
    nodesPerTile: 2,
    autoExpand: false,
    autoExpandDistance: 0,
    visibleNodeBudget: 1200,
  },
  {
    level: 1,
    label: "Branch View",
    maxDepth: 2,
    showHierarchyEdges: true,
    showRelationshipEdges: false,
    showHalos: false,
    clusterHiddenDescendants: true,
    clusterPositionsOnly: false,
    pickRadius: 22,
    nodeScale: 0.34,
    tileSize: 110,
    nodesPerTile: 3,
    autoExpand: false,
    autoExpandDistance: 260,
    visibleNodeBudget: 3600,
  },
  {
    level: 2,
    label: "Agency View",
    maxDepth: 3,
    showHierarchyEdges: true,
    showRelationshipEdges: false,
    showHalos: false,
    clusterHiddenDescendants: true,
    clusterPositionsOnly: false,
    pickRadius: 20,
    nodeScale: 0.5,
    tileSize: 100,
    nodesPerTile: 4,
    autoExpand: true,
    autoExpandDistance: 220,
    visibleNodeBudget: 9000,
  },
  {
    level: 3,
    label: "Office View",
    maxDepth: 4,
    showHierarchyEdges: true,
    showRelationshipEdges: true,
    showHalos: false,
    clusterHiddenDescendants: true,
    clusterPositionsOnly: true,
    pickRadius: 18,
    nodeScale: 0.68,
    tileSize: 92,
    nodesPerTile: 6,
    autoExpand: true,
    autoExpandDistance: 180,
    visibleNodeBudget: 20000,
  },
  {
    level: 4,
    label: "Position View",
    maxDepth: 5,
    showHierarchyEdges: true,
    showRelationshipEdges: true,
    showHalos: false,
    clusterHiddenDescendants: false,
    clusterPositionsOnly: false,
    pickRadius: 16,
    nodeScale: 1,
    tileSize: 84,
    nodesPerTile: 8,
    autoExpand: true,
    autoExpandDistance: 150,
    visibleNodeBudget: 32000,
  },
];

const HALO_ROOTS = new Set([
  "constitution",
  "legislative branch",
  "executive branch",
  "judicial branch",
  "independent agencies",
  "independent agency",
]);

function normalizeKey(value) {
  return String(value || "").trim().toLowerCase();
}

function getLevelForDistance(cameraDistance) {
  if (cameraDistance > DISTANCE_THRESHOLDS.COSMIC_VIEW) {
    return LEVELS[0];
  }
  if (cameraDistance > DISTANCE_THRESHOLDS.BRANCH_VIEW) {
    return LEVELS[1];
  }
  if (cameraDistance > DISTANCE_THRESHOLDS.AGENCY_VIEW) {
    return LEVELS[2];
  }
  if (cameraDistance > DISTANCE_THRESHOLDS.OFFICE_VIEW) {
    return LEVELS[3];
  }
  return LEVELS[4];
}

function getHaloNodeIds(rootNode) {
  const haloIds = new Set();
  if (!rootNode) {
    return haloIds;
  }

  haloIds.add(rootNode.data?.id);
  for (const child of rootNode.childObjs || []) {
    const normalizedName = normalizeKey(child.data?.name || child.data?.id);
    const normalizedType = normalizeKey(child.data?.type);
    if (
      HALO_ROOTS.has(normalizedName) ||
      normalizedType.includes("branch") ||
      normalizedType.includes("independent")
    ) {
      haloIds.add(child.data?.id);
    }
  }
  return haloIds;
}

function getClusterKind(data) {
  const type = normalizeKey(data?.type);
  if (type.includes("agency")) {
    return "agency";
  }
  if (type.includes("bureau")) {
    return "bureau";
  }
  if (type.includes("office")) {
    return "office";
  }
  if (type.includes("position")) {
    return "positions";
  }
  return "group";
}

const CLUSTER_THRESHOLDS = {
  agency: { minDescendants: [18, 16, 14, 10, Infinity], collapseDistance: [9999, 420, 320, 240, 0] },
  bureau: { minDescendants: [16, 14, 12, 9, Infinity], collapseDistance: [9999, 380, 280, 210, 0] },
  office: { minDescendants: [13, 11, 9, 7, Infinity], collapseDistance: [9999, 320, 230, 175, 0] },
  positions: { minDescendants: [10, 8, 6, 5, Infinity], collapseDistance: [9999, 260, 190, 150, 0] },
  group: { minDescendants: [14, 12, 10, 8, Infinity], collapseDistance: [9999, 350, 260, 200, 0] },
};

export function createLodManager({ maxDepth = Infinity } = {}) {
  return {
    thresholds: DISTANCE_THRESHOLDS,
    levels: LEVELS,
    getLevel(cameraDistance) {
      return getLevelForDistance(cameraDistance).level;
    },
    updateLOD({ cameraDistance, rootNode, maxDepthFilter = Infinity }) {
      const levelConfig = getLevelForDistance(cameraDistance);
      const visibleDepth = Math.min(
        maxDepth,
        Number.isFinite(maxDepthFilter) ? maxDepthFilter : maxDepth,
        levelConfig.maxDepth,
      );
      return {
        ...levelConfig,
        cameraDistance,
        visibleDepth,
        haloNodeIds: getHaloNodeIds(rootNode),
      };
    },
    getNodeScale(cameraDistance, lodState) {
      if (lodState.level === 4) {
        return Math.min(1, Math.max(0.3, 1 / Math.max(cameraDistance / 60, 1)));
      }
      return lodState.nodeScale;
    },
    shouldRenderNode(nodeObj, lodState) {
      if (!nodeObj?.visible || nodeObj.depth > lodState.visibleDepth) {
        return false;
      }
      if (lodState.level === 0) {
        return lodState.haloNodeIds.has(nodeObj.data?.id);
      }
      return true;
    },
    shouldRenderHalo(nodeObj, lodState) {
      if (!lodState.showHalos || !nodeObj?.visible) {
        return false;
      }
      return lodState.haloNodeIds.has(nodeObj.data?.id);
    },
    getClusterPolicy(nodeObj, lodState) {
      const kind = getClusterKind(nodeObj?.data);
      const policy = CLUSTER_THRESHOLDS[kind] || CLUSTER_THRESHOLDS.group;
      return {
        kind,
        minDescendants: policy.minDescendants[lodState.level],
        collapseDistance: policy.collapseDistance[lodState.level],
      };
    },
    shouldClusterNode(nodeObj, lodState) {
      if (!lodState.clusterHiddenDescendants || !nodeObj?.visible) {
        return false;
      }
      const maxNodeDepth = nodeObj.data?.__meta?.maxDepth ?? nodeObj.depth;
      if (maxNodeDepth <= lodState.visibleDepth) {
        return false;
      }
      if (lodState.clusterPositionsOnly) {
        return nodeObj.depth >= lodState.visibleDepth - 1;
      }
      return nodeObj.depth < lodState.visibleDepth - 1;
    },
  };
}

export { DISTANCE_THRESHOLDS, LEVELS };
