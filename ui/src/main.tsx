import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

const syncVisibility = () => document.documentElement.classList.toggle("doc-hidden", document.hidden);
document.addEventListener("visibilitychange", syncVisibility);
syncVisibility();

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
