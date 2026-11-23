import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { NextRequest } from "next/server";

import {
  REQUEST_PROTO_HEADER,
  requestIsHttps,
  secureCookieFromObserved,
  sessionCookieOptions,
} from "../lib/cookie-policy";
import { SESSION_COOKIE } from "../lib/cookie-name";
import {
  CONNECTION_MESSAGE,
  CREDENTIALS_MESSAGE,
  kindForStatus,
  REJECTED_MESSAGE,
} from "../lib/errors";
import { originAllowed } from "../lib/origin";
import { middleware } from "../middleware";
import { appOrigin, credentials, hostApiUrl, shot, tokenLifetimeSeconds } from "./support";

test("o cookie fica Secure em HTTPS e um proto http não o desliga", () => {
  const secure = sessionCookieOptions({
    secure: requestIsHttps({
      protocol: "https:",
      forwardedProto: "http",
    }),
    maxAge: 1800,
  });
  expect(secure).toEqual({
    httpOnly: true,
    sameSite: "lax",
    secure: true,
    path: "/",
    maxAge: 1800,
  });

  expect(requestIsHttps({ protocol: "http:", forwardedProto: "http" })).toBe(false);
  expect(requestIsHttps({ protocol: "http", forwardedProto: "https" })).toBe(false);
  expect(requestIsHttps({ forwardedProto: "http, https" })).toBe(true);
  expect(requestIsHttps({ forwardedProto: "http" })).toBe(false);
  expect(secureCookieFromObserved("https")).toBe(true);
  expect(secureCookieFromObserved(null)).toBe(true);
  expect(secureCookieFromObserved("http")).toBe(false);

  const local = sessionCookieOptions({
    secure: requestIsHttps({ protocol: "http:" }),
    maxAge: 60,
  });
  expect(local.secure).toBe(false);
  expect(local.httpOnly).toBe(true);
  expect(local.sameSite).toBe("lax");
  expect(local.path).toBe("/");
});

test("o middleware grava o protocolo observado e não segue o cabeçalho cru", () => {
  const https = middleware(
    new NextRequest("https://kaivita.example/login", {
      headers: { host: "kaivita.example", "x-forwarded-proto": "http" },
    }),
  );
  expect(https.headers.get(`x-middleware-request-${REQUEST_PROTO_HEADER}`)).toBe("https");

  const http = middleware(
    new NextRequest("http://127.0.0.1:3010/login", {
      headers: { host: "127.0.0.1:3010", "x-forwarded-proto": "https" },
    }),
  );
  expect(http.headers.get(`x-middleware-request-${REQUEST_PROTO_HEADER}`)).toBe("http");

  const redirect = middleware(
    new NextRequest("http://evil.example/inicio", { headers: { host: "evil.example" } }),
  );
  expect(redirect.status).toBe(307);
  const target = new URL(redirect.headers.get("location") ?? "");
  expect(target.pathname).toBe("/login");
  expect(target.search).toBe("");
  expect(target.host).toBe("evil.example");
});

test("login e logout exigem a origem deste host", () => {
  expect(
    originAllowed({
      origin: "https://kaivita.example",
      host: "kaivita.example",
      fetchSite: "same-origin",
    }),
  ).toBe(true);
  expect(
    originAllowed({
      origin: "https://kaivita.example",
      host: "kaivita.example:443",
      fetchSite: null,
    }),
  ).toBe(true);
  expect(
    originAllowed({
      origin: "http://127.0.0.1:3010",
      host: "127.0.0.1:3010",
      fetchSite: null,
    }),
  ).toBe(true);
  expect(originAllowed({ origin: null, host: "kaivita.example", fetchSite: null })).toBe(false);
  expect(originAllowed({ origin: "https://kaivita.example", host: null, fetchSite: null })).toBe(false);
  expect(
    originAllowed({
      origin: "https://evil.example",
      host: "kaivita.example",
      fetchSite: "same-origin",
    }),
  ).toBe(false);
  expect(
    originAllowed({
      origin: "https://kaivita.example",
      host: "kaivita.example",
      fetchSite: "cross-site",
    }),
  ).toBe(false);
});

