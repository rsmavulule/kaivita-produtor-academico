import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { loadSession } from "../../lib/current-session";
import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Entrar — Kaivita Produtor Académico",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ motivo?: string }>;
}) {
  const session = await loadSession();
  if (session.kind === "ready") redirect("/inicio");

  const params = await searchParams;
  const notice = noticeFor(params.motivo);

  return (
    <main className="page narrow">
      <p className="eyebrow">Licenciatura em Desenvolvimento de Software</p>
      <h1>Entrar</h1>
      <p className="lead">
        A conta é criada fora desta interface. A sessão fica num cookie que o
        browser guarda e o JavaScript da página não lê.
      </p>
      {notice ? (
        <p className="notice" role="status">
          {notice}
        </p>
      ) : null}
      <LoginForm />
      <p className="note">Não há registo nem recuperação de palavra-passe.</p>
      <p className="note">
        <a href="/">Voltar à entrada</a>
      </p>
    </main>
  );
}

function noticeFor(motivo: string | undefined): string | null {
  if (motivo === "sessao") return "A sessão terminou. Entre novamente.";
  if (motivo === "terminada") return "Sessão terminada neste browser.";
  return null;
}
