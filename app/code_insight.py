"""
Motor de 'code insight': completa la línea que el usuario está escribiendo
(autocompletado) y genera bloques completos desde un prompt (panel rápido).
Soporta dos proveedores intercambiables (config.get_provider()):
  - 'cloud': Gemini (Google AI Studio, capa gratuita, requiere internet + clave)
  - 'local': Ollama (http://localhost:11434 por defecto, sin internet ni clave,
    requiere tener Ollama instalado y un modelo descargado)

Nota de diseño: este módulo se mantiene desacoplado de la interfaz a propósito
(sin iconos ni paneles dedicados en la barra principal) para integrarse como
una capacidad de fondo, similar a como un IDE ofrece autocompletado avanzado.

Nota de robustez: Google renueva la familia de modelos Gemini con frecuencia
y retira nombres de modelo (lo que da errores 404 aunque la clave y el
endpoint sean correctos). Por eso _call_gemini() prueba una lista de
modelos candidatos en orden y solo falla si todos fallan.

Nota de calidad: en la nube usamos modelos distintos según la tarea. Para el
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

MODEL_CANDIDATES_FAST = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.0-flash",
]

MODEL_CANDIDATES_QUALITY = [
    "gemini-2.5-pro",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

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
            "No hay clave configurada. Ve a Tools → Configuración... y agrégala, "
            "o cambia el proveedor a 'Local' si tienes Ollama instalado."
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
            if e.code in (404, 429):
                last_error = f"{model}: HTTP {e.code}"
                continue
            raise RuntimeError(f"{model}: HTTP {e.code} {e.reason}")
        except Exception as e:
            last_error = f"{model}: {e}"
            continue

    raise RuntimeError(
        f"Ningún modelo en la nube respondió (último error: {last_error}). "
        "Revisa tu clave en Tools → Configuración, o que el proyecto de "
        "Google AI Studio tenga la API habilitada."
    )


def _call_ollama(system_instruction: str, user_content: str, max_tokens: int,
                  temperature: float, timeout: int) -> str:
    """Llama a un servidor Ollama local (http://localhost:11434 por defecto).
    Requiere tener Ollama instalado y corriendo, con el modelo ya descargado
    (ej. 'ollama pull qwen2.5-coder:7b')."""
    base_url = config.get_local_url().rstrip("/")
    model = config.get_local_model()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"No se pudo conectar a Ollama en {base_url}. ¿Está corriendo? "
            f"(abre una terminal y ejecuta 'ollama serve'). Detalle: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"Error consultando el modelo local '{model}': {e}")


def _call_llm(system_instruction: str, user_content: str, max_tokens: int,
              temperature: float, timeout: int, cloud_model_list: list[str]) -> str:
    """Despacha al proveedor activo (config.get_provider(): 'cloud' o 'local')."""
    if config.get_provider() == "local":
        return _call_ollama(system_instruction, user_content, max_tokens, temperature, timeout)
    return _call_gemini(system_instruction, user_content, max_tokens, temperature,
                         timeout, cloud_model_list)


def fetch_completion(current_line: str, history: list[str]) -> str:
    if config.get_provider() == "cloud" and not config.get_api_key():
        return ""
    if not current_line.strip():
        return ""
    context = "\n".join(history[-6:])
    prompt = f"Historial reciente:\n{context}\n\nLínea actual incompleta:\n{current_line}"
    try:
        text = _call_llm(INSTRUCTION, prompt, max_tokens=40, temperature=0.2,
                          timeout=8, cloud_model_list=MODEL_CANDIDATES_FAST)
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
    text = _call_llm(GENERATION_INSTRUCTION, user_content, max_tokens=1500,
                      temperature=0.2, timeout=60, cloud_model_list=MODEL_CANDIDATES_QUALITY)
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