test("falhas de rede e respostas 5xx não são 401", () => {
  for (const status of [0, 500, 502, 503, 504]) {
    expect(kindForStatus(status)).toBe("unavailable");
  }
  expect(kindForStatus(401)).toBe("unauthorized");
  expect(kindForStatus(422)).toBe("validation");
});

test("a entrada e o login cabem em 360 px e em 1280 px", async ({ page }) => {
  for (const width of [360, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Entrar" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
    await expect(page.locator("#email")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.screenshot({ path: shot(`login-${width}.png`), fullPage: true });
  }
});

test("o teclado percorre email, palavra-passe e entrar", async ({ page }) => {
  const account = credentials();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/login");
  await page.keyboard.press("Tab");
  await expect(page.locator("#email")).toBeFocused();
  await page.keyboard.type(account.email);
  await page.keyboard.press("Tab");
  await expect(page.locator("#password")).toBeFocused();
  await page.keyboard.type(account.password);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Entrar" })).toBeFocused();

  const posted = page.waitForResponse(async (response) => {
    const headers = await response.headersArray();
    return headers.some(
      (header) =>
        header.name.toLowerCase() === "set-cookie" &&
        header.value.startsWith(`${SESSION_COOKIE}=`),
    );
  });
  await page.keyboard.press("Enter");
  const response = await posted;
  expectCookieFlags(cookieFlags(await response.headersArray()));
  await page.waitForURL(/\/inicio$/);
  await expect(page.getByRole("heading", { name: "Início" })).toBeVisible();
  await expect(page.getByText(account.email).first()).toBeVisible();

  const session = await sessionCookie(page);
  await expectSecretAbsent(page, session.value);
  await expectSecretAbsent(page, account.password);
  await page.screenshot({ path: shot("inicio-1280.png"), fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: shot("inicio-360.png"), fullPage: true });
});

test("credenciais inválidas não criam sessão", async ({ page }) => {
  const account = credentials();
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(`${account.password}-errada`);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.locator("p.alert")).toHaveText(CREDENTIALS_MESSAGE);
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.context().cookies()).toEqual(
    expect.not.arrayContaining([expect.objectContaining({ name: SESSION_COOKIE })]),
  );
  const html = await page.content();
  expect(html.includes(account.password)).toBe(false);
  expect(html.includes("access_token")).toBe(false);
  await page.locator("#password").fill("");
  await page.screenshot({ path: shot("credenciais-invalidas.png"), fullPage: true });
});

