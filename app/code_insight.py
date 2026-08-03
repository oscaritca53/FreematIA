"""
Motor de 'code insight': completa la línea que el usuario está escribiendo,
al estilo de un autocompletado avanzado. Usa la API gratuita de Gemini
(Google AI Studio, capa free, sin tarjeta de crédito).

Nota de diseño: este módulo se mantiene desacoplado de la interfaz a propósito
(sin iconos ni paneles dedicados) para integrarse como una capacidad de fondo
del editor, similar a como un IDE ofrece autocompletado avanzado.
"""
import os
import json
import urllib.request

from PySide6.QtCore import QThread, Signal

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

INSTRUCTION = (
    "Eres un motor de autocompletado de código para una consola de cálculo "
    "numérico en Python (numpy=np, scipy, sympy, matplotlib=plt ya están "
    "disponibles). Te doy el historial reciente y la línea actual incompleta. "
    "Responde SOLO con el texto que continúa la línea actual (la parte que "
    "falta), sin repetir lo ya escrito, sin explicaciones, sin markdown, "
    "sin comillas. Si no hay una continuación razonable, responde con una "
    "cadena vacía. Máximo una línea."
)


def _api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def fetch_completion(current_line: str, history: list[str]) -> str:
    api_key = _api_key()
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
