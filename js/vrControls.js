import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { QUEST_VR_CONFIG } from "./vrConfig.js?v=20260324vr2";

function getButtonPressed(gamepad, index) {
  return Boolean(gamepad?.buttons?.[index]?.pressed);
}

function getAxes(gamepad) {
  if (!gamepad?.axes?.length) {
    return { x: 0, y: 0 };
  }
  const x = gamepad.axes.length >= 3 ? gamepad.axes[2] : gamepad.axes[0] || 0;
  const y = gamepad.axes.length >= 4 ? gamepad.axes[3] : gamepad.axes[1] || 0;
  return { x, y };
}

export function createVrControls({
  graph,
  hud,
  onStatus = () => {},
} = {}) {
  const renderer = graph.getRenderer();
  const scene = graph.getScene();
  const tempVecA = new THREE.Vector3();
  const tempVecB = new THREE.Vector3();
  const tempQuat = new THREE.Quaternion();
  const upVector = new THREE.Vector3(0, 1, 0);

  const controllerStates = [0, 1].map((index) => {
    const controller = renderer.xr.getController(index);
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0, -QUEST_VR_CONFIG.rayLength),
    ]);
    const line = new THREE.Line(
      lineGeometry,
      new THREE.LineBasicMaterial({ color: 0xc8a84a, transparent: true, opacity: 0.85 }),
    );
    line.name = `vr-ray-${index}`;

    const cursor = new THREE.Mesh(
      new THREE.SphereGeometry(0.02, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xe8c86a }),
    );
    cursor.visible = false;
    controller.add(line);
    scene.add(controller);
    scene.add(cursor);

    controller.userData.inputSource = null;
    controller.addEventListener("connected", (event) => {
      controller.userData.inputSource = event.data;
    });
    controller.addEventListener("disconnected", () => {
      controller.userData.inputSource = null;
      cursor.visible = false;
    });

    return {
      index,
      controller,
      line,
      cursor,
      prevTrigger: false,
      prevSqueeze: false,
      prevPrimary: false,
      prevSecondary: false,
      lastSnapTurnAt: 0,
      hovered: null,
    };
  });

  let frameHook = null;

  function getRay(controllerState) {
    const origin = controllerState.controller.getWorldPosition(tempVecA.clone());
    const direction = tempVecB.set(0, 0, -1).applyQuaternion(
      controllerState.controller.getWorldQuaternion(tempQuat),
    ).normalize();
    return { origin, direction };
  }

  function updateRayVisual(controllerState, origin, direction, hit) {
    const hitPosition = hit?.pos || hit?.displayPos || null;
    const targetDistance = hitPosition ? origin.distanceTo(hitPosition) : QUEST_VR_CONFIG.rayLength;
    const positionAttr = controllerState.line.geometry.getAttribute("position");
    positionAttr.setXYZ(0, 0, 0, 0);
    positionAttr.setXYZ(1, 0, 0, -targetDistance);
    positionAttr.needsUpdate = true;
    controllerState.line.material.color.set(hit ? 0xe8c86a : 0x5a7bb8);
    controllerState.cursor.visible = Boolean(hitPosition);
    if (hitPosition) {
      controllerState.cursor.position.copy(hitPosition);
      controllerState.cursor.material.color.set(hit.isCluster ? 0x5a7bb8 : 0xe8c86a);
    }
  }

  function handleButtons(controllerState, hit, deltaSeconds, timeSeconds) {
    const inputSource = controllerState.controller.userData.inputSource;
    const gamepad = inputSource?.gamepad;
    if (!gamepad) {
      return;
    }

    const trigger = getButtonPressed(gamepad, 0);
    const squeeze = getButtonPressed(gamepad, 1);
    const primary = getButtonPressed(gamepad, 4);
    const secondary = getButtonPressed(gamepad, 5);

    if (trigger && !controllerState.prevTrigger) {
      const activated = graph.activateRenderable(hit || graph.getSelectedNode());
      if (activated) {
        onStatus(`Selected ${activated.data?.name || activated.name}.`);
      }
    }

    if (squeeze && !controllerState.prevSqueeze) {
      graph.focusNodeInVr(hit?.sourceNode || hit || graph.getSelectedNode());
    }

    if (primary && !controllerState.prevPrimary) {
      graph.expandSelectedNode();
      onStatus("Expanded selected node.");
    }

    if (secondary && !controllerState.prevSecondary) {
      if (controllerState.controller.userData.inputSource?.handedness === "left") {
        graph.toggleTraceSelectedNode();
        onStatus("Toggled origin trace.");
      } else {
        graph.collapseSelectedNode();
        onStatus("Collapsed selected node.");
      }
    }

    const axes = getAxes(gamepad);
    const handedness = controllerState.controller.userData.inputSource?.handedness;
    if (handedness === "left") {
      const moveX = Math.abs(axes.x) > QUEST_VR_CONFIG.moveDeadzone ? axes.x : 0;
      const moveY = Math.abs(axes.y) > QUEST_VR_CONFIG.moveDeadzone ? axes.y : 0;
      if (moveX || moveY) {
        graph.moveVrRig(
          moveX * QUEST_VR_CONFIG.smoothMoveSpeed * deltaSeconds,
          0,
          -moveY * QUEST_VR_CONFIG.smoothMoveSpeed * deltaSeconds,
        );
      }
    } else if (handedness === "right") {
      if (Math.abs(axes.x) > QUEST_VR_CONFIG.snapTurnDeadzone && timeSeconds - controllerState.lastSnapTurnAt > 0.32) {
        graph.snapTurnVr(-Math.sign(axes.x) * QUEST_VR_CONFIG.snapTurnAngle);
        controllerState.lastSnapTurnAt = timeSeconds;
      }
      if (Math.abs(axes.y) > QUEST_VR_CONFIG.moveDeadzone) {
        graph.moveVrRig(0, -axes.y * QUEST_VR_CONFIG.verticalMoveSpeed * deltaSeconds, 0);
      }
    }

    controllerState.prevTrigger = trigger;
    controllerState.prevSqueeze = squeeze;
    controllerState.prevPrimary = primary;
    controllerState.prevSecondary = secondary;
  }

  function update({ deltaSeconds, time }) {
    let nearestHover = null;

    for (const controllerState of controllerStates) {
      if (!controllerState.controller.userData.inputSource) {
        controllerState.cursor.visible = false;
        continue;
      }

      const { origin, direction } = getRay(controllerState);
      const hit = graph.pickFromRay(origin, direction);
      controllerState.hovered = hit || null;
      updateRayVisual(controllerState, origin, direction, hit);
      if (!nearestHover && hit) {
        nearestHover = hit;
      }
      handleButtons(controllerState, hit, deltaSeconds, time);
    }

    hud?.setHoverNode(nearestHover?.sourceNode || nearestHover || null);
  }

  function init() {
    frameHook = update;
    graph.registerFrameHook(frameHook);
    onStatus("VR controls active.");
  }

  function destroy() {
    if (frameHook) {
      graph.unregisterFrameHook(frameHook);
      frameHook = null;
    }
    for (const controllerState of controllerStates) {
      controllerState.line.removeFromParent();
      controllerState.cursor.removeFromParent();
      controllerState.controller.removeFromParent();
    }
  }

  return {
    init,
    destroy,
  };
}
