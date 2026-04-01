import { createVrControls } from "./vrControls.js?v=20260324vr2";
import { createVrHud } from "./vrHud.js?v=20260324vr2";

export function createVrMode({
  graph,
  button,
  onStatus = () => {},
  onError = () => {},
} = {}) {
  let session = null;
  let vrControls = null;
  let vrHud = null;

  function publishStatus(message, isError = false) {
    if (message) {
      onStatus(message);
      vrHud?.setStatusMessage(message);
    }
    if (isError) {
      vrHud?.setStatusMessage(message || "VR error.");
    }
  }

  function setButtonLabel(label) {
    if (button) {
      button.textContent = label;
    }
  }

  function setButtonVisible(visible) {
    if (button) {
      button.style.display = visible ? "inline-flex" : "none";
    }
  }

  async function endSession() {
    if (!session) {
      graph?.setVrSessionActive(false);
      setButtonLabel("Enter VR");
      return;
    }
    const activeSession = session;
    session = null;
    vrControls?.destroy();
    vrControls = null;
    vrHud?.destroy();
    vrHud = null;
    graph?.setVrSessionActive(false);
    const renderer = graph?.getRenderer?.();
    if (renderer) {
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    }
    setButtonLabel("Enter VR");
    publishStatus("Exited VR.");
    try {
      await activeSession.end();
    } catch (error) {
      onError(error);
    }
  }

  async function startSession() {
    if (!graph || !button || !navigator.xr) {
      return false;
    }

    try {
      publishStatus("Starting VR session…");
      const renderer = graph.getRenderer();
      renderer.xr.enabled = true;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.1));
      renderer.xr.setReferenceSpaceType("local-floor");
      graph.setFlyMode(false);
      session = await navigator.xr.requestSession("immersive-vr", {
        optionalFeatures: ["local-floor", "bounded-floor"],
      });
      session.addEventListener("end", () => {
        session = null;
        vrControls?.destroy();
        vrControls = null;
        vrHud?.destroy();
        vrHud = null;
        graph.setVrSessionActive(false);
        setButtonLabel("Enter VR");
        publishStatus("Exited VR.");
      });
      await renderer.xr.setSession(session);
      graph.setVrSessionActive(true);
      vrHud = createVrHud({ graph, onStatus: publishStatus });
      vrHud.init();
      vrControls = createVrControls({ graph, hud: vrHud, onStatus: publishStatus });
      vrControls.init();
      setButtonLabel("Exit VR");
      publishStatus("VR session active.");
      return true;
    } catch (error) {
      session = null;
      graph?.setVrSessionActive(false);
      setButtonLabel("Enter VR");
      publishStatus("Failed to start VR session.", true);
      onError(error);
      return false;
    }
  }

  async function toggle() {
    if (session || graph?.isVrSessionActive()) {
      await endSession();
      return;
    }
    await startSession();
  }

  async function init() {
    if (!button || !graph || typeof navigator === "undefined" || !navigator.xr) {
      setButtonVisible(false);
      publishStatus("WebXR not available on this device.");
      return false;
    }

    try {
      const supported = await navigator.xr.isSessionSupported("immersive-vr");
      if (!supported) {
        setButtonVisible(false);
        publishStatus("Immersive VR is not supported in this browser.");
        return false;
      }
    } catch (error) {
      publishStatus("Could not verify VR support.", true);
      onError(error);
      setButtonVisible(false);
      return false;
    }

    setButtonVisible(true);
    setButtonLabel("Enter VR");
    button.addEventListener("click", toggle);
    return true;
  }

  return {
    init,
    toggle,
    startSession,
    endSession,
  };
}
