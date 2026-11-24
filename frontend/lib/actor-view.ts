export const NOT_FOUND_MESSAGE = "Actor não encontrado.";

export const ROLE_CODES = ["producer", "buyer", "partner"] as const;
export type RoleCode = (typeof ROLE_CODES)[number];
export type ActorKind = "person" | "organization";
export type Representation = "read" | "manage";

export const ROLE_LABELS: Record<RoleCode, string> = {
  producer: "Produtor",
  buyer: "Comprador",
  partner: "Parceiro",
};
export const KIND_LABELS: Record<ActorKind, string> = {
  person: "Pessoa",
  organization: "Organização",
};
export const REPRESENTATION_LABELS: Record<Representation, string> = {
  read: "Leitura",
  manage: "Gestão",
};

const ACTOR_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isActorId(value: string): boolean {
  return ACTOR_ID.test(value);
}

export type ActorView = {
  id: string;
  kind: ActorKind;
  displayName: string;
  generalLocation: string | null;
  status: string;
  representation: Representation;
};

export type RoleView = { id: string; code: RoleCode };

export type ActorLoad<T> =
  | { kind: "ready"; value: T }
  | { kind: "invalid" }
  | { kind: "missing" }
  | { kind: "unavailable" }
  | { kind: "rejected"; message: string; fieldErrors?: Record<string, string> };
