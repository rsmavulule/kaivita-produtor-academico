"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { isActorId } from "../../../../../lib/actors";
import {
  type ContactChannel,
  isChannel,
  STALE_REVISION,
} from "../../../../../lib/contact-view";
import {
  createContact,
  deactivateContact,
  grantDisclosure,
  loadContact,
  revokeDisclosure,
  updateContact,
} from "../../../../../lib/contacts";
import { CONNECTION_MESSAGE, REJECTED_MESSAGE } from "../../../../../lib/errors";
import { sameOrigin } from "../../../../../lib/origin";
import type { ConfirmFormState, ContactFormState, GrantFormState } from "./form-state";

export async function createContactAction(
  actorId: string,
  _state: ContactFormState,
  formData: FormData,
): Promise<ContactFormState> {
  const next = contactValues(formData);
  if (!isActorId(actorId) || !(await sameOrigin())) return { ...next, formError: REJECTED_MESSAGE };
  const channel = presentedChannel(formData);
  if (channel === null) return { ...next, channelError: "Canal inválido." };
  const result = await createContact(actorId, { channel, value: next.value });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/contactos`);
    redirect(`/actores/${actorId}/contactos/${result.value.id}`);
  }
  return finishContact(actorId, { ...next, channel }, result);
}

export async function updateContactAction(
  actorId: string,
  contactId: string,
  knownRevision: number,
  _state: ContactFormState,
  formData: FormData,
): Promise<ContactFormState> {
  const next = contactValues(formData);
  if (!isActorId(actorId) || !isActorId(contactId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }
  const channel = presentedChannel(formData);
  if (channel === null) return { ...next, channelError: "Canal inválido." };
  const result = await updateContact(actorId, contactId, { channel, value: next.value });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    const outcome = result.value.revision === knownRevision ? "equivalente" : "alterado";
    revalidatePath(`/actores/${actorId}/contactos`);
    revalidatePath(`/actores/${actorId}/contactos/${contactId}`);
    redirect(`/actores/${actorId}/contactos/${contactId}?resultado=${outcome}`);
  }
  return finishContact(actorId, { ...next, channel }, result, contactId);
}

export async function deactivateContactAction(
  actorId: string,
  contactId: string,
  _state: ConfirmFormState,
): Promise<ConfirmFormState> {
  if (!isActorId(actorId) || !isActorId(contactId) || !(await sameOrigin())) {
    return { formError: REJECTED_MESSAGE };
  }
  const result = await deactivateContact(actorId, contactId);
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/contactos`);
    revalidatePath(`/actores/${actorId}/contactos/${contactId}`);
    redirect(`/actores/${actorId}/contactos/${contactId}?resultado=inactivo`);
  }
  return finishContact(actorId, {}, result, contactId);
}

export async function grantDisclosureAction(
  actorId: string,
  contactId: string,
  _state: GrantFormState,
  formData: FormData,
): Promise<GrantFormState> {
  const presented = presentedGrant(formData);
  if (!isActorId(actorId) || !isActorId(contactId) || !(await sameOrigin())) {
    return { ...presented, formError: REJECTED_MESSAGE };
  }
  if (formData.get("confirmed") !== "on") {
    return { ...presented, formError: "A confirmação explícita é obrigatória." };
  }
  if (presented.revision < 1) {
    return { ...presented, formError: "A revisão confirmada não é válida. A divulgação não foi autorizada." };
  }
  const result = await grantDisclosure({
    actorId,
    contactId,
    contactRevision: presented.revision,
    confirmed: true,
  });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    const outcome = result.status === 200 ? "repetida" : "concedida";
    revalidatePath(`/actores/${actorId}/contactos/${contactId}`);
    redirect(`/actores/${actorId}/contactos/${contactId}?resultado=${outcome}`);
  }
  if (result.kind === "conflict") {
    const fresh = await loadContact(actorId, contactId);
    const base = fresh.kind === "ready"
      ? { revision: fresh.value.revision, channel: fresh.value.channel, value: fresh.value.value }
      : presented;
    return {
      ...base,
      formError: `${result.message} Confirme novamente o valor agora apresentado. A divulgação não foi autorizada.`,
    };
  }
  return finishContact(actorId, presented, result, contactId);
}

export async function revokeDisclosureAction(
  actorId: string,
  contactId: string,
  authorizationId: string,
  _state: ConfirmFormState,
): Promise<ConfirmFormState> {
  if (!isActorId(actorId) || !isActorId(contactId) || !isActorId(authorizationId) || !(await sameOrigin())) {
    return { formError: REJECTED_MESSAGE };
  }
  const result = await revokeDisclosure({ actorId, contactId, authorizationId });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/contactos/${contactId}`);
    redirect(`/actores/${actorId}/contactos/${contactId}?resultado=revogada`);
  }
  return finishContact(actorId, {}, result, contactId);
}

function finishContact<T extends ContactFormState | GrantFormState | ConfirmFormState>(
  actorId: string,
  next: T,
  result: Awaited<ReturnType<typeof createContact>>,
  contactId?: string,
): T {
  if (result.kind === "unavailable") return { ...next, formError: CONNECTION_MESSAGE };
  if (result.kind === "missing") {
    revalidatePath(`/actores/${actorId}/contactos`);
    if (contactId) revalidatePath(`/actores/${actorId}/contactos/${contactId}`);
    return { ...next, lostAccess: true };
  }
  if (result.kind === "conflict") {
    return { ...next, formError: result.message === STALE_REVISION ? result.message : result.message };
  }
  if (result.kind !== "rejected") return { ...next, formError: REJECTED_MESSAGE };
  if (!("value" in next)) return { ...next, formError: result.message };
  return {
    ...next,
    formError: result.message,
    channelError: result.fieldErrors?.channel,
    valueError: result.fieldErrors?.value,
  };
}

function contactValues(formData: FormData): ContactFormState {
  const channel = presentedChannel(formData) ?? "email";
  return { channel, value: textField(formData, "value") };
}

function presentedGrant(formData: FormData): GrantFormState {
  return {
    revision: presentedRevision(formData),
    channel: presentedChannel(formData) ?? "email",
    value: textField(formData, "shown_value"),
  };
}

function presentedChannel(formData: FormData): ContactChannel | null {
  const value = formData.get("channel");
  return isChannel(value) ? value : null;
}

function presentedRevision(formData: FormData): number {
  const raw = formData.get("contact_revision");
  if (typeof raw !== "string" || !/^[1-9]\d*$/.test(raw)) return 0;
  let value = 0;
  for (const character of raw) {
    value = value * 10 + (character.charCodeAt(0) - 48);
    if (value > 1_000_000) return 0;
  }
  return value;
}

function textField(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}
