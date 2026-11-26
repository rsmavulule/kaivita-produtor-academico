import { expect, test, type Page } from "@playwright/test";

import { evidenceShot, credentials } from "./support";

const PHOTO = "https://example.com/mel-sintetico.png";
const MISSING = "https://example.com/ausente.png";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

test("a área de actuação, a fotografia e a declaração chegam à oferta pública", async ({ page }) => {
  const stamp = `i81${Date.now()}`;
  const coverage = `Sul de Moçambique ${stamp}`;
  await login(page, credentials());
  await page.goto("/actores");
  await page.getByRole("radio", { name: "Pessoa" }).check();
  await page.locator("#create-name").fill(`Produtor ${stamp}`);
  await page.locator("#create-location").fill("Beira");
  await page.locator("#create-coverage").fill(coverage);
  await page.getByRole("checkbox", { name: "Produtor" }).check();
  await page.getByRole("button", { name: "Criar actor" }).click();
  await page.waitForURL(/\/actores\/[0-9a-f-]{36}$/i);
  await expect(page.getByText(`Área de actuação: ${coverage}.`)).toBeVisible();
  await expect(page.getByText("Beira")).toBeVisible();
  await page.screenshot({ path: evidenceShot("I8.1", "area-de-actuacao.png"), fullPage: true });

  await page.getByRole("link", { name: "Produtos" }).click();
  await page.getByRole("link", { name: "Registar produto" }).click();
  await page.locator("#create-name").fill(`Mel ${stamp}`);
  await page.locator("#create-description").fill("Mel de exemplo");
  await page.locator("#create-category").fill("mel");
  await page.locator("#create-image").fill(PHOTO);
  const declaration = page.getByRole("checkbox", {
    name: "Declaro que possuo os direitos necessários ou autorização para utilizar esta fotografia.",
  });
  await expect(declaration).not.toBeChecked();
  await declaration.check();
  await page.screenshot({ path: evidenceShot("I8.1", "fotografia-e-declaracao.png"), fullPage: true });
  await page.getByRole("button", { name: "Registar produto" }).click();
  await page.waitForURL(/\/produtos\/[0-9a-f-]{36}$/i);
  await expect(page.getByText("Declaração de direitos: registada para esta fotografia.")).toBeVisible();
  await page.screenshot({ path: evidenceShot("I8.1", "declaracao-registada.png"), fullPage: true });
  const productUrl = page.url();

  await page.getByRole("link", { name: "Criar oferta" }).click();
  await page.locator("#create-price").fill("12.00");
  await page.locator("#create-currency").fill("MZN");
  await page.locator("#create-quantity").fill("2.00");
  await page.locator("#create-unit").fill("kg");
  await page.locator("#create-availability").selectOption("available");
  await page.getByRole("button", { name: "Registar oferta" }).click();
  await page.waitForURL(/\/ofertas\/[0-9a-f-]{36}$/i);
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  const offerId = page.url().split("/").pop() ?? "";

  await page.route(PHOTO, (route) => {
    const referer = route.request().headers().referer ?? "";
    expect(referer).toBe("");
    return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
  });
  await page.goto(`/ofertas/${offerId}`);
  await expect(page.getByRole("heading", { name: `Mel ${stamp}` })).toBeVisible();
  await expect(page.getByText(coverage)).toBeVisible();
  await expect(page.getByText("Beira")).toBeVisible();
  await expect(page.locator("img.product-photo")).toBeVisible();
  await page.screenshot({ path: evidenceShot("I8.1", "oferta-publica.png"), fullPage: true });

  await page.goto(productUrl);
  await page.locator("#edit-image").fill(MISSING);
  await expect(page.locator("#edit-image-rights")).not.toBeChecked();
  await page.locator("#edit-image-rights").check();
  await page.getByRole("button", { name: "Guardar produto" }).click();
  await expect(page.getByText(`Referência da imagem: ${MISSING}.`)).toBeVisible();
  await expect(page.getByText("Declaração de direitos: registada para esta fotografia.")).toBeVisible();

  await page.route(MISSING, (route) => route.fulfill({ status: 404, body: "ausente" }));
  await page.goto(`/ofertas/${offerId}`);
  await expect(page.getByRole("heading", { name: `Mel ${stamp}` })).toBeVisible();
  await expect(page.getByText(coverage)).toBeVisible();
  await expect(page.locator("img.product-photo")).toBeHidden();
});

async function login(page: Page, account: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/inicio$/);
}
