"""
Motor de 'code insight': completa la línea que el usuario está escribiendo
(autocompletado) y genera bloques completos desde un prompt (panel rápido).
Usa la API gratuita de Gemini (Google AI Studio, capa free, sin tarjeta).

Nota de diseño: este módulo se mantiene desacoplado de la interfaz a propósito
(sin iconos ni paneles dedicados en la barra principal) para integrarse como
una capacidad de fondo, similar a como un IDE ofrece autocompletado avanzado.

Nota de robustez: Google renueva la familia de modelos Gemini con frecuencia
y retira nombres de modelo (lo que da errores 404 aunque la clave y el
endpoint sean correctos). Por eso _call_gemini() prueba una lista de
modelos candidatos en orden y solo falla si todos fallan.

Nota de calidad: usamos modelos distintos según la tarea. Para el
autocompletado de una línea (se dispara constantemente mientras escribes)
priorizamos velocidad. Para la generación de bloques completos desde el
panel rápido (la disparas tú, con menos frecuencia) priorizamos calidad,
incluyendo un modelo 'Pro' que también tiene cupo gratuito (más limitado,
pero mucho más capaz para razonar sobre una sintaxis no estándar).
"""
import json
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

import config

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Rápidos primero: para el autocompletado de una línea, donde la latencia
# importa más que la sofisticación de la respuesta.
MODEL_CANDIDATES_FAST = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.0-flash",
]

# Modelos de mayor calidad primero: para la generación de bloques completos
# desde el panel rápido. gemini-2.5-pro sigue teniendo cupo gratuito (más
# bajo, ~50 solicitudes/día) pero razona bastante mejor sobre instrucciones
# estrictas como "no uses esta sintaxis", que es justo lo que necesitamos.
MODEL_CANDIDATES_QUALITY = [
    "gemini-2.5-pro",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

# ---------------------------------------------------------------------
# "Hoja de referencia" real del motor .m (mengine/). El motor NO es
# MATLAB/Octave completo: es un subconjunto propio. Si el prompt del
# modelo no deja esto clarísimo, el modelo (entrenado sobre MATLAB real)
# tiende a usar cell arrays, classdef, strsplit, regexp, structs
# complejos, etc. -- cosas que nuestro transpilador no soporta y que
# producen errores o resultados "tontos". Esta lista es la causa más
# probable de que las respuestas parecieran "incapaces".
# ---------------------------------------------------------------------
ENGINE_SPEC = """
Sintaxis soportada por ESTE motor .m (no es MATLAB/Octave completo, es un
subconjunto propio -- NO uses nada fuera de esta lista):

PERMITIDO:
- Asignaciones, operadores + - * / \\ ^ .* ./ .^ , transposición ' 
- if/elseif/else/end, for i=a:b/end, while/end, switch/case/otherwise/end,
  try/catch/end, break, continue
- function y = nombre(x) ... end  (incluye [a,b] = f(x) con varias salidas)
- Matrices literales [1 2; 3 4], rangos 1:2:10, comentarios con %
- Indexado 1-based: A(i), A(i,j), A(end), A(2:end)
- Structs simples: s.campo = valor (solo campos planos, sin arreglos de structs)
- Funciones anónimas: f = @(x) x^2
- Funciones disponibles: zeros, ones, eye, rand, randn, linspace, size,
  length, numel, isempty, disp, fprintf, printf, sprintf, error, warning,
  sum, mean, max, min, sort, find, abs, sqrt, exp, log, log2, log10, sin,
  cos, tan, asin, acos, atan, atan2, floor, ceil, round, mod, rem, class,
  figure, plot, hold, xlabel, ylabel, title, legend, grid, subplot

PROHIBIDO (NO existen en este motor, no las generes bajo ninguna circunstancia):
- Cell arrays con llaves {} como tipo de dato (ej. c = {1, 'a', [1 2]})
- classdef / programación orientada a objetos
- strsplit, regexp, containers.Map, arrayfun, cellfun, string() (tipo string)
- Arreglos de más de 2 dimensiones
- Cualquier función de toolbox que no esté en la lista de arriba

Si el prompt del usuario pide algo que requeriría una función no listada,
resuélvelo con las funciones disponibles o con un bucle explícito en vez
de inventar una función que no existe.
"""

INSTRUCTION = (
    "Eres un motor de autocompletado de código para una consola de cálculo "
    "numérico. " + ENGINE_SPEC + "\n"
    "Te doy el historial reciente y la línea actual incompleta. Responde "
    "SOLO con el texto que continúa la línea actual (la parte que falta), "
    "sin repetir lo ya escrito, sin explicaciones, sin markdown, sin "
    "comillas. Si no hay una continuación razonable, responde con una "
    "cadena vacía. Máximo una línea."
)

GENERATION_INSTRUCTION = (
    "Eres un generador de código para una consola de cálculo numérico. "
    + ENGINE_SPEC + "\n"
    "Responde ÚNICAMENTE con el bloque de código .m que resuelve lo que "
    "pide el usuario, usando exclusivamente la sintaxis y funciones "
    "permitidas arriba. Sin explicaciones, sin markdown, sin ```. Si el "
    "código produce una gráfica, usa figure/plot normalmente."
)


def _call_gemini(system_instruction: str, user_content: str, max_tokens: int,
                  temperature: float, timeout: int, model_list: list[str]) -> str:
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
    for model in model_list:
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
            # 404 = modelo retirado/no disponible; 429 = cupo agotado -> probar el siguiente
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
        text = _call_gemini(INSTRUCTION, prompt, max_tokens=40, temperature=0.2,
                             timeout=8, model_list=MODEL_CANDIDATES_FAST)
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
    text = _call_gemini(GENERATION_INSTRUCTION, user_content, max_tokens=1500,
                         temperature=0.2, timeout=40, model_list=MODEL_CANDIDATES_QUALITY)
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
