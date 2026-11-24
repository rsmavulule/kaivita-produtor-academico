import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { NOT_FOUND_MESSAGE, isActorId } from "../lib/actor-view";
import { SESSION_COOKIE } from "../lib/cookie-name";
import { OFFER_NOT_FOUND } from "../lib/offer-view";
import { setAccess } from "./access";
import { rememberAccount } from "./manifest";
import { setCommercialRoles } from "./roles";
import { credentials, evidenceShot } from "./support";

test("o percurso privado persiste até à oferta retirada", async ({ page }) => {
  const stamp = Date.now();
  const actor = `Moamba ${stamp}`;
  const product = `Tomate ${stamp}`;
  await login(page, credentials());
  await expectSessionPrivate(page);

  await createActor(page, actor, ["Produtor"]);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: evidenceShot("I5.5", "actor-1280.png"), fullPage: true });

  await registerProduct(page, product, "Hortícolas", "Tomate de época");
  await page.screenshot({ path: evidenceShot("I5.5", "produto-1280.png"), fullPage: true });

  await page.getByRole("link", { name: "Criar oferta" }).click();
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();
  await expect(page.getByText("Preço: por preencher.")).toBeVisible();

  await page.locator("#edit-price").fill("45.00");
  await page.locator("#edit-currency").fill("MZN");
  await page.locator("#edit-quantity").fill("120.00");
  await page.locator("#edit-unit").fill("kg");
  await page.locator("#edit-availability").selectOption("available");
  await page.locator("#edit-delivery").fill("Recolha na unidade de produção");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByText("Preço: 45.00 MZN.")).toBeVisible();
  await expect(page.getByText("Quantidade: 120.00 kg.")).toBeVisible();

  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await page.screenshot({ path: evidenceShot("I5.5", "oferta-publicada-1280.png"), fullPage: true });

  await page.getByRole("button", { name: "Suspender" }).click();
  await expect(page.getByText("Suspensa", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Republicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Retirar oferta" }).click();
  await page.getByRole("button", { name: "Confirmar retirada" }).click();
  await expect(page.getByText("Retirada", { exact: true })).toBeVisible();
  const offerUrl = page.url();

  await page.getByRole("button", { name: "Terminar sessão" }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page, credentials());
  await page.goto(offerUrl);
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByText("Retirada", { exact: true })).toBeVisible();
  await expect(page.getByText("Preço: 45.00 MZN.")).toBeVisible();
  await expect(page.getByText("Quantidade: 120.00 kg.")).toBeVisible();
  await expect(page.getByText("Recolha na unidade de produção")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Publicar" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Republicar" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Suspender" })).toHaveCount(0);
  await page.screenshot({ path: evidenceShot("I5.5", "oferta-retirada-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: evidenceShot("I5.5", "oferta-retirada-360.png"), fullPage: true });

  await page.getByRole("link", { name: "Abrir o produto" }).click();
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await page.getByRole("link", { name: "Voltar ao actor" }).click();
  await expect(page.getByRole("heading", { name: actor })).toBeVisible();
});

test("a autorização separa gestor, leitura, estranho e revogação", async ({ page }) => {
  const stamp = Date.now();
  const actor = `Gestor ${stamp}`;
  const product = `Manga ${stamp}`;
  await login(page, credentials());
  await createActor(page, actor, ["Produtor"]);
  await registerProduct(page, product, "Fruta", "Manga local");
  await page.getByRole("link", { name: "Criar oferta" }).click();
  await page.locator("#create-price").fill("80.00");
  await page.locator("#create-currency").fill("MZN");
  await page.locator("#create-quantity").fill("10.00");
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption("available");
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  const offerUrl = page.url();
  const actorId = actorIdFrom(offerUrl, 2);

  const reader = detachedAccount("read");
  setAccess({ ...reader, actorId, mode: "read" });
  await page.context().clearCookies();
  await login(page, reader);
  await page.goto(offerUrl);
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByText("Preço: 80.00 MZN.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Suspender" })).toHaveCount(0);
  await page.screenshot({ path: evidenceShot("I5.5", "oferta-leitura.png"), fullPage: true });

  const stranger = detachedAccount("estranho");
  await page.context().clearCookies();
  await login(page, stranger);
  await page.goto(offerUrl);
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(NOT_FOUND_MESSAGE);
  await expect(page.getByText(product)).toHaveCount(0);
  await expect(page.getByText("80.00")).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, credentials());
  await page.goto("/actores");
  await createActor(page, `Vizinho ${stamp}`, ["Produtor"]);
  const otherActor = actorIdFrom(page.url(), 0);
  const offerId = offerUrl.split("/").pop() ?? "";
  await page.goto(`/actores/${otherActor}/ofertas/${offerId}`);
  await expect(page.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(OFFER_NOT_FOUND);
  await expect(page.getByText(product)).toHaveCount(0);

  await page.goto(offerUrl);
  setCommercialRoles({ actorId, roles: ["buyer"] });
  await page.locator("#edit-price").fill("999.99");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByText("Preço: 80.00 MZN.")).toBeVisible();
  await expect(page.getByText("999.99")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);

  const account = credentials();
  setAccess({ ...account, actorId, mode: "revoke" });
  await page.goto(offerUrl);
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.getByText(product)).toHaveCount(0);
  await expect(page.getByText("80.00")).toHaveCount(0);
});

