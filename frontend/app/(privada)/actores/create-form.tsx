"use client";

import { useActionState } from "react";

import { KIND_LABELS, ROLE_CODES, ROLE_LABELS } from "../../../lib/actor-view";
import { createActorAction } from "./actions";
import { emptyCreateState, type CreateFormState } from "./form-state";

export function CreateActorForm() {
  const [state, action, pending] = useActionState(createActorAction, emptyCreateState);
  const formKey = [state.kind, state.displayName, state.location, state.roles.join(","), state.formError ?? ""].join("|");

  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Novo actor</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <fieldset className="choices">
        <legend>Tipo</legend>
        {(["person", "organization"] as const).map((kind) => (
          <label className="choice" key={kind}>
            <input
              type="radio"
              name="kind"
              value={kind}
              defaultChecked={state.kind === kind}
            />
            {KIND_LABELS[kind]}
          </label>
        ))}
        {state.kindError ? <p className="field-error">{state.kindError}</p> : null}
      </fieldset>
      <TextField
        id="create-name"
        name="display_name"
        label="Nome"
        defaultValue={state.displayName}
        error={state.nameError}
        required
      />
      <TextField
        id="create-location"
        name="general_location"
        label="Localização geral"
        defaultValue={state.location}
        error={state.locationError}
      />
      <RoleChoices selected={state.roles} error={state.rolesError} />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A criar…" : "Criar actor"}
      </button>
    </form>
  );
}

export function TextField(input: {
  id: string;
  name: string;
  label: string;
  defaultValue: string;
  error?: string;
  required?: boolean;
}) {
  const errorId = `${input.id}-error`;
  return (
    <div className="field">
      <label htmlFor={input.id}>{input.label}</label>
      <input
        id={input.id}
        name={input.name}
        type="text"
        defaultValue={input.defaultValue}
        required={input.required}
        aria-invalid={input.error ? true : undefined}
        aria-describedby={input.error ? errorId : undefined}
      />
      {input.error ? (
        <p id={errorId} className="field-error">
          {input.error}
        </p>
      ) : null}
    </div>
  );
}

export function RoleChoices(input: { selected: string[]; error?: string }) {
  return (
    <fieldset className="choices">
      <legend>Papéis comerciais</legend>
      {ROLE_CODES.map((code) => (
        <label className="choice" key={code}>
          <input
            type="checkbox"
            name="roles"
            value={code}
            defaultChecked={input.selected.includes(code)}
          />
          {ROLE_LABELS[code]}
        </label>
      ))}
      {input.error ? <p className="field-error">{input.error}</p> : null}
    </fieldset>
  );
}
