import React from "react";
import ReactDOM from "react-dom/client";

import App from "../src/App";
import "../src/index.css";
import { MockBadge } from "./MockBadge";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <>
      <App />
      <MockBadge />
    </>
  </React.StrictMode>,
);
