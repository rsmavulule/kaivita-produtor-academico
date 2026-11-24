import { isActorId, NOT_FOUND_MESSAGE } from "./actor-view";
import { apiRequest } from "./api";
import { decimalForApi } from "./decimal";
import {
  OFFER_NOT_FOUND,
  type Availability,
  type OfferLoad,
  type OfferStatus,
  type OfferView,
} from "./offer-view";
import { PRODUCT_NOT_FOUND } from "./product-view";
import { readSessionToken } from "./session";

export {
  ARCHIVED_PRODUCT,
  AVAILABILITY_LABELS,
  NOT_PUBLISHABLE,
  OFFER_NOT_FOUND,
  OFFER_STATUS_LABELS,
  PRODUCER_REQUIRED,
  PUBLISHED_MUST_STAY_VALID,
  TRANSITION_REJECTED,
  WITHDRAWN_OFFER,
  ZERO_AVAILABLE,
  amountLine,
  canManageOffers,
} from "./offer-view";
export type { Availability, OfferLoad, OfferStatus, OfferView } from "./offer-view";

const OFFER_KEYS = [
  "id",
  "product_id",
  "owner_actor_id",
  "price",
  "currency",
  "quantity",
  "unit",
  "availability",
  "delivery_terms",
  "status",
] as const;

export type OfferDraft = {
  productId: string;
  price: string | null;
  currency: string | null;
  quantity: string | null;
  unit: string | null;
  availability: string | null;
  deliveryTerms: string | null;
};

export async function loadOffers(actorId: string): Promise<OfferLoad<OfferView[]>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  return loadJson(`/actors/${actorId}/offers`, (data) => parseOfferList(data, actorId));
}

export async function loadOffer(
  actorId: string,
  offerId: string,
): Promise<OfferLoad<OfferView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(offerId)) return { kind: "missing", scope: "offer" };
  return loadJson(`/actors/${actorId}/offers/${offerId}`, (data) => parseOffer(data, actorId));
}

export async function createOffer(
  actorId: string,
  body: OfferDraft,
): Promise<OfferLoad<OfferView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(body.productId)) return { kind: "missing", scope: "product" };
  return writeJson(`/actors/${actorId}/offers`, "POST", createBody(body), (data) =>
    parseOffer(data, actorId),
  );
}

export async function updateOffer(
  actorId: string,
  offerId: string,
  body: Omit<OfferDraft, "productId">,
): Promise<OfferLoad<OfferView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(offerId)) return { kind: "missing", scope: "offer" };
  return writeJson(
    `/actors/${actorId}/offers/${offerId}`,
    "PATCH",
    commercialBody(body),
    (data) => parseOffer(data, actorId),
  );
}

export async function transitionOffer(
  actorId: string,
  offerId: string,
  action: "publish" | "suspend" | "withdraw",
): Promise<OfferLoad<OfferView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(offerId)) return { kind: "missing", scope: "offer" };
  return writeJson(
    `/actors/${actorId}/offers/${offerId}/${action}`,
    "POST",
    undefined,
    (data) => parseOffer(data, actorId),
  );
}

export function commercialDraft(input: {
  price: string;
  currency: string;
  quantity: string;
  unit: string;
  availability: string;
  deliveryTerms: string;
}): Omit<OfferDraft, "productId"> {
  return {
    price: decimalForApi(input.price),
    currency: currencyForApi(input.currency),
    quantity: decimalForApi(input.quantity),
    unit: input.unit === "" ? null : input.unit,
    availability: input.availability === "" ? null : input.availability,
    deliveryTerms: input.deliveryTerms === "" ? null : input.deliveryTerms,
  };
}

function createBody(body: OfferDraft) {
  return { product_id: body.productId, ...commercialBody(body) };
}

function commercialBody(body: Omit<OfferDraft, "productId">) {
  return {
    price: body.price,
    currency: body.currency,
    quantity: body.quantity,
    unit: body.unit,
    availability: body.availability,
    delivery_terms: body.deliveryTerms,
  };
}

