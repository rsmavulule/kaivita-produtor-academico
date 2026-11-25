import type { Metadata } from "next";

import { OfferDetail } from "../../../../components/offer-public";
import { PublicShell } from "../../../../components/public-shell";
import { readPublicOffer } from "../../../../lib/public-offers";
import {
  INVALID_OFFER_ADDRESS,
  OFFER_NOT_FOUND,
  returnHref,
  type RawQuery,
} from "../../../../lib/public-offer-view";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export const metadata: Metadata = {
  title: "Oferta — Kaivita Produtor Académico",
};

export default async function PublicOfferPage({
  params,
  searchParams,
}: {
  params: Promise<{ offerId: string }>;
  searchParams: Promise<RawQuery>;
}) {
  const { offerId } = await params;
  const raw = await searchParams;
  const back = returnHref(raw);
  const offer = await readPublicOffer(offerId);
  const backLabel = back === "/ofertas" ? "Voltar às ofertas" : "Voltar aos resultados";

  return (
    <PublicShell>
      <main className="page">
        <p className="links">
          <a href={back}>{backLabel}</a>
        </p>
        {offer.kind === "ready" ? <OfferDetail offer={offer.offer} /> : null}
        {offer.kind === "invalid" ? (
          <Missing title="Endereço inválido" message={INVALID_OFFER_ADDRESS} />
        ) : null}
        {offer.kind === "missing" ? (
          <Missing title="Oferta não encontrada" message={OFFER_NOT_FOUND} />
        ) : null}
        {offer.kind === "unavailable" || offer.kind === "rejected" ? (
          <Failure message={offer.message} retryHref={`/ofertas/${offerId}`} />
        ) : null}
      </main>
    </PublicShell>
  );
}

function Missing({ title, message }: { title: string; message: string }) {
  return (
    <>
      <h1>{title}</h1>
      <p className="alert" role="alert">
        {message}
      </p>
    </>
  );
}

function Failure({ message, retryHref }: { message: string; retryHref: string }) {
  return (
    <div>
      <h1>Oferta</h1>
      <p className="alert" role="alert">
        {message}
      </p>
      <p className="links">
        <a href={retryHref}>Tentar novamente</a>
      </p>
    </div>
  );
}
