import {
  AVAILABILITY_LABELS,
  DELIVERY_MISSING,
  LOCATION_MISSING,
  offerHref,
  PRODUCER_KIND_LABELS,
  shownText,
  type PublicFilters,
  type PublicOffer,
} from "../lib/public-offer-view";

export function OfferCard({ offer, filters }: { offer: PublicOffer; filters: PublicFilters }) {
  return (
    <article className="offer-card">
      <h2>{offer.productName}</h2>
      <p>Categoria: {offer.productCategory}</p>
      <p>Preço: {offer.price} {offer.currency}</p>
      <p>Quantidade: {offer.quantity} {offer.unit}</p>
      <p>Disponibilidade: {AVAILABILITY_LABELS[offer.availability]}</p>
      <p>Produtor: {offer.producerName}</p>
      <p>{shownText(offer.producerLocation, LOCATION_MISSING)}</p>
      <p className="links">
        <a href={offerHref(offer.id, filters)}>Ver oferta de {offer.productName}</a>
      </p>
    </article>
  );
}

export function OfferDetail({ offer }: { offer: PublicOffer }) {
  return (
    <>
      <p className="eyebrow">{offer.productCategory}</p>
      <h1>{offer.productName}</h1>
      <p className="lead">{offer.productDescription}</p>
      <dl className="facts">
        <div>
          <dt>Preço</dt>
          <dd>{offer.price} {offer.currency}</dd>
        </div>
        <div>
          <dt>Quantidade</dt>
          <dd>{offer.quantity} {offer.unit}</dd>
        </div>
        <div>
          <dt>Disponibilidade</dt>
          <dd>{AVAILABILITY_LABELS[offer.availability]}</dd>
        </div>
        <div>
          <dt>Condições de entrega</dt>
          <dd>{shownText(offer.deliveryTerms, DELIVERY_MISSING)}</dd>
        </div>
        <div>
          <dt>Produtor</dt>
          <dd>{offer.producerName}</dd>
        </div>
        <div>
          <dt>Tipo</dt>
          <dd>{PRODUCER_KIND_LABELS[offer.producerKind]}</dd>
        </div>
        <div>
          <dt>Localização geral</dt>
          <dd>{shownText(offer.producerLocation, LOCATION_MISSING)}</dd>
        </div>
      </dl>
    </>
  );
}
