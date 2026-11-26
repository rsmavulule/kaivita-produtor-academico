"use client";

import { useActionState, useState } from "react";

import { archiveProductAction, updateProductAction } from "../actions";
import type { ArchiveFormState, ProductFormState } from "../form-state";
import { ProductFields, useReloadAfterChange } from "../novo/create-form";

export function ProductEditor(input: {
  actorId: string;
  productId: string;
  name: string;
  description: string;
  category: string;
  imageRef: string;
  imageUseConfirmed: boolean;
}) {
  const initial: ProductFormState = {
    name: input.name,
    description: input.description,
    category: input.category,
    imageRef: input.imageRef,
    imageUseConfirmed: input.imageUseConfirmed,
  };
  const [state, action, pending] = useActionState(
    updateProductAction.bind(null, input.actorId, input.productId),
    initial,
  );
  const formKey = [state.name, state.description, state.category, state.imageRef, state.imageUseConfirmed, state.formError ?? ""].join("|");
  useReloadAfterChange(state.lostAccess || state.accessChanged);
  if (state.lostAccess || state.accessChanged) return <p className="note">A confirmar o acesso.</p>;

  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Ficha</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <ProductFields state={state} idPrefix="edit" />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A guardar…" : "Guardar produto"}
      </button>
    </form>
  );
}

export function ArchiveProduct(input: { actorId: string; productId: string }) {
  const [confirming, setConfirming] = useState(false);
  const [state, action, pending] = useActionState(
    archiveProductAction.bind(null, input.actorId, input.productId),
    {} as ArchiveFormState,
  );
  useReloadAfterChange(state.lostAccess || state.accessChanged);
  if (state.lostAccess || state.accessChanged) return <p className="note">A confirmar o acesso.</p>;
  if (!confirming) {
    return (
      <p className="links">
        <button className="secondary" type="button" onClick={() => setConfirming(true)}>
          Arquivar produto
        </button>
      </p>
    );
  }
  return (
    <form action={action} className="form" aria-busy={pending}>
      <p>O arquivo conserva o produto. O estado não volta a activo.</p>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <p className="links">
        <button className="primary" type="submit" disabled={pending}>
          {pending ? "A arquivar…" : "Confirmar arquivo"}
        </button>
        <button className="secondary" type="button" onClick={() => setConfirming(false)}>
          Cancelar
        </button>
      </p>
    </form>
  );
}
