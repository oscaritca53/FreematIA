"""
Runtime del motor .m: implementa la semántica de MATLAB/FreeMat sobre NumPy
(indexado desde 1, 'end', operadores de matriz vs elemento-a-elemento,
auto-crecimiento de arreglos, formato de salida estilo consola FreeMat).
"""
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt

COLON = object()  # sentinela para ':'


# ---------------------------------------------------------------- estructuras
class Struct:
    """Emula un struct de MATLAB (campos dinámicos)."""
    def __init__(self):
        object.__setattr__(self, "_fields", {})

    def __getattr__(self, name):
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self._fields[name] = value

    def __repr__(self):
        items = ", ".join(f"{k}: {v!r}" for k, v in self._fields.items())
        return f"struct({items})"


def get_field(obj, name):
    return getattr(obj, name)


# ---------------------------------------------------------------- conversión de índices
def _to_zero_based(idx):
    if idx is COLON:
        return slice(None)
    if isinstance(idx, (int, np.integer)):
        return int(idx) - 1
    arr = np.asarray(idx)
    return (arr - 1).astype(int)


def dim_end(obj, axis, nargs):
    """Resuelve la palabra clave 'end' dentro de un índice."""
    if obj is None:
        return 0
    arr = np.asarray(obj) if not isinstance(obj, np.ndarray) else obj
    if nargs == 1:
        return arr.size
    if arr.ndim == 0:
        return 1
    if axis < arr.ndim:
        return arr.shape[axis]
    return 1


def get(obj, *idx):
    """Despacho universal: si obj es invocable -> llamada de función;
    si no -> indexación estilo MATLAB (1-based)."""
    if callable(obj):
        real_args = [None if i is COLON else i for i in idx]
        return obj(*real_args)

    arr = obj
    is_np = isinstance(arr, np.ndarray)
    if not is_np and isinstance(arr, (list, tuple)):
        arr = np.array(arr)
        is_np = True

    if not is_np:
        if len(idx) == 1 and (idx[0] is COLON or idx[0] == 1):
            return arr
        raise IndexError("Índice fuera de rango para un escalar")

    if len(idx) == 1:
        conv = _to_zero_based(idx[0])
        flat = arr.reshape(-1, order="F") if arr.ndim > 1 else arr
        result = flat[conv]
        return result
    if len(idx) == 2:
        i, j = _to_zero_based(idx[0]), _to_zero_based(idx[1])
        return arr[i, j]
    raise IndexError("Solo se soportan hasta 2 dimensiones de indexado")


def set_index(container, idx, value):
    """Asignación con auto-crecimiento, ej. A(3)=5 o A(2,4)=1 cuando A no existe
    o el índice excede el tamaño actual."""
    if len(idx) == 1:
        i = idx[0]
        if container is None:
            top = int(i) if isinstance(i, (int, np.integer)) else int(np.max(i))
            container = np.zeros(top)
        elif np.asarray(container).size and isinstance(i, (int, np.integer)) and i > container.size:
            container = np.concatenate([np.ravel(container), np.zeros(int(i) - container.size)])
        conv = _to_zero_based(i)
        flat = container.reshape(-1) if container.ndim > 1 else container
        flat[conv] = value
        return container
    else:
        i, j = idx[0], idx[1]
        if container is None:
            rows = int(i) if isinstance(i, (int, np.integer)) else int(np.max(i))
            cols = int(j) if isinstance(j, (int, np.integer)) else int(np.max(j))
            container = np.zeros((rows, cols))
        else:
            rows, cols = container.shape
            need_r = int(i) if isinstance(i, (int, np.integer)) else int(np.max(i))
            need_c = int(j) if isinstance(j, (int, np.integer)) else int(np.max(j))
            if need_r > rows or need_c > cols:
                new = np.zeros((max(rows, need_r), max(cols, need_c)))
                new[:rows, :cols] = container
                container = new
        ci, cj = _to_zero_based(i), _to_zero_based(j)
        container[ci, cj] = value
        return container


def set_field(container, name, value):
    if container is None:
        container = Struct()
    setattr(container, name, value)
    return container


# ---------------------------------------------------------------- operadores
def transpose(x):
    if isinstance(x, np.ndarray):
        return x.T
    return x


def mtimes(a, b):
    a_is_scalar = np.isscalar(a) or (isinstance(a, np.ndarray) and a.ndim == 0)
    b_is_scalar = np.isscalar(b) or (isinstance(b, np.ndarray) and b.ndim == 0)
    if a_is_scalar or b_is_scalar:
        return a * b
    a_arr, b_arr = np.asarray(a), np.asarray(b)
    if a_arr.ndim <= 1 or b_arr.ndim <= 1:
        return a_arr * b_arr if a_arr.shape == b_arr.shape else np.dot(a_arr, b_arr)
    return a_arr @ b_arr


