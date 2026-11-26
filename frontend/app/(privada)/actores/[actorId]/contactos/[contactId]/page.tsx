import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor } from "../../../../../../lib/actors";
import {
  AUTHORIZATION_LABELS,
  CHANNEL_LABELS,
  PUBLIC_GAP_NOTICE,
  PURPOSE_LABEL,
  REASON_LABELS,
  REGISTER_NOTICE,
  STATUS_LABELS,
  VISIBILITY_LABELS,
  currentAuthorization,
  formatWhen,
} from "../../../../../../lib/contact-view";
import { loadAuthorizations, loadContact } from "../../../../../../lib/contacts";
import {
  DeactivateContactForm,
  EditContactForm,
  GrantDisclosureForm,
  RevokeDisclosureForm,
} from "../forms";
import { MissingActor, MissingContact, Unavailable } from "../states";

export const metadata: Metadata = {
  title: "Contacto comercial — Kaivita Produtor Académico",
};

const RESULTS: Record<string, string> = {
  concedida: "A divulgação foi autorizada.",
  repetida: "Esta divulgação já estava autorizada. Não foi criada outra autorização.",
  revogada: "A revogação foi registada. Uma consulta pública nova deixa de mostrar o contacto se não existir outra autorização vigente.",
  alterado: "O contacto foi alterado. Se existia uma autorização vigente, foi revogada.",
  equivalente: "O contacto foi guardado. A alteração equivalente preservou a autorização existente.",
  inactivo: "O contacto ficou inactivo. Se existia uma autorização vigente, foi revogada.",
};

export default async function ContactPage({
  params,
  searchParams,
}: {
  params: Promise<{ actorId: string; contactId: string }>;
  searchParams: Promise<{ resultado?: string }>;
}) {
  const { actorId, contactId } = await params;
  const query = await searchParams;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") {
    return <Unavailable href={`/actores/${actorId}/contactos/${contactId}`} />;
  }
  if (actor.kind !== "ready") return <MissingActor />;

  const contact = await loadContact(actorId, contactId);
  if (contact.kind === "invalid") redirect("/sessao/invalida");
  if (contact.kind === "missing") {
    return contact.scope === "actor" ? <MissingActor /> : <MissingContact actorId={actorId} />;
  }
  if (contact.kind !== "ready") {
    return <Unavailable href={`/actores/${actorId}/contactos/${contactId}`} />;
  }

  const history = await loadAuthorizations(actorId, contactId);
  if (history.kind === "invalid") redirect("/sessao/invalida");
  if (history.kind === "missing") {
    return history.scope === "contact" ? <MissingContact actorId={actorId} /> : <MissingActor />;
  }
  if (history.kind !== "ready") {
    return <Unavailable href={`/actores/${actorId}/contactos/${contactId}`} />;
  }

  const current = contact.value;
  const manage = actor.value.representation === "manage";
  const active = current.status === "active";
  const granted = currentAuthorization(history.value);
  const result = typeof query.resultado === "string" ? RESULTS[query.resultado] : undefined;

  return (
    <main className="page">
      <p className="eyebrow">Contacto comercial</p>
      <h1>{CHANNEL_LABELS[current.channel]}</h1>
      <p className="lead contact-value">{current.value}</p>
      {result ? <p className="notice" role="status">{result}</p> : null}
      <dl className="facts">
        <div>
          <dt>Estado</dt>
          <dd>{STATUS_LABELS[current.status]}</dd>
        </div>
        <div>
          <dt>Visibilidade</dt>
          <dd>{VISIBILITY_LABELS[current.visibility]}</dd>
        </div>
        <div>
          <dt>Autorização vigente</dt>
          <dd>{granted ? "Divulgação autorizada" : "Sem autorização vigente"}</dd>
        </div>
        <div>
          <dt>Revisão</dt>
          <dd>{current.revision}</dd>
        </div>
      </dl>
      <p className="note">{PUBLIC_GAP_NOTICE}</p>
      <p className="note">{REGISTER_NOTICE}</p>
      {manage && active ? (
        <>
          <EditContactForm
            actorId={actorId}
            contactId={contactId}
            revision={current.revision}
            initial={{ channel: current.channel, value: current.value }}
          />
          <GrantDisclosureForm
            actorId={actorId}
            contactId={contactId}
            actorName={actor.value.displayName}
            initial={{ revision: current.revision, channel: current.channel, value: current.value }}
          />
          {granted ? (
            <RevokeDisclosureForm
              actorId={actorId}
              contactId={contactId}
              authorizationId={granted.id}
            />
          ) : null}
          <DeactivateContactForm actorId={actorId} contactId={contactId} />
        </>
      ) : (
        <p className="note">
          {active
            ? "A alteração, a autorização e a revogação exigem gestão."
            : "O contacto inactivo não pode ser alterado, divulgado ou reactivado."}
        </p>
      )}
      <h2>Histórico de autorizações</h2>
      {history.value.length === 0 ? (
        <p className="note">Este contacto ainda não teve autorizações de divulgação.</p>
      ) : (
        <ul className="actor-list">
          {history.value.map((item) => (
            <li key={item.id}>
              <p>{AUTHORIZATION_LABELS[item.status]}</p>
              <p>Revisão autorizada: {item.contactRevision}</p>
              <p>Canal: {CHANNEL_LABELS[item.channel]}</p>
              <p>Finalidade: {PURPOSE_LABEL}</p>
              <p>Aviso: {item.noticeVersion}</p>
              <p>Concessão: {formatWhen(item.grantedAt)}</p>
              {item.revokedAt ? <p>Revogação: {formatWhen(item.revokedAt)}</p> : null}
              {item.reason ? <p>Motivo: {REASON_LABELS[item.reason]}</p> : null}
            </li>
          ))}
        </ul>
      )}
      <p className="note">O histórico não recupera o valor antigo do contacto.</p>
      <p className="links">
        <a className="secondary" href={`/actores/${actorId}/contactos`}>Voltar aos contactos</a>
      </p>
    </main>
  );
}
