"""Genera los wireframes de baja fidelidad de la Fase 0 en Excalidraw (.excalidraw) y SVG.

Cada pantalla se describe una sola vez con primitivas (caja, texto, línea, botón) y se escribe en
los dos formatos: el .excalidraw se edita en excalidraw.com y el .svg se ve directo en GitHub.

Uso: python3 design/02-wireframes-baja-fidelidad/generate_wireframes.py
"""

import json
import random
from pathlib import Path
from xml.sax.saxutils import escape

OUT_DIR = Path(__file__).parent
WIDTH = 960
INK = "#1e1e1e"
MUTED = "#868e96"
FILL = "#f1f3f5"
FILL_DARK = "#ced4da"
SVG_FONT = "'Comic Sans MS', 'Comic Neue', 'Segoe Print', cursive"


class Screen:
    """Lienzo de una pantalla: acumula primitivas y las exporta a Excalidraw y SVG."""

    def __init__(self, slug: str, title: str, height: int) -> None:
        self.slug = slug
        self.title = title
        self.height = height
        self.shapes: list[dict] = []

    # Primitivas

    def rect(self, x, y, w, h, fill=None, dashed=False, rounded=True, stroke=INK):
        self.shapes.append(
            {"kind": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill,
             "dashed": dashed, "rounded": rounded, "stroke": stroke}
        )

    def ellipse(self, x, y, w, h, fill=None, stroke=INK):
        self.shapes.append(
            {"kind": "ellipse", "x": x, "y": y, "w": w, "h": h, "fill": fill, "stroke": stroke}
        )

    def line(self, x1, y1, x2, y2, stroke=INK, dashed=False, width=1):
        self.shapes.append(
            {"kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke": stroke,
             "dashed": dashed, "width": width}
        )

    def text(self, x, y, value, size=16, color=INK, anchor="start"):
        """Texto con su borde superior en `y`; `anchor` (start, middle, end) fija qué punto es `x`."""
        self.shapes.append(
            {"kind": "text", "x": x, "y": y, "value": value, "size": size, "color": color,
             "anchor": anchor}
        )

    # Componentes

    def button(self, x, y, w, h, label, primary=False, dashed=False):
        self.rect(x, y, w, h, fill=FILL_DARK if primary else None, dashed=dashed)
        self.text(x + w / 2, y + h / 2 - 8, label, size=14, anchor="middle")

    def field(self, x, y, w, label, placeholder):
        self.text(x, y, label, size=13)
        self.rect(x, y + 22, w, 36)
        self.text(x + 12, y + 32, placeholder, size=13, color=MUTED)

    def image(self, x, y, w, h, label):
        self.rect(x, y, w, h, rounded=False, stroke=MUTED)
        self.line(x, y, x + w, y + h, stroke=MUTED)
        self.line(x + w, y, x, y + h, stroke=MUTED)
        self.rect(x + w / 2 - len(label) * 4 - 8, y + h / 2 - 13, len(label) * 8 + 16, 26,
                  fill="#ffffff", stroke=MUTED)
        self.text(x + w / 2, y + h / 2 - 8, label, size=13, color=MUTED, anchor="middle")

    def paragraph(self, x, y, w, lines=3, gap=14):
        for i in range(lines):
            length = w * (0.6 if i == lines - 1 else 1)
            self.line(x, y + i * gap, x + length, y + i * gap, stroke=MUTED, width=2)

    def chip(self, x, y, label):
        w = len(label) * 6.6 + 20
        self.rect(x, y, w, 24, fill=FILL)
        self.text(x + w / 2, y + 5, label, size=12, anchor="middle")
        return w

    def chips(self, x, y, labels, gap=8):
        for label in labels:
            x += self.chip(x, y, label) + gap

    def progress(self, x, y, w, fraction):
        self.rect(x, y, w, 12)
        self.rect(x, y, w * fraction, 12, fill=FILL_DARK)

    def radio(self, x, y, label, boxed_width=None):
        if boxed_width:
            self.rect(x, y, boxed_width, 36)
            x, y = x + 12, y + 10
        self.ellipse(x, y, 16, 16)
        self.text(x + 28, y, label, size=14)

    def top_bar(self, links, active):
        self.rect(0, 0, WIDTH, 56, fill=FILL, rounded=False)
        self.text(24, 18, "SmartMentor", size=18)
        x = 300
        for link in links:
            self.text(x, 20, link, size=14, color=INK if link == active else MUTED)
            if link == active:
                self.line(x, 42, x + len(link) * 8, 42, width=2)
            x += len(link) * 8 + 40
        self.ellipse(WIDTH - 56, 12, 32, 32)

    def stepper(self, y, active):
        steps = ("1 · Perfil", "2 · Diagnóstico", "3 · Objetivo")
        for i, label in enumerate(steps):
            cx = 280 + i * 200
            self.ellipse(cx - 12, y, 24, 24, fill=FILL_DARK if i <= active else None)
            self.text(cx, y + 30, label, size=13, color=INK if i == active else MUTED,
                      anchor="middle")
            if i < len(steps) - 1:
                self.line(cx + 16, y + 12, cx + 184, y + 12, stroke=MUTED)

    # Exportación

    def to_excalidraw(self) -> dict:
        rng = random.Random(self.slug)
        elements = []

        def base(kind, x, y, w, h, stroke):
            seed = rng.randint(1, 2**31 - 1)
            return {
                "id": f"{self.slug}-{len(elements)}", "type": kind, "x": x, "y": y,
                "width": w, "height": h, "angle": 0, "strokeColor": stroke,
                "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1,
                "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
                "frameId": None, "roundness": None, "seed": seed, "version": 1,
                "versionNonce": seed, "isDeleted": False, "boundElements": None,
                "updated": 1, "link": None, "locked": False,
            }

        caption = Screen(self.slug, self.title, 0)
        caption.text(0, -44, self.title, size=20)
        frame = Screen(self.slug, self.title, 0)
        frame.rect(0, 0, WIDTH, self.height, rounded=False)
        for shape in frame.shapes + caption.shapes + self.shapes:
            kind = shape["kind"]
            if kind in ("rect", "ellipse"):
                el = base("rectangle" if kind == "rect" else "ellipse", shape["x"], shape["y"],
                          shape["w"], shape["h"], shape["stroke"])
                if shape.get("fill"):
                    el["backgroundColor"] = shape["fill"]
                if shape.get("dashed"):
                    el["strokeStyle"] = "dashed"
                if kind == "rect" and shape["rounded"]:
                    el["roundness"] = {"type": 3}
            elif kind == "line":
                dx, dy = shape["x2"] - shape["x1"], shape["y2"] - shape["y1"]
                el = base("line", shape["x1"], shape["y1"], abs(dx), abs(dy), shape["stroke"])
                el.update({"points": [[0, 0], [dx, dy]], "lastCommittedPoint": None,
                           "startBinding": None, "endBinding": None,
                           "startArrowhead": None, "endArrowhead": None,
                           "strokeWidth": shape["width"]})
                if shape["dashed"]:
                    el["strokeStyle"] = "dashed"
            else:
                size = shape["size"]
                w = len(shape["value"]) * size * 0.55
                shift = {"start": 0, "middle": w / 2, "end": w}[shape["anchor"]]
                align = {"start": "left", "middle": "center", "end": "right"}[shape["anchor"]]
                el = base("text", shape["x"] - shift, shape["y"], w, size * 1.25, shape["color"])
                el.update({"text": shape["value"], "originalText": shape["value"],
                           "fontSize": size, "fontFamily": 1, "textAlign": align,
                           "verticalAlign": "top", "containerId": None, "lineHeight": 1.25,
                           "autoResize": True})
            elements.append(el)
        return {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
                "elements": elements,
                "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}}

    def to_svg(self) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -60 {WIDTH + 40} '
            f'{self.height + 80}" width="{WIDTH + 40}" height="{self.height + 80}" '
            f'font-family="{SVG_FONT}">',
            f'<rect x="-20" y="-60" width="{WIDTH + 40}" height="{self.height + 80}" '
            'fill="#ffffff"/>',
            f'<text x="0" y="-26" font-size="20" fill="{INK}">{escape(self.title)}</text>',
            f'<rect x="0" y="0" width="{WIDTH}" height="{self.height}" fill="none" '
            f'stroke="{INK}" stroke-width="1.5"/>',
        ]
        for shape in self.shapes:
            kind = shape["kind"]
            if kind == "rect":
                parts.append(
                    f'<rect x="{shape["x"]}" y="{shape["y"]}" width="{shape["w"]}" '
                    f'height="{shape["h"]}" rx="{6 if shape["rounded"] else 0}" '
                    f'fill="{shape["fill"] or "none"}" stroke="{shape["stroke"]}" '
                    f'stroke-width="1.5"{_dash(shape["dashed"])}/>'
                )
            elif kind == "ellipse":
                parts.append(
                    f'<ellipse cx="{shape["x"] + shape["w"] / 2}" cy="{shape["y"] + shape["h"] / 2}" '
                    f'rx="{shape["w"] / 2}" ry="{shape["h"] / 2}" fill="{shape["fill"] or "none"}" '
                    f'stroke="{shape["stroke"]}" stroke-width="1.5"/>'
                )
            elif kind == "line":
                parts.append(
                    f'<line x1="{shape["x1"]}" y1="{shape["y1"]}" x2="{shape["x2"]}" '
                    f'y2="{shape["y2"]}" stroke="{shape["stroke"]}" '
                    f'stroke-width="{shape["width"] * 1.5}"{_dash(shape["dashed"])}/>'
                )
            else:
                baseline = shape["y"] + shape["size"] * 0.9
                parts.append(
                    f'<text x="{shape["x"]}" y="{baseline}" font-size="{shape["size"]}" '
                    f'fill="{shape["color"]}" text-anchor="{shape["anchor"]}">'
                    f'{escape(shape["value"])}</text>'
                )
        parts.append("</svg>")
        return "\n".join(parts) + "\n"


