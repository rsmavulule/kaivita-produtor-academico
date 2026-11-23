"use client";

import { useActionState } from "react";

import { loginAction } from "./actions";
import type { LoginFormState } from "./form-state";

const initialState: LoginFormState = {};

export function LoginForm() {
  const [state, action, pending] = useActionState(loginAction, initialState);

  return (
    <form action={action} className="form" aria-busy={pending}>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}

      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          aria-invalid={state.emailError ? true : undefined}
          aria-describedby={state.emailError ? "email-error" : undefined}
        />
        {state.emailError ? (
          <p id="email-error" className="field-error">
            {state.emailError}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="password">Palavra-passe</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={state.passwordError ? true : undefined}
          aria-describedby={state.passwordError ? "password-error" : undefined}
        />
        {state.passwordError ? (
          <p id="password-error" className="field-error">
            {state.passwordError}
          </p>
        ) : null}
      </div>

      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A entrar…" : "Entrar"}
      </button>
    </form>
  );
}
