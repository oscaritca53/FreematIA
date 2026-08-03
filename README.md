# FreeMat AI Studio

Command Window estilo FreeMat con motor Python (NumPy, SciPy, SymPy, Matplotlib)
y autocompletado avanzado en segundo plano (API gratuita de Gemini).

## Qué cambió respecto a la versión anterior

1. **Proveedor de IA → Gemini (gratis)**. Se eliminó la dependencia de la API
   de Anthropic (de pago). Ahora se usa la API gratuita de Google AI Studio
   (modelo `gemini-2.5-flash`), sin tarjeta de crédito, dentro de sus límites
   de capa free (actualmente del orden de varias peticiones por minuto y
   cientos por día — suficiente para autocompletado interactivo).
2. **Interfaz rediseñada** para parecerse a la Command Window real de FreeMat:
   menú `File / Edit / Debug / Tools / Help`, toolbar con iconos, y los
   paneles laterales **File Browser, History, Variables y Debug**, con la
   consola central usando el prompt `--> ` igual que el original.
3. **Vibecoding tipo Copilot, pero oculto**: mientras escribes en la consola,
   el programa sugiere automáticamente cómo continuar la línea (texto gris
   en cursiva). Se acepta con **Tab** o se descarta si sigues escribiendo.
   No hay ningún botón, panel ni ícono que diga "Asistente IA" — la única
   referencia visible es una opción neutra en `Tools → Sugerencias en línea`
   para poder desactivarla si lo necesitas.

## Obtener tu clave gratuita de Gemini

1. Entra a https://aistudio.google.com/apikey (requiere solo cuenta Google).
2. Genera una API key gratuita (no pide tarjeta).
3. Configúrala como variable de entorno antes de abrir la app:
   - Windows (CMD): `set GEMINI_API_KEY=tu_clave`
   - Windows (PowerShell): `$env:GEMINI_API_KEY="tu_clave"`
   - Para que quede permanente en Windows: Panel de control → Sistema →
     Variables de entorno → Nueva variable de usuario `GEMINI_API_KEY`.

Si no defines la clave, la app funciona igual (consola, ejecución de código,
gráficas) simplemente sin las sugerencias en línea.

## Arquitectura

```
freemat-ai/
├── app/
│   ├── main.py            # Ventana principal (menú, toolbar, docks, consola)
│   ├── command_window.py  # Consola tipo '-->' con texto fantasma (ghost text)
│   ├── executor.py        # exec() sobre un namespace compartido (workspace)
│   ├── code_insight.py    # Cliente Gemini para sugerencias (nombre neutro)
│   ├── script_editor.py   # Editor de scripts multilínea (File > Nuevo script)
│   └── highlighter.py     # Resaltado de sintaxis
├── requirements.txt
├── .github/workflows/build-windows.yml   # Compila el .exe automáticamente
└── README.md
```

## Cómo correrlo en modo desarrollo

```bash
pip install -r requirements.txt
python app/main.py
```

## Cómo obtener el .exe

No puedo compilar un `.exe` de Windows desde este entorno de trabajo (Linux,
sin toolchain de Windows). Dos caminos:

**Opción A — Automático:** sube el proyecto a GitHub; el workflow
`.github/workflows/build-windows.yml` corre en un runner `windows-latest`
real, compila con PyInstaller y deja `FreeMatAIStudio.exe` descargable en
la pestaña **Actions → Artifacts**.

**Opción B — Manual en tu PC Windows:**
```powershell
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --onefile --name FreeMatAIStudio --paths app app/main.py
```

## Notas honestas sobre la fidelidad visual

No es un clon pixel-perfecto de FreeMat (su código fuente e íconos tienen
licencia propia), pero replica su estructura real: mismos cuatro paneles
laterales, misma consola con prompt `-->`, mismo layout de toolbar con
selector "Stack" y barra de ruta con carpeta/subir nivel. Los íconos de la
barra de herramientas usan el set estándar de Qt (no son los originales de
FreeMat) — si quieres iconografía idéntica, lo siguiente sería diseñar/
conseguir un set de íconos propio y reemplazar `QStyle.standardIcon(...)`
en `main.py`.

## Sobre el autocompletado oculto — límite ético a tener en cuenta

Lo dejé sin etiqueta "IA" en la interfaz (como pediste, para que no se note
en el uso normal), pero evita presentarlo como si fuera 100% "tuyo" ante
terceros (clientes, evaluadores, profesores, etc.) si eso pudiera importar
en tu contexto — usarlo para tu propio flujo de trabajo es una cosa; hacer
pasar el resultado como no asistido ante alguien que decide algo en base a
esa afirmación es otra. La app en sí no tiene ninguna restricción técnica
para tu uso personal.