def mrdivide(a, b):
    if np.isscalar(b) or (isinstance(b, np.ndarray) and b.ndim == 0):
        return a / b
    return np.asarray(a) @ np.linalg.pinv(np.asarray(b))


def mldivide(a, b):
    if np.isscalar(a) or (isinstance(a, np.ndarray) and a.ndim == 0):
        return b / a
    return np.linalg.solve(np.asarray(a), np.asarray(b))


def mpower(a, b):
    a_is_scalar = np.isscalar(a) or (isinstance(a, np.ndarray) and a.ndim == 0)
    if a_is_scalar:
        return a ** b
    if isinstance(b, (int, np.integer)):
        return np.linalg.matrix_power(np.asarray(a), b)
    raise ValueError("Potencia de matriz con exponente no entero no soportada")


def lnot(x):
    return np.logical_not(x) if isinstance(x, np.ndarray) else (not x)


def truthy(x):
    """Semántica de condición MATLAB: verdadero si todos los elementos son
    distintos de cero (arreglo vacío -> falso)."""
    if isinstance(x, str):
        return len(x) > 0
    arr = np.asarray(x)
    if arr.size == 0:
        return False
    return bool(np.all(arr != 0))


def iter_columns(x):
    """'for i = A' itera sobre columnas de A (o elementos si A es vector)."""
    if isinstance(x, str):
        for ch in x:
            yield ch
        return
    arr = np.asarray(x)
    if arr.ndim <= 1:
        for v in arr:
            yield v
    else:
        for col in arr.T:
            yield col


def switch_eq(val, case_val):
    if isinstance(case_val, list):
        return any(switch_eq(val, c) for c in case_val)
    if isinstance(val, str) or isinstance(case_val, str):
        return str(val) == str(case_val)
    try:
        return bool(np.all(np.asarray(val) == np.asarray(case_val)))
    except Exception:
        return val == case_val


def range_(start, step, stop):
    step = 1 if step is None else step
    if step == 0:
        return np.array([])
    n = int(np.floor((stop - start) / step + 1e-9)) + 1
    if n <= 0:
        return np.array([])
    return start + step * np.arange(n)


def build_matrix(rows):
    if not rows:
        return np.array([])
    row_arrays = [np.hstack([np.atleast_1d(np.asarray(v, dtype=float)) for v in row]) for row in rows]
    if len(row_arrays) == 1:
        return row_arrays[0]
    return np.vstack(row_arrays)


def build_cell(rows):
    flat = [v for row in rows for v in row]
    return flat


def unpack(value, n):
    if isinstance(value, tuple):
        vals = list(value)
    elif isinstance(value, np.ndarray) and value.ndim == 1:
        vals = list(value)
    else:
        vals = [value]
    while len(vals) < n:
        vals.append(None)
    return tuple(vals[:n])


def first(value):
    """Cuando una función con múltiples salidas se usa en contexto de una
    sola variable (nargout=1), MATLAB toma solo la primera salida."""
    return value[0] if isinstance(value, tuple) else value


# ---------------------------------------------------------------- funciones "built-in"
def zeros(*dims):
    dims = _norm_dims(dims)
    return np.zeros(dims)


def ones(*dims):
    dims = _norm_dims(dims)
    return np.ones(dims)


def eye(n, m=None):
    return np.eye(int(n), int(m) if m else int(n))


def rand(*dims):
    dims = _norm_dims(dims)
    return np.random.rand(*dims)


def randn(*dims):
    dims = _norm_dims(dims)
    return np.random.randn(*dims)


def _norm_dims(dims):
    if not dims:
        return (1, 1)
    if len(dims) == 1:
        n = int(dims[0])
        return (n, n)
    return tuple(int(d) for d in dims)


def linspace(a, b, n=100):
    return np.linspace(a, b, int(n))


def size(x, dim=None):
    arr = np.atleast_1d(np.asarray(x))
    if arr.ndim == 1:
        shape = (1, arr.shape[0])
    else:
        shape = arr.shape
    if dim is not None:
        return shape[int(dim) - 1]
    return np.array(shape)


def length(x):
    arr = np.atleast_1d(np.asarray(x))
    return max(arr.shape) if arr.size else 0


def numel(x):
    return np.asarray(x).size


def isempty(x):
    return np.asarray(x).size == 0


def max_(x, y=None):
    if y is not None:
        return np.maximum(x, y)
    arr = np.asarray(x)
    if arr.ndim <= 1:
        idx = int(np.argmax(arr))
        return (arr[idx], idx + 1)
    idx = np.argmax(arr, axis=0)
    return (np.max(arr, axis=0), idx + 1)


