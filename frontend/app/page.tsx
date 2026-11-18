const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="page">
      <p className="eyebrow">Licenciatura em Desenvolvimento de Software</p>
      <h1>Kaivita Produtor Académico</h1>
      <p className="lead">
        Protótipo independente para a monografia. Este incremento, o I0,
        estabelece só a fundação técnica: interface, API e base de dados.
      </p>

      <section className="grid" aria-label="Componentes da fundação">
        <article>
          <h2>Interface</h2>
          <p>Next.js com TypeScript. Esta página é o ponto de entrada.</p>
        </article>
        <article>
          <h2>API</h2>
          <p>FastAPI expõe o estado do serviço e a documentação interactiva.</p>
        </article>
        <article>
          <h2>Dados</h2>
          <p>PostgreSQL, com o esquema versionado pelo Alembic.</p>
        </article>
      </section>

      <nav className="links" aria-label="Ligações da API">
        <a className="primary" href={`${apiUrl}/health`}>
          Estado da API
        </a>
        <a className="secondary" href={`${apiUrl}/docs`}>
          Documentação da API
        </a>
      </nav>

      <p className="note">
        Produtores, produtos, ofertas e autenticação ficam para os incrementos
        seguintes.
      </p>
    </main>
  );
}
