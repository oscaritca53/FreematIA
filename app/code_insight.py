"""
Motor de 'code insight': completa la línea que el usuario está escribiendo,
al estilo de un autocompletado avanzado. Usa la API gratuita de Gemini
(Google AI Studio, capa free, sin tarjeta de crédito).

Nota de diseño: este módulo se mantiene desacoplado de la interfaz a propósito
(sin iconos ni paneles dedicados) para integrarse como una capacidad de fondo
del editor, similar a como un IDE ofrece autocompletado avanzado.

Nota de robustez: Google renueva la familia de modelos Gemini con frecuencia
y retira nombres de modelo (lo que da errores 404 aunque la clave y el
endpoint sean correctos). Por eso _call_gemini() prueba una lista de
modelos candidatos en orden y solo falla si todos fallan.
"""
import json
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

import config

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Orden de preferencia: el más nuevo/recomendado primero, con más antiguos
# como respaldo por si el primero fue retirado o no está habilitado en tu
# proyecto. Si en el futuro todos fallan, actualiza esta lista.
MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

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


def _call_gemini(system_instruction: str, user_content: str, max_tokens: int,
                  temperature: float, timeout: int) -> str:
    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError(
            "No hay clave configurada. Ve a Tools → Configuración... y agrégala."
        )

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }
    body = json.dumps(payload).encode("utf-8")

    last_error = None
    for model in MODEL_CANDIDATES:
        url = f"{BASE_URL}/{model}:generateContent"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except urllib.error.HTTPError as e:
            # 404 = modelo retirado/no disponible en este proyecto -> probar el siguiente
            # 429 = límite de la capa gratuita alcanzado -> probar el siguiente
            if e.code in (404, 429):
                last_error = f"{model}: HTTP {e.code}"
                continue
            raise RuntimeError(f"{model}: HTTP {e.code} {e.reason}")
        except Exception as e:
            last_error = f"{model}: {e}"
            continue

    raise RuntimeError(
        f"Ningún modelo disponible respondió (último error: {last_error}). "
        "Revisa tu clave en Tools → Configuración, o que el proyecto de "
        "Google AI Studio tenga la API habilitada."
    )


def fetch_completion(current_line: str, history: list[str]) -> str:
    if not config.get_api_key() or not current_line.strip():
        return ""
    context = "\n".join(history[-6:])
    prompt = f"Historial reciente:\n{context}\n\nLínea actual incompleta:\n{current_line}"
    try:
        text = _call_gemini(INSTRUCTION, prompt, max_tokens=40, temperature=0.2, timeout=8)
    except Exception:
        return ""
    text = text.strip("`").strip()
    if "\n" in text:
        text = text.split("\n", 1)[0]
    return text


def generate_full(prompt: str, attached_text: str = "") -> str:
    """Genera un bloque de código .m completo a partir de un prompt
    (y opcionalmente el contenido de un archivo adjunto)."""
    user_content = prompt
    if attached_text:
        user_content += f"\n\n--- Contenido del archivo adjunto ---\n{attached_text}"
    text = _call_gemini(GENERATION_INSTRUCTION, user_content, max_tokens=1200,
                         temperature=0.3, timeout=30)
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
