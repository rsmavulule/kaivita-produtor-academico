import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { SESSION_COOKIE } from "../lib/cookie-name";
import { CONNECTION_MESSAGE } from "../lib/errors";
import { classifyPublicStatus, publicHeaders } from "../lib/public-offers";
import {
  catalogIsLimited,
  EMPTY_SEARCH,
  INVALID_OFFER_ADDRESS,
  INVALID_QUERY_MESSAGE,
  LIMITED_RESULTS,
  nextOffset,
  OFFER_NOT_FOUND,
  PUBLIC_FIELD_NOTICE,
  PUBLIC_PUBLISH_NOTICE,
  readPublicQuery,
  returnHref,
  STALE_PAGE,
} from "../lib/public-offer-view";
import { rememberAccount } from "./manifest";
import { recoverApi } from "./recover";
import { evidenceShot, hostApiUrl, appOrigin } from "./support";

test("a leitura dos parâmetros públicos rejeita o que a interface não deve encaminhar", () => {
  expect(readPublicQuery({ q: "tomate", offset: "20" })).toEqual({
    kind: "ready",
    filters: { q: "tomate", offset: 20 },
  });
  expect(readPublicQuery({ q: "" }).kind).toBe("ready");
  expect(readPublicQuery({ limit: "1" }).kind).toBe("invalid");
  expect(readPublicQuery({ extra: "SEGREDO" }).kind).toBe("invalid");
  expect(readPublicQuery({ q: ["alfa", "beta"] }).kind).toBe("invalid");
  expect(readPublicQuery({ offset: "1001" }).kind).toBe("invalid");
  expect(readPublicQuery({ offset: "01" }).kind).toBe("invalid");
  expect(readPublicQuery({ offset: "-1" }).kind).toBe("invalid");
  expect(readPublicQuery({ q: "x".repeat(101) }).kind).toBe("invalid");
  expect(returnHref({ return: "https://evil.example" })).toBe("/ofertas");
  expect(returnHref({ q: "tomate", offset: "20" })).toBe("/ofertas?q=tomate&offset=20");
  expect(nextOffset(0, 20, 21)).toBe(20);
  expect(nextOffset(1000, 20, 5000)).toBeNull();
  expect(catalogIsLimited(1020)).toBe(false);
  expect(catalogIsLimited(1021)).toBe(true);
  expect(classifyPublicStatus(404)).toBe("missing");
  expect(classifyPublicStatus(422)).toBe("rejected");
  expect(classifyPublicStatus(503)).toBe("unavailable");
  expect(publicHeaders().has("authorization")).toBe(false);
  const source = readFileSync(path.resolve("lib/public-offers.ts"), "utf8");
  expect(source.includes("readSessionToken")).toBe(false);
  expect(source.includes("apiRequest")).toBe(false);
  expect(source.includes('cache: "no-store"')).toBe(true);
  expect(source.toLowerCase().includes("authorization")).toBe(false);
});

