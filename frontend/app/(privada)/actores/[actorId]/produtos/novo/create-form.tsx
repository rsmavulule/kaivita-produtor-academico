"use client";

import { useActionState, useEffect } from "react";

import { PublicFieldNotice } from "../../../../../../components/public-disclosure";
import { createProductAction } from "../actions";
import type { ProductFormState } from "../form-state";

export function CreateProductForm({
  actorId,
  initial,
}: {
  actorId: string;
  initial: ProductFormState;
}) {
  const [state, action, pending] = useActionState(
    createProductAction.bind(null, actorId),
    initial,
  );
  useReloadAfterChange(state.lostAccess || state.accessChanged);
  if (state.lostAccess || state.accessChanged) return <Recheck />;

  const formKey = [state.name, state.description, state.category, state.imageRef, state.formError ?? ""].join("|");
  return (
    <form action={action} className="form" aria-busy={pending} key={formKey}>
      <h2>Novo produto</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <ProductFields state={state} idPrefix="create" />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A registar…" : "Registar produto"}
      </button>
    </form>
  );
}

export function ProductFields({
  state,
  idPrefix,
}: {
  state: ProductFormState;
  idPrefix: string;
}) {
  return (
    <>
      <PublicFieldNotice id="product-public-notice" />
      <Field
        id={`${idPrefix}-name`}
        name="name"
        label="Nome"
        defaultValue={state.name}
        error={state.nameError}
        hintId="product-public-notice"
        required
      />
      <Field
        id={`${idPrefix}-description`}
        name="description"
        label="Descrição"
        defaultValue={state.description}
        error={state.descriptionError}
        hintId="product-public-notice"
        required
        multiline
      />
      <Field
        id={`${idPrefix}-category`}
        name="category"
        label="Categoria"
        defaultValue={state.category}
        error={state.categoryError}
        hintId="product-public-notice"
        required
      />
      <Field
        id={`${idPrefix}-image`}
        name="image_ref"
        label="Referência da imagem"
        defaultValue={state.imageRef}
        error={state.imageError}
      />
      <p className="note">A referência é texto opcional. Deixe-a vazia para a retirar.</p>
    </>
  );
}

function Recheck() {
  return <p className="note">A confirmar o acesso.</p>;
}

function Field(input: {
  id: string;
  name: string;
  label: string;
  defaultValue: string;
  error?: string;
  required?: boolean;
  multiline?: boolean;
  hintId?: string;
}) {
  const errorId = `${input.id}-error`;
  const described = [input.hintId, input.error ? errorId : undefined].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field">
      <label htmlFor={input.id}>{input.label}</label>
      {input.multiline ? (
        <textarea
          id={input.id}
          name={input.name}
          defaultValue={input.defaultValue}
          required={input.required}
          aria-invalid={input.error ? true : undefined}
          aria-describedby={described}
        />
      ) : (
        <input
          id={input.id}
          name={input.name}
          type="text"
          defaultValue={input.defaultValue}
          required={input.required}
          aria-invalid={input.error ? true : undefined}
          aria-describedby={described}
        />
      )}
      {input.error ? (
        <p id={errorId} className="field-error">
          {input.error}
        </p>
      ) : null}
    </div>
  );
}

export function useReloadAfterChange(reload: boolean | undefined) {
  useEffect(() => {
    if (!reload) return;
    const path = window.location.pathname;
    if (path.startsWith("/actores/")) window.location.replace(path);
  }, [reload]);
}
