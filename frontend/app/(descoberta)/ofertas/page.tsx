import type { Metadata } from "next";

import { OfferCard } from "../../../components/offer-public";
import { OfferSearchForm } from "../../../components/offer-search";
import { PublicShell } from "../../../components/public-shell";
import { listPublicOffers } from "../../../lib/public-offers";
import {
  catalogIsLimited,
  EMPTY_CATALOG,
  EMPTY_SEARCH,
  hasSearch,
  INVALID_QUERY_MESSAGE,
  LIMITED_RESULTS,
  listingHref,
  nextOffset,
  previousOffset,
  readPublicQuery,
  resultRange,
  STALE_PAGE,
  type PublicFilters,
  type RawQuery,
} from "../../../lib/public-offer-view";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export const metadata: Metadata = {
  title: "Ofertas — Kaivita Produtor Académico",
};

export default async function OffersPage({
  searchParams,
}: {
  searchParams: Promise<RawQuery>;
}) {
  const raw = await searchParams;
  const read = readPublicQuery(raw);

  return (
    <PublicShell>
      <main className="page">
        <h1>Ofertas</h1>
        <p className="lead">
          Pesquise pelo nome ou pela descrição e filtre por categoria e
          localização.
        </p>
        {read.kind === "invalid" ? <InvalidSearch /> : <ReadySearch filters={read.filters} />}
      </main>
    </PublicShell>
  );
}

function InvalidSearch() {
  return (
    <>
      <p className="alert" role="alert">
        {INVALID_QUERY_MESSAGE}
      </p>
      <OfferSearchForm filters={{ offset: 0 }} />
    </>
  );
}

async function ReadySearch({ filters }: { filters: PublicFilters }) {
  const catalog = await listPublicOffers(filters);
  return (
    <>
      <OfferSearchForm filters={filters} />
      {catalog.kind === "ready" ? (
        <Results filters={filters} catalog={catalog} />
      ) : (
        <div>
          <p className="alert" role="alert">
            {catalog.message}
          </p>
          <p className="links">
            <a href={listingHref(filters)}>Tentar novamente</a>
          </p>
        </div>
      )}
    </>
  );
}

function Results({
  filters,
  catalog,
}: {
  filters: PublicFilters;
  catalog: {
    offers: Parameters<typeof OfferCard>[0]["offer"][];
    total: number;
  };
}) {
  const shown = catalog.offers.length;
  const previous = previousOffset(filters.offset);
  const next = nextOffset(filters.offset, shown, catalog.total);
  const stale = shown === 0 && catalog.total > 0;
  const empty = shown === 0 && catalog.total === 0;

  return (
    <>
      <p className="note">{resultRange(filters.offset, shown, catalog.total)}</p>
      {catalogIsLimited(catalog.total) ? <p className="notice">{LIMITED_RESULTS}</p> : null}
      {empty ? <p className="note">{hasSearch(filters) ? EMPTY_SEARCH : EMPTY_CATALOG}</p> : null}
      {stale ? (
        <p className="note">
          {STALE_PAGE}{" "}
          <a href={listingHref({ ...filters, offset: 0 })}>Voltar à primeira página</a>
        </p>
      ) : null}
      {shown > 0 ? (
        <ul className="offer-list">
          {catalog.offers.map((offer) => (
            <li key={offer.id}>
              <OfferCard offer={offer} filters={filters} />
            </li>
          ))}
        </ul>
      ) : null}
      <nav className="pager" aria-label="Páginas de resultados">
        {previous === null ? null : (
          <a href={listingHref({ ...filters, offset: previous })}>Anterior</a>
        )}
        {next === null ? null : (
          <a href={listingHref({ ...filters, offset: next })}>Seguinte</a>
        )}
      </nav>
    </>
  );
}
