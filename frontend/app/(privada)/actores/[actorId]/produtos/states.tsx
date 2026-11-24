import { NOT_FOUND_MESSAGE } from "../../../../../lib/actors";
import { CONNECTION_MESSAGE } from "../../../../../lib/errors";
import { PRODUCT_NOT_FOUND } from "../../../../../lib/products";

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

export function MissingProduct({ actorId }: { actorId: string }) {
  return (
    <main className="page narrow">
      <h1>Produto não encontrado</h1>
      <p className="alert" role="alert">
        {PRODUCT_NOT_FOUND}
      </p>
      <p className="links">
        <a className="primary" href={`/actores/${actorId}/produtos`}>
          Voltar aos produtos
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
