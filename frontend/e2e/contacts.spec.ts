import { randomBytes } from "node:crypto";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { NOT_FOUND_MESSAGE, isActorId } from "../lib/actor-view";
import { NOTICE_V1 } from "../lib/contact-view";
import { SESSION_COOKIE } from "../lib/cookie-name";
import { CONNECTION_MESSAGE } from "../lib/errors";
import { setAccess } from "./access";
import { credentials, evidenceShot, hostWebUrl } from "./support";

const shot = (name: string) => evidenceShot("I7.3", name);

test("a lista vazia, o registo, a normalização e a duplicação", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Contactos ${Date.now()}`, ["Produtor"]);
  await page.getByRole("link", { name: "Contactos comerciais" }).click();
  await expect(page.getByText("Este actor ainda não tem contactos comerciais.")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: shot("contactos-vazio-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("contactos-360.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  await page.getByRole("link", { name: "Registar contacto" }).click();
  await expect(page.getByText("Registar o contacto não autoriza a sua divulgação.")).toBeVisible();
  await page.screenshot({ path: shot("contacto-registo.png"), fullPage: true });
  await page.locator("#create-channel").focus();
  await page.locator("#create-channel").press("Tab");
  await expect(page.locator("#create-value")).toBeFocused();
  await page.locator("#create-channel").selectOption("email");
  await page.locator("#create-value").fill(" Produtor.Caixa@Example.com ");
  await page.getByRole("button", { name: "Registar contacto" }).click();
  await page.waitForURL(/\/contactos\/[0-9a-f-]{36}$/i);
  await expect(page.getByRole("heading", { name: "Email" })).toBeVisible();
  await expect(page.locator(".contact-value")).toHaveText("Produtor.Caixa@example.com");
  await expect(page.getByText("Privado", { exact: true })).toBeVisible();
  await expect(page.getByText("Activo", { exact: true })).toBeVisible();
  await expect(page.getByText("Sem autorização vigente")).toBeVisible();
  await page.screenshot({ path: shot("contacto-privado.png"), fullPage: true });

  await page.getByRole("link", { name: "Voltar aos contactos" }).click();
  await page.getByRole("link", { name: "Registar contacto" }).click();
  await page.locator("#create-channel").selectOption("email");
  await page.locator("#create-value").fill("  Produtor.Caixa@EXAMPLE.com  ");
  await page.getByRole("button", { name: "Registar contacto" }).click();
  await expect(page.getByText("Já existe um contacto activo")).toBeVisible();
  await expect(page.locator("#create-value")).toHaveValue("  Produtor.Caixa@EXAMPLE.com  ");
  await page.getByRole("link", { name: "Voltar aos contactos" }).click();
  await expect(page.getByRole("link", { name: /Email/ })).toHaveCount(1);
});

test("a alteração equivalente preserva a autorização e a inválida não a revoga", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Alteração ${Date.now()}`, ["Comprador"]);
  await registerContact(page, "email", "caixa.alteracao@example.com");
  await authorize(page);
  await page.locator("#edit-value").fill("  caixa.alteracao@EXAMPLE.com  ");
  await page.getByRole("button", { name: "Guardar contacto" }).click();
  await expect(page.getByText("A alteração equivalente preservou a autorização existente.")).toBeVisible();
  await expect(page.getByText("Divulgação autorizada")).toBeVisible();
  await expect(page.locator(".contact-value")).toHaveText("caixa.alteracao@example.com");

  await page.locator("#edit-value").fill("nao-e-email");
  await page.getByRole("button", { name: "Guardar contacto" }).click();
  await expect(page.getByText("Email inválido.")).toBeVisible();
  await expect(page.locator("#edit-value")).toHaveValue("nao-e-email");
  await expect(page.locator(".contact-value")).toHaveText("caixa.alteracao@example.com");
  await page.reload();
  await expect(page.getByText("Divulgação autorizada")).toBeVisible();
  await expect(page.getByText("Revogação manual")).toHaveCount(0);
  await expect(page.getByText("Alteração do contacto")).toHaveCount(0);
});

