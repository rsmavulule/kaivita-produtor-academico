import type { Metadata } from "next";

import { loadSession } from "../../../lib/current-session";

export const metadata: Metadata = {
  title: "Início — Kaivita Produtor Académico",
};

export default async function InicioPage() {
  const session = await loadSession();
  if (session.kind !== "ready") return null;

  return (
    <main className="page">
      <p className="eyebrow">Área privada</p>
      <h1>Início</h1>
      <p className="lead">
        Entrou como <strong>{session.email}</strong>. A autorização de cada
        pedido continua a ser verificada pela API.
      </p>
      <p className="note">
        Actores, produtos e ofertas ficam para os incrementos seguintes.
      </p>
    </main>
  );
}
