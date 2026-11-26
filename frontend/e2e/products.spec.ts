import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { NOT_FOUND_MESSAGE } from "../lib/actor-view";
import { isActorId } from "../lib/actor-view";
import { parseApiError } from "../lib/errors";
import { PRODUCT_NOT_FOUND } from "../lib/product-view";
import { setAccess } from "./access";
import { setCommercialRoles } from "./roles";
import { credentials, evidenceShot } from "./support";

const shot = (name: string) => evidenceShot("I5.3", name);

test("o 422 de produto não repete o valor rejeitado", () => {
  const parsed = parseApiError(422, {
    detail: [{ loc: ["body", "name"], msg: "Nome inválido.", type: "value_error" }],
  });
  expect(parsed.fieldErrors?.name).toBe("Nome inválido.");
  expect(parsed.message.includes("mel recusado")).toBe(false);
  expect(isActorId("nao-e-uuid")).toBe(false);
});

test("o catálogo vazio, o registo, a consulta e a edição", async ({ page }) => {
  await login(page, credentials());
  const actor = `Produtor ${Date.now()}`;
  await createActor(page, actor, ["Produtor"]);
  await page.getByRole("link", { name: "Produtos" }).click();
  await expect(page.getByText("Este actor ainda não tem produtos.")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: shot("produtos-vazio-1280.png"), fullPage: true });

  await page.getByRole("link", { name: "Registar produto" }).click();
  await expect(page.getByRole("button", { name: "Registar produto" })).toBeVisible();
  await page.locator("#create-name").pressSequentially("Mel");
  await page.locator("#create-name").press("Tab");
  await expect(page.locator("#create-description")).toBeFocused();
  await page.locator("#create-description").pressSequentially("Mel de miombo");
  await page.locator("#create-description").press("Tab");
  await expect(page.locator("#create-category")).toBeFocused();
  await page.locator("#create-category").pressSequentially("mel");
  await page.locator("#create-category").press("Tab");
  await expect(page.locator("#create-image")).toBeFocused();
  await page.locator("#create-image").pressSequentially("https://example.com/foto-mel.jpg");
  await page.getByRole("button", { name: "Registar produto" }).click();
  await page.waitForURL(/\/produtos\/[0-9a-f-]{36}$/i);

  await expect(page.getByRole("heading", { name: "Mel" })).toBeVisible();
  await expect(page.getByText("Activo", { exact: true })).toBeVisible();
  await expect(page.getByRole("paragraph").filter({ hasText: "Mel de miombo" })).toBeVisible();
  await expect(page.getByText("Referência da imagem: https://example.com/foto-mel.jpg")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: shot("produto-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("produto-360.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  await page.locator("#edit-name").fill("Mel claro");
  await page.locator("#edit-description").fill("Mel claro de miombo");
  await page.locator("#edit-category").fill("mel claro");
  await page.locator("#edit-image").fill("https://example.com/foto-clara.jpg");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByRole("heading", { name: "Mel claro" })).toBeVisible();
  await expect(page.getByText("Categoria: mel claro.")).toBeVisible();
  await expect(page.getByText("Referência da imagem: https://example.com/foto-clara.jpg")).toBeVisible();

  await page.locator("#edit-image").fill("");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByText("sem referência")).toBeVisible();
  await page.getByRole("link", { name: "Voltar aos produtos" }).click();
  await expect(page.getByRole("link", { name: /Mel claro/ })).toContainText("Activo");
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("produtos-360.png"), fullPage: true });
});

test("o arquivo pede confirmação e o produto arquivado continua editável", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Arquivo ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, "Caju", "Castanha", "fruto", "https://example.com/foto-caju.jpg");

  await page.getByRole("button", { name: "Arquivar produto" }).click();
  await expect(page.getByRole("button", { name: "Confirmar arquivo" })).toBeVisible();
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByText("Activo", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Arquivar produto" })).toBeVisible();

  await page.getByRole("button", { name: "Arquivar produto" }).click();
  await page.getByRole("button", { name: "Confirmar arquivo" }).click();
  await expect(page.getByText("Arquivado", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Arquivar produto" })).toHaveCount(0);
  await page.screenshot({ path: shot("produto-arquivado.png"), fullPage: true });

  await page.locator("#edit-category").fill("fruto seco");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByText("Categoria: fruto seco.")).toBeVisible();
  await expect(page.getByText("Arquivado", { exact: true })).toBeVisible();
});