test("a entrada pública abre sem sessão e liga à autenticação", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kaivita Produtor", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Estado da API" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Documentação da API" })).toHaveCount(0);
  await expect(page.getByText(/populares|recomendadas|patrocinadas/i)).toHaveCount(0);
  await page.getByRole("link", { name: "Entrar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
  await page.getByRole("link", { name: "Ver ofertas" }).click();
  await expect(page.getByRole("heading", { name: "Ofertas", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Início", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: evidenceShot("I6.2", "inicio-publico-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: evidenceShot("I6.2", "inicio-publico-360.png"), fullPage: true });
});

test("um cookie inválido não bloqueia as ofertas públicas", async ({ page }) => {
  await page.context().addCookies([
    { name: SESSION_COOKIE, value: "cookie-invalido", url: appOrigin },
  ]);
  await page.goto("/ofertas");
  await expect(page).toHaveURL(/\/ofertas$/);
  await expect(page.getByRole("heading", { name: "Ofertas", exact: true })).toBeVisible();
  await expect(page.locator("#q")).toBeVisible();
});

test("o teclado percorre a pesquisa e o foco fica visível", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/ofertas");
  await page.getByLabel("Nome ou descrição do produto").click();
  await expect(page.locator("#q")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#category")).toBeFocused();
  const outline = await page.locator("#category").evaluate((element) => getComputedStyle(element).outlineStyle);
  expect(outline).not.toBe("none");
  await page.keyboard.press("Tab");
  await expect(page.locator("#location")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Pesquisar" })).toBeFocused();
});

test("parâmetros inválidos não são repetidos na mensagem", async ({ page }) => {
  const secret = "SEGREDO-I62";
  await page.goto(`/ofertas?extra=${secret}`);
  await expect(page.locator("p.alert")).toHaveText(INVALID_QUERY_MESSAGE);
  expect(await page.locator("body").innerText()).not.toContain(secret);
  await expect(page.locator("#q")).toHaveValue("");

  await page.goto("/ofertas?q=alfa&q=beta");
  await expect(page.locator("p.alert")).toHaveText(INVALID_QUERY_MESSAGE);
  await expect(page.locator("#q")).toHaveValue("");

  await page.goto(`/ofertas?q=${"b".repeat(90)}${secret}`);
  await expect(page.locator("p.alert")).toHaveText(INVALID_QUERY_MESSAGE);
  expect(await page.locator("p.alert").innerText()).not.toContain(secret);

  await page.goto("/ofertas?offset=1001");
  await expect(page.locator("p.alert")).toHaveText(INVALID_QUERY_MESSAGE);
  await expect(page.getByText("1001")).toHaveCount(0);

  await page.getByRole("link", { name: "Limpar filtros" }).click();
  await expect(page).toHaveURL(/\/ofertas$/);
  await expect(page.locator("p.alert")).toHaveCount(0);
});

test("um endereço de regresso externo não é seguido", async ({ page }) => {
  const id = "11111111-1111-4111-8111-111111111111";
  await page.goto(`/ofertas/${id}?return=https://evil.example&next=https://evil.example`);
  await expect(page.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();
  const hrefs = await page.locator("a").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("href") ?? ""),
  );
  expect(hrefs.some((href) => href.includes("evil.example"))).toBe(false);
  await expect(page.getByRole("link", { name: "Voltar às ofertas" })).toHaveAttribute("href", "/ofertas");
});

test("o visitante acompanha a publicação, a alteração e a retirada", async ({ browser }) => {
  test.setTimeout(120_000);
  const stamp = `i62${Date.now()}`;
  const actorName = `Produtor ${stamp}`;
  const product = `Açúcar ${stamp}`;
  const description = `Descricao miombo ${stamp}`;
  const category = `Horticolas ${stamp}`;
  const location = `Moamba ${stamp}`;
  const markup = `Entrega <img src=x onerror=alert(1)> ${stamp}`;
  const account = auxiliaryAccount("ciclo");
  const producer = await browser.newContext();
  const visitor = await browser.newContext();
  const producerPage = await producer.newPage();
  const visitorPage = await visitor.newPage();
  visitorPage.on("dialog", () => {
    throw new Error("A página pública executou conteúdo da oferta.");
  });

  try {
    await login(producerPage, account);
    await createActor(producerPage, actorName, location);
    await expect(producerPage.getByText(PUBLIC_FIELD_NOTICE).first()).toBeVisible();
    await registerProduct(producerPage, product, category, description, `foto-secreta-${stamp}`);
    await expect(producerPage.getByText(PUBLIC_FIELD_NOTICE).first()).toBeVisible();
    const actorId = actorIdFrom(producerPage.url());

    await producerPage.getByRole("link", { name: "Criar oferta" }).click();
    await producerPage.getByRole("button", { name: "Registar oferta" }).click();
    await producerPage.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
    const offerUrl = producerPage.url();
    const offerId = offerUrl.split("/").pop() ?? "";

    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: product })).toHaveCount(0);
    await expect(visitorPage.getByText(EMPTY_SEARCH)).toBeVisible();

    await producerPage.locator("#edit-price").fill("45.00");
    await producerPage.locator("#edit-currency").fill("MZN");
    await producerPage.locator("#edit-quantity").fill("120.00");
    await producerPage.locator("#edit-unit").fill("kg");
    await producerPage.locator("#edit-availability").selectOption("available");
    await producerPage.locator("#edit-delivery").fill(markup);
    await producerPage.getByRole("button", { name: "Guardar oferta" }).click();
    await expect(producerPage.getByText("Preço: 45.00 MZN.")).toBeVisible();
    await expect(producerPage.getByText(PUBLIC_PUBLISH_NOTICE)).toBeVisible();
    await producerPage.setViewportSize({ width: 1280, height: 800 });
    await producerPage.screenshot({ path: evidenceShot("I6.2", "aviso-publicacao.png"), fullPage: true });
    await producerPage.getByRole("button", { name: "Publicar" }).click();
    await expect(producerPage.getByText("Publicada", { exact: true })).toBeVisible();

    await search(visitorPage, `acucar ${stamp}`);
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();
    await expect(visitorPage).toHaveURL(new RegExp(`q=acucar(\\+|%20)${stamp}`));
    await visitorPage.reload();
    await expect(visitorPage.locator("#q")).toHaveValue(`acucar ${stamp}`);
    await search(visitorPage, `miombo ${stamp}`);
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();
    await visitorPage.locator("#category").fill(category.toLowerCase());
    await visitorPage.locator("#location").fill(location.toLowerCase());
    await visitorPage.getByRole("button", { name: "Pesquisar" }).click();
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();
    await expect(visitorPage).toHaveURL(/category=/);
    await expect(visitorPage).toHaveURL(/location=/);
    expect(visitorPage.url().includes("offset=")).toBe(false);

    const cardText = await visitorPage.locator("article", { hasText: product }).innerText();
    expect(cardText.includes(offerId)).toBe(false);
    await visitorPage.setViewportSize({ width: 1280, height: 800 });
    await expectNoHorizontalOverflow(visitorPage);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "pesquisa-resultados-1280.png"), fullPage: true });
    await visitorPage.setViewportSize({ width: 360, height: 800 });
    await expectNoHorizontalOverflow(visitorPage);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "pesquisa-resultados-360.png"), fullPage: true });

    await visitorPage.getByRole("link", { name: `Ver oferta de ${product}` }).click();
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();
    await expect(visitorPage.getByText("45.00 MZN")).toBeVisible();
    await expect(visitorPage.getByText("120.00 kg")).toBeVisible();
    await expect(visitorPage.getByText("Disponível", { exact: true })).toBeVisible();
    await expect(visitorPage.getByText(markup)).toBeVisible();
    await expect(visitorPage.locator("img")).toHaveCount(0);
    await expect(visitorPage.getByText(actorName)).toBeVisible();
    await expect(visitorPage.getByText("Pessoa", { exact: true })).toBeVisible();
    await expect(visitorPage.getByText(location)).toBeVisible();
    await expect(visitorPage.getByRole("link", { name: "Voltar aos resultados" })).toBeVisible();
    const html = await visitorPage.content();
    for (const fragment of [account.email, account.password, actorId, `foto-secreta-${stamp}`, "password_hash", "owner_actor_id"]) {
      expect(html.includes(fragment)).toBe(false);
    }
    await visitorPage.setViewportSize({ width: 1280, height: 800 });
    await expectNoHorizontalOverflow(visitorPage);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "oferta-detalhe-1280.png"), fullPage: true });
    await visitorPage.setViewportSize({ width: 360, height: 800 });
    await expectNoHorizontalOverflow(visitorPage);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "oferta-detalhe-360.png"), fullPage: true });
    await visitorPage.getByRole("link", { name: "Voltar aos resultados" }).click();
    await expect(visitorPage).toHaveURL(/category=/);

    await producerPage.locator("#edit-price").fill("46.50");
    await producerPage.locator("#edit-quantity").fill("0");
    await producerPage.locator("#edit-availability").selectOption("unavailable");
    await producerPage.getByRole("button", { name: "Guardar oferta" }).click();
    await expect(producerPage.getByText("Preço: 46.50 MZN.")).toBeVisible();
    await visitorPage.goto(`/ofertas/${offerId}`);
    await expect(visitorPage.getByText("46.50 MZN")).toBeVisible();
    await expect(visitorPage.getByText("0 kg", { exact: true })).toBeVisible();
    await expect(visitorPage.getByText("Indisponível", { exact: true })).toBeVisible();
    await expect(visitorPage.getByText(product)).toBeVisible();
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "oferta-indisponivel.png"), fullPage: true });

    await producerPage.getByRole("button", { name: "Suspender" }).click();
    await expect(producerPage.getByText("Suspensa", { exact: true })).toBeVisible();
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();
    await visitorPage.reload();
    await expect(visitorPage.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();
    await expect(visitorPage.getByText(product)).toHaveCount(0);
    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: product })).toHaveCount(0);
    const missingId = "22222222-2222-4222-8222-222222222222";
    await visitorPage.goto(`/ofertas/${missingId}`);
    await expect(visitorPage.locator("p.alert")).toHaveText(OFFER_NOT_FOUND);
    await visitorPage.goto(`/ofertas/${offerId}`);
    await expect(visitorPage.locator("p.alert")).toHaveText(OFFER_NOT_FOUND);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "oferta-nao-encontrada.png"), fullPage: true });
    await visitorPage.goto(`/ofertas/NAO-E-UUID-${stamp}`);
    await expect(visitorPage.locator("p.alert")).toHaveText(INVALID_OFFER_ADDRESS);
    expect(await visitorPage.locator("body").innerText()).not.toContain(stamp);

    await producerPage.getByRole("button", { name: "Republicar" }).click();
    await expect(producerPage.getByText("Publicada", { exact: true })).toBeVisible();
    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: product })).toBeVisible();

    await producerPage.getByRole("button", { name: "Retirar oferta" }).click();
    await producerPage.getByRole("button", { name: "Confirmar retirada" }).click();
    await expect(producerPage.getByText("Retirada", { exact: true })).toBeVisible();
    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: product })).toHaveCount(0);
    await visitorPage.goto(`/ofertas/${offerId}`);
    await expect(visitorPage.locator("p.alert")).toHaveText(OFFER_NOT_FOUND);

    await search(visitorPage, `${stamp}-ausente`);
    await expect(visitorPage.getByText(EMPTY_SEARCH)).toBeVisible();
    await expect(visitorPage.getByText(CONNECTION_MESSAGE)).toHaveCount(0);
    await visitorPage.screenshot({ path: evidenceShot("I6.2", "pesquisa-sem-resultados.png"), fullPage: true });
    await visitorPage.getByRole("link", { name: "Limpar filtros" }).click();
    await expect(visitorPage).toHaveURL(/\/ofertas$/);
    await expect(visitorPage.locator("#q")).toHaveValue("");
  } finally {
    await producer.close();
    await visitor.close();
  }
});

