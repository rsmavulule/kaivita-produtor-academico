"use client";

import { useActionState, useEffect } from "react";

import {
  CHANNEL_LABELS,
  CHANNELS,
  CHANGE_NOTICE,
  DEACTIVATE_NOTICE,
  NOTICE_V1,
  PURPOSE_LABEL,
  REGISTER_NOTICE,
  REVOKE_NOTICE,
  type ContactChannel,
} from "../../../../../lib/contact-view";
import {
  createContactAction,
  deactivateContactAction,
  grantDisclosureAction,
  revokeDisclosureAction,
  updateContactAction,
} from "./actions";
import type { ConfirmFormState, ContactFormState, GrantFormState } from "./form-state";

export function CreateContactForm({
  actorId,
  initial,
}: {
  actorId: string;
  initial: ContactFormState;
}) {
  const [state, action, pending] = useActionState(createContactAction.bind(null, actorId), initial);
  useReloadAfterChange(state.lostAccess);
  const formKey = [state.channel, state.value, state.formError ?? ""].join("|");
  if (state.lostAccess) return <Recheck />;
  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Novo contacto</h2>
      <p className="notice">{REGISTER_NOTICE}</p>
      {state.formError ? <Alert>{state.formError}</Alert> : null}
      <ContactFields state={state} idPrefix="create" />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A registar…" : "Registar contacto"}
      </button>
    </form>
  );
}

export function EditContactForm(input: {
  actorId: string;
  contactId: string;
  revision: number;
  initial: ContactFormState;
}) {
  const [state, action, pending] = useActionState(
    updateContactAction.bind(null, input.actorId, input.contactId, input.revision),
    input.initial,
  );
  useReloadAfterChange(state.lostAccess);
  const formKey = [state.channel, state.value, state.formError ?? ""].join("|");
  if (state.lostAccess) return <Recheck />;
  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Corrigir contacto</h2>
      <p className="notice">{CHANGE_NOTICE}</p>
      {state.formError ? <Alert>{state.formError}</Alert> : null}
      <ContactFields state={state} idPrefix="edit" />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A guardar…" : "Guardar contacto"}
      </button>
    </form>
  );
}

export function GrantDisclosureForm(input: {
  actorId: string;
  contactId: string;
  actorName: string;
  initial: GrantFormState;
}) {
  const [state, action, pending] = useActionState(
    grantDisclosureAction.bind(null, input.actorId, input.contactId),
    input.initial,
  );
  useReloadAfterChange(state.lostAccess);
  const formKey = [state.revision, state.channel, state.value, state.formError ?? ""].join("|");
  if (state.lostAccess) return <Recheck />;
  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Autorizar divulgação</h2>
      <p>Actor: {input.actorName}</p>
      <p>Canal actual: {CHANNEL_LABELS[state.channel]}</p>
      <p>Valor actual: {state.value}</p>
      <p>Finalidade: {PURPOSE_LABEL}</p>
      <p className="notice" id="disclosure-notice">{NOTICE_V1}</p>
      <p>A revogação posterior impede novas consultas nesta plataforma. Não apaga cópias já feitas por visitantes.</p>
      {state.formError ? <Alert>{state.formError}</Alert> : null}
      <input type="hidden" name="contact_revision" value={state.revision} />
      <input type="hidden" name="channel" value={state.channel} />
      <input type="hidden" name="shown_value" value={state.value} />
      <div className="field">
        <label htmlFor="grant-confirmed">
          <input id="grant-confirmed" name="confirmed" type="checkbox" />
          Confirmo a divulgação deste contacto, com o aviso apresentado.
        </label>
      </div>
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A autorizar…" : "Autorizar divulgação"}
      </button>
    </form>
  );
}

export function RevokeDisclosureForm(input: {
  actorId: string;
  contactId: string;
  authorizationId: string;
}) {
  const [state, action, pending] = useActionState(
    revokeDisclosureAction.bind(null, input.actorId, input.contactId, input.authorizationId),
    {} as ConfirmFormState,
  );
  useReloadAfterChange(state.lostAccess);
  if (state.lostAccess) return <Recheck />;
  return (
    <form action={action} className="form" aria-busy={pending}>
      <h2>Revogar divulgação</h2>
      <p className="notice">{REVOKE_NOTICE}</p>
      {state.formError ? <Alert>{state.formError}</Alert> : null}
      <div className="field">
        <label htmlFor="revoke-confirmed">
          <input id="revoke-confirmed" name="revoke_confirmed" type="checkbox" required />
          Confirmo a revogação desta autorização.
        </label>
      </div>
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A revogar…" : "Revogar autorização"}
      </button>
    </form>
  );
}

export function DeactivateContactForm(input: { actorId: string; contactId: string }) {
  const [state, action, pending] = useActionState(
    deactivateContactAction.bind(null, input.actorId, input.contactId),
    {} as ConfirmFormState,
  );
  useReloadAfterChange(state.lostAccess);
  if (state.lostAccess) return <Recheck />;
  return (
    <form action={action} className="form" aria-busy={pending}>
      <h2>Desactivar contacto</h2>
      <p className="notice">{DEACTIVATE_NOTICE}</p>
      {state.formError ? <Alert>{state.formError}</Alert> : null}
      <div className="field">
        <label htmlFor="deactivate-confirmed">
          <input id="deactivate-confirmed" name="deactivate_confirmed" type="checkbox" required />
          Confirmo a desactivação deste contacto.
        </label>
      </div>
      <button className="secondary" type="submit" disabled={pending}>
        {pending ? "A desactivar…" : "Desactivar contacto"}
      </button>
    </form>
  );
}

function ContactFields({ state, idPrefix }: { state: ContactFormState; idPrefix: string }) {
  return (
    <>
      <div className="field">
        <label htmlFor={`${idPrefix}-channel`}>Canal</label>
        <select
          id={`${idPrefix}-channel`}
          name="channel"
          defaultValue={state.channel}
          aria-invalid={state.channelError ? true : undefined}
          aria-describedby={state.channelError ? `${idPrefix}-channel-error` : undefined}
          required
        >
          {CHANNELS.map((channel) => (
            <option key={channel} value={channel}>
              {CHANNEL_LABELS[channel]}
            </option>
          ))}
        </select>
        {state.channelError ? <FieldError id={`${idPrefix}-channel-error`}>{state.channelError}</FieldError> : null}
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-value`}>Valor</label>
        <input
          id={`${idPrefix}-value`}
          name="value"
          type="text"
          maxLength={320}
          defaultValue={state.value}
          aria-invalid={state.valueError ? true : undefined}
          aria-describedby={state.valueError ? `${idPrefix}-value-error` : undefined}
          required
          autoComplete="off"
        />
        {state.valueError ? <FieldError id={`${idPrefix}-value-error`}>{state.valueError}</FieldError> : null}
      </div>
    </>
  );
}

function Alert({ children }: { children: string }) {
  return (
    <p className="alert" role="alert">
      {children}
    </p>
  );
}

function FieldError({ id, children }: { id: string; children: string }) {
  return (
    <p id={id} className="field-error">
      {children}
    </p>
  );
}

function Recheck() {
  return <p className="note">A confirmar o acesso.</p>;
}

function useReloadAfterChange(reload: boolean | undefined) {
  useEffect(() => {
    if (!reload) return;
    const path = window.location.pathname;
    if (path.startsWith("/actores/")) window.location.replace(path);
  }, [reload]);
}
