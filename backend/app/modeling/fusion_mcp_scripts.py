from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

FUSION_SCRIPT_TOOLS: tuple[str, ...] = (
    "fusion.open_design",
    "fusion.create_sketch",
    "fusion.add_rectangle",
    "fusion.add_circle",
    "fusion.add_polygon",
    "fusion.add_line",
    "fusion.add_arc",
    "fusion.add_ellipse",
    "fusion.add_slot",
    "fusion.add_box",
    "fusion.add_cylinder",
    "fusion.add_sphere",
    "fusion.add_cone",
    "fusion.extrude_profile",
    "fusion.revolve_profile",
    "fusion.fillet_edges",
    "fusion.chamfer_edges",
    "fusion.shell_body",
    "fusion.hole",
    "fusion.pattern_rectangular",
    "fusion.pattern_circular",
    "fusion.mirror_feature",
    "fusion.combine_bodies",
    "fusion.loft_profiles",
    "fusion.sweep_profile",
    "fusion.create_surface_patch",
    "fusion.thicken_surface",
    "fusion.stitch_surfaces",
    "fusion.trim_surface",
    "fusion.extend_surface",
    "fusion.offset_surface",
    "fusion.unstitch_surface",
    "fusion.add_construction_plane",
    "fusion.add_spline",
    "fusion.move_body",
    "fusion.scale_body",
    "fusion.delete_body",
    "fusion.split_body",
    "fusion.query_geometry",
    "fusion.query_timeline",
    "fusion.rollback_timeline",
    "fusion.set_parameter",
    "fusion.export_step",
    "fusion.export_stl",
    "fusion.export_3mf",
    "fusion.validate_dimensions",
    "fusion.validate_printability",
)


