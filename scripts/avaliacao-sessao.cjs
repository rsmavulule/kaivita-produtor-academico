const fs = require("fs");
const path = require("path");
const { chromium } = require(path.join(__dirname, "..", "frontend", "node_modules", "@playwright/test"));

function readEnv(file) {
  const values = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const text = line.trim();
    if (!text || text.startsWith("#")) continue;
    const eq = text.indexOf("=");
    if (eq < 1) continue;
    values[text.slice(0, eq).trim()] = text.slice(eq + 1).trim();
  }
  return values;
}

async function main() {
  const root = path.join(__dirname, "..");
  const env = readEnv(path.join(root, ".env.avaliacao"));
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, "avaliacao-dados.json"), "utf8"));
  const state = JSON.parse(fs.readFileSync(path.join(root, "avaliacao-backups", "estado.json"), "utf8"));
  const web = `http://127.0.0.1:${env.WEB_PORT}`;
  if (env.WEB_PORT === "3010" || env.WEB_PORT === "3000") {
    throw new Error("Porta de desenvolvimento.");
  }
  const password = env[data.accounts.produtor.password_env];
  if (!password) throw new Error("Palavra-passe do produtor em falta.");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  try {
    await page.goto(`${web}/login`, { waitUntil: "domcontentloaded" });
    await page.locator("#email").fill(data.accounts.produtor.email);
    await page.locator("#password").fill(password);
    await page.getByRole("button", { name: "Entrar" }).click();
    await page.waitForURL(/\/inicio$/, { timeout: 20000 });
    const inicio = await page.locator("body").innerText();
    if (!inicio.includes(data.accounts.produtor.email)) {
      throw new Error("A sessao nao mostrou o email da conta.");
    }
    console.log("sessao inicio HTTP autenticado");

    await page.goto(`${web}/ofertas/${state.offer_published_id}`, { waitUntil: "domcontentloaded" });
    await page.getByText(data.products.with_photo.name).waitFor({ timeout: 20000 });
    await page.getByText(data.producer.coverage_area).waitFor({ timeout: 20000 });
    const photo = page.locator("img.product-photo");
    const photoCount = await photo.count();
    console.log(`fotografia elementos=${photoCount}`);

    await page.goto(`${web}/inicio`, { waitUntil: "domcontentloaded" });
    await page.waitForURL(/\/inicio$/, { timeout: 20000 });
    await page.getByRole("button", { name: "Terminar sessão" }).click();
    await page.waitForURL(/\/login\?motivo=terminada$/, { timeout: 20000 });
    const ended = await page.locator("body").innerText();
    if (!ended.includes("Sessão terminada neste browser.")) {
      throw new Error("A mensagem de sessao terminada nao apareceu.");
    }
    await page.goto(`${web}/inicio`, { waitUntil: "domcontentloaded" });
    await page.waitForURL(/\/login/, { timeout: 20000 });
    const after = await page.locator("body").innerText();
    if (after.includes(data.accounts.produtor.email)) {
      throw new Error("O email continuou visivel depois de terminar a sessao.");
    }
    console.log("sessao terminada e acesso seguinte recusado");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message || "sessao falhou");
  process.exit(1);
});
