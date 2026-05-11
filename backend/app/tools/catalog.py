from __future__ import annotations

from app.core.contracts import ToolDefinition

DEFAULT_TOOLS = [
    ToolDefinition(
        id="rag.search",
        name="Busca RAG",
        description="Consulta documentos e memoria semantica indexada.",
        category="knowledge",
    ),
    ToolDefinition(
        id="python.run",
        name="Executar Python",
        description="Executa codigo Python em sandbox Docker.",
        category="code",
        dangerous=True,
        requires_confirmation=True,
    ),
    ToolDefinition(
        id="filesystem.write",
        name="Alterar arquivos",
        description="Cria ou modifica arquivos reais no PC.",
        category="filesystem",
        dangerous=True,
        requires_confirmation=True,
    ),
]
