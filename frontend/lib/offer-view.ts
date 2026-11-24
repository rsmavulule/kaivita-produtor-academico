export const OFFER_NOT_FOUND = "Oferta não encontrada.";
export const PRODUCER_REQUIRED = "O actor não tem o papel producer.";
export const ARCHIVED_PRODUCT = "O produto está arquivado.";
export const WITHDRAWN_OFFER = "A oferta retirada não pode ser alterada.";
export const TRANSITION_REJECTED = "Transição de estado não permitida.";
export const NOT_PUBLISHABLE =
  "A publicação exige preço, moeda, quantidade, unidade e disponibilidade válidos.";
export const ZERO_AVAILABLE = "Quantidade zero não pode estar disponível.";
export const PUBLISHED_MUST_STAY_VALID = "A oferta publicada tem de permanecer válida.";

export const OFFER_STATUS_LABELS = {
  draft: "Rascunho",
  published: "Publicada",
  suspended: "Suspensa",
  withdrawn: "Retirada",
} as const;

export const AVAILABILITY_LABELS = {
  available: "Disponível",
  unavailable: "Indisponível",
} as const;

export type OfferStatus = keyof typeof OFFER_STATUS_LABELS;
export type Availability = keyof typeof AVAILABILITY_LABELS;

export type OfferView = {
  id: string;
  productId: string;
  ownerActorId: string;
  price: string | null;
  currency: string | null;
  quantity: string | null;
  unit: string | null;
  availability: Availability | null;
  deliveryTerms: string | null;
  status: OfferStatus;
};

export type OfferLoad<T> =
  | { kind: "ready"; value: T }
  | { kind: "invalid" }
  | { kind: "missing"; scope: "actor" | "offer" | "product" }
  | { kind: "unavailable" }
  | { kind: "rejected"; message: string; fieldErrors?: Record<string, string> };

export function canManageOffers(
  representation: "read" | "manage",
  roles: readonly string[],
): boolean {
  return representation === "manage" && roles.includes("producer");
}

export function amountLine(
  label: string,
  amount: string | null,
  extra: string | null,
): string {
  if (amount === null && extra === null) return `${label}: por preencher.`;
  const parts = [amount ?? "por preencher"];
  if (extra !== null) parts.push(extra);
  return `${label}: ${parts.join(" ")}.`;
}
