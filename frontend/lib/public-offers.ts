import { CONNECTION_MESSAGE } from "./errors";
import {
  HOME_LIMIT,
  isPublicOfferId,
  PAGE_SIZE,
  type PublicAvailability,
  type PublicFilters,
  type PublicOffer,
  type ProducerKind,
} from "./public-offer-view";

const REQUEST_TIMEOUT_MS = 8_000;
const DECIMAL_TEXT = /^\d+(\.\d+)?$/;

/**
 * Pedidos públicos. Não recebe token e não lê a sessão.
 * API_URL fica no servidor. O cabeçalho leva só accept.
 */
export function publicHeaders(): Headers {
  return new Headers({ accept: "application/json" });
}

export function classifyPublicStatus(
  status: number,
): "ok" | "missing" | "unavailable" | "rejected" {
  if (status >= 200 && status < 300) return "ok";
  if (status === 404) return "missing";
  if (status === 0 || status >= 500) return "unavailable";
  return "rejected";
}

export type PublicListResult =
  | { kind: "ready"; offers: PublicOffer[]; limit: number; offset: number; total: number }
  | { kind: "unavailable"; message: string }
  | { kind: "rejected"; message: string };

export type PublicDetailResult =
  | { kind: "ready"; offer: PublicOffer }
  | { kind: "missing" }
  | { kind: "invalid" }
  | { kind: "unavailable"; message: string }
  | { kind: "rejected"; message: string };

export async function listPublicOffers(
  filters: PublicFilters,
  limit = PAGE_SIZE,
): Promise<PublicListResult> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.category) params.set("category", filters.category);
  if (filters.location) params.set("location", filters.location);
  params.set("limit", String(limit));
  params.set("offset", String(filters.offset));
  const result = await publicGet(`/public/offers?${params.toString()}`);
  if (result.kind === "unavailable") return { kind: "unavailable", message: CONNECTION_MESSAGE };
  if (result.kind !== "ok") {
    return { kind: "rejected", message: "Não foi possível concluir a pesquisa. Tente novamente." };
  }
  const page = parsePage(result.data);
  if (page === null) return { kind: "unavailable", message: CONNECTION_MESSAGE };
  return { kind: "ready", ...page };
}

export async function listHomeOffers(): Promise<PublicListResult> {
  return listPublicOffers({ offset: 0 }, HOME_LIMIT);
}

export async function readPublicOffer(offerId: string): Promise<PublicDetailResult> {
  if (!isPublicOfferId(offerId)) return { kind: "invalid" };
  const result = await publicGet(`/public/offers/${offerId}`);
  if (result.kind === "missing") return { kind: "missing" };
  if (result.kind === "unavailable") return { kind: "unavailable", message: CONNECTION_MESSAGE };
  if (result.kind !== "ok") {
    return { kind: "rejected", message: "Não foi possível abrir a oferta. Tente novamente." };
  }
  const offer = parseOffer(result.data);
  if (offer === null) return { kind: "unavailable", message: CONNECTION_MESSAGE };
  return { kind: "ready", offer };
}

function readApiUrl(): string | null {
  const name = ["API", "URL"].join("_");
  const value = process.env[name];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed === "") return null;
  return trimmed.replace(/\/$/, "");
}

type PublicCall =
  | { kind: "ok"; data: unknown }
  | { kind: "missing" }
  | { kind: "unavailable" }
  | { kind: "rejected" };

async function publicGet(path: string): Promise<PublicCall> {
  const apiUrl = readApiUrl();
  if (apiUrl === null) return { kind: "unavailable" };
  try {
    const response = await fetch(`${apiUrl}${path}`, {
      method: "GET",
      headers: publicHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const status = classifyPublicStatus(response.status);
    if (status === "missing") return { kind: "missing" };
    if (status === "unavailable") return { kind: "unavailable" };
    if (status === "rejected") return { kind: "rejected" };
    return { kind: "ok", data: await readBody(response) };
  } catch {
    return { kind: "unavailable" };
  }
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text === "") return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function parsePage(
  data: unknown,
): { offers: PublicOffer[]; limit: number; offset: number; total: number } | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (!Array.isArray(record.items) || !isCount(record.limit) || !isCount(record.offset) || !isCount(record.total)) {
    return null;
  }
  const offers: PublicOffer[] = [];
  for (const item of record.items) {
    const offer = parseOffer(item);
    if (offer === null) return null;
    offers.push(offer);
  }
  return { offers, limit: record.limit, offset: record.offset, total: record.total };
}

function parseOffer(data: unknown): PublicOffer | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const product = record.product;
  const producer = record.producer;
  if (!product || typeof product !== "object" || !producer || typeof producer !== "object") return null;
  const productRecord = product as Record<string, unknown>;
  const producerRecord = producer as Record<string, unknown>;
  const imageRef = productRecord.image_ref;
  const coverageArea = producerRecord.coverage_area;
  const generalLocation = producerRecord.general_location;
  if (
    typeof record.id !== "string" ||
    !isPublicOfferId(record.id) ||
    !isDecimal(record.price) ||
    typeof record.currency !== "string" ||
    record.currency.trim() === "" ||
    !isDecimal(record.quantity) ||
    typeof record.unit !== "string" ||
    record.unit.trim() === "" ||
    !isAvailability(record.availability) ||
    !isOptionalText(record.delivery_terms) ||
    typeof productRecord.name !== "string" ||
    typeof productRecord.description !== "string" ||
    typeof productRecord.category !== "string" ||
    !isOptionalText(imageRef) ||
    (imageRef !== null && !isHttpsImage(imageRef)) ||
    typeof producerRecord.display_name !== "string" ||
    !isKind(producerRecord.kind) ||
    !isOptionalText(generalLocation) ||
    !isOptionalText(coverageArea)
  ) {
    return null;
  }
  return {
    id: record.id,
    price: record.price,
    currency: record.currency,
    quantity: record.quantity,
    unit: record.unit,
    availability: record.availability,
    deliveryTerms: record.delivery_terms,
    productName: productRecord.name,
    productDescription: productRecord.description,
    productCategory: productRecord.category,
    productImage: imageRef,
    producerName: producerRecord.display_name,
    producerKind: producerRecord.kind,
    producerLocation: generalLocation,
    producerCoverage: coverageArea,
  };
}

function isHttpsImage(value: string): boolean {
  if (value.length > 2048 || value.includes("\\") || /\s/.test(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.username === "" && url.password === "" && url.hostname !== "";
  } catch {
    return false;
  }
}

function isDecimal(value: unknown): value is string {
  return typeof value === "string" && DECIMAL_TEXT.test(value);
}

function isOptionalText(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isAvailability(value: unknown): value is PublicAvailability {
  return value === "available" || value === "unavailable";
}

function isKind(value: unknown): value is ProducerKind {
  return value === "person" || value === "organization";
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}