test("a paginação preparada na API preserva os filtros e o tecto", async ({ page }) => {
  const stamp = `i62pag${Date.now()}`;
  const account = auxiliaryAccount("pagina");
  await login(page, account);
  const token = await sessionToken(page);
  const actor = await api(token, "POST", "/actors", {
    kind: "organization",
    display_name: `Cooperativa ${stamp}`,
    general_location: `Beira ${stamp}`,
    roles: ["producer"],
  });
  for (let index = 0; index < 21; index += 1) {
    const product = await api(token, "POST", `/actors/${actor.id}/products`, {
      name: `Pag ${stamp} ${String(index).padStart(2, "0")}`,
      description: `Lote ${stamp}`,
      category: `Lote ${stamp}`,
    });
    const offer = await api(token, "POST", `/actors/${actor.id}/offers`, {
      product_id: product.id,
      price: index === 0 ? "12.00" : "10.00",
      currency: index === 0 ? "USD" : "MZN",
      quantity: "1.00",
      unit: "kg",
      availability: "available",
    });
    await api(token, "POST", `/actors/${actor.id}/offers/${offer.id}/publish`);
  }

  await page.goto(`/ofertas?q=${stamp}`);
  await expect(page.getByText("1–20 de 21 ofertas")).toBeVisible();
  await expect(page.getByText("12.00 USD")).toBeVisible();
  await expect(page.getByRole("link", { name: "Anterior" })).toHaveCount(0);
  await expect(page.getByText(LIMITED_RESULTS)).toHaveCount(0);
  await page.getByRole("link", { name: "Seguinte" }).click();
  await expect(page).toHaveURL(new RegExp(`q=${stamp}`));
  await expect(page).toHaveURL(/offset=20/);
  await expect(page.getByText("21–21 de 21 ofertas")).toBeVisible();
  await expect(page.getByRole("link", { name: "Seguinte" })).toHaveCount(0);
  await page.getByRole("link", { name: "Anterior" }).click();
  await expect(page.getByText("1–20 de 21 ofertas")).toBeVisible();

  await page.goto(`/ofertas?q=${stamp}&offset=20`);
  await page.locator("#category").fill(`ausente-${stamp}`);
  await page.getByRole("button", { name: "Pesquisar" }).click();
  expect(page.url().includes("offset=")).toBe(false);
  await expect(page.getByText(EMPTY_SEARCH)).toBeVisible();

  await page.goto(`/ofertas?q=${stamp}&offset=40`);
  await expect(page.getByText(STALE_PAGE)).toBeVisible();
  await expect(page.getByText("21 ofertas")).toBeVisible();
  await expect(page.getByRole("link", { name: "Seguinte" })).toHaveCount(0);
});

