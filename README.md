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

## Entrada rápida (prompt/archivo → código)

`Ctrl+Shift+Space` (o `Tools → Entrada rápida`) abre un panel flotante sobre
la consola, tipo paleta de comandos:

- Escribes una instrucción o adjuntas un archivo (botón "Adjuntar").
- **Insertar en consola**: genera el código y lo coloca en la línea de
  entrada actual, sin ejecutarlo (revisas antes de correrlo).
- **Insertar y ejecutar**: lo genera y lo corre de inmediato, como si lo
  hubieras escrito tú y presionado Enter.
- `Esc` o el botón "Cerrar" lo oculta.

Es una herramienta más de la app (aparece en el menú Tools con su atajo),
no un panel diseñado para pasar desapercibido en pantalla compartida o
grabación — simplemente no ocupa espacio fijo en la barra de herramientas,
igual que Ctrl+Shift+P en VS Code.

## Obtener tu clave gratuita de Gemini y configurarla en la app

1. Entra a https://aistudio.google.com/apikey (requiere solo cuenta Google).
2. Genera una API key gratuita (no pide tarjeta).
3. Dentro de la app: menú **Tools → Configuración...** → pega la clave →
   **Save**. Se guarda cifrada-en-reposo no, pero sí en un archivo local
   propio (`%USERPROFILE%\.freemat_ai_studio\config.json` en Windows), no
   depende de variables de entorno del sistema — así funciona igual desde
   el `.exe` compilado sin que tengas que tocar el Panel de Control.

Si no configuras la clave, la app funciona igual (consola, ejecución de
código, gráficas); simplemente no aparecen las sugerencias en línea.

## Archivos .m — motor de compilación real (no solo la extensión)

A diferencia de la versión anterior (donde `.m` era solo el nombre de
archivo pero el contenido seguía siendo Python), ahora hay un **compilador
real de un subconjunto de MATLAB/FreeMat**, en `app/mengine/`:

```
mengine/
├── m_lexer.py       # Tokenizador (números, strings, operadores .* ./ .^ ' etc.)
├── m_ast.py          # Nodos del árbol de sintaxis
├── m_parser.py       # Parser recursive-descent con la precedencia real de MATLAB
├── m_transpiler.py   # AST -> código Python (usa m_runtime como 'mrt')
├── m_runtime.py       # Semántica MATLAB sobre NumPy (índices desde 1, 'end', *, etc.)
└── m_engine.py        # Une todo y reproduce el eco de consola de FreeMat
```

**Soportado:** asignaciones, `if/elseif/else/end`, `for/end`, `while/end`,
`switch/case/otherwise/end`, `try/catch/end`, `function...end` (con una o
varias salidas: `[a,b]=f(x)`), matrices `[1 2; 3 4]`, indexado `A(i,j)` y
`A(end)` desde 1 (no desde 0), `*` como multiplicación matricial vs `.*`
elemento a elemento (igual para `/ \ ^` vs `./ .\ .^`), transposición `'`,
rangos `1:2:10`, funciones anónimas `@(x) x^2`, structs simples `s.campo`,
comentarios `%`, auto-crecimiento de arreglos (`A(5)=1` sin declarar `A`),
variable `ans`, supresión de salida con `;`, y funciones integradas: `zeros,
ones, eye, rand, size, length, disp, fprintf, sum, mean, max, min, sort,
find, sin/cos/tan, plot, figure`, etc.

**No soportado (limitación honesta):** cell arrays `{}` como tipo completo,
clases (`classdef`), arreglos de más de 2 dimensiones, números complejos
más allá de la suma básica, y el indexado lineal usa orden row-major de
NumPy en vez del column-major nativo de MATLAB (solo importa en indexado
lineal de matrices 2D con un único índice, ej. `A(3)` sobre una matriz).

Prueba rápida:
```matlab
A = [1 2 3; 4 5 6];
b = A(1, end)
function y = sq(x)
  y = x^2;
end
sq(5)
```


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
