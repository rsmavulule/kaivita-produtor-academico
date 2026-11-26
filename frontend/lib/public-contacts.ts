import { CONNECTION_MESSAGE } from "./errors";
import { isPublicOfferId } from "./public-offer-view";
import { classifyPublicStatus, publicHeaders } from "./public-offers";

const REQUEST_TIMEOUT_MS = 8_000;

export type PublicContact = { channel: "phone" | "email" | "whatsapp"; value: string };

export type PublicContactsResult =
  | { kind: "ready"; items: PublicContact[] }
  | { kind: "missing" }
  | { kind: "invalid" }
  | { kind: "unavailable"; message: string };

/**
 * Consulta pública sem token e sem ler a sessão.
 * O endereço da API fica no servidor.
 */
export async function readPublicContacts(offerId: string): Promise<PublicContactsResult> {
  if (!isPublicOfferId(offerId)) return { kind: "invalid" };
  const apiUrl = readApiUrl();
  if (apiUrl === null) return { kind: "unavailable", message: CONNECTION_MESSAGE };
  try {
    const response = await fetch(`${apiUrl}/public/offers/${offerId}/contacts`, {
      method: "GET",
      headers: publicHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const status = classifyPublicStatus(response.status);
    if (status === "missing") return { kind: "missing" };
    if (status === "unavailable") return { kind: "unavailable", message: CONNECTION_MESSAGE };
    if (status !== "ok") return { kind: "unavailable", message: CONNECTION_MESSAGE };
    const items = parseItems(await response.json());
    if (items === null) return { kind: "unavailable", message: CONNECTION_MESSAGE };
    return { kind: "ready", items };
  } catch {
    return { kind: "unavailable", message: CONNECTION_MESSAGE };
  }
}

function parseItems(data: unknown): PublicContact[] | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (Object.keys(record).some((key) => key !== "items") || !Array.isArray(record.items)) return null;
  const items: PublicContact[] = [];
  for (const item of record.items) {
    if (!item || typeof item !== "object") return null;
    const contact = item as Record<string, unknown>;
    if (Object.keys(contact).some((key) => key !== "channel" && key !== "value")) return null;
    if (contact.channel !== "phone" && contact.channel !== "email" && contact.channel !== "whatsapp") {
      return null;
    }
    if (typeof contact.value !== "string" || contact.value.trim() === "") return null;
    items.push({ channel: contact.channel, value: contact.value });
  }
  return items;
}

function readApiUrl(): string | null {
  const name = ["API", "URL"].join("_");
  const value = process.env[name];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed === "") return null;
  return trimmed.replace(/\/$/, "");
}
