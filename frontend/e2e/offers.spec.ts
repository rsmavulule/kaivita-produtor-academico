import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { NOT_FOUND_MESSAGE, isActorId } from "../lib/actor-view";
import { readDecimal } from "../lib/decimal";
import { parseApiError } from "../lib/errors";
import {
  NOT_PUBLISHABLE,
  OFFER_NOT_FOUND,
  PUBLISHED_MUST_STAY_VALID,
  ZERO_AVAILABLE,
} from "../lib/offer-view";
import { PRODUCT_NOT_FOUND } from "../lib/product-view";
import { setAccess } from "./access";
import { setCommercialRoles } from "./roles";
import { credentials } from "./support";

const shot = (name: string) =>
  path.resolve(process.cwd(), "..", "docs", "evidencias", "I5.4", "capturas", name);

test("o decimal e o 422 não passam por ponto flutuante nem repetem o valor", () => {
  expect(readDecimal("")).toEqual({ kind: "empty" });
  expect(readDecimal("0")).toEqual({ kind: "value", text: "0" });
  expect(readDecimal("150.00")).toEqual({ kind: "value", text: "150.00" });
  expect(readDecimal("2,50")).toEqual({ kind: "value", text: "2.50" });
  expect(readDecimal("1.500,00").kind).toBe("invalid");
  expect(readDecimal("1,500.00").kind).toBe("invalid");
  const parsed = parseApiError(422, {
    detail: [{ loc: ["body", "price"], msg: "Preço inválido.", type: "value_error" }],
  });
  expect(parsed.fieldErrors?.price).toBe("Preço inválido.");
  expect(parsed.message.includes("150.99")).toBe(false);
  expect(isActorId("nao-e-uuid")).toBe(false);
  for (const file of ["lib/decimal.ts", "lib/offers.ts", "app/(privada)/actores/[actorId]/ofertas/actions.ts"]) {
    const source = readFileSync(path.resolve(process.cwd(), file), "utf8");
    expect(source.includes("parseFloat")).toBe(false);
    expect(source.includes("parseInt")).toBe(false);
    expect(source.includes("Number(")).toBe(false);
  }
});

test("a lista vazia, o rascunho e os decimais", async ({ page }) => {
  await login(page, credentials());
  const actor = `Ofertas ${Date.now()}`;
  const product = `Mel ${Date.now()}`;
  await createActor(page, actor, ["Produtor"]);
  await page.getByRole("link", { name: "Ofertas" }).click();
  await expect(page.getByText("Este actor ainda não tem ofertas.")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: shot("ofertas-vazio-1280.png"), fullPage: true });
  await page.getByRole("link", { name: "Voltar ao actor" }).click();

  await registerProduct(page, product);
  await page.getByRole("link", { name: "Criar oferta" }).click();
  await expect(page.getByRole("button", { name: "Registar oferta" })).toBeVisible();
  const selected = new URL(page.url()).searchParams.get("produto") ?? "";
  expect(isActorId(selected)).toBe(true);
  await expect(page.locator("#create-product")).toHaveValue(selected);

  await page.locator("#create-product").focus();
  await page.locator("#create-product").press("Tab");
  await expect(page.locator("#create-price")).toBeFocused();
  await page.locator("#create-price").press("Tab");
  await expect(page.locator("#create-currency")).toBeFocused();
  await page.locator("#create-currency").press("Tab");
  await expect(page.locator("#create-quantity")).toBeFocused();
  await page.locator("#create-quantity").press("Tab");
  await expect(page.locator("#create-unit")).toBeFocused();
  await page.locator("#create-unit").press("Tab");
  await expect(page.locator("#create-availability")).toBeFocused();
  await page.locator("#create-availability").press("Tab");
  await expect(page.locator("#create-delivery")).toBeFocused();

  await page.locator("#create-price").fill("150.00");
  await page.locator("#create-currency").fill("mzn");
  await page.locator("#create-quantity").fill("2,50");
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption("available");
  await page.locator("#create-delivery").fill("Recolha no mercado");
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);

  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByText("Preço: 150.00 MZN.")).toBeVisible();
  await expect(page.getByText("Quantidade: 2.50 kg.")).toBeVisible();
  await expect(page.getByText("Disponibilidade: Disponível.")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: shot("oferta-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("oferta-360.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  await page.locator("#edit-price").fill("");
  await page.locator("#edit-currency").fill("");
  await page.locator("#edit-quantity").fill("0");
  await page.locator("#edit-availability").selectOption("unavailable");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByText("Preço: por preencher.")).toBeVisible();
  await expect(page.getByText("Quantidade: 0 kg.")).toBeVisible();
  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Voltar às ofertas" }).click();
  await expect(page.getByRole("link", { name: new RegExp(product) })).toContainText("Rascunho");
  await expect(page.getByRole("link", { name: new RegExp(product) })).toContainText("Quantidade: 0 kg.");
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("ofertas-360.png"), fullPage: true });
});

