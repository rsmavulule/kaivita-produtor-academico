"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { isActorId } from "../../../../../lib/actors";
import { CONNECTION_MESSAGE, REJECTED_MESSAGE } from "../../../../../lib/errors";
import {
  ARCHIVED_PRODUCT,
  PRODUCER_REQUIRED,
  TRANSITION_REJECTED,
  WITHDRAWN_OFFER,
  commercialDraft,
  createOffer,
  transitionOffer,
  updateOffer,
} from "../../../../../lib/offers";
import { PRODUCT_NOT_FOUND } from "../../../../../lib/products";
import { sameOrigin } from "../../../../../lib/origin";
import type { OfferFormState, TransitionFormState } from "./form-state";

export async function createOfferAction(
  actorId: string,
  _state: OfferFormState,
  formData: FormData,
): Promise<OfferFormState> {
  const next = offerValues(formData);
  if (!isActorId(actorId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }
  if (!isActorId(next.productId)) {
    return { ...next, productError: PRODUCT_NOT_FOUND };
  }
  const result = await createOffer(actorId, { productId: next.productId, ...draftOf(next) });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/ofertas`);
    redirect(`/actores/${actorId}/ofertas/${result.value.id}`);
  }
  return finishOffer(actorId, next, result);
}

export async function updateOfferAction(
  actorId: string,
  offerId: string,
  _state: OfferFormState,
  formData: FormData,
): Promise<OfferFormState> {
  const next = offerValues(formData, _state.productId);
  if (!isActorId(actorId) || !isActorId(offerId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }
  const result = await updateOffer(actorId, offerId, draftOf(next));
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidateOffer(actorId, offerId);
    redirect(`/actores/${actorId}/ofertas/${offerId}`);
  }
  return finishOffer(actorId, next, result, offerId);
}

export async function publishOfferAction(
  actorId: string,
  offerId: string,
  _state: TransitionFormState,
): Promise<TransitionFormState> {
  return runTransition(actorId, offerId, "publish");
}

export async function suspendOfferAction(
  actorId: string,
  offerId: string,
  _state: TransitionFormState,
): Promise<TransitionFormState> {
  return runTransition(actorId, offerId, "suspend");
}

export async function withdrawOfferAction(
  actorId: string,
  offerId: string,
  _state: TransitionFormState,
): Promise<TransitionFormState> {
  return runTransition(actorId, offerId, "withdraw");
}

async function runTransition(
  actorId: string,
  offerId: string,
  action: "publish" | "suspend" | "withdraw",
): Promise<TransitionFormState> {
  if (!isActorId(actorId) || !isActorId(offerId) || !(await sameOrigin())) {
    return { formError: REJECTED_MESSAGE };
  }
  const result = await transitionOffer(actorId, offerId, action);
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidateOffer(actorId, offerId);
    redirect(`/actores/${actorId}/ofertas/${offerId}`);
  }
  return finishOffer(actorId, {}, result, offerId);
}

function finishOffer<T extends OfferFormState | TransitionFormState>(
  actorId: string,
  next: T,
  result: Awaited<ReturnType<typeof createOffer>>,
  offerId?: string,
): T {
  if (result.kind === "unavailable") return { ...next, formError: CONNECTION_MESSAGE };
  if (result.kind === "missing" && result.scope === "product") {
    return { ...next, productError: PRODUCT_NOT_FOUND, formError: PRODUCT_NOT_FOUND };
  }
  if (result.kind === "missing") {
    revalidateOffer(actorId, offerId);
    return { ...next, lostAccess: true };
  }
  if (result.kind !== "rejected") return { ...next, formError: REJECTED_MESSAGE };
  if (result.message === PRODUCER_REQUIRED) {
    revalidateOffer(actorId, offerId);
    return { ...next, accessChanged: true, formError: result.message };
  }
  if (
    result.message === ARCHIVED_PRODUCT ||
    result.message === WITHDRAWN_OFFER ||
    result.message === TRANSITION_REJECTED
  ) {
    revalidateOffer(actorId, offerId);
    return { ...next, contextChanged: true, formError: result.message };
  }
  if (!("price" in next)) return { ...next, formError: result.message };
  return {
    ...next,
    formError: result.message,
    productError: result.fieldErrors?.product_id,
    priceError: result.fieldErrors?.price,
    currencyError: result.fieldErrors?.currency,
    quantityError: result.fieldErrors?.quantity,
    unitError: result.fieldErrors?.unit,
    availabilityError: result.fieldErrors?.availability,
    deliveryError: result.fieldErrors?.delivery_terms,
  };
}

function draftOf(state: OfferFormState) {
  return commercialDraft(state);
}

function offerValues(formData: FormData, productId = ""): OfferFormState {
  const chosen = textField(formData, "product_id");
  return {
    productId: chosen || productId,
    price: textField(formData, "price"),
    currency: textField(formData, "currency"),
    quantity: textField(formData, "quantity"),
    unit: textField(formData, "unit"),
    availability: textField(formData, "availability"),
    deliveryTerms: textField(formData, "delivery_terms"),
  };
}

function textField(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

function revalidateOffer(actorId: string, offerId?: string) {
  revalidatePath(`/actores/${actorId}`);
  revalidatePath(`/actores/${actorId}/ofertas`);
  revalidatePath(`/actores/${actorId}/produtos`);
  if (offerId) revalidatePath(`/actores/${actorId}/ofertas/${offerId}`);
}
