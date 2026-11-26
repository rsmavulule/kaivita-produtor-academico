"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { isActorId } from "../../../../../lib/actors";
import { CONNECTION_MESSAGE, REJECTED_MESSAGE } from "../../../../../lib/errors";
import { sameOrigin } from "../../../../../lib/origin";
import { PRODUCER_REQUIRED, archiveProduct, createProduct, updateProduct } from "../../../../../lib/products";
import type { ArchiveFormState, ProductFormState } from "./form-state";

export async function createProductAction(
  actorId: string,
  _state: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  const next = productValues(formData);
  if (!isActorId(actorId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }
  const result = await createProduct(actorId, {
    name: next.name,
    description: next.description,
    category: next.category,
    imageRef: blankToNull(next.imageRef),
    imageUseConfirmed: next.imageUseConfirmed,
  });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/produtos`);
    redirect(`/actores/${actorId}/produtos/${result.value.id}`);
  }
  return finishProduct(actorId, next, result);
}

export async function updateProductAction(
  actorId: string,
  productId: string,
  _state: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  const next = productValues(formData);
  if (!isActorId(actorId) || !isActorId(productId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }
  const result = await updateProduct(actorId, productId, {
    name: next.name,
    description: next.description,
    category: next.category,
    imageRef: blankToNull(next.imageRef),
    imageUseConfirmed: next.imageUseConfirmed,
  });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/produtos`);
    revalidatePath(`/actores/${actorId}/produtos/${productId}`);
    redirect(`/actores/${actorId}/produtos/${productId}`);
  }
  return finishProduct(actorId, next, result, productId);
}

export async function archiveProductAction(
  actorId: string,
  productId: string,
  _state: ArchiveFormState,
): Promise<ArchiveFormState> {
  if (!isActorId(actorId) || !isActorId(productId) || !(await sameOrigin())) {
    return { formError: REJECTED_MESSAGE };
  }
  const result = await archiveProduct(actorId, productId);
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}/produtos`);
    revalidatePath(`/actores/${actorId}/produtos/${productId}`);
    redirect(`/actores/${actorId}/produtos/${productId}`);
  }
  return finishProduct(actorId, {}, result, productId);
}

function finishProduct<T extends ProductFormState | ArchiveFormState>(
  actorId: string,
  next: T,
  result: Awaited<ReturnType<typeof createProduct>>,
  productId?: string,
): T {
  if (result.kind === "unavailable") return { ...next, formError: CONNECTION_MESSAGE };
  if (result.kind === "missing") {
    revalidatePath(`/actores/${actorId}`);
    revalidatePath(`/actores/${actorId}/produtos`);
    if (productId) revalidatePath(`/actores/${actorId}/produtos/${productId}`);
    return { ...next, lostAccess: true };
  }
  if (result.kind !== "rejected") return { ...next, formError: REJECTED_MESSAGE };
  if (result.message === PRODUCER_REQUIRED) {
    revalidatePath(`/actores/${actorId}`);
    revalidatePath(`/actores/${actorId}/produtos`);
    if (productId) revalidatePath(`/actores/${actorId}/produtos/${productId}`);
    return { ...next, accessChanged: true, formError: result.message };
  }
  if (!("name" in next)) return { ...next, formError: result.message };
  return {
    ...next,
    formError: result.message,
    nameError: result.fieldErrors?.name,
    descriptionError: result.fieldErrors?.description,
    categoryError: result.fieldErrors?.category,
    imageError: result.fieldErrors?.image_ref ?? result.fieldErrors?.image_use_confirmed,
  };
}

function productValues(formData: FormData): ProductFormState {
  return {
    name: textField(formData, "name"),
    description: textField(formData, "description"),
    category: textField(formData, "category"),
    imageRef: textField(formData, "image_ref"),
    imageUseConfirmed: formData.get("image_use_confirmed") === "yes",
  };
}

function textField(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

function blankToNull(value: string): string | null {
  return value === "" ? null : value;
}
