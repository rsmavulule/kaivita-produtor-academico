import { isActorId } from "./actor-view";
import { NOT_FOUND_MESSAGE } from "./actor-view";
import { apiRequest } from "./api";
import {
  PRODUCT_NOT_FOUND,
  type ProductLoad,
  type ProductStatus,
  type ProductView,
} from "./product-view";
import { readSessionToken } from "./session";

export { canRegisterProducts, PRODUCT_NOT_FOUND, PRODUCER_REQUIRED, STATUS_LABELS } from "./product-view";
export type { ProductLoad, ProductStatus, ProductView } from "./product-view";

export async function loadProducts(actorId: string): Promise<ProductLoad<ProductView[]>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  return loadJson(`/actors/${actorId}/products`, (data) => parseProductList(data, actorId));
}

export async function loadProduct(
  actorId: string,
  productId: string,
): Promise<ProductLoad<ProductView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(productId)) return { kind: "missing", scope: "product" };
  return loadJson(`/actors/${actorId}/products/${productId}`, (data) =>
    parseProduct(data, actorId),
  );
}

export async function createProduct(
  actorId: string,
  body: ProductDraft,
): Promise<ProductLoad<ProductView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  return writeJson(`/actors/${actorId}/products`, "POST", draftBody(body), (data) =>
    parseProduct(data, actorId),
  );
}

export async function updateProduct(
  actorId: string,
  productId: string,
  body: ProductDraft,
): Promise<ProductLoad<ProductView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(productId)) return { kind: "missing", scope: "product" };
  return writeJson(
    `/actors/${actorId}/products/${productId}`,
    "PATCH",
    draftBody(body),
    (data) => parseProduct(data, actorId),
  );
}

export async function archiveProduct(
  actorId: string,
  productId: string,
): Promise<ProductLoad<ProductView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(productId)) return { kind: "missing", scope: "product" };
  return writeJson(
    `/actors/${actorId}/products/${productId}/archive`,
    "POST",
    undefined,
    (data) => parseProduct(data, actorId),
  );
}

type ProductDraft = {
  name: string;
  description: string;
  category: string;
  imageRef: string | null;
  imageUseConfirmed: boolean;
};

function draftBody(body: ProductDraft) {
  return {
    name: body.name,
    description: body.description,
    category: body.category,
    image_ref: body.imageRef,
    image_use_confirmed: body.imageUseConfirmed,
  };
}

async function loadJson<T>(
  path: string,
  parse: (data: unknown) => T | null,
): Promise<ProductLoad<T>> {
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
): Promise<ProductLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  const result = await apiRequest(path, { method, token, body });
  return interpret(result, parse);
}

function interpret<T>(
  result: Awaited<ReturnType<typeof apiRequest>>,
  parse: (data: unknown) => T | null,
): ProductLoad<T> {
  if (result.kind === "unauthorized") return { kind: "invalid" };
  if (result.kind === "unavailable") return { kind: "unavailable" };
  if (result.kind !== "ok") {
    if (result.status === 404) {
      return {
        kind: "missing",
        scope: result.detail === PRODUCT_NOT_FOUND ? "product" : "actor",
      };
    }
    if (result.detail === NOT_FOUND_MESSAGE) return { kind: "missing", scope: "actor" };
    return {
      kind: "rejected",
      message: result.message,
      fieldErrors: result.fieldErrors,
    };
  }
  const value = parse(result.data);
  if (value === null) return { kind: "unavailable" };
  return { kind: "ready", value };
}

function parseProductList(data: unknown, actorId: string): ProductView[] | null {
  if (!Array.isArray(data)) return null;
  const products: ProductView[] = [];
  for (const item of data) {
    const product = parseProduct(item, actorId);
    if (product === null) return null;
    products.push(product);
  }
  return products;
}

function parseProduct(data: unknown, actorId: string): ProductView | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const allowed = new Set([
    "id",
    "owner_actor_id",
    "name",
    "description",
    "category",
    "image_ref",
    "image_use_confirmed",
    "status",
  ]);
  if (Object.keys(record).some((key) => !allowed.has(key))) return null;
  if (typeof record.id !== "string" || !isActorId(record.id)) return null;
  if (record.owner_actor_id !== actorId) return null;
  if (typeof record.name !== "string" || record.name.trim() === "") return null;
  if (typeof record.description !== "string" || record.description.trim() === "") return null;
  if (typeof record.category !== "string" || record.category.trim() === "") return null;
  if (record.image_ref !== null && typeof record.image_ref !== "string") return null;
  if (typeof record.image_use_confirmed !== "boolean") return null;
  if (record.status !== "active" && record.status !== "archived") return null;
  return {
    id: record.id,
    ownerActorId: record.owner_actor_id,
    name: record.name,
    description: record.description,
    category: record.category,
    imageRef: record.image_ref,
    imageUseConfirmed: record.image_use_confirmed,
    status: record.status,
  };
}