test("arquivar o produto e perder o produtor tiram a oferta da pesquisa", async ({ browser }) => {
  const stamp = `i62papel${Date.now()}`;
  const account = auxiliaryAccount("papel");
  const producer = await browser.newContext();
  const visitor = await browser.newContext();
  const producerPage = await producer.newPage();
  const visitorPage = await visitor.newPage();
  try {
    await login(producerPage, account);
    await createActor(producerPage, `Arquivo ${stamp}`, `Local ${stamp}`);
    await registerProduct(producerPage, `Feijao ${stamp}`, "grao", `Grao ${stamp}`, "");
    await publishSimpleOffer(producerPage);
    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: `Feijao ${stamp}` })).toBeVisible();

    await producerPage.getByRole("link", { name: "Abrir o produto" }).click();
    await producerPage.getByRole("button", { name: "Arquivar produto" }).click();
    await producerPage.getByRole("button", { name: "Confirmar arquivo" }).click();
    await expect(producerPage.getByText("Arquivado", { exact: true })).toBeVisible();
    await search(visitorPage, stamp);
    await expect(visitorPage.getByRole("heading", { name: `Feijao ${stamp}` })).toHaveCount(0);

    await producerPage.goto("/actores");
    await createActor(producerPage, `Papel ${stamp}`, `Local ${stamp}`);
    await registerProduct(producerPage, `Caju ${stamp}`, "fruto", `Caju ${stamp}`, "");
    await publishSimpleOffer(producerPage);
    await search(visitorPage, `Caju ${stamp}`);
    await expect(visitorPage.getByRole("heading", { name: `Caju ${stamp}` })).toBeVisible();
    await producerPage.getByRole("link", { name: "Voltar ao actor" }).click();
    await producerPage.getByRole("checkbox", { name: "Produtor" }).uncheck();
    await producerPage.getByRole("checkbox", { name: "Comprador" }).check();
    await producerPage.getByRole("button", { name: "Substituir papéis" }).click();
    await expect(producerPage.getByText("Comprador")).toBeVisible();
    await search(visitorPage, `Caju ${stamp}`);
    await expect(visitorPage.getByRole("heading", { name: `Caju ${stamp}` })).toHaveCount(0);
    await producerPage.getByRole("checkbox", { name: "Produtor" }).check();
    await producerPage.getByRole("checkbox", { name: "Comprador" }).check();
    await producerPage.getByRole("button", { name: "Substituir papéis" }).click();
    await search(visitorPage, `Caju ${stamp}`);
    await expect(visitorPage.getByRole("heading", { name: `Caju ${stamp}` })).toBeVisible();
  } finally {
    await producer.close();
    await visitor.close();
  }
});

