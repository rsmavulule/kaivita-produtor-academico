"use client";

import { useActionState, useEffect } from "react";

import { replaceRolesAction, updateProfileAction } from "../actions";
import type { ProfileFormState, RolesFormState } from "../form-state";
import { RoleChoices, TextField } from "../create-form";

export function ProfileForm(input: {
  actorId: string;
  displayName: string;
  location: string;
}) {
  const initial: ProfileFormState = {
    displayName: input.displayName,
    location: input.location,
  };
  const [state, action, pending] = useActionState(
    updateProfileAction.bind(null, input.actorId),
    initial,
  );
  const formKey = [state.displayName, state.location, state.formError ?? ""].join("|");
  useRefreshAfterAccessLoss(state.lostAccess);

  if (state.lostAccess) return <AccessRecheck />;

  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Perfil</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <TextField
        id="profile-name"
        name="display_name"
        label="Nome"
        defaultValue={state.displayName}
        error={state.nameError}
        required
      />
      <TextField
        id="profile-location"
        name="general_location"
        label="Localização geral"
        defaultValue={state.location}
        error={state.locationError}
      />
      <p className="note">Deixe a localização vazia para a retirar.</p>
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A guardar…" : "Guardar perfil"}
      </button>
    </form>
  );
}

export function RolesForm(input: { actorId: string; roles: string[] }) {
  const initial: RolesFormState = { roles: input.roles };
  const [state, action, pending] = useActionState(
    replaceRolesAction.bind(null, input.actorId),
    initial,
  );
  const formKey = [state.roles.join(","), state.formError ?? ""].join("|");
  useRefreshAfterAccessLoss(state.lostAccess);

  if (state.lostAccess) return <AccessRecheck />;

  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Papéis</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <RoleChoices selected={state.roles} error={state.rolesError} />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A substituir…" : "Substituir papéis"}
      </button>
    </form>
  );
}

function useRefreshAfterAccessLoss(lostAccess: boolean | undefined) {
  useEffect(() => {
    if (!lostAccess) return;
    const path = window.location.pathname;
    if (path.startsWith("/actores/")) window.location.replace(path);
  }, [lostAccess]);
}

function AccessRecheck() {
  return <p className="note">A confirmar o acesso.</p>;
}
