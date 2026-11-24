import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadActor, loadActorRoles } from "../../../../../../lib/actors";
import {
  canRegisterProducts,
  loadProduct,
  STATUS_LABELS,
} from "../../../../../../lib/products";
import { MissingActor, MissingProduct, Unavailable } from "../states";
import { ArchiveProduct, ProductEditor } from "./edit-forms";

export const metadata: Metadata = {
  title: "Produto — Kaivita Produtor Académico",
};

export default async function ProductPage({
  params,
}: {
  params: Promise<{ actorId: string; productId: string }>;
}) {
  const { actorId, productId } = await params;
  const actor = await loadActor(actorId);
  if (actor.kind === "invalid") redirect("/sessao/invalida");
  if (actor.kind === "missing") return <MissingActor />;
  if (actor.kind === "unavailable") {
    return <Unavailable href={`/actores/${actorId}/produtos/${productId}`} />;
  }
  if (actor.kind !== "ready") return <MissingActor />;

  const roles = await loadActorRoles(actorId);
  if (roles.kind === "invalid") redirect("/sessao/invalida");
  if (roles.kind === "missing") return <MissingActor />;
  if (roles.kind !== "ready") {
    return <Unavailable href={`/actores/${actorId}/produtos/${productId}`} />;
  }

  const product = await loadProduct(actorId, productId);
  if (product.kind === "invalid") redirect("/sessao/invalida");
  if (product.kind === "missing") {
    return product.scope === "product" ? <MissingProduct actorId={actorId} /> : <MissingActor />;
  }
  if (product.kind !== "ready") {
    return <Unavailable href={`/actores/${actorId}/produtos/${productId}`} />;
  }

  const sheet = product.value;
  const canWrite = canRegisterProducts(
    actor.value.representation,
    roles.value.map((role) => role.code),
  );

  return (
    <main className="page">
      <p className="eyebrow">{STATUS_LABELS[sheet.status]}</p>
      <h1>{sheet.name}</h1>
      <p className="lead">{sheet.description}</p>
      <p>
        Categoria: {sheet.category}. Referência da imagem:{" "}
        {sheet.imageRef ?? "sem referência"}.
      </p>
      <p className="links">
        {canWrite && sheet.status === "active" ? (
          <a
            className="primary"
            href={`/actores/${actor.value.id}/ofertas/nova?produto=${sheet.id}`}
          >
            Criar oferta
          </a>
        ) : null}
        <a className="secondary" href={`/actores/${actorId}/produtos`}>
          Voltar aos produtos
        </a>
        <a className="secondary" href={`/actores/${actorId}`}>
          Voltar ao actor
        </a>
      </p>
      {canWrite ? (
        <>
          <ProductEditor
            actorId={actor.value.id}
            productId={sheet.id}
            name={sheet.name}
            description={sheet.description}
            category={sheet.category}
            imageRef={sheet.imageRef ?? ""}
          />
          {sheet.status === "active" ? (
            <ArchiveProduct actorId={actor.value.id} productId={sheet.id} />
          ) : (
            <p className="notice" role="status">
              Este produto está arquivado. A ficha pode ser corrigida e o estado mantém-se.
            </p>
          )}
        </>
      ) : (
        <p className="notice" role="status">
          Esta conta pode consultar o produto. Alterar ou arquivar exige gestão e o papel de produtor.
        </p>
      )}
    </main>
  );
}