test("a desactivação pede confirmação e o contacto permanece depois de nova sessão", async ({ page }) => {
  await login(page, credentials());
  const account = credentials();
  await createActor(page, `Sessão ${Date.now()}`, ["Produtor"]);
  await registerContact(page, "phone", "+258 84 000 0731");
  await expect(page.locator(".contact-value")).toHaveText("+258840000731");
  const contactUrl = page.url();
  await page.getByRole("checkbox", { name: "Confirmo a desactivação deste contacto." }).check();
  await page.getByRole("button", { name: "Desactivar contacto" }).click();
  await expect(page.getByText("Inactivo", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Desactivar contacto" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar contacto" })).toHaveCount(0);

  await page.getByRole("button", { name: "Terminar sessão" }).click();
  await expect(page).toHaveURL(/\/login\?motivo=terminada$/);
  await expect(page.getByRole("status")).toHaveText("Sessão terminada neste browser.");
  await login(page, account);
  await page.goto(contactUrl);
  await expect(page.locator(".contact-value")).toHaveText("+258840000731");
  await expect(page.getByText("Inactivo", { exact: true })).toBeVisible();
});

test("a autorização exige confirmação, repete sem nova linha e a revogação fica no histórico", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Aviso ${Date.now()}`, ["Produtor"]);
  await registerContact(page, "email", "aviso.contacto@example.com");
  await expect(page.getByText(NOTICE_V1)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /Confirmo a divulgação/ })).not.toBeChecked();
  await page.screenshot({ path: shot("aviso-divulgacao.png"), fullPage: true });
  await page.getByRole("button", { name: "Autorizar divulgação" }).click();
  await expect(page.getByText("A confirmação explícita é obrigatória.")).toBeVisible();
  await expect(page.getByText("Sem autorização vigente")).toBeVisible();

  await authorize(page);
  await expect(page.getByText("A divulgação foi autorizada.")).toBeVisible();
  await expect(page.getByText("Divulgação autorizada")).toBeVisible();
  await expect(page.getByText("Visibilidade pública")).toBeVisible();
  await page.screenshot({ path: shot("contacto-autorizado.png"), fullPage: true });
  await page.getByRole("checkbox", { name: /Confirmo a divulgação/ }).check();
  await page.getByRole("button", { name: "Autorizar divulgação" }).click();
  await expect(page.getByText("Não foi criada outra autorização.")).toBeVisible();
  await expect(page.getByText("Vigente", { exact: true })).toHaveCount(1);

  await page.getByRole("checkbox", { name: "Confirmo a revogação desta autorização." }).check();
  await page.getByRole("button", { name: "Revogar autorização" }).click();
  await expect(page.getByText("Sem autorização vigente")).toBeVisible();
  await expect(page.getByText("Privado", { exact: true })).toBeVisible();
  await expect(page.getByText("Revogação manual")).toBeVisible();
  await authorize(page);
  await expect(page.getByText("Vigente", { exact: true })).toHaveCount(1);
  await expect(page.getByText("Revogada", { exact: true })).toHaveCount(1);
  await page.screenshot({ path: shot("historico-autorizacoes.png"), fullPage: true });
});

test("uma revisão antiga não é concedida automaticamente", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Revisão ${Date.now()}`, ["Produtor"]);
  await registerContact(page, "email", "revisao.antiga@example.com");
  const contactUrl = page.url();
  const revision = await page.locator('input[name="contact_revision"]').inputValue();
  const other = await page.context().newPage();
  await other.goto(contactUrl);
  await other.locator("#edit-value").fill("revisao.nova@example.com");
  await other.getByRole("button", { name: "Guardar contacto" }).click();
  await expect(other.locator(".contact-value")).toHaveText("revisao.nova@example.com");

  await page.getByRole("checkbox", { name: /Confirmo a divulgação/ }).check();
  await page.getByRole("button", { name: "Autorizar divulgação" }).click();
  await expect(page.getByText("desactualizada")).toBeVisible();
  await expect(page.getByText("A divulgação não foi autorizada.")).toBeVisible();
  await expect(page.getByText("Valor actual: revisao.nova@example.com")).toBeVisible();
  await expect(page.locator('input[name="contact_revision"]')).not.toHaveValue(revision);
  await expect(page.getByRole("checkbox", { name: /Confirmo a divulgação/ })).not.toBeChecked();
  await page.screenshot({ path: shot("conflito-revisao.png"), fullPage: true });
  await page.getByRole("checkbox", { name: /Confirmo a divulgação/ }).check();
  await page.getByRole("button", { name: "Autorizar divulgação" }).click();
  await expect(page.getByText("A divulgação foi autorizada.")).toBeVisible();
  await expect(page.locator(".contact-value")).toHaveText("revisao.nova@example.com");
  await other.close();
});

