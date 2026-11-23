import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { loadSession } from "../../lib/current-session";
import { CONNECTION_MESSAGE } from "../../lib/errors";
import { logoutAction } from "../login/actions";
import { ReloadOnBack } from "./reload-on-back";

export const dynamic = "force-dynamic";

export default async function PrivateLayout({ children }: { children: ReactNode }) {
  const session = await loadSession();
  if (session.kind === "anonymous") redirect("/login");
  if (session.kind === "invalid") redirect("/sessao/invalida");
  if (session.kind === "unavailable") {
    return (
      <main className="page narrow">
        <h1>Serviço indisponível</h1>
        <p className="alert" role="alert">
          {CONNECTION_MESSAGE}
        </p>
        <p className="note">A sessão neste browser mantém-se. Pode tentar outra vez.</p>
        <p className="links">
          <a className="primary" href="/inicio">
            Tentar novamente
          </a>
        </p>
        <LogoutForm />
      </main>
    );
  }

  return (
    <>
      <ReloadOnBack />
      <header className="bar">
        <div>
          <p className="eyebrow">Sessão</p>
          <p className="session-email">{session.email}</p>
        </div>
        <LogoutForm />
      </header>
      {children}
    </>
  );
}

function LogoutForm() {
  return (
    <form action={logoutAction}>
      <button className="secondary" type="submit">
        Terminar sessão
      </button>
    </form>
  );
}
