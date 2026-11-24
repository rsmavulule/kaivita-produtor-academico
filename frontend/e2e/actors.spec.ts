import { randomBytes } from "node:crypto";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { isActorId, NOT_FOUND_MESSAGE } from "../lib/actor-view";
import { parseApiError } from "../lib/errors";
import { setAccess } from "./access";
import { credentials, evidenceShot, hostApiUrl } from "./support";

const shot = (name: string) => evidenceShot("I5.2", name);

test("o 422 em texto e em lista não repete o valor rejeitado", () => {
  expect(isActorId("nao-e-uuid")).toBe(false);
  expect(isActorId("11111111-1111-4111-8111-111111111111")).toBe(true);

  const text = parseApiError(422, { detail: "Papel desconhecido." });
  expect(text.kind).toBe("validation");
  expect(text.message).toBe("Papel desconhecido.");
  expect(text.message.includes("admin")).toBe(false);

  const listed = parseApiError(422, {
    detail: [{ loc: ["body", "roles"], msg: "Papel repetido.", type: "value_error" }],
  });
  expect(listed.fieldErrors?.roles).toBe("Papel repetido.");
  expect(listed.message.includes("buyer")).toBe(false);
});

test("a lista e a criação de pessoa e organização", async ({ page }) => {
  const account = credentials();
  await login(page, account);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/actores");
  await expect(page.getByRole("heading", { name: "Actores" })).toBeVisible();
  await page.screenshot({ path: shot("actores-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("actores-360.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  const person = `Pessoa ${Date.now()}`;
  await page.locator("#create-name").fill(person);
  await page.locator("#create-location").fill("Maputo");
  await page.getByRole("checkbox", { name: "Produtor" }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
  await expect(page.getByRole("heading", { name: person })).toBeVisible();
  await expect(page.getByText("Pessoa.")).toBeVisible();
  await expect(page.getByText("Gestão")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Produtor" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar perfil" })).toBeVisible();

  await page.goto("/actores");
  const personLink = page.getByRole("link", { name: new RegExp(person) });
  await expect(personLink).toContainText("Pessoa");
  await expect(personLink).toContainText("Maputo");
  await expect(personLink).toContainText("Gestão");

  const organization = `Organização ${Date.now()}`;
  await page.getByRole("radio", { name: "Organização" }).check();
  await page.locator("#create-name").fill(organization);
  await page.locator("#create-location").fill("Beira");
  await page.getByRole("checkbox", { name: "Comprador" }).check();
  await page.getByRole("checkbox", { name: "Parceiro" }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
  await expect(page.getByRole("heading", { name: organization })).toBeVisible();
  await expect(page.getByText("Organização.")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Comprador" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Parceiro" })).toBeVisible();
});

test("o teclado percorre o formulário de criação", async ({ page }) => {
  await login(page, credentials());
  await page.goto("/actores");
  const name = page.locator("#create-name");
  await expect(page.getByRole("button", { name: "Criar actor" })).toBeVisible();
  await name.focus();
  await expect(name).toBeFocused();
  await page.keyboard.type("Teclado");
  await page.keyboard.press("Tab");
  await expect(page.locator("#create-location")).toBeFocused();
  await page.keyboard.type("Lichinga");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("checkbox", { name: "Produtor" })).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.getByRole("checkbox", { name: "Produtor" })).toBeChecked();
});

