# Truth's Forge — Fusion 360 add-in

Bridge loopback entre o backend da Truth's Forge e o Fusion 360. O add-in
escuta em `127.0.0.1:<porta>` com um token efêmero, recebe JSON-RPC line-
delimited (mesma wire format dos servidores stdio do PR #5) e despacha cada
tool call para a main thread do Fusion via `app.fireCustomEvent` — o padrão
oficial da Autodesk para não corromper a API.

## Instalação

1. Garanta que o Fusion 360 está atualizado (versão 2.0.20000+ recomendada).
2. Em **Utilities → Scripts and Add-Ins → Add-Ins**, clique em **+ Add**.
3. Selecione esta pasta (`apps/fusion-addin/`).
4. Marque **Run on Startup** se quiser o bridge sempre ativo ao abrir o Fusion.
5. Clique em **Run**. Uma caixa de diálogo confirma o endereço/porta e o
   caminho do arquivo de discovery (`~/.truths_forge/fusion-bridge.json`).

O backend já vem pré-configurado para esse caminho. Para overridar (por
exemplo, em um workspace customizado), defina `TRUTHS_FORGE_FUSION_BRIDGE_DISCOVERY`
no ambiente onde o backend roda — o add-in respeita a mesma variável.

## Como o backend descobre o add-in

1. O add-in grava `fusion-bridge.json` com `{host, port, token, pid, tools}`
   ao subir (operação atômica via `.tmp` + rename).
2. O `FusionDesktopAdapter` lê o arquivo, abre TCP loopback, envia `auth`
   com o token e, em seguida, `tools/list`/`tools/call` conforme necessário.
3. Quando o add-in é desativado ou o Fusion fecha, o `stop()` apaga o
   arquivo de discovery. O backend volta a operar em mock.

## Segurança

- **Token efêmero**: regenerado a cada `run()`. Não persiste entre sessões.
- **Loopback-only**: o `bind` é em `127.0.0.1`. Conexões de fora da máquina
  são impossíveis no nível do socket.
- **Auth obrigatória**: o primeiro frame de cada conexão tem que ser
  `{"method": "auth", "params": {"token": "..."}}`. Qualquer outra coisa
  fecha o socket.
- **Allowlist de tools**: o `_execute_on_main_thread` rejeita tudo que não
  estiver em `FUSION_TOOLS`. Scripts livres não são suportados.
- **Sem subprocess shell**: a comunicação é só via socket loopback; o
  add-in nunca executa comandos do sistema operacional.

## Tools expostas

| Tool | O que faz |
|---|---|
| `fusion.open_design` | cria um documento de design novo |
| `fusion.create_sketch` | cria sketch em `xy`/`yz`/`xz` |
| `fusion.add_rectangle` | retângulo `width_mm × height_mm` centrado |
| `fusion.add_circle` | círculo `diameter_mm` em `(center_x_mm, center_y_mm)` |
| `fusion.extrude_profile` | extrude do último profile do sketch alvo, `distance_mm` + `operation` (`new_body`/`join`/`cut`/`intersect`) |
| `fusion.set_parameter` | upsert de `userParameter` (`name`, `expression`, `unit`) |
| `fusion.export_step` / `export_stl` / `export_3mf` | export pelo `ExportManager` |
| `fusion.validate_dimensions` | bbox e volume de cada corpo |
| `fusion.validate_printability` | placeholder — recomenda `blender.validate_printability` no STL/3MF |

## Troubleshooting

**Add-in não aparece em "Add-Ins"** — clique em **+ Add** e selecione a
pasta exata (`apps/fusion-addin/`); o `.manifest` precisa estar dentro.

**Caixa de diálogo não aparece** — verifique o painel **Text Commands**
(`Ctrl+Alt+C` no Windows) no console do Fusion; mensagens de erro do add-in
saem ali.

**Backend continua em "adapter_mock"** — confirme que o arquivo
`~/.truths_forge/fusion-bridge.json` existe; rode `python -m
app.modeling.fusion_adapter` (status check) ou cheque o `status` em
`GET /api/3d/capabilities`. Se o backend roda em container e o add-in no
host, o discovery file precisa estar montado como volume **e** o `127.0.0.1`
do container precisa enxergar o host — geralmente isso significa configurar
o adapter para usar `host.docker.internal` em vez de `127.0.0.1`. Esse modo
não está coberto neste PR (fica para uma evolução futura).

**"Timeout esperando main thread"** — alguma tool ficou presa numa caixa
de diálogo modal do Fusion. Feche o diálogo e tente de novo. O timeout
default é 120 s.