def _dash(dashed: bool) -> str:
    return ' stroke-dasharray="8 6"' if dashed else ""


STUDENT_LINKS = ("Rutas", "Mi progreso", "Logros")


def login() -> Screen:
    s = Screen("01-login", "1 · Login (Figma A2 y A4)", 600)
    s.rect(0, 0, 420, 600, fill=FILL, rounded=False)
    s.image(40, 120, 340, 260, "Ilustración")
    s.text(40, 410, "Rutas de aprendizaje con IA", size=18)
    s.paragraph(40, 450, 340, lines=2)
    s.text(690, 70, "SmartMentor", size=28, anchor="middle")
    s.text(690, 115, "Inicia sesión", size=18, color=MUTED, anchor="middle")
    s.field(520, 160, 340, "Correo institucional", "nombre@universidad.edu.co")
    s.field(520, 240, 340, "Contraseña", "••••••••")
    s.text(520, 310, "¿Olvidaste tu contraseña?", size=13, color=MUTED)
    s.button(520, 345, 340, 44, "Entrar", primary=True)
    s.line(520, 412, 860, 412, stroke=MUTED, dashed=True)
    s.button(520, 430, 340, 44, "Entrar con cuenta institucional")
    s.text(520, 500, "Docente y admin: verificación en dos pasos al entrar.", size=12, color=MUTED)
    s.text(520, 525, "Error: «Correo o contraseña incorrectos» bajo el botón.", size=12,
           color=MUTED)
    return s


