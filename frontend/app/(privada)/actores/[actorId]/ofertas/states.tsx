import { NOT_FOUND_MESSAGE } from "../../../../../lib/actors";
import { CONNECTION_MESSAGE } from "../../../../../lib/errors";
import { OFFER_NOT_FOUND } from "../../../../../lib/offers";

export function MissingActor() {
  return (
    <main className="page narrow">
      <h1>Actor não encontrado</h1>
      <p className="alert" role="alert">
        {NOT_FOUND_MESSAGE}
      </p>
      <p className="links">
        <a className="primary" href="/actores">
          Voltar aos actores
        </a>
      </p>
    </main>
  );
}

export function MissingOffer({ actorId }: { actorId: string }) {
  return (
    <main className="page narrow">
      <h1>Oferta não encontrada</h1>
      <p className="alert" role="alert">
        {OFFER_NOT_FOUND}
      </p>
      <p className="links">
        <a className="primary" href={`/actores/${actorId}/ofertas`}>
          Voltar às ofertas
        </a>
      </p>
    </main>
  );
}

export function Unavailable({ href }: { href: string }) {
  return (
    <main className="page narrow">
      <h1>Serviço indisponível</h1>
      <p className="alert" role="alert">
        {CONNECTION_MESSAGE}
      </p>
      <p className="links">
        <a className="primary" href={href}>
          Tentar novamente
        </a>
      </p>
    </main>
  );
}
