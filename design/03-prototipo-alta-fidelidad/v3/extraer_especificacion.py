#!/usr/bin/env python3
"""Extrae una especificación compacta de diseño desde la exportación JSON de un archivo de Figma.

Convierte el JSON completo (decenas de MB, con URL firmadas de miniaturas) en archivos pequeños que
sí se versionan y que bastan para implementar la interfaz sin abrir Figma:

  tokens.json                 colores (variables con nombre), tipografía, radios, espaciado, sombras
  estructura-pantallas.json   árbol simplificado de cada pantalla: textos, diseño, componentes, enlaces
  pantallas.md                inventario de pantallas con su captura y a dónde navega cada una

Solo usa la biblioteca estándar. Uso (desde la raíz del repositorio):

  python3 -I design/03-prototipo-alta-fidelidad/v3/extraer_especificacion.py \\
      --figma design/03-prototipo-alta-fidelidad/archivo_completo.json \\
      --variables design/03-prototipo-alta-fidelidad/v3/variables.json \\
      --pantallas design/03-prototipo-alta-fidelidad/smartmentor_figma/pantallas \\
      --salida design/03-prototipo-alta-fidelidad/v3

El JSON de entrada se trata como dato no confiable: solo se leen campos conocidos.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

Node = dict[str, Any]

TYPE_CODE = {
    "FRAME": "F",
    "TEXT": "T",
    "INSTANCE": "I",
    "RECTANGLE": "R",
    "ELLIPSE": "E",
    "VECTOR": "V",
    "COMPONENT": "C",
    "GROUP": "G",
}


def hex_color(color: dict[str, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(round(color[k] * 255) for k in "rgb"))


def screen_group(name: str) -> str:
    """Agrupa las pantallas por el prefijo de su nombre en Figma."""
    if re.match(r"^AD\d", name):
        return "admin"
    if re.match(r"^A\d", name):
        return "acceso"
    if re.match(r"^E\d", name):
        return "aprendiz"
    if re.match(r"^D\d", name):
        return "instructor"
    if re.match(r"^U\d", name):
        return "carga"
    if name.startswith("Catálogo de prompts"):
        return "ia"
    if name.startswith("Matriz"):
        return "referencia"
    if name.startswith("Componentes"):
        return "biblioteca"
    return "otro"


class Extractor:
    def __init__(self, figma: Node, variables: dict[str, Any], png_dir: Path | None) -> None:
        self.figma = figma
        self.page = figma["document"]["children"][0]
        self.var_name: dict[str, str] = {k: v["name"] for k, v in variables["variables"].items()}
        self.components: dict[str, Node] = figma.get("components", {})
        self.component_sets: dict[str, Node] = figma.get("componentSets", {})
        self.typography: Counter[tuple[Any, ...]] = Counter()
        self.radii: Counter[float] = Counter()
        self.spacing: Counter[float] = Counter()
        self.shadows: Counter[str] = Counter()
        self.frame_ids = {c["id"] for c in self.page["children"] if c["type"] == "FRAME"}
        self.parent_frame: dict[str, str] = {}
        self.png_by_id: dict[str, str] = {}
        if png_dir is not None and png_dir.is_dir():
            for file in sorted(png_dir.glob("*.png")):
                match = re.search(r"\[(\d+)-(\d+)\]\.png$", file.name)
                if match:
                    self.png_by_id[f"{match.group(1)}:{match.group(2)}"] = file.name

    # -- colores -------------------------------------------------------------------------------
    def paint_ref(self, node: Node, prop: str) -> str | None:
        paints = node.get(prop) or []
        bound = (node.get("boundVariables") or {}).get(prop) or []
        for index, paint in enumerate(paints):
            if paint.get("visible") is False:
                continue
            if paint.get("type") == "SOLID":
                variable = bound[index].get("id") if index < len(bound) else None
                if variable and variable in self.var_name:
                    return "$" + self.var_name[variable]
                color = hex_color(paint["color"])
                alpha = paint.get("opacity", paint["color"].get("a", 1))
                return color if alpha >= 0.999 else f"{color}@{round(alpha, 2)}"
            if paint.get("type", "").startswith("GRADIENT"):
                return "gradiente"
            if paint.get("type") == "IMAGE":
                return "imagen"
        return None

    # -- tipografía ----------------------------------------------------------------------------
    def typography_key(self, style: Node) -> str:
        key = (
            style.get("fontFamily"),
            style.get("fontSize"),
            style.get("fontWeight"),
            round(style["lineHeightPx"], 1) if style.get("lineHeightPx") else None,
            round(style.get("letterSpacing") or 0, 2),
        )
        self.typography[key] += 1
        family, size, weight, line, spacing = key
        text = f"{family} {size:g}/{weight}"
        if line:
            text += f" lh{line:g}"
        if spacing:
            text += f" ls{spacing:g}"
        return text

    # -- navegación ----------------------------------------------------------------------------
    def first_label(self, node: Node) -> str:
        if node["type"] == "TEXT":
            return (node.get("characters") or "").strip().replace("\n", " ")[:50]
        for child in node.get("children", []) or []:
            label = self.first_label(child)
            if label:
                return label
        return ""

    def interactions(self, node: Node) -> list[dict[str, str]]:
        result = []
        for interaction in node.get("interactions") or []:
            trigger = (interaction.get("trigger") or {}).get("type", "")
            for action in interaction.get("actions") or []:
                if action.get("type") == "NODE" and action.get("destinationId"):
                    result.append(
                        {
                            "ev": trigger,
                            "to": action["destinationId"],
                            "k": action.get("navigation", "NAVIGATE"),
                        }
                    )
                elif action.get("type") in ("BACK", "CLOSE", "URL"):
                    result.append({"ev": trigger, "k": action["type"], "url": action.get("url", "")})
        return result

    # -- árbol simplificado --------------------------------------------------------------------
    def component_label(self, node: Node) -> str | None:
        component = self.components.get(node.get("componentId", ""))
        if component is None:
            return None
        set_id = component.get("componentSetId")
        prefix = self.component_sets.get(set_id, {}).get("name") if set_id else None
        return f"{prefix}/{component['name']}" if prefix else component["name"]

    def simplify(self, node: Node, parent: Node | None, frame_id: str, nav: list[dict[str, Any]]) -> Node | None:
        if node.get("visible") is False:
            return None
        self.parent_frame[node["id"]] = frame_id
        kind = TYPE_CODE.get(node["type"], node["type"])
        out: Node = {"id": node["id"], "t": kind}
        box = node.get("absoluteBoundingBox")
        if box:
            out["w"], out["h"] = round(box["width"]), round(box["height"])
            parent_box = parent.get("absoluteBoundingBox") if parent else None
            if parent_box and parent is not None and parent.get("layoutMode", "NONE") == "NONE":
                out["x"], out["y"] = round(box["x"] - parent_box["x"]), round(box["y"] - parent_box["y"])
        if node["type"] != "TEXT" and node.get("name"):
            out["n"] = node["name"]

        if node["type"] == "TEXT":
            style = node.get("style") or {}
            out["c"] = node.get("characters", "")
            out["ty"] = self.typography_key(style)
            if style.get("textAlignHorizontal") not in (None, "LEFT"):
                out["al"] = style["textAlignHorizontal"].lower()
            color = self.paint_ref(node, "fills")
            if color:
                out["f"] = color
        else:
            fill = self.paint_ref(node, "fills")
            if fill:
                out["f"] = fill
            stroke = self.paint_ref(node, "strokes")
            if stroke:
                out["s"] = stroke
                if node.get("strokeWeight") not in (None, 1):
                    out["sw"] = node["strokeWeight"]
            radius = node.get("cornerRadius")
            if radius:
                out["r"] = radius
                self.radii[radius] += 1
            elif node.get("rectangleCornerRadii"):
                out["r"] = node["rectangleCornerRadii"]
            mode = node.get("layoutMode", "NONE")
            if mode != "NONE":
                out["lm"] = "H" if mode == "HORIZONTAL" else "V"
                gap = node.get("itemSpacing") or 0
                if gap:
                    out["g"] = gap
                    self.spacing[gap] += 1
                padding = [node.get(k) or 0 for k in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft")]
                if any(padding):
                    out["p"] = padding
                    for value in padding:
                        if value:
                            self.spacing[value] += 1
                for key, short in (("primaryAxisAlignItems", "pa"), ("counterAxisAlignItems", "ca")):
                    value = node.get(key)
                    if value and value not in ("MIN",):
                        out[short] = value.lower()
                if node.get("layoutWrap") == "WRAP":
                    out["wrap"] = True
            sizing = (node.get("layoutSizingHorizontal"), node.get("layoutSizingVertical"))
            if parent is not None and parent.get("layoutMode", "NONE") != "NONE" and any(sizing):
                out["sz"] = "/".join(s or "-" for s in sizing)
            for effect in node.get("effects") or []:
                if effect.get("visible") is not False and effect.get("type") in ("DROP_SHADOW", "INNER_SHADOW"):
                    offset = effect.get("offset", {})
                    desc = f"{effect['type'].lower()} {offset.get('x', 0):g} {offset.get('y', 0):g} blur{effect.get('radius', 0):g} {hex_color(effect['color'])}@{round(effect['color'].get('a', 1), 2)}"
                    out.setdefault("fx", []).append(desc)
                    self.shadows[desc] += 1
        if node["type"] == "INSTANCE":
            label = self.component_label(node)
            if label:
                out["cmp"] = label
        if node.get("opacity", 1) < 0.999:
            out["op"] = round(node["opacity"], 2)
        links = self.interactions(node)
        if links:
            out["go"] = links
            label = self.first_label(node) or node.get("name", "")
            for link in links:
                nav.append({"from": node["id"], "label": label, **link})
        children = []
        for child in node.get("children", []) or []:
            simple = self.simplify(child, node, frame_id, nav)
            if simple is not None:
                children.append(simple)
        if children:
            out["ch"] = children
        return out

    # -- salida --------------------------------------------------------------------------------
    def run(self) -> tuple[list[Node], dict[str, Any]]:
        screens: list[Node] = []
        for frame in self.page["children"]:
            if frame["type"] != "FRAME" or frame.get("visible") is False:
                continue
            nav: list[dict[str, Any]] = []
            tree = self.simplify(frame, None, frame["id"], nav)
            assert tree is not None
            screens.append(
                {
                    "id": frame["id"],
                    "name": frame["name"],
                    "grupo": screen_group(frame["name"]),
                    "png": self.png_by_id.get(frame["id"]),
                    "nav": nav,
                    "raiz": tree,
                }
            )
        # resolver cada destino a su pantalla (el destino puede ser un nodo interno)
        for screen in screens:
            for link in screen["nav"]:
                destination = link.get("to")
                if destination:
                    link["pantalla"] = destination if destination in self.frame_ids else self.parent_frame.get(destination)
        tokens = {
            "tipografia": [
                {"estilo": self.typography_key_text(key), "usos": count}
                for key, count in self.typography.most_common()
            ],
            "radios": [{"px": radius, "usos": count} for radius, count in sorted(self.radii.items())],
            "espaciado": [{"px": value, "usos": count} for value, count in sorted(self.spacing.items())],
            "sombras": [{"efecto": desc, "usos": count} for desc, count in self.shadows.most_common()],
        }
        return screens, tokens

    @staticmethod
    def typography_key_text(key: tuple[Any, ...]) -> str:
        family, size, weight, line, spacing = key
        text = f"{family} {size:g}/{weight}"
        if line:
            text += f" lh{line:g}"
        if spacing:
            text += f" ls{spacing:g}"
        return text


def count_nodes(node: Node) -> Counter[str]:
    counter: Counter[str] = Counter({node["t"]: 1})
    for child in node.get("ch", []):
        counter += count_nodes(child)
    return counter


def collect_texts(node: Node, out: list[str]) -> None:
    if node["t"] == "T" and node.get("c", "").strip():
        out.append(node["c"].strip())
    for child in node.get("ch", []):
        collect_texts(child, out)


def collect_components(node: Node, out: Counter[str]) -> None:
    if node.get("cmp"):
        out[node["cmp"]] += 1
    for child in node.get("ch", []):
        collect_components(child, out)


def write_inventory(screens: list[Node], path: Path) -> None:
    by_id = {s["id"]: s for s in screens}
    labels = {
        "acceso": "Acceso (A)",
        "aprendiz": "Aprendiz (E)",
        "instructor": "Instructor (D)",
        "admin": "Administrador (AD)",
        "carga": "Estados de carga (U)",
        "ia": "Catálogo de prompts de IA",
        "referencia": "Referencia",
        "biblioteca": "Biblioteca de componentes",
        "otro": "Otras",
    }
    lines = [
        "# Inventario de pantallas del prototipo v3",
        "",
        "Generado por `extraer_especificacion.py` a partir de la exportación de Figma. No se edita a mano: se regenera.",
        "",
        f"Total: **{len(screens)}** pantallas. Columnas: identificador del nodo en Figma, nombre, tamaño, captura (en "
        "`design/03-prototipo-alta-fidelidad/smartmentor_figma/pantallas/`, no versionada), textos, componentes usados y "
        "las pantallas a las que navega (según los enlaces del prototipo).",
        "",
    ]
    for group, title in labels.items():
        members = [s for s in screens if s["grupo"] == group]
        if not members:
            continue
        lines += [f"## {title}", "", "| Nodo | Pantalla | Tamaño | Captura | Textos | Componentes | Navega a |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for screen in members:
            texts: list[str] = []
            collect_texts(screen["raiz"], texts)
            components: Counter[str] = Counter()
            collect_components(screen["raiz"], components)
            targets: list[str] = []
            for link in screen["nav"]:
                target = link.get("pantalla")
                if target and target != screen["id"] and target in by_id:
                    short = re.match(r"^[A-Z]+\d+[a-z]*", by_id[target]["name"])
                    tag = short.group(0) if short else target
                    if tag not in targets:
                        targets.append(tag)
            png = f"`{screen['png']}`" if screen["png"] else "—"
            comp = ", ".join(f"{name.split('/')[-1]}×{n}" for name, n in components.most_common(3)) or "—"
            size = f"{screen['raiz'].get('w', '?')}×{screen['raiz'].get('h', '?')}"
            lines.append(
                f"| `{screen['id']}` | {screen['name']} | {size} | {png} | {len(texts)} | {comp} | {', '.join(targets) or '—'} |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figma", type=Path, required=True, help="JSON exportado de Figma")
    parser.add_argument("--variables", type=Path, required=True, help="variables.json (id → nombre y valor)")
    parser.add_argument("--pantallas", type=Path, help="carpeta con las capturas PNG exportadas")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta de salida")
    args = parser.parse_args()

    figma = json.loads(args.figma.read_text(encoding="utf-8"))
    variables = json.loads(args.variables.read_text(encoding="utf-8"))
    extractor = Extractor(figma, variables, args.pantallas)
    screens, tokens = extractor.run()

    args.salida.mkdir(parents=True, exist_ok=True)
    meta = {
        "archivo": figma.get("name"),
        "ultima_modificacion": figma.get("lastModified"),
        "pagina": extractor.page.get("name"),
        "puntos_de_inicio": extractor.page.get("flowStartingPoints", []),
    }
    (args.salida / "estructura-pantallas.json").write_text(
        json.dumps({"meta": meta, "pantallas": screens}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    colors = {
        entry["name"]: {"hex": entry["hex"], "id": vid, "grupo": entry["name"].split("/")[0], "estado": entry["estado"]}
        for vid, entry in variables["variables"].items()
    }
    (args.salida / "tokens.json").write_text(
        json.dumps({"meta": meta, "colores": colors, **tokens}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    write_inventory(screens, args.salida / "pantallas.md")

    totals: Counter[str] = Counter()
    for screen in screens:
        totals += count_nodes(screen["raiz"])
    links = sum(len(s["nav"]) for s in screens)
    print(f"{len(screens)} pantallas, {sum(totals.values())} nodos {dict(totals)}, {links} enlaces de navegación")
    print(f"{len(tokens['tipografia'])} estilos tipográficos, {len(tokens['radios'])} radios, {len(tokens['espaciado'])} valores de espaciado")


if __name__ == "__main__":
    main()
