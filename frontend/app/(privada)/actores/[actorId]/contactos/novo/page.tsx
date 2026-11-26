import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor } from "../../../../../../lib/actors";
import { emptyContactState } from "../form-state";
import { CreateContactForm } from "../forms";
import { MissingActor, Unavailable } from "../states";

export const metadata: Metadata = {
  title: "Novo contacto — Kaivita Produtor Académico",
};

export default async function NewContactPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable href={`/actores/${actorId}/contactos/novo`} />;
  if (actor.kind !== "ready") return <MissingActor />;
  if (actor.value.representation !== "manage") {
    return (
      <main className="page">
        <h1>Novo contacto</h1>
        <p className="note">O registo exige gestão. O papel de produtor não substitui essa representação.</p>
        <p className="links">
          <a className="secondary" href={`/actores/${actorId}/contactos`}>Voltar aos contactos</a>
        </p>
      </main>
    );
  }

  return (
    <main className="page">
      <p className="eyebrow">Novo contacto</p>
      <h1>{actor.value.displayName}</h1>
      <CreateContactForm actorId={actorId} initial={emptyContactState()} />
      <p className="links">
        <a className="secondary" href={`/actores/${actorId}/contactos`}>Voltar aos contactos</a>
      </p>
    </main>
  );
}
