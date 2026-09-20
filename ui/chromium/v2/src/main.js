import "./styles/tokens.css";
import "./styles/shell.css";
import { createAuraApp } from "./app/aura-app.js";

const root = document.getElementById("aura-v2-root");

if (!root) {
  throw new Error("AURA UI V2 root is missing");
}

const app = createAuraApp(root);
app.mount();

window.AuraUiV2Foundation = Object.freeze({
  version: "2-foundation",
  status: "dormant",
  setState: app.setState,
  setMode: app.setMode,
  snapshot: app.snapshot,
});