def catalog() -> Screen:
    s = Screen("02-catalogo", "2 · Catálogo de rutas (Figma E1)", 690)
    s.top_bar(STUDENT_LINKS, "Rutas")
    s.text(32, 80, "Rutas disponibles", size=24)
    s.text(32, 115, "Elige una ruta. Primero harás un diagnóstico corto.", size=14, color=MUTED)
    s.rect(32, 150, 896, 64, fill=FILL)
    s.text(52, 163, "Continúa donde quedaste", size=14)
    s.text(52, 186, "Fundamentos de ML · 2 de 5 temas", size=13, color=MUTED)
    s.progress(380, 176, 300, 0.4)
    s.button(780, 162, 128, 40, "Continuar", primary=True)
    s.rect(32, 236, 560, 40)
    s.text(48, 248, "Buscar ruta…", size=14, color=MUTED)
    s.rect(608, 236, 200, 40)
    s.text(624, 248, "Filtrar: todas  ▾", size=14, color=MUTED)
    cards = (
        ("Fundamentos de ML", "Inscrito"),
        ("Estadística", "Disponible"),
        ("Python", "Disponible"),
        ("Series de tiempo", "Disponible"),
        ("Visualización", "Próximamente"),
    )
    for i, (title, status) in enumerate(cards):
        x, y = 32 + (i % 3) * 304, 296 + (i // 3) * 192
        s.rect(x, y, 288, 176)
        s.image(x + 12, y + 12, 264, 60, "imagen")
        s.text(x + 12, y + 82, title, size=15)
        s.text(x + 12, y + 104, "5 temas · ~6 h · docente", size=12, color=MUTED)
        s.chip(x + 12, y + 136, status)
        s.button(x + 176, y + 130, 100, 34, "Ver ruta", primary=status == "Inscrito")
    s.rect(640, 488, 288, 176, dashed=True, stroke=MUTED)
    s.text(784, 556, "Estado vacío:", size=13, color=MUTED, anchor="middle")
    s.text(784, 578, "«Aún no hay rutas publicadas»", size=13, color=MUTED, anchor="middle")
    return s


def profile() -> Screen:
    s = Screen("03-perfil", "3 · Perfil del estudiante (Figma E2)", 610)
    s.top_bar(STUDENT_LINKS, "Rutas")
    s.stepper(76, active=0)
    s.text(160, 140, "Cuéntanos sobre ti", size=24)
    s.text(160, 175, "Inscripción: Fundamentos de ML", size=14, color=MUTED)
    s.text(160, 212, "Describe tu experiencia, formación e intereses", size=15)
    s.rect(160, 240, 640, 160)
    s.text(176, 256, "Ej.: Soy ingeniera industrial, uso Excel a diario y…", size=13,
           color=MUTED)
    s.text(800, 406, "0 / 1000", size=12, color=MUTED, anchor="end")
    s.text(160, 418, "Ideas para escribir:", size=13, color=MUTED)
    s.chips(160, 440, ("Formación", "Experiencia laboral", "Herramientas que usas",
                       "Qué quieres lograr"))
    s.rect(160, 482, 640, 44, fill=FILL)
    s.text(176, 496, "ⓘ Se usa para estimar tu nivel previo. No cuenta para tu nota.", size=13)
    s.button(160, 548, 120, 40, "Atrás")
    s.button(560, 548, 240, 40, "Continuar al diagnóstico", primary=True)
    return s


def diagnostic() -> Screen:
    s = Screen("04-diagnostico", "4 · Diagnóstico (Figma E3; resultado en E4)", 620)
    s.top_bar(STUDENT_LINKS, "Rutas")
    s.stepper(76, active=1)
    s.text(160, 140, "Diagnóstico", size=24)
    s.text(800, 146, "Pregunta 3 de 10", size=13, color=MUTED, anchor="end")
    s.progress(160, 180, 640, 0.3)
    s.chips(160, 206, ("Tema: Regresión lineal", "Bloom: aplicar"))
    s.text(160, 248, "Enunciado de la pregunta", size=17)
    s.paragraph(160, 284, 640, lines=2)
    for i, label in enumerate(("Opción A", "Opción B", "Opción C", "Opción D")):
        s.radio(160, 318 + i * 44, label, boxed_width=640)
    s.text(160, 504, "No cuenta para tu nota. Si no sabes, elige «No lo sé».", size=12,
           color=MUTED)
    s.button(160, 552, 120, 40, "Anterior")
    s.button(400, 552, 160, 40, "No lo sé", dashed=True)
    s.button(680, 552, 120, 40, "Siguiente", primary=True)
    return s


def path_view() -> Screen:
    s = Screen("05-vista-de-ruta", "5 · Vista de ruta (Figma E5)", 680)
    s.top_bar(STUDENT_LINKS, "Rutas")
    s.text(32, 76, "Fundamentos de ML", size=24)
    s.text(32, 112, "Docente: Elena Ramírez · inscrita el 28 sep", size=13, color=MUTED)
    s.rect(32, 140, 600, 80, fill=FILL)
    s.text(48, 152, "Tu objetivo", size=13, color=MUTED)
    s.text(600, 152, "Editar", size=13, color=MUTED, anchor="end")
    s.paragraph(48, 184, 560, lines=2, gap=16)
    s.text(32, 238, "Avance: 2 de 5 temas", size=14)
    s.progress(32, 262, 600, 0.4)
    topics = (
        ("1 · Introducción y tipos", "Dominado en el diagnóstico (85 %)", "Omitido", True),
        ("2 · Regresión lineal", "Intento 1 · 90 %", "Aprobado", True),
        ("3 · Regresión logística", "Intento 2 de 3 · último 60 %", "En curso", False),
        ("4 · Árboles de decisión", "Requiere el tema 3", "Pendiente", False),
        ("5 · Evaluación de modelos", "Requiere el tema 4", "Pendiente", False),
    )
    for i, (name, detail, state, done) in enumerate(topics):
        y = 300 + i * 62
        s.line(48, y + 26, 48, y + 62, stroke=MUTED)
        s.ellipse(36, y, 24, 24, fill=FILL_DARK if done else None)
        s.text(76, y, name, size=15)
        s.text(76, y + 22, detail, size=12, color=MUTED)
        s.chip(500, y + 2, state)
    s.ellipse(36, 610, 24, 24)
    s.rect(76, 600, 556, 52, dashed=True, stroke=MUTED)
    s.text(92, 608, "Evaluación final · se habilita al completar los 5 temas", size=14)
    s.text(92, 628, "Aprobación ≥ 80 % · otorga el badge", size=12, color=MUTED)
    s.rect(664, 140, 264, 170)
    s.text(680, 154, "Siguiente paso", size=13, color=MUTED)
    s.text(680, 180, "Tema 3 · Regresión logística", size=15)
    s.text(680, 206, "Intento 2 de 3", size=13, color=MUTED)
    s.button(680, 250, 232, 40, "Continuar tema", primary=True)
    s.rect(664, 330, 264, 140, fill=FILL)
    s.text(680, 344, "Reglas de la ruta", size=13, color=MUTED)
    s.text(680, 374, "Aprobar un tema: ≥ 70 %", size=13)
    s.text(680, 400, "Máximo 3 intentos por tema", size=13)
    s.text(680, 426, "Evaluación final: ≥ 80 %", size=13)
    return s


def topic() -> Screen:
    s = Screen("06-tema", "6 · Tema: video, texto y quiz (Figma E6; resultado en E7)", 880)
    s.top_bar(STUDENT_LINKS, "Rutas")
    s.text(32, 70, "Mi ruta  ›  Tema 3 de 5", size=13, color=MUTED)
    s.text(32, 92, "Regresión logística", size=24)
    s.chips(32, 130, ("Bloom: aplicar", "Intento 2 de 3"))
    s.image(32, 170, 440, 248, "Video (YouTube)")
    s.text(32, 428, "Título del video · 12 min · relevancia 0,87", size=12, color=MUTED)
    s.text(496, 170, "Explicación", size=17)
    s.paragraph(496, 204, 432, lines=4)
    s.text(800, 240, "[1]", size=12, color=MUTED)
    s.paragraph(496, 272, 432, lines=3)
    s.text(800, 294, "[2]", size=12, color=MUTED)
    s.text(496, 330, "Fuentes", size=14)
    s.text(496, 354, "[1] Libro abierto, cap. 4", size=12, color=MUTED)
    s.text(496, 374, "[2] Apuntes del docente, p. 12", size=12, color=MUTED)
    s.text(496, 404, "Generado con IA · explicacion_tema v1.3", size=11, color=MUTED)
    s.rect(32, 456, 896, 48, fill=FILL)
    s.text(48, 471, "Explicación alterna: este intento usa un enfoque distinto al anterior.",
           size=13)
    s.line(32, 528, 928, 528, stroke=MUTED)
    s.text(32, 544, "Quiz del tema", size=20)
    s.text(32, 574, "Necesitas ≥ 70 % para aprobar · preguntas nuevas en cada intento",
           size=13, color=MUTED)
    s.text(32, 608, "1. Pregunta de opción múltiple", size=15)
    for i, label in enumerate(("Opción A", "Opción B", "Opción C", "Opción D")):
        s.radio(48, 638 + i * 28, label)
    s.text(32, 762, "2. Pregunta de respuesta corta", size=15)
    s.rect(32, 790, 600, 56)
    s.text(44, 802, "Escribe tu respuesta…", size=13, color=MUTED)
    s.button(768, 802, 160, 44, "Enviar quiz", primary=True)
    return s


def badge() -> Screen:
    s = Screen("07-badge", "7 · Badge (Figma E10; colección en E12)", 640)
    s.top_bar(STUDENT_LINKS, "Logros")
    s.ellipse(400, 84, 160, 160, fill=FILL)
    s.text(480, 154, "Badge", size=18, color=MUTED, anchor="middle")
    s.text(480, 268, "¡Ruta completada!", size=26, anchor="middle")
    s.text(480, 310, "Fundamentos de ML · evaluación final 88 % · 5 oct 2026", size=14,
           color=MUTED, anchor="middle")
    s.button(209, 346, 170, 40, "Descargar imagen", primary=True)
    s.button(395, 346, 170, 40, "Descargar JSON")
    s.button(581, 346, 170, 40, "Copiar enlace")
    s.rect(209, 410, 542, 150)
    rows = (
        ("Emisor", "Maestría en Ciencia de Datos"),
        ("Criterio", "Evaluación final ≥ 80 %"),
        ("Fecha de emisión", "5 oct 2026"),
        ("Formato", "Open Badges (imagen + JSON)"),
    )
    for i, (label, value) in enumerate(rows):
        y = 428 + i * 30
        s.text(229, y, label, size=13, color=MUTED)
        s.text(420, y, value, size=13)
    s.text(480, 590, "Ver todos mis logros  ›", size=14, anchor="middle")
    return s


SCREENS = (login, catalog, profile, diagnostic, path_view, topic, badge)


def main() -> None:
    for build in SCREENS:
        screen = build()
        (OUT_DIR / f"{screen.slug}.excalidraw").write_text(
            json.dumps(screen.to_excalidraw(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (OUT_DIR / f"{screen.slug}.svg").write_text(screen.to_svg(), encoding="utf-8")
        print(f"{screen.slug}: .excalidraw y .svg")


if __name__ == "__main__":
    main()
