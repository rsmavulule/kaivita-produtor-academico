import { isActorId, NOT_FOUND_MESSAGE } from "./actor-view";
import { apiRequest } from "./api";
import {
  AUTHORIZATION_NOT_FOUND,
  CONTACT_NOT_FOUND,
  type AuthorizationView,
  type ContactChannel,
  type ContactView,
  isChannel,
} from "./contact-view";
import type { FieldName } from "./errors";
import { readSessionToken } from "./session";

export type ContactLoad<T> =
  | { kind: "ready"; status: number; value: T }
  | { kind: "invalid" }
  | { kind: "missing"; scope: "actor" | "contact" | "authorization" }
  | { kind: "unavailable" }
  | { kind: "conflict"; message: string }
  | { kind: "rejected"; message: string; fieldErrors?: Partial<Record<FieldName, string>> };

export async function loadContacts(actorId: string): Promise<ContactLoad<ContactView[]>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  return loadJson(`/actors/${actorId}/contacts`, (data) => parseContactList(data));
}

export async function loadContact(
  actorId: string,
  contactId: string,
): Promise<ContactLoad<ContactView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(contactId)) return { kind: "missing", scope: "contact" };
  return loadJson(`/actors/${actorId}/contacts/${contactId}`, (data) => parseContact(data));
}

export async function loadAuthorizations(
  actorId: string,
  contactId: string,
): Promise<ContactLoad<AuthorizationView[]>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(contactId)) return { kind: "missing", scope: "contact" };
  return loadJson(`/actors/${actorId}/contacts/${contactId}/authorizations`, (data) =>
    parseAuthorizations(data, contactId),
  );
}

export async function createContact(
  actorId: string,
  body: { channel: ContactChannel; value: string },
): Promise<ContactLoad<ContactView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  return writeJson(`/actors/${actorId}/contacts`, "POST", body, (data) => parseContact(data));
}

export async function updateContact(
  actorId: string,
  contactId: string,
  body: { channel: ContactChannel; value: string },
): Promise<ContactLoad<ContactView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(contactId)) return { kind: "missing", scope: "contact" };
  return writeJson(`/actors/${actorId}/contacts/${contactId}`, "PATCH", body, (data) =>
    parseContact(data),
  );
}

export async function deactivateContact(
  actorId: string,
  contactId: string,
): Promise<ContactLoad<ContactView>> {
  if (!isActorId(actorId)) return { kind: "missing", scope: "actor" };
  if (!isActorId(contactId)) return { kind: "missing", scope: "contact" };
  return writeJson(
    `/actors/${actorId}/contacts/${contactId}/deactivate`,
    "POST",
    undefined,
    (data) => parseContact(data),
  );
}

export async function grantDisclosure(input: {
  actorId: string;
  contactId: string;
  contactRevision: number;
  confirmed: true;
}): Promise<ContactLoad<AuthorizationView>> {
  return writeJson(
    `/actors/${input.actorId}/contacts/${input.contactId}/authorizations`,
    "POST",
    {
      contact_revision: input.contactRevision,
      purpose: "commercial_discovery",
      notice_version: "v1",
      confirmed: input.confirmed,
    },
    (data) => parseAuthorization(data, input.contactId),
  );
}

export async function revokeDisclosure(input: {
  actorId: string;
  contactId: string;
  authorizationId: string;
}): Promise<ContactLoad<AuthorizationView>> {
  if (!isActorId(input.authorizationId)) return { kind: "missing", scope: "authorization" };
  return writeJson(
    `/actors/${input.actorId}/contacts/${input.contactId}/authorizations/${input.authorizationId}/revoke`,
    "POST",
    undefined,
    (data) => parseAuthorization(data, input.contactId),
  );
}

async function loadJson<T>(
  path: string,
  parse: (data: unknown) => T | null,
): Promise<ContactLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  return interpret(await apiRequest(path, { token }), parse);
}

async function writeJson<T>(
  path: string,
  method: string,
  body: unknown,
  parse: (data: unknown) => T | null,
): Promise<ContactLoad<T>> {
  const token = await readSessionToken();
  if (!token) return { kind: "invalid" };
  return interpret(await apiRequest(path, { method, token, body }), parse);
}

