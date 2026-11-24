import { apiRequest } from "./api";
import {
  isActorId,
  type ActorLoad,
  type ActorView,
  type RoleCode,
  type RoleView,
} from "./actor-view";
import { readSessionToken } from "./session";

export {
  isActorId,
  KIND_LABELS,
  NOT_FOUND_MESSAGE,
  REPRESENTATION_LABELS,
  ROLE_CODES,
  ROLE_LABELS,
} from "./actor-view";
export type {
  ActorKind,
  ActorLoad,
  ActorView,
  Representation,
  RoleCode,
  RoleView,
} from "./actor-view";

export async function loadActors(): Promise<ActorLoad<ActorView[]>> {
  return loadJson("/actors", parseActorList);
}

export async function loadActor(actorId: string): Promise<ActorLoad<ActorView>> {
  if (!isActorId(actorId)) return { kind: "missing" };
  return loadJson(`/actors/${actorId}`, parseActor);
}

export async function loadActorRoles(actorId: string): Promise<ActorLoad<RoleView[]>> {
  if (!isActorId(actorId)) return { kind: "missing" };
  return loadJson(`/actors/${actorId}/roles`, parseRoles);
}

export async function loadCatalog(): Promise<ActorLoad<RoleView[]>> {
  return loadJson("/roles", parseRoles);
}

export async function createActor(body: {
  kind: string;
  displayName: string;
  generalLocation: string | null;
  roles: string[];
}): Promise<ActorLoad<{ id: string }>> {
  return writeJson("/actors", "POST", {
    kind: body.kind,
    display_name: body.displayName,
    general_location: body.generalLocation,
    roles: body.roles,
  }, parseCreatedId);
}

export async function updateActorProfile(
  actorId: string,
  body: { displayName: string; generalLocation: string | null },
): Promise<ActorLoad<{ id: string }>> {
  if (!isActorId(actorId)) return { kind: "missing" };
  return writeJson(`/actors/${actorId}`, "PATCH", {
    display_name: body.displayName,
    general_location: body.generalLocation,
  }, parseCreatedId);
}

export async function replaceActorRoles(
  actorId: string,
  roles: string[],
): Promise<ActorLoad<{ id: string }>> {
  if (!isActorId(actorId)) return { kind: "missing" };
  return writeJson(`/actors/${actorId}/roles`, "PUT", { roles }, () => ({ id: actorId }));
}

async function writeJson<T>(
  path: string,
  method: string,
  body: unknown,
  parse: (data: unknown) => T | null,
): Promise<ActorLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  const result = await apiRequest(path, { method, token, body });
  if (result.kind === "unauthorized") return { kind: "invalid" };
  if (result.kind === "unavailable") return { kind: "unavailable" };
  if (result.kind !== "ok") {
    if (result.status === 404) return { kind: "missing" };
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

function parseCreatedId(data: unknown): { id: string } | null {
  if (!data || typeof data !== "object") return null;
  const id = (data as { id?: unknown }).id;
  if (typeof id !== "string" || !isActorId(id)) return null;
  if ("representation" in data || "access_level" in data || "user_id" in data) return null;
  return { id };
}

async function loadJson<T>(
  path: string,
  parse: (data: unknown) => T | null,
): Promise<ActorLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  const result = await apiRequest(path, { token });
  if (result.kind === "unauthorized") return { kind: "invalid" };
  if (result.kind === "unavailable") return { kind: "unavailable" };
  if (result.kind !== "ok") {
    if (result.status === 404) return { kind: "missing" };
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

function parseActorList(data: unknown): ActorView[] | null {
  if (!Array.isArray(data)) return null;
  const actors: ActorView[] = [];
  for (const item of data) {
    const actor = parseActor(item);
    if (actor === null) return null;
    actors.push(actor);
  }
  return actors;
}

function parseActor(data: unknown): ActorView | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (typeof record.id !== "string" || !isActorId(record.id)) return null;
  if (record.kind !== "person" && record.kind !== "organization") return null;
  if (typeof record.display_name !== "string" || record.display_name.trim() === "") return null;
  if (record.general_location !== null && typeof record.general_location !== "string") return null;
  if (record.status !== "active" && record.status !== "inactive") return null;
  if (record.representation !== "read" && record.representation !== "manage") return null;
  if ("user_id" in record || "access_level" in record) return null;
  return {
    id: record.id,
    kind: record.kind,
    displayName: record.display_name,
    generalLocation: record.general_location,
    status: record.status,
    representation: record.representation,
  };
}

function parseRoles(data: unknown): RoleView[] | null {
  if (!Array.isArray(data)) return null;
  const roles: RoleView[] = [];
  for (const item of data) {
    if (!item || typeof item !== "object") return null;
    const record = item as Record<string, unknown>;
    if (typeof record.id !== "string" || !isActorId(record.id)) return null;
    if (!isRoleCode(record.code)) return null;
    roles.push({ id: record.id, code: record.code });
  }
  return roles;
}

function isRoleCode(value: unknown): value is RoleCode {
  return value === "producer" || value === "buyer" || value === "partner";
}
