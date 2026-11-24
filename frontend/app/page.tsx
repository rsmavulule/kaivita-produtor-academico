const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="page">
      <p className="eyebrow">Licenciatura em Desenvolvimento de Software</p>
      <h1>Kaivita Produtor Académico</h1>
      <p className="lead">
        Protótipo independente para a monografia. A interface autentica o
        representante. A sessão fica no servidor Next.js e a API continua a
        autorizar cada pedido.
      </p>

      <section className="grid" aria-label="Componentes da fundação">
        <article>
          <h2>Interface</h2>
          <p>Next.js com TypeScript. O login e a área privada começam aqui.</p>
        </article>
        <article>
          <h2>API</h2>
          <p>FastAPI valida a conta e continua a exigir o token Bearer.</p>
        </article>
        <article>
          <h2>Dados</h2>
          <p>PostgreSQL, com o esquema versionado pelo Alembic.</p>
        </article>
      </section>

      <nav className="links" aria-label="Entrada">
        <a className="primary" href="/login">
          Entrar
        </a>
      </nav>

      <nav className="links" aria-label="Ligações da API">
        <a className="secondary" href={`${apiUrl}/health`}>
          Estado da API
        </a>
        <a className="secondary" href={`${apiUrl}/docs`}>
          Documentação da API
        </a>
      </nav>

      <p className="note">
        A gestão de actores e papéis fica em /actores, depois de entrar.
        Produtos e ofertas ainda não têm ecrã. Não há registo público.
      </p>
    </main>
  );
}