test("a leitura e a gestão sem produtor não escrevem", async ({ page }) => {
  await login(page, credentials());
  const actor = `Leitura ${Date.now()}`;
  await createActor(page, actor, ["Produtor"]);
  await registerProduct(page, "Manga", "Fruta", "fruto", "");
  const productUrl = page.url();
  const actorId = actorIdFrom(page.url(), 2);

  const reader = {
    email: `i53-read-${Date.now()}@example.com`,
    password: randomBytes(18).toString("base64url"),
  };
  setAccess({ ...reader, actorId, mode: "read" });
  await page.context().clearCookies();
  await login(page, reader);
  await page.goto(productUrl);
  await expect(page.getByRole("heading", { name: "Manga" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar produto" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Arquivar produto" })).toHaveCount(0);
  await page.screenshot({ path: shot("produto-read.png"), fullPage: true });
  await page.getByRole("link", { name: "Voltar aos produtos" }).click();
  await expect(page.getByRole("link", { name: "Registar produto" })).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, credentials());
  await createActor(page, `Comprador ${Date.now()}`, ["Comprador"]);
  await page.getByRole("link", { name: "Produtos" }).click();
  await expect(page.getByText("O registo exige gestão e o papel de produtor.")).toBeVisible();
  await page.goto(`${page.url().replace(/\/$/, "")}/novo`);
  await expect(page.getByText("O registo de produtos exige gestão e o papel de produtor.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Registar produto" })).toHaveCount(0);
});

test("perder o produtor ou a representação retira a gestão", async ({ page }) => {
  await login(page, credentials());
  const account = credentials();
  const name = `Milho ${Date.now()}`;
  await createActor(page, `Revogável ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, name, "Grão", "cereal", "");
  const actorId = actorIdFrom(page.url(), 2);
  setCommercialRoles({ actorId, roles: ["buyer"] });

  await page.locator("#edit-name").fill("Milho recusado");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar produto" })).toHaveCount(0);
  await expect(page.getByText("Milho recusado")).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, account);
  await createActor(page, `Sai ${Date.now()}`, ["Produtor"]);
  const kept = `Feijão ${Date.now()}`;
  await registerProduct(page, kept, "Grão", "legume", "");
  const revokedActor = actorIdFrom(page.url(), 2);
  setAccess({ ...account, actorId: revokedActor, mode: "revoke" });
  await page.locator("#edit-name").fill("Feijão recusado");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(NOT_FOUND_MESSAGE);
  await expect(page.getByText(kept)).toHaveCount(0);
  await expect(page.getByText("Feijão recusado")).toHaveCount(0);
});

test("um produto de outro actor não é mostrado", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Dono ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, "Banana", "Fruta", "fruto", "");
  const productId = page.url().split("/").pop() ?? "";
  await page.goto("/actores");
  await createActor(page, `Outro ${Date.now()}`, ["Produtor"]);
  const otherActor = actorIdFrom(page.url(), 0);
  await page.goto(`/actores/${otherActor}/produtos/${productId}`);
  await expect(page.getByRole("heading", { name: "Produto não encontrado" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(PRODUCT_NOT_FOUND);
  await expect(page.getByText("Banana")).toHaveCount(0);
  await page.goto(`/actores/${otherActor}/produtos/nao-e-uuid`);
  await expect(page.getByRole("heading", { name: "Produto não encontrado" })).toBeVisible();
});

test("um campo inválido conserva a ficha gravada", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Estável ${Date.now()}`, ["Produtor"]);
  await registerProduct(page, "Arroz", "Grão", "cereal", "https://example.com/foto-arroz.jpg");
  await page.locator("#edit-name").evaluate((input) => {
    (input as HTMLInputElement).required = false;
  });
  await page.locator("#edit-name").fill("   ");
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.locator("#edit-name-error")).toHaveText("Nome inválido.");
  await expect(page.getByRole("heading", { name: "Arroz" })).toBeVisible();
  await expect(page.locator("#edit-name")).toHaveValue("   ");
  await expect(page.locator("#edit-name-error")).toHaveText("Nome inválido.");
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

async function registerProduct(
  page: Page,
  name: string,
  description: string,
  category: string,
  imageRef: string,
) {
  await page.getByRole("link", { name: "Produtos" }).click();
  await page.getByRole("link", { name: "Registar produto" }).click();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-description").fill(description);
  await page.locator("#create-category").fill(category);
  if (imageRef) await page.locator("#create-image").fill(imageRef);
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
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflows).toBe(false);
}