test("uma origem em falta ou estrangeira não cria nem apaga a sessão", async ({ page }) => {
  const account = credentials();
  await page.route("**/*", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const headers = route.request().headers();
    delete headers["origin"];
    const response = await route.fetch({ headers });
    await route.fulfill({ response });
  });
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.locator("p.alert")).toHaveText(REJECTED_MESSAGE);
  expect(await sessionOrNull(page)).toBeNull();
  await page.unroute("**/*");

  await page.route("**/*", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const headers = route.request().headers();
    headers["origin"] = "https://evil.example";
    const response = await route.fetch({ headers });
    await route.fulfill({ response });
  });
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.locator("p.alert")).toHaveText(REJECTED_MESSAGE);
  expect(await sessionOrNull(page)).toBeNull();
  await page.unroute("**/*");

  await login(page, account);
  await page.route("**/*", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const headers = route.request().headers();
    delete headers["origin"];
    const response = await route.fetch({ headers });
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Terminar sessão" }).click();
  await expect(page).toHaveURL(/\/inicio$/);
  expect(await sessionOrNull(page)).not.toBeNull();
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test("x-forwarded-proto http não marca Secure nem bloqueia o login local", async ({ page }) => {
  const account = credentials();
  await page.route("**/*", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const headers = route.request().headers();
    headers["x-forwarded-proto"] = "http";
    await route.continue({ headers });
  });
  const posted = page.waitForResponse(async (response) => {
    const headers = await response.headersArray();
    return headers.some(
      (header) =>
        header.name.toLowerCase() === "set-cookie" &&
        header.value.startsWith(`${SESSION_COOKIE}=`),
    );
  });
  await login(page, account);
  expect(cookieFlags(await (await posted).headersArray()).includes("secure")).toBe(false);
  await expect(page.getByRole("heading", { name: "Início" })).toBeVisible();
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test("a validação da API aparece nos campos sem ecoar os valores", async ({ page }) => {
  await page.goto("/login");
  await page.locator("form").evaluate((form) => {
    (form as HTMLFormElement).noValidate = true;
  });
  await page.locator("#email").fill("sem-arroba");
  await page.locator("#password").fill("curta");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.locator("#email-error")).toContainText("Email inválido");
  await expect(page.locator("#password-error")).toContainText("Palavra-passe inválida");
  const emailError = await page.locator("#email-error").innerText();
  const passwordError = await page.locator("#password-error").innerText();
  expect(emailError.includes("sem-arroba")).toBe(false);
  expect(passwordError.includes("curta")).toBe(false);
  const html = await page.content();
  expect(html.includes("access_token")).toBe(false);
});

test("/inicio sem sessão volta ao login", async ({ page }) => {
  await page.goto("/inicio");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Início" })).toHaveCount(0);
});

test("um cookie inválido termina a sessão", async ({ page }) => {
  await page.context().addCookies([
    {
      name: SESSION_COOKIE,
      value: "token-invalido",
      url: appOrigin,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.goto("/inicio");
  await expect(page).toHaveURL(/\/login\?motivo=sessao$/);
  await expect(page.getByRole("status")).toHaveText("A sessão terminou. Entre novamente.");
  expect(await sessionOrNull(page)).toBeNull();
  const html = await page.content();
  expect(html.includes("token-invalido")).toBe(false);
});

test("um token expirado termina a sessão", async ({ page }) => {
  const token = expiredAccessToken();
  await page.context().addCookies([
    {
      name: SESSION_COOKIE,
      value: token,
      url: appOrigin,
      httpOnly: true,
      sameSite: "Lax",
      expires: Math.floor(Date.now() / 1000) + 3600,
    },
  ]);
  await page.goto("/inicio");
  await expect(page).toHaveURL(/\/login\?motivo=sessao$/);
  expect(await sessionOrNull(page)).toBeNull();
  const html = await page.content();
  expect(html.includes(token)).toBe(false);
});

test("um cookie já expirado no browser não abre a área privada", async ({ page }) => {
  await page.context().addCookies([
    {
      name: SESSION_COOKIE,
      value: "cookie-expirado",
      url: appOrigin,
      httpOnly: true,
      sameSite: "Lax",
      expires: Math.floor(Date.now() / 1000) - 60,
    },
  ]);
  await page.goto("/inicio");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Início" })).toHaveCount(0);
});

test("terminar sessão impede o acesso seguinte", async ({ page }) => {
  const account = credentials();
  await login(page, account);
  await page.getByRole("button", { name: "Terminar sessão" }).click();
  await expect(page).toHaveURL(/\/login\?motivo=terminada$/);
  await expect(page.getByRole("status")).toHaveText("Sessão terminada neste browser.");
  expect(await sessionOrNull(page)).toBeNull();

  await page.goto("/inicio");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText(account.email)).toHaveCount(0);

  await login(page, account);
  await page.getByRole("button", { name: "Terminar sessão" }).click();
  await expect(page).toHaveURL(/\/login\?motivo=terminada$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  await expect(page.getByText(account.email)).toHaveCount(0);
});

test("uma falha de ligação não é tratada como credencial inválida", async ({ page }) => {
  test.setTimeout(120_000);
  const root = path.resolve(process.cwd(), "..");
  const stopped = spawnSync("docker", ["compose", "stop", "api"], {
    cwd: root,
    encoding: "utf8",
  });
  if (stopped.status !== 0) {
    throw new Error("Não foi possível parar a API para o teste de ligação.");
  }

  const account = credentials();
  try {
    await waitUntil(async () => !(await apiIsUp()));
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/login");
    await page.locator("#email").fill(account.email);
    await page.locator("#password").fill(account.password);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.locator("p.alert")).toHaveText(CONNECTION_MESSAGE, { timeout: 15_000 });
    expect(await sessionOrNull(page)).toBeNull();
    const html = await page.content();
    expect(html.includes(account.password)).toBe(false);
    expect(html.includes("access_token")).toBe(false);
    await page.locator("#password").fill("");
    await page.screenshot({ path: shot("ligacao-indisponivel.png"), fullPage: true });
  } finally {
    spawnSync("docker", ["compose", "start", "api"], { cwd: root, encoding: "utf8" });
    await waitUntil(apiIsUp);
  }
});

async function login(page: Page, account: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/inicio$/);
}

function expectCookieFlags(flags: string) {
  const lifetime = tokenLifetimeSeconds();
  expect(flags).toContain("httponly");
  expect(flags).toContain("samesite=lax");
  expect(flags).toContain("path=/");
  expect(flags.includes("secure")).toBe(false);
  expect(flags).toContain(`max-age=${lifetime}`);
}

function cookieFlags(headers: { name: string; value: string }[]): string {
  const header = headers.find(
    (item) =>
      item.name.toLowerCase() === "set-cookie" && item.value.startsWith(`${SESSION_COOKIE}=`),
  );
  if (!header) throw new Error("O cookie de sessão não veio na resposta.");
  return header.value.split(";").slice(1).join(";").toLowerCase();
}

async function sessionCookie(page: Page) {
  const cookie = await sessionOrNull(page);
  if (!cookie?.value) throw new Error("A sessão não ficou gravada no browser.");
  return cookie;
}

async function sessionOrNull(page: Page) {
  const cookies = await page.context().cookies();
  return cookies.find((cookie) => cookie.name === SESSION_COOKIE) ?? null;
}

async function expectSecretAbsent(page: Page, secret: string) {
  const html = await page.content();
  expect(html.includes(secret)).toBe(false);
  expect(html.includes("access_token")).toBe(false);
  const srcs = await page.locator("script[src]").evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("src") ?? "").filter((src) => src !== ""),
  );
  for (const src of srcs) {
    const address = new URL(src, page.url()).toString();
    const response = await page.request.get(address);
    const body = await response.text();
    expect(body.includes(secret)).toBe(false);
    expect(body.includes("access_token")).toBe(false);
  }
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflows = await page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  });
  expect(overflows).toBe(false);
}

function expiredAccessToken(): string {
  const backend = path.resolve(process.cwd(), "..", "backend");
  const python = path.join(backend, ".venv", "Scripts", "python.exe");
  const executable = existsSync(python) ? python : "python";
  const script = [
    "from app.tokens import issue_access_token",
    "import uuid",
    "print(issue_access_token(uuid.uuid4(), expires_in=-30), end='')",
  ].join("; ");
  const result = spawnSync(executable, ["-c", script], { cwd: backend, encoding: "utf8" });
  if (result.status !== 0 || !result.stdout.trim()) {
    throw new Error("Não foi possível preparar um token expirado.");
  }
  return result.stdout.trim();
}

async function apiIsUp(): Promise<boolean> {
  try {
    const response = await fetch(`${hostApiUrl()}/health`, {
      signal: AbortSignal.timeout(1500),
    });
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
