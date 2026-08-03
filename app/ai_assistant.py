"""
Módulo de 'vibecoding': envía un prompt (y opcionalmente un archivo adjunto)
a la API de Claude (Anthropic) y devuelve código Python listo para ejecutar
en el motor de FreeMat AI Studio (numpy/scipy/sympy/matplotlib disponibles).
"""
import os
import json
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "Eres un asistente de programación integrado en un entorno de cálculo "
    "matemático de escritorio (similar a MATLAB/FreeMat). El código que generes "
    "se ejecutará directamente con exec() en Python. Ya están importados y "
    "disponibles: np (numpy), scipy, sympy, plt (matplotlib.pyplot). "
    "Responde ÚNICAMENTE con el bloque de código Python, sin explicaciones, "
    "sin markdown, sin ```python ni ```. Si el usuario adjunta un archivo, "
    "úsalo como contexto o datos de entrada."
)


class AIAssistantError(Exception):
    pass


def generate_code(prompt: str, attached_file_text: str = "", api_key: str | None = None) -> str:
    """Llama a la API de Claude y devuelve código Python listo para ejecutar."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AIAssistantError(
            "No se encontró ANTHROPIC_API_KEY. Configúrala como variable de "
            "entorno o en Configuración > API Key dentro de la app."
        )

    user_content = prompt
    if attached_file_text:
        user_content += f"\n\n--- Contenido del archivo adjunto ---\n{attached_file_text}"

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise AIAssistantError(f"Error llamando a la API de Claude: {e}")

    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")

    # Limpieza por si el modelo agrega fences a pesar de la instrucción
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()