test("uma falha da API não esvazia o catálogo nem termina a sessão", async ({ page }) => {
  test.setTimeout(120_000);
  const account = auxiliaryAccount("rede");
  await login(page, account);
  const root = path.resolve(process.cwd(), "..");
  const stopped = spawnSync("docker", ["compose", "stop", "api"], { cwd: root, encoding: "utf8" });
  if (stopped.status !== 0) throw new Error("Não foi possível parar a API.");
  try {
    await waitUntil(async () => !(await apiIsUp()));
    await page.goto("/ofertas?q=tomate");
    await expect(page.locator("p.alert")).toHaveText(CONNECTION_MESSAGE);
    await expect(page.getByText(EMPTY_SEARCH)).toHaveCount(0);
    await expect(page.getByText("Ainda não há ofertas publicadas.")).toHaveCount(0);
    expect(await sessionToken(page)).not.toBe("");
    await page.goto("/");
    await expect(page.locator("p.alert")).toHaveText(CONNECTION_MESSAGE);
    await expect(page.getByRole("link", { name: "Entrar", exact: true })).toBeVisible();
  } finally {
    await recoverApi();
  }
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { name: "Início" })).toBeVisible();
  await expect(page.getByText(account.email).first()).toBeVisible();
});

async function search(page: Page, text: string) {
  await page.goto("/ofertas");
  await page.locator("#q").fill(text);
  await page.getByRole("button", { name: "Pesquisar" }).click();
  await expect(page).toHaveURL(/q=/);
}

