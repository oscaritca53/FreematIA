"""Motor .m: compila código MATLAB/FreeMat a Python y lo ejecuta,
reproduciendo el comportamiento de la consola (eco 'nombre = valor',
supresión con ';', variable 'ans', etc.)."""
import io
import contextlib
import traceback

from . import m_runtime as mrt
from .m_lexer import LexError
from .m_parser import parse, ParseError
from .m_transpiler import transpile, TranspileError

BUILTIN_NAMES = [
    "zeros", "ones", "eye", "rand", "randn", "linspace", "size", "length",
    "numel", "isempty", "disp", "fprintf", "printf", "sprintf",
    "figure", "plot", "hold", "xlabel", "ylabel", "title", "legend",
    "grid", "subplot", "mod", "rem", "sqrt", "exp", "log", "log2", "log10",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "floor", "ceil",
    "error", "warning",
]

# nombres cuyo identificador MATLAB choca con builtins/keywords de Python
ALIAS_NAMES = {
    "max": "max_", "min": "min_", "sort": "sort_", "sum": "sum_",
    "mean": "mean_", "abs": "abs_", "round": "round_", "find": "find",
}


def make_namespace() -> dict:
    ns = {"mrt": mrt, "np": mrt.np}
    for name in BUILTIN_NAMES:
        ns[name] = getattr(mrt, name)
    for matlab_name, runtime_name in ALIAS_NAMES.items():
        ns[matlab_name] = getattr(mrt, runtime_name)
    ns["class_"] = mrt.class_
    ns["__mdisplay__"] = lambda name, value: print(mrt.display_result(name, value), end="")
    return ns


def to_python(source: str) -> str:
    """Solo transpila (útil para depuración/inspección)."""
    tree = parse(source)
    return transpile(tree)


def run(source: str, namespace: dict):
    """Compila y ejecuta código .m sobre el namespace dado.
    Devuelve (salida_texto, error_o_None, lista_de_figuras)."""
    try:
        tree = parse(source)
        py_code = transpile(tree)
    except LexError as e:
        return "", f"Error léxico: {e}", []
    except ParseError as e:
        return "", f"Error de sintaxis: {e}", []
    except TranspileError as e:
        return "", f"Error de compilación: {e}", []

    buf = io.StringIO()
    error = None
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(py_code, "<m>", "exec"), namespace)
    except Exception:
        tb = traceback.format_exc()
        last_line = tb.strip().splitlines()[-1]
        error = f"??? {last_line}"

    figures = [mrt.plt.figure(n) for n in mrt.plt.get_fignums()]
    return buf.getvalue(), error, figures


def visible_variables(namespace: dict):
    skip = set(BUILTIN_NAMES) | set(ALIAS_NAMES.keys()) | {"mrt", "np", "class_", "__mdisplay__", "__builtins__", "ans"}
    out = []
    for name, value in namespace.items():
        if name in skip or name.startswith("_"):
            continue
        if callable(value):
            continue
        out.append((name, mrt.class_(value), mrt.format_value(value).replace("\n", " ")[:60]))
    return sorted(out)
