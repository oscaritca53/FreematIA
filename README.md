
# FreeMat AI Studio

(Ver historial de cambios más abajo — este README se ha ido actualizando
turno a turno con cada mejora.)

## Sobre "empaquetar Ollama dentro del .exe"

No es viable literalmente: un modelo de Ollama como `qwen2.5-coder:7b` pesa
4-5 GB, y Ollama es un servidor aparte, no una librería embebible en un
`.exe` de PyInstaller. Meterlo en un `--onefile` produciría un ejecutable
de varios GB que además se re-extrae completo cada vez que lo abres.

**Lo que sí se agregó, como equivalente práctico:** en
`Tools → Configuración → Preparar IA local`, la app ahora:
1. Detecta si Ollama está instalado (si no, te da el link de descarga).
2. Arranca el servidor de Ollama automáticamente si no está corriendo.
3. Descarga el modelo configurado automáticamente si no lo tienes, con
   una barra de progreso en vivo.

Todo esto sin que abras una terminal tú mismo. Está en
`app/ollama_manager.py`. Lo probé simulando los tres escenarios (Ollama no
instalado, servidor apagado + modelo faltante, todo ya listo) antes de
entregarlo.

## Sobre el permiso de administrador

El `.exe` no debería pedir permisos de administrador: solo escribe en
`%USERPROFILE%\.freemat_ai_studio` (configuración) y no toca Program
Files ni el registro. Si Windows muestra una advertencia, es el
SmartScreen por ser un ejecutable sin firma digital — distinto a pedir
admin — se resuelve con "Más información → Ejecutar de todas formas".

## Entrada rápida ahora es un chat real (multi-turno)

`Ctrl+Shift+Space` ya no es un formulario de una sola pasada — es un chat
de ida y vuelta con historial:

- Escribes, la IA responde (en prosa y/o con bloques de código ```matlab```).
- Puedes pedir correcciones sobre lo último que generó ("ese bucle está
  mal, arréglalo") y mantiene el contexto de la conversación.
- **Insertar último código** / **Insertar y ejecutar**: toman el bloque de
  código de la respuesta más reciente del asistente (lo extraen del
  markdown automáticamente) y lo llevan a la consola.
- **Nueva conversación**: limpia el historial para empezar de cero.
- El panel ya NO se cierra solo al insertar/ejecutar — se queda abierto
  para que sigas la conversación, como cualquier chat.

## Validación y auto-corrección de código generado

Este fue un fix importante de robustez: antes, si el modelo generaba
código truncado o con errores (algo que puede pasar con cualquier LLM,
sin importar cuán bueno sea), ese código roto llegaba directo a la
consola sin que nadie lo revisara.

Ahora `code_insight.generate_full()`:
1. Genera el código.
2. Lo valida con **nuestro propio parser real** (`mengine.m_engine.validate`),
   que además detecta heurísticamente cuando el código quedó cortado a la
   mitad (termina en una coma/operador colgante, o tiene paréntesis sin
   cerrar) — algo que un parser tolerante normalmente no marcaría como
   error de sintaxis.
3. Si falla, le muestra al modelo el error exacto y le da **una
   oportunidad de corregirse** dentro de la misma conversación.
4. Si sigue fallando, te lo dice claramente en vez de entregarte algo
   roto en silencio.

Probé este flujo completo simulando tu caso real (el código truncado del
método de Euler) y confirmé que detecta el corte, pide la corrección, y
solo entrega la versión ya validada.
