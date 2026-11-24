import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor, loadActorRoles } from "../../../../../../lib/actors";
import { canRegisterProducts } from "../../../../../../lib/products";
import { emptyProductState } from "../form-state";
import { MissingActor, Unavailable } from "../states";
import { CreateProductForm } from "./create-form";

export const metadata: Metadata = {
  title: "Novo produto — Kaivita Produtor Académico",
};

export default async function NewProductPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") {
    return <Unavailable href={`/actores/${actorId}/produtos/novo`} />;
  }
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable href={`/actores/${actorId}/produtos/novo`} />;

  const canWrite = canRegisterProducts(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );

  return (
    <main className="page">
      <p className="eyebrow">Novo produto</p>
      <h1>{actor.value.displayName}</h1>
      {canWrite ? (
        <CreateProductForm actorId={actor.value.id} initial={emptyProductState} />
      ) : (
        <p className="notice" role="status">
          O registo de produtos exige gestão e o papel de produtor.
        </p>
      )}
      <p className="links">
        <a className="secondary" href={`/actores/${actorId}/produtos`}>
          Voltar aos produtos
        </a>
      </p>
    </main>
  );
}
