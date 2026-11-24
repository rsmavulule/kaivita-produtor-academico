import type { Metadata } from "next";
import { redirect } from "next/navigation";

import {
  KIND_LABELS,
  REPRESENTATION_LABELS,
  loadActors,
} from "../../../lib/actors";
import { CONNECTION_MESSAGE } from "../../../lib/errors";
import { CreateActorForm } from "./create-form";

export const metadata: Metadata = {
  title: "Actores — Kaivita Produtor Académico",
};

export default async function ActorsPage() {
  const loaded = await loadActors();
  if (loaded.kind === "invalid") redirect("/sessao/invalida");
  if (loaded.kind === "unavailable") {
    return (
      <main className="page">
        <h1>Actores</h1>
        <p className="alert" role="alert">
          {CONNECTION_MESSAGE}
        </p>
        <p className="links">
          <a className="primary" href="/actores">
            Tentar novamente
          </a>
        </p>
      </main>
    );
  }
  if (loaded.kind !== "ready") {
    return (
      <main className="page">
        <h1>Actores</h1>
        <p className="alert" role="alert">
          {loaded.kind === "rejected" ? loaded.message : CONNECTION_MESSAGE}
        </p>
      </main>
    );
  }

  return (
    <main className="page">
      <p className="eyebrow">Representação</p>
      <h1>Actores</h1>
      <p className="lead">
        A lista mostra só os actores desta conta. O nível vem da associação
        activa e não pode ser escolhido aqui.
      </p>
      {loaded.value.length === 0 ? (
        <p className="notice" role="status">
          Ainda não representa nenhum actor.
        </p>
      ) : (
        <ul className="actor-list">
          {loaded.value.map((actor) => (
            <li key={actor.id}>
              <a href={`/actores/${actor.id}`}>
                <span className="actor-name">{actor.displayName}</span>
                <span>{KIND_LABELS[actor.kind]}</span>
                <span>{actor.generalLocation ?? "Localização desconhecida"}</span>
                <span className="badge">{REPRESENTATION_LABELS[actor.representation]}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <CreateActorForm />
    </main>
  );
}
