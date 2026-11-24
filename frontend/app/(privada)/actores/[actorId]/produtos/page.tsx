import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor, loadActorRoles } from "../../../../../lib/actors";
import { canRegisterProducts, loadProducts, STATUS_LABELS } from "../../../../../lib/products";
import { MissingActor, Unavailable } from "./states";

export const metadata: Metadata = {
  title: "Produtos — Kaivita Produtor Académico",
};

export default async function ProductsPage({
  params,
}: {
  params: Promise<{ actorId: string }>;
}) {
  const { actorId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") return <Unavailable href={`/actores/${actorId}/produtos`} />;
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") return <Unavailable href={`/actores/${actorId}/produtos`} />;

  const products = await loadProducts(actorId);
  if (products.kind === "invalid") redirect("/sessao/invalida");
  if (products.kind === "missing") return <MissingActor />;
  if (products.kind !== "ready") return <Unavailable href={`/actores/${actorId}/produtos`} />;

  const canWrite = canRegisterProducts(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );

  return (
    <main className="page">
      <p className="eyebrow">Produtos</p>
      <h1>{actor.value.displayName}</h1>
      <p className="lead">Catálogo deste actor, incluindo produtos arquivados.</p>
      {products.value.length === 0 ? (
        <p className="note">Este actor ainda não tem produtos.</p>
      ) : (
        <ul className="actor-list">
          {products.value.map((product) => (
            <li key={product.id}>
              <a href={`/actores/${actorId}/produtos/${product.id}`}>
                <span className="actor-name">{product.name}</span>
                <span>{product.category}</span>
                <span className="badge">{STATUS_LABELS[product.status]}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="links">
        {canWrite ? (
          <a className="primary" href={`/actores/${actorId}/produtos/novo`}>
            Registar produto
          </a>
        ) : (
          <span className="note">O registo exige gestão e o papel de produtor.</span>
        )}
        <a className="secondary" href={`/actores/${actorId}`}>
          Voltar ao actor
        </a>
      </p>
    </main>
  );
}
