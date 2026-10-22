import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { createLodManager } from "./lodManager.js?v=20261022a";

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const CAMERA_DISTANCE = 280;
const HIDDEN_OFFSET = 1e8;
//: Worth less than one place in the importance ordering's real terms (the
//: smallest of which, a depth step, is 400) so it settles flicker without
//: letting a node hold a tile against a genuinely more important one.
const DENSITY_STICKY_BONUS = 120;
//: Measured on the White House Office's 249-child brood, orbiting: at 8
//: frames 28 nodes toggled three or more times over 26 samples, at 20 it was
//: 16, at 40 it was 6 and at 80 it was none. The mean drawn count was 84, 86,
//: 87 and 87 across those runs, so the longer hold does not defeat the cap it
//: stabilises. A node leaving the SCREEN is frustum-culled regardless of this
//: hold; what lingers is only one that loses its tile while still on screen,
//: which is the thing that should not have vanished in the first place.
const DENSITY_HOLD_FRAMES = 80;
const MAX_NODES = 100000;
const MAX_DEPTH = 20;
const MAX_BATCH = 200;
const NODE_RADIUS = 4;
const NODE_OPACITY = 0.92;
const EXPANSION_TIME_BUDGET_MS = 8;
const EXPANSION_CHILD_BUDGET = MAX_BATCH;
const EXPANSION_PARENT_BATCH = MAX_BATCH;
const CLUSTER_CAPACITY = 16384;
const CLUSTER_LABEL_CAPACITY = 256;
// The selected node's own children are the brood a reader just asked to see;
// each gets a name badge, up to this many, before the overlap pass thins them.
const BROOD_LABEL_CAPACITY = 48;
// Everything outside the selection, its ancestors and its brood is tinted
// toward the ink so the brood reads as the subject and the rest as context.
// A tint is a selection state, never a fact about a node: the base colour
// and the size are untouched.
const FOCUS_DIM = new THREE.Color(0.4, 0.42, 0.46);
const FOCUS_FULL = new THREE.Color(1, 1, 1);
// A lens is a question, not a look. Each one changes which published field
// drives a node's colour (and, for Money alone, its size) and nothing about
// what the data says: the panel's rules still decide every figure, and a
// node with nothing to say under a lens is drawn dark rather than invented.
// Structure is the default and is exactly the branch-hue drawing above.
export const LENSES = ["structure", "money", "evidence", "pay", "whole"];
// The two sectors beneath the Executive that are drawn as their own masses,
// each in its own hue and out of the branches' plane.
const SECTOR_BRANCH_KEYS = new Set(["independent", "regulatory"]);
const SECTOR_ROOT_IDS = new Set(["exec-independent", "exec-regulatory"]);
const EXECUTIVE_RED = "#c84a4a";
// Whole: every node this graph carries, drawn at once in the branch hues,
// so the three branches read as three masses. The LOD tiers exist to keep
// a far camera from drawing 5,510 dots; this lens is the reader asking for
// exactly that, so clustering, the density cap and the depth tier are set
// aside and the node is drawn at one world size whatever the distance. A
// manual depth filter is an explicit choice and still wins. The caption
// under each branch halo says what the mass is — nodes in THIS graph,
// which is its depth of curation and not the government's size — beside
// the branch's measured figure, which is.
const WHOLE_LOD = Object.freeze({
  level: 4,
  label: "Whole Government",
  maxDepth: Infinity,
  showHierarchyEdges: true,
  showRelationshipEdges: false,
  showHalos: true,
  clusterHiddenDescendants: false,
  clusterPositionsOnly: false,
  pickRadius: 16,
  nodeScale: 1,
  tileSize: 84,
  nodesPerTile: 1_000_000,
  autoExpand: false,
  autoExpandDistance: 0,
  visibleNodeBudget: 1_000_000,
});
const WHOLE_NODE_SCALE = 1.5;
// The ordinary floor on zoom keeps the camera within 1,000 units; the whole
// tree is wider than that, so the Whole lens may pull back further.
const MIN_ZOOM = 0.28;
const WHOLE_MIN_ZOOM = 0.07;
const LENS_INK = "#2E3542";
// Evidence: verificationStatus, with the two states ui.js already tells
// apart from a bare "unverified" — never checked at all, and a host that
// refused the crawler (verificationUnread).
const EVIDENCE_COLORS = {
  verified: "#4FBF8C",
  partial: "#E0A83C",
  notFound: "#E06A4F",
  unread: "#9A86CF",
  noDocument: "#B7A9DC",
  unsourced: "#6E7079",
  treasuryLine: "#8AA0B0",
};
// Pay: the kind of claim the panel would head the post's figure with, in
// the order ui.js's PAY_STAND_IN_ORDER reads them. A unit has no salary and
// is drawn as context.
const PAY_COLORS = {
  office: "#EDD27E",
  incumbency: "#D4B25A",
  range: "#A8893F",
  notFederal: "#7A8A99",
  unpriced: "#5A5E66",
  unit: LENS_INK,
};
// Money: cost_status. An estimate takes a colour only when the reader has
// ticked "Also show estimated shares", the same opt-in the panel uses.
const MONEY_COLORS = {
  measured: "#EDD27E",
  receipts: "#8AA0B0",
  estimate: "#8C7A44",
  none: LENS_INK,
};
const MIN_CLUSTER_DISTANCE = 6;
const REPULSION = -60;
const LINK_DISTANCE = 30;
const DAMPING = 0.9;
const MIN_DISTANCE = 5;
const RELAXATION_MAX_SIBLINGS = 320;
const WEB_FORCE_SETTLE_EPSILON_SQ = 0.0001;
const OUTWARD_FORCE = 0.02;
const BASE_RADIUS = 16;
const RADIUS_STEP = 40;
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
  receipts: "#8a8aa8",
  position: "#666666",
};
const branchSectorDirections = {
  constitution: new THREE.Vector3(0, 1, 0.08).normalize(),
  // The three branches sit on an equilateral triangle in the screen plane
  // (90 / 210 / 330 degrees). Fanning them around the Constitution's own +Y axis
  // put the ring in the X-Z plane, which the camera flattens along Z: the
  // branches landed at y = +0.655 / +0.635 / +0.970, a 4.4:1 arc that read as a
  // horizontal line. The small +z tilt keeps them off a perfectly flat plane.
  legislative: new THREE.Vector3(-0.866, -0.5, 0.1).normalize(),
  executive: new THREE.Vector3(0.866, -0.5, 0.1).normalize(),
  judicial: new THREE.Vector3(0, 1, 0.1).normalize(),
  // Independent Establishments sits OUT of the screen plane, toward the
  // viewer, and the regulatory commissions behind it: both are the
  // Executive's (so offset toward its side, +x), and neither may lie in
  // the plane the three branches share. At (-0.46, -0.68, 0.57), blended
  // a third of the way toward the Executive, the unit landed under the
  // Constitution between the branches and swept across the Judiciary's
  // sector as a reader orbited.
  // Measured on the first try at (0.3, -0.22, 0.93): pointing almost
  // straight at the camera, the unit sat between the camera and the
  // focus and projected across the Constitution from the front. Tilted
  // onto the Executive's own side, it stays out of the plane and on the
  // Executive's half of the picture.
  independent: new THREE.Vector3(0.62, -0.28, 0.73).normalize(),
  regulatory: new THREE.Vector3(0.58, -0.54, -0.61).normalize(),
  // The government-wide receipts line the Treasury nets against Total
  // Outlays sits beside the three branches, below the Constitution.
  receipts: new THREE.Vector3(0, -1, 0.1).normalize(),
  position: new THREE.Vector3(-0.14, 0.18, 0.97).normalize(),
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
  renderer.setClearColor(0x0a0e14, 1); // the shell's ink ground (css/shell.css --ink)
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
  const inkColor = new THREE.Color(0x0a0e14);
  const desiredCameraPosition = new THREE.Vector3();

  const state = {
    data: null,
    rootObj: null,
    selectedNode: null,
    totalNodeCount: 0,
    candidateNodeCount: 0,
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
    broodLabels: [],
    focusIds: new Set(),
    focusKey: "",
    lens: "structure",
    showEstimateFigures: false,
    wholeLayoutApplied: false,
    lastInteractionAt: 0,
    edgeBatch: null,
    allNodes: new Set(),
    allEdges: new Set(),
    visibleNodes: new Set(),
    visibleNodeCount: 0,
    drawnNodeCount: 0,
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
    orbitPosition: new THREE.Vector3(0, 0, CAMERA_DISTANCE),
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
    showSupersededNodes: false,
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
    onCountsChange({
      visibleNodeCount: state.visibleNodeCount,
      drawnNodeCount: state.drawnNodeCount,
      totalNodeCount: state.totalNodeCount,
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
      showSupersededNodes: state.showSupersededNodes,
      showCandidateNodes: state.showCandidateNodes,
    });
  }

  function hexToInt(hex) {
    return parseInt((hex || "#888888").replace("#", ""), 16);
  }

  function inferBranchKey(data) {
    const id = String(data?.id || "").toLowerCase();
    const type = String(data?.type || "").toLowerCase();

    if (type.includes("constitution") || id === "constitution" || id.startsWith("const")) {
      return "constitution";
    }
    if (type.includes("treasury accounting")) {
      return "receipts";
    }
    // The three branch nodes are "legislative-branch" / "executive-branch" /
    // "judicial-branch" (type Branch); the prefix rules below only matched
    // their descendants, so the branches themselves fell through to
    // "position" and never reached the sector triangle.
    if (type === "branch" || id.endsWith("-branch")) {
      if (id.startsWith("legislative")) {
        return "legislative";
      }
      if (id.startsWith("judicial")) {
        return "judicial";
      }
      if (id.startsWith("executive")) {
        return "executive";
      }
    }
    if (type === "position" || type.includes("office") || type.includes("officer")) {
      return "position";
    }
    if (id.startsWith("leg-")) {
      return "legislative";
    }
    if (id.startsWith("jud-")) {
      return "judicial";
    }
    if (id.startsWith("exec-regulatory") || type.includes("regulatory")) {
      return "regulatory";
    }
    if (
      id.startsWith("exec-ind") ||
      id === "exec-independent" ||
      type.includes("government corporation") ||
      type.includes("independent")
    ) {
      return "independent";
    }
    if (id.startsWith("exec-")) {
      return "executive";
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
      // A unit beneath the independent establishments or the regulatory
      // commissions that the curated file coloured executive red takes its
      // sector's hue, so the sector reads as one colour: 49 such units under
      // the green Independent Establishments drew red among green siblings.
      // Posts keep the position grey and Treasury lines their own colour.
      if (data.color.toLowerCase() === EXECUTIVE_RED) {
        const id = String(data.id || "").toLowerCase();
        if (id.startsWith("exec-ind")) {
          return branchColors.independent;
        }
        if (id.startsWith("exec-regulatory")) {
          return branchColors.regulatory;
        }
      }
      return data.color;
    }

    return branchColors[inferBranchKey(data)] || branchColors.position;
  }

  function getBranchColor(branchKey) {
    return branchColors[branchKey] || branchColors.position;
  }

  // Mirrors ui.js isNeverChecked: zero sources and no verification timestamp
  // means nothing was ever checked. That is not the checked-and-failed state
  // the wireframe "unverified" material and the hide toggle exist for — with
  // every curated node stamped "unverified" by default, the whole graph drew
  // as 20% ghosts and the toggle blanked the Constitution.
  function isNeverChecked(data) {
    if (!data || data.isCandidate) {
      return false;
    }
    const sourceCount = Number(data.sourceCount || (Array.isArray(data.sourceUrls) ? data.sourceUrls.length : 0));
    return sourceCount === 0 && !data.lastVerified;
  }

  function getVerificationStyleKey(data) {
    if (data?.isCandidate) {
      return "candidate";
    }
    if (isNeverChecked(data)) {
      return "unsourced";
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

  // --- Lens readers. Each reads published fields the same way js/ui.js
  // does and returns a small verdict the colour, the size and the brood
  // badge all draw from, so the three can never disagree about a node.

  function isPostData(data) {
    return /position|\brole\b|office holder/i.test(String(data?.type || ""));
  }

  function isTreasuryLineData(data) {
    return Boolean(data?.synthetic) || /treasury accounting line/i.test(String(data?.type || ""));
  }

  function finiteAmount(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function blockAmount(block) {
    if (!block || typeof block !== "object") {
      return null;
    }
    const amount = finiteAmount(block.amount);
    return amount !== null && amount > 0 ? amount : null;
  }

  function blockRange(block) {
    if (!block || typeof block !== "object") {
      return null;
    }
    const min = finiteAmount(block.minimum);
    const max = finiteAmount(block.maximum);
    return min !== null && max !== null && max > 0 ? { min, max } : null;
  }

  // Evidence: one of six words. "notFound" is the checked-and-failed state
  // (a date and no source), "unread" the host that refused the crawler, and
  // "unsourced" that nothing was ever checked — ui.js's isNeverChecked.
  function evidenceVerdict(data) {
    if (isTreasuryLineData(data)) {
      return { key: "treasuryLine", text: "the statement's own line" };
    }
    const sources = Number(data?.sourceCount || (Array.isArray(data?.sourceUrls) ? data.sourceUrls.length : 0));
    const status = String(data?.verificationStatus || "").toLowerCase();
    if (sources > 0 && status === "verified") {
      return { key: "verified", text: `verified · ${sources} official ${sources === 1 ? "source" : "sources"}` };
    }
    if (sources > 0 && status === "partial") {
      return { key: "partial", text: "partial · one official source" };
    }
    if (data?.verificationUnread) {
      return { key: "unread", text: "host refuses the crawler" };
    }
    if (sources === 0 && data?.lastVerified) {
      return { key: "notFound", text: "checked, not found" };
    }
    // No page was ever queued, and the record says why: the name is this
    // graph's own count label or grouping, the site is off every .gov host,
    // or the only host that would carry it refuses the crawler. A checked
    // negative above outranks it: a document was read.
    if (data?.verificationNoDocument) {
      return { key: "noDocument", text: "no page could be named" };
    }
    if (sources > 0) {
      return { key: "partial", text: "source recorded, unverified" };
    }
    return { key: "unsourced", text: "no source recorded" };
  }

  // Pay: the claim the panel heads a post's figure with, in the order
  // ui.js's PAY_STAND_IN_ORDER reads it — a figure a document states for
  // the office, then for one incumbency, then a range. A range is never
  // written as a rate. Never on a unit.
  const PAY_READERS = [
    ["office", "statute", (d) => blockAmount(d.positionStatutoryPay)],
    ["office", "Executive Schedule", (d) => blockAmount(d.positionSchedulePay)],
    ["office", "set by reference to a level", (d) => blockAmount(d.positionTierReferencePay)],
    ["office", "derived, stated by no document", (d) => blockAmount(d.positionDerivedPay)],
    ["office", "12 × monthly basic pay", (d) => blockAmount(d.positionMilitaryPay)],
    ["incumbency", "White House roster", (d) => blockAmount(d.positionReportedPay)],
    ["incumbency", "current Plum Book", (d) => blockAmount(d.positionCurrentPay)],
    ["incumbency", "listed level, OPM table", (d) => blockAmount(d.positionPayRate)],
  ];

  function payVerdict(data) {
    if (!isPostData(data)) {
      return { key: "unit", text: "a unit has no salary" };
    }
    for (const [key, basis, read] of PAY_READERS) {
      const amount = read(data);
      if (amount !== null) {
        const holders = data.positionStatutoryPay?.holders || data.positionDerivedPay?.holders || data.positionTierReferencePay?.holders || data.positionMilitaryPay?.holders || data.positionSchedulePay?.holders || data.positionReportedPay?.holders;
        const each = holders && typeof holders === "object" ? " · each holder" : "";
        return { key, amount, text: `${formatDollars(amount)} · ${basis}${each}` };
      }
    }
    const range = blockRange(data.positionGradePay) || blockRange(data.positionTierPay);
    if (range) {
      return { key: "range", text: `${formatDollars(range.min)}–${formatDollars(range.max)} · a range, not a rate` };
    }
    const employer = data.positionEmployer;
    if (employer && typeof employer === "object" && employer.federallyPaid === false) {
      return { key: "notFederal", text: "not on a federal pay schedule" };
    }
    return { key: "unpriced", text: "no document names the title" };
  }

  // Money: cost_status, read as the panel reads it. An estimate is a
  // verdict only while the reader has opted in; otherwise it is "none" and
  // draws exactly like a node with no figure, which is what the default
  // view publishes.
  function moneyVerdict(data) {
    const status = String(data?.cost_status || "").toLowerCase();
    const amount = finiteAmount(data?.resolved_total_amount);
    if ((status === "official" || status === "root_total") && amount !== null && amount !== 0) {
      if (isTreasuryLineData(data) || amount < 0) {
        return { key: "receipts", amount, text: `${formatDollars(amount)} · the statement's line` };
      }
      return { key: "measured", amount, text: `${formatDollars(amount)} · measured` };
    }
    if (status === "allocated" && amount !== null && amount !== 0 && state.showEstimateFigures) {
      return { key: "estimate", amount, text: `≈ ${formatDollars(amount)} · estimate` };
    }
    if (isPostData(data)) {
      return { key: "none", text: "a post is not a budget unit" };
    }
    if (status === "allocated") {
      return { key: "none", text: "estimate withheld" };
    }
    return { key: "none", text: "no figure" };
  }

  function formatDollars(amount) {
    const abs = Math.abs(amount);
    const sign = amount < 0 ? "−" : "";
    if (abs >= 1e12) {
      return `${sign}$${(abs / 1e12).toFixed(2)}T`;
    }
    if (abs >= 1e9) {
      return `${sign}$${(abs / 1e9).toFixed(abs >= 1e11 ? 0 : 1)}B`;
    }
    if (abs >= 1e6) {
      return `${sign}$${(abs / 1e6).toFixed(abs >= 1e8 ? 0 : 1)}M`;
    }
    return `${sign}$${Math.round(abs).toLocaleString("en-US")}`;
  }

  function lensVerdict(data) {
    if (state.lens === "whole") {
      return { key: "whole", text: wholeCaption(data) };
    }
    if (state.lens === "evidence") {
      return evidenceVerdict(data);
    }
    if (state.lens === "pay") {
      return payVerdict(data);
    }
    if (state.lens === "money") {
      return moneyVerdict(data);
    }
    return null;
  }

  // The caption under a branch halo in the Whole lens: how many nodes this
  // graph carries beneath it, split into units and posts, and the branch's
  // own measured figure where a record states one. Counted once per node
  // off the data, never off what happens to be drawn.
  const wholeCaptionCache = new Map();

  function wholeCaption(data) {
    const id = `${data?.id || ""}:${state.showEstimateFigures ? 1 : 0}`;
    if (wholeCaptionCache.has(id)) {
      return wholeCaptionCache.get(id);
    }
    let units = 0;
    let posts = 0;
    let sectorsApart = 0;
    const walk = (node) => {
      for (const child of node.children || []) {
        // A sector captioned on its own is not counted again in its
        // branch's caption: the two captions describe two masses.
        if (SECTOR_ROOT_IDS.has(String(child.id)) && !SECTOR_ROOT_IDS.has(String(data?.id))) {
          sectorsApart += 1;
          continue;
        }
        if (isPostData(child)) {
          posts += 1;
        } else if (!isTreasuryLineData(child)) {
          units += 1;
        }
        walk(child);
      }
    };
    walk(data || {});
    const parts = [`${units.toLocaleString("en-US")} units · ${posts.toLocaleString("en-US")} posts in this graph${sectorsApart ? `, its ${sectorsApart} sectors captioned apart` : ""}`];
    const money = moneyVerdict(data || {});
    if (money.key === "measured") {
      parts.push(`${formatDollars(money.amount)} measured`);
    } else if (money.key === "estimate") {
      parts.push(money.text);
    }
    const caption = parts.join(" · ");
    wholeCaptionCache.set(id, caption);
    return caption;
  }

  const lensColorCache = new Map();

  // Whole: every node takes the hue of the branch it sits under, posts
  // included — 83% of the nodes are posts, and drawn in the position grey
  // the three masses would read as one grey cloud. A Treasury line keeps
  // its own colour. Cached per node; the ancestry does not change.
  const wholeHueCache = new Map();

  function wholeHue(data) {
    const id = String(data?.id || "");
    if (wholeHueCache.has(id)) {
      return wholeHueCache.get(id);
    }
    let hue = null;
    if (isTreasuryLineData(data)) {
      hue = getNodeColor(data);
    } else {
      let cursor = data;
      let guard = 0;
      while (cursor && guard < 64) {
        if (cursor !== data && (normalizeClusterKey(cursor.type) === "branch" || SECTOR_ROOT_IDS.has(String(cursor.id)) || !state.parentIdById.get(cursor.id))) {
          hue = getNodeColor(cursor);
          break;
        }
        const parentId = state.parentIdById.get(cursor.id);
        cursor = parentId ? state.dataMap.get(parentId) : null;
        guard += 1;
      }
      if (!hue) {
        hue = getNodeColor(data);
      }
    }
    wholeHueCache.set(id, hue);
    return hue;
  }

  function lensColorHex(data) {
    if (state.lens === "whole") {
      return wholeHue(data);
    }
    const verdict = lensVerdict(data);
    if (!verdict) {
      return null;
    }
    if (state.lens === "evidence") {
      return EVIDENCE_COLORS[verdict.key] || EVIDENCE_COLORS.unsourced;
    }
    if (state.lens === "pay") {
      return PAY_COLORS[verdict.key] || PAY_COLORS.unpriced;
    }
    return MONEY_COLORS[verdict.key] || MONEY_COLORS.none;
  }

  function lensColor(hex) {
    let color = lensColorCache.get(hex);
    if (!color) {
      color = new THREE.Color(hex);
      lensColorCache.set(hex, color);
    }
    return color;
  }

  // Money alone changes a size, and only for a figure a record states or
  // an estimate the reader opted into: the radius grows with the fourth
  // root of the figure, so a $1B line draws at 0.9× and the largest
  // measured line at the cap. Everything else draws slightly smaller, so
  // the measured money is what the eye lands on. A size is never read off
  // subtree count, which this project records as the dishonest proxy.
  function lensScaleOf(nodeObj) {
    return lensScaleForData(nodeObj.data, nodeObj === state.rootObj);
  }

  function lensScaleForData(data, isRoot) {
    if (state.lens !== "money" || isRoot) {
      return 1;
    }
    const verdict = moneyVerdict(data);
    if (verdict.key === "none") {
      return 0.7;
    }
    const scale = Math.pow(Math.abs(verdict.amount) / 1e9, 0.25) * 0.9;
    const clamped = THREE.MathUtils.clamp(scale, 0.7, 2.6);
    return verdict.key === "estimate" ? clamped * 0.85 : clamped;
  }

  // Under a lens the batch materials go neutral and the instance colour
  // carries the verdict; under Structure the verification profile is
  // restored exactly. The verification style (a partial node's 0.64
  // opacity, an unverified one's wireframe) stays on the material either
  // way, so Evidence shows it twice over and the others do not hide it.
  function applyLensMaterials() {
    const neutral = state.lens !== "structure";
    for (const batch of state.nodeBatches.values()) {
      const material = batch.mesh.material;
      if (neutral) {
        // Emissive is not multiplied by the instance colour, so a white
        // glow would grey every verdict evenly; the ambient light carries
        // the colour instead.
        material.color.set(0xffffff);
        material.emissive.set(0x000000);
        material.emissiveIntensity = 0;
      } else {
        material.color.copy(batch.profile.color);
        material.emissive.copy(batch.profile.emissive);
        material.emissiveIntensity = batch.profile.emissiveIntensity;
      }
      material.needsUpdate = true;
      batch.dirty = true;
    }
  }

  function setLens(name) {
    const next = LENSES.includes(name) ? name : "structure";
    if (next === state.lens) {
      return;
    }
    if (state.lens === "whole" && next !== "whole") {
      restoreWholeLayout();
    }
    state.lens = next;
    // The far plane sits at 3,000 units, inside the distance the Whole
    // lens's zoom floor allows; pushed out while that lens is on, so the
    // far side of the tree is drawn rather than clipped.
    camera.far = next === "whole" ? 20000 : 3000;
    camera.updateProjectionMatrix();
    applyLensMaterials();
    state.focusKey = "";
    state.highlightVersion += 1;
    state.renderDirty = true;
    state.forceFullRenderRefresh = true;
    updateLodState();
    refreshVisibility();
  }

  // The Whole lens lays the tree out as one sphere you can turn in your
  // hands, rather than the cones the expansion layout grows. Each node gets a
  // patch of the sphere's surface — an equal-area treemap in (longitude,
  // height) coordinates, where a rectangle's area is exactly its solid angle
  // — in proportion to the leaves beneath it, so a branch or a sector is one
  // contiguous region and the leaves (most of them posts) cover the surface
  // evenly as its crust. A unit sits inside, along the centre of its patch,
  // at a radius set by its depth, so the edges run outward like the spokes
  // of a globe. A patch's area is this graph's count of leaves beneath the
  // node — its depth of curation, which the key and the captions say — and
  // never a figure.
  //
  // The crust is not one radius. Each branch's patch sits at a radius set by
  // the branch's share of the graph's leaves (`WHOLE_RELIEF`: the largest
  // branch at the full radius, the others drawn in proportionally), so the
  // globe carries the same count a second way, as relief — the Executive's
  // mass stands out from the sphere and the Judiciary's sits in. Both are
  // this graph's depth of curation, which the key says.
  const WHOLE_SPHERE_RADIUS = 1080;
  const WHOLE_RELIEF = 0.2;

  function applyWholeLayout() {
    if (!state.rootObj) {
      return;
    }
    const visibleChildren = (nodeObj) => (nodeObj.childObjs || []).filter((child) => child.visible);
    const leaves = new Map();
    let maxInternalDepth = 1;
    const countLeaves = (nodeObj) => {
      const kids = visibleChildren(nodeObj);
      if (!kids.length) {
        leaves.set(nodeObj, 1);
        return 1;
      }
      maxInternalDepth = Math.max(maxInternalDepth, nodeObj.depth);
      let total = 0;
      for (const child of kids) {
        total += countLeaves(child);
      }
      leaves.set(nodeObj, total);
      return total;
    };
    countLeaves(state.rootObj);
    // Relief: a branch's crust radius from its share of the leaves. Only the
    // root's own children carry a factor; every node beneath takes its
    // branch's, so a patch is one continuous shell and the edges inside it
    // stay radial.
    const branchFactor = new Map();
    const branches = visibleChildren(state.rootObj);
    const largest = branches.reduce((most, child) => Math.max(most, leaves.get(child) || 0), 0) || 1;
    for (const child of branches) {
      const share = (leaves.get(child) || 0) / largest;
      branchFactor.set(child, 1 - WHOLE_RELIEF + WHOLE_RELIEF * Math.sqrt(share));
    }
    const reliefOf = (nodeObj) => {
      let walker = nodeObj;
      while (walker && walker.parent && walker.parent !== state.rootObj) {
        walker = walker.parent;
      }
      return (walker && branchFactor.get(walker)) || 1;
    };
    const now = performance.now();
    const moveTo = (nodeObj, x, y, z) => {
      if (!nodeObj.wholeHome) {
        nodeObj.wholeHome = nodeObj.targetPos.clone();
      }
      nodeObj.animFrom.copy(nodeObj.pos);
      nodeObj.targetPos.set(x, y, z);
      nodeObj.animStart = now;
      nodeObj.animating = true;
    };
    const place = (nodeObj, lon0, lon1, h0, h1) => {
      const lon = (lon0 + lon1) / 2;
      const h = (h0 + h1) / 2;
      const ring = Math.sqrt(Math.max(0, 1 - h * h));
      const kids = visibleChildren(nodeObj);
      const shell = WHOLE_SPHERE_RADIUS * (nodeObj === state.rootObj ? 1 : reliefOf(nodeObj));
      const radius = nodeObj === state.rootObj
        ? 0
        : !kids.length
          ? shell
          : shell * 0.94 * Math.pow(nodeObj.depth / (maxInternalDepth + 1), 0.8);
      moveTo(nodeObj, radius * ring * Math.cos(lon), radius * h, radius * ring * Math.sin(lon));
      if (kids.length) {
        split(kids, lon0, lon1, h0, h1);
      }
    };
    // Split the sibling list into two halves of nearly equal leaf count and
    // the patch along its longer side, recursively: a balanced binary
    // treemap, which keeps 249 siblings from becoming 249 slivers.
    const split = (list, lon0, lon1, h0, h1) => {
      if (list.length === 1) {
        place(list[0], lon0, lon1, h0, h1);
        return;
      }
      const total = list.reduce((sum, nodeObj) => sum + leaves.get(nodeObj), 0);
      let cut = 1;
      let running = leaves.get(list[0]);
      while (cut < list.length - 1 && running + leaves.get(list[cut]) / 2 < total / 2) {
        running += leaves.get(list[cut]);
        cut += 1;
      }
      const share = running / total;
      const hMid = (h0 + h1) / 2;
      const ring = Math.max(Math.sqrt(Math.max(0, 1 - hMid * hMid)), 0.2);
      const wide = (lon1 - lon0) * ring >= (h1 - h0) / ring;
      if (wide) {
        const lonCut = lon0 + (lon1 - lon0) * share;
        split(list.slice(0, cut), lon0, lonCut, h0, h1);
        split(list.slice(cut), lonCut, lon1, h0, h1);
      } else {
        const hCut = h0 + (h1 - h0) * share;
        split(list.slice(0, cut), lon0, lon1, h0, hCut);
        split(list.slice(cut), lon0, lon1, hCut, h1);
      }
    };
    place(state.rootObj, 0, Math.PI * 2, -1, 1);
    state.wholeLayoutApplied = true;
    state.renderDirty = true;
    state.forceFullRenderRefresh = true;
  }

  // Back to the layout the expansion grew, for every node the sphere moved.
  function restoreWholeLayout() {
    if (!state.wholeLayoutApplied) {
      return;
    }
    const now = performance.now();
    for (const nodeObj of state.allNodes) {
      if (!nodeObj.wholeHome) {
        continue;
      }
      nodeObj.animFrom.copy(nodeObj.pos);
      nodeObj.targetPos.copy(nodeObj.wholeHome);
      nodeObj.wholeHome = null;
      nodeObj.animStart = now;
      nodeObj.animating = true;
    }
    state.wholeLayoutApplied = false;
    state.renderDirty = true;
    state.forceFullRenderRefresh = true;
  }

  // Frame everything loaded: the Whole lens's camera, called by ui.js once
  // the expansion it asked for has finished. The sphere is laid out first,
  // so the frame fits the sphere and not the cones it replaces.
  function frameWhole() {
    if (!state.rootObj || state.flyMode) {
      return;
    }
    if (state.lens === "whole") {
      applyWholeLayout();
      state.camFocusTarget.set(0, 0, 0);
      state.lastInteractionAt = 0;
    }
    frameSubtreeOf(state.rootObj, Infinity);
    // `frameSubtreeOf` fits the subtree to the camera's VERTICAL field over
    // the whole canvas. The whole tree is wider than it is tall, and the
    // rail on the left and the inspector on the right cover the canvas's
    // edges, so the Executive's mass was running under the panel. Refit to
    // the stage the chrome leaves: the horizontal extent against the
    // uncovered width, and the focus shifted so the tree's centre sits in
    // the uncovered width's centre rather than the canvas's.
    const { width, height, usable } = stageGeometry();
    const points = [];
    for (const nodeObj of state.visibleNodes) {
      points.push(nodeObj.targetPos && nodeObj.targetPos.lengthSq() > 0 ? nodeObj.targetPos : nodeObj.pos);
    }
    if (points.length < 2) {
      return;
    }
    const centroid = state.camFocusTarget.clone();
    let reach = 0;
    for (const point of points) {
      reach = Math.max(reach, point.distanceTo(centroid));
    }
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    const aspect = width / Math.max(height, 1);
    // 1.35, not 1.1: a sphere's silhouette subtends more than its radius
    // does at the centre's distance, and the top bar covers the canvas's
    // top 60px — at 1.1 the sphere's poles were clipped.
    const verticalFit = (reach * 1.35) / Math.max(Math.tan(halfFov), 0.05);
    const horizontalFit = (reach * 1.35) / Math.max(Math.tan(halfFov) * aspect * (usable / width), 0.05);
    const fitDistance = Math.max(verticalFit, horizontalFit);
    state.targetZoom = THREE.MathUtils.clamp(CAMERA_DISTANCE / Math.max(fitDistance, 1), minZoom(), 10);
    state.renderDirty = true;
  }

  function setShowEstimateFigures(enabled) {
    const next = Boolean(enabled);
    if (next === state.showEstimateFigures) {
      return;
    }
    state.showEstimateFigures = next;
    if (state.lens === "money") {
      state.focusKey = "";
      state.renderDirty = true;
      state.forceFullRenderRefresh = true;
    }
  }

  function getVerificationBadgeColor(data) {
    const styleKey = getVerificationStyleKey(data);
    if (styleKey === "partial") {
      return "#d9b55e";
    }
    if (styleKey === "unverified") {
      return "#8e7d62";
    }
    if (styleKey === "unsourced") {
      return "#9a8a6a";
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
    // A unit the government has replaced. The data is never deleted — the node
    // keeps its id, its description and every source anybody earned for it —
    // but the default view is the government as it stands, so it is drawn only
    // when the reader asks for replaced units.
    if (String(data?.lifecycle || "") === "superseded" && !state.showSupersededNodes) {
      return false;
    }
    if (state.showUnverifiedNodes) {
      return true;
    }
    if (isNeverChecked(data)) {
      // The toggle hides nodes that were checked and failed, not the curated
      // hierarchy nothing has checked.
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
      // A label is read, not placed in depth: the Whole lens's fog must not
      // fade a caption that sits at the sphere's centre.
      fog: false,
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
    if (label.text === title && label.subtext === subtitle && label.hue === color) {
      return;
    }

    const { context, canvas, texture } = label;
    context.clearRect(0, 0, canvas.width, canvas.height);
    // The badge is drawn in the shell's own language (css/shell.css): ink
    // panel, hairline in the node's hue, a serif name over a mono count.
    context.fillStyle = options.fillStyle || "rgba(13, 18, 26, 0.92)";
    context.strokeStyle = options.strokeStyle || `${color}b3`;
    context.lineWidth = options.lineWidth || 2;
    context.beginPath();
    context.roundRect(6, 8, canvas.width - 12, canvas.height - 16, 18);
    context.fill();
    context.stroke();

    context.textAlign = "center";
    context.fillStyle = options.titleColor || "#EDE6D8";
    context.font = options.titleFont || "600 32px 'Playfair Display', Georgia, serif";
    context.fillText(title, canvas.width / 2, 66, canvas.width - 44);
    context.fillStyle = options.subtitleColor || color;
    context.font = options.subtitleFont || "500 22px 'IBM Plex Mono', Menlo, monospace";
    context.fillText(subtitle, canvas.width / 2, 108, canvas.width - 44);

    texture.needsUpdate = true;
    label.text = title;
    label.subtext = subtitle;
    label.hue = color;
  }

  function drawClusterLabel(label, title, subtitle, color) {
    drawTextBadge(label, title, subtitle, color);
  }

  function drawHaloLabel(label, title, subtitle, color) {
    drawTextBadge(label, title, subtitle, color, {
      fillStyle: "rgba(13, 18, 26, 0.82)",
      strokeStyle: `${color}99`,
      lineWidth: 2,
      titleFont: "600 34px 'Playfair Display', Georgia, serif",
      subtitleFont: "500 22px 'IBM Plex Mono', Menlo, monospace",
      subtitleColor: "#B8AE9A",
    });
  }

  function drawBroodLabel(label, title, subtitle, color) {
    drawTextBadge(label, title, subtitle, color, {
      fillStyle: "rgba(13, 18, 26, 0.9)",
      strokeStyle: `${color}8c`,
      lineWidth: 2,
      titleFont: "500 34px 'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
      subtitleFont: "500 22px 'IBM Plex Mono', Menlo, monospace",
      subtitleColor: "#8A8270",
    });
  }

  function ensureBroodLabelPool(count) {
    while (state.broodLabels.length < Math.min(count, BROOD_LABEL_CAPACITY)) {
      state.broodLabels.push(createTextSprite());
    }
  }

  // What a brood badge says beneath the name. Under Structure: how much sits
  // beneath the child, or that it is a post — never a figure, since the
  // panel's cost rules are the only place a number appears with its badge.
  // Under a lens the badge says the lens's own verdict, in the panel's own
  // words, and a figure is written only with the claim it is ("· statute",
  // "· estimate", "a range, not a rate"), the same labels the panel heads it
  // with, so the badge can never claim more than the panel does.
  function broodSubtitle(childObj) {
    const data = childObj.data || {};
    const verdict = state.lens === "whole" ? null : lensVerdict(data);
    if (verdict) {
      return verdict.text;
    }
    const type = String(data.type || "");
    const beneath = Array.isArray(data.children) ? data.children.length : 0;
    if (beneath > 0) {
      return `${type} · ${beneath.toLocaleString()} beneath`;
    }
    return type || "Unit";
  }

  // Name badges for the selected node's own children, and for the selected
  // node where no halo already names it. Pressing Expand is a request to see
  // the children; until this they were drawn as unlabelled dots, so a reader
  // saw a fan of edges ending in nothing they could name. Bounded to one
  // brood, never a subtree, the bound the LOD exemption already uses.
  function updateBroodLabels(protectedIds = getProtectedNodeIds()) {
    const selected = state.selectedNode;
    const candidates = [];
    const subjects = [];
    // Under Whole the captions at the centre of each mass are the labels;
    // a selection's brood badges would pile up in the sphere's middle.
    if (selected && !selected.isCluster && selected.renderVisible && !selected.clustered && state.lens !== "whole") {
      if (!state.lod.haloNodeIds?.has(selected.data?.id)) {
        subjects.push({ nodeObj: selected, priority: 1_200_000 });
      }
      for (const childObj of selected.childObjs || []) {
        if (!childObj.renderVisible || childObj.clustered || childObj.culled) {
          continue;
        }
        // Under Whole a branch's halo already names it, with the caption
        // this lens exists for; a brood badge on top would cover it.
        if (state.lens === "whole" && state.lod.haloNodeIds?.has(childObj.data?.id)) {
          continue;
        }
        // Units before posts, the order the panel's own list uses, so the
        // overlap pass keeps the children that carry structure — except
        // under the Pay lens, whose question is about the posts.
        const isPost = /position|role|office holder/i.test(String(childObj.data?.type || ""));
        const leads = state.lens === "pay" ? isPost : !isPost;
        subjects.push({ nodeObj: childObj, priority: 400_000 + (leads ? 50_000 : 0) + (protectedIds.has(childObj.data?.id) ? 100_000 : 0) });
      }
    }
    subjects.sort((a, b) => b.priority - a.priority);
    const shown = subjects.slice(0, BROOD_LABEL_CAPACITY);
    ensureBroodLabelPool(shown.length);
    for (let i = 0; i < shown.length; i += 1) {
      const { nodeObj, priority } = shown[i];
      const label = state.broodLabels[i];
      const color = lensColorHex(nodeObj.data) || getNodeColor(nodeObj.data);
      drawBroodLabel(label, nodeObj.data.name, nodeObj === selected ? "selected" : broodSubtitle(nodeObj), color);
      label.sprite.visible = true;
      label.sprite.position.copy(nodeObj.pos);
      const labelScale = getLabelDistanceScale(label.sprite.position);
      label.sprite.position.y += NODE_RADIUS * 1.6 + 3.8 * labelScale;
      label.sprite.scale.set(24 * labelScale, 7.4 * labelScale, 1);
      candidates.push({ sprite: label.sprite, priority, brood: true });
    }
    for (let i = shown.length; i < state.broodLabels.length; i += 1) {
      state.broodLabels[i].sprite.visible = false;
    }
    return candidates;
  }

  // The focus set: the selection, its ancestors and its own children. Nodes
  // outside it are tinted toward the ink and their edges dimmed, so an
  // expansion reads as one subject against a quiet field rather than one
  // more handful of dots among thousands. Recomputed only when the selection
  // or its brood changes; the tint rides on the instance colour, which
  // multiplies the batch material and changes nothing about the data.
  const tempLensColor = new THREE.Color();

  function refreshFocus() {
    const selected = state.selectedNode && !state.selectedNode.isCluster ? state.selectedNode : null;
    // The loaded count is in the key: a slot assigned after the last pass
    // carries the mesh's default white until this runs again, and an
    // expansion under a lens was drawing its new nodes uncoloured.
    const key = `${state.lens}:${state.showEstimateFigures ? 1 : 0}:${state.allNodes.size}:${selected ? `${selected.data.id}:${(selected.childObjs || []).length}` : ""}`;
    if (key === state.focusKey) {
      return;
    }
    state.focusKey = key;
    const focus = new Set();
    if (selected) {
      let cursor = selected;
      while (cursor) {
        focus.add(cursor.data.id);
        cursor = cursor.parent;
      }
      for (const childObj of selected.childObjs || []) {
        focus.add(childObj.data.id);
      }
    }
    state.focusIds = focus;
    state.highlightVersion += 1;
    for (const nodeObj of state.allNodes) {
      if (!nodeObj.batch || nodeObj.slot < 0) {
        continue;
      }
      // Under Whole nothing is context: the reader asked to see all of it.
      const tint = state.lens === "whole" || focus.size === 0 || focus.has(nodeObj.data.id) ? FOCUS_FULL : FOCUS_DIM;
      const hex = lensColorHex(nodeObj.data);
      if (hex) {
        // The verdict's colour, dimmed outside the focus the same way the
        // branch hue is under Structure.
        tempLensColor.copy(lensColor(hex)).multiply(tint);
        nodeObj.batch.mesh.setColorAt(nodeObj.slot, tempLensColor);
      } else {
        nodeObj.batch.mesh.setColorAt(nodeObj.slot, tint);
      }
      nodeObj.batch.dirty = true;
    }
  }

  function getLabelDistanceScale(worldPosition) {
    const distance = Math.max(camera.position.distanceTo(worldPosition), 1);
    // The Whole lens sits far enough back that the ordinary ceiling leaves
    // a branch's caption unreadable; it may grow further there.
    return THREE.MathUtils.clamp(distance * 0.006, 0.5, state.lens === "whole" ? 14 : 4);
  }

  function hashString(input) {
    let hash = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      hash ^= input.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function minZoom() {
    return state.lens === "whole" ? WHOLE_MIN_ZOOM : MIN_ZOOM;
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

  // The shell a brood of `count` children is laid out on. Until 2026-09-21
  // this was the depth radius alone, so a parent with three children and a
  // parent with 249 got the same sphere and the big brood simply piled up:
  // the White House Office carries 249 and "Other Independent Agencies" went
  // from 32 to 70 the same day. Growth is sub-linear in the count, so a
  // typical brood barely moves (five children: 1.05x) while the two that
  // overflow get real room (70: 1.20x, 249: 1.38x), and every child of one
  // parent still shares one sphere.
  function shellRadiusForBrood(depth, count) {
    const crowding = Math.min(0.55, Math.sqrt(Math.max(count, 1)) / 42);
    return shellRadiusForDepth(depth) * (1 + crowding);
  }

  // How wide a cone that brood is spread over. The cap was a flat 0.42 -- a
  // roughly 23-degree half-angle -- whatever the count, which is the other
  // half of the same pile-up.
  function spreadCapForCount(count) {
    if (count <= 12) {
      return 0.42;
    }
    return Math.min(0.95, 0.42 * (1 + Math.log10(count / 12) * 0.62));
  }

  function getNavigationDistance() {
    if (state.flyMode) {
      // flyLookTarget is always FLY_LOOK_DISTANCE ahead of the camera, so
      // measuring to it pinned the LOD at Position View from any range.
      const anchor = state.selectedNode?.pos || state.rootObj?.pos;
      return Math.max(anchor ? camera.position.distanceTo(anchor) : camera.position.length(), 1);
    }
    // The orbit position, not the rendered camera: the render camera sits
    // one stage-shift to the side, and the tier is about how far the reader
    // has pulled back, not where the picture was slid to.
    return Math.max(state.orbitPosition.distanceTo(state.camFocus), 1);
  }

  function updateLodState() {
    state.lod = lodManager.updateLOD({
      cameraDistance: getNavigationDistance(),
      rootNode: state.rootObj,
      maxDepthFilter: state.manualDepthFilter,
    });
    if (state.lens === "whole") {
      const manualDepth = Number.isFinite(state.manualDepthFilter) ? Math.min(state.manualDepthFilter, MAX_DEPTH) : MAX_DEPTH;
      // The two sectors are masses of their own on the sphere, so each gets
      // a halo and a caption like a branch.
      const haloNodeIds = new Set(state.lod.haloNodeIds || []);
      for (const id of SECTOR_ROOT_IDS) {
        if (state.nodeMap.has(id)) {
          haloNodeIds.add(id);
        }
      }
      state.lod = { ...state.lod, ...WHOLE_LOD, visibleDepth: manualDepth, haloNodeIds };
    }
    state.maxVisibleDepth = state.lod.visibleDepth;
    return state.lod;
  }

  // The branch used to be curated as "Legislative Branch — The Congress",
  // which is not "legislative branch", so a name lookup protected two
  // branches out of three. The type says what it is; the name never did.
  function isBranchRoot(data) {
    if (!data) {
      return false;
    }
    // Exactly "branch": "Military Branch" (Army, Navy, ...) is not a branch of government.
    if (normalizeClusterKey(data.type) === "branch") {
      return true;
    }
    return ALWAYS_VISIBLE_CLUSTER_NAMES.has(normalizeClusterKey(data.name || data.id));
  }

  function getProtectedNodeIds() {
    const protectedIds = new Set([state.rootObj?.data?.id].filter(Boolean));
    for (const nodeObj of state.visibleNodes) {
      if (isBranchRoot(nodeObj.data)) {
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
    // A node that is on screen keeps a small edge over one that is not. The
    // cap is recomputed every frame from screen-tile membership, so a node
    // drifting across a tile edge joins a different contest and could lose a
    // place it had held a moment earlier; at the widest zoom a tile keeps
    // only ONE node, so in a crowded brood the survivor changed constantly
    // and the rest blinked. The bonus is small enough that real importance
    // still wins and a node cannot hold a tile against a better one.
    if (nodeObj.densityCapped === false) {
      score += DENSITY_STICKY_BONUS;
    }
    // Ties are the other half. Sibling positions share a depth and a subtree
    // count of one, so their scores are identical to the point, and which of
    // them survived was decided by their order in the bucket -- which shifts
    // as nodes rebin. A constant per node makes that order the same on every
    // frame. It is derived from the id, so it is stable across reloads too.
    score += (hashString(String(nodeObj.data?.id || "")) % 997) / 1000;
    return score;
  }

  function computeScreenSpaceBuckets(nodeObjs, tileSize = state.lod.tileSize, useCachedProjection = false) {
    const buckets = new Map();
    for (const nodeObj of nodeObjs) {
      if (!useCachedProjection) {
        const screen = projectWorldToScreen(nodeObj.pos);
        nodeObj.screenX = screen.x;
        nodeObj.screenY = screen.y;
        nodeObj.screenZ = screen.z;
      }
      if (nodeObj.screenZ < -1 || nodeObj.screenZ > 1) {
        continue;
      }
      const tileX = Math.floor(nodeObj.screenX / tileSize);
      const tileY = Math.floor(nodeObj.screenY / tileSize);
      const key = `${tileX}:${tileY}`;
      if (!buckets.has(key)) {
        buckets.set(key, []);
      }
      buckets.get(key).push(nodeObj);
    }
    return buckets;
  }

  function applyDensityCap(nodeObjs, protectedIds = getProtectedNodeIds()) {
    const ancestorIds = state.selectedNode?.isCluster ? new Set() : getAncestorIds(state.selectedNode);
    // Reuse the screen projections computed earlier in the same visibility
    // pass instead of projecting every node a second time.
    const buckets = computeScreenSpaceBuckets(nodeObjs, state.lod.tileSize, true);
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
    // The selected node's own children are exempt from the cap, for the
    // reason `isNodeRenderableAtCurrentLod` exempts them from the tier and
    // with the same bound: one brood, never a subtree. Framing a wide brood
    // pulls the camera back to a tier whose tiles keep two nodes each, so
    // the cap was quietly undoing the exemption -- measured on 2026-09-30 on
    // the White House Office's 249 children: 239 drawn while the hold below
    // lasted, then 26 once it expired, with 244 "density-hidden". A reader
    // who pressed Expand asked to see these; the cap's job is the pile a
    // reader did not ask for.
    //
    // Since 2026-10-21 the same holds for every brood a reader opened, not
    // only the selection's: clicking one department of an expanded Cabinet
    // to read it took the other fourteen out of the exemption, and the cap
    // hid some of them the moment the selection moved.
    for (const nodeObj of nodeObjs) {
      const parentObj = nodeObj.parent;
      if (!parentObj) {
        continue;
      }
      if ((parentObj === state.selectedNode && !state.selectedNode.isCluster) || parentObj.readerOpened) {
        allowed.add(nodeObj.data.id);
      }
    }

    // A minimum dwell. Winning a tile's place is decided afresh every frame,
    // so a node drifting near a tile edge can lose and regain its place over
    // and over -- the blinking. Once a node is drawn it is held for a short
    // while whatever the next frame's contest says, which turns an
    // oscillation into at most one transition. The hold is short enough that
    // a node genuinely leaving the view is gone within a third of a second,
    // and it can only ever show MORE than the cap intends, never fewer.
    let hiddenCount = 0;
    for (const nodeObj of nodeObjs) {
      let visible = allowed.has(nodeObj.data.id);
      if (visible) {
        nodeObj.densityHoldUntil = state.frame + DENSITY_HOLD_FRAMES;
      } else if ((nodeObj.densityHoldUntil || 0) > state.frame) {
        visible = true;
      }
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

  // The panels the page draws over the canvas. Labels have always been
  // de-overlapped against each other and were never compared with these at
  // all, so on 2026-09-22 a 1400x900 capture had "Executive Office of the
  // President (EOP) (430)" sitting on top of the legend's colour key, two
  // cluster labels sliced off by the right panel's edge, and a third under
  // the left column's text.
  // Measured from the DOM rather than written down as pixels: the panels are
  // sized by their own content and the reading-guide button, the depth list
  // and the stats block have each changed the left column's width this month.
  const CHROME_ELEMENT_IDS = [
    "left-stack",
    "info-panel",
    "breadcrumb",
    "depth-ctrl",
    "legend",
    "stats",
    "search-wrap",
    "controls-hint",
  ];
  let chromeRectCache = { frame: -1, rects: [] };

  function getChromeRects() {
    if (chromeRectCache.frame === state.frame) {
      return chromeRectCache.rects;
    }
    const canvasRect = renderer.domElement.getBoundingClientRect();
    const rects = [];
    for (const id of CHROME_ELEMENT_IDS) {
      const element = document.getElementById(id);
      if (!element) {
        continue;
      }
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
        continue;
      }
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        continue;
      }
      // Canvas-relative, since label bounds are measured in canvas pixels.
      rects.push({
        left: rect.left - canvasRect.left,
        right: rect.right - canvasRect.left,
        top: rect.top - canvasRect.top,
        bottom: rect.bottom - canvasRect.top,
      });
    }
    chromeRectCache = { frame: state.frame, rects };
    return rects;
  }

  // The stage: the part of the canvas the rail on the left and the
  // inspector on the right leave uncovered. The camera centres the
  // selection in THIS, not in the canvas — with the inspector open, a brood
  // laid in the Executive's sector (down and to the right) was landing
  // under the panel on every expansion, so a reader saw edges leaving the
  // frame and nothing at the end of them. A tall chrome rect hugging an
  // edge is a column; anything else (the breadcrumb, the hint) is not.
  function stageGeometry() {
    const width = renderer.domElement.clientWidth || window.innerWidth;
    const height = renderer.domElement.clientHeight || window.innerHeight;
    let left = 0;
    let right = width;
    for (const rect of getChromeRects()) {
      if (rect.bottom - rect.top <= height * 0.5) {
        continue;
      }
      if (rect.left <= 2 && rect.right < width * 0.5) {
        left = Math.max(left, rect.right);
      } else if (rect.right >= width - 2 && rect.left > width * 0.5) {
        right = Math.min(right, rect.left);
      }
    }
    const usable = Math.max(right - left, width * 0.3);
    return { width, height, left, right, usable, centreOffsetPx: (left + right) / 2 - width / 2 };
  }

  // The world-space translation that puts the camera's focus at the
  // stage's centre rather than the canvas's: along the camera's own right
  // vector, by the stage offset scaled to the visible width at the focus
  // distance. Applied to the camera and its target together, so it is a
  // pure slide of the picture and changes nothing about the view's angle.
  const stageShiftVector = new THREE.Vector3();
  const cameraRightVector = new THREE.Vector3();

  // The distance at which a sphere of this reach fits both the vertical
  // field and the stage's uncovered width — whichever is tighter.
  function fitDistanceForReach(reach, halfFov) {
    const stage = stageGeometry();
    const aspect = stage.width / Math.max(stage.height, 1);
    const vertical = reach / Math.max(Math.tan(halfFov), 0.05);
    const horizontal = reach / Math.max(Math.tan(halfFov) * aspect * (stage.usable / stage.width), 0.05);
    return Math.max(vertical, horizontal);
  }

  function stageShift(distance, out = stageShiftVector) {
    const stage = stageGeometry();
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    const aspect = stage.width / Math.max(stage.height, 1);
    const visibleWidth = 2 * Math.tan(halfFov) * aspect * distance;
    const shift = -(stage.centreOffsetPx / stage.width) * visibleWidth;
    cameraRightVector.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
    return out.copy(cameraRightVector).multiplyScalar(shift);
  }

  // The screen rectangle the selected node's brood occupies, padded: a
  // context cluster's badge is kept out of it, so collapsed siblings never
  // sit over the children a reader just asked to see. Their rings stay.
  function broodScreenBounds(candidates) {
    let bounds = null;
    for (const candidate of candidates) {
      if (!candidate.brood || !candidate.sprite.visible) {
        continue;
      }
      const b = measureLabelBounds(candidate.sprite, candidate.priority);
      if (!bounds) {
        bounds = { left: b.left, right: b.right, top: b.top, bottom: b.bottom };
      } else {
        bounds.left = Math.min(bounds.left, b.left);
        bounds.right = Math.max(bounds.right, b.right);
        bounds.top = Math.min(bounds.top, b.top);
        bounds.bottom = Math.max(bounds.bottom, b.bottom);
      }
    }
    if (bounds) {
      bounds.left -= 24; bounds.right += 24; bounds.top -= 24; bounds.bottom += 24;
    }
    return bounds;
  }

  function suppressOverlappingLabels(candidates) {
    const accepted = [];
    const chrome = getChromeRects();
    const broodBounds = broodScreenBounds(candidates);
    candidates.sort((a, b) => b.priority - a.priority);
    for (const candidate of candidates) {
      if (!candidate.sprite.visible) {
        continue;
      }
      const bounds = measureLabelBounds(candidate.sprite, candidate.priority);
      let blocked = false;
      if (candidate.context && broodBounds && labelBoundsIntersect(bounds, broodBounds)) {
        blocked = true;
      }
      for (const chromeBounds of chrome) {
        if (blocked) break;
        if (labelBoundsIntersect(bounds, chromeBounds)) {
          blocked = true;
          break;
        }
      }
      if (!blocked) {
        for (const acceptedBounds of accepted) {
          if (labelBoundsIntersect(bounds, acceptedBounds)) {
            blocked = true;
            break;
          }
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
      sourceCount: Number(node.sourceCount || (Array.isArray(node.sourceUrls) ? node.sourceUrls.length : 0)),
      lastVerified: node.lastVerified || null,
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
    if (styleKey === "unsourced") {
      // Solid and slightly dimmer than verified: present, not discredited.
      return {
        color: baseColor.clone().lerp(whiteColor, 0.1),
        emissive: baseColor.clone().multiplyScalar(0.16),
        emissiveIntensity: 0.1,
        opacity: 0.78,
        wireframe: false,
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
    mesh.count = 0;
    scene.add(mesh);
    return {
      depth,
      radius,
      color,
      styleKey,
      profile,
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
    clusterMesh.count = 0;
    scene.add(clusterMesh);
    state.clusterBatch = {
      mesh: clusterMesh,
      clustersBySlot: new Array(CLUSTER_CAPACITY),
      lastActiveCount: 0,
      dirty: true,
    };

    const edgeCapacity = Math.max(state.totalNodeCount + (state.candidateNodeCount || 0) + state.relationships.length + 256, 1);
    const edgePositions = new Float32Array(edgeCapacity * 6);
    const edgeColors = new Float32Array(edgeCapacity * 6);
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute("color", new THREE.BufferAttribute(edgeColors, 3));
    // vertexColors, or the per-edge colour attribute above (and every
    // setEdgeColor / origin-trace tint) is ignored and edges render flat grey.
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0xffffff,
      vertexColors: true,
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
    const batchKey = `${nodeObj.depth}:${getNodeColor(nodeObj.data)}:${getVerificationStyleKey(nodeObj.data)}`;
    const batch = state.nodeBatches.get(batchKey);
    nodeObj.batch = batch;
    nodeObj.slot = batch.freeSlots.length > 0 ? batch.freeSlots.pop() : batch.nextSlot++;
    batch.nodesBySlot[nodeObj.slot] = nodeObj;
    // Draw/raycast only the slots ever assigned, not the full capacity.
    batch.mesh.count = batch.nextSlot;
  }

  function createNodeObj(data, parent, depth) {
    const layoutBranchKey = resolveLayoutBranchKey(data, parent?.layoutBranchKey || null);
    const nodeObj = {
      data,
      parent,
      depth,
      layoutBranchKey,
      branchDirection: new THREE.Vector3(),
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

    assignBatchSlot(nodeObj);
    state.nodeMap.set(data.id, nodeObj);
    state.nodeRenderMap.set(data.id, { mesh: nodeObj.batch.mesh, slot: nodeObj.slot });
    state.allNodes.add(nodeObj);
    return nodeObj;
  }

  function placeCandidateNode(nodeObj, index = 0, total = 1) {
    // Pack candidates over a bounded shell band via a golden-angle sphere
    // distribution so every candidate stays well inside the camera far plane
    // (a linearly growing radius pushed ~80% of them past it).
    const innerRadius = shellRadiusForDepth(1) + 30;
    const count = Math.max(total, 1);
    const t = (index + 0.5) / count;
    const y = 1 - 2 * t;
    const ringRadius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * (index + 1);
    const direction = new THREE.Vector3(
      Math.cos(theta) * ringRadius,
      y,
      Math.sin(theta) * ringRadius,
    ).normalize();
    const seed = hashString(nodeObj.data.id);
    const radius = innerRadius + (seed % 8) * 22;
    nodeObj.pos.copy(direction).multiplyScalar(radius);
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
    state.visibleNodes.add(nodeObj);
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
    state.visibleNodes.delete(nodeObj);
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
    // Under the Whole lens every node keeps one world size: the tier scale
    // and the distance scale exist to thin a far view, and this lens is the
    // reader asking to see all of it.
    // Under the Whole lens a node keeps roughly one SCREEN size: the tier
    // scale and the distance scale exist to thin a far view, and this lens
    // is the reader asking to see all of it from far away; closer in, the
    // dots shrink back toward the ordinary size rather than becoming balls.
    // A node nearer the camera than the focus looms: a brood is laid on a
    // sphere, so its near side sits between the camera and the selection
    // and, in perspective, a sibling a third of the way to the lens drew
    // as a translucent disc three times the size of the one it stood
    // beside. Nothing in the data is three times anything, so a node
    // inside the focus distance keeps the screen size it would have AT
    // the focus. Nodes beyond it are untouched.
    const focusDistance = Math.max(camera.position.distanceTo(state.camFocus), 1);
    const nearFactor = Math.min(1, cameraDistance / focusDistance);
    const finalScale = (state.lens === "whole"
      ? WHOLE_NODE_SCALE * THREE.MathUtils.clamp(cameraDistance / 1400, 0.3, 1) * scaleMultiplier
      : scaleMultiplier * zoomScale) * nearFactor;
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
    state.allEdges.add(edge);
    fromObj.edges.push(edge);
    toObj.edges.push(edge);
    if (edge.type === "hierarchy") {
      toObj.edgeToParent = edge;
    }
    hideEdge(edge);
    return edge;
  }

  // Under the Evidence lens a hierarchy edge is the placement claim for the
  // edge itself: bright green where the parent's own page (or a directory)
  // lists the child, grey where nothing checked it, and the ordinary dim
  // where the parent has no page to check. The edge's hue under every other
  // lens is the child's own verdict colour.
  function edgeLensColor(edge) {
    if (edge.type !== "hierarchy") {
      return null;
    }
    if (state.lens === "evidence") {
      const child = edge.to.data || {};
      if (child.placementVerified === true) {
        return EVIDENCE_COLORS.verified;
      }
      if (child.placementCheckable === false) {
        return "#3A4150";
      }
      return "#5A5E66";
    }
    return lensColorHex(edge.to.data);
  }

  function refreshEdgeColor(edge) {
    edge.color.copy(edge.baseColor);
    const lensHex = edgeLensColor(edge);
    if (lensHex) {
      edge.color.set(lensHex);
    }
    if (state.focusIds.size > 0) {
      const selected = state.selectedNode;
      if (edge.type === "hierarchy" && selected && edge.from === selected) {
        // The brood's own edges carry the child's hue, so the fan a reader
        // asked for is the brightest thing on the stage.
        edge.color.set(lensHex || getNodeColor(edge.to.data)).lerp(whiteColor, 0.1);
      } else if (state.lens !== "whole" && !(state.focusIds.has(edge.from.data.id) && state.focusIds.has(edge.to.data.id))) {
        edge.color.lerp(inkColor, 0.62);
      }
    }
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
    const zoomAllowed =
      edge.type === "relationship" ? state.lod.showRelationshipEdges : state.lod.showHierarchyEdges;
    if (edge.highlightVersion !== state.highlightVersion) {
      setEdgeColor(edge);
    }
    // Hierarchy edges keep the strict "<" on the parent side (the parent sits
    // one level above the child); relationship endpoints are arbitrary, so
    // both may legitimately sit at the max visible depth.
    const depthAllowed =
      edge.type === "relationship"
        ? edge.from.depth <= state.maxVisibleDepth && edge.to.depth <= state.maxVisibleDepth
        : edge.from.depth < state.maxVisibleDepth && edge.to.depth <= state.maxVisibleDepth;
    const show =
      zoomAllowed &&
      edge.from.renderVisible &&
      edge.to.renderVisible &&
      !edge.from.clustered &&
      !edge.to.clustered &&
      depthAllowed;
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

  function getOrbitBasis(anchorDir) {
    basisA.copy(anchorDir);
    if (Math.abs(basisA.dot(upVector)) > 0.92) {
      basisA.set(1, 0, 0);
    } else {
      basisA.cross(upVector).normalize();
    }
    basisB.copy(anchorDir).cross(basisA).normalize();
  }

  function relaxSiblingPositions(positions, shellRadius) {
    if (positions.length > RELAXATION_MAX_SIBLINGS) {
      // The golden-angle spiral already spreads large broods evenly; skipping
      // the O(k^2) pass keeps huge expansions (root: ~3.8K children) from
      // freezing the main thread.
      return;
    }
    const minimumDistance = Math.max(MIN_DISTANCE, NODE_RADIUS * 2.2);
    const minimumDistanceSq = minimumDistance * minimumDistance;

    for (let iteration = 0; iteration < 2; iteration += 1) {
      for (let i = 0; i < positions.length; i += 1) {
        for (let j = i + 1; j < positions.length; j += 1) {
          tempVecA.subVectors(positions[i], positions[j]);
          const distanceSq = tempVecA.lengthSq();
          if (distanceSq >= minimumDistanceSq) {
            continue;
          }

          if (distanceSq < 0.0001) {
            tempVecA.set(Math.sin(i + 1), Math.cos(j + 1), Math.sin(i + j + 1));
          }

          const distance = Math.sqrt(Math.max(distanceSq, 0.0001));
          const pushStrength = ((minimumDistance - distance) / minimumDistance) * (-REPULSION / 400);
          tempVecA.normalize().multiplyScalar(pushStrength);
          positions[i].add(tempVecA);
          positions[j].sub(tempVecA);
        }
      }

      for (const position of positions) {
        position.normalize().multiplyScalar(shellRadius * DAMPING + shellRadius * (1 - DAMPING));
      }
    }
  }

  function getLayoutDirectionForChild(childData, parentObj, childSeed) {
    const parentBranchKey = parentObj.layoutBranchKey || inferBranchKey(parentObj.data);
    const childBranchKey = resolveLayoutBranchKey(childData, parentBranchKey);
    const hasParentDirection = parentObj.branchDirection && parentObj.branchDirection.lengthSq() > 0;
    const parentDirection = hasParentDirection
      ? tempVecA.copy(parentObj.branchDirection).normalize()
      : parentObj.pos.lengthSq() > 0.0001
        ? tempVecA.copy(parentObj.pos).normalize()
        : copyBranchBaseDirection(parentBranchKey, tempVecA);
    const branchBase = copyBranchBaseDirection(childBranchKey, tempVecB);
    const seeded = directionFromSeed(childSeed, parentObj.depth + 1);
    // A sector of its own beneath a branch (the independent establishments,
    // the regulatory commissions) keeps its own direction: blending it toward
    // the Executive is what pulled it back into the branches' plane.
    const opensSector = childBranchKey !== parentBranchKey && SECTOR_BRANCH_KEYS.has(childBranchKey);

    return tempVecC
      .copy(branchBase)
      // No blend toward the parent at depth 0: the sector triangle IS the
      // intended arrangement there, and pulling it toward the Constitution's +Y
      // axis only collapses it back toward the flat arc it replaced.
      .lerp(parentDirection, parentObj.depth === 0 ? 0 : opensSector ? 0.06 : BRANCH_PARENT_BLEND)
      .addScaledVector(seeded, childBranchKey === parentBranchKey ? 0.08 : 0.14)
      .normalize();
  }

  function getSpreadPositions(parentObj, children) {
    const depth = parentObj.depth + 1;
    const shellRadius = shellRadiusForBrood(depth, children.length);
    const spreadCap = spreadCapForCount(children.length);
    const parentSeed = hashString(parentObj.data.id);
    // Own vector: getLayoutDirectionForChild reuses tempVecA inside the loop,
    // so aliasing the anchor to it would silently retarget the lerp below.
    const anchorDir =
      parentObj.pos.lengthSq() > 0.0001
        ? parentObj.pos.clone().normalize()
        : directionFromSeed(parentSeed, depth);

    const count = children.length;
    const positions = new Array(count);
    const directions = new Array(count);

    for (let i = 0; i < count; i += 1) {
      const childSeed = hashString(children[i].id);
      const theta = GOLDEN_ANGLE * (i + 1);
      const radial = Math.min(spreadCap, 0.08 + Math.sqrt((i + 0.5) / Math.max(count, 1)) * spreadCap * 0.72);
      const shellDirection = directionFromSeed(childSeed, depth);
      const branchDirection = getLayoutDirectionForChild(children[i], parentObj, childSeed).clone();
      getOrbitBasis(branchDirection);
      const childOpensSector =
        SECTOR_BRANCH_KEYS.has(resolveLayoutBranchKey(children[i], parentObj.layoutBranchKey || inferBranchKey(parentObj.data))) &&
        !SECTOR_BRANCH_KEYS.has(parentObj.layoutBranchKey || inferBranchKey(parentObj.data));
      directionVec
        .copy(branchDirection)
        .lerp(anchorDir, childOpensSector ? 0.02 : parentObj.depth > 0 ? 0.18 : 0.06)
        .addScaledVector(basisA, Math.cos(theta) * radial)
        .addScaledVector(basisB, Math.sin(theta) * radial)
        .addScaledVector(shellDirection, 0.12)
        .normalize();

      positions[i] = directionVec.clone().multiplyScalar(shellRadius);
      directions[i] = branchDirection;
    }

    relaxSiblingPositions(positions, shellRadius);
    return positions.map((position, index) => ({
      position,
      shellRadius,
      direction: positions[index].clone().normalize().lerp(directions[index], 0.28).normalize(),
      layoutBranchKey: resolveLayoutBranchKey(children[index], parentObj.layoutBranchKey || inferBranchKey(parentObj.data)),
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
      seenChildIds: new Set(),
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
      const conflictingReuse =
        childObj &&
        (childObj.isCandidate ||
          childObj === state.rootObj ||
          (childObj.parent && childObj.parent !== parentObj));
      if (conflictingReuse || job.seenChildIds.has(childData.id)) {
        // Duplicate id already instantiated elsewhere (second placement in the
        // data, or a candidate collision): keep the first render node instead
        // of silently reparenting/teleporting the shared object.
        job.seenChildIds.add(childData.id);
        job.index += 1;
        processedChildren += 1;
        if (job.index >= children.length) {
          parentObj.expanded = true;
          parentObj.expanding = false;
          state.pendingExpansions.shift();
        }
        continue;
      }
      job.seenChildIds.add(childData.id);
      if (!childObj) {
        childObj = createNodeObj(childData, parentObj, parentObj.depth + 1);
        setNodeColor(childObj);
        connectRelationshipsForNode(childObj);
      }

      childObj.parent = parentObj;
      parentObj.childObjs.push(childObj);
      markVisible(childObj);

      const placement = placements[job.index];
      const targetPos = placement.position;
      childObj.layoutBranchKey = placement.layoutBranchKey;
      // Without this the settle pass below drags the brood back to the
      // depth-only radius every frame, undoing the spread and moving nodes
      // while it does it.
      childObj.shellRadius = placement.shellRadius;
      childObj.branchDirection.copy(placement.direction);
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

  // `byReader` marks an expansion a reader asked for -- a button, the
  // children list, a folded group clicked open, a search or a link -- as
  // opposed to the boot expansion. What a reader opened stays laid out:
  // `isProtectedFromClustering` never folds it or its children into a group
  // ring until the reader collapses it (since 2026-10-21; see there).
  function expandNodesBatch(nodes, animate = true, byReader = false) {
    const expandedParents = [];
    for (const nodeObj of nodes.slice(0, EXPANSION_PARENT_BATCH)) {
      if (byReader && nodeObj) {
        nodeObj.readerOpened = true;
      }
      if (nodeObj.expanded || nodeObj.expanding) {
        continue;
      }
      queueExpansion(nodeObj, animate);
      expandedParents.push(nodeObj);
    }
    flushPendingExpansions(10, 1024);
    return expandedParents;
  }

  function expandNode(nodeObj, animate = true, byReader = false) {
    return expandNodesBatch([nodeObj], animate, byReader);
  }

  function disposeNodeObject(nodeObj) {
    if (nodeObj.batch) {
      nodeObj.batch.nodesBySlot[nodeObj.slot] = null;
      nodeObj.batch.freeSlots.push(nodeObj.slot);
    }
    state.nodeMap.delete(nodeObj.data.id);
    state.nodeRenderMap.delete(nodeObj.data.id);
    state.allNodes.delete(nodeObj);
    markHidden(nodeObj);
  }

  function removeEdge(edge) {
    hideEdge(edge);
    state.edgeBatch.freeSlots.push(edge.slot);
    state.allEdges.delete(edge);
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

    // Iterative subtree walk with a single counts notification: the recursive
    // version re-filtered the queue and fired notifyCounts once per descendant.
    const stack = [...parentObj.childObjs];
    while (stack.length > 0) {
      const child = stack.pop();
      for (const grandChild of child.childObjs) {
        stack.push(grandChild);
      }
      child.childObjs = [];
      child.expanded = false;
      child.expanding = false;
      for (const edge of [...child.edges]) {
        removeEdge(edge);
      }
      disposeNodeObject(child);
    }
    parentObj.childObjs = [];
    parentObj.expanded = false;
    parentObj.expanding = false;
    parentObj.readerOpened = false;
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
    if (isBranchRoot(nodeObj.data)) {
      return true;
    }
    if (state.highlightedPathIds.has(nodeObj.data.id)) {
      return true;
    }
    // What a reader opened stays laid out. Protection used to follow the
    // SELECTION alone, so expanding the Cabinet drew its fifteen departments
    // and clicking one of them to read it folded the other fourteen into
    // group rings (22 nodes drawn -> 7, measured 2026-10-21): they were no
    // longer the selection's ancestors or descendants. A node the reader
    // expanded, and every child it laid out, is never folded until the
    // reader collapses it; the boot expansion and the distant tree still
    // cluster as before.
    if (nodeObj.readerOpened || nodeObj.parent?.readerOpened) {
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

    const candidates = [...state.allNodes]
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

    // A folded group clicked open is a reader's request for what is inside.
    expandNode(sourceNode, true, true);
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

  // The orbit zoom at which the LOD tier draws a node of this depth. The
  // tiers are keyed on camera distance (lodManager.thresholds), and each
  // caps the depth it draws: Agency View stops at depth 3, so a depth-8
  // node selected from a search was drawn alone, exempt as the selection,
  // with every ancestor between it and the department hidden. Flying to a
  // node means getting close enough that its tier shows its level.
  function zoomForDepth(depth) {
    const levels = lodManager.levels;
    const ceilings = [
      lodManager.thresholds.COSMIC_VIEW,
      lodManager.thresholds.BRANCH_VIEW,
      lodManager.thresholds.AGENCY_VIEW,
      lodManager.thresholds.OFFICE_VIEW,
    ];
    for (let level = 0; level < levels.length; level += 1) {
      if (depth <= levels[level].maxDepth) {
        if (level === 0) {
          return 0;
        }
        // Inside the ceiling by a margin, so a settling camera does not sit
        // on the boundary and flicker between tiers.
        return CAMERA_DISTANCE / (ceilings[level - 1] * 0.9);
      }
    }
    return CAMERA_DISTANCE / (ceilings[ceilings.length - 1] * 0.9);
  }

  function focusNode(nodeObj) {
    if (!nodeObj) {
      return;
    }
    state.lastUserDrillAt = performance.now();
    if (state.flyMode) {
      const focusPoint = nodeObj.pos;
      const backward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA).multiplyScalar(-Math.max(22, nodeObj.radius ? nodeObj.radius * 5 : 28));
      state.flyPosition.copy(focusPoint).add(backward);
      setFlyLookAt(focusPoint);
      return;
    }
    // A node whose children are already on the stage is framed WITH them:
    // selecting the Cabinet from the search box used to zoom to the node
    // itself at Position View, with its fifteen departments laid on a shell
    // a hundred units out and every one of them outside the frame — the
    // inspector listed fifteen sub-units and the picture showed fifteen
    // edges leaving it. The children are what a reader selected it to see.
    if (nodeObj.expanded && (nodeObj.childObjs || []).some((child) => child.visible)) {
      frameBroodOf(nodeObj);
      return;
    }
    state.camFocusTarget.copy(nodeObj.pos);
    // Never pulls the camera outward: a reader who zoomed in stays in.
    state.targetZoom = Math.max(state.targetZoom, 1.45, zoomForDepth(nodeObj.depth));
    state.renderDirty = true;
  }

  // Frame a node's children, rather than the node. `focusNode` centres the
  // selection and never pulls the camera outward, which is right for a
  // selection and wrong for an expansion: pressing "Expand All Below" on the
  // White House Office, whose 249 children sit on a shell 374 units across,
  // drew a fan of edges running off every side of the frame with nothing
  // visible at the far end of any of them -- the children were placed, drawn
  // and outside the view. Measured 2026-09-22 at 1400x900: 74 of 1,122 loaded
  // nodes on screen after the expansion, against 249 children asked for.
  //
  // So an explicit expansion -- and only an expansion -- is allowed to pull
  // the camera back far enough to hold the brood. The rule `focusNode`
  // states still governs selection, where a reader who zoomed in stays in.
  function frameBroodOf(nodeObj) {
    if (!nodeObj) {
      return;
    }
    const children = nodeObj.childObjs || [];
    if (!children.length) {
      focusNode(nodeObj);
      return;
    }
    state.lastUserDrillAt = performance.now();
    if (state.flyMode) {
      focusNode(nodeObj);
      return;
    }
    // Frame the brood, not the parent. `getSpreadPositions` lays children on
    // a CONE rather than a full sphere -- a half-angle of 0.42 radians for a
    // small brood, widening to 0.95 for a large one -- so a camera centred on
    // the parent puts the whole brood to one side and leaves half the frame
    // empty. The focus point is the middle of what has to be held: the
    // parent and its children together.
    //
    // `targetPos`, not `pos`: a brood expanded a frame ago is still animating
    // out of the parent's own position, so measuring `pos` would fit the
    // camera to a sphere of radius nearly zero and slam it into the parent.
    const centroid = new THREE.Vector3().copy(nodeObj.pos);
    for (const childObj of children) {
      centroid.add(childObj.targetPos || childObj.pos);
    }
    centroid.divideScalar(children.length + 1);
    let reach = centroid.distanceTo(nodeObj.pos);
    for (const childObj of children) {
      const where = childObj.targetPos || childObj.pos;
      reach = Math.max(reach, where.distanceTo(centroid));
    }
    if (reach <= 0) {
      focusNode(nodeObj);
      return;
    }
    state.camFocusTarget.copy(centroid);
    // Vertical half-angle of the frustum, with a margin so the outermost
    // child sits inside the frame and not on its edge.
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    const fitDistance = fitDistanceForReach(reach * 1.25, halfFov);
    const fitZoom = CAMERA_DISTANCE / Math.max(fitDistance, 1);
    state.targetZoom = THREE.MathUtils.clamp(fitZoom, minZoom(), 10);
    state.renderDirty = true;
  }

  // Frame what "Expand All Below" put on the stage: the node, its children
  // and every visible descendant, bounded, rather than the first generation
  // alone -- the grandchildren sit on larger shells and were landing outside
  // a frame fitted to the brood. Same rule as frameBroodOf otherwise: only an
  // explicit expansion may pull the camera back.
  function frameSubtreeOf(nodeObj, maxNodes = 900) {
    if (!nodeObj || state.flyMode) {
      frameBroodOf(nodeObj);
      return;
    }
    const points = [];
    const queue = [nodeObj];
    while (queue.length && points.length < maxNodes) {
      const current = queue.shift();
      // `visible` only, never `culled`: culling is last frame's frustum
      // result, and a child the old camera could not see is exactly the one
      // the new frame has to hold.
      if (current !== nodeObj && !current.visible) {
        continue;
      }
      points.push(current.targetPos && current.targetPos.lengthSq() > 0 ? current.targetPos : current.pos);
      for (const childObj of current.childObjs || []) {
        queue.push(childObj);
      }
    }
    if (points.length < 2) {
      frameBroodOf(nodeObj);
      return;
    }
    // Not a drill. `frameBroodOf` stamps `lastUserDrillAt` and this copied
    // it, which let `ensureLodCoverage` open any unexpanded node within the
    // auto-expand distance of the selection for four seconds after the
    // camera pulled back — "Expand All Below" on the Interior finished by
    // loading the Council of Economic Advisers' whole brood, 95 nodes
    // outside the subtree the button promised (the smoke check that
    // measures this now compares ids, not counts, and caught it).
    const centroid = new THREE.Vector3();
    for (const point of points) {
      centroid.add(point);
    }
    centroid.divideScalar(points.length);
    // Pulled a third of the way back toward the node itself: a deep subtree's
    // centroid sits among the grandchildren, and the node the reader expanded
    // was landing on the frame's edge.
    centroid.lerp(nodeObj.pos, 0.35);
    let reach = 0;
    for (const point of points) {
      reach = Math.max(reach, point.distanceTo(centroid));
    }
    if (reach <= 0) {
      frameBroodOf(nodeObj);
      return;
    }
    state.camFocusTarget.copy(centroid);
    const halfFov = THREE.MathUtils.degToRad(camera.fov) / 2;
    const fitDistance = fitDistanceForReach(reach * 1.15, halfFov);
    const fitZoom = CAMERA_DISTANCE / Math.max(fitDistance, 1);
    state.targetZoom = THREE.MathUtils.clamp(fitZoom, minZoom(), 10);
    state.renderDirty = true;
  }

  function setDepthFilter(depth) {
    state.manualDepthFilter = Number.isFinite(depth) ? Math.min(depth, MAX_DEPTH) : MAX_DEPTH;
    updateLodState();
    state.renderDirty = true;
    refreshVisibility();
  }

  // The shallowest unexpanded, child-bearing nodes — the next level a
  // progressive expansion should open. With `scopeObj` the search is confined
  // to that node's own subtree: "Expand All Below" on the Department of the
  // Interior used to walk this over every loaded node and open all 5,402,
  // because nothing told it "below" meant below the selection.
  function getFrontier(targetDepth = Infinity, scopeObj = null) {
    const boundedDepth = Number.isFinite(targetDepth) ? Math.min(targetDepth, MAX_DEPTH) : MAX_DEPTH;
    let minDepth = Infinity;
    const frontier = [];

    for (const nodeObj of state.visibleNodes) {
      if (nodeObj.expanded || nodeObj.expanding || nodeObj.depth >= boundedDepth) {
        continue;
      }
      if (scopeObj && !isDescendantOf(nodeObj, scopeObj)) {
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

  // Contract: the return value is deterministic. A node object means the node
  // is materialized; null means it can never materialize (unknown id, or an
  // ancestor could not be built) — callers such as ui.js revealAndSelect must
  // treat null as terminal failure and stop retrying.
  function revealNodeById(id, animate = true) {
    if (!state.dataMap.has(id)) {
      return null;
    }
    // A hidden candidate cannot be shown: selecting it flew the camera to an
    // empty point. Deterministic failure, per this function's contract.
    if (state.dataMap.get(id)?.isCandidate && !state.showCandidateNodes) {
      return null;
    }

    const pathIds = getPathIds(id);
    state.lastUserDrillAt = performance.now();
    for (let i = 0; i < pathIds.length - 1; i += 1) {
      const ancestorId = pathIds[i];
      let ancestorObj = state.nodeMap.get(ancestorId);
      // The ancestor may still be waiting in the expansion queue (budgeted
      // flushes can leave large parents partially built); drain the queue so
      // the path cannot be silently skipped by an expansion-budget race.
      while (!ancestorObj && state.pendingExpansions.length > 0) {
        flushPendingExpansions(Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
        ancestorObj = state.nodeMap.get(ancestorId);
      }
      if (!ancestorObj) {
        return null;
      }
      // The path to a searched or linked node is what the reader asked for.
      if (ancestorObj.depth < MAX_DEPTH) {
        expandNode(ancestorObj, animate, true);
      }
      flushPendingExpansions(Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
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

    if (isBranchRoot(nodeObj.data)) {
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
    // A collapsed subtree's ring is a hint of how much sits folded beneath
    // a node, and at 92px across fifteen of them in one brood were larger
    // than the spacing between the siblings they stood beside — the Cabinet
    // read as a pile of discs with the departments somewhere behind them.
    const maxPixelFootprint = clusterObj.kind === "positions" ? 48 : 60;
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

  // A cluster outside the focus set is context: its ring is tinted toward the
  // ink and drawn at three quarters, so a selected node's own brood reads
  // over the collapsed siblings beside it instead of under their rings.
  function clusterIsContext(clusterObj) {
    return state.focusIds.size > 0 && !state.focusIds.has(clusterObj?.data?.sourceId);
  }

  function setClusterSlot(slot, clusterObj) {
    const context = clusterIsContext(clusterObj);
    const scale = Math.max(2.4, clusterObj.displayRadius || clusterObj.radius) * (context ? 0.5 : 1);
    tempQuat.copy(camera.quaternion);
    tempMat4.compose(
      clusterObj.displayPos || clusterObj.pos,
      tempQuat,
      tempScale.set(scale, scale, Math.max(0.7, clusterObj.tubeThickness || 1)),
    );
    state.clusterBatch.mesh.setMatrixAt(slot, tempMat4);
    state.clusterBatch.mesh.setColorAt(
      slot,
      tempClusterColor.set(clusterObj.color || clusterColor).lerp(clusterAccentColor, 0.08).lerp(inkColor, context ? 0.72 : 0),
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

  function updateClusterLabels(protectedIds = getProtectedNodeIds()) {
    ensureClusterLabelPool(state.activeClusters.length);
    const candidates = [];
    let labelIndex = 0;
    for (const clusterObj of state.activeClusters) {
      if (!clusterObj.renderVisible || labelIndex >= state.clusterLabels.length) {
        continue;
      }

      const label = state.clusterLabels[labelIndex];
      const title = clusterObj.data.clusterLabel || clusterObj.data.name;
      const subtitle = clusterObj.data.clusterCountLabel || getClusterCountLabel(clusterObj);
      const context = clusterIsContext(clusterObj);
      drawClusterLabel(label, title, subtitle, clusterObj.color || "#d3c29a");
      label.sprite.visible = true;
      label.sprite.position.copy(clusterObj.pos);
      label.sprite.position.y += Math.max(8, clusterObj.radius + 5) * (context ? 0.72 : 1);
      const labelScale = getLabelDistanceScale(label.sprite.position) * (context ? 0.72 : 1);
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
      candidates.push({ sprite: label.sprite, priority, context });
      labelIndex += 1;
    }

    for (let i = labelIndex; i < state.clusterLabels.length; i += 1) {
      state.clusterLabels[i].sprite.visible = false;
    }
    return candidates;
  }

  // Under the Whole lens a branch's caption sits at the centre of the mass
  // it describes — the mean position of everything drawn beneath it —
  // rather than on the branch node itself, which sits beside the root where
  // the four halos overlap and the overlap pass kept only one of them.
  function wholeMassCentres() {
    const sums = new Map();
    for (const nodeObj of state.visibleNodes) {
      if (!nodeObj.renderVisible || nodeObj.culled || nodeObj.depth < 2) {
        continue;
      }
      // The nearest captioned ancestor below the root: a branch, or one of
      // the Executive's two sectors.
      let cursor = nodeObj.parent;
      while (cursor && cursor.depth > 0 && !state.lod.haloNodeIds?.has(cursor.data?.id)) {
        cursor = cursor.parent;
      }
      if (!cursor || cursor.depth === 0) {
        continue;
      }
      let entry = sums.get(cursor.data.id);
      if (!entry) {
        entry = { sum: new THREE.Vector3(), count: 0 };
        sums.set(cursor.data.id, entry);
      }
      entry.sum.add(nodeObj.pos);
      entry.count += 1;
    }
    const centres = new Map();
    for (const [id, entry] of sums) {
      if (entry.count >= 8) {
        const centre = entry.sum.divideScalar(entry.count);
        // On the sphere a patch's centroid sinks toward the middle, where
        // every caption then fought over the same few pixels and the
        // overlap pass dropped all but one. Push it out along its own
        // direction, so each caption sits over its patch.
        if (state.wholeLayoutApplied && centre.lengthSq() > 1) {
          centre.normalize().multiplyScalar(WHOLE_SPHERE_RADIUS * 0.72);
        }
        centres.set(id, centre);
      }
    }
    return centres;
  }

  function updateHaloNodes(protectedIds = getProtectedNodeIds()) {
    const haloCandidates = [...state.visibleNodes].filter(
      (nodeObj) => nodeObj.renderVisible && lodManager.shouldRenderHalo(nodeObj, state.lod),
    );
    ensureHaloPool(haloCandidates.length);
    const labelCandidates = [];
    const massCentres = state.lens === "whole" ? wholeMassCentres() : null;

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

      drawHaloLabel(haloLabel, nodeObj.data.name, state.lens === "whole" ? wholeCaption(nodeObj.data) : nodeObj.data.type || "Institution", color);
      haloLabel.sprite.visible = true;
      const massCentre = massCentres && massCentres.get(nodeObj.data.id);
      haloLabel.sprite.position.copy(massCentre || nodeObj.pos);
      haloLabel.sprite.position.y += massCentre ? 0 : haloRadius + 14;
      const labelScale = getLabelDistanceScale(haloLabel.sprite.position);
      haloLabel.sprite.scale.set(22 * labelScale, 7 * labelScale, 1);
      let priority = 50_000;
      if (state.lens === "whole") {
        // Under Whole the captions are the labels and the selection is
        // incidental: a branch's caption first, then a sector's, then the
        // root's, whatever is selected — with the old order a selected
        // sector's caption knocked the Legislative Branch's off the sphere.
        priority = nodeObj.depth === 1 ? 2_000_000 : massCentre ? 1_800_000 : 1_600_000;
        labelCandidates.push({ sprite: haloLabel.sprite, priority });
        continue;
      }
      if (massCentre) {
        // The caption is what this lens is for: it wins over the root's.
        priority += 400_000;
      }
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

    // Report whether any cluster is still lerping toward its target so the
    // caller can keep visibility passes running until the animation settles.
    for (const clusterObj of nextClusters) {
      if (
        clusterObj.displayPos.distanceToSquared(clusterObj.targetPos) > 0.01 ||
        Math.abs(clusterObj.displayRadius - clusterObj.targetRadius) > 0.05
      ) {
        return true;
      }
    }
    return false;
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
    if (!state.rootObj || !state.lod.autoExpand || state.pendingExpansions.length > 8) {
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

  function isNodeRenderableAtCurrentLod(nodeObj) {
    // The selected node is exempt from depth/tier filtering so search and
    // selection can never point at an invisible node.
    if (nodeObj === state.selectedNode && nodeObj.visible) {
      return true;
    }
    // ...and so are its own children, for the reason `frameBroodOf` exists.
    // The tier is a function of camera DISTANCE, so pulling back far enough
    // to hold a wide brood is exactly what drops the tier and stops the
    // brood being drawn: framing the White House Office's 249 children took
    // the view from Office View to Branch View and the drawn count from 74
    // to 11. Zooming out to see something cannot be the thing that hides it.
    //
    // Bounded to one brood, never a subtree, so the cost is the selection's
    // own child count -- 249 at the worst node in this graph. The two user
    // choices above the tier still stand: an explicit depth filter wins
    // (that is a reader saying how deep to go, not the camera guessing), and
    // the verification toggles decide what may be shown at all.
    if (
      nodeObj.visible &&
      state.selectedNode &&
      nodeObj.parent === state.selectedNode &&
      state.manualDepthFilter >= MAX_DEPTH
    ) {
      return shouldDisplayNodeByVerification(nodeObj.data);
    }
    return lodManager.shouldRenderNode(nodeObj, state.lod) && shouldDisplayNodeByVerification(nodeObj.data);
  }

  function applyRenderVisibility() {
    if (!state.clusterBatch) {
      return;
    }
    updateLodState();
    updateFrustum();
    const protectedIds = getProtectedNodeIds();
    const lodVisibleNodes = [];
    for (const nodeObj of state.visibleNodes) {
      if (isNodeRenderableAtCurrentLod(nodeObj)) {
        lodVisibleNodes.push(nodeObj);
      }
    }
    state.screenSpaceBuckets = computeScreenSpaceBuckets(lodVisibleNodes);
    const clustersSettling = recomputeClusters();
    const baseEdgeOpacity = state.lod.level <= 1 ? 0.34 : state.zoom <= 1 ? 0.24 : 0.3;
    state.edgeBatch.lines.material.opacity =
      state.lens === "whole"
        // 5,510 edges at the ordinary opacity are a white web over the
        // masses they connect; faint, they read as the shape of the tree.
        ? 0.1
        : state.highlightedPathEdgeSlots.size > 0 || state.focusIds.size > 0 ? Math.max(baseEdgeOpacity, 0.5) : baseEdgeOpacity;
    const nodeCandidates = [];

    for (const nodeObj of state.allNodes) {
      nodeObj.renderVisible = false;
      if (!isNodeRenderableAtCurrentLod(nodeObj) || nodeObj.clustered) {
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

    applyDensityCap(nodeCandidates, protectedIds);
    // What is actually on screen this pass. "5,402 / 5,402 nodes rendered"
    // used to be printed while the Agency tier drew depth 3 and nothing
    // below it: the loaded count and the drawn count are different numbers,
    // and the counter has to carry both.
    let drawnCount = 0;
    for (const nodeObj of nodeCandidates) {
      if (nodeObj.densityCapped && nodeObj !== state.selectedNode && nodeObj !== state.rootObj) {
        hideNodeInstance(nodeObj);
        continue;
      }
      drawnCount += 1;
      setNodeMatrix(nodeObj, lensScaleOf(nodeObj));
    }
    for (const nodeObj of state.allNodes) {
      if (nodeObj.renderVisible && !nodeObj.culled && lodManager.shouldRenderHalo(nodeObj, state.lod)) {
        drawnCount += 1;
      }
    }
    const drawnChanged = drawnCount !== state.drawnNodeCount;
    state.drawnNodeCount = drawnCount;

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
    for (let i = clusterSlot; i < state.clusterBatch.lastActiveCount; i += 1) {
      if (state.clusterBatch.clustersBySlot[i]) {
        hideClusterSlot(i);
      }
    }
    // Only the live cluster slots are drawn and raycast; the remaining
    // capacity (up to 16,384 instances) is skipped entirely.
    state.clusterBatch.lastActiveCount = clusterSlot;
    state.clusterBatch.mesh.count = clusterSlot;

    refreshFocus();
    const clusterLabelCandidates = updateClusterLabels(protectedIds);
    const haloLabelCandidates = updateHaloNodes(protectedIds);
    const broodLabelCandidates = updateBroodLabels(protectedIds);
    suppressOverlappingLabels([...clusterLabelCandidates, ...haloLabelCandidates, ...broodLabelCandidates]);

    for (const edge of state.allEdges) {
      applyEdgeVisibility(edge);
    }

    updatePathGlowMeshes();

    state.renderDirty = clustersSettling;
    if (drawnChanged) {
      notifyCounts();
    }
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

  function updateDynamicInstances(positionsChanged = false) {
    if (!state.clusterBatch) {
      return;
    }
    // Only rewrite instance matrices, edge positions, and glow meshes when
    // node positions actually moved this frame; otherwise this forced a full
    // edge-buffer reupload every frame.
    if (positionsChanged) {
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
    return anyAnimating;
  }

  function applyWebForces() {
    // The sphere is an exact layout; the forces would pull each node back
    // toward its expansion-layout shell.
    if (state.frame % 2 !== 0 || state.wholeLayoutApplied) {
      return false;
    }

    let updated = false;
    for (const nodeObj of state.visibleNodes) {
      if (nodeObj.depth === 0 || nodeObj.isCandidate || nodeObj.animating || !nodeObj.renderVisible || nodeObj.clustered) {
        continue;
      }

      const desiredRadius = nodeObj.shellRadius || shellRadiusForDepth(nodeObj.depth);
      const branchTarget =
        nodeObj.branchDirection.lengthSq() > 0
          ? tempVecD.copy(nodeObj.branchDirection).normalize().multiplyScalar(desiredRadius)
          : null;
      const outwardTarget =
        nodeObj.targetPos.lengthSq() > 0
          ? tempVecA.copy(nodeObj.targetPos).normalize().multiplyScalar(desiredRadius)
          : tempVecA.copy(nodeObj.pos).normalize().multiplyScalar(desiredRadius);

      if (outwardTarget.lengthSq() === 0) {
        continue;
      }

      tempVecC.copy(nodeObj.pos);
      if (branchTarget) {
        nodeObj.pos.lerp(branchTarget, BRANCH_FORCE);
      }
      nodeObj.pos.lerp(outwardTarget, OUTWARD_FORCE);

      if (nodeObj.parent) {
        tempVecB.subVectors(nodeObj.pos, nodeObj.parent.pos);
        const distance = tempVecB.length();
        if (distance < LINK_DISTANCE && distance > 0.0001) {
          tempVecB.normalize().multiplyScalar((LINK_DISTANCE - distance) * 0.08);
          nodeObj.pos.add(tempVecB);
        }
      }

      // Settle below an epsilon so the asymptotic lerp cannot keep the whole
      // render pipeline dirty forever once nodes have effectively converged.
      if (nodeObj.pos.distanceToSquared(tempVecC) > WEB_FORCE_SETTLE_EPSILON_SQ) {
        updated = true;
      } else {
        nodeObj.pos.copy(tempVecC);
      }
    }

    if (updated) {
      state.renderDirty = true;
    }
    return updated;
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

    // Under Whole the sphere turns slowly on its own until the reader takes
    // hold of it, and again a few seconds after they let go — a presentation
    // shows a sphere without anybody having to drag it.
    if (state.wholeLayoutApplied && !state.flyMode && now - state.lastInteractionAt > 4000) {
      state.targetRotY += Math.min(deltaSeconds, 0.05) * 0.12;
      state.renderDirty = true;
    }
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
      // The orbit position is lerped on its own and never carries the stage
      // shift: the first version added the shift to camera.position after
      // the lerp, and since the lerp only pulls 8% of the way back each
      // frame the shift compounded twelve-fold — the camera settled far off
      // to one side at a distance the LOD read as Office View, and a post
      // selected from the search box rendered as a "Position Cluster".
      state.orbitPosition.lerp(desiredCameraPosition, ORBIT_CAMERA_LERP);
      camera.position.copy(state.orbitPosition);
      camera.lookAt(state.camFocus);
      // Slide the picture so the focus sits in the uncovered stage. Read
      // off the matrix the lookAt just set, then applied to both ends.
      camera.updateMatrixWorld();
      stageShift(distance);
      camera.position.add(stageShiftVector);
      camera.lookAt(tempVecD.copy(state.camFocus).add(stageShiftVector));
    }
    camera.updateMatrixWorld();
    // Depth fog on the sphere, so the far hemisphere sinks into the ink
    // behind the near one instead of interleaving its colours with it.
    if (state.wholeLayoutApplied) {
      const centreDistance = camera.position.length();
      if (!scene.fog) {
        scene.fog = new THREE.Fog(0x0a0e14, 1, 2);
      }
      scene.fog.near = Math.max(1, centreDistance - WHOLE_SPHERE_RADIUS * 0.4);
      scene.fog.far = centreDistance + WHOLE_SPHERE_RADIUS * 1.15;
    } else if (scene.fog) {
      scene.fog = null;
    }
    updateLodState();
    ensureLodCoverage();

    const nodesAnimated = animateNodes();
    const forcesUpdated = applyWebForces();

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

    if (state.clusterBatch && (state.renderDirty || state.forceFullRenderRefresh)) {
      applyRenderVisibility();
      state.forceFullRenderRefresh = false;
    }

    updateDynamicInstances(nodesAnimated || forcesUpdated);

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
      state.lastInteractionAt = performance.now();
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
      state.lastInteractionAt = performance.now();
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

    // mouseup only: binding the same handler to both mouseup and click made
    // every selection run twice (double raycast, double onSelect).
    canvas.addEventListener("mouseup", handleSelection);

    canvas.addEventListener(
      "wheel",
      (event) => {
        state.lastInteractionAt = performance.now();
        if (state.flyMode) {
          const forward = getForwardFromAngles(state.flyYaw, state.flyPitch, tempVecA);
          const zoomStep = event.deltaY > 0 ? -16 : 16;
          state.flyPosition.addScaledVector(forward, zoomStep);
          updateFlyLookTarget();
        } else {
          // Scroll down zooms out, scroll up zooms in (matches fly mode).
          state.targetZoom *= event.deltaY > 0 ? 0.9 : 1.1;
          state.targetZoom = Math.max(minZoom(), Math.min(10, state.targetZoom));
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

    const isTypingTarget = (event) => Boolean(event.target?.closest?.("input, textarea, select, [contenteditable]"));
    window.addEventListener("keydown", (event) => {
      if (isTypingTarget(event)) {
        return;
      }
      if (event.code in state.keyState) {
        state.keyState[event.code] = true;
      }
      if (event.code === "Space" && state.flyMode) {
        stopFlyMovement();
      }
    });

    window.addEventListener("keyup", (event) => {
      if (isTypingTarget(event)) {
        return;
      }
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
    // Drop candidates whose ids collide with real tree nodes so a hidden
    // candidate stub can never alias (and hijack) an actual hierarchy node.
    const candidateList = (data.candidateNodes || []).filter(
      (candidateNode) => !state.dataMap.has(candidateNode.id),
    );
    for (const candidateNode of candidateList) {
      registerCandidateNode(candidateNode);
    }
    // Candidates are the review queue, not the graph: 3,812 unreviewed
    // records must not read as "9,042 total nodes" on a 5,170-node site.
    state.totalNodeCount = meta.subtreeCount;
    state.candidateNodeCount = candidateList.length;
    state.maxDataDepth = Math.min(data.__meta.maxDepth, MAX_DEPTH);
    state.maxNodes = MAX_NODES;
    state.manualDepthFilter = MAX_DEPTH;
    state.maxVisibleDepth = MAX_DEPTH;

    ensureNodeBatches();
    indexRelationships(data.relationships || []);

    state.rootObj = createNodeObj(data, null, 0);
    setNodeColor(state.rootObj);
    state.rootObj.layoutBranchKey = "constitution";
    copyBranchBaseDirection("constitution", state.rootObj.branchDirection);
    state.rootObj.pos.set(0, 0, 0);
    state.rootObj.targetPos.set(0, 0, 0);
    setNodeMatrix(state.rootObj, 1);
    markVisible(state.rootObj);
    connectRelationshipsForNode(state.rootObj);
    for (const [index, candidateData] of candidateList.entries()) {
      const candidateObj = createNodeObj(candidateData, null, 1);
      setNodeColor(candidateObj);
      placeCandidateNode(candidateObj, index, candidateList.length);
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
    // Every caller outside this file is a reader's action, so the exported
    // functions mark what they open (`byReader`); the boot expansion calls
    // the inner ones directly and does not.
    expandNode(nodeObj, animate = true) {
      return expandNode(nodeObj, animate, true);
    },
    expandNodesBatch(nodes, animate = true) {
      return expandNodesBatch(nodes, animate, true);
    },
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
    setShowSupersededNodes(enabled) {
      state.showSupersededNodes = Boolean(enabled);
      state.renderDirty = true;
      refreshVisibility(true);
      return state.showSupersededNodes;
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
      focusNode(state.selectedNode);
    },
    focusNode,
    frameBroodOf,
    frameSubtreeOf,
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
    // The ids actually drawn this frame. Exposed so a regression check can
    // assert that a still camera produces a still picture: the density cap is
    // recomputed every frame from screen-tile membership, and when it is
    // unstable nodes blink in and out with nothing moving. The drawn COUNT is
    // not enough to catch that -- membership can churn while the count holds.
    // Every node currently loaded into the scene, drawn or not.
    getLoadedNodeIds() {
      return [...state.nodeMap.keys()].map(String).sort();
    },
    getDrawnNodeIds() {
      const ids = [];
      for (const nodeObj of state.visibleNodes) {
        if (nodeObj.renderVisible && !nodeObj.clustered && !nodeObj.culled && nodeObj.data?.id) {
          ids.push(String(nodeObj.data.id));
        }
      }
      ids.sort();
      return ids;
    },
    getStats() {
      return {
        visibleNodeCount: state.visibleNodeCount,
        drawnNodeCount: state.drawnNodeCount,
        totalNodeCount: state.totalNodeCount,
        candidateNodeCount: state.candidateNodeCount,
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
      showSupersededNodes: state.showSupersededNodes,
        showCandidateNodes: state.showCandidateNodes,
        zoom: state.zoom,
        targetZoom: state.targetZoom,
      };
    },
    getMaxDataDepth() {
      return state.maxDataDepth;
    },
    setLens(name) {
      setLens(name);
    },
    frameWhole() {
      frameWhole();
    },
    getLens() {
      return state.lens;
    },
    setShowEstimateFigures(enabled) {
      setShowEstimateFigures(enabled);
    },
    // The lens's own verdict for a node, in the words the brood badge uses;
    // null under Structure. Exposed so the smoke check can compare the
    // picture with the data it is drawn from.
    // Where a loaded node sits: world position and its projection to canvas
    // pixels. Read-only, for the smoke check and layout measurements.
    nodeScreenPosition(nodeId) {
      const nodeObj = state.nodeMap.get(nodeId);
      if (!nodeObj) {
        return null;
      }
      const width = renderer.domElement.clientWidth || window.innerWidth;
      const height = renderer.domElement.clientHeight || window.innerHeight;
      const projected = nodeObj.pos.clone().project(camera);
      return {
        world: { x: nodeObj.pos.x, y: nodeObj.pos.y, z: nodeObj.pos.z },
        screen: { x: (projected.x + 1) * width / 2, y: (1 - projected.y) * height / 2 },
        drawn: Boolean(nodeObj.renderVisible && !nodeObj.culled && !nodeObj.clustered),
      };
    },
    lensVerdictFor(nodeId) {
      const data = state.dataMap.get(nodeId);
      if (!data) {
        return null;
      }
      const verdict = lensVerdict(data);
      return verdict ? { ...verdict, color: lensColorHex(data), scale: lensScaleForData(data, state.rootObj?.data === data) } : null;
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
