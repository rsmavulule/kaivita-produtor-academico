import type { ReactNode } from "react";

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="bar">
        <div>
          <p className="eyebrow">Kaivita Produtor</p>
          <a href="/">Início</a>
        </div>
        <nav className="links" aria-label="Descoberta">
          <a href="/ofertas">Ofertas</a>
          <a href="/login">Entrar</a>
        </nav>
      </header>
      {children}
    </>
  );
}
