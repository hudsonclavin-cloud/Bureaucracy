import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { createLodManager } from "./lodManager.js?v=20260312a";

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const CAMERA_DISTANCE = 280;
const HIDDEN_OFFSET = 1e8;
const MAX_VISIBLE_NODES = 25000;
const MAX_DEPTH = 20;
const MAX_BATCH = 200;
const NODE_RADIUS = 4;
const NODE_OPACITY = 0.92;
const EXPANSION_TIME_BUDGET_MS = 8;
const EXPANSION_CHILD_BUDGET = MAX_BATCH;
const EXPANSION_PARENT_BATCH = MAX_BATCH;
const CLUSTER_CAPACITY = 16384;
const CLUSTER_LABEL_CAPACITY = 256;
const MIN_CLUSTER_DISTANCE = 6;
const REPULSION = -60;
const LINK_DISTANCE = 30;
const DAMPING = 0.9;
const MIN_DISTANCE = 5;
const OUTWARD_FORCE = 0.02;
const BASE_RADIUS = 16;
const RADIUS_STEP = 40;
const SPHERE_RADIUS_SPACING = 18;
const SHELL_CAPACITIES = [32, 64, 128];
const SHELL_GAP_MULTIPLIER = 1.55;
const SHELL_BRANCH_HINT_BLEND = 0.12;
const DEEP_SHELL_BRANCH_HINT_BLEND = 0.01;
const SHELL_ANCHOR_RESTORE = 0.12;
const BRANCH_RELAXATION_ITERATIONS = 5;
const BRANCH_SECTOR_BASE_DISTANCE = 88;
const BRANCH_SECTOR_SPACING = 16;
const BRANCH_SECTOR_BLEND = 0.62;
const BRANCH_PARENT_BLEND = 0.32;
const BRANCH_FORCE = 0.018;
const FLY_TURN_MULTIPLIER = 3;
const FLY_MOVE_SPEED = 120;
const FLY_LOOK_DISTANCE = 42;
const FLY_PITCH_LIMIT = Math.PI / 2.15;
const FLY_DAMPING = 0.85;
const FLY_MAX_SPEED = 160;
const MIN_ZOOM_NODE_SCALE = 0.35;
const ORBIT_CAMERA_LERP = 0.08;
const DENSITY_BUCKET_BUFFER = 1;
const ALWAYS_VISIBLE_CLUSTER_NAMES = new Set([
  "constitution",
  "legislative branch",
  "executive branch",
  "judicial branch",
]);
const branchColors = {
  constitution: "#c8a84a",
  legislative: "#8a4ac8",
  executive: "#c84a4a",
  judicial: "#4a8ac8",
  independent: "#4ac88a",
  regulatory: "#c8884a",
  position: "#888888",
};
const branchSectorDirections = {
  constitution: new THREE.Vector3(0, 0, 0),
  legislative: new THREE.Vector3(-1, 0, 0).normalize(),
  executive: new THREE.Vector3(1, 0, 0).normalize(),
  judicial: new THREE.Vector3(0, 1, 0).normalize(),
  independent: new THREE.Vector3(0, -1, 0).normalize(),
  regulatory: new THREE.Vector3(0, 0, 1).normalize(),
  position: new THREE.Vector3(0, 0, -1).normalize(),
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
  const lodManager = createLodManager({ maxDepth: MAX_DEPTH });

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
  const particlePositions = new Float32Array(2000 * 3);
  for (let i = 0; i < 2000; i += 1) {
    const index = i * 3;
    particlePositions[index] = (Math.random() - 0.5) * 2200;
    particlePositions[index + 1] = (Math.random() - 0.5) * 2200;
    particlePositions[index + 2] = (Math.random() - 0.5) * 2200;
  }
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({ color: 0xe8eef8, size: 0.5, transparent: true, opacity: 0.32 }),
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

  const rootCore = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshStandardMaterial({
      color: 0xc8a84a,
      emissive: 0xc8a84a,
      emissiveIntensity: 0.55,
      roughness: 0.28,
      metalness: 0.08,
      transparent: true,
      opacity: 0.96,
    }),
  );
  rootCore.visible = false;
  scene.add(rootCore);

  const pathGlowGeometry = new THREE.SphereGeometry(1, 14, 14);
  const pathGlowPool = Array.from({ length: MAX_DEPTH + 8 }, () => {
    const mesh = new THREE.Mesh(
      pathGlowGeometry,
      new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.28,
      }),
    );
    mesh.visible = false;
    scene.add(mesh);
    return mesh;
  });

  const raycaster = new THREE.Raycaster();
  raycaster.params.Points.threshold = 6;
  const mouse2d = new THREE.Vector2();
  const frustum = new THREE.Frustum();
  const projectionMatrix = new THREE.Matrix4();
  const upVector = new THREE.Vector3(0, 1, 0);
  const basisA = new THREE.Vector3();
  const basisB = new THREE.Vector3();
  const directionVec = new THREE.Vector3();
  const tempVecA = new THREE.Vector3();
  const tempVecB = new THREE.Vector3();
  const tempVecC = new THREE.Vector3();
  const tempVecD = new THREE.Vector3();
  const tempMat4 = new THREE.Matrix4();
  const tempQuat = new THREE.Quaternion();
  const tempQuatB = new THREE.Quaternion();
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
  const whiteColor = new THREE.Color(0xffffff);
  const desiredCameraPosition = new THREE.Vector3();
  const edgeUpdateRange = { offset: Infinity, count: 0 };

  const state = {
    data: null,
    rootObj: null,
    selectedNode: null,
    totalNodeCount: 0,
    maxDataDepth: 0,
    maxNodes: 0,
    maxVisibleDepth: MAX_DEPTH,
    manualDepthFilter: MAX_DEPTH,
    nodeMap: new Map(),
    dataMap: new Map(),
    parentIdById: new Map(),
    searchIndex: [],
    depthTotals: new Map(),
    batchTotals: new Map(),
    nodeBatches: new Map(),
    nodeRenderMap: new Map(),
    clusterBatch: null,
    clusterLabels: [],
    haloMeshes: [],
    haloLabels: [],
    edgeBatch: null,
    allNodes: [],
    allEdges: [],
    visibleNodes: [],
    visibleNodeCount: 0,
    screenSpaceBuckets: new Map(),
    activeClusters: [],
    clusterMap: new Map(),
    pendingExpansions: [],
    relationships: [],
    relationshipIndex: new Map(),
    connectedRelationshipKeys: new Set(),
    highlightedPathNodes: [],
    highlightedPathIds: new Set(),
    highlightedPathEdgeSlots: new Set(),
    hoveredNode: null,
    highlightVersion: 0,
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
    lod: lodManager.updateLOD({
      cameraDistance: CAMERA_DISTANCE,
      rootNode: null,
      maxDepthFilter: MAX_DEPTH,
    }),
    time: 0,
    frame: 0,
    lastFrameTime: performance.now(),
    renderDirty: false,
    forceFullRenderRefresh: true,
    lastCameraSignature: "",
    flyMode: false,
    flyPosition: new THREE.Vector3(),
    flyVelocity: new THREE.Vector3(),
    flyLookTarget: new THREE.Vector3(),
    flyYaw: 0,
    flyPitch: 0,
    flyYawTarget: 0,
    flyPitchTarget: 0,
    lastUserDrillAt: 0,
    showUnverifiedNodes: true,
    showCandidateNodes: false,
    candidateNodes: [],
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
    const loadedDisplayNodeCount = state.visibleNodes.reduce(
      (count, nodeObj) => count + (shouldDisplayNodeByVerification(nodeObj.data) ? 1 : 0),
      0,
    );
    const eligibleTotalNodeCount = Array.from(state.dataMap.values()).reduce(
      (count, dataNode) => count + (shouldDisplayNodeByVerification(dataNode) ? 1 : 0),
      0,
    );
    const candidateNodeCount = state.candidateNodes.length;
    const hiddenCandidateCount = state.showCandidateNodes ? 0 : candidateNodeCount;
    onCountsChange({
      visibleNodeCount: state.visibleNodeCount,
      totalNodeCount: state.totalNodeCount,
      loadedDisplayNodeCount,
      eligibleTotalNodeCount,
      candidateNodeCount,
      hiddenCandidateCount,
      maxDataDepth: state.maxDataDepth,
      maxVisibleDepth: state.maxVisibleDepth,
      manualDepthFilter: state.manualDepthFilter,
      maxNodes: state.maxNodes,
      pendingExpansions: state.pendingExpansions.length,
      lodLevel: state.lod.level,
      lodLabel: state.lod.label,
      cameraDistance: state.lod.cameraDistance,
      densityHiddenNodeCount: state.lod.densityHiddenNodeCount || 0,
      showUnverifiedNodes: state.showUnverifiedNodes,
      showCandidateNodes: state.showCandidateNodes,
    });
  }

  function hexToInt(hex) {
    return parseInt((hex || "#888888").replace("#", ""), 16);
  }

  function inferBranchKey(data) {
    const id = String(data?.id || "").toLowerCase();
    const type = String(data?.type || "").toLowerCase();
    const name = String(data?.name || "").toLowerCase();

    if (type.includes("constitution") || name.includes("constitution") || id === "constitution" || id.startsWith("const")) {
      return "constitution";
    }
    if (
      id.startsWith("leg-") ||
      id.startsWith("legislative-") ||
      name.includes("legislative branch") ||
      name.includes("congress") ||
      name.includes("house of representatives") ||
      name.includes("senate")
    ) {
      return "legislative";
    }
    if (
      id.startsWith("jud-") ||
      id.startsWith("judicial-") ||
      name.includes("judicial branch") ||
      name.includes("supreme court") ||
      name.includes("federal judiciary") ||
      type.includes("court")
    ) {
      return "judicial";
    }
    if (
      id.startsWith("exec-regulatory") ||
      type.includes("regulatory") ||
      type.includes("commission") ||
      name.includes("regulatory") ||
      name.includes("commission")
    ) {
      return "regulatory";
    }
    if (
      id.startsWith("exec-ind") ||
      id === "exec-independent" ||
      name.includes("independent") ||
      type.includes("government corporation") ||
      type.includes("independent")
    ) {
      return "independent";
    }
    if (
      id.startsWith("exec-") ||
      id.startsWith("executive-") ||
      name.includes("executive branch") ||
      name.includes("department of ") ||
      type.includes("department") ||
      type.includes("cabinet") ||
      type.includes("agency") ||
      type.includes("bureau")
    ) {
      return "executive";
    }
    if (type === "position" || type.includes("office") || type.includes("officer") || type.includes("division")) {
      return "position";
    }
    return "position";
  }

  function resolveLayoutBranchKey(data, parentBranchKey = null) {
    const branchKey = inferBranchKey(data);
    if (branchKey === "position" && parentBranchKey && parentBranchKey !== "constitution") {
      return parentBranchKey;
    }
    return branchKey;
  }

  function copyBranchBaseDirection(branchKey, out = new THREE.Vector3()) {
    out.copy(branchSectorDirections[branchKey] || branchSectorDirections.position);
    return out.normalize();
  }

  function getNodeColor(data) {
    if (typeof data?.color === "string" && data.color.length > 0) {
      return data.color;
    }

    return branchColors[inferBranchKey(data)] || branchColors.position;
  }

  function getBranchColor(branchKey) {
    return branchColors[branchKey] || branchColors.position;
  }

  function getVerificationStyleKey(data) {
    if (data?.isCandidate) {
      return "candidate";
    }
    const status = String(data?.verificationStatus || "verified").toLowerCase();
    if (status === "partial") {
      return "partial";
    }
    if (status === "unverified") {
      return "unverified";
    }
    return "verified";
  }

  function getVerificationBadgeColor(data) {
    const styleKey = getVerificationStyleKey(data);
    if (styleKey === "partial") {
      return "#d9b55e";
    }
    if (styleKey === "unverified") {
      return "#8e7d62";
    }
    if (styleKey === "candidate") {
      return "#9b8bbd";
    }
    return "#6fcf97";
  }

  function shouldDisplayNodeByVerification(data) {
    if (data?.isCandidate) {
      return state.showCandidateNodes;
    }
    if (state.showUnverifiedNodes) {
      return true;
    }
    return !(Number(data?.confidenceScore || 0) < 0.5 || String(data?.verificationStatus || "") === "unverified");
  }

  function normalizeClusterKey(value) {
    return String(value || "").trim().toLowerCase();
  }

  function getOrganizationClusterKind(data) {
    const type = normalizeClusterKey(data?.type);
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

  function getClusterCountLabel(clusterObj) {
    const count = clusterObj.count || 0;
    if (clusterObj.kind === "positions" || clusterObj.kind === "office") {
      return `${count} positions`;
    }
    return `${count} nodes`;
  }

  function createTextSprite() {
    const canvasEl = document.createElement("canvas");
    canvasEl.width = 512;
    canvasEl.height = 160;
    const context = canvasEl.getContext("2d");
    const texture = new THREE.CanvasTexture(canvasEl);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      depthTest: false,
    });
    const sprite = new THREE.Sprite(material);
    sprite.visible = false;
    sprite.renderOrder = 10;
    scene.add(sprite);
    return {
      sprite,
      canvas: canvasEl,
      context,
      texture,
      text: "",
      subtext: "",
    };
  }

  function createClusterLabelSprite() {
    return createTextSprite();
  }

  function createHaloLabelSprite() {
    return createTextSprite();
  }

  function ensureClusterLabelPool(count) {
    while (state.clusterLabels.length < Math.min(count, CLUSTER_LABEL_CAPACITY)) {
      state.clusterLabels.push(createClusterLabelSprite());
    }
  }

  function ensureHaloPool(count) {
    while (state.haloMeshes.length < count) {
      const halo = new THREE.Mesh(
        new THREE.RingGeometry(20, 25, 64),
        new THREE.MeshBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: 0.55,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      );
      halo.visible = false;
      halo.renderOrder = 8;
      scene.add(halo);
      state.haloMeshes.push(halo);
    }
    while (state.haloLabels.length < count) {
      state.haloLabels.push(createHaloLabelSprite());
    }
  }

  function drawTextBadge(label, title, subtitle, color, options = {}) {
    if (label.text === title && label.subtext === subtitle) {
      return;
    }

    const { context, canvas, texture } = label;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = options.fillStyle || "rgba(2, 4, 8, 0.84)";
    context.strokeStyle = options.strokeStyle || `${color}cc`;
    context.lineWidth = options.lineWidth || 3;
    context.beginPath();
    context.roundRect(6, 8, canvas.width - 12, canvas.height - 16, 28);
    context.fill();
    context.stroke();

    context.textAlign = "center";
    context.fillStyle = options.titleColor || "#f7f1dd";
    context.font = options.titleFont || "700 32px Georgia";
    context.fillText(title, canvas.width / 2, 64, canvas.width - 44);
    context.fillStyle = options.subtitleColor || color;
    context.font = options.subtitleFont || "600 24px Georgia";
    context.fillText(subtitle, canvas.width / 2, 108, canvas.width - 44);

    texture.needsUpdate = true;
    label.text = title;
    label.subtext = subtitle;
  }

  function drawClusterLabel(label, title, subtitle, color) {
    drawTextBadge(label, title, subtitle, color);
  }

  function drawHaloLabel(label, title, subtitle, color) {
    drawTextBadge(label, title, subtitle, color, {
      fillStyle: "rgba(2, 6, 12, 0.72)",
      strokeStyle: `${color}aa`,
      lineWidth: 2,
      titleFont: "700 34px Georgia",
      subtitleFont: "600 22px Georgia",
      subtitleColor: "#cfd8ea",
    });
  }

  function getLabelDistanceScale(worldPosition) {
    const distance = Math.max(camera.position.distanceTo(worldPosition), 1);
    return THREE.MathUtils.clamp(distance * 0.006, 0.5, 4);
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

  function getForwardFromAngles(yaw, pitch, out = new THREE.Vector3()) {
    out.set(
      Math.sin(yaw) * Math.cos(pitch),
      Math.sin(pitch),
      Math.cos(yaw) * Math.cos(pitch),
    );
    return out.normalize();
  }

  function shellRadiusForDepth(depth) {
    return BASE_RADIUS + depth * RADIUS_STEP + depth * depth * 6;
  }

  function childSphereRadius(parentObj, childCount) {
    const baseRadius = BASE_RADIUS + parentObj.depth * 10;
    return baseRadius + SPHERE_RADIUS_SPACING * Math.sqrt(Math.max(childCount, 1));
  }

  function topLevelBranchDistance(subtreeCount) {
    return BRANCH_SECTOR_BASE_DISTANCE + Math.sqrt(Math.max(subtreeCount, 1)) * BRANCH_SECTOR_SPACING;
  }

  function getShellCapacity(shellIndex) {
    if (shellIndex < SHELL_CAPACITIES.length) {
      return SHELL_CAPACITIES[shellIndex];
    }
    return SHELL_CAPACITIES[SHELL_CAPACITIES.length - 1] * (2 ** (shellIndex - SHELL_CAPACITIES.length + 1));
  }

  function buildChildShells(parentObj, childCount) {
    const shells = [];
    let remaining = childCount;
    let start = 0;
    let shellIndex = 0;
    const baseShellRadius = childSphereRadius(parentObj, childCount);
    const shellGap = Math.max(
      SPHERE_RADIUS_SPACING * SHELL_GAP_MULTIPLIER,
      12 + Math.sqrt(Math.max(childCount, 1)) * 2.4,
    );

    while (remaining > 0) {
      const capacity = getShellCapacity(shellIndex);
      const count = Math.min(remaining, capacity);
      shells.push({
        index: shellIndex,
        start,
        count,
        radius: baseShellRadius + shellIndex * shellGap,
      });
      remaining -= count;
      start += count;
      shellIndex += 1;
    }

    return shells;
  }

  function computeVisibleNodeBudget(cameraDistance) {
    const distance = Math.max(cameraDistance, 1);
    const normalizedDistance = THREE.MathUtils.clamp((distance - 140) / 1100, 0, 1);
    const farBudget = Math.max(5000, Math.floor(MAX_VISIBLE_NODES * 0.3));
    return Math.round(THREE.MathUtils.lerp(MAX_VISIBLE_NODES, farBudget, normalizedDistance));
  }

  function getNavigationDistance() {
    if (state.flyMode) {
      return Math.max(camera.position.distanceTo(state.flyLookTarget), 1);
    }
    return Math.max(camera.position.distanceTo(state.camFocus), 1);
  }

  function updateLodState() {
    const cameraDistance = getNavigationDistance();
    state.lod = lodManager.updateLOD({
      cameraDistance,
      rootNode: state.rootObj,
      maxDepthFilter: state.manualDepthFilter,
    });
    state.maxNodes = computeVisibleNodeBudget(cameraDistance);
    state.maxVisibleDepth = state.lod.visibleDepth;
    return state.lod;
  }

  function getProtectedNodeIds() {
    const protectedIds = new Set([state.rootObj?.data?.id].filter(Boolean));
    for (const nodeObj of state.visibleNodes) {
      const normalizedName = normalizeClusterKey(nodeObj.data?.name || nodeObj.data?.id);
      if (ALWAYS_VISIBLE_CLUSTER_NAMES.has(normalizedName)) {
        protectedIds.add(nodeObj.data.id);
      }
    }
    return protectedIds;
  }

  function projectWorldToScreen(position) {
    const width = renderer.domElement.clientWidth || window.innerWidth;
    const height = renderer.domElement.clientHeight || window.innerHeight;
    const projected = tempVecD.copy(position).project(camera);
    return {
      x: ((projected.x + 1) * 0.5) * width,
      y: ((1 - projected.y) * 0.5) * height,
      z: projected.z,
      width,
      height,
    };
  }

  function scoreNodeImportance(nodeObj, protectedIds, ancestorIds) {
    if (!nodeObj) {
      return -Infinity;
    }

    let score = 0;
    if (nodeObj === state.selectedNode) {
      score += 1_000_000;
    }
    if (nodeObj === state.hoveredNode) {
      score += 80_000;
    }
    if (ancestorIds.has(nodeObj.data.id)) {
      score += 300_000;
    }
    if (protectedIds.has(nodeObj.data.id)) {
      score += 250_000;
    }
    if (state.highlightedPathIds.has(nodeObj.data.id)) {
      score += 180_000;
    }
    if (nodeObj.depth <= 1) {
      score += 120_000;
    }
    if (nodeObj.isCandidate) {
      score -= 60_000;
    }
    score += Math.min(90_000, (nodeObj.data?.__meta?.subtreeCount || 1) * 4);
    score -= nodeObj.depth * 400;
    if (nodeObj.clusterRef) {
      score -= 2_000;
    }
    return score;
  }

  function computeScreenSpaceBuckets(nodeObjs, tileSize = state.lod.tileSize) {
    const buckets = new Map();
    for (const nodeObj of nodeObjs) {
      const screen = projectWorldToScreen(nodeObj.pos);
      nodeObj.screenX = screen.x;
      nodeObj.screenY = screen.y;
      nodeObj.screenZ = screen.z;
      if (screen.z < -1 || screen.z > 1) {
        continue;
      }
      const tileX = Math.floor(screen.x / tileSize);
      const tileY = Math.floor(screen.y / tileSize);
      const key = `${tileX}:${tileY}`;
      if (!buckets.has(key)) {
        buckets.set(key, []);
      }
      buckets.get(key).push(nodeObj);
    }
    return buckets;
  }

  function applyDensityCap(nodeObjs) {
    const protectedIds = getProtectedNodeIds();
    const ancestorIds = state.selectedNode?.isCluster ? new Set() : getAncestorIds(state.selectedNode);
    const buckets = computeScreenSpaceBuckets(nodeObjs);
    state.screenSpaceBuckets = buckets;
    const allowed = new Set();

    for (const nodeObj of nodeObjs) {
      nodeObj.importanceScore = scoreNodeImportance(nodeObj, protectedIds, ancestorIds);
    }

    for (const entries of buckets.values()) {
      entries.sort((a, b) => b.importanceScore - a.importanceScore);
      const limit = Math.max(1, state.lod.nodesPerTile);
      for (let i = 0; i < Math.min(entries.length, limit); i += 1) {
        allowed.add(entries[i].data.id);
      }
      for (const entry of entries) {
        if (entry.importanceScore >= 250_000) {
          allowed.add(entry.data.id);
        }
      }
    }

    let hiddenCount = 0;
    for (const nodeObj of nodeObjs) {
      const visible = allowed.has(nodeObj.data.id);
      nodeObj.densityCapped = !visible;
      if (!visible) {
        hiddenCount += 1;
      }
    }
    state.lod.densityHiddenNodeCount = hiddenCount;
  }

  function worldUnitsToPixels(position, widthWorld, heightWorld) {
    const width = renderer.domElement.clientWidth || window.innerWidth;
    const height = renderer.domElement.clientHeight || window.innerHeight;
    const distance = Math.max(camera.position.distanceTo(position), 1);
    const visibleHeight = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5)) * distance;
    const visibleWidth = visibleHeight * camera.aspect;
    return {
      width: (widthWorld / visibleWidth) * width,
      height: (heightWorld / visibleHeight) * height,
    };
  }

  function measureLabelBounds(sprite, priority = 0) {
    const screen = projectWorldToScreen(sprite.position);
    if (screen.z < -1 || screen.z > 1) {
      sprite.visible = false;
    }
    const size = worldUnitsToPixels(sprite.position, sprite.scale.x, sprite.scale.y);
    return {
      sprite,
      priority,
      left: screen.x - size.width * 0.5,
      right: screen.x + size.width * 0.5,
      top: screen.y - size.height * 0.5,
      bottom: screen.y + size.height * 0.5,
    };
  }

  function labelBoundsIntersect(a, b) {
    return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
  }

  function suppressOverlappingLabels(candidates) {
    const accepted = [];
    candidates.sort((a, b) => b.priority - a.priority);
    for (const candidate of candidates) {
      if (!candidate.sprite.visible) {
        continue;
      }
      const bounds = measureLabelBounds(candidate.sprite, candidate.priority);
      let blocked = false;
      for (const acceptedBounds of accepted) {
        if (labelBoundsIntersect(bounds, acceptedBounds)) {
          blocked = true;
          break;
        }
      }
      candidate.sprite.visible = !blocked;
      if (!blocked) {
        accepted.push(bounds);
      }
    }
  }

  function getClusterCollapseDistance(nodeObj) {
    return lodManager.getClusterPolicy(nodeObj, state.lod).collapseDistance;
  }

  function getClusterDescendantThreshold(nodeObj) {
    return lodManager.getClusterPolicy(nodeObj, state.lod).minDescendants;
  }

  function directionFromSeed(seedA, seedB = 0) {
    const thetaSeed = (seedA ^ (seedB * 2654435761)) >>> 0;
    const phiSeed = (seedA * 1597334677 + seedB * 3812015801) >>> 0;
    const theta = ((thetaSeed % 100000) / 100000) * Math.PI * 2;
    const phi = Math.acos((phiSeed % 200000) / 100000 - 1);

    return new THREE.Vector3(
      Math.sin(phi) * Math.cos(theta),
      Math.sin(phi) * Math.sin(theta),
      Math.cos(phi),
    );
  }

  function fibonacciSphereDirection(index, count, out = new THREE.Vector3()) {
    if (count <= 1) {
      return out.set(0, 1, 0);
    }
    const sample = (index + 0.5) / count;
    const y = 1 - sample * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * index;
    out.set(Math.cos(theta) * radius, y, Math.sin(theta) * radius);
    return out.normalize();
  }

  function syncFlyStateFromCamera() {
    camera.getWorldDirection(tempVecA);
    state.flyPosition.copy(camera.position);
    state.flyVelocity.set(0, 0, 0);
    state.flyLookTarget.copy(state.camFocus);
    state.flyYaw = Math.atan2(tempVecA.x, tempVecA.z);
    state.flyPitch = Math.asin(THREE.MathUtils.clamp(tempVecA.y, -0.999, 0.999));
    state.flyYawTarget = state.flyYaw;
    state.flyPitchTarget = state.flyPitch;
  }

  function syncOrbitStateFromFlyCamera() {
    const distance = CAMERA_DISTANCE / Math.max(state.zoom, 0.35);
    const forward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA);
    state.camFocus.copy(state.flyPosition).addScaledVector(forward, distance);
    state.camFocusTarget.copy(state.camFocus);

    const offset = tempVecB.copy(state.flyPosition).sub(state.camFocus);
    const offsetLength = Math.max(offset.length(), 0.0001);
    const nextRotX = Math.asin(THREE.MathUtils.clamp(offset.y / offsetLength, -1, 1));
    const nextRotY = Math.atan2(offset.x, offset.z);
    state.rotX = nextRotX;
    state.rotY = nextRotY;
    state.targetRotX = nextRotX;
    state.targetRotY = nextRotY;
    state.flyVelocity.set(0, 0, 0);
  }

  function updateFlyLookTarget() {
    getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA);
    state.flyLookTarget.copy(state.flyPosition).addScaledVector(tempVecA, FLY_LOOK_DISTANCE);
    state.camFocus.copy(state.flyLookTarget);
    state.camFocusTarget.copy(state.flyLookTarget);
  }

  function setFlyLookAt(target) {
    tempVecA.copy(target).sub(state.flyPosition);
    if (tempVecA.lengthSq() < 0.0001) {
      return;
    }
    tempVecA.normalize();
    state.flyYaw = Math.atan2(tempVecA.x, tempVecA.z);
    state.flyPitch = Math.asin(THREE.MathUtils.clamp(tempVecA.y, -0.999, 0.999));
    state.flyYawTarget = state.flyYaw;
    state.flyPitchTarget = state.flyPitch;
    state.flyLookTarget.copy(target);
    state.camFocus.copy(target);
    state.camFocusTarget.copy(target);
  }

  function stopFlyMovement() {
    state.flyVelocity.set(0, 0, 0);
    state.renderDirty = true;
  }

  function registerDataNode(node, parentId = null, depth = 0, path = []) {
    const nextPath = [...path, node.name];
    node.parent = parentId;
    node.depth = depth;
    state.dataMap.set(node.id, node);
    state.parentIdById.set(node.id, parentId);
    state.depthTotals.set(depth, (state.depthTotals.get(depth) || 0) + 1);
    const batchKey = `${depth}:${getNodeColor(node)}:${getVerificationStyleKey(node)}`;
    state.batchTotals.set(batchKey, (state.batchTotals.get(batchKey) || 0) + 1);
    state.searchIndex.push({
      id: node.id,
      name: node.name,
      type: node.type,
      color: node.color,
      verificationStatus: node.verificationStatus || "unverified",
      isCandidate: Boolean(node.isCandidate),
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

  function registerCandidateNode(node) {
    const depth = 1;
    node.parent = null;
    node.depth = depth;
    state.dataMap.set(node.id, node);
    state.parentIdById.set(node.id, null);
    state.depthTotals.set(depth, (state.depthTotals.get(depth) || 0) + 1);
    const batchKey = `${depth}:${getNodeColor(node)}:${getVerificationStyleKey(node)}`;
    state.batchTotals.set(batchKey, (state.batchTotals.get(batchKey) || 0) + 1);
    state.searchIndex.push({
      id: node.id,
      name: node.name,
      type: node.type,
      color: node.color,
      verificationStatus: "candidate",
      isCandidate: true,
      pathStr: node.possibleParent ? `Candidate › ${node.possibleParent}` : "Candidate",
    });
    node.__meta = {
      depth,
      subtreeCount: 1,
      maxDepth: depth,
      childCount: 0,
    };
  }

  function getVerificationMaterialProfile(styleKey, color) {
    const baseColor = new THREE.Color(color);
    if (styleKey === "partial") {
      return {
        color: baseColor.clone().lerp(whiteColor, 0.12),
        emissive: baseColor.clone().multiplyScalar(0.42),
        emissiveIntensity: 0.12,
        opacity: 0.64,
        wireframe: false,
      };
    }
    if (styleKey === "unverified") {
      return {
        color: baseColor.clone().lerp(whiteColor, 0.18),
        emissive: baseColor.clone().multiplyScalar(0.08),
        emissiveIntensity: 0.05,
        opacity: 0.2,
        wireframe: true,
      };
    }
    if (styleKey === "candidate") {
      return {
        color: baseColor.clone().lerp(whiteColor, 0.2),
        emissive: baseColor.clone().multiplyScalar(0.12),
        emissiveIntensity: 0.06,
        opacity: 0.16,
        wireframe: true,
      };
    }
    return {
      color: baseColor,
      emissive: baseColor.clone(),
      emissiveIntensity: 0.3,
      opacity: NODE_OPACITY,
      wireframe: false,
    };
  }

  function createNodeBatch(depth, color, styleKey, capacity) {
    const radius = nodeRadiusForDepth(depth);
    const geometry = new THREE.SphereGeometry(radius, depth <= 2 ? 16 : 10, depth <= 2 ? 16 : 10);
    const profile = getVerificationMaterialProfile(styleKey, color);
    const material = new THREE.MeshStandardMaterial({
      color: profile.color,
      emissive: profile.emissive,
      emissiveIntensity: profile.emissiveIntensity,
      roughness: 0.38,
      metalness: 0.05,
      transparent: true,
      opacity: profile.opacity,
      wireframe: profile.wireframe,
    });
    const mesh = new THREE.InstancedMesh(geometry, material, Math.max(capacity, 1));
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.frustumCulled = false;
    scene.add(mesh);
    return {
      depth,
      radius,
      color,
      styleKey,
      mesh,
      nodesBySlot: new Array(Math.max(capacity, 1)),
      nextSlot: 0,
      freeSlots: [],
      dirty: true,
    };
  }

  function ensureNodeBatches() {
    for (const [batchKey, count] of state.batchTotals) {
      const [depthText, color, styleKey] = batchKey.split(":");
      const depth = Number(depthText);
      state.nodeBatches.set(batchKey, createNodeBatch(depth, color, styleKey, count));
    }

    const clusterGeometry = new THREE.TorusGeometry(1, 0.18, 10, 28);
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
    const positionAttribute = new THREE.BufferAttribute(edgePositions, 3);
    const colorAttribute = new THREE.BufferAttribute(edgeColors, 3);
    positionAttribute.setUsage(THREE.DynamicDrawUsage);
    colorAttribute.setUsage(THREE.DynamicDrawUsage);
    edgeGeometry.setAttribute("position", positionAttribute);
    edgeGeometry.setAttribute("color", colorAttribute);
    edgeGeometry.setDrawRange(0, 0);
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x999999,
      transparent: true,
      opacity: 0.3,
      vertexColors: true,
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
      activeCount: 0,
      maxActiveSlot: -1,
      dirtyPositions: false,
      dirtyColors: false,
    };
  }

  function assignBatchSlot(nodeObj) {
    const batchKey = `${nodeObj.depth}:${getNodeColor(nodeObj.data)}:${getVerificationStyleKey(nodeObj.data)}`;
    const batch = state.nodeBatches.get(batchKey);
    nodeObj.batch = batch;
    nodeObj.slot = batch.freeSlots.length > 0 ? batch.freeSlots.pop() : batch.nextSlot++;
    batch.nodesBySlot[nodeObj.slot] = nodeObj;
  }

  function createNodeObj(data, parent, depth) {
    const layoutBranchKey = resolveLayoutBranchKey(data, parent?.layoutBranchKey || null);
    const nodeObj = {
      data,
      parent,
      depth,
      layoutBranchKey,
      branchDirection: new THREE.Vector3(),
      sectorDirection: new THREE.Vector3(),
      shellRadius: 0,
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
      resolvedColor: getNodeColor(data),
      isCandidate: Boolean(data?.isCandidate),
    };

    if (parent?.branchDirection?.lengthSq() > 0) {
      nodeObj.branchDirection.copy(parent.branchDirection);
    } else {
      copyBranchBaseDirection(layoutBranchKey, nodeObj.branchDirection);
    }
    if (parent?.sectorDirection?.lengthSq() > 0) {
      nodeObj.sectorDirection.copy(parent.sectorDirection);
    } else {
      copyBranchBaseDirection(layoutBranchKey, nodeObj.sectorDirection);
    }

    assignBatchSlot(nodeObj);
    state.nodeMap.set(data.id, nodeObj);
    state.nodeRenderMap.set(data.id, { mesh: nodeObj.batch.mesh, slot: nodeObj.slot });
    state.allNodes.push(nodeObj);
    return nodeObj;
  }

  function placeCandidateNode(nodeObj, index = 0) {
    const baseDistance = shellRadiusForDepth(1) + 30 + index * 2.4;
    const seed = hashString(nodeObj.data.id);
    const direction = directionFromSeed(seed, index + 1);
    nodeObj.pos.copy(direction).multiplyScalar(baseDistance);
    nodeObj.targetPos.copy(nodeObj.pos);
    nodeObj.branchDirection.copy(direction);
  }

  function syncCandidateVisibility() {
    for (const nodeObj of state.candidateNodes) {
      if (state.showCandidateNodes) {
        markVisible(nodeObj);
      } else {
        markHidden(nodeObj);
      }
    }
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
    const cameraDistance = Math.max(camera.position.distanceTo(nodeObj.pos), 1);
    const distanceScale = THREE.MathUtils.clamp(180 / cameraDistance, MIN_ZOOM_NODE_SCALE, 1);
    const zoomScale = Math.max(
      MIN_ZOOM_NODE_SCALE,
      lodManager.getNodeScale(cameraDistance, state.lod) * distanceScale,
    );
    const finalScale = scaleMultiplier * zoomScale;
    if (nodeObj === state.rootObj) {
      rootCore.visible = nodeObj.visible !== false;
      rootCore.position.copy(nodeObj.pos);
      rootCore.scale.setScalar(nodeRadiusForDepth(0) * 1.45);
      rootCore.material.color.set(getNodeColor(nodeObj.data));
      rootCore.material.emissive.set(getNodeColor(nodeObj.data));
    }
    tempMat4.compose(
      nodeObj.pos,
      tempQuat,
      tempScale.set(finalScale, finalScale, finalScale),
    );
    nodeObj.batch.mesh.setMatrixAt(nodeObj.slot, tempMat4);
    nodeObj.batch.dirty = true;
    nodeObj.renderVisible = finalScale > 0;
  }

  function setNodeColor(nodeObj) {
    nodeObj.resolvedColor = getNodeColor(nodeObj.data);
  }

  function relationshipKey(fromId, toId, type = "relationship") {
    return `${fromId}->${toId}:${type}`;
  }

  function createEdge(fromObj, toObj, options = {}) {
    const baseColor = new THREE.Color(hexToInt(options.color || "#aaaaaa"));
    const edge = {
      from: fromObj,
      to: toObj,
      slot: state.edgeBatch.freeSlots.length > 0 ? state.edgeBatch.freeSlots.pop() : state.edgeBatch.nextSlot++,
      active: false,
      baseColor,
      color: baseColor.clone(),
      highlightVersion: -1,
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

  function refreshEdgeColor(edge) {
    edge.color.copy(edge.baseColor);
    if (state.highlightedPathEdgeSlots.has(edge.slot)) {
      const highlightHex = edge.type === "hierarchy" ? getNodeColor(edge.to.data) : "#8fc2ff";
      edge.color.set(highlightHex).lerp(whiteColor, 0.18);
    }
  }

  function setEdgeColor(edge) {
    refreshEdgeColor(edge);
    edge.highlightVersion = state.highlightVersion;
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

  function markEdgeBatchRange(offset, count = 6) {
    edgeUpdateRange.offset = Math.min(edgeUpdateRange.offset, offset);
    edgeUpdateRange.count = Math.max(edgeUpdateRange.count, offset + count - edgeUpdateRange.offset);
  }

  function recomputeActiveEdgeRange() {
    let maxActiveSlot = -1;
    let activeCount = 0;
    for (const edge of state.allEdges) {
      if (!edge.active) {
        continue;
      }
      activeCount += 1;
      if (edge.slot > maxActiveSlot) {
        maxActiveSlot = edge.slot;
      }
    }
    state.edgeBatch.activeCount = activeCount;
    state.edgeBatch.maxActiveSlot = maxActiveSlot;
    state.edgeBatch.geometry.setDrawRange(0, Math.max(0, (maxActiveSlot + 1) * 2));
  }

  function updateEdge(edge) {
    const offset = edge.slot * 6;
    state.edgeBatch.positions[offset] = edge.from.pos.x;
    state.edgeBatch.positions[offset + 1] = edge.from.pos.y;
    state.edgeBatch.positions[offset + 2] = edge.from.pos.z;
    state.edgeBatch.positions[offset + 3] = edge.to.pos.x;
    state.edgeBatch.positions[offset + 4] = edge.to.pos.y;
    state.edgeBatch.positions[offset + 5] = edge.to.pos.z;
    markEdgeBatchRange(offset);
    state.edgeBatch.dirtyPositions = true;
    if (!edge.active) {
      edge.active = true;
      state.edgeBatch.activeCount += 1;
      if (edge.slot > state.edgeBatch.maxActiveSlot) {
        state.edgeBatch.maxActiveSlot = edge.slot;
        state.edgeBatch.geometry.setDrawRange(0, (state.edgeBatch.maxActiveSlot + 1) * 2);
      }
    }
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
    markEdgeBatchRange(offset);
    state.edgeBatch.dirtyPositions = true;
    if (edge.active) {
      edge.active = false;
      state.edgeBatch.activeCount = Math.max(0, state.edgeBatch.activeCount - 1);
      if (edge.slot === state.edgeBatch.maxActiveSlot) {
        recomputeActiveEdgeRange();
      }
    }
  }

  function applyEdgeVisibility(edge) {
    const zoomAllowed =
      edge.type === "relationship" ? state.lod.showRelationshipEdges : state.lod.showHierarchyEdges;
    if (edge.highlightVersion !== state.highlightVersion) {
      setEdgeColor(edge);
    }
    const show =
      zoomAllowed &&
      edge.from.renderVisible &&
      edge.to.renderVisible &&
      !edge.from.clustered &&
      !edge.to.clustered &&
      !edge.from.culled &&
      !edge.to.culled &&
      edge.from.depth < state.maxVisibleDepth &&
      edge.to.depth <= state.maxVisibleDepth;
    if (show) {
      updateEdge(edge);
    } else {
      hideEdge(edge);
    }
  }

  function updatePathGlowMeshes() {
    for (const glowMesh of pathGlowPool) {
      glowMesh.visible = false;
    }

    let glowIndex = 0;
    for (const nodeObj of state.highlightedPathNodes) {
      if (!nodeObj?.renderVisible || nodeObj.clustered || nodeObj.culled) {
        continue;
      }
      const glowMesh = pathGlowPool[glowIndex];
      if (!glowMesh) {
        break;
      }

      glowMesh.visible = true;
      glowMesh.position.copy(nodeObj.pos);
      glowMesh.scale.setScalar(nodeRadiusForDepth(nodeObj.depth) * (nodeObj === state.selectedNode ? 3.4 : 2.65));
      glowMesh.material.color.set(getNodeColor(nodeObj.data));
      glowMesh.material.opacity = nodeObj === state.selectedNode ? 0.38 : 0.24;
      glowIndex += 1;
    }
  }

  function relaxSiblingPositions(offsets, shellRadii, branchAnchors = [], branchMetadata = []) {
    for (let iteration = 0; iteration < BRANCH_RELAXATION_ITERATIONS; iteration += 1) {
      for (let i = 0; i < offsets.length; i += 1) {
        for (let j = i + 1; j < offsets.length; j += 1) {
          tempVecA.subVectors(offsets[i], offsets[j]);
          const distanceSq = tempVecA.lengthSq();
          const metaA = branchMetadata[i] || {};
          const metaB = branchMetadata[j] || {};
          const subtreeScaleA = Math.max(1, Math.sqrt(metaA.subtreeCount || 1));
          const subtreeScaleB = Math.max(1, Math.sqrt(metaB.subtreeCount || 1));
          const shellRadius = Math.max(shellRadii[i] || 0, shellRadii[j] || 0, MIN_DISTANCE);
          const baseDistance = Math.max(MIN_DISTANCE * 1.8, shellRadius * 0.18, NODE_RADIUS * 3.2);
          const branchBoost = metaA.branchKey === metaB.branchKey ? 0 : 1.2;
          const minimumDistance = baseDistance + (subtreeScaleA + subtreeScaleB) * 1.8 + branchBoost * 6;
          const minimumDistanceSq = minimumDistance * minimumDistance;
          if (distanceSq >= minimumDistanceSq) {
            continue;
          }

          if (distanceSq < 0.0001) {
            tempVecA.set(Math.sin(i + 1), Math.cos(j + 1), Math.sin(i + j + 1));
          }

          const distance = Math.sqrt(Math.max(distanceSq, 0.0001));
          const pushStrength = ((minimumDistance - distance) / minimumDistance) * (-REPULSION / 220);
          tempVecB.copy(offsets[i]).normalize();
          tempVecC.copy(offsets[j]).normalize();

          const pushI = tempVecD
            .copy(tempVecA)
            .sub(tempVecB.clone().multiplyScalar(tempVecA.dot(tempVecB)));
          if (pushI.lengthSq() < 0.0001) {
            pushI.copy(directionFromSeed(i + 1, j + 1));
          }
          pushI.normalize().multiplyScalar(pushStrength);
          offsets[i].add(pushI);

          const pushJ = basisA
            .copy(tempVecA)
            .negate()
            .sub(tempVecC.clone().multiplyScalar(tempVecA.clone().negate().dot(tempVecC)));
          if (pushJ.lengthSq() < 0.0001) {
            pushJ.copy(directionFromSeed(j + 1, i + 1));
          }
          pushJ.normalize().multiplyScalar(pushStrength);
          offsets[j].add(pushJ);
        }
      }

      for (let i = 0; i < offsets.length; i += 1) {
        const offset = offsets[i];
        const shellRadius = shellRadii[i] || MIN_DISTANCE;
        if (branchAnchors[i]?.lengthSq() > 0) {
          offset.lerp(branchAnchors[i], SHELL_ANCHOR_RESTORE);
        }
        offset.normalize().multiplyScalar(shellRadius);
      }
    }
  }

  function getShellOrientationQuaternion(parentObj, shellIndex) {
    const anchor = directionFromSeed(hashString(parentObj.data.id), shellIndex + parentObj.depth * 17 + 1);
    tempQuat.setFromUnitVectors(upVector, anchor);
    tempQuatB.setFromAxisAngle(
      anchor,
      (((hashString(parentObj.data.id) >>> 4) + shellIndex * 977) % 4096) / 4096 * Math.PI * 2,
    );
    return tempQuat.multiply(tempQuatB);
  }

  function getRootBranchPlacements(parentObj, children, parentBranchKey) {
    const placements = new Array(children.length);
    const groups = new Map();

    for (let i = 0; i < children.length; i += 1) {
      const childBranchKey = resolveLayoutBranchKey(children[i], parentBranchKey);
      if (!groups.has(childBranchKey)) {
        groups.set(childBranchKey, []);
      }
      groups.get(childBranchKey).push({ index: i, data: children[i] });
    }

    for (const [branchKey, group] of groups) {
      const sectorDirection = copyBranchBaseDirection(branchKey, tempVecA).clone();
      const largestSubtree = Math.max(...group.map(({ data }) => data.__meta?.subtreeCount || 1));
      const sectorCenter = tempVecB
        .copy(parentObj.pos)
        .addScaledVector(sectorDirection, topLevelBranchDistance(largestSubtree));
      const localRadius = group.length <= 1
        ? 0
        : Math.max(12, SPHERE_RADIUS_SPACING * 0.9 * Math.sqrt(group.length));
      const shellQuaternion = tempQuat.setFromUnitVectors(upVector, sectorDirection).clone();

      for (let localIndex = 0; localIndex < group.length; localIndex += 1) {
        const { index, data } = group[localIndex];
        let position = sectorCenter.clone();
        if (localRadius > 0) {
          position = sectorCenter
            .clone()
            .add(
              fibonacciSphereDirection(localIndex, group.length, tempVecC)
                .clone()
                .applyQuaternion(shellQuaternion)
                .multiplyScalar(localRadius),
            );
        }
        placements[index] = {
          position,
          direction: position.clone().sub(parentObj.pos).normalize(),
          sectorDirection: sectorDirection.clone(),
          shellRadius: position.distanceTo(parentObj.pos),
          layoutBranchKey: resolveLayoutBranchKey(data, parentBranchKey),
        };
      }
    }

    return placements;
  }

  function getSpreadPositions(parentObj, children) {
    const childCount = children.length;
    const parentBranchKey = parentObj.layoutBranchKey || inferBranchKey(parentObj.data);
    if (parentObj.depth === 0) {
      return getRootBranchPlacements(parentObj, children, parentBranchKey);
    }
    const shells = buildChildShells(parentObj, childCount);
    const offsets = new Array(childCount);
    const directions = new Array(childCount);
    const branchAnchors = new Array(childCount);
    const shellRadii = new Array(childCount);
    const branchMetadata = new Array(childCount);

    for (const shell of shells) {
      const shellQuaternion = getShellOrientationQuaternion(parentObj, shell.index).clone();

      for (let localIndex = 0; localIndex < shell.count; localIndex += 1) {
        const i = shell.start + localIndex;
        const childData = children[i];
        const childSeed = hashString(childData.id);
        const childBranchKey = resolveLayoutBranchKey(childData, parentBranchKey);
        const baseDirection = fibonacciSphereDirection(localIndex, shell.count, tempVecA).clone();
        const branchHint = copyBranchBaseDirection(childBranchKey, tempVecB).clone();
        const branchHintBlend = parentObj.depth <= 1 ? DEEP_SHELL_BRANCH_HINT_BLEND : 0;

        directionVec
          .copy(baseDirection)
          .applyQuaternion(shellQuaternion)
          .lerp(branchHint, branchHintBlend)
          .addScaledVector(directionFromSeed(childSeed, parentObj.depth + shell.index + 1), 0.035)
          .normalize();

        offsets[i] = directionVec.clone().multiplyScalar(shell.radius);
        directions[i] = directionVec.clone();
        branchAnchors[i] = offsets[i].clone();
        shellRadii[i] = shell.radius;
        branchMetadata[i] = {
          branchKey: childBranchKey,
          subtreeCount: childData.__meta?.subtreeCount || 1,
        };
      }
    }

    relaxSiblingPositions(offsets, shellRadii, branchAnchors, branchMetadata);
    return offsets.map((offset, index) => ({
      position: tempVecA.copy(parentObj.pos).add(offset).clone(),
      direction: offset.clone().normalize(),
      sectorDirection: parentObj.sectorDirection.clone(),
      shellRadius: shellRadii[index],
      layoutBranchKey: resolveLayoutBranchKey(children[index], parentBranchKey),
    }));
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
      placements: getSpreadPositions(parentObj, children),
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
      const { parentObj, children, placements, animate } = job;
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

      const placement = placements[job.index];
      const targetPos = placement.position;
      childObj.layoutBranchKey = placement.layoutBranchKey;
      childObj.branchDirection.copy(placement.direction);
      if (placement.sectorDirection?.lengthSq() > 0) {
        childObj.sectorDirection.copy(placement.sectorDirection);
      } else if (parentObj.sectorDirection.lengthSq() > 0) {
        childObj.sectorDirection.copy(parentObj.sectorDirection);
      } else {
        copyBranchBaseDirection(childObj.layoutBranchKey, childObj.sectorDirection);
      }
      childObj.shellRadius = placement.shellRadius || targetPos.distanceTo(parentObj.pos);
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
    state.nodeRenderMap.delete(nodeObj.data.id);
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
    if (!nodeObj) {
      return ancestorIds;
    }
    let cursor = nodeObj;
    while (cursor) {
      ancestorIds.add(cursor.data.id);
      cursor = cursor.parent;
    }
    return ancestorIds;
  }

  function traceOrigin(nodeObj) {
    const path = [];
    let current = nodeObj || null;
    while (current) {
      path.unshift(current);
      current = current.parent;
    }
    return path;
  }

  function setOriginTrace(pathNodes = []) {
    state.highlightedPathNodes = pathNodes.filter(Boolean);
    state.highlightedPathIds = new Set(state.highlightedPathNodes.map((nodeObj) => nodeObj.data.id));
    state.highlightedPathEdgeSlots = new Set();
    state.highlightVersion += 1;

    for (let i = 1; i < state.highlightedPathNodes.length; i += 1) {
      const child = state.highlightedPathNodes[i];
      if (child?.edgeToParent) {
        state.highlightedPathEdgeSlots.add(child.edgeToParent.slot);
      }
    }

    state.renderDirty = true;
    for (const edge of state.allEdges) {
      setEdgeColor(edge);
    }
  }

  function clearOriginTrace() {
    if (state.highlightedPathNodes.length === 0) {
      return;
    }
    state.highlightedPathNodes = [];
    state.highlightedPathIds = new Set();
    state.highlightedPathEdgeSlots = new Set();
    state.highlightVersion += 1;
    state.renderDirty = true;
    for (const edge of state.allEdges) {
      setEdgeColor(edge);
    }
  }

  function isProtectedFromClustering(nodeObj) {
    if (!nodeObj || nodeObj.isCandidate || nodeObj === state.rootObj || nodeObj === state.selectedNode) {
      return true;
    }
    const normalizedName = normalizeClusterKey(nodeObj.data?.name || nodeObj.data?.id);
    if (ALWAYS_VISIBLE_CLUSTER_NAMES.has(normalizedName)) {
      return true;
    }
    if (state.highlightedPathIds.has(nodeObj.data.id)) {
      return true;
    }
    if (!state.selectedNode || state.selectedNode.isCluster) {
      return false;
    }
    return isDescendantOf(nodeObj, state.selectedNode) || isDescendantOf(state.selectedNode, nodeObj);
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
    selectionHalo.material.color.set(getNodeColor(state.selectedNode.data));
    selectionHalo.visible = true;
    selectionHalo.position.copy(state.selectedNode.pos);
    selectionHalo.scale.setScalar(radius);
  }

  function activateCluster(clusterObj) {
    if (!clusterObj?.sourceNode) {
      setSelectedNode(clusterObj);
      return;
    }

    const sourceNode = clusterObj.sourceNode;
    if (state.flyMode) {
      setFlyLookAt(clusterObj.pos);
    } else {
      state.camFocusTarget.copy(clusterObj.pos);
      state.targetZoom = Math.max(state.targetZoom, 2.4);
    }

    if (!sourceNode.expanded && !sourceNode.expanding) {
      expandNode(sourceNode, true);
    }
    state.lastUserDrillAt = performance.now();
    setSelectedNode(sourceNode);
  }

  function setSelectedNode(nodeObj) {
    if (!nodeObj) {
      return;
    }

    state.selectedNode = nodeObj;
    state.lastUserDrillAt = performance.now();
    if (state.flyMode) {
      setFlyLookAt(nodeObj.pos);
    } else {
      state.camFocusTarget.copy(nodeObj.pos);
    }
    state.renderDirty = true;
    updateSelectionHalo();
    onSelect(nodeObj);
  }

  function setDepthFilter(depth) {
    state.manualDepthFilter = Number.isFinite(depth) ? Math.min(depth, MAX_DEPTH) : MAX_DEPTH;
    updateLodState();
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
    state.lastUserDrillAt = performance.now();
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

  function setPointerFromEvent(event) {
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    mouse2d.set(x, y);
    return rect;
  }

  function pickScreenSpaceHit(clientX, clientY, rect) {
    const pointerX = clientX - rect.left;
    const pointerY = clientY - rect.top;
    let bestNode = null;
    let bestNodeScore = Infinity;
    let bestCluster = null;
    let bestClusterScore = Infinity;

    for (const nodeObj of state.visibleNodes) {
      if (!nodeObj.renderVisible || nodeObj.clustered) {
        continue;
      }
      tempVecD.copy(nodeObj.pos).project(camera);
      if (tempVecD.z < -1 || tempVecD.z > 1) {
        continue;
      }

      const screenX = ((tempVecD.x + 1) * 0.5) * rect.width;
      const screenY = ((1 - tempVecD.y) * 0.5) * rect.height;
      const distanceToPointer = Math.hypot(screenX - pointerX, screenY - pointerY);
      const threshold = state.lod.pickRadius + nodeRadiusForDepth(nodeObj.depth) * 1.3;
      if (distanceToPointer > threshold) {
        continue;
      }

      const score = distanceToPointer + Math.max(0, tempVecD.z) * 8;
      if (score < bestNodeScore) {
        bestNodeScore = score;
        bestNode = nodeObj;
      }
    }

    for (const clusterObj of state.activeClusters) {
      if (!clusterObj.renderVisible) {
        continue;
      }
      tempVecD.copy(clusterObj.pos).project(camera);
      if (tempVecD.z < -1 || tempVecD.z > 1) {
        continue;
      }

      const screenX = ((tempVecD.x + 1) * 0.5) * rect.width;
      const screenY = ((1 - tempVecD.y) * 0.5) * rect.height;
      const distanceToPointer = Math.hypot(screenX - pointerX, screenY - pointerY);
      const threshold = state.lod.pickRadius + clusterObj.radius * 1.8;
      if (distanceToPointer > threshold) {
        continue;
      }

      const score = distanceToPointer + Math.max(0, tempVecD.z) * 8;
      if (score < bestClusterScore) {
        bestClusterScore = score;
        bestCluster = clusterObj;
      }
    }

    return bestNode || bestCluster || null;
  }

  function getHit(event, { allowScreenSpaceFallback = true } = {}) {
    if (!state.clusterBatch) {
      return null;
    }
    const rect = setPointerFromEvent(event);
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

    if (allowScreenSpaceFallback) {
      const screenHit = pickScreenSpaceHit(event.clientX, event.clientY, rect);
      if (screenHit) {
        return screenHit;
      }
    }

    return clusterFallback;
  }

  function updateFrustum() {
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    projectionMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(projectionMatrix);
  }

  function getClusterDisplayColor(members) {
    const counts = new Map();
    let dominantBranch = "position";
    let dominantCount = 0;

    for (const member of members) {
      const branchKey = member.layoutBranchKey || inferBranchKey(member.data);
      const nextCount = (counts.get(branchKey) || 0) + 1;
      counts.set(branchKey, nextCount);
      if (nextCount > dominantCount) {
        dominantCount = nextCount;
        dominantBranch = branchKey;
      }
    }

    return getBranchColor(dominantBranch);
  }

  function separateClusterCenters(clusters) {
    for (let iteration = 0; iteration < 2; iteration += 1) {
      for (let i = 0; i < clusters.length; i += 1) {
        for (let j = i + 1; j < clusters.length; j += 1) {
          const clusterA = clusters[i];
          const clusterB = clusters[j];
          tempVecA.subVectors(clusterA.targetPos, clusterB.targetPos);
          const minDistance = MIN_CLUSTER_DISTANCE + clusterA.targetRadius + clusterB.targetRadius;
          const distanceSq = tempVecA.lengthSq();
          if (distanceSq >= minDistance * minDistance) {
            continue;
          }

          if (distanceSq < 0.0001) {
            tempVecA.set(Math.sin(i + 1), Math.cos(j + 1), Math.sin(i + j + 1));
          }

          const distance = Math.sqrt(Math.max(distanceSq, 0.0001));
          const push = (minDistance - distance) * 0.5;
          tempVecA.normalize().multiplyScalar(push);
          clusterA.targetPos.add(tempVecA);
          clusterB.targetPos.sub(tempVecA);
        }
      }
    }
  }

  function collectVisibleClusterMembers(rootNode) {
    const members = [];
    const stack = [...rootNode.childObjs];
    while (stack.length > 0) {
      const current = stack.pop();
      if (!current || !current.visible || current.depth > state.maxVisibleDepth) {
        continue;
      }
      members.push(current);
      for (const child of current.childObjs) {
        stack.push(child);
      }
    }
    return members;
  }

  function markClusteredMembers(clusterObj) {
    clusterObj.sourceNode.clustered = true;
    clusterObj.sourceNode.clusterRef = clusterObj;
    for (const member of clusterObj.members) {
      member.clustered = true;
      member.clusterRef = clusterObj;
    }
  }

  function shouldCollapseBranchIntoCluster(nodeObj, clusteredRoots) {
    if (!nodeObj || !nodeObj.visible || nodeObj.depth > state.maxVisibleDepth) {
      return false;
    }
    if (clusteredRoots.has(nodeObj.data.id) || isProtectedFromClustering(nodeObj)) {
      return false;
    }

    const normalizedName = normalizeClusterKey(nodeObj.data?.name || nodeObj.data?.id);
    if (ALWAYS_VISIBLE_CLUSTER_NAMES.has(normalizedName)) {
      return false;
    }

    const childCount = nodeObj.data?.children?.length || 0;
    const descendantCount = Math.max(0, (nodeObj.data?.__meta?.subtreeCount || 1) - 1);
    if (childCount === 0 || descendantCount < getClusterDescendantThreshold(nodeObj)) {
      return false;
    }

    if (lodManager.shouldClusterNode(nodeObj, state.lod)) {
      return true;
    }

    const cameraDistance = camera.position.distanceTo(nodeObj.pos);
    return cameraDistance > getClusterCollapseDistance(nodeObj);
  }

  function getScreenDensityAtPosition(position) {
    const screen = projectWorldToScreen(position);
    const tileSize = state.lod.tileSize;
    const tileX = Math.floor(screen.x / tileSize);
    const tileY = Math.floor(screen.y / tileSize);
    let density = 0;
    for (let dx = -DENSITY_BUCKET_BUFFER; dx <= DENSITY_BUCKET_BUFFER; dx += 1) {
      for (let dy = -DENSITY_BUCKET_BUFFER; dy <= DENSITY_BUCKET_BUFFER; dy += 1) {
        const key = `${tileX + dx}:${tileY + dy}`;
        density += state.screenSpaceBuckets.get(key)?.length || 0;
      }
    }
    return density;
  }

  function computeClusterRadius(clusterObj, cameraDistance, screenDensity) {
    const count = Math.max(clusterObj.count || 0, 1);
    const base = clusterObj.kind === "positions" ? 4.4 : 5.6;
    const factor = clusterObj.kind === "agency" ? 0.34 : clusterObj.kind === "bureau" ? 0.3 : 0.26;
    const maxRadius = clusterObj.kind === "agency" ? 16 : 13;
    const densityBoost = Math.min(3.5, Math.sqrt(Math.max(screenDensity, 1)) * 0.16);
    const rawRadius = base + Math.min(maxRadius, Math.sqrt(count) * factor + densityBoost);
    const pixelFootprint = worldUnitsToPixels(clusterObj.pos, rawRadius * 2, rawRadius * 2).width;
    const maxPixelFootprint = clusterObj.kind === "positions" ? 72 : 92;
    const clampedRadius = pixelFootprint > maxPixelFootprint
      ? rawRadius * (maxPixelFootprint / Math.max(pixelFootprint, 1))
      : rawRadius;
    const tubeThickness = Math.min(0.42, 0.14 + Math.log10(count + 1) * 0.08);
    return {
      radius: Math.max(clusterObj.kind === "positions" ? 4.8 : 5.8, clampedRadius),
      tubeThickness,
    };
  }

  function createHierarchyCluster(nodeObj) {
    const key = `cluster-${nodeObj.data.id}`;
    let clusterObj = state.clusterMap.get(key);
    if (!clusterObj) {
      clusterObj = {
        key,
        id: key,
        isCluster: true,
        type: "cluster",
        pos: new THREE.Vector3(),
        displayPos: new THREE.Vector3(),
        targetPos: new THREE.Vector3(),
        radius: 1,
        displayRadius: 1,
        targetRadius: 1,
        renderVisible: false,
        slot: -1,
        members: [],
        children: [],
        data: {},
        sourceNode: nodeObj,
        parent: nodeObj.parent || null,
        depth: nodeObj.depth,
      };
      state.clusterMap.set(key, clusterObj);
    }

    const members = collectVisibleClusterMembers(nodeObj);
    const descendantCount = Math.max(0, (nodeObj.data?.__meta?.subtreeCount || 1) - 1);
    clusterObj.sourceNode = nodeObj;
    clusterObj.parent = nodeObj.parent || null;
    clusterObj.depth = nodeObj.depth;
    clusterObj.members = members;
    clusterObj.count = descendantCount;
    clusterObj.kind = getOrganizationClusterKind(nodeObj.data);
    clusterObj.children = (nodeObj.data.children || []).map((child) => child.id);
    clusterObj.color = getClusterDisplayColor([nodeObj, ...members]);
    clusterObj.targetPos.copy(nodeObj.pos);
    const radiusConfig = computeClusterRadius(
      clusterObj,
      camera.position.distanceTo(nodeObj.pos),
      getScreenDensityAtPosition(nodeObj.pos),
    );
    clusterObj.targetRadius = radiusConfig.radius;
    clusterObj.tubeThickness = radiusConfig.tubeThickness;
    if (clusterObj.displayRadius <= 1.01) {
      clusterObj.displayPos.copy(clusterObj.targetPos);
      clusterObj.displayRadius = clusterObj.targetRadius;
    } else {
      clusterObj.displayPos.lerp(clusterObj.targetPos, 0.24);
      clusterObj.displayRadius = THREE.MathUtils.lerp(clusterObj.displayRadius, clusterObj.targetRadius, 0.24);
    }
    clusterObj.pos.copy(clusterObj.displayPos);
    clusterObj.radius = clusterObj.displayRadius;
    clusterObj.lastSeenFrame = state.frame;
    clusterObj.data = {
      id: key,
      type: "cluster",
      name: nodeObj.data.name,
      desc: `Zoom in or click to expand ${nodeObj.data.name}.`,
      color: clusterObj.color,
      count: descendantCount,
      children: clusterObj.children,
      clusterLabel: `${nodeObj.data.name} (${descendantCount})`,
      clusterCountLabel: getClusterCountLabel(clusterObj),
      sourceId: nodeObj.data.id,
      sourceType: nodeObj.data.type,
      depth: nodeObj.depth,
      clusterReason: `Clustered because deeper levels are hidden at ${state.lod.label}.`,
      clusterTierLabel: state.lod.label,
      loadedBranchCount: nodeObj.childObjs.length,
    };
    return clusterObj;
  }

  function setClusterSlot(slot, clusterObj) {
    const scale = Math.max(2.4, clusterObj.displayRadius || clusterObj.radius);
    tempQuat.copy(camera.quaternion);
    tempMat4.compose(
      clusterObj.displayPos || clusterObj.pos,
      tempQuat,
      tempScale.set(scale, scale, Math.max(0.7, clusterObj.tubeThickness || 1)),
    );
    state.clusterBatch.mesh.setMatrixAt(slot, tempMat4);
    state.clusterBatch.mesh.setColorAt(
      slot,
      tempClusterColor.set(clusterObj.color || clusterColor).lerp(clusterAccentColor, 0.08),
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

  function updateClusterLabels() {
    ensureClusterLabelPool(state.activeClusters.length);
    const protectedIds = getProtectedNodeIds();
    const candidates = [];
    let labelIndex = 0;
    for (const clusterObj of state.activeClusters) {
      if (!clusterObj.renderVisible || labelIndex >= state.clusterLabels.length) {
        continue;
      }

      const label = state.clusterLabels[labelIndex];
      const title = clusterObj.data.clusterLabel || clusterObj.data.name;
      const subtitle = clusterObj.data.clusterCountLabel || getClusterCountLabel(clusterObj);
      drawClusterLabel(label, title, subtitle, clusterObj.color || "#d3c29a");
      label.sprite.visible = true;
      label.sprite.position.copy(clusterObj.pos);
      label.sprite.position.y += Math.max(8, clusterObj.radius + 5);
      const labelScale = getLabelDistanceScale(label.sprite.position);
      label.sprite.scale.set(28 * labelScale, 8.4 * labelScale, 1);
      let priority = clusterObj.count || 0;
      if (state.selectedNode?.data?.id === clusterObj.data.sourceId) {
        priority += 1_000_000;
      }
      if (protectedIds.has(clusterObj.data.sourceId)) {
        priority += 250_000;
      }
      if (state.highlightedPathIds.has(clusterObj.data.sourceId)) {
        priority += 150_000;
      }
      candidates.push({ sprite: label.sprite, priority });
      labelIndex += 1;
    }

    for (let i = labelIndex; i < state.clusterLabels.length; i += 1) {
      state.clusterLabels[i].sprite.visible = false;
    }
    return candidates;
  }

  function updateHaloNodes() {
    const haloCandidates = state.visibleNodes.filter(
      (nodeObj) => nodeObj.renderVisible && lodManager.shouldRenderHalo(nodeObj, state.lod),
    );
    ensureHaloPool(haloCandidates.length);
    const protectedIds = getProtectedNodeIds();
    const labelCandidates = [];

    for (let i = 0; i < haloCandidates.length; i += 1) {
      const nodeObj = haloCandidates[i];
      const haloMesh = state.haloMeshes[i];
      const haloLabel = state.haloLabels[i];
      const color = getNodeColor(nodeObj.data);
      const haloRadius = nodeObj.depth === 0 ? 24 : 20;
      haloMesh.visible = true;
      haloMesh.position.copy(nodeObj.pos);
      haloMesh.quaternion.copy(camera.quaternion);
      haloMesh.material.color.set(color);
      haloMesh.material.opacity = nodeObj === state.selectedNode ? 0.72 : 0.52;
      haloMesh.scale.setScalar(nodeObj.depth === 0 ? 1.22 : 1);

      drawHaloLabel(haloLabel, nodeObj.data.name, nodeObj.data.type || "Institution", color);
      haloLabel.sprite.visible = true;
      haloLabel.sprite.position.copy(nodeObj.pos);
      haloLabel.sprite.position.y += haloRadius + 14;
      const labelScale = getLabelDistanceScale(haloLabel.sprite.position);
      haloLabel.sprite.scale.set(22 * labelScale, 7 * labelScale, 1);
      let priority = 50_000;
      if (nodeObj === state.selectedNode) {
        priority += 1_000_000;
      }
      if (protectedIds.has(nodeObj.data.id)) {
        priority += 300_000;
      }
      if (state.highlightedPathIds.has(nodeObj.data.id)) {
        priority += 150_000;
      }
      labelCandidates.push({ sprite: haloLabel.sprite, priority });
    }

    for (let i = haloCandidates.length; i < state.haloMeshes.length; i += 1) {
      state.haloMeshes[i].visible = false;
    }
    for (let i = haloCandidates.length; i < state.haloLabels.length; i += 1) {
      state.haloLabels[i].sprite.visible = false;
    }
    return labelCandidates;
  }

  function recomputeClusters() {
    for (const nodeObj of state.visibleNodes) {
      nodeObj.clustered = false;
      nodeObj.clusterRef = null;
    }

    const nextClusters = [];
    const clusteredRoots = new Set();
    const candidates = [...state.visibleNodes].sort((a, b) => a.depth - b.depth);
    for (const nodeObj of candidates) {
      if (!shouldCollapseBranchIntoCluster(nodeObj, clusteredRoots)) {
        continue;
      }

      let ancestor = nodeObj.parent;
      let blockedByAncestorCluster = false;
      while (ancestor) {
        if (clusteredRoots.has(ancestor.data.id)) {
          blockedByAncestorCluster = true;
          break;
        }
        ancestor = ancestor.parent;
      }
      if (blockedByAncestorCluster) {
        continue;
      }

      const clusterObj = createHierarchyCluster(nodeObj);
      nextClusters.push(clusterObj);
      clusteredRoots.add(nodeObj.data.id);
      markClusteredMembers(clusterObj);
    }

    if (nextClusters.length > 1) {
      separateClusterCenters(nextClusters);
    }

    for (const clusterObj of state.activeClusters) {
      clusterObj.renderVisible = false;
    }
    state.activeClusters = nextClusters;

    for (const [key, clusterObj] of state.clusterMap) {
      if ((clusterObj.lastSeenFrame || 0) < state.frame - 8) {
        state.clusterMap.delete(key);
      }
    }
  }

  function visibleNodeBudgetExceeded() {
    return state.visibleNodeCount >= Math.min(state.maxNodes, state.lod.visibleNodeBudget);
  }

  function shouldAutoExpandAtCurrentTier(nodeObj) {
    if (!nodeObj || !state.lod.autoExpand || visibleNodeBudgetExceeded()) {
      return false;
    }
    if (state.lod.level <= 1) {
      return false;
    }
    if (!state.selectedNode || state.selectedNode === state.rootObj) {
      return false;
    }
    const focusTarget = state.selectedNode?.isCluster ? state.camFocusTarget : state.selectedNode?.pos || state.camFocusTarget;
    const focusDistance = focusTarget.distanceTo(nodeObj.pos);
    const recentlyDrilled = performance.now() - state.lastUserDrillAt < 4000;
    return recentlyDrilled && focusDistance <= state.lod.autoExpandDistance;
  }

  function ensureLodCoverage() {
    if (!state.rootObj || state.pendingExpansions.length > 8) {
      return;
    }
    if (visibleNodeBudgetExceeded()) {
      return;
    }

    const pending = [];
    const candidates = [...state.visibleNodes].sort((a, b) => a.depth - b.depth);
    for (const nodeObj of candidates) {
      if (
        nodeObj.depth >= state.maxVisibleDepth ||
        nodeObj.expanded ||
        nodeObj.expanding ||
        !shouldAutoExpandAtCurrentTier(nodeObj)
      ) {
        continue;
      }
      if ((nodeObj.data?.children || []).length === 0) {
        continue;
      }
      pending.push(nodeObj);
      if (pending.length >= 10) {
        break;
      }
    }

    if (pending.length > 0) {
      expandNodesBatch(pending, false);
    }
  }

  function applyRenderVisibility() {
    if (!state.clusterBatch) {
      return;
    }
    updateLodState();
    updateFrustum();
    state.screenSpaceBuckets = computeScreenSpaceBuckets(
      state.visibleNodes.filter(
        (nodeObj) => lodManager.shouldRenderNode(nodeObj, state.lod) && shouldDisplayNodeByVerification(nodeObj.data),
      ),
    );
    recomputeClusters();
    const baseEdgeOpacity = state.lod.level <= 1 ? 0.34 : state.zoom <= 1 ? 0.24 : 0.3;
    state.edgeBatch.lines.material.opacity =
      state.highlightedPathEdgeSlots.size > 0 ? Math.max(baseEdgeOpacity, 0.42) : baseEdgeOpacity;
    const nodeCandidates = [];

    for (const nodeObj of state.allNodes) {
      nodeObj.renderVisible = false;
      if (
        !lodManager.shouldRenderNode(nodeObj, state.lod) ||
        !shouldDisplayNodeByVerification(nodeObj.data) ||
        nodeObj.clustered
      ) {
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
      } else if (lodManager.shouldRenderHalo(nodeObj, state.lod)) {
        hideNodeInstance(nodeObj);
        nodeObj.renderVisible = true;
      } else {
        nodeCandidates.push(nodeObj);
        nodeObj.renderVisible = true;
      }
    }

    applyDensityCap(nodeCandidates);
    for (const nodeObj of nodeCandidates) {
      if (nodeObj.densityCapped && nodeObj !== state.selectedNode && nodeObj !== state.rootObj) {
        hideNodeInstance(nodeObj);
        continue;
      }
      setNodeMatrix(nodeObj, 1);
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

    const clusterLabelCandidates = updateClusterLabels();
    const haloLabelCandidates = updateHaloNodes();
    suppressOverlappingLabels([...clusterLabelCandidates, ...haloLabelCandidates]);

    for (const edge of state.allEdges) {
      applyEdgeVisibility(edge);
    }

    updatePathGlowMeshes();

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

    updatePathGlowMeshes();

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
      const attribute = state.edgeBatch.geometry.attributes.position;
      if (edgeUpdateRange.offset !== Infinity) {
        attribute.updateRange.offset = edgeUpdateRange.offset;
        attribute.updateRange.count = edgeUpdateRange.count;
      }
      attribute.needsUpdate = true;
      state.edgeBatch.dirtyPositions = false;
      edgeUpdateRange.offset = Infinity;
      edgeUpdateRange.count = 0;
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

  function applyWebForces() {
    if (state.frame % 2 !== 0) {
      return;
    }

    let updated = false;
    for (const nodeObj of state.visibleNodes) {
      if (nodeObj.depth === 0 || nodeObj.isCandidate || nodeObj.animating || !nodeObj.renderVisible || nodeObj.clustered) {
        continue;
      }

      if (!nodeObj.parent) {
        continue;
      }

      const desiredOffset =
        nodeObj.targetPos.lengthSq() > 0
          ? tempVecA.copy(nodeObj.targetPos).sub(nodeObj.parent.pos)
          : tempVecA.copy(nodeObj.pos).sub(nodeObj.parent.pos);
      if (desiredOffset.lengthSq() === 0) {
        continue;
      }

      const shellRadius = Math.max(
        LINK_DISTANCE,
        nodeObj.shellRadius || desiredOffset.length(),
      );
      const targetDirection = tempVecB.copy(desiredOffset).normalize();
      const currentOffset = tempVecC.copy(nodeObj.pos).sub(nodeObj.parent.pos);
      const currentDirection =
        currentOffset.lengthSq() > 0.0001
          ? currentOffset.normalize()
          : targetDirection;

      currentDirection.lerp(targetDirection, OUTWARD_FORCE).normalize();
      nodeObj.pos.copy(nodeObj.parent.pos).addScaledVector(currentDirection, shellRadius);

      tempVecD.subVectors(nodeObj.pos, nodeObj.parent.pos);
      if (tempVecD.lengthSq() > 0.0001) {
        tempVecD.normalize().multiplyScalar(shellRadius);
        nodeObj.pos.copy(nodeObj.parent.pos).add(tempVecD);
      }

      updated = true;
    }

    if (updated) {
      state.renderDirty = true;
    }
  }

  function applyFlyMovement(deltaSeconds) {
    if (!state.flyMode) {
      return;
    }

    state.flyYaw += (state.flyYawTarget - state.flyYaw) * 0.22;
    state.flyPitch += (state.flyPitchTarget - state.flyPitch) * 0.22;

    const forward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA);
    const right = tempVecB.crossVectors(forward, upVector).normalize();
    const worldUp = tempVecC.set(0, 1, 0);
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

    if (delta.lengthSq() > 0) {
      const moveSpeed = FLY_MOVE_SPEED * deltaSeconds * Math.max(0.7, 1 / Math.sqrt(Math.max(state.zoom, 0.35)));
      delta.normalize().multiplyScalar(moveSpeed);
      state.flyVelocity.add(delta);
      if (state.flyVelocity.length() > FLY_MAX_SPEED) {
        state.flyVelocity.setLength(FLY_MAX_SPEED);
      }
    } else {
      state.flyVelocity.multiplyScalar(FLY_DAMPING);
      if (state.flyVelocity.lengthSq() < 0.0001) {
        state.flyVelocity.set(0, 0, 0);
      }
    }

    if (state.flyVelocity.lengthSq() === 0) {
      updateFlyLookTarget();
      return;
    }

    state.flyPosition.add(state.flyVelocity);
    updateFlyLookTarget();
    state.renderDirty = true;
  }

  function animate() {
    requestAnimationFrame(animate);
    const now = performance.now();
    const deltaSeconds = Math.min((now - state.lastFrameTime) / 1000, 0.05) || 0.016;
    state.lastFrameTime = now;
    state.time += deltaSeconds * 0.5;
    state.frame += 1;

    flushPendingExpansions();

    state.rotX += (state.targetRotX - state.rotX) * 0.07;
    state.rotY += (state.targetRotY - state.rotY) * 0.07;
    state.zoom += (state.targetZoom - state.zoom) * 0.07;
    if (state.flyMode) {
      applyFlyMovement(deltaSeconds);
      camera.position.copy(state.flyPosition);
      camera.lookAt(state.flyLookTarget);
    } else {
      state.camFocus.lerp(state.camFocusTarget, 0.05);
      const distance = CAMERA_DISTANCE / state.zoom;
      desiredCameraPosition.set(
        state.camFocus.x + distance * Math.sin(state.rotY) * Math.cos(state.rotX),
        state.camFocus.y + distance * Math.sin(state.rotX),
        state.camFocus.z + distance * Math.cos(state.rotY) * Math.cos(state.rotX),
      );
      camera.position.lerp(desiredCameraPosition, ORBIT_CAMERA_LERP);
      camera.lookAt(state.camFocus);
    }
    camera.updateMatrixWorld();
    updateLodState();
    ensureLodCoverage();

    animateNodes();
    applyWebForces();

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
      rootCore.visible = true;
      rootCore.position.copy(state.rootObj.pos);
      rootCore.scale.setScalar(nodeRadiusForDepth(0) * (1.42 + Math.sin(state.time * 1.2) * 0.04));
      rootCore.material.opacity = state.selectedNode === state.rootObj ? 1 : 0.96;
      rootCore.material.emissiveIntensity = 0.5 + Math.sin(state.time * 1.4) * 0.06;
    }
    if (selectionHalo.visible) {
      selectionHalo.material.opacity = 0.12 + Math.sin(state.time * 2.5) * 0.05;
    }

    particles.position.copy(camera.position);
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
      if (state.flyMode) {
        state.flyYawTarget += dx * 0.004 * FLY_TURN_MULTIPLIER;
        state.flyPitchTarget = THREE.MathUtils.clamp(
          state.flyPitchTarget + dy * 0.004 * FLY_TURN_MULTIPLIER,
          -FLY_PITCH_LIMIT,
          FLY_PITCH_LIMIT,
        );
      } else if (event.shiftKey) {
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

    const hit = getHit(event, { allowScreenSpaceFallback: false });
    state.hoveredNode = hit?.isCluster ? hit.sourceNode || null : hit || null;
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

    function handleSelection(event) {
      document.body.classList.remove("dragging");
      if (state.isDragging) {
        return;
      }
      const hit = getHit(event, { allowScreenSpaceFallback: true });
      if (hit) {
        if (hit.isCluster) {
          activateCluster(hit);
          return;
        }
        setSelectedNode(hit);
      }
    }

    canvas.addEventListener("mouseup", handleSelection);
    canvas.addEventListener("click", handleSelection);

    canvas.addEventListener(
      "wheel",
      (event) => {
        if (state.flyMode) {
          const forward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA);
          const zoomStep = event.deltaY > 0 ? -16 : 16;
          state.flyPosition.addScaledVector(forward, zoomStep);
          updateFlyLookTarget();
        } else {
          state.targetZoom *= event.deltaY > 0 ? 1.1 : 0.9;
          state.targetZoom = Math.max(0.28, Math.min(10, state.targetZoom));
        }
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
        if (state.flyMode) {
          state.flyYawTarget += dx * 0.004 * FLY_TURN_MULTIPLIER;
          state.flyPitchTarget = THREE.MathUtils.clamp(
            state.flyPitchTarget + dy * 0.004 * FLY_TURN_MULTIPLIER,
            -FLY_PITCH_LIMIT,
            FLY_PITCH_LIMIT,
          );
        } else {
          state.targetRotY += dx * 0.004;
          state.targetRotX += dy * 0.004;
        }
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
      if (event.code === "Space" && state.flyMode) {
        stopFlyMovement();
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
    state.batchTotals.clear();
    state.candidateNodes = [];
    state.relationships = [];
    state.relationshipIndex = new Map();
    state.connectedRelationshipKeys.clear();
    const meta = registerDataNode(data);
    for (const candidateNode of data.candidateNodes || []) {
      registerCandidateNode(candidateNode);
    }
    state.totalNodeCount = meta.subtreeCount + (data.candidateNodes || []).length;
    state.maxDataDepth = Math.min(data.__meta.maxDepth, MAX_DEPTH);
    state.maxNodes = MAX_VISIBLE_NODES;
    state.manualDepthFilter = MAX_DEPTH;
    state.maxVisibleDepth = MAX_DEPTH;

    ensureNodeBatches();
    indexRelationships(data.relationships || []);

    state.rootObj = createNodeObj(data, null, 0);
    setNodeColor(state.rootObj);
    state.rootObj.layoutBranchKey = "constitution";
    copyBranchBaseDirection("constitution", state.rootObj.branchDirection);
    copyBranchBaseDirection("constitution", state.rootObj.sectorDirection);
    state.rootObj.pos.set(0, 0, 0);
    state.rootObj.targetPos.set(0, 0, 0);
    setNodeMatrix(state.rootObj, 1);
    markVisible(state.rootObj);
    connectRelationshipsForNode(state.rootObj);
    for (const [index, candidateData] of (data.candidateNodes || []).entries()) {
      const candidateObj = createNodeObj(candidateData, null, 1);
      setNodeColor(candidateObj);
      placeCandidateNode(candidateObj, index);
      setNodeMatrix(candidateObj, 1);
      state.candidateNodes.push(candidateObj);
    }
    syncCandidateVisibility();
    expandNode(state.rootObj, false);
    flushPendingExpansions(18, 4096);
    updateLodState();
    ensureLodCoverage();
    flushPendingExpansions(18, 4096);
    rootHalo.visible = true;
    rootHalo.material.color.set(getNodeColor(state.rootObj.data));
    rootCore.visible = true;
    rootCore.material.color.set(getNodeColor(state.rootObj.data));
    rootCore.material.emissive.set(getNodeColor(state.rootObj.data));
    setSelectedNode(state.rootObj);
    syncFlyStateFromCamera();
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
    setShowUnverifiedNodes(enabled) {
      state.showUnverifiedNodes = Boolean(enabled);
      state.renderDirty = true;
      refreshVisibility(true);
      return state.showUnverifiedNodes;
    },
    setShowCandidateNodes(enabled) {
      state.showCandidateNodes = Boolean(enabled);
      syncCandidateVisibility();
      state.renderDirty = true;
      refreshVisibility(true);
      return state.showCandidateNodes;
    },
    getFrontier,
    refreshVisibility,
    focusSelectedNode() {
      if (state.selectedNode) {
        state.lastUserDrillAt = performance.now();
        if (state.flyMode) {
          const focusPoint = state.selectedNode.pos;
          const backward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA).multiplyScalar(-Math.max(22, state.selectedNode.radius ? state.selectedNode.radius * 5 : 28));
          state.flyPosition.copy(focusPoint).add(backward);
          setFlyLookAt(focusPoint);
        } else {
          state.camFocusTarget.copy(state.selectedNode.pos);
          state.targetZoom = Math.max(state.targetZoom, 1.45);
        }
      }
    },
    setFlyMode(enabled) {
      const nextEnabled = Boolean(enabled);
      if (nextEnabled === state.flyMode) {
        return state.flyMode;
      }

      state.flyMode = nextEnabled;
      if (state.flyMode) {
        syncFlyStateFromCamera();
        stopFlyMovement();
        state.targetZoom = Math.max(state.targetZoom, 1.6);
      } else {
        syncOrbitStateFromFlyCamera();
        stopFlyMovement();
      }
      state.renderDirty = true;
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
    traceOrigin(nodeObj = state.selectedNode) {
      return traceOrigin(nodeObj);
    },
    setOriginTrace(pathNodes) {
      setOriginTrace(pathNodes);
    },
    clearOriginTrace() {
      clearOriginTrace();
    },
    getOriginTrace() {
      return [...state.highlightedPathNodes];
    },
    getRootNode() {
      return state.rootObj;
    },
    getSearchIndex() {
      return state.searchIndex;
    },
    getStats() {
      const loadedDisplayNodeCount = state.visibleNodes.reduce(
        (count, nodeObj) => count + (shouldDisplayNodeByVerification(nodeObj.data) ? 1 : 0),
        0,
      );
      const eligibleTotalNodeCount = Array.from(state.dataMap.values()).reduce(
        (count, dataNode) => count + (shouldDisplayNodeByVerification(dataNode) ? 1 : 0),
        0,
      );
      const candidateNodeCount = state.candidateNodes.length;
      return {
        visibleNodeCount: state.visibleNodeCount,
        totalNodeCount: state.totalNodeCount,
        loadedDisplayNodeCount,
        eligibleTotalNodeCount,
        candidateNodeCount,
        hiddenCandidateCount: state.showCandidateNodes ? 0 : candidateNodeCount,
        maxDataDepth: state.maxDataDepth,
        maxVisibleDepth: state.maxVisibleDepth,
        manualDepthFilter: state.manualDepthFilter,
        maxNodes: state.maxNodes,
        pendingExpansions: state.pendingExpansions.length,
        lodLevel: state.lod.level,
        lodLabel: state.lod.label,
        cameraDistance: state.lod.cameraDistance,
        densityHiddenNodeCount: state.lod.densityHiddenNodeCount || 0,
        showUnverifiedNodes: state.showUnverifiedNodes,
        showCandidateNodes: state.showCandidateNodes,
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
        MAX_VISIBLE_NODES,
        MAX_DEPTH,
      };
    },
  };
}