test("publicar, corrigir e recusar uma oferta inválida", async ({ page }) => {
  await login(page, credentials());
  const product = `Caju ${Date.now()}`;
  await createActor(page, `Publicar ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await page.getByRole("link", { name: "Criar oferta" }).click();
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await expect(page.getByText("Preço: por preencher.")).toBeVisible();
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: NOT_PUBLISHABLE })).toHaveText(NOT_PUBLISHABLE);
  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();

  await fillCommercial(page, "150.00", "MZN", "0", "kg", "available");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByRole("alert").filter({ hasText: ZERO_AVAILABLE })).toHaveText(ZERO_AVAILABLE);
  await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();
  await expect(page.getByText("Preço: por preencher.")).toBeVisible();

  await fillCommercial(page, "150.00", "MZN", "2.50", "kg", "available");
  await page.locator("#edit-delivery").fill("Recolha");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByText("Preço: 150.00 MZN.")).toBeVisible();
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await page.screenshot({ path: shot("oferta-publicada.png"), fullPage: true });

  await page.locator("#edit-price").fill("180.00");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByText("Preço: 180.00 MZN.")).toBeVisible();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await expect(page.getByText("150.00")).toHaveCount(0);

  await page.locator("#edit-currency").fill("");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.locator("p.alert")).toHaveText(PUBLISHED_MUST_STAY_VALID);
  await expect(page.getByText("Preço: 180.00 MZN.")).toBeVisible();
  await expect(page.locator("#edit-currency")).toHaveValue("");
});

test("suspender, republicar e retirar", async ({ page }) => {
  await login(page, credentials());
  const product = `Manga ${Date.now()}`;
  await createActor(page, `Ciclo ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await publishOffer(page);

  await page.getByRole("button", { name: "Suspender" }).click();
  await expect(page.getByText("Suspensa", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Republicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Retirar oferta" }).click();
  await expect(page.getByRole("button", { name: "Confirmar retirada" })).toBeVisible();
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retirar oferta" })).toBeVisible();

  await page.getByRole("button", { name: "Retirar oferta" }).click();
  await page.getByRole("button", { name: "Confirmar retirada" }).click();
  await expect(page.getByText("Retirada", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Republicar" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Suspender" })).toHaveCount(0);
  await expect(page.getByText("A retirada é definitiva.")).toBeVisible();
  await page.screenshot({ path: shot("oferta-retirada.png"), fullPage: true });
});

test("um produto arquivado limita a oferta sem a apagar", async ({ page }) => {
  await login(page, credentials());
  const product = `Arroz ${Date.now()}`;
  await createActor(page, `Arquivo ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await publishOffer(page);
  const actorId = actorIdFrom(page.url(), 2);

  await page.getByRole("link", { name: "Abrir o produto" }).click();
  await page.getByRole("button", { name: "Arquivar produto" }).click();
  await page.getByRole("button", { name: "Confirmar arquivo" }).click();
  await expect(page.getByText("Arquivado", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Criar oferta" })).toHaveCount(0);

  await page.goto(`/actores/${actorId}/ofertas/nova`);
  await expect(page.getByText("Não há produtos activos.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Registar oferta" })).toHaveCount(0);
  await expect(page.getByText(product)).toHaveCount(0);

  await page.goto(`/actores/${actorId}/ofertas`);
  await page.getByRole("link", { name: new RegExp(product) }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await expect(page.getByText("O produto está arquivado.")).toBeVisible();
  await page.screenshot({ path: shot("oferta-produto-arquivado.png"), fullPage: true });

  await page.locator("#edit-delivery").fill("Entrega adiada");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByText("Condições de entrega: Entrega adiada.")).toBeVisible();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Suspender" }).click();
  await expect(page.getByText("Suspensa", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Republicar" }).click();
  await expect(page.getByText("Suspensa", { exact: true })).toBeVisible();
  await expect(page.getByText("Publicada", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Retirar oferta" }).click();
  await page.getByRole("button", { name: "Confirmar retirada" }).click();
  await expect(page.getByText("Retirada", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
});

test("a leitura e a gestão sem produtor não escrevem", async ({ page }) => {
  await login(page, credentials());
  const product = `Feijão ${Date.now()}`;
  await createActor(page, `Leitura ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await publishOffer(page);
  const offerUrl = page.url();
  const actorId = actorIdFrom(page.url(), 2);

  const reader = {
    email: `i54-read-${Date.now()}@example.com`,
    password: randomBytes(18).toString("base64url"),
  };
  setAccess({ ...reader, actorId, mode: "read" });
  await page.context().clearCookies();
  await login(page, reader);
  await page.goto(offerUrl);
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Suspender" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retirar oferta" })).toHaveCount(0);
  await page.screenshot({ path: shot("oferta-read.png"), fullPage: true });
  await page.getByRole("link", { name: "Voltar às ofertas" }).click();
  await expect(page.getByRole("link", { name: "Registar oferta" })).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, credentials());
  await createActor(page, `Comprador ${Date.now()}`, ["Comprador"]);
  await page.getByRole("link", { name: "Ofertas" }).click();
  await expect(page.getByText("O registo exige gestão e o papel de produtor.")).toBeVisible();
  await page.goto(`${page.url().replace(/\/$/, "")}/nova`);
  await expect(page.getByText("O registo de ofertas exige gestão e o papel de produtor.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Registar oferta" })).toHaveCount(0);
});

