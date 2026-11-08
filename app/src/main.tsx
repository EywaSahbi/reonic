import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { DemoGate } from "./DemoGate";
import { Installer } from "./Installer";
import { ReoIntroPreview } from "./ReoIntroPreview";
import { ReoVestPreview } from "./ReoVestPreview";
import "./styles.css";

// Two views, one hash route: "#/installer" = planner workspace, anything else = customer site.
function Root() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => setHash(location.hash);
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  if (hash.startsWith("#/reo-intro")) return <ReoIntroPreview />;
  if (hash.startsWith("#/reo-vest")) return <ReoVestPreview />;
  return hash.startsWith("#/installer") ? <Installer /> : <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <DemoGate><Root /></DemoGate>
  </React.StrictMode>,
);
