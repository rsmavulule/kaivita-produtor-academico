import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor, loadActorRoles } from "../../../../../../lib/actors";
import {
  AVAILABILITY_LABELS,
  OFFER_STATUS_LABELS,
  amountLine,
  canManageOffers,
  loadOffer,
} from "../../../../../../lib/offers";
import { STATUS_LABELS, loadProduct } from "../../../../../../lib/products";
import { MissingActor, MissingOffer, Unavailable } from "../states";
import { OfferEditor, OfferTransitions } from "./edit-forms";

export const metadata: Metadata = {
  title: "Oferta — Kaivita Produtor Académico",
};

export default async function OfferPage({
  params,
}: {
  params: Promise<{ actorId: string; offerId: string }>;
}) {
  const { actorId, offerId } = await params;
  const href = `/actores/${actorId}/ofertas/${offerId}`;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable href={href} />;
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable href={href} />;

  const offer = await loadOffer(actorId, offerId);
  if (offer.kind === "invalid") redirect("/sessao/invalida");
  if (offer.kind === "missing") {
    return offer.scope === "offer" ? <MissingOffer actorId={actorId} /> : <MissingActor />;
  }
  if (offer.kind !== "ready") return <Unavailable href={href} />;

  const product = await loadProduct(actorId, offer.value.productId);
  if (product.kind === "invalid") redirect("/sessao/invalida");
  if (product.kind === "unavailable") return <Unavailable href={href} />;

  const sheet = offer.value;
  const productName = product.kind === "ready" ? product.value.name : "Produto não encontrado";
  const productStatus = product.kind === "ready" ? product.value.status : null;
  const archived = productStatus === "archived";
  const canWrite = canManageOffers(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );
  const editable = canWrite && sheet.status !== "withdrawn";

  return (
    <main className="page">
      <p className="eyebrow">{OFFER_STATUS_LABELS[sheet.status]}</p>
      <h1>{productName}</h1>
      <p className="lead">
        Produto {productStatus ? STATUS_LABELS[productStatus].toLowerCase() : "indisponível"}.{" "}
        {amountLine("Preço", sheet.price, sheet.currency)}{" "}
        {amountLine("Quantidade", sheet.quantity, sheet.unit)}
      </p>
      <p>
        {sheet.availability === null
          ? "Disponibilidade: por preencher."
          : `Disponibilidade: ${AVAILABILITY_LABELS[sheet.availability]}.`}{" "}
        Condições de entrega: {sheet.deliveryTerms ?? "por preencher"}.
      </p>
      {archived ? (
        <p className="notice" role="status">
          O produto está arquivado. A oferta mantém o estado actual. Não há oferta nova, publicação
          nem republicação. A consulta, a correcção permitida, a suspensão e a retirada continuam
          disponíveis. A pesquisa pública futura exclui esta oferta, mesmo publicada.
        </p>
      ) : null}
      <p className="links">
        {product.kind === "ready" ? (
          <a className="secondary" href={`/actores/${actorId}/produtos/${sheet.productId}`}>
            Abrir o produto
          </a>
        ) : null}
        <a className="secondary" href={`/actores/${actorId}/ofertas`}>
          Voltar às ofertas
        </a>
        <a className="secondary" href={`/actores/${actorId}`}>
          Voltar ao actor
        </a>
      </p>
      {editable ? (
        <OfferEditor
          actorId={actor.value.id}
          offerId={sheet.id}
          price={sheet.price ?? ""}
          currency={sheet.currency ?? ""}
          quantity={sheet.quantity ?? ""}
          unit={sheet.unit ?? ""}
          availability={sheet.availability ?? ""}
          deliveryTerms={sheet.deliveryTerms ?? ""}
          published={sheet.status === "published"}
          incomplete={sheet.status === "draft"}
        />
      ) : null}
      {canWrite && sheet.status !== "withdrawn" ? (
        <OfferTransitions
          actorId={actor.value.id}
          offerId={sheet.id}
          status={sheet.status}
        />
      ) : (
        <p className="notice" role="status">
          {sheet.status === "withdrawn"
            ? "A retirada é definitiva. A oferta fica só em consulta."
            : "Esta conta pode consultar a oferta. Alterar o ciclo exige gestão e o papel de produtor."}
        </p>
      )}
    </main>
  );
}
