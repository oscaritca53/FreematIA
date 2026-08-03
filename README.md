# FreeMat AI Studio

Entorno de escritorio visual para cálculo matemático (estilo FreeMat/MATLAB) con
motor Python (NumPy, SciPy, SymPy, Matplotlib) y asistente de **vibecoding**
integrado usando la API de Claude.

## Arquitectura

```
freemat-ai/
├── app/
│   ├── main.py          # Ventana principal (PySide6): editor, consola, gráficas, panel IA
│   ├── highlighter.py    # Resaltado de sintaxis del editor
│   ├── executor.py       # Motor de ejecución (QThread, captura stdout, figuras matplotlib)
│   └── ai_assistant.py   # Cliente Claude API: prompt/archivo -> código Python
├── requirements.txt
├── .github/workflows/build-windows.yml   # Compila el .exe automáticamente
└── README.md
```

- **UI**: PySide6 (Qt6) — editor con resaltado de sintaxis, consola de salida en vivo,
  pestañas de gráficas embebidas (Matplotlib), panel lateral de IA.
- **Ejecución**: el código del editor se corre con `exec()` dentro de un `QThread`
  separado (no congela la interfaz), con `np`, `scipy`, `sympy`, `plt` ya inyectados
  en el namespace — igual que la filosofía de FreeMat.
- **Vibecoding**: el panel de IA envía tu prompt (+ archivo adjunto opcional) a la
  API de Claude, recibe código Python listo, lo inserta en el editor y opcionalmente
  lo ejecuta automáticamente — el equivalente a Copilot pero especializado en cálculo.

## Cómo correrlo en tu PC (modo desarrollo)

```bash
pip install -r requirements.txt
set ANTHROPIC_API_KEY=tu_api_key      # (en Windows CMD; en PowerShell: $env:ANTHROPIC_API_KEY="...")
python app/main.py
```

## Cómo obtener el .exe

No puedo compilar un `.exe` de Windows desde este entorno (es Linux, sin toolchain
de Windows). Dos caminos reales:

**Opción A — Automático (recomendado):**
1. Sube esta carpeta a un repositorio de GitHub.
2. El workflow `.github/workflows/build-windows.yml` ya incluido se dispara solo
   en cada push (o manualmente desde la pestaña "Actions" → "Run workflow").
3. Corre en un runner **windows-latest** real, instala PyInstaller y genera
   `FreeMatAIStudio.exe`.
4. Descárgalo desde la pestaña **Actions → tu ejecución → Artifacts**.

**Opción B — Manual, en tu propia PC con Windows:**
```powershell
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --onefile --name FreeMatAIStudio --paths app app/main.py
```
El `.exe` queda en `dist/FreeMatAIStudio.exe`.

## Próximos pasos sugeridos (roadmap)

- Autocompletado en línea (estilo Copilot) usando streaming de la API mientras se escribe.
- Sandbox de ejecución más estricto (subprocess aislado) si vas a ejecutar código de terceros.
- Soporte multi-lenguaje (Octave/MATLAB syntax) vía un transpilador.
- Firma de código del .exe para evitar advertencias de SmartScreen en Windows.
