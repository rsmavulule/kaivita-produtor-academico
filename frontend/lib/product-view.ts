export const PRODUCT_NOT_FOUND = "Produto não encontrado.";
export const PRODUCER_REQUIRED = "O actor não tem o papel producer.";

export const STATUS_LABELS = {
  active: "Activo",
  archived: "Arquivado",
} as const;

export type ProductStatus = keyof typeof STATUS_LABELS;

export type ProductView = {
  id: string;
  ownerActorId: string;
  name: string;
  description: string;
  category: string;
  imageRef: string | null;
  status: ProductStatus;
};

export type ProductLoad<T> =
  | { kind: "ready"; value: T }
  | { kind: "invalid" }
  | { kind: "missing"; scope: "actor" | "product" }
  | { kind: "unavailable" }
  | { kind: "rejected"; message: string; fieldErrors?: Record<string, string> };

export function canRegisterProducts(
  representation: "read" | "manage",
  roles: readonly string[],
): boolean {
  return representation === "manage" && roles.includes("producer");
}