function currencyForApi(raw: string): string | null {
  if (raw === "") return null;
  const trimmed = raw.trim();
  if (/^[A-Za-z]{3}$/.test(trimmed)) return trimmed.toUpperCase();
  return raw;
}

async function loadJson<T>(
  path: string,
  parse: (data: unknown) => T | null,
): Promise<OfferLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  const result = await apiRequest(path, { token });
  return interpret(result, parse);
}

async function writeJson<T>(
  path: string,
  method: string,
  body: unknown,
  parse: (data: unknown) => T | null,
): Promise<OfferLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  const result = await apiRequest(path, { method, token, body });
  return interpret(result, parse);
}

function interpret<T>(
  result: Awaited<ReturnType<typeof apiRequest>>,
  parse: (data: unknown) => T | null,
): OfferLoad<T> {
  if (result.kind === "unauthorized") return { kind: "invalid" };
  if (result.kind === "unavailable") return { kind: "unavailable" };
  if (result.kind !== "ok") {
    if (result.status === 404) {
      const scope =
        result.detail === OFFER_NOT_FOUND
          ? "offer"
          : result.detail === PRODUCT_NOT_FOUND
            ? "product"
            : "actor";
      return { kind: "missing", scope };
    }
    if (result.detail === NOT_FOUND_MESSAGE) return { kind: "missing", scope: "actor" };
    return { kind: "rejected", message: result.message, fieldErrors: result.fieldErrors };
  }
  const value = parse(result.data);
  if (value === null) return { kind: "unavailable" };
  return { kind: "ready", value };
}

function parseOfferList(data: unknown, actorId: string): OfferView[] | null {
  if (!Array.isArray(data)) return null;
  const offers: OfferView[] = [];
  for (const item of data) {
    const offer = parseOffer(item, actorId);
    if (offer === null) return null;
    offers.push(offer);
  }
  return offers;
}

function parseOffer(data: unknown, actorId: string): OfferView | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const allowed = new Set<string>(OFFER_KEYS);
  if (Object.keys(record).some((key) => !allowed.has(key))) return null;
  if (typeof record.id !== "string" || !isActorId(record.id)) return null;
  if (typeof record.product_id !== "string" || !isActorId(record.product_id)) return null;
  if (record.owner_actor_id !== actorId) return null;
  const price = optionalDecimal(record.price);
  const quantity = optionalDecimal(record.quantity);
  const currency = optionalText(record.currency);
  const unit = optionalText(record.unit);
  const delivery = optionalText(record.delivery_terms);
  const availability = optionalAvailability(record.availability);
  const status = optionalStatus(record.status);
  if (price === undefined || quantity === undefined) return null;
  if (currency === undefined || unit === undefined || delivery === undefined) return null;
  if (availability === undefined || status === undefined) return null;
  return {
    id: record.id,
    productId: record.product_id,
    ownerActorId: actorId,
    price,
    currency,
    quantity,
    unit,
    availability,
    deliveryTerms: delivery,
    status,
  };
}

function optionalDecimal(value: unknown): string | null | undefined {
  if (value === null) return null;
  if (typeof value !== "string") return undefined;
  if (!/^\d+(\.\d+)?$/.test(value)) return undefined;
  return value;
}

function optionalText(value: unknown): string | null | undefined {
  if (value === null) return null;
  if (typeof value !== "string" || value.trim() === "") return undefined;
  return value;
}

function optionalAvailability(value: unknown): Availability | null | undefined {
  if (value === null) return null;
  if (value === "available" || value === "unavailable") return value;
  return undefined;
}

function optionalStatus(value: unknown): OfferStatus | undefined {
  if (
    value === "draft" ||
    value === "published" ||
    value === "suspended" ||
    value === "withdrawn"
  ) {
    return value;
  }
  return undefined;
}
