from __future__ import annotations


def judite_dev_response(message: str, model_id: str | None) -> str:
    selected = model_id or "modelo padrao configuravel"
    return (
        f"JUDITE esta operando no modo dev com {selected}. "
        "A camada de orquestracao ja esta preparada para roteamento, memoria, politicas e agentes. "
        f"Recebi sua mensagem: {message}"
    )
