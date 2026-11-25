import {
  type PublicFilters,
} from "../lib/public-offer-view";

export function OfferSearchForm({
  filters,
  home = false,
}: {
  filters: PublicFilters;
  home?: boolean;
}) {
  return (
    <form className="form" action="/ofertas" method="get">
      <div className="field">
        <label htmlFor={home ? "home-q" : "q"}>
          {home ? "Pesquisar produtos" : "Nome ou descrição do produto"}
        </label>
        <input
          id={home ? "home-q" : "q"}
          name="q"
          type="text"
          maxLength={100}
          defaultValue={filters.q ?? ""}
        />
      </div>
      {home ? null : (
        <>
          <div className="field">
            <label htmlFor="category">Categoria</label>
            <input
              id="category"
              name="category"
              type="text"
              maxLength={100}
              defaultValue={filters.category ?? ""}
            />
          </div>
          <div className="field">
            <label htmlFor="location">Localização</label>
            <input
              id="location"
              name="location"
              type="text"
              maxLength={100}
              defaultValue={filters.location ?? ""}
            />
          </div>
        </>
      )}
      <p className="links">
        <button className="primary" type="submit">
          {home ? "Pesquisar ofertas" : "Pesquisar"}
        </button>
        {home ? null : (
          <a className="secondary" href="/ofertas">
            Limpar filtros
          </a>
        )}
      </p>
    </form>
  );
}
