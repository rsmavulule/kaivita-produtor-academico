"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  createActor,
  isActorId,
  replaceActorRoles,
  updateActorProfile,
} from "../../../lib/actors";
import { CONNECTION_MESSAGE, REJECTED_MESSAGE } from "../../../lib/errors";
import { sameOrigin } from "../../../lib/origin";
import type { CreateFormState, ProfileFormState, RolesFormState } from "./form-state";

export async function createActorAction(
  _state: CreateFormState,
  formData: FormData,
): Promise<CreateFormState> {
  const next = createValues(formData);
  if (!(await sameOrigin())) return { ...next, formError: REJECTED_MESSAGE };

  const result = await createActor({
    kind: next.kind,
    displayName: next.displayName,
    generalLocation: blankToNull(next.location),
    roles: next.roles,
  });
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "ready") {
    revalidatePath("/actores");
    redirect(`/actores/${result.value.id}`);
  }
  if (result.kind === "unavailable") return { ...next, formError: CONNECTION_MESSAGE };
  if (result.kind !== "rejected") return { ...next, formError: REJECTED_MESSAGE };
  return {
    ...next,
    formError: result.message,
    kindError: result.fieldErrors?.kind,
    nameError: result.fieldErrors?.display_name,
    locationError: result.fieldErrors?.general_location,
    rolesError: result.fieldErrors?.roles,
  };
}

export async function updateProfileAction(
  actorId: string,
  _state: ProfileFormState,
  formData: FormData,
): Promise<ProfileFormState> {
  const next = {
    displayName: textField(formData, "display_name"),
    location: textField(formData, "general_location"),
  };
  if (!isActorId(actorId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }

  const result = await updateActorProfile(actorId, {
    displayName: next.displayName,
    generalLocation: blankToNull(next.location),
  });
  return finishWrite(actorId, next, result);
}

export async function replaceRolesAction(
  actorId: string,
  _state: RolesFormState,
  formData: FormData,
): Promise<RolesFormState> {
  const roles = formData
    .getAll("roles")
    .filter((value): value is string => typeof value === "string");
  const next = { roles };
  if (!isActorId(actorId) || !(await sameOrigin())) {
    return { ...next, formError: REJECTED_MESSAGE };
  }

  const result = await replaceActorRoles(actorId, roles);
  return finishWrite(actorId, next, result, "roles");
}

function finishWrite<T extends ProfileFormState | RolesFormState>(
  actorId: string,
  next: T,
  result: Awaited<ReturnType<typeof updateActorProfile>>,
  rolesField?: "roles",
): T {
  if (result.kind === "invalid") redirect("/sessao/invalida");
  if (result.kind === "missing") {
    revalidatePath(`/actores/${actorId}`);
    revalidatePath("/actores");
    return { ...next, lostAccess: true };
  }
  if (result.kind === "ready") {
    revalidatePath(`/actores/${actorId}`);
    revalidatePath("/actores");
    redirect(`/actores/${actorId}`);
  }
  if (result.kind === "unavailable") {
    return { ...next, formError: CONNECTION_MESSAGE };
  }
  return {
    ...next,
    formError: result.message,
    ...(rolesField
      ? { rolesError: result.fieldErrors?.roles }
      : {
          nameError: result.fieldErrors?.display_name,
          locationError: result.fieldErrors?.general_location,
        }),
  } as T;
}

function createValues(formData: FormData): CreateFormState {
  return {
    kind: textField(formData, "kind") || "person",
    displayName: textField(formData, "display_name"),
    location: textField(formData, "general_location"),
    roles: formData.getAll("roles").filter((value): value is string => typeof value === "string"),
  };
}

function textField(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

function blankToNull(value: string): string | null {
  return value === "" ? null : value;
}