async function expectSessionPrivate(page: Page) {
  const cookie = (await page.context().cookies()).find((item) => item.name === SESSION_COOKIE);
  expect(cookie?.httpOnly).toBe(true);
  const token = cookie?.value ?? "";
  expect(token.length).toBeGreaterThan(0);
  expect(page.url().includes(token)).toBe(false);
  const leaked = await page.evaluate((secret) => {
    const stored = JSON.stringify(localStorage) + JSON.stringify(sessionStorage);
    return document.documentElement.innerHTML.includes(secret) || location.href.includes(secret) || stored.includes(secret);
  }, token);
  expect(leaked).toBe(false);
  const scripts = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLScriptElement).src).filter((src) => src !== ""),
  );
  for (const src of scripts) {
    const body = await (await page.request.get(src)).text();
    expect(body.includes(token)).toBe(false);
    expect(body.includes("access_token")).toBe(false);
  }
}

function detachedAccount(kind: string): { email: string; password: string } {
  const email = `i55-${kind}-${Date.now()}@example.com`;
  const password = randomBytes(18).toString("base64url");
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const created = spawnSync(python, ["-m", "app.create_user", "--email", email], {
    cwd: backend,
    input: `${password}\n`,
    encoding: "utf8",
  });
  if (created.status !== 0) throw new Error("Não foi possível preparar a conta auxiliar.");
  rememberAccount(email);
  return { email, password };
}

async function login(page: Page, account: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/inicio$/);
}

async function createActor(page: Page, name: string, roles: string[]) {
  await page.goto("/actores");
  await page.getByRole("radio", { name: "Pessoa" }).check();
  await page.locator("#create-name").fill(name);
  for (const role of roles) await page.getByRole("checkbox", { name: role }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
}

async function registerProduct(page: Page, name: string, category: string, description: string) {
  await page.getByRole("link", { name: "Produtos" }).click();
  await page.getByRole("link", { name: "Registar produto" }).click();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-description").fill(description);
  await page.locator("#create-category").fill(category);
  await page.getByRole("button", { name: "Registar produto" }).click();
  await page.waitForURL(/\/produtos\/[0-9a-f-]{36}$/i);
}

function actorIdFrom(url: string, fromEnd: number): string {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const id = fromEnd === 0 ? parts[1] : parts[parts.length - 1 - fromEnd];
  if (!id || !isActorId(id)) throw new Error("A rota não tem o actor esperado.");
  return id;
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflows).toBe(false);
}