test("a leitura não escreve e os actores do mesmo utilizador ficam isolados", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Isolado ${Date.now()}`, ["Produtor"]);
  await registerContact(page, "email", "isolado.contacto@example.com");
  const contactUrl = page.url();
  const actorId = actorIdFrom(contactUrl);
  await page.getByRole("link", { name: "Voltar aos contactos" }).click();
  await page.getByRole("link", { name: "Voltar ao actor" }).click();
  await createActor(page, `Outro ${Date.now()}`, ["Produtor"]);
  const otherActor = actorIdFrom(page.url());
  await page.goto(`/actores/${otherActor}/contactos`);
  await expect(page.getByText("isolado.contacto@example.com")).toHaveCount(0);
  await page.goto(`/actores/${otherActor}/contactos/${contactIdFrom(contactUrl)}`);
  await expect(page.getByRole("heading", { name: "Contacto não encontrado" })).toBeVisible();
  await expect(page.getByText("isolado.contacto@example.com")).toHaveCount(0);

  const reader = account("i73-read");
  setAccess({ ...reader, actorId, mode: "read" });
  await page.context().clearCookies();
  await login(page, reader);
  await page.goto(contactUrl);
  await expect(page.getByText("isolado.contacto@example.com")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar contacto" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Autorizar divulgação" })).toHaveCount(0);
  await expect(page.getByText("Histórico de autorizações")).toBeVisible();
  await page.goto(`/actores/${actorId}/contactos/novo`);
  await expect(page.getByRole("button", { name: "Registar contacto" })).toHaveCount(0);

  setAccess({ ...reader, actorId, mode: "revoke" });
  await page.goto(`/actores/${actorId}/contactos`);
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.getByText(NOT_FOUND_MESSAGE)).toBeVisible();
  await expect(page.getByText("isolado.contacto@example.com")).toHaveCount(0);

  const stranger = account("i73-fora");
  setAccess({ ...stranger, actorId, mode: "read" });
  setAccess({ ...stranger, actorId, mode: "revoke" });
  await page.context().clearCookies();
  await login(page, stranger);
  await page.goto(contactUrl);
  await expect(page.getByText("isolado.contacto@example.com")).toHaveCount(0);
});

test("o visitante só vê o contacto depois da acção e deixa de o ver depois da revogação", async ({ page, browser }) => {
  const stamp = Date.now();
  const actorName = `Associação de Produtores da Moamba ${stamp}`;
  const product = `Tomate ${stamp}`;
  await login(page, credentials());
  await createActor(page, actorName, ["Produtor"]);
  const actorUrl = page.url();
  await registerProduct(page, product, "Tomate de época", "Hortícolas");
  await page.goto(actorUrl);
  await createOffer(page, product, "45.00", "120.00", "available");
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByRole("button", { name: "Suspender" })).toBeVisible();
  const offerId = offerIdFrom(page.url());

  await page.goto(actorUrl);
  await registerContact(page, "email", "produtor@example.com");
  const contactUrl = page.url();

  const visitor = await anonymousPage(browser);
  const seen: string[] = [];
  visitor.on("request", (request) => {
    if (request.url().includes("/contactos")) seen.push(request.url());
  });
  await visitor.goto(`/ofertas?q=${encodeURIComponent(product)}`);
  await visitor.getByRole("link", { name: `Ver oferta de ${product}` }).click();
  await expect(visitor.getByRole("heading", { name: product })).toBeVisible();
  await expect(visitor.getByRole("button", { name: "Ver contactos" })).toBeVisible();
  expect(await visitor.content()).not.toContain("produtor@example.com");
  expect(seen).toEqual([]);
  await visitor.screenshot({ path: shot("oferta-antes-consulta.png"), fullPage: true });
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Não existem contactos comerciais disponíveis para esta oferta.")).toBeVisible();

  await page.goto(contactUrl);
  await authorize(page);
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("produtor@example.com")).toBeVisible();
  await visitor.screenshot({ path: shot("oferta-contacto-divulgado.png"), fullPage: true });
  await visitor.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(visitor);
  await visitor.screenshot({ path: shot("oferta-contacto-360.png"), fullPage: true });
  await visitor.setViewportSize({ width: 1280, height: 800 });

  await page.locator("#edit-value").fill("comercial@example.com");
  await confirmedClick(page, "Guardar contacto");
  await expect(page.getByText("Se existia uma autorização vigente, foi revogada.")).toBeVisible();
  await expect(page.locator(".contact-value")).toHaveText("comercial@example.com");
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Não existem contactos comerciais disponíveis para esta oferta.")).toBeVisible();
  await expect(visitor.getByText("produtor@example.com")).toHaveCount(0);
  await expect(visitor.getByText("comercial@example.com")).toHaveCount(0);

  await authorize(page);
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("comercial@example.com")).toBeVisible();
  await expect(visitor.getByText("produtor@example.com")).toHaveCount(0);

  await page.getByRole("checkbox", { name: "Confirmo a revogação desta autorização." }).check();
  await confirmedClick(page, "Revogar autorização");
  await expect(page.getByText("Sem autorização vigente")).toBeVisible();
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Não existem contactos comerciais disponíveis para esta oferta.")).toBeVisible();
  await expect(visitor.getByText("comercial@example.com")).toHaveCount(0);
  await visitor.screenshot({ path: shot("oferta-sem-contactos.png"), fullPage: true });
  await visitor.context().close();

  expect(offerId).toMatch(/^[0-9a-f-]{36}$/i);
});

test("a elegibilidade pública esconde e restaura só o que o ciclo permite", async ({ page, browser }) => {
  const stamp = Date.now();
  const product = `Couve ${stamp}`;
  await login(page, credentials());
  await createActor(page, `Elegível ${stamp}`, ["Produtor"]);
  const actorUrl = page.url();
  const actorId = actorIdFrom(actorUrl);
  await registerProduct(page, product, "Hortícola de folha", "Hortícolas");
  const productUrl = page.url();
  await page.goto(actorUrl);
  await createOffer(page, product, "45.00", "120.00", "available");
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.locator("main p.eyebrow")).toHaveText("Publicada");
  const offerUrl = `/ofertas/${offerIdFrom(page.url())}`;
  await page.goto(actorUrl);
  await registerContact(page, "email", "elegivel.contacto@example.com");
  await authorize(page);

  const visitor = await anonymousPage(browser);
  await visitor.goto(offerUrl);
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("elegivel.contacto@example.com")).toBeVisible();

  await page.goto(actorUrl);
  await page.getByRole("link", { name: "Ofertas" }).click();
  await page.getByRole("link", { name: new RegExp(product) }).click();
  await page.getByRole("button", { name: "Suspender" }).click();
  await expect(page.locator("main p.eyebrow")).toHaveText("Suspensa");
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Oferta não encontrada ou indisponível.")).toBeVisible();
  await expect(visitor.getByText("elegivel.contacto@example.com")).toHaveCount(0);

  await page.getByRole("button", { name: "Republicar" }).click();
  await expect(page.locator("main p.eyebrow")).toHaveText("Publicada");
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("elegivel.contacto@example.com")).toBeVisible();

  await page.goto(actorUrl);
  await page.getByRole("checkbox", { name: "Produtor" }).uncheck();
  await page.getByRole("checkbox", { name: "Comprador" }).check();
  await confirmedClick(page, "Substituir papéis");
  await expect(page.getByRole("checkbox", { name: "Produtor" })).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Comprador" })).toBeChecked();
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Oferta não encontrada ou indisponível.")).toBeVisible();
  await page.getByRole("checkbox", { name: "Produtor" }).check();
  await confirmedClick(page, "Substituir papéis");
  await expect(page.getByRole("checkbox", { name: "Produtor" })).toBeChecked();
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("elegivel.contacto@example.com")).toBeVisible();

  await page.goto(productUrl);
  await page.getByRole("button", { name: "Arquivar produto" }).click();
  await confirmedClick(page, "Confirmar arquivo");
  await expect(page.getByText("Arquivado", { exact: true })).toBeVisible();
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("Oferta não encontrada ou indisponível.")).toBeVisible();

  await page.goto(actorUrl);
  await registerProduct(page, `Repolho ${stamp}`, "Hortícola", "Hortícolas");
  await page.goto(actorUrl);
  await createOffer(page, `Repolho ${stamp}`, "10.00", "1.00", "available");
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retirar oferta" }).click();
  await page.getByRole("button", { name: "Confirmar retirada" }).click();
  await expect(page.getByText("Retirada", { exact: true })).toBeVisible();
  const withdrawn = `/ofertas/${offerIdFrom(page.url())}`;
  await visitor.goto(withdrawn);
  await expect(visitor.getByRole("heading", { name: "Oferta não encontrada" })).toBeVisible();

  await page.goto(actorUrl);
  await page.getByRole("link", { name: "Contactos comerciais" }).click();
  await page.getByRole("link", { name: /Email/ }).first().click();
  await page.getByRole("checkbox", { name: "Confirmo a desactivação deste contacto." }).check();
  await page.getByRole("button", { name: "Desactivar contacto" }).click();
  await expect(page.getByText("Inactivo", { exact: true })).toBeVisible();
  await visitor.context().close();
  expect(isActorId(actorId)).toBe(true);
});

test("uma oferta indisponível elegível continua a divulgar o contacto autorizado", async ({ page, browser }) => {
  const stamp = Date.now();
  const product = `Cebola ${stamp}`;
  await login(page, credentials());
  await createActor(page, `Indisponível ${stamp}`, ["Produtor"]);
  const actorUrl = page.url();
  await registerProduct(page, product, "Bolbo", "Hortícolas");
  await page.goto(actorUrl);
  await createOffer(page, product, "45.00", "0", "unavailable");
  await page.getByRole("button", { name: "Publicar" }).click();
  const offerUrl = `/ofertas/${offerIdFrom(page.url())}`;
  await page.goto(actorUrl);
  await registerContact(page, "email", "indisponivel.contacto@example.com");
  await authorize(page);
  const visitor = await anonymousPage(browser);
  await visitor.goto(offerUrl);
  await expect(visitor.getByText("Indisponível", { exact: true })).toBeVisible();
  await visitor.getByRole("button", { name: "Ver contactos" }).click();
  await expect(visitor.getByText("indisponivel.contacto@example.com")).toBeVisible();
  await visitor.context().close();
});

test("uma resposta atrasada não repõe contactos de outra oferta", async ({ page }) => {
  let releaseFirst: (() => void) | undefined;
  const first = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  await page.route("**/api/public/ofertas/**/contactos", async (route) => {
    const url = route.request().url();
    if (url.includes("/ofertas/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/")) {
      await first;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [{ channel: "email", value: "antigo@example.com" }] }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.goto("/ofertas/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
  await page.getByRole("button", { name: "Ver contactos" }).click();
  await page.goto("/ofertas/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
  releaseFirst?.();
  await page.getByRole("button", { name: "Ver contactos" }).click();
  await expect(page.getByText("Não existem contactos comerciais disponíveis para esta oferta.")).toBeVisible();
  await expect(page.getByText("antigo@example.com")).toHaveCount(0);
  await page.unroute("**/api/public/ofertas/**/contactos");
});

test("uma falha simulada da consulta pública não termina a sessão nem conserva contactos", async ({ page }) => {
  await page.route("**/api/public/ofertas/**/contactos", (route) => route.abort());
  await page.goto("/ofertas/cccccccc-cccc-cccc-cccc-cccccccccccc");
  await page.getByRole("button", { name: "Ver contactos" }).click();
  await expect(page.getByText(CONNECTION_MESSAGE)).toBeVisible();
  await expect(page).not.toHaveURL(/\/login/);
  await page.unroute("**/api/public/ofertas/**/contactos");
  await page.route("**/api/public/ofertas/**/contactos", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    }),
  );
  await page.getByRole("button", { name: "Ver contactos" }).click();
  await expect(page.getByText("Não existem contactos comerciais disponíveis para esta oferta.")).toBeVisible();
  await expect(page.getByText(CONNECTION_MESSAGE)).toHaveCount(0);
});

test("um cookie inválido não impede a consulta pública", async ({ page }) => {
  await page.context().addCookies([
    { name: SESSION_COOKIE, value: "lixo", url: hostWebUrl() },
  ]);
  await page.route("**/api/public/ofertas/**/contactos", (route) => {
    expect(route.request().headers().authorization).toBeUndefined();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [{ channel: "email", value: "publico.cookie@example.com" }] }),
    });
  });
  await page.goto("/ofertas/dddddddd-dddd-dddd-dddd-dddddddddddd");
  await page.getByRole("button", { name: "Ver contactos" }).click();
  await expect(page.getByText("publico.cookie@example.com")).toBeVisible();
  expect(page.url()).not.toContain("publico.cookie@example.com");
});

test("o teclado percorre o contacto, a confirmação e a validação", async ({ page }) => {
  await login(page, credentials());
  await createActor(page, `Teclado contacto ${Date.now()}`, ["Produtor"]);
  await page.getByRole("link", { name: "Contactos comerciais" }).click();
  await page.getByRole("link", { name: "Registar contacto" }).click();
  await page.waitForURL(/\/contactos\/novo$/);
  await expect(page.getByRole("button", { name: "Registar contacto" })).toBeVisible();
  await expect(page.getByText("A carregar os contactos.")).toHaveCount(0);

  await expect(page.getByLabel("Canal")).toHaveAttribute("id", "create-channel");
  await expect(page.getByLabel("Valor")).toHaveAttribute("id", "create-value");

  await page.locator("#create-channel").focus();
  await page.locator("#create-channel").press("Tab");
  await expect(page.locator("#create-value")).toBeFocused();
  await expectVisibleFocus(page);
  await page.locator("#create-value").press("Shift+Tab");
  await expect(page.locator("#create-channel")).toBeFocused();

  await page.getByRole("button", { name: "Registar contacto" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#create-value")).toBeFocused();
  expect(await validationMessage(page, "#create-value")).not.toBe("");

  await page.locator("#create-channel").focus();
  await page.locator("#create-channel").press("e");
  await expect(page.locator("#create-channel")).toHaveValue("email");
  await page.locator("#create-channel").press("ArrowDown");
  await expect(page.locator("#create-channel")).toHaveValue("whatsapp");
  await page.locator("#create-channel").press("ArrowUp");
  await expect(page.locator("#create-channel")).toHaveValue("email");
  await page.locator("#create-value").focus();
  await page.keyboard.type("teclado.contacto@example.com");
  await page.locator("#create-value").press("Tab");
  await expect(page.getByRole("button", { name: "Registar contacto" })).toBeFocused();
  await page.getByRole("button", { name: "Registar contacto" }).press("Tab");
  await expect(page.getByRole("button", { name: "Registar contacto" })).not.toBeFocused();
  await page.getByRole("button", { name: "Registar contacto" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/contactos\/[0-9a-f-]{36}$/i);

  const confirm = page.getByRole("checkbox", { name: /Confirmo a divulgação/ });
  await confirm.focus();
  await confirm.press("Tab");
  await expect(page.getByRole("button", { name: "Autorizar divulgação" })).toBeFocused();
  await page.getByRole("button", { name: "Autorizar divulgação" }).press("Shift+Tab");
  await expect(confirm).toBeFocused();
  await confirm.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert").filter({ hasText: "A confirmação explícita é obrigatória." })).toBeVisible();

  await confirm.focus();
  await page.keyboard.press("Space");
  await expect(confirm).toBeChecked();
  await confirm.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Divulgação autorizada")).toBeVisible();
});

async function confirmedClick(page: Page, name: string) {
  const finished = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/actores/") &&
      response.status() < 500,
  );
  await page.getByRole("button", { name }).click();
  await finished;
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

async function registerContact(page: Page, channel: string, value: string) {
  await page.getByRole("link", { name: "Contactos comerciais" }).click();
  await page.getByRole("link", { name: "Registar contacto" }).click();
  await page.locator("#create-channel").selectOption(channel);
  await page.locator("#create-value").fill(value);
  await page.getByRole("button", { name: "Registar contacto" }).click();
  await page.waitForURL(/\/contactos\/[0-9a-f-]{36}$/i);
}

async function authorize(page: Page) {
  await page.getByRole("checkbox", { name: /Confirmo a divulgação/ }).check();
  await page.getByRole("button", { name: "Autorizar divulgação" }).click();
  await expect(page.getByText("Divulgação autorizada")).toBeVisible();
}

async function registerProduct(page: Page, name: string, description: string, category: string) {
  await page.getByRole("link", { name: "Produtos" }).click();
  await page.getByRole("link", { name: "Registar produto" }).click();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-description").fill(description);
  await page.locator("#create-category").fill(category);
  await page.getByRole("button", { name: "Registar produto" }).click();
  await page.waitForURL(/\/produtos\/[0-9a-f-]{36}$/i);
}

async function createOffer(
  page: Page,
  productName: string,
  price: string,
  quantity: string,
  availability: string,
) {
  await page.getByRole("link", { name: "Ofertas" }).click();
  await page.getByRole("link", { name: "Registar oferta" }).click();
  await page.locator("#create-product").selectOption({ label: productName });
  await page.locator("#create-price").fill(price);
  await page.locator("#create-currency").fill("MZN");
  await page.locator("#create-quantity").fill(quantity);
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption(availability);
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
}

async function anonymousPage(browser: Browser) {
  const context = await browser.newContext();
  return context.newPage();
}

function account(prefix: string) {
  return {
    email: `${prefix}-${Date.now()}@example.com`,
    password: randomBytes(18).toString("base64url"),
  };
}

function actorIdFrom(url: string): string {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const id = parts[1];
  if (!id || !isActorId(id)) throw new Error("A rota não tem o actor esperado.");
  return id;
}

function contactIdFrom(url: string): string {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const id = parts[3];
  if (!id || !isActorId(id)) throw new Error("A rota não tem o contacto esperado.");
  return id;
}

function offerIdFrom(url: string): string {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const id = parts[parts.length - 1];
  if (!id || !isActorId(id)) throw new Error("A rota não tem a oferta esperada.");
  return id;
}

async function validationMessage(page: Page, selector: string) {
  return page.locator(selector).evaluate((element) => {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement)) {
      return "";
    }
    return element.validationMessage.trim();
  });
}

async function expectVisibleFocus(page: Page) {
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflows).toBe(false);
}
