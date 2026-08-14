"""
Motor de 'code insight': completa la línea que el usuario está escribiendo,
al estilo de un autocompletado avanzado. Usa la API gratuita de Gemini
(Google AI Studio, capa free, sin tarjeta de crédito).

Nota de diseño: este módulo se mantiene desacoplado de la interfaz a propósito
(sin iconos ni paneles dedicados) para integrarse como una capacidad de fondo
del editor, similar a como un IDE ofrece autocompletado avanzado.
"""
import json
import urllib.request

from PySide6.QtCore import QThread, Signal

import config

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

INSTRUCTION = (
    "Eres un motor de autocompletado de código para una consola de cálculo "
    "numérico estilo MATLAB/FreeMat (archivos .m). La sintaxis es MATLAB: "
    "asignaciones sin 'def', matrices con [1 2; 3 4], bloques if/for/while "
    "terminados en 'end', comentarios con %, funciones zeros/ones/size/disp/ "
    "fprintf/plot ya disponibles, indexado desde 1 con A(i,j) y A(end). "
    "Te doy el historial reciente y la línea actual incompleta. Responde "
    "SOLO con el texto que continúa la línea actual (la parte que falta), "
    "sin repetir lo ya escrito, sin explicaciones, sin markdown, sin "
    "comillas. Si no hay una continuación razonable, responde con una "
    "cadena vacía. Máximo una línea."
)


def fetch_completion(current_line: str, history: list[str]) -> str:
    api_key = config.get_api_key()
    if not api_key or not current_line.strip():
        return ""

    context = "\n".join(history[-6:])
    prompt = f"Historial reciente:\n{context}\n\nLínea actual incompleta:\n{current_line}"

    payload = {
        "system_instruction": {"parts": [{"text": INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 40, "temperature": 0.2},
    }

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        text = text.strip("`").strip()
        if "\n" in text:
            text = text.split("\n", 1)[0]
        return text
    except Exception:
        return ""


GENERATION_INSTRUCTION = (
    "Eres un generador de código para una consola de cálculo numérico estilo "
    "MATLAB/FreeMat (archivos .m). Sintaxis MATLAB: asignaciones sin 'def', "
    "matrices con [1 2; 3 4], bloques if/for/while/function terminados en "
    "'end', comentarios con %, indexado desde 1 con A(i,j) y A(end). "
    "Funciones ya disponibles: zeros, ones, eye, rand, size, length, disp, "
    "fprintf, sum, mean, max, min, sort, find, sin/cos/tan, plot, figure, etc. "
    "Responde ÚNICAMENTE con el bloque de código .m, sin explicaciones, sin "
    "markdown, sin ``` "
)


def generate_full(prompt: str, attached_text: str = "") -> str:
    """Genera un bloque de código .m completo a partir de un prompt
    (y opcionalmente el contenido de un archivo adjunto)."""
    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError(
            "No hay clave configurada. Ve a Tools → Configuración... y agrégala."
        )

    user_content = prompt
    if attached_text:
        user_content += f"\n\n--- Contenido del archivo adjunto ---\n{attached_text}"

    payload = {
        "system_instruction": {"parts": [{"text": GENERATION_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.3},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts).strip()
    text = text.strip("`")
    if text.startswith("matlab\n"):
        text = text[len("matlab\n"):]
    return text.strip()


class GenerationWorker(QThread):
    """Genera un bloque completo en segundo plano (prompt + archivo)."""
    result_ready = Signal(str)
    error_raised = Signal(str)

    def __init__(self, prompt: str, attached_text: str = ""):
        super().__init__()
        self.prompt = prompt
        self.attached_text = attached_text

    def run(self):
        try:
            code = generate_full(self.prompt, self.attached_text)
            self.result_ready.emit(code)
        except Exception as e:
            self.error_raised.emit(str(e))


class SuggestionWorker(QThread):
    """Corre la petición en segundo plano para no bloquear la escritura."""
    suggestion_ready = Signal(str, str)  # (línea_para_la_que_se_pidió, sugerencia)

    def __init__(self, current_line: str, history: list[str]):
        super().__init__()
        self.current_line = current_line
        self.history = history

    def run(self):
        suggestion = fetch_completion(self.current_line, self.history)
        self.suggestion_ready.emit(self.current_line, suggestion)
