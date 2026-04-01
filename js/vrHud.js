import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { QUEST_VR_CONFIG } from "./vrConfig.js?v=20260324vr2";

const VR_THEME = {
  red: "#ff3b30",
  blue: "#007aff",
  yellow: "#ffd60a",
  green: "#34c759",
  white: "#f7fbff",
  ink: "#050814",
  panel: "rgba(7, 11, 22, 0.92)",
  panelSoft: "rgba(9, 14, 28, 0.88)",
  line: "rgba(255, 255, 255, 0.16)",
};

function clampText(value, maxLength = 150) {
  const text = String(value || "").trim();
  if (!text) {
    return "No description available.";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

export function createVrHud({
  graph,
  onStatus = () => {},
} = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 640;
  const ctx = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;

  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    opacity: 0.96,
    side: THREE.DoubleSide,
  });
  const panel = new THREE.Mesh(
    new THREE.PlaneGeometry(QUEST_VR_CONFIG.hudWidth, QUEST_VR_CONFIG.hudHeightWorld),
    material,
  );
  panel.position.set(0, QUEST_VR_CONFIG.hudHeight, -QUEST_VR_CONFIG.hudDistance);

  const root = new THREE.Group();
  root.visible = false;
  root.name = "vr-hud";
  root.add(panel);

  let frameHook = null;
  let lastSignature = "";
  let hoverNode = null;
  let statusMessage = "VR ready.";

  function drawRoundedRect(x, y, width, height, radius, fillStyle, strokeStyle = null) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    ctx.fillStyle = fillStyle;
    ctx.fill();
    if (strokeStyle) {
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  function drawWrappedText(text, x, startY, maxWidth, lineHeight, color, font) {
    ctx.fillStyle = color;
    ctx.font = font;
    const words = String(text || "").split(/\s+/);
    let line = "";
    let y = startY;
    for (const word of words) {
      const nextLine = line ? `${line} ${word}` : word;
      if (ctx.measureText(nextLine).width > maxWidth && line) {
        ctx.fillText(line, x, y);
        line = word;
        y += lineHeight;
      } else {
        line = nextLine;
      }
    }
    if (line) {
      ctx.fillText(line, x, y);
      y += lineHeight;
    }
    return y;
  }

  function renderPanel() {
    const selectedNode = graph.getSelectedNode();
    const stats = graph.getStats();
    const trace = graph.getOriginTrace();
    const selectedData = selectedNode?.data || {};
    const name = selectedData.name || "No node selected";
    const type = selectedData.type || "Institution";
    const desc = clampText(selectedData.desc, 220);
    const childrenCount = selectedData.children?.length || 0;
    const traceText = trace.length > 0 ? trace.map((node) => node.data?.name).join("  >  ") : "No active origin trace";
    const hoverText = hoverNode?.data?.name || hoverNode?.name || "Nothing targeted";
    const signature = [
      name,
      type,
      desc,
      childrenCount,
      traceText,
      hoverText,
      statusMessage,
      stats.pendingExpansions,
      stats.lodLabel,
    ].join("|");

    if (signature === lastSignature) {
      return;
    }
    lastSignature = signature;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bgGradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    bgGradient.addColorStop(0, VR_THEME.panel);
    bgGradient.addColorStop(0.5, VR_THEME.ink);
    bgGradient.addColorStop(1, VR_THEME.panelSoft);
    drawRoundedRect(0, 0, canvas.width, canvas.height, 34, bgGradient, VR_THEME.line);
    drawRoundedRect(28, 26, canvas.width - 56, 92, 18, "rgba(16, 22, 40, 0.98)");
    drawRoundedRect(28, 134, canvas.width - 56, 230, 18, "rgba(9, 12, 20, 0.86)");
    drawRoundedRect(28, 382, canvas.width - 56, 102, 18, "rgba(11, 16, 28, 0.86)");
    drawRoundedRect(28, 500, canvas.width - 56, 112, 18, "rgba(9, 12, 20, 0.86)");
    drawRoundedRect(28, 620 - 88, canvas.width - 56, 60, 18, "rgba(12, 18, 30, 0.86)");

    ctx.fillStyle = VR_THEME.yellow;
    ctx.font = "700 44px Georgia";
    ctx.fillText(name, 48, 72);

    ctx.fillStyle = VR_THEME.blue;
    ctx.font = "600 20px IBM Plex Mono";
    ctx.fillText(type.toUpperCase(), 50, 104);

    let nextY = drawWrappedText(desc, 48, 178, 920, 34, VR_THEME.white, "28px IBM Plex Mono");
    nextY = drawWrappedText(`Children: ${childrenCount}    Queue: ${stats.pendingExpansions}    View: ${stats.lodLabel}`, 48, Math.max(294, nextY + 18), 920, 32, VR_THEME.green, "24px IBM Plex Mono");

    ctx.fillStyle = VR_THEME.red;
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("TARGET", 50, 420);
    ctx.fillStyle = VR_THEME.white;
    ctx.font = "26px IBM Plex Mono";
    ctx.fillText(hoverText, 50, 456);

    ctx.fillStyle = VR_THEME.blue;
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("TRACE ORIGIN", 50, 536);
    drawWrappedText(traceText, 50, 572, 920, 28, VR_THEME.white, "22px IBM Plex Mono");

    ctx.fillStyle = VR_THEME.green;
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("CONTROLS", 520, 420);
    drawWrappedText(
      "Trigger: select  |  Squeeze: focus  |  A/X: expand  |  B/Y: collapse/trace  |  Stick press: recenter  |  Left stick: fly  |  Right stick: snap-turn / rise-fall",
      520,
      456,
      430,
      28,
      VR_THEME.white,
      "22px IBM Plex Mono",
    );

    ctx.fillStyle = VR_THEME.yellow;
    ctx.font = "700 20px IBM Plex Mono";
    ctx.fillText("STATUS", 50, 580);
    drawWrappedText(statusMessage, 160, 580, 800, 26, VR_THEME.blue, "22px IBM Plex Mono");

    texture.needsUpdate = true;
  }

  function setHoverNode(nodeObj) {
    hoverNode = nodeObj || null;
  }

  function setStatusMessage(message) {
    statusMessage = String(message || "VR ready.");
  }

  function init() {
    graph.getScene().add(root);
    root.visible = true;
    frameHook = ({ activeCamera }) => {
      activeCamera.getWorldPosition(root.position);
      activeCamera.getWorldQuaternion(root.quaternion);
      root.translateZ(-QUEST_VR_CONFIG.hudDistance);
      root.translateY(QUEST_VR_CONFIG.hudHeight);
      renderPanel();
    };
    graph.registerFrameHook(frameHook);
    renderPanel();
    onStatus("VR HUD active.");
  }

  function destroy() {
    if (frameHook) {
      graph.unregisterFrameHook(frameHook);
      frameHook = null;
    }
    root.removeFromParent();
    root.visible = false;
  }

  return {
    init,
    destroy,
    setHoverNode,
    setStatusMessage,
    getObject() {
      return root;
    },
  };
}
