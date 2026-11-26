import { CONNECTION_MESSAGE } from "../../../../../lib/errors";
import { AUTHORIZATION_NOT_FOUND, CONTACT_NOT_FOUND } from "../../../../../lib/contact-view";
import { NOT_FOUND_MESSAGE } from "../../../../../lib/actors";

export function MissingActor() {
  return (
    <main className="page narrow">
      <h1>Actor não encontrado</h1>
      <p className="alert" role="alert">{NOT_FOUND_MESSAGE}</p>
      <p className="links">
        <a className="primary" href="/actores">Voltar aos actores</a>
      </p>
    </main>
  );
}

export function MissingContact({ actorId }: { actorId: string }) {
  return (
    <main className="page narrow">
      <h1>Contacto não encontrado</h1>
      <p className="alert" role="alert">{CONTACT_NOT_FOUND}</p>
      <p className="links">
        <a className="primary" href={`/actores/${actorId}/contactos`}>Voltar aos contactos</a>
      </p>
    </main>
  );
}

export function MissingAuthorization({ actorId, contactId }: { actorId: string; contactId: string }) {
  return (
    <main className="page narrow">
      <h1>Autorização não encontrada</h1>
      <p className="alert" role="alert">{AUTHORIZATION_NOT_FOUND}</p>
      <p className="links">
        <a className="primary" href={`/actores/${actorId}/contactos/${contactId}`}>Voltar ao contacto</a>
      </p>
    </main>
  );
}

export function Unavailable({ href }: { href: string }) {
  return (
    <main className="page narrow">
      <h1>Serviço indisponível</h1>
      <p className="alert" role="alert">{CONNECTION_MESSAGE}</p>
      <p className="links">
        <a className="primary" href={href}>Tentar novamente</a>
      </p>
    </main>
  );
}
