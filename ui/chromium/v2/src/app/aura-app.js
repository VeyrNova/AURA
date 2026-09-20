import { createAuraState } from "../runtime/aura-state.js";
import { createAuraEventBus } from "../runtime/aura-event-bus.js";
import { createAuraShell } from "../components/aura-shell.js";

export function createAuraApp(root) {
  const state = createAuraState();
  const events = createAuraEventBus();
  const shell = createAuraShell();
  let unsubscribe = null;

  function render(snapshot) {
    shell.render(snapshot);
    events.emit("ui:render", snapshot);
  }

  return Object.freeze({
    mount() {
      root.replaceChildren(shell.element);
      unsubscribe = state.subscribe(render);
      render(state.getSnapshot());
      root.dataset.auraUiV2 = "foundation";
      root.dataset.activation = "dormant";
    },
    unmount() {
      if (unsubscribe) unsubscribe();
      unsubscribe = null;
      root.replaceChildren();
    },
    setState(value, activity) {
      return state.setState(value, activity);
    },
    setMode(value) {
      return state.setMode(value);
    },
    snapshot() {
      return state.getSnapshot();
    },
    events,
  });
}
