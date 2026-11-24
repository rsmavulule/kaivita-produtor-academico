import type { Metadata } from "next";
import { redirect } from "next/navigation";

import {
  KIND_LABELS,
  NOT_FOUND_MESSAGE,
  REPRESENTATION_LABELS,
  ROLE_LABELS,
  loadActor,
  loadActorRoles,
} from "../../../../lib/actors";
import { CONNECTION_MESSAGE } from "../../../../lib/errors";
import { ProfileForm, RolesForm } from "./edit-forms";

export const metadata: Metadata = {
  title: "Actor — Kaivita Produtor Académico",
};

export default async function ActorPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable actorId={actorId} />;
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable actorId={actorId} />;

  const profile = actor.value;
  const manage = profile.representation === "manage";

  return (
    <main className="page">
      <p className="eyebrow">{REPRESENTATION_LABELS[profile.representation]}</p>
      <h1>{profile.displayName}</h1>
      <p className="lead">
        {KIND_LABELS[profile.kind]}.{" "}
        {profile.generalLocation ?? "Localização desconhecida"}.
      </p>
      <h2>Papéis comerciais</h2>
      {roles.value.length === 0 ? (
        <p className="note">Este actor não tem papéis comerciais.</p>
      ) : (
        <ul className="role-list">
          {roles.value.map((role) => (
            <li key={role.id}>{ROLE_LABELS[role.code]}</li>
          ))}
        </ul>
      )}
      <p className="links">
        <a className="secondary" href="/actores">
          Voltar aos actores
        </a>
      </p>
      {manage ? (
        <>
          <ProfileForm
            actorId={profile.id}
            displayName={profile.displayName}
            location={profile.generalLocation ?? ""}
          />
          <RolesForm actorId={profile.id} roles={roles.value.map((role) => role.code)} />
        </>
      ) : (
        <p className="notice" role="status">
          Esta conta pode consultar o actor. A edição exige gestão.
        </p>
      )}
    </main>
  );
}

function MissingActor() {
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

function Unavailable({ actorId }: { actorId: string }) {
  return (
    <main className="page narrow">
      <h1>Serviço indisponível</h1>
      <p className="alert" role="alert">
        {CONNECTION_MESSAGE}
      </p>
      <p className="links">
        <a className="primary" href={`/actores/${actorId}`}>
          Tentar novamente
        </a>
      </p>
    </main>
  );
}