def min_(x, y=None):
    if y is not None:
        return np.minimum(x, y)
    arr = np.asarray(x)
    if arr.ndim <= 1:
        idx = int(np.argmin(arr))
        return (arr[idx], idx + 1)
    idx = np.argmin(arr, axis=0)
    return (np.min(arr, axis=0), idx + 1)


def sort_(x):
    arr = np.asarray(x)
    idx = np.argsort(arr)
    return (arr[idx], idx + 1)


def find(x):
    arr = np.asarray(x)
    idx = np.flatnonzero(arr.reshape(-1, order="F") if arr.ndim > 1 else arr)
    return (idx + 1).astype(float)


def sum_(x, dim=None):
    arr = np.asarray(x)
    if arr.ndim <= 1:
        return float(np.sum(arr))
    axis = 0 if dim is None else int(dim) - 1
    return np.sum(arr, axis=axis)


def mean_(x, dim=None):
    arr = np.asarray(x)
    if arr.ndim <= 1:
        return float(np.mean(arr))
    axis = 0 if dim is None else int(dim) - 1
    return np.mean(arr, axis=axis)


def mod(a, b):
    return np.mod(a, b)


def rem(a, b):
    return np.remainder(a, b)


abs_ = np.abs
sqrt = np.sqrt
exp = np.exp
log = np.log
log2 = np.log2
log10 = np.log10
sin = np.sin
cos = np.cos
tan = np.tan
asin = np.arcsin
acos = np.arccos
atan = np.arctan
atan2 = np.arctan2
floor = np.floor
ceil = np.ceil
round_ = np.round


def disp(x):
    print(format_value(x))


def fprintf(fmt, *args):
    if isinstance(fmt, (int, float)) and args:
        fmt = args[0]
        args = args[1:]
    print(_sprintf(fmt, args), end="")


printf = fprintf


def sprintf(fmt, *args):
    return _sprintf(fmt, args)


def _sprintf(fmt, args):
    fmt = (fmt.replace("\\n", "\n").replace("\\t", "\t")
               .replace("\\r", "\r").replace("\\\\", "\\"))
    try:
        return fmt % tuple(args) if args else fmt
    except TypeError:
        return fmt


def error(msg, *args):
    raise RuntimeError(_sprintf(msg, args) if args else msg)


def warning(msg, *args):
    print("Warning: " + (_sprintf(msg, args) if args else msg))


def class_(x):
    if isinstance(x, np.ndarray):
        return "double"
    if isinstance(x, str):
        return "char"
    if isinstance(x, bool):
        return "logical"
    if isinstance(x, (int, float, np.integer, np.floating)):
        return "double"
    if callable(x):
        return "function_handle"
    return type(x).__name__


# ---------------------------------------------------------------- gráficas
def figure(*a, **k):
    return plt.figure()


def plot(*args, **kwargs):
    plt.plot(*args, **kwargs)
    return None


def hold(state=True):
    if isinstance(state, str):
        state = state.lower() != "off"


def xlabel(s):
    plt.xlabel(s)


def ylabel(s):
    plt.ylabel(s)


def title(s):
    plt.title(s)


def legend(*a):
    plt.legend(*a)


def grid(state=True):
    plt.grid(state if not isinstance(state, str) else state.lower() != "off")


def subplot(*a):
    plt.subplot(*a)


# ---------------------------------------------------------------- formato de salida (estilo FreeMat)
def format_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, np.integer)):
        return f"{int(value)}"
    if isinstance(value, (float, np.floating)):
        return _format_float(float(value))
    if isinstance(value, np.ndarray):
        return _format_array(value)
    if isinstance(value, Struct):
        return repr(value)
    return str(value)


def _format_float(v: float) -> str:
    if v == int(v) and abs(v) < 1e15:
        return f"{int(v)}"
    return f"{v:.4f}"


def _format_array(arr: np.ndarray) -> str:
    if arr.size == 0:
        return "[](0x0)"
    if arr.ndim <= 1 or arr.shape[0] == 1:
        vals = np.atleast_1d(arr).ravel()
        return "   " + "   ".join(
            (str(int(v)) if v == int(v) else _format_float(v)) for v in vals
        )
    lines = []
    for row in arr:
        lines.append("   " + "   ".join(
            (str(int(v)) if v == int(v) else _format_float(v)) for v in np.atleast_1d(row)
        ))
    return "\n".join(lines)


def display_result(name: str, value) -> str:
    """Genera el bloque de salida estilo consola FreeMat/MATLAB."""
    body = format_value(value)
    if isinstance(value, str):
        return f"{name} = {body}\n"
    return f"{name} =\n\n{body}\n\n"
