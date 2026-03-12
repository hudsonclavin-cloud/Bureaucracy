import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const CAMERA_DISTANCE = 280;
const HIDDEN_OFFSET = 1e8;
const MAX_NODES = 25000;
const MAX_DEPTH = 20;
const NODE_RADIUS = 4;
const NODE_OPACITY = 0.92;
const EXPANSION_TIME_BUDGET_MS = 8;
const EXPANSION_CHILD_BUDGET = 240;
const EXPANSION_PARENT_BATCH = 48;
const CLUSTER_CAPACITY = 8192;
const branchColors = {
  constitution: "#FFD166",
  legislative: "#9B5DE5",
  executive: "#F94144",
  judicial: "#4D96FF",
  independent: "#06D6A0",
  regulatory: "#F8961E",
  position: "#B0B0B0",
};

export function createGovernmentGraph({
  canvas,
  onSelect = () => {},
  onHover = () => {},
  onCountsChange = () => {},
} = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x020408, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(52, window.innerWidth / window.innerHeight, 0.1, 3000);
  camera.position.set(0, 0, CAMERA_DISTANCE);

  scene.add(new THREE.AmbientLight(0xffffff, 1.55));
  const lightA = new THREE.PointLight(0xffffff, 2.6, 900);
  lightA.position.set(0, 120, 120);
  scene.add(lightA);
  const lightB = new THREE.PointLight(0x4D96FF, 1.8, 700);
  lightB.position.set(-120, -60, 60);
  scene.add(lightB);
  const lightC = new THREE.PointLight(0xFFD166, 1.4, 700);
  lightC.position.set(100, -100, -60);
  scene.add(lightC);

  const particleGeometry = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(2400 * 3);
  for (let i = 0; i < 2400; i += 1) {
    const index = i * 3;
    particlePositions[index] = (Math.random() - 0.5) * 900;
    particlePositions[index + 1] = (Math.random() - 0.5) * 900;
    particlePositions[index + 2] = (Math.random() - 0.5) * 900;
  }
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({ color: 0x223344, size: 0.4, transparent: true, opacity: 0.5 }),
  );
  scene.add(particles);

  const selectionHalo = new THREE.Mesh(
    new THREE.SphereGeometry(1, 18, 18),
    new THREE.MeshBasicMaterial({
      color: 0xc8a84a,
      transparent: true,
      opacity: 0.18,
      side: THREE.BackSide,
    }),
  );
  selectionHalo.visible = false;
  scene.add(selectionHalo);

  const rootHalo = new THREE.Mesh(
    new THREE.SphereGeometry(1, 16, 16),
    new THREE.MeshBasicMaterial({
      color: 0xc8a84a,
      transparent: true,
      opacity: 0.08,
      side: THREE.BackSide,
    }),
  );
  rootHalo.visible = false;
  scene.add(rootHalo);

  const raycaster = new THREE.Raycaster();
  raycaster.params.Points.threshold = 5;
  const mouse2d = new THREE.Vector2();
  const frustum = new THREE.Frustum();
  const projectionMatrix = new THREE.Matrix4();
  const upVector = new THREE.Vector3(0, 1, 0);
  const basisA = new THREE.Vector3();
  const basisB = new THREE.Vector3();
  const directionVec = new THREE.Vector3();
  const tempVecA = new THREE.Vector3();
  const tempMat4 = new THREE.Matrix4();
  const tempQuat = new THREE.Quaternion();
  const tempScale = new THREE.Vector3();
  const tempSphere = new THREE.Sphere();
  const tempClusterColor = new THREE.Color();
  const hiddenMatrix = new THREE.Matrix4().compose(
    new THREE.Vector3(HIDDEN_OFFSET, HIDDEN_OFFSET, HIDDEN_OFFSET),
    tempQuat,
    new THREE.Vector3(0.0001, 0.0001, 0.0001),
  );
  const hiddenVector = new THREE.Vector3(HIDDEN_OFFSET, HIDDEN_OFFSET, HIDDEN_OFFSET);
  const clusterColor = new THREE.Color(0xc8a84a);
  const clusterAccentColor = new THREE.Color(0x5a7bb8);

  const state = {
    data: null,
    rootObj: null,
    selectedNode: null,
    totalNodeCount: 0,
    maxDataDepth: 0,
    maxNodes: 0,
    maxVisibleDepth: MAX_DEPTH,
    nodeMap: new Map(),
    dataMap: new Map(),
    parentIdById: new Map(),
    searchIndex: [],
    depthTotals: new Map(),
    nodeBatches: new Map(),
    clusterBatch: null,
    edgeBatch: null,
    allNodes: [],
    allEdges: [],
    visibleNodes: [],
    visibleNodeCount: 0,
    activeClusters: [],
    clusterMap: new Map(),
    pendingExpansions: [],
    relationships: [],
    relationshipIndex: new Map(),
    connectedRelationshipKeys: new Set(),
    countsVersion: 0,
    isDragging: false,
    prevMouse: { x: 0, y: 0 },
    mouseDownPos: { x: 0, y: 0 },
    rotX: 0,
    rotY: 0,
    targetRotX: 0,
    targetRotY: 0,
    zoom: 1,
    targetZoom: 1,
    camFocus: new THREE.Vector3(),
    camFocusTarget: new THREE.Vector3(),
    time: 0,
    frame: 0,
    renderDirty: false,
    forceFullRenderRefresh: true,
    lastCameraSignature: "",
    flyMode: false,
    keyState: {
      KeyW: false,
      KeyA: false,
      KeyS: false,
      KeyD: false,
      KeyQ: false,
      KeyE: false,
    },
  };

  function notifyCounts() {
    onCountsChange({
      visibleNodeCount: state.visibleNodeCount,
      totalNodeCount: state.totalNodeCount,
      maxDataDepth: state.maxDataDepth,
      maxVisibleDepth: state.maxVisibleDepth,
      maxNodes: state.maxNodes,
      pendingExpansions: state.pendingExpansions.length,
    });
  }

  function hexToInt(hex) {
    return parseInt((hex || "#888888").replace("#", ""), 16);
  }

  function getNodeColor(data) {
    const id = String(data?.id || "").toLowerCase();
    const type = String(data?.type || "").toLowerCase();

    if (type.includes("constitution") || id === "constitution" || id.startsWith("const")) {
      return branchColors.constitution;
    }
    if (type === "position" || type.includes("office") || type.includes("officer")) {
      return branchColors.position;
    }
    if (id.startsWith("leg-")) {
      return branchColors.legislative;
    }
    if (id.startsWith("jud-")) {
      return branchColors.judicial;
    }
    if (id.startsWith("exec-regulatory") || type.includes("regulatory")) {
      return branchColors.regulatory;
    }
    if (
      id.startsWith("exec-ind") ||
      id === "exec-independent" ||
      type.includes("government corporation") ||
      type.includes("independent")
    ) {
      return branchColors.independent;
    }
    if (id.startsWith("exec-")) {
      return branchColors.executive;
    }
    return data?.color || branchColors.position;
  }

  function hashString(input) {
    let hash = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      hash ^= input.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function nodeRadiusForDepth(depth) {
    return NODE_RADIUS;
  }

  function shellRadiusForDepth(depth) {
    return 18 + depth * 36 + depth * depth * 4.5;
  }

  function registerDataNode(node, parentId = null, depth = 0, path = []) {
    const nextPath = [...path, node.name];
    state.dataMap.set(node.id, node);
    state.parentIdById.set(node.id, parentId);
    state.depthTotals.set(depth, (state.depthTotals.get(depth) || 0) + 1);
    state.searchIndex.push({
      id: node.id,
      name: node.name,
      type: node.type,
      color: node.color,
      pathStr: path.join(" › "),
    });

    let subtreeCount = 1;
    let subtreeDepth = depth;
    const children = node.children || [];
    for (const child of children) {
      const childMeta = registerDataNode(child, node.id, depth + 1, nextPath);
      subtreeCount += childMeta.subtreeCount;
      subtreeDepth = Math.max(subtreeDepth, childMeta.maxDepth);
    }

    node.__meta = {
      depth,
      subtreeCount,
      maxDepth: subtreeDepth,
      childCount: children.length,
    };
    return { subtreeCount, maxDepth: subtreeDepth };
  }

  function createNodeBatch(depth, capacity) {
    const radius = nodeRadiusForDepth(depth);
    const geometry = new THREE.SphereGeometry(radius, depth <= 2 ? 16 : 10, depth <= 2 ? 16 : 10);
    const material = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.3,
      roughness: 0.38,
      metalness: 0.05,
      transparent: true,
      opacity: NODE_OPACITY,
      vertexColors: true,
    });
    const mesh = new THREE.InstancedMesh(geometry, material, Math.max(capacity, 1));
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.frustumCulled = false;
    scene.add(mesh);
    return {
      depth,
      radius,
      mesh,
      nodesBySlot: new Array(Math.max(capacity, 1)),
      nextSlot: 0,
      freeSlots: [],
      dirty: true,
    };
  }

  function ensureNodeBatches() {
    for (const [depth, count] of state.depthTotals) {
      state.nodeBatches.set(depth, createNodeBatch(depth, count));
    }

    const clusterGeometry = new THREE.SphereGeometry(1, 12, 12);
    const clusterMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.18,
      roughness: 0.5,
      metalness: 0.04,
      transparent: true,
      opacity: 0.9,
      vertexColors: true,
    });
    const clusterMesh = new THREE.InstancedMesh(clusterGeometry, clusterMaterial, CLUSTER_CAPACITY);
    clusterMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    clusterMesh.frustumCulled = false;
    scene.add(clusterMesh);
    state.clusterBatch = {
      mesh: clusterMesh,
      clustersBySlot: new Array(CLUSTER_CAPACITY),
      dirty: true,
    };

    const edgeCapacity = Math.max(state.totalNodeCount + state.relationships.length + 256, 1);
    const edgePositions = new Float32Array(edgeCapacity * 6);
    const edgeColors = new Float32Array(edgeCapacity * 6);
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute("color", new THREE.BufferAttribute(edgeColors, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x999999,
      transparent: true,
      opacity: 0.3,
    });
    const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeLines.frustumCulled = false;
    scene.add(edgeLines);
    state.edgeBatch = {
      positions: edgePositions,
      colors: edgeColors,
      geometry: edgeGeometry,
      lines: edgeLines,
      nextSlot: 0,
      freeSlots: [],
      dirtyPositions: false,
      dirtyColors: false,
    };
  }

  function assignBatchSlot(nodeObj) {
    const batch = state.nodeBatches.get(nodeObj.depth);
    nodeObj.batch = batch;
    nodeObj.slot = batch.freeSlots.length > 0 ? batch.freeSlots.pop() : batch.nextSlot++;
    batch.nodesBySlot[nodeObj.slot] = nodeObj;
  }

  function createNodeObj(data, parent, depth) {
    const nodeObj = {
      data,
      parent,
      depth,
      pos: new THREE.Vector3(),
      targetPos: new THREE.Vector3(),
      animFrom: new THREE.Vector3(),
      visible: false,
      expanded: false,
      childObjs: [],
      edges: [],
      animating: false,
      animStart: 0,
      batch: null,
      slot: -1,
      culled: false,
      clustered: false,
      renderVisible: false,
      clusterRef: null,
      edgeToParent: null,
    };

    assignBatchSlot(nodeObj);
    state.nodeMap.set(data.id, nodeObj);
    state.allNodes.push(nodeObj);
    return nodeObj;
  }

  function markVisible(nodeObj) {
    if (nodeObj.visible) {
      return;
    }
    nodeObj.visible = true;
    state.visibleNodes.push(nodeObj);
    state.visibleNodeCount += 1;
    state.renderDirty = true;
  }

  function hideNodeInstance(nodeObj) {
    if (!nodeObj.batch) {
      return;
    }
    nodeObj.batch.mesh.setMatrixAt(nodeObj.slot, hiddenMatrix);
    nodeObj.batch.dirty = true;
    nodeObj.renderVisible = false;
  }

  function markHidden(nodeObj) {
    if (!nodeObj.visible) {
      return;
    }
    nodeObj.visible = false;
    nodeObj.culled = false;
    nodeObj.clustered = false;
    nodeObj.clusterRef = null;
    state.visibleNodeCount -= 1;
    const visibleIndex = state.visibleNodes.indexOf(nodeObj);
    if (visibleIndex >= 0) {
      state.visibleNodes.splice(visibleIndex, 1);
    }
    hideNodeInstance(nodeObj);
    state.renderDirty = true;
  }

  function setNodeMatrix(nodeObj, scaleMultiplier = 1) {
    tempMat4.compose(
      nodeObj.pos,
      tempQuat,
      tempScale.set(scaleMultiplier, scaleMultiplier, scaleMultiplier),
    );
    nodeObj.batch.mesh.setMatrixAt(nodeObj.slot, tempMat4);
    nodeObj.batch.dirty = true;
    nodeObj.renderVisible = scaleMultiplier > 0;
  }

  function setNodeColor(nodeObj) {
    const resolvedColor = getNodeColor(nodeObj.data);
    nodeObj.batch.mesh.setColorAt(nodeObj.slot, new THREE.Color(hexToInt(resolvedColor)));
    nodeObj.batch.dirty = true;
  }

  function relationshipKey(fromId, toId, type = "relationship") {
    return `${fromId}->${toId}:${type}`;
  }

  function createEdge(fromObj, toObj, options = {}) {
    const edge = {
      from: fromObj,
      to: toObj,
      slot: state.edgeBatch.freeSlots.length > 0 ? state.edgeBatch.freeSlots.pop() : state.edgeBatch.nextSlot++,
      active: false,
      color: new THREE.Color(hexToInt(options.color || "#aaaaaa")),
      type: options.type || "hierarchy",
      key: options.key || null,
    };
    state.allEdges.push(edge);
    fromObj.edges.push(edge);
    toObj.edges.push(edge);
    if (edge.type === "hierarchy") {
      toObj.edgeToParent = edge;
    }
    hideEdge(edge);
    return edge;
  }

  function setEdgeColor(edge) {
    if (!state.edgeBatch.geometry.getAttribute("color")) {
      return;
    }
    const offset = edge.slot * 6;
    for (let i = 0; i < 2; i += 1) {
      state.edgeBatch.colors[offset + i * 3] = edge.color.r;
      state.edgeBatch.colors[offset + i * 3 + 1] = edge.color.g;
      state.edgeBatch.colors[offset + i * 3 + 2] = edge.color.b;
    }
    state.edgeBatch.dirtyColors = true;
  }

  function updateEdge(edge) {
    const offset = edge.slot * 6;
    state.edgeBatch.positions[offset] = edge.from.pos.x;
    state.edgeBatch.positions[offset + 1] = edge.from.pos.y;
    state.edgeBatch.positions[offset + 2] = edge.from.pos.z;
    state.edgeBatch.positions[offset + 3] = edge.to.pos.x;
    state.edgeBatch.positions[offset + 4] = edge.to.pos.y;
    state.edgeBatch.positions[offset + 5] = edge.to.pos.z;
    state.edgeBatch.dirtyPositions = true;
    edge.active = true;
  }

  function hideEdge(edge) {
    const offset = edge.slot * 6;
    state.edgeBatch.positions[offset] = hiddenVector.x;
    state.edgeBatch.positions[offset + 1] = hiddenVector.y;
    state.edgeBatch.positions[offset + 2] = hiddenVector.z;
    state.edgeBatch.positions[offset + 3] = hiddenVector.x;
    state.edgeBatch.positions[offset + 4] = hiddenVector.y;
    state.edgeBatch.positions[offset + 5] = hiddenVector.z;
    state.edgeBatch.dirtyPositions = true;
    edge.active = false;
  }

  function applyEdgeVisibility(edge) {
    const show =
      edge.from.renderVisible &&
      edge.to.renderVisible &&
      !edge.from.clustered &&
      !edge.to.clustered &&
      state.zoom >= (edge.type === "relationship" ? 0.8 : 0.55) &&
      edge.from.depth < state.maxVisibleDepth &&
      edge.to.depth <= state.maxVisibleDepth;
    if (show) {
      updateEdge(edge);
    } else {
      hideEdge(edge);
    }
  }

  function getOrbitBasis(anchorDir) {
    basisA.copy(anchorDir);
    if (Math.abs(basisA.dot(upVector)) > 0.92) {
      basisA.set(1, 0, 0);
    } else {
      basisA.cross(upVector).normalize();
    }
    basisB.copy(anchorDir).cross(basisA).normalize();
  }

  function getSpreadPositions(parentObj, children) {
    const depth = parentObj.depth + 1;
    const shellRadius = shellRadiusForDepth(depth);
    const anchorDir =
      parentObj.pos.lengthSq() > 0.0001
        ? tempVecA.copy(parentObj.pos).normalize()
        : new THREE.Vector3(
            Math.cos(hashString(parentObj.data.id) * 0.0003),
            0.3,
            Math.sin(hashString(parentObj.data.id) * 0.0003),
          ).normalize();
    getOrbitBasis(anchorDir);

    const count = children.length;
    const baseSpread = Math.min(0.9, 0.22 + count * 0.012 + depth * 0.015);
    const seed = hashString(parentObj.data.id) % 10000;
    const positions = new Array(count);

    for (let i = 0; i < count; i += 1) {
      const theta = GOLDEN_ANGLE * (i + seed * 0.001);
      const radial = Math.sqrt((i + 0.5) / Math.max(count, 1)) * baseSpread;
      directionVec
        .copy(anchorDir)
        .addScaledVector(basisA, Math.cos(theta) * radial)
        .addScaledVector(basisB, Math.sin(theta) * radial)
        .normalize();

      positions[i] = directionVec.clone().multiplyScalar(shellRadius);
    }

    return positions;
  }

  function estimateExpansionSize(nodes) {
    let nextNodes = 0;
    for (const nodeObj of nodes) {
      if (!nodeObj.expanded && !nodeObj.expanding) {
        nextNodes += (nodeObj.data.children || []).length;
      }
    }
    return nextNodes;
  }

  function indexRelationships(relationships = []) {
    state.relationships = [];
    state.relationshipIndex = new Map();
    state.connectedRelationshipKeys.clear();

    for (const relationship of relationships) {
      if (!relationship?.source || !relationship?.target) {
        continue;
      }
      const normalized = {
        source: String(relationship.source),
        target: String(relationship.target),
        type: String(relationship.type || "relationship"),
      };
      state.relationships.push(normalized);
      for (const nodeId of [normalized.source, normalized.target]) {
        if (!state.relationshipIndex.has(nodeId)) {
          state.relationshipIndex.set(nodeId, []);
        }
        state.relationshipIndex.get(nodeId).push(normalized);
      }
    }
  }

  function connectRelationshipsForNode(nodeObj) {
    const relationships = state.relationshipIndex.get(nodeObj.data.id) || [];
    for (const relationship of relationships) {
      const key = relationshipKey(relationship.source, relationship.target, relationship.type);
      if (state.connectedRelationshipKeys.has(key)) {
        continue;
      }
      const sourceNode = state.nodeMap.get(relationship.source);
      const targetNode = state.nodeMap.get(relationship.target);
      if (!sourceNode || !targetNode) {
        continue;
      }
      const edge = createEdge(sourceNode, targetNode, {
        type: "relationship",
        key,
        color: "#78a8ff",
      });
      setEdgeColor(edge);
      updateEdge(edge);
      state.connectedRelationshipKeys.add(key);
    }
  }

  function queueExpansion(parentObj, animate = true) {
    if (!parentObj || parentObj.expanded || parentObj.expanding) {
      return;
    }
    if (parentObj.depth >= MAX_DEPTH) {
      parentObj.expanded = true;
      parentObj.expanding = false;
      return;
    }
    const children = parentObj.data.children || [];
    if (children.length === 0) {
      parentObj.expanded = true;
      return;
    }

    parentObj.childObjs.length = 0;
    parentObj.expanding = true;
    state.pendingExpansions.push({
      parentObj,
      animate,
      children,
      positions: getSpreadPositions(parentObj, children),
      index: 0,
    });
  }

  function flushPendingExpansions(timeBudgetMs = EXPANSION_TIME_BUDGET_MS, childBudget = EXPANSION_CHILD_BUDGET) {
    const start = performance.now();
    let processedChildren = 0;

    while (
      state.pendingExpansions.length > 0 &&
      processedChildren < childBudget &&
      performance.now() - start < timeBudgetMs
    ) {
      const job = state.pendingExpansions[0];
      const { parentObj, children, positions, animate } = job;
      const childData = children[job.index];
      let childObj = state.nodeMap.get(childData.id);
      if (!childObj) {
        childObj = createNodeObj(childData, parentObj, parentObj.depth + 1);
        setNodeColor(childObj);
        connectRelationshipsForNode(childObj);
      }

      childObj.parent = parentObj;
      if (!parentObj.childObjs.includes(childObj)) {
        parentObj.childObjs.push(childObj);
      }
      markVisible(childObj);

      const targetPos = positions[job.index];
      childObj.targetPos.copy(targetPos);

      if (animate) {
        childObj.pos.copy(parentObj.pos);
        childObj.animFrom.copy(parentObj.pos);
        childObj.animStart = performance.now();
        childObj.animating = true;
      } else {
        childObj.pos.copy(targetPos);
        childObj.animating = false;
      }

      setNodeMatrix(childObj, 1);

      if (!childObj.edgeToParent) {
        const edge = createEdge(parentObj, childObj);
        setEdgeColor(edge);
        updateEdge(edge);
      }
      connectRelationshipsForNode(childObj);

      job.index += 1;
      processedChildren += 1;

      if (job.index >= children.length) {
        parentObj.expanded = true;
        parentObj.expanding = false;
        state.pendingExpansions.shift();
      }
    }

    if (processedChildren > 0) {
      state.renderDirty = true;
      notifyCounts();
    }
  }

  function expandNodesBatch(nodes, animate = true) {
    const expandedParents = [];
    for (const nodeObj of nodes.slice(0, EXPANSION_PARENT_BATCH)) {
      if (nodeObj.expanded || nodeObj.expanding) {
        continue;
      }
      queueExpansion(nodeObj, animate);
      expandedParents.push(nodeObj);
    }
    flushPendingExpansions(10, 1024);
    return expandedParents;
  }

  function expandNode(nodeObj, animate = true) {
    return expandNodesBatch([nodeObj], animate);
  }

  function disposeNodeObject(nodeObj) {
    if (nodeObj.batch) {
      nodeObj.batch.nodesBySlot[nodeObj.slot] = null;
      nodeObj.batch.freeSlots.push(nodeObj.slot);
    }
    state.nodeMap.delete(nodeObj.data.id);
    const nodeIndex = state.allNodes.indexOf(nodeObj);
    if (nodeIndex >= 0) {
      state.allNodes.splice(nodeIndex, 1);
    }
    markHidden(nodeObj);
  }

  function removeEdge(edge) {
    hideEdge(edge);
    state.edgeBatch.freeSlots.push(edge.slot);
    const edgeIndex = state.allEdges.indexOf(edge);
    if (edgeIndex >= 0) {
      state.allEdges.splice(edgeIndex, 1);
    }
    const fromIndex = edge.from.edges.indexOf(edge);
    if (fromIndex >= 0) {
      edge.from.edges.splice(fromIndex, 1);
    }
    const toIndex = edge.to.edges.indexOf(edge);
    if (toIndex >= 0) {
      edge.to.edges.splice(toIndex, 1);
    }
    if (edge.to.edgeToParent === edge) {
      edge.to.edgeToParent = null;
    }
    if (edge.key) {
      state.connectedRelationshipKeys.delete(edge.key);
    }
  }

  function isDescendantOf(nodeObj, ancestorObj) {
    let cursor = nodeObj;
    while (cursor) {
      if (cursor === ancestorObj) {
        return true;
      }
      cursor = cursor.parent;
    }
    return false;
  }

  function collapseNode(parentObj) {
    state.pendingExpansions = state.pendingExpansions.filter((job) => !isDescendantOf(job.parentObj, parentObj));

    for (const child of [...parentObj.childObjs]) {
      collapseNode(child);
      for (const edge of [...child.edges]) {
        removeEdge(edge);
      }
      disposeNodeObject(child);
    }
    parentObj.childObjs = [];
    parentObj.expanded = false;
    parentObj.expanding = false;
    state.renderDirty = true;
    notifyCounts();
  }

  function getAncestorIds(nodeObj) {
    const ancestorIds = new Set();
    let cursor = nodeObj;
    while (cursor) {
      ancestorIds.add(cursor.data.id);
      cursor = cursor.parent;
    }
    return ancestorIds;
  }

  function pruneDistantNodes() {
    if (state.visibleNodeCount <= state.maxNodes) {
      return;
    }

    const protectedIds = state.selectedNode?.isCluster ? new Set() : state.selectedNode ? getAncestorIds(state.selectedNode) : new Set();
    if (state.rootObj) {
      protectedIds.add(state.rootObj.data.id);
    }

    const candidates = state.allNodes
      .filter((nodeObj) => nodeObj.expanded && nodeObj.childObjs.length > 0 && !protectedIds.has(nodeObj.data.id))
      .sort((a, b) => b.pos.distanceTo(state.camFocusTarget) - a.pos.distanceTo(state.camFocusTarget));

    for (const candidate of candidates) {
      if (state.visibleNodeCount <= state.maxNodes) {
        break;
      }
      collapseNode(candidate);
    }
  }

  function updateSelectionHalo() {
    if (!state.selectedNode) {
      selectionHalo.visible = false;
      return;
    }

    const radius = state.selectedNode.isCluster
      ? Math.max(6, state.selectedNode.radius * 1.4)
      : nodeRadiusForDepth(state.selectedNode.depth) * 2.1;
    selectionHalo.visible = true;
    selectionHalo.position.copy(state.selectedNode.pos);
    selectionHalo.scale.setScalar(radius);
  }

  function setSelectedNode(nodeObj) {
    if (!nodeObj) {
      return;
    }

    state.selectedNode = nodeObj;
    state.camFocusTarget.copy(nodeObj.pos);
    updateSelectionHalo();
    onSelect(nodeObj);
  }

  function setDepthFilter(depth) {
    state.maxVisibleDepth = Number.isFinite(depth) ? Math.min(depth, MAX_DEPTH) : MAX_DEPTH;
    state.renderDirty = true;
    refreshVisibility();
  }

  function getFrontier(targetDepth = Infinity) {
    const boundedDepth = Number.isFinite(targetDepth) ? Math.min(targetDepth, MAX_DEPTH) : MAX_DEPTH;
    let minDepth = Infinity;
    const frontier = [];

    for (const nodeObj of state.visibleNodes) {
      if (nodeObj.expanded || nodeObj.expanding || nodeObj.depth >= boundedDepth) {
        continue;
      }
      const childCount = nodeObj.data.__meta?.childCount || 0;
      if (childCount === 0) {
        continue;
      }
      if (nodeObj.depth < minDepth) {
        minDepth = nodeObj.depth;
        frontier.length = 0;
      }
      if (nodeObj.depth === minDepth) {
        frontier.push(nodeObj);
      }
    }

    return { depth: minDepth, nodes: frontier };
  }

  function getPathIds(id) {
    const pathIds = [];
    let cursor = id;
    while (cursor) {
      pathIds.unshift(cursor);
      cursor = state.parentIdById.get(cursor) || null;
    }
    return pathIds;
  }

  function revealNodeById(id, animate = true) {
    if (!state.dataMap.has(id)) {
      return null;
    }

    const pathIds = getPathIds(id);
    for (let i = 0; i < pathIds.length - 1; i += 1) {
      const ancestorId = pathIds[i];
      const ancestorObj = state.nodeMap.get(ancestorId);
      if (ancestorObj && ancestorObj.depth < MAX_DEPTH && !ancestorObj.expanded) {
        expandNode(ancestorObj, animate);
      }
      flushPendingExpansions(12, 1200);
    }

    return state.nodeMap.get(id) || null;
  }

  function getRenderableFromIntersection(hit) {
    if (!hit || hit.instanceId == null) {
      return null;
    }
    if (hit.object === state.clusterBatch.mesh) {
      return state.clusterBatch.clustersBySlot[hit.instanceId] || null;
    }

    for (const batch of state.nodeBatches.values()) {
      if (hit.object === batch.mesh) {
        return batch.nodesBySlot[hit.instanceId] || null;
      }
    }
    return null;
  }

  function getHit(event) {
    if (!state.clusterBatch) {
      return null;
    }
    mouse2d.set((event.clientX / window.innerWidth) * 2 - 1, -(event.clientY / window.innerHeight) * 2 + 1);
    raycaster.setFromCamera(mouse2d, camera);
    const interactive = [state.clusterBatch.mesh, ...[...state.nodeBatches.values()].map((batch) => batch.mesh)];
    const hits = raycaster.intersectObjects(interactive, false);
    let clusterFallback = null;
    for (const hit of hits) {
      const target = getRenderableFromIntersection(hit);
      if (target && target.renderVisible !== false) {
        if (!target.isCluster) {
          return target;
        }
        if (!clusterFallback) {
          clusterFallback = target;
        }
      }
    }
    return clusterFallback;
  }

  function updateFrustum() {
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    projectionMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(projectionMatrix);
  }

  function clusterGridSize(depth) {
    return (42 + depth * 16) / Math.max(state.zoom, 0.25);
  }

  function shouldClusterNode(nodeObj) {
    if (nodeObj === state.rootObj || nodeObj === state.selectedNode || nodeObj.depth < 2) {
      return false;
    }
    if (state.zoom > 0.9) {
      return false;
    }
    return nodeObj.depth >= 2;
  }

  function setClusterSlot(slot, clusterObj) {
    const scale = Math.max(2.4, clusterObj.radius);
    tempMat4.compose(clusterObj.pos, tempQuat, tempScale.set(scale, scale, scale));
    state.clusterBatch.mesh.setMatrixAt(slot, tempMat4);
    state.clusterBatch.mesh.setColorAt(
      slot,
      tempClusterColor.copy(clusterColor).lerp(clusterAccentColor, Math.min(clusterObj.depth / 8, 0.5)),
    );
    state.clusterBatch.clustersBySlot[slot] = clusterObj;
    state.clusterBatch.dirty = true;
    clusterObj.slot = slot;
    clusterObj.renderVisible = true;
  }

  function hideClusterSlot(slot) {
    state.clusterBatch.mesh.setMatrixAt(slot, hiddenMatrix);
    state.clusterBatch.clustersBySlot[slot] = null;
    state.clusterBatch.dirty = true;
  }

  function recomputeClusters() {
    const clusterBuckets = new Map();
    for (const nodeObj of state.visibleNodes) {
      nodeObj.clustered = false;
      nodeObj.clusterRef = null;
      if (nodeObj.depth > state.maxVisibleDepth) {
        continue;
      }
      if (!shouldClusterNode(nodeObj)) {
        continue;
      }
      const cellSize = clusterGridSize(nodeObj.depth);
      const key = [
        nodeObj.depth,
        Math.round(nodeObj.pos.x / cellSize),
        Math.round(nodeObj.pos.y / cellSize),
        Math.round(nodeObj.pos.z / cellSize),
      ].join(":");
      if (!clusterBuckets.has(key)) {
        clusterBuckets.set(key, []);
      }
      clusterBuckets.get(key).push(nodeObj);
    }

    const nextClusters = [];
    for (const [key, members] of clusterBuckets) {
      if (members.length < 4) {
        continue;
      }
      let clusterObj = state.clusterMap.get(key);
      if (!clusterObj) {
        clusterObj = {
          key,
          isCluster: true,
          depth: members[0].depth,
          pos: new THREE.Vector3(),
          radius: 1,
          renderVisible: false,
          slot: -1,
          members: [],
          data: {},
        };
        state.clusterMap.set(key, clusterObj);
      }

      clusterObj.members = members;
      clusterObj.pos.set(0, 0, 0);
      for (const member of members) {
        clusterObj.pos.add(member.pos);
      }
      clusterObj.pos.multiplyScalar(1 / members.length);
      clusterObj.radius = 2.8 + Math.sqrt(members.length) * 0.9;
      clusterObj.data = {
        id: key,
        name: `${members.length} clustered nodes`,
        type: `Depth ${clusterObj.depth} cluster`,
        desc: "Zoom in to inspect individual offices.",
        color: branchColors.constitution,
        children: [],
      };
      nextClusters.push(clusterObj);
      for (const member of members) {
        member.clustered = true;
        member.clusterRef = clusterObj;
      }
    }

    for (const clusterObj of state.activeClusters) {
      clusterObj.renderVisible = false;
    }
    state.activeClusters = nextClusters;
  }

  function applyRenderVisibility() {
    if (!state.clusterBatch) {
      return;
    }
    updateFrustum();
    recomputeClusters();

    for (const nodeObj of state.allNodes) {
      nodeObj.renderVisible = false;
      if (!nodeObj.visible || nodeObj.depth > state.maxVisibleDepth || nodeObj.clustered) {
        hideNodeInstance(nodeObj);
        continue;
      }

      const radius = nodeRadiusForDepth(nodeObj.depth);
      tempSphere.center.copy(nodeObj.pos);
      tempSphere.radius = radius;
      nodeObj.culled = !frustum.intersectsSphere(tempSphere);
      if (nodeObj === state.selectedNode || nodeObj === state.rootObj) {
        nodeObj.culled = false;
      }

      if (nodeObj.culled) {
        hideNodeInstance(nodeObj);
      } else {
        setNodeMatrix(nodeObj, 1);
      }
    }

    let clusterSlot = 0;
    for (const clusterObj of state.activeClusters) {
      tempSphere.center.copy(clusterObj.pos);
      tempSphere.radius = clusterObj.radius;
      if (!frustum.intersectsSphere(tempSphere)) {
        clusterObj.renderVisible = false;
        continue;
      }
      if (clusterSlot >= CLUSTER_CAPACITY) {
        clusterObj.renderVisible = false;
        continue;
      }
      setClusterSlot(clusterSlot, clusterObj);
      clusterSlot += 1;
    }
    for (let i = clusterSlot; i < CLUSTER_CAPACITY; i += 1) {
      if (state.clusterBatch.clustersBySlot[i]) {
        hideClusterSlot(i);
      }
    }

    for (const edge of state.allEdges) {
      applyEdgeVisibility(edge);
    }

    state.renderDirty = false;
  }

  function refreshVisibility(force = false) {
    if (!state.clusterBatch) {
      return;
    }
    if (force) {
      state.forceFullRenderRefresh = true;
    }
    applyRenderVisibility();
    notifyCounts();
  }

  function updateDynamicInstances() {
    if (!state.clusterBatch) {
      return;
    }
    for (const nodeObj of state.allNodes) {
      if (nodeObj.animating && nodeObj.renderVisible && !nodeObj.clustered && !nodeObj.culled) {
        setNodeMatrix(nodeObj, 1);
      }
    }

    for (const edge of state.allEdges) {
      if (edge.active) {
        updateEdge(edge);
      }
    }

    for (const batch of state.nodeBatches.values()) {
      if (batch.dirty) {
        batch.mesh.instanceMatrix.needsUpdate = true;
        if (batch.mesh.instanceColor) {
          batch.mesh.instanceColor.needsUpdate = true;
        }
        batch.dirty = false;
      }
    }
    if (state.clusterBatch.dirty) {
      state.clusterBatch.mesh.instanceMatrix.needsUpdate = true;
      if (state.clusterBatch.mesh.instanceColor) {
        state.clusterBatch.mesh.instanceColor.needsUpdate = true;
      }
      state.clusterBatch.dirty = false;
    }
    if (state.edgeBatch.dirtyPositions) {
      state.edgeBatch.geometry.attributes.position.needsUpdate = true;
      state.edgeBatch.dirtyPositions = false;
    }
    if (state.edgeBatch.dirtyColors) {
      state.edgeBatch.geometry.attributes.color.needsUpdate = true;
      state.edgeBatch.dirtyColors = false;
    }
  }

  function animateNodes() {
    const now = performance.now();
    let anyAnimating = false;
    for (const nodeObj of state.allNodes) {
      if (!nodeObj.animating) {
        continue;
      }
      anyAnimating = true;
      const progress = Math.min((now - nodeObj.animStart) / 700, 1);
      const eased = 1 - (1 - progress) ** 4;
      nodeObj.pos.lerpVectors(nodeObj.animFrom, nodeObj.targetPos, eased);
      if (progress >= 1) {
        nodeObj.animating = false;
        nodeObj.pos.copy(nodeObj.targetPos);
      }
    }

    if (anyAnimating) {
      state.renderDirty = true;
    }
  }

  function applyFlyMovement() {
    if (!state.flyMode) {
      return;
    }

    const moveSpeed = Math.max(0.65, 1.8 / Math.max(state.zoom, 0.35));
    const forward = tempVecA.copy(state.camFocusTarget).sub(camera.position).normalize();
    const right = basisA.copy(forward).cross(camera.up).normalize();
    const worldUp = basisB.set(0, 1, 0);
    const delta = directionVec.set(0, 0, 0);

    if (state.keyState.KeyW) {
      delta.add(forward);
    }
    if (state.keyState.KeyS) {
      delta.sub(forward);
    }
    if (state.keyState.KeyD) {
      delta.add(right);
    }
    if (state.keyState.KeyA) {
      delta.sub(right);
    }
    if (state.keyState.KeyE) {
      delta.add(worldUp);
    }
    if (state.keyState.KeyQ) {
      delta.sub(worldUp);
    }

    if (delta.lengthSq() === 0) {
      return;
    }

    delta.normalize().multiplyScalar(moveSpeed);
    state.camFocusTarget.add(delta);
    state.renderDirty = true;
  }

  function animate() {
    requestAnimationFrame(animate);
    state.time += 0.008;
    state.frame += 1;

    flushPendingExpansions();

    state.rotX += (state.targetRotX - state.rotX) * 0.07;
    state.rotY += (state.targetRotY - state.rotY) * 0.07;
    state.zoom += (state.targetZoom - state.zoom) * 0.07;
    state.camFocus.lerp(state.camFocusTarget, 0.05);
    applyFlyMovement();

    const distance = CAMERA_DISTANCE / state.zoom;
    camera.position.x = distance * Math.sin(state.rotY) * Math.cos(state.rotX);
    camera.position.y = distance * Math.sin(state.rotX);
    camera.position.z = distance * Math.cos(state.rotY) * Math.cos(state.rotX);
    camera.lookAt(state.camFocus);
    camera.updateMatrixWorld();

    animateNodes();

    const cameraSignature = [
      camera.position.x.toFixed(2),
      camera.position.y.toFixed(2),
      camera.position.z.toFixed(2),
      state.camFocus.x.toFixed(2),
      state.camFocus.y.toFixed(2),
      state.camFocus.z.toFixed(2),
      state.zoom.toFixed(2),
    ].join("|");
    if (cameraSignature !== state.lastCameraSignature) {
      state.lastCameraSignature = cameraSignature;
      state.renderDirty = true;
    }

    if (state.clusterBatch && (state.renderDirty || state.forceFullRenderRefresh || state.frame % 4 === 0)) {
      applyRenderVisibility();
      state.forceFullRenderRefresh = false;
    }

    updateDynamicInstances();

    if (state.rootObj) {
      rootHalo.visible = true;
      rootHalo.position.copy(state.rootObj.pos);
      rootHalo.scale.setScalar(nodeRadiusForDepth(0) * (1.7 + Math.sin(state.time * 1.5) * 0.18));
    }
    if (selectionHalo.visible) {
      selectionHalo.material.opacity = 0.12 + Math.sin(state.time * 2.5) * 0.05;
    }

    particles.rotation.y = state.time * 0.015;
    particles.rotation.x = state.time * 0.006;
    lightA.position.x = Math.sin(state.time * 0.4) * 50;
    lightA.position.y = 120 + Math.cos(state.time * 0.3) * 30;

    renderer.render(scene, camera);
  }

  function handlePointerMove(event) {
    const dx = event.clientX - state.prevMouse.x;
    const dy = event.clientY - state.prevMouse.y;
    const dragDistance = Math.hypot(event.clientX - state.mouseDownPos.x, event.clientY - state.mouseDownPos.y);
    if (dragDistance > 3) {
      state.isDragging = true;
    }

    if (event.buttons === 1 && state.isDragging) {
      if (event.shiftKey && !state.flyMode) {
        const distance = CAMERA_DISTANCE / state.zoom;
        const forward = tempVecA.copy(state.camFocus).sub(camera.position).normalize();
        const right = basisA.copy(forward).cross(camera.up).normalize();
        const up = basisB.copy(camera.up).normalize();
        const panScale = distance * 0.0018;
        state.camFocusTarget.addScaledVector(right, -dx * panScale);
        state.camFocusTarget.addScaledVector(up, dy * panScale);
      } else {
        state.targetRotY += dx * 0.004;
        state.targetRotX += dy * 0.004;
        state.targetRotX = Math.max(-Math.PI / 2.1, Math.min(Math.PI / 2.1, state.targetRotX));
      }
      state.renderDirty = true;
    }
    state.prevMouse = { x: event.clientX, y: event.clientY };

    const hit = getHit(event);
    onHover(hit ? { node: hit, x: event.clientX, y: event.clientY } : null);
  }

  function attachEvents() {
    canvas.addEventListener("mousedown", (event) => {
      state.isDragging = false;
      state.mouseDownPos = { x: event.clientX, y: event.clientY };
      state.prevMouse = { x: event.clientX, y: event.clientY };
      document.body.classList.add("dragging");
    });

    canvas.addEventListener("mousemove", handlePointerMove);

    canvas.addEventListener("mouseup", (event) => {
      document.body.classList.remove("dragging");
      if (state.isDragging) {
        return;
      }
      const hit = getHit(event);
      if (hit) {
        if (hit.isCluster) {
          state.camFocusTarget.copy(hit.pos);
          state.targetZoom = Math.min(3.5, Math.max(state.targetZoom, 1.15));
        }
        setSelectedNode(hit);
      }
    });

    canvas.addEventListener(
      "wheel",
      (event) => {
        state.targetZoom *= event.deltaY > 0 ? 1.1 : 0.9;
        state.targetZoom = Math.max(0.28, Math.min(10, state.targetZoom));
        state.renderDirty = true;
        event.preventDefault();
      },
      { passive: false },
    );

    canvas.addEventListener("touchstart", (event) => {
      const touch = event.touches[0];
      state.prevMouse = { x: touch.clientX, y: touch.clientY };
    });

    canvas.addEventListener(
      "touchmove",
      (event) => {
        const touch = event.touches[0];
        const dx = touch.clientX - state.prevMouse.x;
        const dy = touch.clientY - state.prevMouse.y;
        state.targetRotY += dx * 0.004;
        state.targetRotX += dy * 0.004;
        state.prevMouse = { x: touch.clientX, y: touch.clientY };
        state.renderDirty = true;
        event.preventDefault();
      },
      { passive: false },
    );

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      state.renderDirty = true;
    });

    window.addEventListener("keydown", (event) => {
      if (event.code in state.keyState) {
        state.keyState[event.code] = true;
      }
    });

    window.addEventListener("keyup", (event) => {
      if (event.code in state.keyState) {
        state.keyState[event.code] = false;
      }
    });
  }

  function loadData(data) {
    state.data = data;
    state.searchIndex = [];
    state.depthTotals.clear();
    state.relationships = [];
    state.relationshipIndex = new Map();
    state.connectedRelationshipKeys.clear();
    const meta = registerDataNode(data);
    state.totalNodeCount = meta.subtreeCount;
    state.maxDataDepth = Math.min(data.__meta.maxDepth, MAX_DEPTH);
    state.maxNodes = MAX_NODES;
    state.maxVisibleDepth = MAX_DEPTH;

    ensureNodeBatches();
    indexRelationships(data.relationships || []);

    state.rootObj = createNodeObj(data, null, 0);
    setNodeColor(state.rootObj);
    state.rootObj.pos.set(0, 0, 0);
    state.rootObj.targetPos.set(0, 0, 0);
    setNodeMatrix(state.rootObj, 1);
    markVisible(state.rootObj);
    connectRelationshipsForNode(state.rootObj);
    rootHalo.visible = true;
    setSelectedNode(state.rootObj);
    refreshVisibility(true);
    return state.rootObj;
  }

  attachEvents();
  animate();

  return {
    loadData,
    expandNode,
    expandNodesBatch,
    collapseNode,
    pruneDistantNodes,
    estimateExpansionSize,
    revealNodeById,
    setSelectedNode,
    setDepthFilter,
    getFrontier,
    refreshVisibility,
    focusSelectedNode() {
      if (state.selectedNode) {
        state.camFocusTarget.copy(state.selectedNode.pos);
        state.targetZoom = Math.max(state.targetZoom, 1.45);
      }
    },
    setFlyMode(enabled) {
      state.flyMode = Boolean(enabled);
      if (state.flyMode) {
        state.targetZoom = Math.max(state.targetZoom, 1.6);
      }
      return state.flyMode;
    },
    isFlyMode() {
      return state.flyMode;
    },
    getNodeById(id) {
      return state.nodeMap.get(id) || null;
    },
    getSelectedNode() {
      return state.selectedNode;
    },
    getRootNode() {
      return state.rootObj;
    },
    getSearchIndex() {
      return state.searchIndex;
    },
    getStats() {
      return {
        visibleNodeCount: state.visibleNodeCount,
        totalNodeCount: state.totalNodeCount,
        maxDataDepth: state.maxDataDepth,
        maxVisibleDepth: state.maxVisibleDepth,
        maxNodes: state.maxNodes,
        pendingExpansions: state.pendingExpansions.length,
      };
    },
    getMaxDataDepth() {
      return state.maxDataDepth;
    },
    hasPendingExpansions() {
      return state.pendingExpansions.length > 0;
    },
    getConfig() {
      return {
        MAX_NODES,
        MAX_DEPTH,
      };
    },
  };
}
