import type { Metadata } from "next";

import { OfferCard } from "../../components/offer-public";
import { OfferSearchForm } from "../../components/offer-search";
import { PublicShell } from "../../components/public-shell";
import { listHomeOffers } from "../../lib/public-offers";
import { EMPTY_CATALOG } from "../../lib/public-offer-view";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export const metadata: Metadata = {
  title: "Kaivita Produtor Académico",
  description: "Descubra ofertas de produtores: preço, quantidade, disponibilidade e localização geral.",
};

export default async function HomePage() {
  const catalog = await listHomeOffers();

  return (
    <PublicShell>
      <main className="page">
        <p className="eyebrow">Licenciatura em Desenvolvimento de Software</p>
        <h1>Kaivita Produtor</h1>
        <p className="lead">
          Encontre produtos de produtores e consulte o preço, a quantidade, a
          disponibilidade e a localização geral.
        </p>
        <OfferSearchForm filters={{ offset: 0 }} home />
        <p className="links">
          <a href="/ofertas">Ver todas as ofertas</a>
        </p>
        <section aria-labelledby="ofertas-publicadas">
          <h2 id="ofertas-publicadas">Ofertas publicadas</h2>
          {catalog.kind === "ready" ? (
            catalog.offers.length === 0 ? (
              <p className="note">{EMPTY_CATALOG}</p>
            ) : (
              <ul className="offer-list">
                {catalog.offers.map((offer) => (
                  <li key={offer.id}>
                    <OfferCard offer={offer} filters={{ offset: 0 }} />
                  </li>
                ))}
              </ul>
            )
          ) : (
            <div>
              <p className="alert" role="alert">
                {catalog.message}
              </p>
              <p className="links">
                <a href="/">Tentar novamente</a>
              </p>
            </div>
          )}
        </section>
        <section aria-labelledby="para-produtores">
          <h2 id="para-produtores">Para produtores</h2>
          <p>
            Quem representa um produtor entra para registar produtos e publicar
            ofertas. Uma oferta publicada e elegível pode ser consultada por
            qualquer visitante.
          </p>
          <p className="links">
            <a className="primary" href="/login">
              Publicar uma oferta
            </a>
          </p>
        </section>
      </main>
    </PublicShell>
  );
}
