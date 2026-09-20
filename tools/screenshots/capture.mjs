import { chromium } from "playwright";
import fs from "node:fs";

const TARGET_URL = "https://intelligent-sales-agent.onrender.com/dashboard/";
const KEY = process.env.SOPHIE_API_KEY;
if (!KEY) { console.error("Set SOPHIE_API_KEY first."); process.exit(1); }

const OUT = new URL("../../docs/images/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });

const SHOTS = [
  { file: "01-dashboard.png",  tab: "Vue d'ensemble" },
  { file: "02-leads.png",      tab: "Prospects & CRM" },
  { file: "03-simulateur.png", tab: "Simulateur Sophie", chat: ["Bonjour", "Je suis à Namur"] },
  { file: "04-live.png",       tab: "Supervision Live" },
  { file: "05-knowledge.png",  tab: "Base de Connaissances" },
];

// Blur emails and phone numbers so no personal data ends up in the images.
async function maskPII(page) {
  await page.evaluate(() => {
    const email = /[\w.+-]+@[\w-]+\.[\w.]+/;
    const phone = /(\+|00|0)\d[\d\s.-]{7,}\d/;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const n = w.currentNode, el = n.parentElement;
      if (el && (email.test(n.textContent) || phone.test(n.textContent))) el.style.filter = "blur(6px)";
    }
  });
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: "fr-FR" });

console.log("Opening the dashboard (free Render plan: allow up to 2 minutes)...");
await page.goto(TARGET_URL, { waitUntil: "domcontentloaded", timeout: 120000 });
const pwd = page.locator('input[type="password"]');
await pwd.waitFor({ timeout: 120000 });
await pwd.fill(KEY);
await page.getByRole("button", { name: "Accéder à la console" }).click();
await page.locator("aside").getByText("Vue d'ensemble").first().waitFor({ timeout: 60000 });

for (const s of SHOTS) {
  await page.locator("aside").getByText(s.tab).first().click();
  await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
  if (s.chat) {
    const box = page.getByPlaceholder(/Tapez un message pour Sophie/);
    for (const m of s.chat) { await box.fill(m); await box.press("Enter"); await page.waitForTimeout(6000); }
  }
  await page.waitForTimeout(1500);
  await maskPII(page);
  await page.screenshot({ path: OUT + s.file });
  console.log("saved", s.file);
}
await browser.close();