async function publishSimpleOffer(page: Page) {
  await page.getByRole("link", { name: "Criar oferta" }).click();
  await page.locator("#create-price").fill("8.00");
  await page.locator("#create-currency").fill("MZN");
  await page.locator("#create-quantity").fill("3.00");
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption("available");
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
}

async function login(page: Page, account: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/inicio$/);
}

async function createActor(page: Page, name: string, location: string) {
  await page.goto("/actores");
  await page.getByRole("radio", { name: "Pessoa" }).check();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-location").fill(location);
  await page.getByRole("checkbox", { name: "Produtor" }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
}

async function registerProduct(
  page: Page,
  name: string,
  category: string,
  description: string,
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

function actorIdFrom(url: string): string {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  return parts[1] ?? "";
}

function auxiliaryAccount(kind: string): { email: string; password: string } {
  const email = `i562-${kind}-${Date.now()}@example.com`;
  const password = randomBytes(18).toString("base64url");
  const backend = path.resolve(process.cwd(), "..", "backend");
  const venvPython = path.join(backend, ".venv", "Scripts", "python.exe");
  const python = existsSync(venvPython) ? venvPython : "python";
  const created = spawnSync(python, ["-m", "app.create_user", "--email", email], {
    cwd: backend,
    input: `${password}\n`,
    encoding: "utf8",
  });
  if (created.status !== 0) throw new Error("Não foi possível preparar a conta de teste.");
  rememberAccount(email);
  return { email, password };
}

async function sessionToken(page: Page): Promise<string> {
  const cookie = (await page.context().cookies()).find((item) => item.name === SESSION_COOKIE);
  return cookie?.value ?? "";
}

async function api(token: string, method: string, apiPath: string, body?: unknown): Promise<{ id: string }> {
  const response = await fetch(`${hostApiUrl()}${apiPath}`, {
    method,
    headers: {
      accept: "application/json",
      ...(body === undefined ? {} : { "content-type": "application/json" }),
      authorization: `Bearer ${token}`,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${apiPath} respondeu ${response.status}.`);
  if (response.status === 204) return { id: "" };
  return (await response.json()) as { id: string };
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflows).toBe(false);
}

async function apiIsUp(): Promise<boolean> {
  try {
    const response = await fetch(`${hostApiUrl()}/health`, { signal: AbortSignal.timeout(1500) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitUntil(predicate: () => Promise<boolean>) {
  const started = Date.now();
  while (Date.now() - started < 40_000) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("A API não chegou ao estado esperado.");
}
