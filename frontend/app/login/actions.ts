"use server";

import { redirect } from "next/navigation";

import { requestLogin } from "../../lib/api";
import { CREDENTIALS_MESSAGE, REJECTED_MESSAGE } from "../../lib/errors";
import { sameOrigin } from "../../lib/origin";
import { clearSession, writeSession } from "../../lib/session";
import type { LoginFormState } from "./form-state";

export async function loginAction(
  _state: LoginFormState,
  formData: FormData,
): Promise<LoginFormState> {
  if (!(await sameOrigin())) return { formError: REJECTED_MESSAGE };

  const email = formData.get("email");
  const password = formData.get("password");
  if (typeof email !== "string" || typeof password !== "string") {
    return { formError: REJECTED_MESSAGE };
  }

  const result = await requestLogin(email, password);
  if (result.kind === "ready") {
    await writeSession(result.token, result.expiresIn);
    redirect("/inicio");
  }
  if (result.kind === "unauthorized") return { formError: CREDENTIALS_MESSAGE };
  if (result.kind === "validation") {
    return {
      formError: result.message,
      emailError: result.emailError,
      passwordError: result.passwordError,
    };
  }
  return { formError: result.message };
}

export async function logoutAction(_formData: FormData): Promise<void> {
  if (!(await sameOrigin())) redirect("/inicio");
  await clearSession();
  redirect("/login?motivo=terminada");
}
