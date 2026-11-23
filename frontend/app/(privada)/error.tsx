"use client";

export default function PrivateError() {
  return (
    <main className="page narrow">
      <h1>Não foi possível mostrar esta página</h1>
      <p className="lead">Volte a tentar. Se a sessão tiver terminado, entre novamente.</p>
      <p className="links">
        <a className="primary" href="/inicio">
          Tentar novamente
        </a>
      </p>
    </main>
  );
}
