/** Ícone (chave lucide mapeada em ChatMessageList) de cada atalho do empty-state. */
export type QuickActionIcon = "boxes" | "lightbulb" | "users" | "library" | "scale";

export type QuickAction = {
  /** Texto exibido e semente do draft (o handler usa o label). */
  label: string;
  /** Sub-rótulo mono curto, descreve o ponto de partida (não é dado dinâmico). */
  hint: string;
  icon: QuickActionIcon;
};

export const quickActions: readonly QuickAction[] = [
  { label: "Planejar uma arquitetura técnica", hint: "começa um rascunho técnico", icon: "boxes" },
  { label: "Refinar uma ideia de produto", hint: "lapida o conceito", icon: "lightbulb" },
  { label: "Configurar um time de agentes", hint: "abre o editor de agentes", icon: "users" },
  { label: "Criar um prompt reutilizável", hint: "modela um prompt-mãe", icon: "library" },
  { label: "Revisar uma decisão do projeto", hint: "pesa os trade-offs", icon: "scale" }
];

export const infraLinks = [
  {
    title: "Postgres / pgAdmin",
    href: "http://localhost:8080",
    detail: "PGADMIN_DEFAULT_EMAIL / PGADMIN_DEFAULT_PASSWORD"
  },
  {
    title: "Redis / Valkey Commander",
    href: "http://127.0.0.1:8081",
    detail: "valkey:6379"
  },
  {
    title: "Qdrant Dashboard",
    href: "http://127.0.0.1:6333/dashboard",
    detail: "truths_forge_documents"
  },
  {
    title: "OpenAPI",
    href: "http://127.0.0.1:8000/docs",
    detail: "FastAPI Swagger"
  },
  {
    title: "Docs do projeto",
    href: "http://127.0.0.1:3000",
    detail: "Docusaurus"
  }
];
