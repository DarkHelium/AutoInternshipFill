import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/_index.tsx"),
  route("home", "routes/home.tsx"),
  route("jobs", "routes/jobs._index.tsx"),
  route("jobs/:jobId", "routes/jobs.$jobId.tsx"),
  route("runs/:runId", "routes/runs.$runId.tsx"),
  route("runs/start-desktop", "routes/runs.start-desktop.tsx"),
  route("profile", "routes/profile._index.tsx"),
] satisfies RouteConfig;