def build_autodesk_fusion_script(tool_name: str, arguments: dict[str, Any]) -> str:
    """Build a deterministic Fusion script for the official Autodesk MCP server.

    Autodesk's local Fusion MCP exposes a generic Python execution tool. This
    module keeps Truth's Forge on the narrow adapter path: only backend-owned
    scripts for allowlisted tools are generated, and model/user text only enters
    as JSON data.
    """

    if tool_name not in FUSION_SCRIPT_TOOLS:
        raise ValueError(f"Ferramenta Fusion fora da allowlist: {tool_name}")

    return dedent(
        f"""
        import json
        import math
        import tempfile
        import traceback
        from pathlib import Path

        import adsk.core
        import adsk.fusion

        TOOL_NAME = {json.dumps(tool_name)}
        # Fix #4: ARGUMENTS é desserializado em runtime via json.loads em vez
        # de interpolado direto como literal. O JSON usa ``true``/``false``/
        # ``null`` mas Python espera ``True``/``False``/``None``, então
        # qualquer arg booleano ou nulo crashava o script com
        # ``NameError: name 'true' is not defined``. Pego no trace do bug
        # porta-figurinhas WC2026 (fusion.export_stl com {{"binary": true}}).
        ARGUMENTS = json.loads({repr(json.dumps(arguments, ensure_ascii=False, sort_keys=True))})


        class ToolError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code


        def _emit(payload):
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


        def _app():
            app = adsk.core.Application.get()
            if app is None:
                raise ToolError("fusion.no_application", "Fusion API não retornou aplicação ativa.")
            return app


        def _design():
            design = adsk.fusion.Design.cast(_app().activeProduct)
            if design is None:
                raise ToolError(
                    "fusion.no_active_design",
                    (
                        "Nenhum design ativo no Fusion. "
                        "Abra ou crie um documento antes de chamar tools."
                    ),
                )
            return design


        def _root(design):
            return design.rootComponent


        def _plane_from_ref(design, plane_ref):
            # Fix #8: LLM as vezes manda planos abstratos que nao sao
            # construction planes (ex: "InnerFace_Left", "Top",
            # "front_face_of_body_1"). Esses casos exigem face references
            # reais, fora do escopo desta iteracao. Para evitar cascata,
            # fazemos fallback para XY com aviso e emitimos o nome
            # original no message do tool call (visivel via trace).
            # Fix T4 gate: planos construidos via add_construction_plane
            # devem ser reconhecidos por nome (sem isso, create_sketch
            # silenciosamente cai em XY apesar do plano existir).
            root = _root(design)
            mapping = {{
                "xy": root.xYConstructionPlane,
                "yz": root.yZConstructionPlane,
                "xz": root.xZConstructionPlane,
                "top": root.xYConstructionPlane,
                "front": root.xZConstructionPlane,
                "right": root.yZConstructionPlane,
            }}
            normalized = str(plane_ref or "xy").lower()
            plane = mapping.get(normalized)
            if plane is not None:
                return plane
            # Tenta resolver como plano construido pelo nome.
            target = str(plane_ref or "").strip()
            if target:
                for cp in root.constructionPlanes:
                    if cp.name == target:
                        return cp
            return root.xYConstructionPlane


        def _eval_param(value, design, default=None):
            # Fix #10: resolve valor para mm aceitando 4 formatos:
            #   (a) int/float       -> assume mm, retorna direto
            #   (b) "49" / "49.5"  -> parse direto como mm
            #   (c) "param_name"   -> lookup em userParameters
            #                         (com prefixo opcional "-" para negar)
            #   (d) "a + b - c"    -> eval em namespace dos params (mm)
            #
            # Fusion API armazena userParameters em cm internamente; multiplicamos
            # por 10 ao expor em mm. Para expressoes compostas usamos eval com
            # __builtins__ vazio (sandboxed) e namespace so com nomes/valores
            # dos parametros do design.
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if not isinstance(value, str):
                return default
            s = value.strip()
            # Sintaxe de expressao do Fusion: o LLM as vezes prefixa "=" como
            # na barra de parametros ("=plate_width", "=hole_diameter/2").
            # Removemos o "=" lider; o restante e nome de param ou expressao.
            if s.startswith("="):
                s = s[1:].strip()
            if not s:
                return default
            try:
                return float(s)
            except ValueError:
                pass
            # Lookup simples de parametro (com sinal opcional)
            simple_token = s.lstrip("-+").strip()
            if simple_token and all(c.isalnum() or c == "_" for c in simple_token):
                param = design.userParameters.itemByName(simple_token)
                if param is not None:
                    sign = -1.0 if s.startswith("-") else 1.0
                    return sign * float(param.value) * 10.0
            # Expressao composta: eval em namespace fechado (sem builtins).
            namespace = {{}}
            for i in range(design.userParameters.count):
                p = design.userParameters.item(i)
                namespace[p.name] = float(p.value) * 10.0
            try:
                return float(eval(s, {{"__builtins__": {{}}}}, namespace))
            except Exception:
                return default


        def _eval_pair(value_list, design):
            # Helper para listas tipo origin_mm=[x, y] ou cell_size_mm=[w, h]
            # cujos elementos podem ser strings paramentricas.
            if not isinstance(value_list, (list, tuple)) or len(value_list) < 2:
                return None
            a = _eval_param(value_list[0], design)
            b = _eval_param(value_list[1], design)
            if a is None or b is None:
                return None
            return (a, b)


        def _param_value_input(arg, design):
            # G1.1: retorna um ValueInput para uma distancia linear (mm).
            # Se ``arg`` e um NOME de parametro existente (ex: "Diameter_mm",
            # "-wall_thickness_mm"), usa createByString -> cria VINCULO
            # parametrico (mudar o parametro depois atualiza a geometria).
            # Senao, resolve para numero via _eval_param e usa createByReal
            # (cm). Expressoes compostas sao bakeadas para evitar ambiguidade
            # de unidade do createByString. Retorna None se nao resolver.
            if isinstance(arg, str):
                expr = arg.strip()
                if expr.startswith("="):
                    expr = expr[1:].strip()
                token = expr.lstrip("-+").strip()
                if token and all(c.isalnum() or c == "_" for c in token):
                    if design.userParameters.itemByName(token) is not None:
                        return adsk.core.ValueInput.createByString(expr)
            mm = _eval_param(arg, design)
            if mm is None:
                return None
            return adsk.core.ValueInput.createByReal(mm / 10.0)


        def _param_angle_input(arg, design):
            # G1.1: ValueInput para um ANGULO. Se ``arg`` referencia um
            # userParameter existente (nome/expressao), createByString -> vinculo
            # parametrico; senao numero em GRAUS -> radianos via createByReal.
            # None se nao resolver.
            if isinstance(arg, str):
                expr = arg.strip()
                if expr.startswith("="):
                    expr = expr[1:].strip()
                token = expr.lstrip("-+").strip()
                if token and all(c.isalnum() or c == "_" for c in token):
                    if design.userParameters.itemByName(token) is not None:
                        return adsk.core.ValueInput.createByString(expr)
            deg = _eval_param(arg, design)
            if deg is None:
                return None
            return adsk.core.ValueInput.createByReal(float(deg) * math.pi / 180.0)


        def _param_name_or_none(arg, design):
            # G1.2: retorna o nome do parametro se ``arg`` e uma referencia
            # pura a um userParameter existente; senao None. Usado para
            # decidir se vale a pena amarrar uma sketch dimension.
            if not isinstance(arg, str):
                return None
            token = arg.strip()
            if token.startswith("="):
                token = token[1:].strip()
            if token and all(c.isalnum() or c == "_" for c in token):
                if design.userParameters.itemByName(token) is not None:
                    return token
            return None


        def _find_sketch(design, sketch_ref=None):
            sketches = _root(design).sketches
            if not sketch_ref:
                if sketches.count == 0:
                    raise ToolError("fusion.no_sketch", "Nenhum sketch disponível na cena.")
                return sketches.item(sketches.count - 1)
            for index in range(sketches.count):
                item = sketches.item(index)
                if item.name == sketch_ref or item.entityToken == sketch_ref:
                    return item
            raise ToolError("fusion.sketch_not_found", "Sketch não encontrado.")


        def _find_body(design, body_ref=None):
            # Onda C + T4.2 (Fase 4): resolve body por:
            #   1. stable_id (TF.stable_id attribute) — sobrevive a rename.
            #   2. nome do body.
            #   3. indice (int/str) — volatil a reorder.
            #   4. ultimo criado quando ref vazio.
            bodies = _root(design).bRepBodies
            if bodies.count == 0:
                raise ToolError("fusion.no_body", "Nenhum corpo solido na cena.")
            if body_ref is None or body_ref == "":
                return bodies.item(bodies.count - 1)
            ref = str(body_ref)
            # T4.2: stable_id primeiro — sobrevive a rename do usuario e a
            # recompute, ao contrario de nome/indice.
            for i in range(bodies.count):
                if _stable_id_of(bodies.item(i)) == ref:
                    return bodies.item(i)
            for i in range(bodies.count):
                if bodies.item(i).name == ref:
                    return bodies.item(i)
            try:
                idx = int(ref)
                if 0 <= idx < bodies.count:
                    return bodies.item(idx)
            except (TypeError, ValueError):
                pass
            _avail = [bodies.item(i).name for i in range(bodies.count)]
            raise ToolError(
                "fusion.body_not_found",
                "Corpo nao encontrado: " + ref + ". Corpos disponiveis: " + str(_avail),
            )


        def _edge_z_range(edge):
            # Retorna (zmin, zmax) de uma aresta. Arestas circulares podem nao
            # ter start/end vertex; cai no boundingBox.
            try:
                z0 = edge.startVertex.geometry.z
                z1 = edge.endVertex.geometry.z
                return (min(z0, z1), max(z0, z1))
            except Exception:
                ebb = edge.boundingBox
                return (ebb.minPoint.z, ebb.maxPoint.z)


        def _select_edges_extra(body, selector, coll):
            # G2.1: selectors adicionais de aresta — tamanho e posicao.
            # longest/shortest: a aresta de maior/menor comprimento.
            # near=<implicito>: tratado fora (precisa de ponto).
            sel = selector.lower()
            edges = body.edges
            if sel in ("longest", "shortest"):
                best = None
                best_len = None
                for i in range(edges.count):
                    e = edges.item(i)
                    try:
                        length = e.length
                    except Exception:
                        continue
                    if best_len is None or (
                        length > best_len if sel == "longest" else length < best_len
                    ):
                        best_len = length
                        best = e
                if best is not None:
                    coll.add(best)
                return True
            return False


        def _select_edges(body, selector):
            # Onda C + G2.1 + T5.3a: selectors SEMANTICOS (o LLM nao conhece edge
            # tokens do Fusion). Suportados:
            #   all / top / bottom / vertical / horizontal (Onda C)
            #   longest / shortest (G2.1, por comprimento)
            #   free_edges (T5.3a, arestas com <2 faces — bordas livres de
            #   SurfaceBody; entrada tipica de extend_surface).
            selector = str(selector or "all").lower()
            coll = adsk.core.ObjectCollection.create()
            if selector == "free_edges":
                for i in range(body.edges.count):
                    edge = body.edges.item(i)
                    try:
                        face_count = edge.faces.count
                    except Exception:
                        face_count = 0
                    if face_count <= 1:
                        coll.add(edge)
                return coll
            if _select_edges_extra(body, selector, coll):
                return coll
            bbox = body.boundingBox
            zmin = bbox.minPoint.z
            zmax = bbox.maxPoint.z
            tol = max(1e-4, (zmax - zmin) * 0.01)
            for i in range(body.edges.count):
                edge = body.edges.item(i)
                if selector == "all":
                    coll.add(edge)
                    continue
                ez_min, ez_max = _edge_z_range(edge)
                if selector == "top" and abs(ez_min - zmax) <= tol and abs(ez_max - zmax) <= tol:
                    coll.add(edge)
                elif (
                    selector == "bottom"
                    and abs(ez_min - zmin) <= tol
                    and abs(ez_max - zmin) <= tol
                ):
                    coll.add(edge)
                elif selector == "vertical" and (ez_max - ez_min) > tol:
                    coll.add(edge)
                elif selector == "horizontal" and (ez_max - ez_min) <= tol:
                    coll.add(edge)
            return coll


        def _face_normal_axis(face):
            # G2.1: retorna o eixo dominante da normal da face planar
            # (+x/-x/+y/-y/+z/-z) ou None se nao for avaliavel.
            try:
                evaluator = face.geometry
                # Plano tem .normal; superficies curvas nao caem aqui.
                normal = evaluator.normal
            except Exception:
                return None
            comps = [("x", normal.x), ("y", normal.y), ("z", normal.z)]
            axis, value = max(comps, key=lambda c: abs(c[1]))
            if abs(value) < 0.7:
                return None
            return ("+" if value > 0 else "-") + axis


        def _select_faces(body, selector):
            # Onda C + G2.1: faces semanticas. Suportados:
            #   top / bottom (planar no zmax/zmin) — Onda C
            #   none (nenhuma) — Onda C
            #   +x/-x/+y/-y/+z/-z (orientacao da normal) — G2.1
            #   planar / cylindrical (tipo de superficie) — G2.1
            #   largest (maior area) — G2.1
            selector = str(selector or "top").lower()
            coll = adsk.core.ObjectCollection.create()
            if selector == "none":
                return coll
            bbox = body.boundingBox
            zmin = bbox.minPoint.z
            zmax = bbox.maxPoint.z
            tol = max(1e-4, (zmax - zmin) * 0.01)

            if selector == "largest":
                best = None
                best_area = None
                for i in range(body.faces.count):
                    f = body.faces.item(i)
                    try:
                        area = f.area
                    except Exception:
                        continue
                    if best_area is None or area > best_area:
                        best_area = area
                        best = f
                if best is not None:
                    coll.add(best)
                return coll

            for i in range(body.faces.count):
                face = body.faces.item(i)
                fbb = face.boundingBox
                surface_type = face.geometry.surfaceType
                is_planar = surface_type == adsk.core.SurfaceTypes.PlaneSurfaceType
                is_cyl = surface_type == adsk.core.SurfaceTypes.CylinderSurfaceType
                if (
                    selector == "top"
                    and abs(fbb.minPoint.z - zmax) <= tol
                    and abs(fbb.maxPoint.z - zmax) <= tol
                ):
                    coll.add(face)
                elif (
                    selector == "bottom"
                    and abs(fbb.minPoint.z - zmin) <= tol
                    and abs(fbb.maxPoint.z - zmin) <= tol
                ):
                    coll.add(face)
                elif selector == "planar" and is_planar:
                    coll.add(face)
                elif selector == "cylindrical" and is_cyl:
                    coll.add(face)
                elif selector in ("+x", "-x", "+y", "-y", "+z", "-z"):
                    if _face_normal_axis(face) == selector:
                        coll.add(face)
            return coll


        def _maybe_rename_last_body(design, args):
            # G2.3: se o caller passou result_name/output_name, renomeia o
            # body recem-criado (assumido o ultimo) para um nome estavel,
            # permitindo que pattern/mirror/fillet referenciem com seguranca
            # e resolvendo o drift de identidade. NAO usa 'result' (que e
            # alias de operation no revolve).
            name = args.get("result_name") or args.get("output_name")
            if not name:
                return None
            bodies = _root(design).bRepBodies
            if bodies.count == 0:
                return None
            try:
                bodies.item(bodies.count - 1).name = str(name)
                return str(name)
            except Exception:
                return None


        def _edges_by_ids(body, ids):
            # G2.2: seleciona arestas por indice explicito (vindo de
            # query_geometry). Mais preciso que selectors semanticos.
            coll = adsk.core.ObjectCollection.create()
            for raw in ids:
                try:
                    idx = int(raw)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < body.edges.count:
                    coll.add(body.edges.item(idx))
            return coll


        def _faces_by_ids(body, ids):
            coll = adsk.core.ObjectCollection.create()
            for raw in ids:
                try:
                    idx = int(raw)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < body.faces.count:
                    coll.add(body.faces.item(idx))
            return coll


        def _open_design(args):
            # P3 (edicao nao pode quebrar o modelo): por padrao REUSA o design
            # ativo em vez de criar um 'Untitled' novo a cada execucao — antes,
            # toda edicao criava um documento novo e zerava o modelo. Cria um
            # documento novo apenas quando NAO ha design ativo OU quando o
            # caller pede explicitamente (new_document/reset/force_new), que e
            # o caso de "modelo do zero". Ver chat-flow-redesign.md (P3).
            args = args or {{}}
            force_new = bool(
                args.get("new_document")
                or args.get("reset")
                or args.get("force_new")
            )
            app = _app()
            if not force_new:
                active = adsk.fusion.Design.cast(app.activeProduct)
                if active is not None:
                    doc_name = ""
                    try:
                        doc_name = app.activeDocument.name
                    except Exception:
                        doc_name = ""
                    return {{
                        "message": "Design ativo reutilizado{{}}.".format(
                            " ('" + doc_name + "')" if doc_name else ""
                        ),
                        "document_name": doc_name,
                        "reused": True,
                    }}
            doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            return {{
                "message": "Documento '{{}}' criado.".format(doc.name),
                "document_name": doc.name,
                "reused": False,
            }}


        def _create_sketch(args):
            # Fix #2: aceita aliases ``plane``/``plane_ref`` e
            # ``sketch_name``/``name`` porque o LLM (planner) emite o
            # primeiro de cada par mas a versão antiga deste script só
            # lia o segundo, descartando silenciosamente o nome do
            # usuário.
            # Fix #8: planos desconhecidos (ex: 'InnerFace_Left') caiam
            # em XY com warning visivel via trace ao inves de cascade.
            # Schema drift (teste bola, 20/05): o LLM usa ``sketch`` como nome
            # consistentemente em create_sketch E nos steps seguintes
            # (add_arc/add_line/revolve que buscam por ``sketch``). Aceitar
            # ``sketch`` como alias do nome aqui faz toda a cadeia linkar —
            # senao o nome vira default TF_Sketch e os steps seguintes dao
            # sketch_not_found (drift de identidade do handoff).
            design = _design()
            plane_ref = str(args.get("plane_ref") or args.get("plane") or "xy")
            name = str(
                args.get("sketch_name")
                or args.get("name")
                or args.get("sketch")
                or "TF_Sketch"
            )
            _KNOWN_PLANES = ("xy", "yz", "xz", "top", "front", "right")
            # Fix T4 gate: plano construido (criado via add_construction_plane)
            # tambem conta como resolvido — _plane_from_ref agora o reconhece.
            construction_names = {{cp.name for cp in _root(design).constructionPlanes}}
            fallback_applied = (
                plane_ref.lower() not in _KNOWN_PLANES
                and plane_ref not in construction_names
            )
            sketch = _root(design).sketches.add(_plane_from_ref(design, plane_ref))
            sketch.name = name
            warn_suffix = (
                " [WARN: plano '{{}}' nao suportado, usei XY como fallback]".format(plane_ref)
                if fallback_applied
                else ""
            )
            return {{
                "message": "Sketch '{{}}' criado em {{}}.{{}}".format(
                    sketch.name, plane_ref, warn_suffix
                ),
                "sketch_name": sketch.name,
                "sketch_token": sketch.entityToken,
                "plane_fallback_applied": fallback_applied,
            }}


        def _add_rectangle(args):
            # Fix #6: aceita formatos do LLM:
            # (a) width_mm + height_mm                (legado/canonico)
            # (b) corner1_mm=[x1,y1] + corner2_mm=[x2,y2]   (dois pontos)
            # (c) size_mm=[w, h]                       (lista shorthand)
            # Fix #9: modo grade quando vier cols + rows + cell_size_mm.
            # LLM usa esse formato para criar grades de bolsos. Cada
            # celula vira um retangulo separado no mesmo sketch, com
            # offset incremental.
            design = _design()

            # Drift do trace placa-parametrizada: o LLM emite chaves sem
            # sufixo (width/height) com sintaxe de expressao do Fusion
            # ("=plate_width"). Mapeamos para as chaves canonicas _mm;
            # _eval_param/_param_name_or_none ja lidam com o "=" lider.
            args = dict(args)
            for _canon, _alias in (("width_mm", "width"), ("height_mm", "height")):
                if args.get(_canon) is None and args.get(_alias) is not None:
                    args[_canon] = args[_alias]

            # Fix #10: cols/rows podem vir como nomes de parametro
            # (ex: "num_rows"). Resolve via _eval_param antes do int().
            cols_val = _eval_param(args.get("cols") or args.get("columns"), design, 0.0)
            rows_val = _eval_param(args.get("rows"), design, 0.0)
            cols = int(cols_val or 0)
            rows = int(rows_val or 0)
            cell_pair = _eval_pair(args.get("cell_size_mm"), design)
            if (
                cols > 0
                and rows > 0
                and cell_pair is not None
            ):
                cell_w_mm, cell_h_mm = cell_pair
                gap_mm = _eval_param(args.get("gap_mm"), design, 0.0) or 0.0
                grid_pair = _eval_pair(
                    args.get("grid_origin_mm") or [0, 0], design
                ) or (0.0, 0.0)
                origin_x_mm, origin_y_mm = grid_pair
                sketch = _find_sketch(design, args.get("sketch"))
                count = 0
                for row in range(rows):
                    for col in range(cols):
                        x0_mm = origin_x_mm + col * (cell_w_mm + gap_mm)
                        y0_mm = origin_y_mm + row * (cell_h_mm + gap_mm)
                        p1 = adsk.core.Point3D.create(
                            x0_mm / 10.0, y0_mm / 10.0, 0
                        )
                        p2 = adsk.core.Point3D.create(
                            (x0_mm + cell_w_mm) / 10.0,
                            (y0_mm + cell_h_mm) / 10.0,
                            0,
                        )
                        sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
                        count += 1
                return {{
                    "message": (
                        "Grade {{}}x{{}} ({{}} retangulos {{}}x{{}}mm) "
                        "adicionada a '{{}}'."
                    ).format(
                        cols, rows, count, cell_w_mm, cell_h_mm, sketch.name
                    ),
                    "sketch_name": sketch.name,
                    "rectangles_added": count,
                }}

            # Fix #10: width_mm/height_mm podem ser expressoes paramentricas.
            width_mm = _eval_param(args.get("width_mm"), design, 0.0) or 0.0
            height_mm = _eval_param(args.get("height_mm"), design, 0.0) or 0.0

            corner1 = _eval_pair(
                args.get("corner1_mm") or args.get("point1_mm"), design
            )
            corner2 = _eval_pair(
                args.get("corner2_mm") or args.get("point2_mm"), design
            )
            if width_mm <= 0 and height_mm <= 0 and corner1 and corner2:
                width_mm = abs(corner2[0] - corner1[0])
                height_mm = abs(corner2[1] - corner1[1])

            size_pair = _eval_pair(args.get("size_mm"), design)
            if width_mm <= 0 and height_mm <= 0 and size_pair:
                width_mm, height_mm = size_pair

            if width_mm <= 0 or height_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "width_mm/height_mm (ou corner1_mm+corner2_mm, "
                    "ou size_mm) precisam ser positivos.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            width_cm = width_mm / 10.0
            height_cm = height_mm / 10.0
            point1 = adsk.core.Point3D.create(-width_cm / 2, -height_cm / 2, 0)
            point2 = adsk.core.Point3D.create(width_cm / 2, height_cm / 2, 0)
            rect_lines = sketch.sketchCurves.sketchLines.addTwoPointRectangle(point1, point2)
            # G1.2: amarra width/height a parametros quando vieram como
            # referencia. SEGURO: retangulo ja desenhado; dimension em
            # try/except mantem o bakeado se algo falhar (sem regressao).
            _param_dim = False
            try:
                w_name = _param_name_or_none(args.get("width_mm"), design)
                h_name = _param_name_or_none(args.get("height_mm"), design)
                dims = sketch.sketchDimensions
                horiz = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
                vert = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
                if w_name:
                    bottom = rect_lines.item(0)
                    dim = dims.addDistanceDimension(
                        bottom.startSketchPoint,
                        bottom.endSketchPoint,
                        horiz,
                        adsk.core.Point3D.create(0, -height_cm / 2 - 0.5, 0),
                    )
                    dim.parameter.expression = w_name
                    _param_dim = True
                if h_name:
                    right = rect_lines.item(1)
                    dim = dims.addDistanceDimension(
                        right.startSketchPoint,
                        right.endSketchPoint,
                        vert,
                        adsk.core.Point3D.create(width_cm / 2 + 0.5, 0, 0),
                    )
                    dim.parameter.expression = h_name
                    _param_dim = True
            except Exception:
                _param_dim = False
            return {{
                "message": "Retângulo {{}}x{{}} mm adicionado a '{{}}'{{}}.".format(
                    width_mm, height_mm, sketch.name, " [parametrico]" if _param_dim else ""
                ),
                "sketch_name": sketch.name,
            }}


        def _add_circle(args):
            # Fix #10: diameter_mm/center_*_mm podem ser expressoes paramentricas.
            # Onda A quick fix: aceita aliases circle_diameter_mm e radius_mm
            # (LLM varia o nome do campo). center_mm=[x,y] como lista tambem.
            design = _design()

            # Drift do trace placa-parametrizada: chaves sem sufixo
            # (radius/diameter) com sintaxe de expressao ("=hole_diameter/2").
            args = dict(args)

            # Fix T4 gate: o planner as vezes empacota multiplas chamadas em
            # 1 step (ex.: 4 furos num unico add_circle). O normalizador
            # embrulha a lista em {{"_raw": [...]}}; aqui desempacotamos e
            # iteramos. Mantemos so itens dict para evitar recursao maligna.
            raw_batch = args.get("_raw")
            if isinstance(raw_batch, list):
                batch_results = []
                batch_messages = []
                for item in raw_batch:
                    if not isinstance(item, dict):
                        continue
                    inner = _add_circle(item)
                    batch_results.append(inner)
                    inner_msg = inner.get("message") if isinstance(inner, dict) else None
                    if inner_msg:
                        batch_messages.append(inner_msg)
                if not batch_results:
                    raise ToolError(
                        "fusion.invalid_dimensions",
                        "add_circle batch vazio: forneca pelo menos um item valido.",
                    )
                summary = "{{}} circulos adicionados em batch.".format(len(batch_results))
                return {{
                    "message": summary,
                    "batch": True,
                    "count": len(batch_results),
                    "items": batch_results,
                    "messages": batch_messages,
                }}

            for _canon, _alias in (("diameter_mm", "diameter"), ("radius_mm", "radius")):
                if args.get(_canon) is None and args.get(_alias) is not None:
                    args[_canon] = args[_alias]

            diameter_mm = _eval_param(
                args.get("diameter_mm") or args.get("circle_diameter_mm"), design, 0.0
            ) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            if diameter_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm/circle_diameter_mm) precisa ser positivo.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            radius_cm = diameter_mm / 20.0
            center_pair = _eval_pair(args.get("center_mm"), design)
            if center_pair is not None:
                center_x_mm, center_y_mm = center_pair
            else:
                center_x_mm = _eval_param(args.get("center_x_mm"), design, 0.0) or 0.0
                center_y_mm = _eval_param(args.get("center_y_mm"), design, 0.0) or 0.0
            center = adsk.core.Point3D.create(
                center_x_mm / 10.0,
                center_y_mm / 10.0,
                0,
            )
            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius_cm)
            # G1.2: se diameter/radius veio como referencia a parametro, amarra
            # uma sketch dimension ao parametro (geometria editavel-por-param).
            # SEGURO: a geometria ja foi desenhada acima no valor resolvido;
            # se a dimension falhar/over-constrain, o try/except mantem o
            # circulo bakeado (sem regressao no extrude).
            _param_dim = False
            try:
                d_name = _param_name_or_none(
                    args.get("diameter_mm") or args.get("circle_diameter_mm"), design
                )
                r_name = _param_name_or_none(args.get("radius_mm"), design)
                if d_name:
                    dim = sketch.sketchDimensions.addDiameterDimension(
                        circle, circle.centerSketchPoint.geometry
                    )
                    dim.parameter.expression = d_name
                    _param_dim = True
                elif r_name:
                    dim = sketch.sketchDimensions.addRadialDimension(
                        circle, circle.centerSketchPoint.geometry
                    )
                    dim.parameter.expression = r_name
                    _param_dim = True
            except Exception:
                _param_dim = False
            return {{
                "message": "Círculo ø{{}} mm adicionado a '{{}}'{{}}.".format(
                    diameter_mm, sketch.name, " [parametrico]" if _param_dim else ""
                ),
                "sketch_name": sketch.name,
            }}


        def _extrude_profile(args):
            # Fix #10: distance_mm pode ser expressao paramentrica.
            # Aceita tambem distancia negativa (para cut em direcao oposta).
            design = _design()

            # Drift do trace placa-parametrizada: chave sem sufixo (distance)
            # com sintaxe de expressao do Fusion ("=thickness").
            args = dict(args)
            for _canon, _alias in (("distance_mm", "distance"),):
                if args.get(_canon) is None and args.get(_alias) is not None:
                    args[_canon] = args[_alias]

            distance_mm = _eval_param(args.get("distance_mm"), design, 0.0) or 0.0
            if distance_mm == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "distance_mm precisa ser diferente de zero.",
                )
            operation = str(args.get("operation") or "new_body").lower()
            operation_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            # Onda A quick fix: operation desconhecida (ex: 'join_or_new_body'
            # que o LLM inventou) cai em new_body com warning visivel no trace
            # em vez de abortar o step. Tenta primeiro extrair um token valido
            # da string composta.
            operation_warning = ""
            if operation not in operation_map:
                matched = next((op for op in operation_map if op in operation), None)
                fallback_op = matched or "new_body"
                operation_warning = (
                    " [WARN: operation '{{}}' invalida, usei '{{}}']".format(
                        operation, fallback_op
                    )
                )
                operation = fallback_op
            sketch = _find_sketch(design, args.get("sketch"))
            # T5.1a/T5.1b (Fase 5): as_surface=true permite (1) produzir
            # SurfaceBody (isSolid=False) e (2) usar openProfile quando o
            # sketch nao tem profile fechado. Sem o flag, mantem checagem
            # legada que exige profile fechado.
            as_surface = bool(args.get("as_surface"))
            if not as_surface and sketch.profiles.count == 0:
                raise ToolError(
                    "fusion.no_profile",
                    "Sketch não tem profile fechado para extrudar.",
                )
            # Fix (trace m3d_plan_2f7aeff0): nao extrudar cegamente profiles[0].
            # Seletor explicito quando informado; aviso visivel no trace quando
            # um cut ambiguo (varios profiles, sem seletor) cai no profiles[0] —
            # foi exatamente isso que consumiu a placa no gate.
            profile = _profile_or_open(sketch, args, design, as_surface)
            _has_selector = (
                args.get("profile_index") is not None
                or args.get("profile_diameter_mm") is not None
            )
            if operation == "cut" and sketch.profiles.count > 1 and not _has_selector:
                operation_warning += (
                    " [WARN: cut em sketch com "
                    + str(sketch.profiles.count)
                    + " profiles sem seletor; usei profiles[0] - verifique se nao"
                    + " consumiu a peca (use profile_index/profile_diameter_mm)]"
                )
            extrudes = _root(design).features.extrudeFeatures
            input_obj = extrudes.createInput(profile, operation_map[operation])
            if as_surface:
                input_obj.isSolid = False
            input_obj.setDistanceExtent(
                False,
                _param_value_input(args.get("distance_mm"), design),
            )
            ext = extrudes.add(input_obj)
            body_name = None
            stable_id = None
            if ext.bodies.count > 0:
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or sketch.name))
                ext.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(ext.bodies.item(0))
            dims = _body_dims_mm(ext.bodies.item(0)) if ext.bodies.count > 0 else [0.0, 0.0, 0.0]
            kind_label = "Superficie extrudada" if as_surface else "Extrusao"
            return {{
                "message": "{{}} de {{}} mm aplicada (operation={{}}).{{}}".format(
                    kind_label, distance_mm, operation, operation_warning
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "is_surface": as_surface,
            }}


        def _add_polygon(args):
            # Onda A: poligono regular de N lados inscrito num circulo.
            # Constroi os vertices por trigonometria e conecta com linhas
            # (Fusion auto-merge de pontos coincidentes fecha o profile).
            # Aceita diameter_mm OU radius_mm; center_mm=[x,y] opcional.
            design = _design()
            sides = int(_eval_param(args.get("sides"), design, 0.0) or 0)
            if sides < 3:
                raise ToolError("fusion.invalid_dimensions", "sides precisa ser >= 3.")
            radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
            if radius_mm <= 0:
                diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
                if diameter_mm > 0:
                    radius_mm = diameter_mm / 2
            if radius_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm ou radius_mm precisa ser positivo.",
                )
            center_pair = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            cx_cm = center_pair[0] / 10.0
            cy_cm = center_pair[1] / 10.0
            radius_cm = radius_mm / 10.0
            sketch = _find_sketch(design, args.get("sketch"))
            points = []
            for i in range(sides):
                angle = 2 * math.pi * i / sides + math.pi / 2
                points.append(
                    adsk.core.Point3D.create(
                        cx_cm + radius_cm * math.cos(angle),
                        cy_cm + radius_cm * math.sin(angle),
                        0,
                    )
                )
            lines = sketch.sketchCurves.sketchLines
            for i in range(sides):
                lines.addByTwoPoints(points[i], points[(i + 1) % sides])
            return {{
                "message": "Poligono de {{}} lados (r={{}}mm) adicionado a '{{}}'.".format(
                    sides, radius_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_line(args):
            # Onda A: polilinha a partir de uma lista de pontos [[x,y],...].
            # closed=true fecha o loop (ultimo -> primeiro), permitindo
            # perfis arbitrarios fechados para extrude/revolve.
            design = _design()
            raw_points = args.get("points_mm") or args.get("points") or []
            # Schema drift (teste bola): o LLM tambem manda uma unica linha
            # como start_mm + end_mm. Convertemos para a lista de 2 pontos.
            if not raw_points:
                s = args.get("start_mm")
                e = args.get("end_mm")
                if s is not None and e is not None:
                    raw_points = [s, e]
            if not isinstance(raw_points, list) or len(raw_points) < 2:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "informe points_mm (>= 2 pontos) OU start_mm + end_mm.",
                )
            pts = []
            for raw in raw_points:
                pair = _eval_pair(raw, design)
                if pair is None:
                    raise ToolError(
                        "fusion.invalid_dimensions",
                        "ponto invalido em points_mm; use [x, y] em mm.",
                    )
                pts.append(adsk.core.Point3D.create(pair[0] / 10.0, pair[1] / 10.0, 0))
            sketch = _find_sketch(design, args.get("sketch"))
            lines = sketch.sketchCurves.sketchLines
            closed = bool(args.get("closed"))
            n = len(pts)
            edges = n if closed else n - 1
            for i in range(edges):
                lines.addByTwoPoints(pts[i], pts[(i + 1) % n])
            return {{
                "message": "Polilinha de {{}} ponto(s){{}} adicionada a '{{}}'.".format(
                    n, " (fechada)" if closed else "", sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_arc(args):
            # Onda A: arco por centro + ponto inicial + angulo de varredura.
            # Schema drift (teste bola): o LLM tambem manda forma POLAR
            # (center_mm + radius_mm + start_angle_deg + end_angle_deg).
            # Aceitamos os dois: se start_mm faltar mas radius+start_angle
            # vierem, derivamos o ponto inicial; se sweep_deg faltar mas
            # end_angle vier, derivamos sweep = end - start.
            # Fix T4 gate: 3a sinatura natural — start_mm + end_mm + center_mm
            # (LLM emite isso ao descrever "arco de A para B em torno de C").
            # Compute sweep via atan2; default = arco curto (sweep normalizado
            # em (-180, 180]). Se o usuario quer o arco longo, deve passar
            # sweep_deg ou angles explicitos.
            design = _design()
            center_pair = _eval_pair(args.get("center_mm"), design)
            if center_pair is None:
                raise ToolError("fusion.invalid_dimensions", "center_mm e obrigatorio.")
            start_pair = _eval_pair(args.get("start_mm"), design)
            end_pair = _eval_pair(args.get("end_mm"), design)
            sweep_deg = _eval_param(args.get("sweep_deg"), design, 0.0) or 0.0
            radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
            start_angle = _eval_param(args.get("start_angle_deg"), design, 0.0) or 0.0
            end_angle = _eval_param(args.get("end_angle_deg"), design)
            if start_pair is None and radius_mm > 0:
                start_pair = (
                    center_pair[0] + radius_mm * math.cos(start_angle * math.pi / 180.0),
                    center_pair[1] + radius_mm * math.sin(start_angle * math.pi / 180.0),
                )
            if sweep_deg == 0 and end_angle is not None:
                sweep_deg = float(end_angle) - start_angle
            if sweep_deg == 0 and start_pair is not None and end_pair is not None:
                sa = math.atan2(
                    start_pair[1] - center_pair[1], start_pair[0] - center_pair[0]
                )
                ea = math.atan2(
                    end_pair[1] - center_pair[1], end_pair[0] - center_pair[0]
                )
                sweep_rad = ea - sa
                while sweep_rad <= -math.pi:
                    sweep_rad += 2 * math.pi
                while sweep_rad > math.pi:
                    sweep_rad -= 2 * math.pi
                if abs(sweep_rad) > 1e-9:
                    sweep_deg = sweep_rad * 180.0 / math.pi
            if start_pair is None or sweep_deg == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "informe start_mm+sweep_deg OU start_mm+end_mm+center_mm OU radius_mm+start_angle_deg+end_angle_deg.",
                )
            center = adsk.core.Point3D.create(
                center_pair[0] / 10.0, center_pair[1] / 10.0, 0
            )
            start = adsk.core.Point3D.create(
                start_pair[0] / 10.0, start_pair[1] / 10.0, 0
            )
            sketch = _find_sketch(design, args.get("sketch"))
            sweep_rad = sweep_deg * math.pi / 180.0
            sketch.sketchCurves.sketchArcs.addByCenterStartSweep(center, start, sweep_rad)
            return {{
                "message": "Arco de {{}} graus adicionado a '{{}}'.".format(
                    sweep_deg, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_ellipse(args):
            # G3: elipse por centro + eixos maior/menor (diametros em mm).
            design = _design()
            major_mm = _eval_param(args.get("major_mm") or args.get("width_mm"), design, 0.0) or 0.0
            minor_mm = _eval_param(args.get("minor_mm") or args.get("height_mm"), design, 0.0) or 0.0
            if major_mm <= 0 or minor_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "major_mm e minor_mm precisam ser positivos.",
                )
            center_pair = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            cx = center_pair[0] / 10.0
            cy = center_pair[1] / 10.0
            a = major_mm / 20.0
            b = minor_mm / 20.0
            sketch = _find_sketch(design, args.get("sketch"))
            center = adsk.core.Point3D.create(cx, cy, 0)
            major = adsk.core.Point3D.create(cx + a, cy, 0)
            through = adsk.core.Point3D.create(cx, cy + b, 0)
            sketch.sketchCurves.sketchEllipses.add(center, major, through)
            return {{
                "message": "Elipse {{}}x{{}} mm adicionada a '{{}}'.".format(
                    major_mm, minor_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _add_slot(args):
            # G3: slot (oblongo) horizontal: 2 arcos semicirculares + 2 linhas.
            # length_mm = comprimento total (centro a centro + width); width_mm
            # = diametro das pontas. Centrado em center_mm.
            design = _design()
            length_mm = _eval_param(args.get("length_mm"), design, 0.0) or 0.0
            width_mm = _eval_param(args.get("width_mm"), design, 0.0) or 0.0
            if length_mm <= 0 or width_mm <= 0 or length_mm <= width_mm:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "length_mm e width_mm positivos e length > width.",
                )
            center_pair = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            cx = center_pair[0] / 10.0
            cy = center_pair[1] / 10.0
            r = width_mm / 20.0
            half = (length_mm - width_mm) / 20.0  # distancia do centro a cada arco
            sketch = _find_sketch(design, args.get("sketch"))
            lines = sketch.sketchCurves.sketchLines
            arcs = sketch.sketchCurves.sketchArcs
            # linhas superior e inferior
            lines.addByTwoPoints(
                adsk.core.Point3D.create(cx - half, cy + r, 0),
                adsk.core.Point3D.create(cx + half, cy + r, 0),
            )
            lines.addByTwoPoints(
                adsk.core.Point3D.create(cx - half, cy - r, 0),
                adsk.core.Point3D.create(cx + half, cy - r, 0),
            )
            # arco direito (de cima para baixo, bulge +x) e esquerdo (bulge -x)
            arcs.addByCenterStartSweep(
                adsk.core.Point3D.create(cx + half, cy, 0),
                adsk.core.Point3D.create(cx + half, cy + r, 0),
                -math.pi,
            )
            arcs.addByCenterStartSweep(
                adsk.core.Point3D.create(cx - half, cy, 0),
                adsk.core.Point3D.create(cx - half, cy - r, 0),
                -math.pi,
            )
            return {{
                "message": "Slot {{}}x{{}} mm adicionado a '{{}}'.".format(
                    length_mm, width_mm, sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        def _revolve_profile(args):
            # Onda A: revolve um profile fechado em torno de um eixo
            # (x/y/z) por um angulo (default 360 = solido completo).
            # Destrava esferas (semicirculo revolvido), cones, vasos.
            design = _design()
            sketch = _find_sketch(design, args.get("sketch"))
            # T5.1b: as_surface=true aceita meio-perfil aberto (openProfile);
            # sem o flag, mantem a exigencia legada de profile fechado.
            _as_surface_early = bool(args.get("as_surface"))
            if not _as_surface_early and sketch.profiles.count == 0:
                raise ToolError(
                    "fusion.no_profile",
                    "Sketch nao tem profile fechado para revolver.",
                )
            angle_deg = _eval_param(args.get("angle_deg"), design, 360.0)
            if not angle_deg:
                angle_deg = 360.0
            # Schema drift (teste bola): o LLM manda ``result`` em vez de
            # ``operation``. Aceitamos os dois.
            operation = str(
                args.get("operation") or args.get("result") or "new_body"
            ).lower()
            operation_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            op = operation_map.get(operation, operation_map["new_body"])
            # Fix T4 gate: o LLM as vezes emite ``axis_line`` (formato
            # geometrico: 2 pontos 3D definindo a reta) em vez de ``axis``
            # ("x"/"y"/"z"). O handler antigo ignorava axis_line e caia no
            # default "y", causando ASM_PATH_TANGENT quando o eixo Y cruzava
            # o perfil. Derivamos o axis nativo pelo maior componente do
            # vetor end-start; se for arbitrario (nao alinhado a x/y/z) cai
            # no default antigo para evitar regressao.
            axis_name = str(args.get("axis") or "").lower().strip()
            if axis_name not in ("x", "y", "z"):
                axis_line = args.get("axis_line")
                if (
                    isinstance(axis_line, (list, tuple))
                    and len(axis_line) == 2
                    and isinstance(axis_line[0], (list, tuple))
                    and isinstance(axis_line[1], (list, tuple))
                    and len(axis_line[0]) >= 3
                    and len(axis_line[1]) >= 3
                ):
                    dx = float(axis_line[1][0]) - float(axis_line[0][0])
                    dy = float(axis_line[1][1]) - float(axis_line[0][1])
                    dz = float(axis_line[1][2]) - float(axis_line[0][2])
                    mag = max(abs(dx), abs(dy), abs(dz))
                    if mag > 1e-9:
                        if abs(dx) == mag:
                            axis_name = "x"
                        elif abs(dy) == mag:
                            axis_name = "y"
                        elif abs(dz) == mag:
                            axis_name = "z"
            if axis_name not in ("x", "y", "z"):
                axis_name = "y"
            root = _root(design)
            axis_map = {{
                "x": root.xConstructionAxis,
                "y": root.yConstructionAxis,
                "z": root.zConstructionAxis,
            }}
            axis = axis_map.get(axis_name, root.yConstructionAxis)
            revolves = root.features.revolveFeatures
            # T5.1a/T5.1b: as_surface=true forca SurfaceBody (isSolid=False)
            # antes do setAngleExtent e aceita meio-perfil aberto (no modo
            # solido o perfil precisa cruzar o eixo; em surface nao).
            as_surface = _as_surface_early
            input_obj = revolves.createInput(
                _profile_or_open(sketch, args, design, as_surface), axis, op
            )
            if as_surface:
                input_obj.isSolid = False
            # G1.1: liga o angulo a um parametro quando ``angle_deg`` referencia
            # um userParameter (createByString); senao usa o numero resolvido.
            angle_vi = _param_angle_input(args.get("angle_deg"), design)
            if angle_vi is None:
                angle_vi = adsk.core.ValueInput.createByReal(float(angle_deg) * math.pi / 180.0)
            input_obj.setAngleExtent(False, angle_vi)
            feat = revolves.add(input_obj)
            # Fix T4 gate: nomeia o body criado para que edits subsequentes
            # consigam referenciar por nome (vide _extrude_profile).
            body_name = None
            stable_id = None
            if feat.bodies.count > 0:
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or sketch.name))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
            dims = _body_dims_mm(feat.bodies.item(0)) if feat.bodies.count > 0 else [0.0, 0.0, 0.0]
            raw_angle = args.get("angle_deg")
            if isinstance(raw_angle, str):
                angle_label = "'{{}}'".format(raw_angle)
            else:
                angle_label = "{{:g}} graus".format(angle_deg)
            kind_label = "Superficie revolvida" if as_surface else "Revolucao"
            return {{
                "message": "{{}} de {{}} (eixo {{}}) aplicada a '{{}}'.".format(
                    kind_label, angle_label, axis_name, sketch.name
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "is_surface": as_surface,
            }}


        def _unique_sketch_name(design, base):
            # Gera um nome de sketch livre (base, base (1), base (2)...).
            existing = set()
            sketches = _root(design).sketches
            for i in range(sketches.count):
                existing.add(sketches.item(i).name)
            if base not in existing:
                return base
            n = 1
            while "{{}} ({{}})".format(base, n) in existing:
                n += 1
            return "{{}} ({{}})".format(base, n)


        def _unique_body_name(design, base):
            # Gera um nome de CORPO livre (base, base (1), ...). As primitivas
            # passam a nomear o BODY (nao so o sketch) para que shell/fillet/
            # pattern/etc. consigam referenciar por nome — bug do gate caixa+
            # tampa: 'name' nomeava so o sketch, o body ficava Body1/Body2 e a
            # referencia por nome dava fusion.body_not_found.
            existing = set()
            bodies = _root(design).bRepBodies
            for i in range(bodies.count):
                existing.add(bodies.item(i).name)
            if base not in existing:
                return base
            n = 1
            while "{{}} ({{}})".format(base, n) in existing:
                n += 1
            return "{{}} ({{}})".format(base, n)


        def _attach_stable_id(entity, value=None):
            # T4.2 (Fase 4): anexa um attribute TF.stable_id no body criado.
            # Sobrevive a recompute paramétrico E a rename pelo usuário —
            # o LLM pode referenciar o body por stable_id mesmo que o nome
            # mude entre edições. Retorna o UUID curto gerado, ou None se
            # a API rejeitar (best-effort).
            try:
                import uuid as _uuid
                sid = str(value) if value else _uuid.uuid4().hex[:12]
                entity.attributes.add("TF", "stable_id", sid)
                return sid
            except Exception:
                return None


        def _stable_id_of(entity):
            # T4.2: lê o attribute TF.stable_id de um body/feature. None se
            # ausente ou se a API não expor attributes (ex.: SurfaceBody em
            # versões antigas do Fusion).
            try:
                attr = entity.attributes.itemByName("TF", "stable_id")
                if attr is not None:
                    return attr.value
            except Exception:
                pass
            return None


        def _xyz_mm(value, design):
            # Extrai (x, y, z) em mm de uma lista origin_mm/center_mm; faltantes=0.
            if not isinstance(value, (list, tuple)):
                return (0.0, 0.0, 0.0)

            def _g(i):
                if len(value) <= i:
                    return 0.0
                return _eval_param(value[i], design, 0.0) or 0.0

            return (_g(0), _g(1), _g(2))


        def _translate_body(design, body, dx_cm, dy_cm, dz_cm):
            # Move um corpo por um vetor (cm). No-op se vetor zero — mantem
            # compat: primitiva sem origin/z NAO gera feature de move (zero
            # impacto nos planos existentes e nos corpos que devem ficar no lugar).
            if dx_cm == 0.0 and dy_cm == 0.0 and dz_cm == 0.0:
                return
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(dx_cm, dy_cm, dz_cm)
            moves = root.features.moveFeatures
            try:
                inp = moves.createInput(coll, transform)
                moves.add(inp)
            except (AttributeError, RuntimeError):
                inp = moves.createInput2(coll)
                inp.defineAsFreeMove(transform)
                moves.add(inp)


        def _body_dims_mm(body):
            # Read-back: dimensoes (bbox) do corpo em mm [x, y, z]. Alimenta o
            # verifier do loop (expected_dimensions_mm x medido). bbox ~0 sinaliza
            # corpo consumido (ex.: cut que comeu a peca).
            bb = body.boundingBox
            return [
                round((bb.maxPoint.x - bb.minPoint.x) * 10.0, 3),
                round((bb.maxPoint.y - bb.minPoint.y) * 10.0, 3),
                round((bb.maxPoint.z - bb.minPoint.z) * 10.0, 3),
            ]


        def _add_box(args):
            # Onda B: primitiva direta. Cria sketch interno + extrude num
            # unico step (corpo editavel na timeline, nao TemporaryBRep).
            design = _design()
            w = _eval_param(args.get("width_mm"), design, 0.0) or 0.0
            d = _eval_param(args.get("depth_mm"), design, 0.0) or 0.0
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            # Drift do trace placa (mt_019e46cf2726): o LLM manda as 3 medidas
            # numa lista unica ``dimensions_mm``/``size_mm``/``dimensions``
            # [w, d, h] em vez das chaves separadas. Resolve elemento a elemento
            # (cada um pode ser numero ou expressao parametrica).
            if w <= 0 and d <= 0 and h <= 0:
                dims = (
                    args.get("dimensions_mm")
                    or args.get("size_mm")
                    or args.get("dimensions")
                    or args.get("size")
                )
                if isinstance(dims, (list, tuple)) and len(dims) >= 3:
                    w = _eval_param(dims[0], design, 0.0) or 0.0
                    d = _eval_param(dims[1], design, 0.0) or 0.0
                    h = _eval_param(dims[2], design, 0.0) or 0.0
            if w <= 0 or d <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "width_mm, depth_mm e height_mm (ou dimensions_mm=[w,d,h]) "
                    "precisam ser positivos.",
                )
            root = _root(design)
            sketch = root.sketches.add(root.xYConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Box"))
            w_cm = w / 10.0
            d_cm = d / 10.0
            # Posicionamento: ``origin_mm`` trata o ponto como CANTO inferior
            # (modelo mental do LLM: origem no canto, furos referenciados a
            # partir dela); ``center_mm`` (ou ausencia) CENTRALIZA no ponto.
            origin = _eval_pair(args.get("origin_mm"), design)
            if origin is not None:
                ox_cm = origin[0] / 10.0
                oy_cm = origin[1] / 10.0
                p1 = adsk.core.Point3D.create(ox_cm, oy_cm, 0)
                p2 = adsk.core.Point3D.create(ox_cm + w_cm, oy_cm + d_cm, 0)
            else:
                center = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
                cx_cm = center[0] / 10.0
                cy_cm = center[1] / 10.0
                p1 = adsk.core.Point3D.create(cx_cm - w_cm / 2, cy_cm - d_cm / 2, 0)
                p2 = adsk.core.Point3D.create(cx_cm + w_cm / 2, cy_cm + d_cm / 2, 0)
            sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
            extrudes = root.features.extrudeFeatures
            inp = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h / 10.0))
            feat = extrudes.add(inp)
            body_name = sketch.name
            stable_id = None
            dims = [0.0, 0.0, 0.0]
            if feat.bodies.count > 0:
                body_name = _unique_body_name(design, str(args.get("name") or "Box"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
                _oz = _xyz_mm(args.get("origin_mm") or args.get("center_mm"), design)[2]
                _translate_body(design, feat.bodies.item(0), 0.0, 0.0, _oz / 10.0)
                dims = _body_dims_mm(feat.bodies.item(0))
            return {{
                "message": "Caixa {{}}x{{}}x{{}} mm criada (corpo '{{}}').".format(
                    w, d, h, body_name
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
            }}


        def _add_cylinder(args):
            # Onda B: cilindro = circulo + extrude.
            design = _design()
            diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm) e height_mm precisam ser positivos.",
                )
            center = _eval_pair(args.get("center_mm"), design) or (0.0, 0.0)
            root = _root(design)
            sketch = root.sketches.add(root.xYConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Cylinder"))
            center_pt = adsk.core.Point3D.create(
                center[0] / 10.0, center[1] / 10.0, 0
            )
            sketch.sketchCurves.sketchCircles.addByCenterRadius(
                center_pt, diameter_mm / 20.0
            )
            extrudes = root.features.extrudeFeatures
            inp = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h / 10.0))
            feat = extrudes.add(inp)
            body_name = sketch.name
            stable_id = None
            dims = [0.0, 0.0, 0.0]
            if feat.bodies.count > 0:
                body_name = _unique_body_name(design, str(args.get("name") or "Cylinder"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
                _oz = _xyz_mm(args.get("center_mm") or args.get("origin_mm"), design)[2]
                _translate_body(design, feat.bodies.item(0), 0.0, 0.0, _oz / 10.0)
                dims = _body_dims_mm(feat.bodies.item(0))
            return {{
                "message": "Cilindro o{{}}x{{}} mm criado (corpo '{{}}').".format(
                    diameter_mm, h, body_name
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
            }}


        def _add_sphere(args):
            # Onda B: esfera = semicirculo revolvido 360 graus.
            # Desenha um meio-perfil (linha diametral no eixo + arco) no
            # plano XZ e revolve em torno da linha diametral.
            design = _design()
            diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0:
                radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
                if radius_mm > 0:
                    diameter_mm = radius_mm * 2
            if diameter_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "diameter_mm (ou radius_mm) precisa ser positivo.",
                )
            r_cm = diameter_mm / 20.0
            root = _root(design)
            sketch = root.sketches.add(root.xZConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Sphere"))
            top = adsk.core.Point3D.create(0, r_cm, 0)
            bottom = adsk.core.Point3D.create(0, -r_cm, 0)
            # Linha diametral (eixo de revolucao) + arco semicircular ao lado +X.
            axis_line = sketch.sketchCurves.sketchLines.addByTwoPoints(bottom, top)
            sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
                adsk.core.Point3D.create(0, 0, 0), top, -math.pi
            )
            revolves = root.features.revolveFeatures
            inp = revolves.createInput(
                sketch.profiles.item(0),
                axis_line,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
            feat = revolves.add(inp)
            body_name = sketch.name
            stable_id = None
            dims = [0.0, 0.0, 0.0]
            if feat.bodies.count > 0:
                body_name = _unique_body_name(design, str(args.get("name") or "Sphere"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
                _ox, _oy, _oz = _xyz_mm(args.get("origin_mm") or args.get("center_mm"), design)
                _translate_body(design, feat.bodies.item(0), _ox / 10.0, _oy / 10.0, _oz / 10.0)
                dims = _body_dims_mm(feat.bodies.item(0))
            return {{
                "message": "Esfera o{{}} mm criada (corpo '{{}}').".format(
                    diameter_mm, body_name
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
            }}


        def _add_cone(args):
            # Onda B: cone/frustum = trapezio (ou triangulo) revolvido.
            # top_diameter_mm=0 => cone pontudo; >0 => frustum.
            design = _design()
            base_d = _eval_param(args.get("base_diameter_mm"), design, 0.0) or 0.0
            if base_d <= 0:
                base_r = _eval_param(args.get("base_radius_mm"), design, 0.0) or 0.0
                if base_r > 0:
                    base_d = base_r * 2
            top_d = _eval_param(args.get("top_diameter_mm"), design, 0.0) or 0.0
            h = _eval_param(args.get("height_mm"), design, 0.0) or 0.0
            if base_d <= 0 or h <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "base_diameter_mm e height_mm precisam ser positivos.",
                )
            base_r_cm = base_d / 20.0
            top_r_cm = top_d / 20.0
            h_cm = h / 10.0
            root = _root(design)
            sketch = root.sketches.add(root.xZConstructionPlane)
            sketch.name = _unique_sketch_name(design, str(args.get("name") or "Cone"))
            # Perfil no semiplano +X: (0,0) -> (base_r,0) -> (top_r,h) -> (0,h)
            # fechando de volta em (0,0). A aresta x=0 e o eixo de revolucao.
            pts = [
                adsk.core.Point3D.create(0, 0, 0),
                adsk.core.Point3D.create(base_r_cm, 0, 0),
                adsk.core.Point3D.create(max(top_r_cm, 0.0), h_cm, 0),
                adsk.core.Point3D.create(0, h_cm, 0),
            ]
            lines = sketch.sketchCurves.sketchLines
            axis_line = lines.addByTwoPoints(pts[3], pts[0])  # aresta x=0 = eixo
            lines.addByTwoPoints(pts[0], pts[1])
            lines.addByTwoPoints(pts[1], pts[2])
            lines.addByTwoPoints(pts[2], pts[3])
            revolves = root.features.revolveFeatures
            inp = revolves.createInput(
                sketch.profiles.item(0),
                axis_line,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            )
            inp.setAngleExtent(False, adsk.core.ValueInput.createByReal(2 * math.pi))
            feat = revolves.add(inp)
            body_name = sketch.name
            stable_id = None
            dims = [0.0, 0.0, 0.0]
            if feat.bodies.count > 0:
                body_name = _unique_body_name(design, str(args.get("name") or "Cone"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
                _ox, _oy, _oz = _xyz_mm(args.get("origin_mm") or args.get("center_mm"), design)
                _translate_body(design, feat.bodies.item(0), _ox / 10.0, _oy / 10.0, _oz / 10.0)
                dims = _body_dims_mm(feat.bodies.item(0))
            shape = "cone" if top_d <= 0 else "tronco de cone"
            return {{
                "message": "{{}} base o{{}} topo o{{}} altura {{}} mm criado ('{{}}').".format(
                    shape, base_d, top_d, h, body_name
                ),
                "sketch_name": sketch.name,
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
            }}


        def _fillet_edges(args):
            # Onda C: arredonda arestas de um body. edge_selector semantico
            # (all/top/bottom/vertical/horizontal). body_ref opcional.
            design = _design()
            radius_mm = _eval_param(args.get("radius_mm"), design, 0.0) or 0.0
            if radius_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "radius_mm precisa ser positivo.")
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            edge_warn = ""
            edge_ids = args.get("edge_ids") or args.get("edge_indices")
            if edge_ids:
                selector = "edge_ids"
                edges = _edges_by_ids(body, edge_ids)
            else:
                selector = args.get("edge_selector") or args.get("edges")
                if selector is None:
                    # Era o fallback silencioso: o planner mandava a intencao de
                    # aresta numa chave nao reconhecida (ex.: edge_ids_from_
                    # previous_query com texto livre) e caiamos mudo em "all" —
                    # filetando ate o furo. Agora avisamos alto no trace.
                    _recognized = {{
                        "radius_mm", "distance_mm", "edge_ids", "edge_indices",
                        "edge_selector", "edges", "body_ref", "body", "body_name",
                    }}
                    _unknown = [
                        k for k in args
                        if k not in _recognized
                        and ("edge" in k.lower() or "selector" in k.lower())
                    ]
                    if _unknown:
                        edge_warn = (
                            " [WARN: args de aresta nao reconhecidos "
                            + str(sorted(_unknown))
                            + " ignorados; apliquei em TODAS as arestas - selecao"
                            + " pode estar imprecisa. Use edge_selector=all|top|"
                            + "bottom|vertical|horizontal ou edge_ids=[i,j] de"
                            + " query_geometry]"
                        )
                    selector = "all"
                edges = _select_edges(body, selector)
            if edges.count == 0:
                raise ToolError(
                    "fusion.no_edges",
                    "Nenhuma aresta correspondeu ao selector '{{}}'.".format(selector),
                )
            fillets = _root(design).features.filletFeatures
            inp = fillets.createInput()
            inp.addConstantRadiusEdgeSet(
                edges, _param_value_input(args.get("radius_mm"), design), True
            )
            fillets.add(inp)
            return {{
                "message": "Fillet r={{}}mm em {{}} aresta(s) ({{}}) de '{{}}'.{{}}".format(
                    radius_mm, edges.count, selector, body.name, edge_warn
                ),
                "body_name": body.name,
                "dimensions_mm": _body_dims_mm(body),
            }}


        def _chamfer_edges(args):
            # Onda C: chanfra arestas. Mesmo padrao de selector do fillet.
            design = _design()
            distance_mm = _eval_param(args.get("distance_mm"), design, 0.0) or 0.0
            if distance_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "distance_mm precisa ser positivo.")
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            edge_warn = ""
            edge_ids = args.get("edge_ids") or args.get("edge_indices")
            if edge_ids:
                selector = "edge_ids"
                edges = _edges_by_ids(body, edge_ids)
            else:
                selector = args.get("edge_selector") or args.get("edges")
                if selector is None:
                    # Era o fallback silencioso: o planner mandava a intencao de
                    # aresta numa chave nao reconhecida (ex.: edge_ids_from_
                    # previous_query com texto livre) e caiamos mudo em "all" —
                    # chanfrando ate o furo. Agora avisamos alto no trace.
                    _recognized = {{
                        "radius_mm", "distance_mm", "edge_ids", "edge_indices",
                        "edge_selector", "edges", "body_ref", "body", "body_name",
                    }}
                    _unknown = [
                        k for k in args
                        if k not in _recognized
                        and ("edge" in k.lower() or "selector" in k.lower())
                    ]
                    if _unknown:
                        edge_warn = (
                            " [WARN: args de aresta nao reconhecidos "
                            + str(sorted(_unknown))
                            + " ignorados; apliquei em TODAS as arestas - selecao"
                            + " pode estar imprecisa. Use edge_selector=all|top|"
                            + "bottom|vertical|horizontal ou edge_ids=[i,j] de"
                            + " query_geometry]"
                        )
                    selector = "all"
                edges = _select_edges(body, selector)
            if edges.count == 0:
                raise ToolError(
                    "fusion.no_edges",
                    "Nenhuma aresta correspondeu ao selector '{{}}'.".format(selector),
                )
            chamfers = _root(design).features.chamferFeatures
            dist_vi = _param_value_input(args.get("distance_mm"), design)
            # G5: a API de chamfer mudou entre versoes. Tenta a forma antiga
            # (createInput + setToEqualDistance); se nao existir, usa a nova
            # (createInput2 + chamferEdgeSets).
            try:
                inp = chamfers.createInput(edges, True)
                inp.setToEqualDistance(dist_vi)
                chamfers.add(inp)
            except (AttributeError, RuntimeError):
                inp = chamfers.createInput2()
                inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, dist_vi, True)
                chamfers.add(inp)
            return {{
                "message": "Chanfro d={{}}mm em {{}} aresta(s) ({{}}) de '{{}}'.{{}}".format(
                    distance_mm, edges.count, selector, body.name, edge_warn
                ),
                "body_name": body.name,
                "dimensions_mm": _body_dims_mm(body),
            }}


        def _shell_body(args):
            # Onda C: oca um body. open_faces semantico (top/bottom/none).
            # none => casca totalmente fechada (passa o body, nao faces).
            design = _design()
            thickness_mm = _eval_param(args.get("thickness_mm"), design, 0.0) or 0.0
            if thickness_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "thickness_mm precisa ser positivo.")
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            # Schema drift (teste bola): o LLM manda `faces` em vez de
            # `open_faces`. "all"/"none" => casca fechada (sem face aberta;
            # abrir "todas" deletaria o corpo, entao tratamos como fechada).
            face_ids = args.get("face_ids") or args.get("face_indices")
            if face_ids:
                open_sel = "face_ids"
                faces = _faces_by_ids(body, face_ids)
            else:
                open_sel = str(
                    args.get("open_faces") or args.get("faces") or "top"
                ).lower()
                if open_sel == "all":
                    open_sel = "none"
                faces = _select_faces(body, open_sel)
            coll = adsk.core.ObjectCollection.create()
            if faces.count > 0:
                for i in range(faces.count):
                    coll.add(faces.item(i))
            else:
                # Sem faces abertas (none, ou nao achou planar) => oca fechado.
                coll.add(body)
            shells = _root(design).features.shellFeatures
            inp = shells.createInput(coll, False)
            inp.insideThickness = _param_value_input(args.get("thickness_mm"), design)
            shells.add(inp)
            return {{
                "message": "Shell t={{}}mm (open={{}}) em '{{}}'.".format(
                    thickness_mm, open_sel, body.name
                ),
                "body_name": body.name,
                "dimensions_mm": _body_dims_mm(body),
            }}


        def _profile_for_circle(sketch, radius_cm):
            # Bug do teste real da placa (mt_019e46e06f3b): ao criar um sketch
            # SOBRE uma face existente, o Fusion inclui o contorno da face no
            # sketch, entao desenhar um circulo gera DOIS profiles: o disco
            # central e o anel (face menos o circulo). Pegar profiles.item(0)
            # pode pegar o ANEL -> o CUT remove tudo menos o miolo, consumindo
            # a peca e deixando so o plug cilindrico. Selecionamos o profile
            # cuja area bate com a do circulo (pi*r^2). Fallback: menor area
            # (o disco e sempre menor que o anel) e por fim item(0).
            target = math.pi * radius_cm * radius_cm
            best = None
            best_err = None
            for i in range(sketch.profiles.count):
                prof = sketch.profiles.item(i)
                try:
                    area = prof.areaProperties(
                        adsk.fusion.CalculationAccuracy.LowCalculationAccuracy
                    ).area
                except Exception:
                    try:
                        area = prof.areaProperties().area
                    except Exception:
                        area = None
                if area is None:
                    continue
                err = abs(area - target)
                if best_err is None or err < best_err:
                    best_err = err
                    best = prof
            if best is not None:
                return best
            return sketch.profiles.item(0)


        def _resolve_profile_selection(sketch, args, design):
            # Selecao explicita de profile para extrude/revolve/sweep. Sem isto
            # caia sempre em sketch.profiles.item(0) (bug "cut apaga a peca",
            # trace real m3d_plan_2f7aeff0): num sketch com varios profiles
            # (ex.: retangulo + circulo coplanares) item(0) pode ser a peca toda
            # e um operation=cut a consome. Suporta profile_index (direto) e
            # profile_diameter_mm (area do circulo, reusando _profile_for_circle).
            # Sem seletor mantem o comportamento legado (item(0)).
            count = sketch.profiles.count
            idx = args.get("profile_index")
            if idx is not None:
                try:
                    i = int(idx)
                except Exception:
                    i = -1
                if 0 <= i < count:
                    return sketch.profiles.item(i)
            diam = _eval_param(args.get("profile_diameter_mm"), design, 0.0) or 0.0
            if diam > 0:
                return _profile_for_circle(sketch, diam / 20.0)
            return sketch.profiles.item(0)


        def _open_profile_from_sketch(design, sketch, args):
            # T5.1b fix (gate m3d_plan_cd836aec): o objeto Sketch da API do
            # Fusion NAO expoe `.openProfiles` (AttributeError no Fusion real).
            # O caminho correto para um perfil ABERTO e
            # Component.createOpenProfile(sketchEntity, chainCurves=True), que
            # segue a cadeia de curvas conectadas a partir de uma curva-semente.
            # Retorna um Profile aberto valido para extrude/revolve/sweep em
            # modo superficie (isSolid=False).
            curves = sketch.sketchCurves
            if curves.count == 0:
                return None
            idx_raw = args.get("open_profile_index")
            try:
                i = int(idx_raw) if idx_raw is not None else 0
            except Exception:
                i = 0
            if not (0 <= i < curves.count):
                i = 0
            seed = curves.item(i)
            try:
                return _root(design).createOpenProfile(seed, True)
            except Exception:
                # Algumas versoes aceitam so 1 arg (chainCurves default True).
                return _root(design).createOpenProfile(seed)


        def _profile_or_open(sketch, args, design, as_surface):
            # T5.1b (Fase 5): em modo superficie aceita openProfile (curva
            # aberta) como alternativa ao profile fechado — permite extrudar/
            # varrer/loftar uma linha ou spline para gerar uma "lasca" NURBS.
            # Prefere SEMPRE profile fechado quando disponivel; so cai em
            # openProfile se o sketch nao tem nenhum profile fechado E o
            # chamador esta em modo surface (extrude/revolve/sweep/loft com
            # as_surface=true). Sem o flag, mantem comportamento legado.
            if sketch.profiles.count > 0:
                return _resolve_profile_selection(sketch, args, design)
            if as_surface:
                open_prof = _open_profile_from_sketch(design, sketch, args)
                if open_prof is not None:
                    return open_prof
            raise ToolError(
                "fusion.no_profile",
                "Sketch '{{}}' sem profile fechado{{}}.".format(
                    sketch.name,
                    " nem curvas p/ openProfile (precisa de geometria)"
                    if as_surface
                    else "",
                ),
            )


        def _collect_edges_for_patch(design, edge_ids, body_ref):
            # T5.1b (Fase 5): monta um ObjectCollection<BRepEdge> para o
            # boundary de patch/extend/trim. edge_ids referem-se ao corpo
            # body_ref (ou primeiro body se omitido), no mesmo esquema do
            # query_geometry (indice estavel dentro do body).
            if not isinstance(edge_ids, list) or len(edge_ids) == 0:
                raise ToolError(
                    "fusion.invalid_arg",
                    "edge_ids precisa ser lista nao-vazia de inteiros.",
                )
            body = _find_body(design, body_ref)
            edge_count = body.edges.count
            coll = adsk.core.ObjectCollection.create()
            for raw in edge_ids:
                try:
                    i = int(raw)
                except Exception:
                    raise ToolError(
                        "fusion.invalid_arg",
                        "edge_id '{{}}' nao eh inteiro.".format(raw),
                    )
                if not (0 <= i < edge_count):
                    raise ToolError(
                        "fusion.invalid_arg",
                        "edge_id {{}} fora do intervalo [0,{{}}) do body '{{}}'.".format(
                            i, edge_count, body.name
                        ),
                    )
                coll.add(body.edges.item(i))
            return coll


        def _create_surface_patch(args):
            # T5.1b (Fase 5): cria uma SurfaceBody preenchendo um boundary
            # fechado. Aceita boundary via sketch (primeiro profile fechado do
            # sketch) OU via edge_ids (arestas livres de um body resolvido,
            # tipico apos sweep/extrude as_surface=true que deixa aberturas).
            # Bridge para a peca-exemplo do gate da Fase 5: as 2 tampas da
            # carenagem entram via patch sobre as arestas livres da casca.
            design = _design()
            sketch_ref = args.get("sketch") or args.get("boundary_sketch")
            edge_ids = args.get("edge_ids") or args.get("boundary_edge_ids")
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])

            if sketch_ref:
                sketch = _find_sketch(design, sketch_ref)
                if sketch.profiles.count == 0:
                    raise ToolError(
                        "fusion.no_profile",
                        "Sketch '{{}}' sem profile fechado para patch.".format(sketch.name),
                    )
                boundary = sketch.profiles.item(0)
                source_label = "sketch '{{}}'".format(sketch_ref)
            elif edge_ids:
                body_ref = (
                    args.get("body_ref")
                    or args.get("body")
                    or args.get("body_name")
                )
                boundary = _collect_edges_for_patch(design, edge_ids, body_ref)
                source_label = "{{}} aresta(s)".format(len(edge_ids))
            else:
                raise ToolError(
                    "fusion.invalid_arg",
                    "create_surface_patch precisa de 'sketch' OU 'edge_ids' (+ body_ref).",
                )

            patches = _root(design).features.patchFeatures
            inp = patches.createInput(boundary, op)
            feat = patches.add(inp)
            body_name = None
            if feat.bodies.count > 0:
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or "Patch"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
            else:
                stable_id = None
            dims = (
                _body_dims_mm(feat.bodies.item(0))
                if feat.bodies.count > 0
                else [0.0, 0.0, 0.0]
            )
            area_mm2 = 0.0
            if feat.bodies.count > 0:
                try:
                    area_mm2 = round(feat.bodies.item(0).physicalProperties.area * 100.0, 2)
                except Exception:
                    area_mm2 = 0.0
            return {{
                "message": "Patch de superficie criado ({{}}).".format(source_label),
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "surface_area_mm2": area_mm2,
                "is_surface": True,
            }}


        def _collect_surface_bodies(design, refs):
            # T5.2 (Fase 5): resolve uma lista de refs (nomes/indices) em um
            # ObjectCollection<BRepBody>. Aceita SurfaceBody E Body solido
            # (stitch/thicken podem operar em ambos em algumas variantes da API).
            # Aliases de entrada: ref unica vira lista de 1; itens podem ser
            # string (nome ou indice serializado) ou int (indice direto).
            if isinstance(refs, (str, int)):
                refs = [refs]
            if not isinstance(refs, list) or len(refs) == 0:
                raise ToolError(
                    "fusion.invalid_arg",
                    "surface_refs precisa ser lista nao-vazia (nomes ou indices).",
                )
            bodies = _root(design).bRepBodies
            if bodies.count == 0:
                raise ToolError("fusion.no_body", "Nenhum corpo na cena (precisa de SurfaceBody).")
            coll = adsk.core.ObjectCollection.create()
            available = [bodies.item(i).name for i in range(bodies.count)]
            for raw in refs:
                target = None
                ref_str = str(raw)
                for i in range(bodies.count):
                    if bodies.item(i).name == ref_str:
                        target = bodies.item(i)
                        break
                if target is None:
                    try:
                        idx = int(ref_str)
                        if 0 <= idx < bodies.count:
                            target = bodies.item(idx)
                    except (TypeError, ValueError):
                        pass
                if target is None:
                    raise ToolError(
                        "fusion.body_not_found",
                        "Surface/body nao encontrado: {{}}. Disponiveis: {{}}".format(
                            ref_str, available
                        ),
                    )
                coll.add(target)
            return coll


        def _thicken_surface(args):
            # T5.2d (Fase 5): espessa SurfaceBody(ies) gerando BRepBody solido.
            # Eh a PONTE surface->solid da peca-exemplo do gate (carenagem).
            # API: ThickenFeatures.createInput(coll, thickness, isSymmetric,
            # operation, isChainSelection). thickness em cm via ValueInput;
            # parametrico (createByString) quando o arg referencia userParameter.
            design = _design()
            refs = (
                args.get("surface_refs")
                or args.get("surfaces")
                or args.get("surface_ref")
                or args.get("body_refs")
                or args.get("bodies")
            )
            surfaces = _collect_surface_bodies(design, refs)
            thickness_mm = _eval_param(args.get("thickness_mm"), design, 0.0) or 0.0
            if thickness_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "thickness_mm precisa ser positivo.",
                )
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])
            is_symmetric = bool(args.get("is_symmetric") or args.get("symmetric"))
            chain_raw = args.get("chain")
            is_chain = True if chain_raw is None else bool(chain_raw)
            thicken = _root(design).features.thickenFeatures
            thickness_vi = _param_value_input(args.get("thickness_mm"), design)
            inp = thicken.createInput(surfaces, thickness_vi, is_symmetric, op, is_chain)
            feat = thicken.add(inp)
            body_name = None
            if feat.bodies.count > 0:
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or "Thickened"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
            else:
                stable_id = None
            dims = (
                _body_dims_mm(feat.bodies.item(0))
                if feat.bodies.count > 0
                else [0.0, 0.0, 0.0]
            )
            return {{
                "message": "Superficie espessada em {{}} mm ({{}} face(s)){{}}.".format(
                    thickness_mm,
                    surfaces.count,
                    " [simetrico]" if is_symmetric else "",
                ),
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "is_surface": False,
            }}


        def _stitch_surfaces(args):
            # T5.2e (Fase 5): costura 2+ SurfaceBody por arestas livres
            # adjacentes. Resultado pode ser SurfaceBody (se costura nao fecha)
            # OU BRepBody solido (se fecha volume) — Fusion decide. is_surface
            # no output reflete o que saiu, util pro verifier saber se pode
            # ja passar pro fillet/export ou se precisa de thicken antes.
            design = _design()
            refs = (
                args.get("surface_refs")
                or args.get("surfaces")
                or args.get("body_refs")
                or args.get("bodies")
            )
            surfaces = _collect_surface_bodies(design, refs)
            if surfaces.count < 2:
                raise ToolError(
                    "fusion.invalid_arg",
                    "stitch_surfaces precisa de >= 2 superficies (recebido: {{}}).".format(
                        surfaces.count
                    ),
                )
            tolerance_mm = _eval_param(args.get("tolerance_mm"), design, 0.01)
            if tolerance_mm is None or tolerance_mm <= 0:
                tolerance_mm = 0.01
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])
            stitches = _root(design).features.stitchFeatures
            tolerance_vi = adsk.core.ValueInput.createByReal(float(tolerance_mm) / 10.0)
            inp = stitches.createInput(surfaces, tolerance_vi, op)
            feat = stitches.add(inp)
            body_name = None
            is_surface_result = True
            if feat.bodies.count > 0:
                first = feat.bodies.item(0)
                try:
                    is_surface_result = not bool(first.isSolid)
                except Exception:
                    is_surface_result = True
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or "Stitched"))
                first.name = body_name
                stable_id = _attach_stable_id(first)
            else:
                stable_id = None
            dims = (
                _body_dims_mm(feat.bodies.item(0))
                if feat.bodies.count > 0
                else [0.0, 0.0, 0.0]
            )
            area_mm2 = 0.0
            if feat.bodies.count > 0:
                try:
                    area_mm2 = round(feat.bodies.item(0).physicalProperties.area * 100.0, 2)
                except Exception:
                    area_mm2 = 0.0
            return {{
                "message": "Stitch de {{}} superficies (tol={{}}mm){{}}.".format(
                    surfaces.count,
                    tolerance_mm,
                    " - resultado solido" if not is_surface_result else "",
                ),
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "surface_area_mm2": area_mm2,
                "is_surface": is_surface_result,
            }}


        def _trim_surface(args):
            # T5.2a (Fase 5): apara SurfaceBody com uma ferramenta (sketch
            # curve, outra superficie ou face). API: trimFeatures.createInput
            # (trimmingTool, surfaceToTrim) — escolhe célula a manter por
            # criterio keep ("largest" default por area). Versoes diferentes
            # do Fusion expõem createInput vs createInput2 — tentamos a
            # forma de 2 args primeiro.
            design = _design()
            surface_ref = (
                args.get("surface_ref")
                or args.get("surface")
                or args.get("body_ref")
                or args.get("body")
            )
            tool_ref = (
                args.get("trim_tool_ref")
                or args.get("trim_tool")
                or args.get("tool_ref")
                or args.get("trimming_tool")
            )
            if not surface_ref or not tool_ref:
                raise ToolError(
                    "fusion.invalid_arg",
                    "trim_surface precisa de surface_ref + trim_tool_ref.",
                )
            surface_body = _find_body(design, surface_ref)
            keep = str(args.get("keep") or "largest").lower()
            # tool pode ser body ou sketch — tentamos sketch primeiro pra
            # pegar a curva (mais comum em trim de superficie).
            tool_entity = None
            try:
                tool_entity = _find_sketch(design, tool_ref)
            except Exception:
                tool_entity = None
            if tool_entity is None:
                tool_entity = _find_body(design, tool_ref)
            trims = _root(design).features.trimFeatures
            # Fix gate (probe extend_trim): TrimFeatures.createInput aceita
            # APENAS a trimTool (1 arg); a surface a aparar e as celulas vem
            # do TrimFeatureInput. Selecionamos as celulas a remover por area
            # (keep=largest mantem a maior, remove as outras) via isRemoved.
            inp = trims.createInput(tool_entity)
            removed = 0
            try:
                cells = inp.bRepCells
                if cells is not None and cells.count > 1:
                    best_i, best_a = 0, -1.0
                    areas = []
                    for ci in range(cells.count):
                        try:
                            a = cells.item(ci).cellSurface.area
                        except Exception:
                            a = 0.0
                        areas.append(a)
                        if a > best_a:
                            best_a, best_i = a, ci
                    for ci in range(cells.count):
                        try:
                            cells.item(ci).isRemoved = ci != best_i
                            if ci != best_i:
                                removed += 1
                        except Exception:
                            pass
            except Exception:
                pass
            feat = trims.add(inp)
            body_name = None
            if feat.bodies.count > 0:
                target = feat.bodies.item(0)
                if keep == "largest" and feat.bodies.count > 1:
                    best_area = -1.0
                    for bi in range(feat.bodies.count):
                        try:
                            area = feat.bodies.item(bi).physicalProperties.area
                        except Exception:
                            area = 0.0
                        if area > best_area:
                            best_area = area
                            target = feat.bodies.item(bi)
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or "Trimmed"))
                target.name = body_name
                stable_id = _attach_stable_id(target)
            else:
                stable_id = None
            dims = (
                _body_dims_mm(feat.bodies.item(0))
                if feat.bodies.count > 0
                else [0.0, 0.0, 0.0]
            )
            return {{
                "message": "Trim de superficie aplicado (keep={{}}).".format(keep),
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "is_surface": True,
            }}


        def _extend_surface(args):
            # T5.2b (Fase 5): estende SurfaceBody ao longo de arestas livres.
            # API: extendFeatures.createInput(edges, ValueInput distance,
            # SurfaceExtendType). edge_ids referem-se ao body_ref (default
            # primeiro body); use selector "free_edges" via query_geometry
            # para descobrir os indices.
            design = _design()
            edge_ids = args.get("edge_ids") or args.get("edges")
            distance_mm = _eval_param(args.get("distance_mm"), design, 0.0) or 0.0
            if distance_mm <= 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "distance_mm precisa ser positivo.",
                )
            extend_type_name = str(args.get("extend_type") or "natural").lower()
            extend_type_map = {{
                "natural": adsk.fusion.SurfaceExtendTypes.NaturalSurfaceExtendType,
                "perpendicular": adsk.fusion.SurfaceExtendTypes.PerpendicularSurfaceExtendType,
                "tangent": adsk.fusion.SurfaceExtendTypes.TangentSurfaceExtendType,
            }}
            extend_type = extend_type_map.get(
                extend_type_name, extend_type_map["natural"]
            )
            body_ref = args.get("body_ref") or args.get("body") or args.get("body_name")
            if not edge_ids:
                raise ToolError(
                    "fusion.invalid_arg",
                    "extend_surface precisa de edge_ids (use query_geometry com selector free_edges).",
                )
            edges = _collect_edges_for_patch(design, edge_ids, body_ref)
            extends = _root(design).features.extendFeatures
            distance_vi = _param_value_input(args.get("distance_mm"), design)
            inp = extends.createInput(edges, distance_vi, extend_type)
            feat = extends.add(inp)
            return {{
                "message": "Superficie estendida {{}} mm ({{}} aresta(s), tipo={{}}).".format(
                    distance_mm, edges.count, extend_type_name
                ),
                "feature_id": feat.entityToken if hasattr(feat, "entityToken") else None,
                "is_surface": True,
            }}


        def _offset_surface(args):
            # T5.2c (Fase 5): cria SurfaceBody paralela a face(s)/superficie(s).
            # API: offsetFeatures.createInput(inputSurfaces, ValueInput distance,
            # FeatureOperation). Aceita lista de faces ou SurfaceBody inteiro.
            design = _design()
            distance_mm = _eval_param(args.get("distance_mm"), design, 0.0) or 0.0
            if distance_mm == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "distance_mm precisa ser diferente de zero.",
                )
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])
            # Resolucao: se face_ids veio, monta ObjectCollection<BRepFace>
            # usando body_ref; senao usa surface_refs (collection de bodies).
            face_ids = args.get("face_ids") or args.get("faces")
            surface_refs = args.get("surface_refs") or args.get("surfaces")
            inputs = None
            source_label = ""
            if face_ids:
                body_ref = args.get("body_ref") or args.get("body") or args.get("body_name")
                body = _find_body(design, body_ref)
                inputs = adsk.core.ObjectCollection.create()
                face_count = body.faces.count
                for raw in face_ids:
                    try:
                        i = int(raw)
                    except Exception:
                        raise ToolError(
                            "fusion.invalid_arg",
                            "face_id '{{}}' nao eh inteiro.".format(raw),
                        )
                    if 0 <= i < face_count:
                        inputs.add(body.faces.item(i))
                source_label = "{{}} face(s)".format(inputs.count)
            elif surface_refs:
                inputs = _collect_surface_bodies(design, surface_refs)
                source_label = "{{}} superficie(s)".format(inputs.count)
            else:
                raise ToolError(
                    "fusion.invalid_arg",
                    "offset_surface precisa de face_ids+body_ref OU surface_refs.",
                )
            offsets = _root(design).features.offsetFeatures
            distance_vi = _param_value_input(args.get("distance_mm"), design)
            inp = offsets.createInput(inputs, distance_vi, op)
            feat = offsets.add(inp)
            body_name = None
            if feat.bodies.count > 0:
                explicit = (
                    args.get("name")
                    or args.get("result_name")
                    or args.get("body_name")
                    or args.get("result")
                )
                body_name = _unique_body_name(design, str(explicit or "Offset"))
                feat.bodies.item(0).name = body_name
                stable_id = _attach_stable_id(feat.bodies.item(0))
            else:
                stable_id = None
            dims = (
                _body_dims_mm(feat.bodies.item(0))
                if feat.bodies.count > 0
                else [0.0, 0.0, 0.0]
            )
            return {{
                "message": "Offset de {{}} mm aplicado ({{}}).".format(
                    distance_mm, source_label
                ),
                "body_name": body_name,
                "stable_id": stable_id,
                "dimensions_mm": dims,
                "is_surface": True,
            }}


        def _unstitch_surface(args):
            # T5.2f (Fase 5): quebra body/SurfaceBody em superficies individuais
            # por face — inverso do stitch. Util para reparar trecho especifico
            # (unstitch -> patch novo -> stitch). API:
            # unstitchFeatures.add(faces, isChainSelection, isSplitConnected).
            design = _design()
            face_ids = args.get("face_ids") or args.get("faces")
            surface_ref = (
                args.get("surface_ref")
                or args.get("body_ref")
                or args.get("body")
                or args.get("body_name")
            )
            faces_coll = adsk.core.ObjectCollection.create()
            if face_ids:
                body = _find_body(design, surface_ref)
                face_count = body.faces.count
                for raw in face_ids:
                    try:
                        i = int(raw)
                    except Exception:
                        raise ToolError(
                            "fusion.invalid_arg",
                            "face_id '{{}}' nao eh inteiro.".format(raw),
                        )
                    if 0 <= i < face_count:
                        faces_coll.add(body.faces.item(i))
            elif surface_ref:
                # Sem face_ids, unstitch o body inteiro (todas as faces).
                body = _find_body(design, surface_ref)
                for fi in range(body.faces.count):
                    faces_coll.add(body.faces.item(fi))
            else:
                raise ToolError(
                    "fusion.invalid_arg",
                    "unstitch_surface precisa de face_ids+body_ref OU surface_ref.",
                )
            is_chain = bool(args.get("is_chain_selection") or args.get("chain"))
            unstitches = _root(design).features.unstitchFeatures
            # Fix gate (probe edicao): UnstitchFeatures NAO tem createInput — o
            # .add() recebe os argumentos direto: add(faces, isChainSelection,
            # isSplitConnectedSurfaces). Tenta a forma completa e cai p/ formas
            # mais curtas em versoes diferentes do Fusion.
            try:
                feat = unstitches.add(faces_coll, is_chain, False)
            except Exception:
                try:
                    feat = unstitches.add(faces_coll, is_chain)
                except Exception:
                    feat = unstitches.add(faces_coll)
            return {{
                "message": "Unstitch aplicado ({{}} face(s), chain={{}}).".format(
                    faces_coll.count, is_chain
                ),
                "bodies_count": feat.bodies.count if hasattr(feat, "bodies") else 0,
                "is_surface": True,
            }}


        def _hole(args):
            # Onda C: furo via circulo + cut-extrude na face superior do body.
            # MVP pragmatico (nao usa holeFeatures, que exige point/face refs
            # precisos). position_mm=[x,y] no plano da face; depth_mm opcional
            # (sem depth = through-all). Limitacao documentada: assume face
            # superior planar. Para furos em outras faces, iteracao futura.
            design = _design()
            diameter_mm = _eval_param(args.get("diameter_mm"), design, 0.0) or 0.0
            if diameter_mm <= 0:
                raise ToolError("fusion.invalid_dimensions", "diameter_mm precisa ser positivo.")
            depth_mm = _eval_param(args.get("depth_mm"), design, 0.0) or 0.0
            pos = _eval_pair(args.get("position_mm"), design) or (0.0, 0.0)
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            top_faces = _select_faces(body, "top")
            if top_faces.count == 0:
                raise ToolError(
                    "fusion.no_face",
                    "Sem face superior planar para o furo.",
                )
            face = top_faces.item(0)
            root = _root(design)
            sketch = root.sketches.add(face)
            sketch.name = _unique_sketch_name(design, "Hole")
            world = adsk.core.Point3D.create(
                pos[0] / 10.0, pos[1] / 10.0, face.boundingBox.maxPoint.z
            )
            center = sketch.modelToSketchSpace(world)
            center.z = 0
            sketch.sketchCurves.sketchCircles.addByCenterRadius(center, diameter_mm / 20.0)
            extrudes = root.features.extrudeFeatures
            inp = extrudes.createInput(
                _profile_for_circle(sketch, diameter_mm / 20.0),
                adsk.fusion.FeatureOperations.CutFeatureOperation,
            )
            if depth_mm > 0:
                inp.setDistanceExtent(
                    False, adsk.core.ValueInput.createByReal(-depth_mm / 10.0)
                )
            else:
                inp.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
            extrudes.add(inp)
            # G3 hole v2: counterbore = recesso cilindrico mais largo e raso
            # no topo (para cabeca de parafuso). type=counterbore +
            # counterbore_diameter_mm + counterbore_depth_mm. countersink
            # (conico) fica para futuro (exige revolve/chamfer da borda).
            hole_type = str(args.get("type") or "simple").lower()
            cbore_note = ""
            if hole_type in ("counterbore", "cbore"):
                cb_d = _eval_param(args.get("counterbore_diameter_mm"), design, 0.0) or 0.0
                cb_depth = _eval_param(args.get("counterbore_depth_mm"), design, 0.0) or 0.0
                if cb_d > diameter_mm and cb_depth > 0:
                    cb_sketch = root.sketches.add(face)
                    cb_sketch.name = _unique_sketch_name(design, "Counterbore")
                    cb_center = cb_sketch.modelToSketchSpace(world)
                    cb_center.z = 0
                    cb_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                        cb_center, cb_d / 20.0
                    )
                    cb_inp = extrudes.createInput(
                        _profile_for_circle(cb_sketch, cb_d / 20.0),
                        adsk.fusion.FeatureOperations.CutFeatureOperation,
                    )
                    cb_inp.setDistanceExtent(
                        False, adsk.core.ValueInput.createByReal(-cb_depth / 10.0)
                    )
                    extrudes.add(cb_inp)
                    cbore_note = " + counterbore o{{}}x{{}}mm".format(cb_d, cb_depth)
                else:
                    cbore_note = " [WARN: counterbore exige counterbore_diameter_mm>diameter e _depth_mm>0]"
            return {{
                "message": "Furo o{{}}mm (prof={{}}) em '{{}}'{{}}.".format(
                    diameter_mm, depth_mm or "through", body.name, cbore_note
                ),
                "body_name": body.name,
                "dimensions_mm": _body_dims_mm(body),
            }}


        # ---- Onda D: replicacao e combinacao ----

        def _axis_from_name(design, axis_name):
            root = _root(design)
            return {{
                "x": root.xConstructionAxis,
                "y": root.yConstructionAxis,
                "z": root.zConstructionAxis,
            }}.get(str(axis_name or "x").lower(), root.xConstructionAxis)


        def _plane_from_name(design, plane_name):
            root = _root(design)
            return {{
                "xy": root.xYConstructionPlane,
                "yz": root.yZConstructionPlane,
                "xz": root.xZConstructionPlane,
            }}.get(str(plane_name or "xy").lower(), root.xYConstructionPlane)


        def _pattern_rectangular(args):
            # Onda D: replica um body em grade retangular ao longo de 2 eixos.
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            count_x = int(
                _eval_param(
                    args.get("count_x") or args.get("occurrences_x") or args.get("instances_x"),
                    design,
                    1.0,
                )
                or 1
            )
            count_y = int(
                _eval_param(
                    args.get("count_y") or args.get("occurrences_y") or args.get("instances_y"),
                    design,
                    1.0,
                )
                or 1
            )
            spacing_x = _eval_param(args.get("spacing_x_mm"), design, 0.0) or 0.0
            spacing_y = _eval_param(args.get("spacing_y_mm"), design, 0.0) or 0.0
            if count_x < 1 or count_y < 1:
                raise ToolError("fusion.invalid_dimensions", "count_x e count_y precisam ser >= 1.")
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            patterns = root.features.rectangularPatternFeatures
            dist_type = adsk.fusion.PatternDistanceType.SpacingPatternDistanceType
            inp = patterns.createInput(
                coll,
                _axis_from_name(design, args.get("axis_x") or "x"),
                adsk.core.ValueInput.createByString(str(count_x)),
                adsk.core.ValueInput.createByReal(spacing_x / 10.0),
                dist_type,
            )
            inp.setDirectionTwo(
                _axis_from_name(design, args.get("axis_y") or "y"),
                adsk.core.ValueInput.createByString(str(count_y)),
                adsk.core.ValueInput.createByReal(spacing_y / 10.0),
            )
            patterns.add(inp)
            return {{
                "message": "Padrao retangular {{}}x{{}} de '{{}}'.".format(
                    count_x, count_y, body.name
                ),
                "body_name": body.name,
            }}


        def _pattern_circular(args):
            # Onda D: replica um body em torno de um eixo.
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            # Schema drift (teste bola): o LLM manda occurrences/quantity em
            # vez de count, e angle_deg em vez de total_angle_deg. Sem os
            # aliases, count defaultava pra 1 (pattern virava no-op).
            count = int(
                _eval_param(
                    args.get("count")
                    or args.get("occurrences")
                    or args.get("quantity")
                    or args.get("instances"),
                    design,
                    1.0,
                )
                or 1
            )
            if count < 1:
                raise ToolError("fusion.invalid_dimensions", "count precisa ser >= 1.")
            total_angle = _eval_param(
                args.get("total_angle_deg") or args.get("angle_deg"), design, 360.0
            )
            if not total_angle:
                total_angle = 360.0
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            patterns = root.features.circularPatternFeatures
            inp = patterns.createInput(coll, _axis_from_name(design, args.get("axis") or "z"))
            inp.quantity = adsk.core.ValueInput.createByString(str(count))
            inp.totalAngle = adsk.core.ValueInput.createByString(
                "{{}} deg".format(total_angle)
            )
            inp.isSymmetric = False
            patterns.add(inp)
            return {{
                "message": "Padrao circular {{}}x ({{}} graus) de '{{}}'.".format(
                    count, total_angle, body.name
                ),
                "body_name": body.name,
            }}


        def _mirror_feature(args):
            # Onda D: espelha um body em torno de um plano construtivo.
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            plane = _plane_from_name(design, args.get("plane") or "xy")
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            mirrors = root.features.mirrorFeatures
            inp = mirrors.createInput(coll, plane)
            mirrors.add(inp)
            return {{
                "message": "Espelho de '{{}}' no plano {{}}.".format(
                    body.name, str(args.get("plane") or "xy")
                ),
                "body_name": body.name,
            }}


        def _combine_bodies(args):
            # Onda D (high_risk): boolean entre bodies existentes.
            # target_ref + tool_refs[] (nomes/indices) + operation.
            design = _design()
            target = _find_body(design, args.get("target_ref") or args.get("target"))
            tool_refs = args.get("tool_refs") or args.get("tools") or []
            if not isinstance(tool_refs, list) or not tool_refs:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "tool_refs precisa ser uma lista nao vazia de bodies.",
                )
            tools = adsk.core.ObjectCollection.create()
            for ref in tool_refs:
                tools.add(_find_body(design, ref))
            operation = str(args.get("operation") or "join").lower()
            op_map = {{
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            }}
            if operation not in op_map:
                raise ToolError(
                    "fusion.invalid_operation",
                    "operation deve ser join, cut ou intersect.",
                )
            combines = _root(design).features.combineFeatures
            inp = combines.createInput(target, tools)
            inp.operation = op_map[operation]
            combines.add(inp)
            try:
                dims = _body_dims_mm(target)
            except Exception:
                dims = [0.0, 0.0, 0.0]  # target consumido pelo boolean (cut/intersect)
            return {{
                "message": "Combine {{}} de {{}} body(ies) em '{{}}'.".format(
                    operation, tools.count, target.name
                ),
                "body_name": target.name,
                "dimensions_mm": dims,
            }}


        # ---- Onda E: sweeps avancados e construcao ----

        def _loft_profiles(args):
            # Onda E: loft entre 2+ profiles (sketches ordenados).
            design = _design()
            refs = args.get("profiles") or args.get("sketches") or []
            if not isinstance(refs, list) or len(refs) < 2:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "profiles precisa listar >= 2 sketches.",
                )
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])
            lofts = _root(design).features.loftFeatures
            inp = lofts.createInput(op)
            # T5.1a/T5.1b: as_surface=true → isSolid=False E permite que cada
            # section seja openProfile (curva aberta) alem de profile fechado.
            as_surface = bool(args.get("as_surface"))
            if as_surface:
                inp.isSolid = False
            for ref in refs:
                sk = _find_sketch(design, ref)
                if sk.profiles.count > 0:
                    section = sk.profiles.item(0)
                elif as_surface:
                    # T5.1b fix: Sketch nao tem .openProfiles; usar
                    # createOpenProfile (ver _open_profile_from_sketch).
                    section = _open_profile_from_sketch(design, sk, {{}})
                    if section is None:
                        raise ToolError(
                            "fusion.no_profile",
                            "Sketch '{{}}' sem profile fechado nem curvas.".format(ref),
                        )
                else:
                    raise ToolError(
                        "fusion.no_profile",
                        "Sketch '{{}}' sem profile fechado.".format(ref),
                    )
                inp.loftSections.add(section)
            feat = lofts.add(inp)
            dims = _body_dims_mm(feat.bodies.item(0)) if feat.bodies.count > 0 else [0.0, 0.0, 0.0]
            kind_label = "Loft de superficie" if as_surface else "Loft"
            return {{
                "message": "{{}} entre {{}} profiles.".format(kind_label, len(refs)),
                "dimensions_mm": dims,
                "is_surface": as_surface,
            }}


        def _sweep_profile(args):
            # Onda E: varre um profile ao longo de um caminho (sketch path).
            # T5.1b: as_surface=true aceita perfil aberto (gera lasca NURBS).
            design = _design()
            profile_sketch = _find_sketch(design, args.get("profile") or args.get("profile_sketch"))
            _as_surface_sweep = bool(args.get("as_surface"))
            if not _as_surface_sweep and profile_sketch.profiles.count == 0:
                raise ToolError("fusion.no_profile", "Profile sem perfil fechado.")
            path_sketch = _find_sketch(design, args.get("path") or args.get("path_sketch"))
            if path_sketch.sketchCurves.count == 0:
                raise ToolError("fusion.no_path", "Path sketch sem curvas.")
            operation = str(args.get("operation") or "new_body").lower()
            op_map = {{
                "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
            }}
            op = op_map.get(operation, op_map["new_body"])
            root = _root(design)
            path = root.features.createPath(path_sketch.sketchCurves.item(0))
            sweeps = root.features.sweepFeatures
            as_surface = _as_surface_sweep
            inp = sweeps.createInput(
                _profile_or_open(profile_sketch, args, design, as_surface), path, op
            )
            if as_surface:
                inp.isSolid = False
            feat = sweeps.add(inp)
            dims = _body_dims_mm(feat.bodies.item(0)) if feat.bodies.count > 0 else [0.0, 0.0, 0.0]
            kind_label = "Sweep de superficie" if as_surface else "Sweep"
            return {{
                "message": "{{}} do profile '{{}}' pelo path '{{}}'.".format(
                    kind_label, profile_sketch.name, path_sketch.name
                ),
                "dimensions_mm": dims,
                "is_surface": as_surface,
            }}


        def _add_construction_plane(args):
            # Onda E: plano construtivo por offset de um plano base.
            design = _design()
            offset_mm = _eval_param(args.get("offset_mm"), design, 0.0) or 0.0
            base_name = str(args.get("base") or "xy").lower()
            base = _plane_from_name(design, base_name)
            root = _root(design)
            planes = root.constructionPlanes
            inp = planes.createInput()
            inp.setByOffset(base, adsk.core.ValueInput.createByReal(offset_mm / 10.0))
            plane = planes.add(inp)
            name = str(args.get("name") or "")
            if name:
                plane.name = name
            return {{
                "message": "Plano construtivo offset {{}}mm de {{}}.".format(
                    offset_mm, base_name
                ),
                "plane_name": plane.name,
            }}


        def _add_spline(args):
            # Onda E: spline ajustada por pontos num sketch.
            design = _design()
            raw_points = args.get("points_mm") or args.get("points") or []
            if not isinstance(raw_points, list) or len(raw_points) < 2:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "points_mm precisa ter >= 2 pontos.",
                )
            sketch = _find_sketch(design, args.get("sketch"))
            coll = adsk.core.ObjectCollection.create()
            for raw in raw_points:
                pair = _eval_pair(raw, design)
                if pair is None:
                    raise ToolError("fusion.invalid_dimensions", "ponto invalido em points_mm.")
                coll.add(adsk.core.Point3D.create(pair[0] / 10.0, pair[1] / 10.0, 0))
            sketch.sketchCurves.sketchFittedSplines.add(coll)
            return {{
                "message": "Spline de {{}} pontos em '{{}}'.".format(
                    len(raw_points), sketch.name
                ),
                "sketch_name": sketch.name,
            }}


        # ---- Onda F: modificacao direta de bodies ----

        def _move_body(args):
            # Onda F + G3: translada E/OU rotaciona um body. Translacao via
            # translation_mm=[x,y,z]; rotacao via rotation_deg + axis (x/y/z ou
            # vetor [x,y,z]) em torno de center_mm (default = centro do bbox).
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            tx = ty = tz = 0.0
            raw = args.get("translation_mm")
            if isinstance(raw, (list, tuple)) and len(raw) >= 3:
                tx = _eval_param(raw[0], design, 0.0) or 0.0
                ty = _eval_param(raw[1], design, 0.0) or 0.0
                tz = _eval_param(raw[2], design, 0.0) or 0.0
            else:
                trans = _eval_pair(raw, design)
                if trans is not None:
                    tx, ty = trans
            rot_deg = _eval_param(args.get("rotation_deg"), design, 0.0) or 0.0
            axis_arg = args.get("axis")
            axis_map = {{"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}}
            if isinstance(axis_arg, (list, tuple)) and len(axis_arg) >= 3:
                ax = (float(axis_arg[0]), float(axis_arg[1]), float(axis_arg[2]))
                axis_label = "vec"
            else:
                axis_label = str(axis_arg or "z").lower()
                ax = axis_map.get(axis_label, (0.0, 0.0, 1.0))
            if tx == 0 and ty == 0 and tz == 0 and rot_deg == 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "Informe translation_mm e/ou rotation_deg nao-zero.",
                )
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            transform = adsk.core.Matrix3D.create()
            if rot_deg != 0:
                center = args.get("center_mm")
                if isinstance(center, (list, tuple)) and len(center) >= 3:
                    cx = (_eval_param(center[0], design, 0.0) or 0.0) / 10.0
                    cy = (_eval_param(center[1], design, 0.0) or 0.0) / 10.0
                    cz = (_eval_param(center[2], design, 0.0) or 0.0) / 10.0
                else:
                    bb = body.boundingBox
                    cx = (bb.minPoint.x + bb.maxPoint.x) / 2.0
                    cy = (bb.minPoint.y + bb.maxPoint.y) / 2.0
                    cz = (bb.minPoint.z + bb.maxPoint.z) / 2.0
                transform.setToRotation(
                    rot_deg * math.pi / 180.0,
                    adsk.core.Vector3D.create(ax[0], ax[1], ax[2]),
                    adsk.core.Point3D.create(cx, cy, cz),
                )
            if tx != 0 or ty != 0 or tz != 0:
                trans_m = adsk.core.Matrix3D.create()
                trans_m.translation = adsk.core.Vector3D.create(tx / 10.0, ty / 10.0, tz / 10.0)
                transform.transformBy(trans_m)
            moves = root.features.moveFeatures
            # G5: moveFeatures.createInput(entities, transform) foi deprecada
            # em favor de createInput2(entities)+defineAsFreeMove(transform).
            try:
                inp = moves.createInput(coll, transform)
                moves.add(inp)
            except (AttributeError, RuntimeError, TypeError):
                inp = moves.createInput2(coll)
                inp.defineAsFreeMove(transform)
                moves.add(inp)
            return {{
                "message": "Body '{{}}' movido t=({{}},{{}},{{}})mm rot={{}}deg/{{}}.".format(
                    body.name, tx, ty, tz, rot_deg, axis_label
                ),
                "body_name": body.name,
            }}


        def _scale_body(args):
            # Onda F: escala uniforme (factor) de um body em torno da origem.
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            factor = _eval_param(args.get("factor"), design, 0.0) or 0.0
            if factor <= 0:
                raise ToolError("fusion.invalid_dimensions", "factor precisa ser positivo.")
            root = _root(design)
            coll = adsk.core.ObjectCollection.create()
            coll.add(body)
            scales = root.features.scaleFeatures
            inp = scales.createInput(
                coll,
                root.originConstructionPoint,
                adsk.core.ValueInput.createByReal(factor),
            )
            scales.add(inp)
            return {{
                "message": "Body '{{}}' escalado x{{}}.".format(body.name, factor),
                "body_name": body.name,
            }}


        def _delete_body(args):
            # Onda F (destructive): remove um body. Exige aprovacao humana
            # (categoria destructive na policy).
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            name = body.name
            removes = _root(design).features.removeFeatures
            removes.add(body)
            return {{"message": "Body '{{}}' removido.".format(name)}}


        def _split_body(args):
            # G3: divide um body por um plano construtivo (xy/yz/xz) ou por
            # um plano de offset. Gera 2+ bodies.
            design = _design()
            body = _find_body(design, args.get("body_ref") or args.get("body") or args.get("body_name"))
            root = _root(design)
            offset_mm = _eval_param(args.get("offset_mm"), design)
            base_name = str(args.get("plane") or "xy").lower()
            if offset_mm is not None:
                planes = root.constructionPlanes
                pinp = planes.createInput()
                pinp.setByOffset(
                    _plane_from_name(design, base_name),
                    adsk.core.ValueInput.createByReal(offset_mm / 10.0),
                )
                splitting_tool = planes.add(pinp)
            else:
                splitting_tool = _plane_from_name(design, base_name)
            splits = root.features.splitBodyFeatures
            inp = splits.createInput(body, splitting_tool, True)
            splits.add(inp)
            return {{
                "message": "Body '{{}}' dividido pelo plano {{}}.".format(
                    body.name, base_name
                ),
                "body_name": body.name,
            }}


        def _query_geometry(args):
            # G2.2 (read-only): lista bodies/faces/arestas com indice estavel
            # + metadata, para o LLM mirar por face_ids/edge_ids depois em vez
            # de adivinhar selectors. Limita contagem para nao estourar payload.
            design = _design()
            root = _root(design)
            limit = int(_eval_param(args.get("limit"), design, 60.0) or 60)
            bodies_out = []
            for bi in range(root.bRepBodies.count):
                body = root.bRepBodies.item(bi)
                bbox = body.boundingBox
                faces_out = []
                for fi in range(min(body.faces.count, limit)):
                    f = body.faces.item(fi)
                    fbb = f.boundingBox
                    try:
                        stype = f.geometry.surfaceType
                        type_name = {{
                            adsk.core.SurfaceTypes.PlaneSurfaceType: "planar",
                            adsk.core.SurfaceTypes.CylinderSurfaceType: "cylindrical",
                            adsk.core.SurfaceTypes.ConeSurfaceType: "conical",
                            adsk.core.SurfaceTypes.SphereSurfaceType: "spherical",
                        }}.get(stype, "other")
                    except Exception:
                        type_name = "other"
                    try:
                        area_mm2 = f.area * 100.0
                    except Exception:
                        area_mm2 = 0.0
                    faces_out.append({{
                        "face_index": fi,
                        "type": type_name,
                        "area_mm2": round(area_mm2, 2),
                        "normal_axis": _face_normal_axis(f),
                        "center_mm": [
                            round((fbb.minPoint.x + fbb.maxPoint.x) * 5.0, 2),
                            round((fbb.minPoint.y + fbb.maxPoint.y) * 5.0, 2),
                            round((fbb.minPoint.z + fbb.maxPoint.z) * 5.0, 2),
                        ],
                    }})
                edges_out = []
                for ei in range(min(body.edges.count, limit)):
                    e = body.edges.item(ei)
                    try:
                        length_mm = e.length * 10.0
                    except Exception:
                        length_mm = 0.0
                    edges_out.append({{
                        "edge_index": ei,
                        "length_mm": round(length_mm, 2),
                    }})
                # T5.3a (Fase 5): expor is_solid/is_closed/surface_area_mm2 e
                # contagem de arestas livres para SurfaceBody. O LLM precisa
                # ver isso para decidir: stitch fechou? thicken pode rodar?
                # Sem isso o verifier de dimensoes nao detecta "stitch deixou
                # gap" — a peca-exemplo (carenagem) escorrega.
                try:
                    is_solid = bool(body.isSolid)
                except Exception:
                    is_solid = True
                try:
                    surface_area_mm2 = round(body.physicalProperties.area * 100.0, 2)
                except Exception:
                    surface_area_mm2 = 0.0
                free_edge_count = 0
                for ei2 in range(body.edges.count):
                    try:
                        if body.edges.item(ei2).faces.count <= 1:
                            free_edge_count += 1
                    except Exception:
                        pass
                # is_closed = body solido (fechado por definicao) OU superficie
                # sem arestas livres. Fix gate: um stitch que fecha volume vira
                # is_solid=true, mas a seam do revolve 360 pode contar 1 free
                # edge — sem o "is_solid or", o verifier teria falso-negativo de
                # is_closed e o loop "corrigiria" uma costura que ja funcionou.
                is_closed = bool(is_solid) or free_edge_count == 0
                bodies_out.append({{
                    "body_index": bi,
                    "name": body.name,
                    # T4.2: stable_id sobrevive a rename do usuario; o LLM
                    # deve preferi-lo a body_name em refs subsequentes.
                    "stable_id": _stable_id_of(body),
                    "dimensions_mm": [
                        round((bbox.maxPoint.x - bbox.minPoint.x) * 10.0, 2),
                        round((bbox.maxPoint.y - bbox.minPoint.y) * 10.0, 2),
                        round((bbox.maxPoint.z - bbox.minPoint.z) * 10.0, 2),
                    ],
                    "face_count": body.faces.count,
                    "edge_count": body.edges.count,
                    "free_edge_count": free_edge_count,
                    "is_solid": is_solid,
                    "is_closed": is_closed,
                    "surface_area_mm2": surface_area_mm2,
                    "faces": faces_out,
                    "edges": edges_out,
                }})
            return {{
                "message": "{{}} corpo(s) inspecionado(s).".format(len(bodies_out)),
                "bodies": bodies_out,
            }}


        def _query_timeline(args):
            # T3.1 (read-only): le a timeline (features, ordem, supressao) + os
            # user parameters atuais. Insumo da reconciliacao (T3.2/T3.3): o
            # planner ve o estado REAL antes de planejar uma edicao, mesmo que o
            # usuario tenha mexido a mao direto no Fusion.
            design = _design()
            limit = int(_eval_param(args.get("limit"), design, 200.0) or 200)
            features_out = []
            tl = design.timeline
            for i in range(min(tl.count, limit)):
                obj = tl.item(i)
                try:
                    ent = obj.entity
                except Exception:
                    ent = None
                try:
                    fname = ent.name if ent is not None else None
                except Exception:
                    fname = None
                try:
                    ftype = ent.objectType if ent is not None else None
                except Exception:
                    ftype = None
                try:
                    suppressed = bool(obj.isSuppressed)
                except Exception:
                    suppressed = False
                features_out.append({{
                    "index": i,
                    "name": fname,
                    "type": ftype,
                    "suppressed": suppressed,
                }})
            params_out = []
            ups = design.userParameters
            for pi in range(min(ups.count, limit)):
                p = ups.item(pi)
                try:
                    params_out.append({{
                        "name": p.name,
                        "expression": p.expression,
                        "unit": p.unit,
                    }})
                except Exception:
                    continue
            return {{
                "message": "Timeline: {{}} feature(s), {{}} parametro(s).".format(
                    tl.count, ups.count
                ),
                "timeline_count": tl.count,
                "timeline": features_out,
                "parameters": params_out,
            }}


        def _rollback_timeline(args):
            # T3.6: desfaz a ultima edicao deletando as features da timeline a
            # partir de target_count (a contagem capturada ANTES da edicao).
            # Deleta de tras pra frente p/ nao invalidar indices. Destrutivo;
            # acionado pelo usuario (botao undo), nunca planejado pelo LLM.
            design = _design()
            raw = args.get("target_count")
            try:
                target = int(raw)
            except (TypeError, ValueError):
                target = -1
            if target < 0:
                raise ToolError(
                    "fusion.invalid_dimensions",
                    "target_count (contagem da timeline antes da edicao) e obrigatorio.",
                )
            tl = design.timeline
            before = tl.count
            if target > before:
                target = before
            removed = 0
            errors = []
            for i in range(before - 1, target - 1, -1):
                obj = tl.item(i)
                done = False
                # TimelineObject.deleteMe() devolve BOOL (nem sempre levanta) — o
                # codigo antigo ignorava o retorno e contava como removido mesmo
                # quando falhava. Checa o bool E captura a excecao real do Fusion.
                try:
                    if obj.deleteMe():
                        done = True
                except Exception as exc:
                    errors.append("tl[{{}}].deleteMe: {{}}".format(i, exc))
                if not done:
                    # Fallback: deleta a feature/entidade subjacente.
                    try:
                        ent = obj.entity
                        if ent is not None and hasattr(ent, "deleteMe") and ent.deleteMe():
                            done = True
                    except Exception as exc:
                        errors.append("tl[{{}}].entity.deleteMe: {{}}".format(i, exc))
                if done:
                    removed += 1
            after = design.timeline.count
            if removed == 0 and target < before:
                # Nao reverteu nada quando deveria: falha ALTA (nao "completed"
                # silencioso) com o motivo real do Fusion p/ diagnostico/gate.
                raise ToolError(
                    "fusion.rollback_failed",
                    "Rollback nao removeu features (timeline segue em {{}}). {{}}".format(
                        after, " | ".join(errors[:6]) or "deleteMe sem efeito e sem excecao"
                    ),
                )
            msg = "Rollback: {{}}/{{}} feature(s) removida(s) (timeline {{}} -> {{}}).".format(
                removed, before - target, before, after
            )
            return {{
                "message": msg,
                "removed": removed,
                "timeline_count": after,
                "errors": errors[:12],
            }}


        def _set_parameter(args):
            # Fix #1: aceita dois formatos:
            # (a) singular legado:  name='X', expression='10mm', unit='mm'
            # (b) bulk emitido pelo LLM:  parameters dict mapping
            #     param_name -> value (ex: album_width_mm -> 210).
            #     A unidade e inferida do sufixo do nome (_mm/_cm/_deg) e o
            #     valor numerico vira ``expression`` como string.
            # Pegado via trace do bug porta-figurinhas WC2026. Comentarios
            # sem chaves literais porque este modulo inteiro e um f-string
            # template e qualquer ``X`` cru e interpretado como expressao.
            design = _design()

            def _infer_unit_from_expr(raw_expr):
                # Fix T4 gate: o LLM as vezes manda a unidade DENTRO da
                # expression (ex.: "270 deg", "5mm", "1.5 rad"). Quando o
                # nome do parametro nao tem sufixo (_deg/_mm/...) e nao ha
                # ``unit`` explicito, o fallback "mm" do _unit_for fazia
                # userParameters.add rejeitar "270 deg" com "Invalid
                # expression". Aqui detectamos a unidade no fim da string.
                if not isinstance(raw_expr, str):
                    return None
                stripped = raw_expr.strip().lower().replace(" ", "")
                for candidate in ("deg", "rad", "mm", "cm"):
                    if stripped.endswith(candidate):
                        return candidate
                return None

            def _unit_for(param_name, default_unit):
                lower_name = str(param_name).lower()
                if lower_name.endswith("_mm"):
                    return "mm"
                if lower_name.endswith("_cm"):
                    return "cm"
                if lower_name.endswith("_deg"):
                    return "deg"
                if lower_name.endswith("_rad"):
                    return "rad"
                return default_unit

            def _ensure_param(param_name, expression, unit, comment):
                if not param_name or not expression:
                    raise ToolError(
                        "fusion.invalid_parameter",
                        "name e expression são obrigatórios.",
                    )
                existing = design.userParameters.itemByName(param_name)
                if existing is not None:
                    existing.expression = expression
                else:
                    design.userParameters.add(
                        param_name,
                        adsk.core.ValueInput.createByString(expression),
                        unit,
                        comment,
                    )

            # Aliases observados em traces reais: ``parameters``,
            # ``parameters_mm``, ``params``. O LLM varia a chave conforme
            # o contexto da unidade. Sempre que vier dict bulk, processa.
            bulk = (
                args.get("parameters")
                or args.get("parameters_mm")
                or args.get("params")
            )
            if isinstance(bulk, dict) and bulk:
                default_unit = (
                    "mm" if args.get("parameters_mm") else str(args.get("unit") or "mm")
                )
                applied = []
                for raw_name, raw_value in bulk.items():
                    param_name = str(raw_name).strip()
                    expression = str(raw_value).strip()
                    unit = (
                        _infer_unit_from_expr(expression)
                        or _unit_for(param_name, default_unit)
                    )
                    _ensure_param(param_name, expression, unit, "")
                    applied.append(param_name)
                return {{
                    "message": "{{}} parâmetro(s) aplicado(s): {{}}.".format(
                        len(applied), ", ".join(applied)
                    ),
                    "applied": applied,
                }}

            # Fix #1.2: bulk implicito — LLM as vezes manda os parametros
            # DIRETO como kwargs no args raiz, sem wrapper ``parameters``.
            # Exemplo de input observado: cols=4, rows=3, sticker_width_mm=46.
            # Detectamos esse modo pela ausencia de ``name``/``expression``
            # singulares + presenca de >=2 chaves que parecem nomes de
            # parametro (valor numerico ou expressao string). Chaves
            # reservadas (notes, unit, comment) sao ignoradas.
            # NOTA: nao usar chaves literais em comentarios deste modulo;
            # ele e um f-string template e isso gera SyntaxError.
            singular_name = str(args.get("name") or "").strip()
            singular_expr = str(args.get("expression") or "").strip()
            if not singular_name and not singular_expr:
                _RESERVED_KEYS = {{
                    "notes",
                    "unit",
                    "comment",
                    "parameters",
                    "parameters_mm",
                    "params",
                }}
                implicit_bulk = {{
                    k: v
                    for k, v in args.items()
                    if k not in _RESERVED_KEYS
                    and (isinstance(v, (int, float)) or isinstance(v, str))
                }}
                if len(implicit_bulk) >= 2:
                    default_unit = str(args.get("unit") or "mm")
                    applied = []
                    for raw_name, raw_value in implicit_bulk.items():
                        param_name = str(raw_name).strip()
                        expression = str(raw_value).strip()
                        unit = (
                            _infer_unit_from_expr(expression)
                            or _unit_for(param_name, default_unit)
                        )
                        _ensure_param(param_name, expression, unit, "")
                        applied.append(param_name)
                    return {{
                        "message": "{{}} parametro(s) aplicado(s) (bulk implicito): {{}}.".format(
                            len(applied), ", ".join(applied)
                        ),
                        "applied": applied,
                    }}

            # fallback: formato singular legado
            name = singular_name
            expression = singular_expr
            # Drift do trace placa-parametrizada: o LLM emite o valor em
            # ``value_mm``/``value`` em vez de ``expression`` (ex:
            # name='plate_width', value_mm=80). Aceitamos esses aliases e
            # inferimos a unidade do sufixo do alias quando presente.
            alias_unit = None
            if not expression:
                for alias_key, alias_unit_hint in (
                    ("value_mm", "mm"),
                    ("value_cm", "cm"),
                    ("value_deg", "deg"),
                    ("value_rad", "rad"),
                    ("value", None),
                ):
                    if args.get(alias_key) is not None:
                        expression = str(args.get(alias_key)).strip()
                        alias_unit = alias_unit_hint
                        break
            unit = str(
                args.get("unit")
                or alias_unit
                or _infer_unit_from_expr(expression)
                or _unit_for(name, "mm")
            )
            comment = str(args.get("comment") or "")
            _ensure_param(name, expression, unit, comment)
            return {{"message": "Parâmetro '{{}}' = {{}}.".format(name, expression)}}


        def _export(args, fmt):
            # Fix #5: STL e 3MF crashavam com InternalValidationError quando
            # o design não tinha bodies (consequência dos sketches falhados
            # antes dos fixes #0+#2). Adicionado guard explícito para retornar
            # um erro tipado em vez de propagar o crash da SDK do Fusion,
            # que vinha como traceback opaco. STEP funciona com design vazio
            # porque exporta a estrutura mesmo sem geometria.
            design = _design()
            target = str(args.get("target") or "preview." + fmt)
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = Path(tempfile.gettempdir()) / target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            export_manager = design.exportManager
            if fmt == "step":
                options = export_manager.createSTEPExportOptions(str(target_path), _root(design))
            elif fmt == "stl":
                if _root(design).bRepBodies.count == 0:
                    raise ToolError(
                        "fusion.no_geometry",
                        "STL requer pelo menos um body sólido; o design está vazio.",
                    )
                options = export_manager.createSTLExportOptions(_root(design), str(target_path))
            elif fmt == "3mf":
                if _root(design).bRepBodies.count == 0:
                    raise ToolError(
                        "fusion.no_geometry",
                        "3MF requer pelo menos um body sólido; o design está vazio.",
                    )
                options = export_manager.createC3MFExportOptions(_root(design), str(target_path))
            else:
                raise ToolError("fusion.invalid_export_format", "Formato não suportado.")
            export_manager.execute(options)
            return {{
                "message": "Exportado para {{}} ({{}}).".format(target_path, fmt),
                "artifact_paths": [str(target_path)],
            }}


        def _validate_dimensions(_args):
            design = _design()
            bodies = _root(design).bRepBodies
            summary = []
            for index in range(bodies.count):
                body = bodies.item(index)
                bbox = body.boundingBox
                summary.append({{
                    "name": body.name,
                    "min_cm": [bbox.minPoint.x, bbox.minPoint.y, bbox.minPoint.z],
                    "max_cm": [bbox.maxPoint.x, bbox.maxPoint.y, bbox.maxPoint.z],
                    "volume_cm3": body.volume,
                }})
            return {{
                "message": "{{}} corpo(s) inspecionado(s).".format(len(summary)),
                "bodies": summary,
            }}


        def _collect_bodies(design):
            bodies = _root(design).bRepBodies
            output = []
            for index in range(bodies.count):
                body = bodies.item(index)
                bbox = body.boundingBox
                try:
                    surface_cm2 = float(body.physicalProperties.area)
                except Exception:
                    surface_cm2 = 0.0
                output.append({{
                    "name": body.name,
                    "is_solid": bool(getattr(body, "isSolid", True)),
                    "volume_mm3": float(getattr(body, "volume", 0.0)) * 1000.0,
                    "surface_area_mm2": surface_cm2 * 100.0,
                    "bbox_min_mm": [
                        bbox.minPoint.x * 10.0,
                        bbox.minPoint.y * 10.0,
                        bbox.minPoint.z * 10.0,
                    ],
                    "bbox_max_mm": [
                        bbox.maxPoint.x * 10.0,
                        bbox.maxPoint.y * 10.0,
                        bbox.maxPoint.z * 10.0,
                    ],
                }})
            return output


        def _validate_printability(args):
            checks = list(
                args.get("checks")
                or ["is_solid", "volume", "bounding_box", "wall_thickness_approx"]
            )
            min_dimension_mm = 0.8
            min_wall_mm = 0.8
            issues = []
            metrics = {{}}
            for body in _collect_bodies(_design()):
                name = body["name"]
                dims = [
                    abs(body["bbox_max_mm"][i] - body["bbox_min_mm"][i])
                    for i in range(3)
                ]
                metrics[name] = {{
                    "dimensions_mm": dims,
                    "volume_mm3": body["volume_mm3"],
                    "surface_area_mm2": body["surface_area_mm2"],
                    "is_solid": body["is_solid"],
                }}
                if "is_solid" in checks and not body["is_solid"]:
                    issues.append({{
                        "object_name": name,
                        "check": "is_solid",
                        "severity": "error",
                        "message": "Corpo não é sólido fechado.",
                        "recommendation": "Feche o corpo antes de exportar para impressão.",
                    }})
                if "volume" in checks and body["volume_mm3"] <= 0:
                    issues.append({{
                        "object_name": name,
                        "check": "volume",
                        "severity": "error",
                        "message": "Volume não positivo.",
                        "recommendation": "Revise a geometria do corpo.",
                    }})
                if "bounding_box" in checks and dims and min(dims) < min_dimension_mm:
                    issues.append({{
                        "object_name": name,
                        "check": "bounding_box",
                        "severity": "warning",
                        "message": "Dimensão mínima abaixo do perfil de impressão.",
                        "recommendation": "Aumente a escala ou a menor espessura da peça.",
                    }})
                if "wall_thickness_approx" in checks and body["surface_area_mm2"] > 0:
                    approx_wall = 2 * body["volume_mm3"] / body["surface_area_mm2"]
                    metrics[name]["wall_thickness_approx_mm"] = approx_wall
                    if approx_wall < min_wall_mm:
                        issues.append({{
                            "object_name": name,
                            "check": "wall_thickness_approx",
                            "severity": "warning",
                            "message": "Espessura aproximada abaixo do perfil de impressão.",
                            "recommendation": "Aumente paredes ou simplifique regiões finas.",
                        }})
            weights = {{"error": 0.5, "warning": 0.2, "info": 0.05}}
            risk_score = min(1.0, sum(weights.get(item["severity"], 0.0) for item in issues))
            recommendations = []
            for issue in issues:
                rec = issue.get("recommendation")
                if rec and rec not in recommendations:
                    recommendations.append(rec)
            return {{
                "message": "{{}} corpo(s), {{}} issue(s).".format(len(metrics), len(issues)),
                "objects_inspected": len(metrics),
                "checks_executed": checks,
                "issues": issues,
                "metrics": metrics,
                "recommendations": recommendations,
                "risk_score": risk_score,
                "printer_profile": args.get("printer_profile"),
            }}


        def _dispatch_inner(tool_name, args):
            if tool_name == "fusion.open_design":
                return _open_design(args)
            if tool_name == "fusion.create_sketch":
                return _create_sketch(args)
            if tool_name == "fusion.add_rectangle":
                return _add_rectangle(args)
            if tool_name == "fusion.add_circle":
                return _add_circle(args)
            if tool_name == "fusion.add_polygon":
                return _add_polygon(args)
            if tool_name == "fusion.add_line":
                return _add_line(args)
            if tool_name == "fusion.add_arc":
                return _add_arc(args)
            if tool_name == "fusion.add_ellipse":
                return _add_ellipse(args)
            if tool_name == "fusion.add_slot":
                return _add_slot(args)
            if tool_name == "fusion.extrude_profile":
                return _extrude_profile(args)
            if tool_name == "fusion.revolve_profile":
                return _revolve_profile(args)
            if tool_name == "fusion.add_box":
                return _add_box(args)
            if tool_name == "fusion.add_cylinder":
                return _add_cylinder(args)
            if tool_name == "fusion.add_sphere":
                return _add_sphere(args)
            if tool_name == "fusion.add_cone":
                return _add_cone(args)
            if tool_name == "fusion.fillet_edges":
                return _fillet_edges(args)
            if tool_name == "fusion.chamfer_edges":
                return _chamfer_edges(args)
            if tool_name == "fusion.shell_body":
                return _shell_body(args)
            if tool_name == "fusion.hole":
                return _hole(args)
            if tool_name == "fusion.pattern_rectangular":
                return _pattern_rectangular(args)
            if tool_name == "fusion.pattern_circular":
                return _pattern_circular(args)
            if tool_name == "fusion.mirror_feature":
                return _mirror_feature(args)
            if tool_name == "fusion.combine_bodies":
                return _combine_bodies(args)
            if tool_name == "fusion.loft_profiles":
                return _loft_profiles(args)
            if tool_name == "fusion.sweep_profile":
                return _sweep_profile(args)
            if tool_name == "fusion.create_surface_patch":
                return _create_surface_patch(args)
            if tool_name == "fusion.thicken_surface":
                return _thicken_surface(args)
            if tool_name == "fusion.stitch_surfaces":
                return _stitch_surfaces(args)
            if tool_name == "fusion.trim_surface":
                return _trim_surface(args)
            if tool_name == "fusion.extend_surface":
                return _extend_surface(args)
            if tool_name == "fusion.offset_surface":
                return _offset_surface(args)
            if tool_name == "fusion.unstitch_surface":
                return _unstitch_surface(args)
            if tool_name == "fusion.add_construction_plane":
                return _add_construction_plane(args)
            if tool_name == "fusion.add_spline":
                return _add_spline(args)
            if tool_name == "fusion.move_body":
                return _move_body(args)
            if tool_name == "fusion.scale_body":
                return _scale_body(args)
            if tool_name == "fusion.delete_body":
                return _delete_body(args)
            if tool_name == "fusion.split_body":
                return _split_body(args)
            if tool_name == "fusion.query_geometry":
                return _query_geometry(args)
            if tool_name == "fusion.query_timeline":
                return _query_timeline(args)
            if tool_name == "fusion.rollback_timeline":
                return _rollback_timeline(args)
            if tool_name == "fusion.set_parameter":
                return _set_parameter(args)
            if tool_name == "fusion.export_step":
                return _export(args, "step")
            if tool_name == "fusion.export_stl":
                return _export(args, "stl")
            if tool_name == "fusion.export_3mf":
                return _export(args, "3mf")
            if tool_name == "fusion.validate_dimensions":
                return _validate_dimensions(args)
            if tool_name == "fusion.validate_printability":
                return _validate_printability(args)
            raise ToolError("fusion.tool_not_implemented", "Ferramenta sem handler determinístico.")


        _BODY_CREATORS = (
            "fusion.extrude_profile",
            "fusion.revolve_profile",
            "fusion.add_box",
            "fusion.add_cylinder",
            "fusion.add_sphere",
            "fusion.add_cone",
            "fusion.loft_profiles",
            "fusion.sweep_profile",
        )


        def _normalize_param_suffix(args):
            # Drift do trace placa (mt_019e46d6dc46): o LLM expressa vinculos
            # parametricos com o sufixo "_param" carregando o NOME do parametro
            # (ex: width_param="plate_length", distance_param="plate_thickness",
            # diameter_param="hole_diameter"). A convencao e uniforme:
            # <base>_param -> <base>_mm com valor = nome do parametro. Mapeamos
            # aqui no dispatch para TODA tool dimensional; _eval_param /
            # _param_value_input / _param_name_or_none ja resolvem nome de
            # parametro como vinculo (G1.1/G1.2). So preenche se a chave _mm
            # canonica ainda nao veio. Nao usar chaves literais em comentarios
            # (modulo e f-string template).
            for key in list(args.keys()):
                if not key.endswith("_param"):
                    continue
                base = key[: -len("_param")]
                target = base + "_mm"
                if args.get(target) is None and args.get(key) is not None:
                    args[target] = args[key]
            return args


        def _dispatch(tool_name, args):
            # G2.3: wrapper que aplica result_name/output_name pos-criacao
            # nos tools que criam body, dando um handle estavel para steps
            # seguintes (pattern/mirror/fillet) referenciarem.
            args = _normalize_param_suffix(args)
            result = _dispatch_inner(tool_name, args)
            if tool_name in _BODY_CREATORS and (
                args.get("result_name") or args.get("output_name")
            ):
                try:
                    renamed = _maybe_rename_last_body(_design(), args)
                    if renamed and isinstance(result, dict):
                        result["body_name"] = renamed
                except Exception:
                    pass
            return result


        def run(_context: str):
            try:
                result = _dispatch(TOOL_NAME, dict(ARGUMENTS))
                result.update({{
                    "ok": True,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                }})
                _emit(result)
            except ToolError as exc:
                _emit({{
                    "ok": False,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                    "error_code": exc.code,
                    "message": str(exc),
                    "retryable": True,
                }})
            except Exception as exc:
                _emit({{
                    "ok": False,
                    "tool_name": TOOL_NAME,
                    "software": "fusion",
                    "error_code": "fusion.script_failed",
                    "message": str(exc),
                    "retryable": True,
                    "traceback": traceback.format_exc(limit=5),
                }})
        """
    ).strip()
