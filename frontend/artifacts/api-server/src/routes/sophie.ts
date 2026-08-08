/**
 * Sophie proxy routes — forwards all /api/dashboard/*, /api/campaigns/*, /api/leads/*
 * requests to the Python FastAPI backend (SOPHIE_API_URL) injecting the X-API-Key
 * server-side so the key is never exposed to the browser.
 */
import { Router, type IRouter, type Request, type Response } from "express";

const router: IRouter = Router();

const SOPHIE_API_URL = process.env["SOPHIE_API_URL"] ?? "";
const SOPHIE_API_KEY = process.env["SOPHIE_API_KEY"] ?? "";

if (!SOPHIE_API_URL) {
  console.warn(
    "[sophie-proxy] SOPHIE_API_URL is not set — all Sophie requests will fail with 503.",
  );
}

/**
 * Build the upstream URL by stripping the /api prefix (already present in the
 * Express mount path) and prepending SOPHIE_API_URL + /api.
 *
 * Example: incoming path = /dashboard/overview
 *          upstream      = ${SOPHIE_API_URL}/api/dashboard/overview
 */
function buildUpstreamUrl(req: Request): string {
  const qs = req.url.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
  return `${SOPHIE_API_URL}/api${req.path}${qs}`;
}

async function proxyRequest(req: Request, res: Response): Promise<void> {
  if (!SOPHIE_API_URL) {
    res
      .status(503)
      .json({ error: "SOPHIE_API_URL is not configured on this server." });
    return;
  }

  const upstreamUrl = buildUpstreamUrl(req);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (SOPHIE_API_KEY) {
    headers["X-API-Key"] = SOPHIE_API_KEY;
  }

  let bodyInit: BodyInit | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    bodyInit = JSON.stringify(req.body);
  }

  let upstreamRes: Response_ | undefined;
  try {
    upstreamRes = await fetch(upstreamUrl, {
      method: req.method,
      headers,
      body: bodyInit,
    });
  } catch (err) {
    console.error("[sophie-proxy] fetch error", { upstreamUrl, err });
    res.status(502).json({ error: "Upstream connection failed.", detail: String(err) });
    return;
  }

  // Forward status
  res.status(upstreamRes.status);

  // Forward content-type
  const ct = upstreamRes.headers.get("content-type");
  if (ct) {
    res.setHeader("Content-Type", ct);
  }

  // Forward body
  const body = await upstreamRes.text();
  res.send(body);
}

// Convenience type alias so we can use the global Response type without clashing
// with Express's Response
type Response_ = globalThis.Response;

// ── Dashboard ────────────────────────────────────────────────────────────────
router.get("/dashboard/overview", proxyRequest);
router.get("/dashboard/stats", proxyRequest);
router.get("/dashboard/leads", proxyRequest);
router.get("/dashboard/leads/:leadId", proxyRequest);

// ── Campaigns ────────────────────────────────────────────────────────────────
router.get("/campaigns", proxyRequest);
router.post("/campaigns", proxyRequest);
router.get("/campaigns/:campaignId", proxyRequest);
router.get("/campaigns/:campaignId/analytics", proxyRequest);
router.post("/campaigns/:campaignId/start", proxyRequest);
router.post("/campaigns/:campaignId/pause", proxyRequest);
router.post("/campaigns/:campaignId/resume", proxyRequest);

// ── Leads import ─────────────────────────────────────────────────────────────
router.post("/leads/import/preview", proxyRequest);
router.post("/leads/import", proxyRequest);
router.get("/leads/:leadId", proxyRequest);
router.get("/leads/:leadId/history", proxyRequest);

export default router;
