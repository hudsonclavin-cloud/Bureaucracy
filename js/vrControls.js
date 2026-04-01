import * as THREE from "https://unpkg.com/three@0.160.1/build/three.module.js";
import { QUEST_VR_CONFIG } from "./vrConfig.js?v=20260324vr2";

const VR_THEME = {
  red: 0xff3b30,
  blue: 0x007aff,
  yellow: 0xffd60a,
  green: 0x34c759,
  white: 0xf7fbff,
};

function getButtonPressed(gamepad, indices) {
  const list = Array.isArray(indices) ? indices : [indices];
  return list.some((index) => Boolean(gamepad?.buttons?.[index]?.pressed));
}

function getAxes(gamepad, handedness = "right") {
  if (!gamepad?.axes?.length) {
    return { x: 0, y: 0 };
  }
  const primaryPair = handedness === "left" ? [0, 1] : [2, 3];
  const fallbackPair = handedness === "left" ? [2, 3] : [0, 1];
  const pair = gamepad.axes.length > Math.max(...primaryPair) ? primaryPair : fallbackPair;
  const x = gamepad.axes[pair[0]] || 0;
  const y = gamepad.axes[pair[1]] || 0;
  return { x, y };
}

function getQuestBindings(inputSource = {}) {
  const handedness = inputSource.handedness || "right";
  const profiles = inputSource.profiles || [];
  const isQuestProfile = profiles.some((profile) => /oculus|meta|touch/i.test(profile));

  return {
    handedness,
    trigger: isQuestProfile ? [0] : [0],
    squeeze: isQuestProfile ? [1] : [1],
    stickPress: isQuestProfile ? [3] : [3],
    primary: handedness === "left" ? [4] : [4],
    secondary: handedness === "left" ? [5] : [5],
  };
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
      new THREE.LineBasicMaterial({ color: VR_THEME.blue, transparent: true, opacity: 0.9 }),
    );
    line.name = `vr-ray-${index}`;

    const cursor = new THREE.Mesh(
      new THREE.SphereGeometry(0.02, 12, 12),
      new THREE.MeshBasicMaterial({ color: VR_THEME.yellow }),
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
      prevStickPress: false,
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
    controllerState.line.material.color.set(hit ? VR_THEME.yellow : VR_THEME.blue);
    controllerState.cursor.visible = Boolean(hitPosition);
    if (hitPosition) {
      controllerState.cursor.position.copy(hitPosition);
      controllerState.cursor.material.color.set(hit.isCluster ? VR_THEME.blue : VR_THEME.yellow);
    }
  }

  function handleButtons(controllerState, hit, deltaSeconds, timeSeconds) {
    const inputSource = controllerState.controller.userData.inputSource;
    const gamepad = inputSource?.gamepad;
    if (!gamepad) {
      return;
    }
    const bindings = getQuestBindings(inputSource);

    const trigger = getButtonPressed(gamepad, bindings.trigger);
    const squeeze = getButtonPressed(gamepad, bindings.squeeze);
    const primary = getButtonPressed(gamepad, bindings.primary);
    const secondary = getButtonPressed(gamepad, bindings.secondary);
    const stickPress = getButtonPressed(gamepad, bindings.stickPress);

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
      if (bindings.handedness === "left") {
        graph.toggleTraceSelectedNode();
        onStatus("Toggled origin trace.");
      } else {
        graph.collapseSelectedNode();
        onStatus("Collapsed selected node.");
      }
    }

    if (stickPress && !controllerState.prevStickPress) {
      graph.resetVrRig();
      onStatus("Recentred VR view.");
    }

    const axes = getAxes(gamepad, bindings.handedness);
    if (bindings.handedness === "left") {
      const moveX = Math.abs(axes.x) > QUEST_VR_CONFIG.moveDeadzone ? axes.x : 0;
      const moveY = Math.abs(axes.y) > QUEST_VR_CONFIG.moveDeadzone ? axes.y : 0;
      if (moveX || moveY) {
        graph.moveVrRig(
          moveX * QUEST_VR_CONFIG.smoothMoveSpeed * deltaSeconds,
          0,
          -moveY * QUEST_VR_CONFIG.smoothMoveSpeed * deltaSeconds,
        );
      }
    } else if (bindings.handedness === "right") {
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
    controllerState.prevStickPress = stickPress;
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
