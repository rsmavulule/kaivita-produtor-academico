"use client";

import { useActionState, useEffect } from "react";

import { createOfferAction } from "../actions";
import type { OfferFormState } from "../form-state";

export function CreateOfferForm({
  actorId,
  products,
  initial,
}: {
  actorId: string;
  products: { id: string; name: string }[];
  initial: OfferFormState;
}) {
  const [state, action, pending] = useActionState(createOfferAction.bind(null, actorId), initial);
  useReloadAfterChange(state.lostAccess || state.accessChanged || state.contextChanged);
  if (state.lostAccess || state.accessChanged || state.contextChanged) {
    return <p className="note">A confirmar o acesso.</p>;
  }

  const formKey = [
    state.productId,
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
      <h2>Novo rascunho</h2>
      {state.formError ? (
        <p className="alert" role="alert">
          {state.formError}
        </p>
      ) : null}
      <OfferFields state={state} idPrefix="create" products={products} examples incomplete />
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "A registar…" : "Registar oferta"}
      </button>
    </form>
  );
}

export function OfferFields({
  state,
  idPrefix,
  products,
  examples = false,
  incomplete = false,
}: {
  state: OfferFormState;
  idPrefix: string;
  products?: { id: string; name: string }[];
  examples?: boolean;
  incomplete?: boolean;
}) {
  return (
    <>
      {products ? (
        <div className="field">
          <label htmlFor={`${idPrefix}-product`}>Produto</label>
          <select
            id={`${idPrefix}-product`}
            name="product_id"
            defaultValue={state.productId}
            required
            aria-invalid={state.productError ? true : undefined}
            aria-describedby={state.productError ? `${idPrefix}-product-error` : undefined}
          >
            <option value="">Escolher produto</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
          {state.productError ? (
            <p id={`${idPrefix}-product-error`} className="field-error">
              {state.productError}
            </p>
          ) : null}
        </div>
      ) : null}
      <TextField
        id={`${idPrefix}-price`}
        name="price"
        label="Preço"
        defaultValue={state.price}
        error={state.priceError}
      />
      <TextField
        id={`${idPrefix}-currency`}
        name="currency"
        label="Moeda"
        defaultValue={state.currency}
        error={state.currencyError}
      />
      <TextField
        id={`${idPrefix}-quantity`}
        name="quantity"
        label="Quantidade"
        defaultValue={state.quantity}
        error={state.quantityError}
      />
      <TextField
        id={`${idPrefix}-unit`}
        name="unit"
        label="Unidade"
        defaultValue={state.unit}
        error={state.unitError}
      />
      <div className="field">
        <label htmlFor={`${idPrefix}-availability`}>Disponibilidade</label>
        <select
          id={`${idPrefix}-availability`}
          name="availability"
          defaultValue={state.availability}
          aria-invalid={state.availabilityError ? true : undefined}
          aria-describedby={state.availabilityError ? `${idPrefix}-availability-error` : undefined}
        >
          <option value="">Por preencher</option>
          <option value="available">Disponível</option>
          <option value="unavailable">Indisponível</option>
        </select>
        {state.availabilityError ? (
          <p id={`${idPrefix}-availability-error`} className="field-error">
            {state.availabilityError}
          </p>
        ) : null}
      </div>
      <TextField
        id={`${idPrefix}-delivery`}
        name="delivery_terms"
        label="Condições de entrega"
        defaultValue={state.deliveryTerms}
        error={state.deliveryError}
        multiline
      />
      <p className="note">
        {incomplete ? "O rascunho pode ficar incompleto. " : null}
        Preço e quantidade são texto decimal
        {examples ? ", por exemplo 150.00 e 2.50" : ""}. Zero é um valor. O campo vazio fica por
        preencher. Uma vírgula decimal isolada é aceite.
      </p>
    </>
  );
}

function TextField(input: {
  id: string;
  name: string;
  label: string;
  defaultValue: string;
  error?: string;
  multiline?: boolean;
}) {
  const errorId = `${input.id}-error`;
  const described = input.error ? errorId : undefined;
  return (
    <div className="field">
      <label htmlFor={input.id}>{input.label}</label>
      {input.multiline ? (
        <textarea
          id={input.id}
          name={input.name}
          defaultValue={input.defaultValue}
          aria-invalid={input.error ? true : undefined}
          aria-describedby={described}
        />
      ) : (
        <input
          id={input.id}
          name={input.name}
          type="text"
          inputMode={input.name === "price" || input.name === "quantity" ? "decimal" : undefined}
          autoComplete="off"
          defaultValue={input.defaultValue}
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