function interpret<T>(
  result: Awaited<ReturnType<typeof apiRequest>>,
  parse: (data: unknown) => T | null,
): ContactLoad<T> {
  if (result.kind === "unauthorized") return { kind: "invalid" };
  if (result.kind === "unavailable") return { kind: "unavailable" };
  if (result.kind !== "ok") {
    if (result.status === 404) return { kind: "missing", scope: missingScope(result.detail) };
    if (result.detail === NOT_FOUND_MESSAGE) return { kind: "missing", scope: "actor" };
    if (result.status === 409 && result.detail) return { kind: "conflict", message: result.detail };
    return { kind: "rejected", message: result.message, fieldErrors: result.fieldErrors };
  }
  const value = parse(result.data);
  if (value === null) return { kind: "unavailable" };
  return { kind: "ready", status: result.status, value };
}

function missingScope(detail: string | undefined): "actor" | "contact" | "authorization" {
  if (detail === CONTACT_NOT_FOUND) return "contact";
  if (detail === AUTHORIZATION_NOT_FOUND) return "authorization";
  return "actor";
}

function parseContactList(data: unknown): ContactView[] | null {
  if (!data || typeof data !== "object") return null;
  const items = (data as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  const contacts: ContactView[] = [];
  for (const item of items) {
    const contact = parseContact(item);
    if (contact === null) return null;
    contacts.push(contact);
  }
  return contacts;
}

function parseContact(data: unknown): ContactView | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const allowed = new Set([
    "id",
    "channel",
    "value",
    "visibility",
    "status",
    "revision",
    "created_at",
    "updated_at",
  ]);
  if (Object.keys(record).some((key) => !allowed.has(key))) return null;
  if (typeof record.id !== "string" || !isActorId(record.id)) return null;
  if (!isChannel(record.channel)) return null;
  if (typeof record.value !== "string" || record.value.trim() === "") return null;
  if (record.visibility !== "private" && record.visibility !== "public") return null;
  if (record.status !== "active" && record.status !== "inactive") return null;
  if (!isPositiveInteger(record.revision)) return null;
  if (typeof record.created_at !== "string" || typeof record.updated_at !== "string") return null;
  return {
    id: record.id,
    channel: record.channel,
    value: record.value,
    visibility: record.visibility,
    status: record.status,
    revision: record.revision,
  };
}

function parseAuthorizations(data: unknown, contactId: string): AuthorizationView[] | null {
  if (!data || typeof data !== "object") return null;
  const items = (data as { items?: unknown }).items;
  if (!Array.isArray(items)) return null;
  const authorizations: AuthorizationView[] = [];
  for (const item of items) {
    const authorization = parseAuthorization(item, contactId);
    if (authorization === null) return null;
    authorizations.push(authorization);
  }
  return authorizations;
}

function parseAuthorization(data: unknown, contactId: string): AuthorizationView | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const allowed = new Set([
    "id",
    "contact_id",
    "contact_revision",
    "channel",
    "purpose",
    "notice_version",
    "status",
    "granted_at",
    "granted_by_user_id",
    "revoked_at",
    "revoked_by_user_id",
    "revocation_reason",
  ]);
  if (Object.keys(record).some((key) => !allowed.has(key))) return null;
  if (typeof record.id !== "string" || !isActorId(record.id)) return null;
  if (record.contact_id !== contactId) return null;
  if (!isPositiveInteger(record.contact_revision) || !isChannel(record.channel)) return null;
  if (record.purpose !== "commercial_discovery") return null;
  if (typeof record.notice_version !== "string" || record.notice_version.trim() === "") return null;
  if (record.status !== "granted" && record.status !== "revoked") return null;
  if (typeof record.granted_at !== "string") return null;
  if (typeof record.granted_by_user_id !== "string" || !isActorId(record.granted_by_user_id)) {
    return null;
  }
  if (record.revoked_at !== null && typeof record.revoked_at !== "string") return null;
  if (record.revoked_by_user_id !== null && typeof record.revoked_by_user_id !== "string") return null;
  if (
    record.revocation_reason !== null &&
    record.revocation_reason !== "manual" &&
    record.revocation_reason !== "contact_changed" &&
    record.revocation_reason !== "contact_deactivated"
  ) {
    return null;
  }
  return {
    id: record.id,
    contactId,
    contactRevision: record.contact_revision,
    channel: record.channel,
    noticeVersion: record.notice_version,
    status: record.status,
    grantedAt: record.granted_at,
    revokedAt: record.revoked_at,
    reason: record.revocation_reason,
  };
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1;
}
