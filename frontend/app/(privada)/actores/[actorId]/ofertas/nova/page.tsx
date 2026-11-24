import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { isActorId, loadActor, loadActorRoles } from "../../../../../../lib/actors";
import { canManageOffers } from "../../../../../../lib/offers";
import { loadProducts } from "../../../../../../lib/products";
import { emptyOfferState } from "../form-state";
import { MissingActor, Unavailable } from "../states";
import { CreateOfferForm } from "./create-form";

export const metadata: Metadata = {
  title: "Nova oferta — Kaivita Produtor Académico",
};

export default async function NewOfferPage({
  params,
  searchParams,
}: {
  params: Promise<{ actorId: string }>;
  searchParams: Promise<{ produto?: string | string[] }>;
}) {
  const { actorId } = await params;
  const query = await searchParams;
  const requested = Array.isArray(query.produto) ? "" : (query.produto ?? "");
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") {
    return <Unavailable href={`/actores/${actorId}/ofertas/nova`} />;
  }
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable href={`/actores/${actorId}/ofertas/nova`} />;

  const products = await loadProducts(actorId);
  if (products.kind === "invalid") redirect("/sessao/invalida");
  if (products.kind === "missing") return <MissingActor />;
  if (products.kind !== "ready") {
    return <Unavailable href={`/actores/${actorId}/ofertas/nova`} />;
  }

  const canWrite = canManageOffers(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );
  const active = products.value
    .filter((product) => product.status === "active")
    .map((product) => ({ id: product.id, name: product.name }));
  const selected = isActorId(requested) && active.some((product) => product.id === requested);
  const presetRejected = requested !== "" && !selected;

  return (
    <main className="page">
      <p className="eyebrow">Nova oferta</p>
      <h1>{actor.value.displayName}</h1>
      {canWrite ? (
        active.length === 0 ? (
          <p className="notice" role="status">
            Não há produtos activos. Uma oferta nova exige um produto activo deste actor.{" "}
            <a href={`/actores/${actorId}/produtos`}>Ir para os produtos</a>
          </p>
        ) : (
          <>
            {presetRejected ? (
              <p className="notice" role="status">
                O produto indicado não está activo neste actor.
              </p>
            ) : null}
            <CreateOfferForm
              actorId={actor.value.id}
              products={active}
              initial={{ ...emptyOfferState, productId: selected ? requested : "" }}
            />
          </>
        )
      ) : (
        <p className="notice" role="status">
          O registo de ofertas exige gestão e o papel de produtor.
        </p>
      )}
      <p className="links">
        <a className="secondary" href={`/actores/${actorId}/ofertas`}>
          Voltar às ofertas
        </a>
      </p>
    </main>
  );
}
