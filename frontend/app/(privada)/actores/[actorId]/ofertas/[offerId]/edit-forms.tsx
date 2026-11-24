"use client";

import { useActionState, useState } from "react";

import {
  publishOfferAction,
  suspendOfferAction,
  updateOfferAction,
  withdrawOfferAction,
} from "../actions";
import type { OfferFormState, TransitionFormState } from "../form-state";
import { OfferFields, useReloadAfterChange } from "../nova/create-form";

export function OfferEditor(input: {
  actorId: string;
  offerId: string;
  price: string;
  currency: string;
  quantity: string;
  unit: string;
  availability: string;
  deliveryTerms: string;
  published: boolean;
  incomplete: boolean;
}) {
  const initial: OfferFormState = {
    productId: "",
    price: input.price,
    currency: input.currency,
    quantity: input.quantity,
    unit: input.unit,
    availability: input.availability,
    deliveryTerms: input.deliveryTerms,
  };
  const [state, action, pending] = useActionState(
    updateOfferAction.bind(null, input.actorId, input.offerId),
    initial,
  );
  useReloadAfterChange(state.lostAccess || state.accessChanged || state.contextChanged);
  if (state.lostAccess || state.accessChanged || state.contextChanged) {
    return <p className="note">A confirmar o acesso.</p>;
  }
  const formKey = [
    state.price,
    state.currency,
    state.quantity,
    state.unit,
    state.availability,
    state.deliveryTerms,
    state.formError ?? "",
  ].join("|");

  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Condições comerciais</h2>
      {input.published ? (
        <p className="note">Uma oferta publicada tem de continuar válida depois de gravar.</p>
      ) : null}
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <OfferFields state={state} idPrefix="edit" incomplete={input.incomplete} />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A guardar…" : "Guardar oferta"}
      </button>
    </form>
  );
}

export function OfferTransitions(input: {
  actorId: string;
  offerId: string;
  status: "draft" | "published" | "suspended";
}) {
  const [confirming, setConfirming] = useState(false);
  const [publishState, publishAction, publishPending] = useActionState(
    publishOfferAction.bind(null, input.actorId, input.offerId),
    {} as TransitionFormState,
  );
  const [suspendState, suspendAction, suspendPending] = useActionState(
    suspendOfferAction.bind(null, input.actorId, input.offerId),
    {} as TransitionFormState,
  );
  const [withdrawState, withdrawAction, withdrawPending] = useActionState(
    withdrawOfferAction.bind(null, input.actorId, input.offerId),
    {} as TransitionFormState,
  );
  const pending = publishPending || suspendPending || withdrawPending;
  const changed =
    flag(publishState) || flag(suspendState) || flag(withdrawState);
  useReloadAfterChange(changed);
  if (changed) return <p className="note">A confirmar o acesso.</p>;

  const error = publishState.formError || suspendState.formError || withdrawState.formError;
  const publishLabel = input.status === "suspended" ? "Republicar" : "Publicar";

  return (
    <div className="form">
      <h2>Ciclo de vida</h2>
      {error ? (
        <p className="alert" role="alert">
          {error}
        </p>
      ) : null}
      {input.status === "draft" || input.status === "suspended" ? (
        <form action={publishAction} aria-busy={publishPending}>
          <button className="primary" type="submit" disabled={pending}>
            {publishPending ? "A publicar…" : publishLabel}
          </button>
        </form>
      ) : null}
      {input.status === "published" ? (
        <form action={suspendAction} aria-busy={suspendPending}>
          <button className="secondary" type="submit" disabled={pending}>
            {suspendPending ? "A suspender…" : "Suspender"}
          </button>
        </form>
      ) : null}
      {confirming ? (
        <form action={withdrawAction} aria-busy={withdrawPending}>
          <p>A retirada é definitiva. A oferta deixa de poder ser editada ou republicada.</p>
          <p className="links">
            <button className="primary" type="submit" disabled={pending}>
              {withdrawPending ? "A retirar…" : "Confirmar retirada"}
            </button>
            <button className="secondary" type="button" onClick={() => setConfirming(false)} disabled={pending}>
              Cancelar
            </button>
          </p>
        </form>
      ) : (
        <p className="links">
          <button className="secondary" type="button" onClick={() => setConfirming(true)} disabled={pending}>
            Retirar oferta
          </button>
        </p>
      )}
    </div>
  );
}

function flag(state: TransitionFormState): boolean {
  return Boolean(state.lostAccess || state.accessChanged || state.contextChanged);
}
