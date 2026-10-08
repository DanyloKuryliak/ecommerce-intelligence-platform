import snapshot from "../../web/demo-data.json";
import Dashboard from "./dashboard";

export default function Page() {
  return <Dashboard initialData={snapshot} />;
}
