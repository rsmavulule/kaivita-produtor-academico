import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor } from "../../../../../lib/actors";
import {
  CHANNEL_LABELS,
  PUBLIC_GAP_NOTICE,
  STATUS_LABELS,
  VISIBILITY_LABELS,
} from "../../../../../lib/contact-view";
import { loadContacts } from "../../../../../lib/contacts";
import { MissingActor, Unavailable } from "./states";

export const metadata: Metadata = {
  title: "Contactos comerciais — Kaivita Produtor Académico",
};

export default async function ContactsPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable href={`/actores/${actorId}/contactos`} />;
  if (actor.kind !== "ready") return <MissingActor />;

  const contacts = await loadContacts(actorId);
  if (contacts.kind === "invalid") redirect("/sessao/invalida");
  if (contacts.kind === "missing") return <MissingActor />;
  if (contacts.kind !== "ready") return <Unavailable href={`/actores/${actorId}/contactos`} />;

  const manage = actor.value.representation === "manage";

  return (
    <main className="page">
      <p className="eyebrow">Contactos comerciais</p>
      <h1>{actor.value.displayName}</h1>
      <p className="lead">Contactos deste actor. A visibilidade não é a consulta pública numa oferta.</p>
      <p className="note">{PUBLIC_GAP_NOTICE}</p>
      {contacts.value.length === 0 ? (
        <p className="note">Este actor ainda não tem contactos comerciais.</p>
      ) : (
        <ul className="actor-list">
          {contacts.value.map((contact) => (
            <li key={contact.id}>
              <a href={`/actores/${actorId}/contactos/${contact.id}`}>
                <span className="actor-name">{CHANNEL_LABELS[contact.channel]}</span>
                <span>{contact.value}</span>
                <span className="badge">{STATUS_LABELS[contact.status]}</span>
                <span className="badge">{VISIBILITY_LABELS[contact.visibility]}</span>
                <span>Revisão {contact.revision}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="links">
        {manage ? (
          <a className="primary" href={`/actores/${actorId}/contactos/novo`}>Registar contacto</a>
        ) : (
          <span className="note">O registo exige gestão. O papel de produtor não substitui essa representação.</span>
        )}
        <a className="secondary" href={`/actores/${actorId}`}>Voltar ao actor</a>
      </p>
    </main>
  );
}
