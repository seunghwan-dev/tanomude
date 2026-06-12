import React from "react";
import ReactDOM from "react-dom/client";

import App from "../src/App";
import "../src/index.css";
import { MockBadge } from "./MockBadge";
import { MockNav } from "./MockNav";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <>
      <MockNav />
      <App />
      <MockBadge />
    </>
  </React.StrictMode>,
);
