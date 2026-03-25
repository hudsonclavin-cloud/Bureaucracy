import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { QUEST_VR_CONFIG } from "./vrConfig.js?v=20260324vr2";

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
      stats.pendingExpansions,
      stats.lodLabel,
    ].join("|");

    if (signature === lastSignature) {
      return;
    }
    lastSignature = signature;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawRoundedRect(0, 0, canvas.width, canvas.height, 34, "rgba(4, 8, 16, 0.92)", "rgba(200, 168, 74, 0.35)");
    drawRoundedRect(28, 26, canvas.width - 56, 92, 18, "rgba(12, 20, 34, 0.96)");
    drawRoundedRect(28, 134, canvas.width - 56, 230, 18, "rgba(10, 12, 18, 0.84)");
    drawRoundedRect(28, 382, canvas.width - 56, 102, 18, "rgba(18, 18, 28, 0.84)");
    drawRoundedRect(28, 500, canvas.width - 56, 112, 18, "rgba(10, 12, 18, 0.84)");

    ctx.fillStyle = "#e8c86a";
    ctx.font = "700 44px Georgia";
    ctx.fillText(name, 48, 72);

    ctx.fillStyle = "#8fa0bf";
    ctx.font = "600 20px IBM Plex Mono";
    ctx.fillText(type.toUpperCase(), 50, 104);

    let nextY = drawWrappedText(desc, 48, 178, 920, 34, "#d7d2c5", "28px IBM Plex Mono");
    nextY = drawWrappedText(`Children: ${childrenCount}    Queue: ${stats.pendingExpansions}    View: ${stats.lodLabel}`, 48, Math.max(294, nextY + 18), 920, 32, "#9fb2d9", "24px IBM Plex Mono");

    ctx.fillStyle = "#e8c86a";
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("TARGET", 50, 420);
    ctx.fillStyle = "#d2d7e2";
    ctx.font = "26px IBM Plex Mono";
    ctx.fillText(hoverText, 50, 456);

    ctx.fillStyle = "#e8c86a";
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("TRACE ORIGIN", 50, 536);
    drawWrappedText(traceText, 50, 572, 920, 28, "#d2d7e2", "22px IBM Plex Mono");

    ctx.fillStyle = "#e8c86a";
    ctx.font = "700 24px IBM Plex Mono";
    ctx.fillText("CONTROLS", 520, 420);
    drawWrappedText(
      "Trigger: select  |  Squeeze: focus  |  A/X: expand  |  B/Y: collapse  |  Left stick: fly  |  Right stick: snap-turn / rise-fall  |  Trace: X",
      520,
      456,
      430,
      28,
      "#d2d7e2",
      "22px IBM Plex Mono",
    );

    texture.needsUpdate = true;
  }

  function setHoverNode(nodeObj) {
    hoverNode = nodeObj || null;
  }

  function init() {
    const camera = graph.getCamera();
    camera.add(root);
    root.visible = true;
    frameHook = () => renderPanel();
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
    getObject() {
      return root;
    },
  };
}