test("a gestão edita o perfil, limpa a localização e substitui os papéis", async ({ page }) => {
  const account = credentials();
  await login(page, account);
  const name = `Gestão ${Date.now()}`;
  await createThroughForm(page, name, "Inhambane", ["Produtor"]);
  await page.screenshot({ path: shot("actor-manage-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("actor-manage-360.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  const renamed = `${name} actualizado`;
  await page.locator("#profile-name").fill(renamed);
  await page.locator("#profile-location").fill("Nampula");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.getByRole("heading", { name: renamed })).toBeVisible();
  await expect(page.getByText("Nampula")).toBeVisible();

  await page.locator("#profile-location").fill("");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.getByText("Localização desconhecida")).toBeVisible();

  await page.getByRole("checkbox", { name: "Produtor" }).uncheck();
  await page.getByRole("checkbox", { name: "Comprador" }).check();
  await page.getByRole("checkbox", { name: "Parceiro" }).check();
  await page.getByRole("button", { name: "Substituir papéis" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Comprador" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Parceiro" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Produtor" })).toHaveCount(0);
});

test("um erro de perfil ou de papéis preserva o que estava gravado", async ({ page }) => {
  await login(page, credentials());
  const name = `Estável ${Date.now()}`;
  await createThroughForm(page, name, "Tete", ["Produtor"]);

  await page.locator("#profile-name").evaluate((input) => {
    (input as HTMLInputElement).required = false;
  });
  await page.locator("#profile-name").fill("   ");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.locator("#profile-name-error")).toContainText("Nome inválido");
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.locator("#profile-name")).toHaveValue("   ");

  const rolesForm = page.locator("form", {
    has: page.getByRole("button", { name: "Substituir papéis" }),
  });
  await page.getByRole("checkbox", { name: "Produtor" }).uncheck();
  await page.getByRole("button", { name: "Substituir papéis" }).click();
  await expect(rolesForm.locator(".field-error")).toHaveText("É necessário pelo menos um papel.");
  await expect(page.getByRole("listitem").filter({ hasText: "Produtor" })).toBeVisible();

  await replaceHiddenRoles(rolesForm, ["producer", "admin"]);
  await page.getByRole("button", { name: "Substituir papéis" }).click();
  await expect(rolesForm.locator(".field-error")).toHaveText("Papel desconhecido.");
  await expect(rolesForm.locator(".field-error")).not.toContainText("admin");
  await expect(page.getByRole("listitem").filter({ hasText: "Produtor" })).toBeVisible();

  await replaceHiddenRoles(rolesForm, ["buyer", "buyer"]);
  await page.getByRole("button", { name: "Substituir papéis" }).click();
  await expect(rolesForm.locator(".field-error")).toHaveText("Papel repetido.");
  await expect(rolesForm.locator(".field-error")).not.toContainText("buyer");
  await expect(page.getByRole("listitem").filter({ hasText: "Produtor" })).toBeVisible();
});

test("a leitura não edita e a API recusa a escrita", async ({ page }) => {
  await login(page, credentials());
  const name = `Só leitura ${Date.now()}`;
  await createThroughForm(page, name, "Gaza", ["Produtor"]);
  const actorId = actorIdFrom(page.url());
  const reader = {
    email: `i52-read-${Date.now()}@example.com`,
    password: randomBytes(18).toString("base64url"),
  };
  setAccess({ ...reader, actorId, mode: "read" });

  await page.context().clearCookies();
  await login(page, reader);
  await page.goto(`/actores/${actorId}`);
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText("Leitura", { exact: true })).toBeVisible();
  await expect(page.getByText("A edição exige gestão.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar perfil" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Substituir papéis" })).toHaveCount(0);
  await page.screenshot({ path: shot("actor-read.png"), fullPage: true });

  const token = await apiToken(reader);
  const denied = await fetch(`${hostApiUrl()}/actors/${actorId}`, {
    method: "PATCH",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ display_name: "Nome recusado" }),
  });
  expect(denied.status).toBe(404);
  const body = await denied.json();
  expect(body).toEqual({ detail: NOT_FOUND_MESSAGE });
  await page.reload();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText("Nome recusado")).toHaveCount(0);
});

test("um actor inacessível não revela dados", async ({ page }) => {
  await login(page, credentials());
  await page.goto("/actores/11111111-1111-4111-8111-111111111199");
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.locator("p.alert")).toHaveText(NOT_FOUND_MESSAGE);
  await page.goto("/actores/nao-e-um-uuid");
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
});

test("uma associação revogada deixa de mostrar o actor", async ({ page }) => {
  const account = credentials();
  await login(page, account);
  const name = `Revogável ${Date.now()}`;
  const renamed = "Nome que não pode ficar";
  await createThroughForm(page, name, "Sofala", ["Produtor"]);
  const actorId = actorIdFrom(page.url());
  setAccess({ ...account, actorId, mode: "revoke" });

  await page.locator("#profile-name").fill(renamed);
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.getByRole("heading", { name: "Actor não encontrado" })).toBeVisible();
  await expect(page.getByText(name)).toHaveCount(0);
  await expect(page.getByText(renamed)).toHaveCount(0);
  await page.goto("/actores");
  await expect(page.getByRole("link", { name: new RegExp(name) })).toHaveCount(0);
});

async function replaceHiddenRoles(form: Locator, values: string[]) {
  await form.evaluate((node, codes) => {
    node.querySelectorAll("input[type='hidden'][name='roles']").forEach((item) => item.remove());
    for (const value of codes) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "roles";
      input.value = value;
      node.appendChild(input);
    }
  }, values);
}

async function login(page: Page, account: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/inicio$/);
}

async function createThroughForm(page: Page, name: string, location: string, roles: string[]) {
  await page.goto("/actores");
  await page.getByRole("radio", { name: "Pessoa" }).check();
  await page.locator("#create-name").fill(name);
  await page.locator("#create-location").fill(location);
  for (const role of roles) await page.getByRole("checkbox", { name: role }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
}

function actorIdFrom(url: string): string {
  const id = new URL(url).pathname.split("/").pop() ?? "";
  if (!isActorId(id)) throw new Error("A ficha não devolveu um identificador válido.");
  return id;
}

async function apiToken(account: { email: string; password: string }): Promise<string> {
  const response = await fetch(`${hostApiUrl()}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(account),
  });
  const body = (await response.json()) as { access_token?: string };
  if (!response.ok || !body.access_token) {
    throw new Error("Não foi possível obter uma sessão de teste na API.");
  }
  return body.access_token;
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflows = await page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  });
  expect(overflows).toBe(false);
}
