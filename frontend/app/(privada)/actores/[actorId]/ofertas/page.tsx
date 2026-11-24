import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor, loadActorRoles } from "../../../../../lib/actors";
import {
  AVAILABILITY_LABELS,
  OFFER_STATUS_LABELS,
  amountLine,
  canManageOffers,
  loadOffers,
} from "../../../../../lib/offers";
import { loadProducts } from "../../../../../lib/products";
import { MissingActor, Unavailable } from "./states";

export const metadata: Metadata = {
  title: "Ofertas — Kaivita Produtor Académico",
};

export default async function OffersPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable href={`/actores/${actorId}/ofertas`} />;
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable href={`/actores/${actorId}/ofertas`} />;

  const offers = await loadOffers(actorId);
  if (offers.kind === "invalid") redirect("/sessao/invalida");
  if (offers.kind === "missing") return <MissingActor />;
  if (offers.kind !== "ready") return <Unavailable href={`/actores/${actorId}/ofertas`} />;

  const products = await loadProducts(actorId);
  if (products.kind === "invalid") redirect("/sessao/invalida");
  if (products.kind === "missing") return <MissingActor />;
  if (products.kind !== "ready") return <Unavailable href={`/actores/${actorId}/ofertas`} />;

  const names = new Map(products.value.map((product) => [product.id, product.name]));
  const canWrite = canManageOffers(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );

  return (
    <main className="page">
      <p className="eyebrow">Ofertas</p>
      <h1>{actor.value.displayName}</h1>
      <p className="lead">
        Ofertas deste actor, em qualquer estado. Um produto arquivado continua nesta lista.
      </p>
      {offers.value.length === 0 ? (
        <p className="note">Este actor ainda não tem ofertas.</p>
      ) : (
        <ul className="actor-list">
          {offers.value.map((offer) => (
            <li key={offer.id}>
              <a href={`/actores/${actorId}/ofertas/${offer.id}`}>
                <span className="actor-name">{names.get(offer.productId) ?? "Produto não encontrado"}</span>
                <span>{amountLine("Preço", offer.price, offer.currency)}</span>
                <span>{amountLine("Quantidade", offer.quantity, offer.unit)}</span>
                <span>
                  {offer.availability === null
                    ? "Disponibilidade: por preencher."
                    : AVAILABILITY_LABELS[offer.availability]}
                </span>
                <span className="badge">{OFFER_STATUS_LABELS[offer.status]}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="links">
        {canWrite ? (
          <a className="primary" href={`/actores/${actorId}/ofertas/nova`}>
            Registar oferta
          </a>
        ) : (
          <span className="note">O registo exige gestão e o papel de produtor.</span>
        )}
        <a className="secondary" href={`/actores/${actorId}`}>
          Voltar ao actor
        </a>
      </p>
    </main>
  );
}
