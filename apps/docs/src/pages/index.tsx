import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";

const docs = [
  {
    title: "Arquitetura",
    description: "Visão dos serviços, dados e fluxo containerizado.",
    href: "/docs/architecture"
  },
  {
    title: "API",
    description: "Rotas iniciais, chat streaming, settings, custos e RAG.",
    href: "/docs/api"
  },
  {
    title: "MVP readiness",
    description: "O que já está pronto e o que ainda falta para o MVP.",
    href: "/docs/mvp-readiness"
  },
  {
    title: "Mapa da aplicação",
    description: "Explicação didática de cada elemento do monorepo.",
    href: "/docs/application-map"
  },
  {
    title: "Observabilidade",
    description: "Como ver Postgres, Redis/Valkey e Qdrant por GUIs.",
    href: "/docs/infra-observability"
  },
  {
    title: "Desenvolvimento local",
    description: "Como subir, testar e operar o stack no Docker.",
    href: "/docs/local-dev"
  }
];

export default function Home(): JSX.Element {
  return (
    <Layout title="Documentação" description="Documentação local do Truth's Forge AI">
      <main className="docsHome">
        <section className="docsHero">
          <div>
            <p className="eyebrow">Documentação local</p>
            <h1>Truth's Forge AI</h1>
            <p>
              Arquitetura, decisões, APIs e operação do MVP em um servidor dedicado,
              lendo os arquivos Markdown diretamente de <code>D:\projects\truths_forge_ai\docs</code>.
            </p>
            <div className="heroActions">
              <Link className="button button--primary" to="/docs/architecture">
                Abrir docs
              </Link>
              <Link className="button button--secondary" to="http://127.0.0.1:5173">
                Abrir aplicação
              </Link>
            </div>
          </div>
        </section>
        <section className="docsGrid">
          {docs.map((doc) => (
            <Link className="docCard" key={doc.href} to={doc.href}>
              <h2>{doc.title}</h2>
              <p>{doc.description}</p>
            </Link>
          ))}
        </section>
      </main>
    </Layout>
  );
}