test("perder o produtor ou a representação retira a gestão", async ({ page }) => {
  await login(page, credentials());
  const account = credentials();
  const product = `Milho ${Date.now()}`;
  await createActor(page, `Papel ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await publishOffer(page);
  const actorId = actorIdFrom(page.url(), 2);
  setCommercialRoles({ actorId, roles: ["buyer"] });

  await page.locator("#edit-price").fill("888.88");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByRole("heading", { name: product })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar oferta" })).toHaveCount(0);
  await expect(page.getByText("888.88")).toHaveCount(0);
  await expect(page.getByText("Preço: 150.00 MZN.")).toBeVisible();

  await page.context().clearCookies();
  await login(page, account);
  const kept = `Sorgo ${Date.now()}`;
  await createActor(page, `Sai ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, kept);
  await publishOffer(page);
  const revokedActor = actorIdFrom(page.url(), 2);
  setAccess({ ...account, actorId: revokedActor, mode: "revoke" });
  await page.locator("#edit-price").fill("777.77");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(NOT_FOUND_MESSAGE);
  await expect(page.getByText(kept)).toHaveCount(0);
  await expect(page.getByText("777.77")).toHaveCount(0);
});

test("uma oferta ou um produto de outro actor não são mostrados", async ({ page }) => {
  await login(page, credentials());
  const own = `Banana ${Date.now()}`;
  await createActor(page, `Dono ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, own);
  await publishOffer(page);
  const offerId = page.url().split("/").pop() ?? "";

  await page.goto("/actores");
  const other = `Outro ${Date.now()}`;
  await createActor(page, other, ["Produtor"]);
  const otherActor = actorIdFrom(page.url(), 0);
  await registerProduct(page, `Local ${Date.now()}`);
  await page.goto(`/actores/${otherActor}/ofertas/${offerId}`);
  await expect(page.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(OFFER_NOT_FOUND);
  await expect(page.getByText(own)).toHaveCount(0);
  await page.goto(`/actores/${otherActor}/ofertas/nao-e-uuid`);
  await expect(page.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();

  await page.goto("/actores");
  await createActor(page, `Origem ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, own);
  const foreignProduct = new URL(page.url()).pathname.split("/").pop() ?? "";
  await page.goto("/actores");
  await page.getByRole("link", { name: other }).click();
  await page.getByRole("link", { name: "Ofertas" }).click();
  await page.getByRole("link", { name: "Registar oferta" }).click();
  await expect(page.getByRole("button", { name: "Registar oferta" })).toBeVisible();
  await page.locator("#create-product").evaluate((select, productId) => {
    const option = document.createElement("option");
    option.value = String(productId);
    option.text = "externo";
    select.append(option);
    (select as HTMLSelectElement).value = String(productId);
  }, foreignProduct);
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await expect(page).toHaveURL(/\/ofertas\/nova/);
  await expect(page.locator("p.alert")).toHaveText(PRODUCT_NOT_FOUND);
  await expect(page.getByText(own)).toHaveCount(0);
});

test("um preço inválido conserva a oferta gravada", async ({ page }) => {
  await login(page, credentials());
  const product = `Açúcar ${Date.now()}`;
  await createActor(page, `Estável ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, product);
  await publishOffer(page);
  await page.locator("#edit-price").fill("abc");
  await page.getByRole("button", { name: "Guardar oferta" }).click();
  await expect(page.locator("#edit-price-error")).toHaveText("Preço inválido.");
  await expect(page.locator("p.alert")).toHaveText("Alguns campos não foram aceites.");
  await expect(page.locator("p.alert")).not.toContainText("abc");
  await expect(page.getByText("Preço: 150.00 MZN.")).toBeVisible();
  await expect(page.locator("#edit-price")).toHaveValue("abc");
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
});

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

async function registerProduct(page: Page, name: string) {
  await page.getByRole("link", { name: "Produtos" }).click();
  await page.getByRole("link", { name: "Registar produto" }).click();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-description").fill("Descrição estável");
  await page.locator("#create-category").fill("geral");
  await page.getByRole("button", { name: "Registar produto" }).click();
  await page.waitForURL(/\/produtos\/[0-9a-f-]{36}$/i);
}

async function publishOffer(page: Page) {
  await page.getByRole("link", { name: "Criar oferta" }).click();
  await expect(page.getByRole("button", { name: "Registar oferta" })).toBeVisible();
  await page.locator("#create-price").fill("150.00");
  await page.locator("#create-currency").fill("MZN");
  await page.locator("#create-quantity").fill("2.50");
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption("available");
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
}

async function fillCommercial(
  page: Page,
  price: string,
  currency: string,
  quantity: string,
  unit: string,
  availability: string,
) {
  await page.locator("#edit-price").fill(price);
  await page.locator("#edit-currency").fill(currency);
  await page.locator("#edit-quantity").fill(quantity);
  await page.locator("#edit-unit").fill(unit);
  await page.locator("#edit-availability").selectOption(availability);
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
