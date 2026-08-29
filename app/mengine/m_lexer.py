"""
Lexer (tokenizador) de sintaxis .m estilo MATLAB/FreeMat.
Convierte el código fuente en una lista de tokens (type, value, line).
"""

KEYWORDS = {
    "function", "end", "if", "elseif", "else", "for", "while", "switch",
    "case", "otherwise", "break", "continue", "return", "global",
    "try", "catch", "true", "false",
}

# Operadores ordenados de más largo a más corto (para matching greedy)
OPERATORS = [
    "...", "==", "~=", "<=", ">=", "&&", "||", ".*", "./", ".^", ".'",
    "+=", "-=",
    "=", "+", "-", "*", "/", "\\", "^", "'", "<", ">", "~", "&", "|",
    "(", ")", "[", "]", "{", "}", ",", ";", ":", ".", "@",
]


class Token:
    __slots__ = ("type", "value", "line")

    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r})"


class LexError(Exception):
    pass


def tokenize(source: str):
    tokens = []
    i = 0
    n = len(source)
    line = 1
    paren_depth = 0     # ( )
    bracket_depth = 0   # [ ] { }

    # tipo del último token "significativo" (para decidir si ' es transpose)
    prev_significant = None

    def last_allows_transpose():
        return prev_significant in ("NUMBER", "STRING", "IDENT", ")", "]", "}", "'", ".'")

    while i < n:
        c = source[i]

        # continuación de línea "..."
        if source.startswith("...", i):
            j = source.find("\n", i)
            if j == -1:
                i = n
            else:
                i = j + 1
                line += 1
            continue

        # comentarios de bloque %{ ... %} en línea propia (simplificado: cualquier %{ ... %})
        if source.startswith("%{", i):
            j = source.find("%}", i)
            i = n if j == -1 else j + 2
            continue

        # comentarios de línea
        if c == "%" or c == "#":
            j = source.find("\n", i)
            i = n if j == -1 else j
            continue

        if c == "\n":
            if paren_depth > 0:
                pass  # dentro de () una nueva línea no separa
            elif bracket_depth > 0:
                if tokens and tokens[-1].type not in (";", ",", "[", "{"):
                    tokens.append(Token(";", ";", line))
                    prev_significant = ";"
            else:
                if tokens and tokens[-1].type != "NEWLINE":
                    tokens.append(Token("NEWLINE", "\n", line))
                    prev_significant = "NEWLINE"
            line += 1
            i += 1
            continue

        if c in " \t\r":
            i += 1
            continue

        # números: 123, 12.3, 1.5e-3, .5
        if c.isdigit() or (c == "." and i + 1 < n and source[i + 1].isdigit()):
            start = i
            i += 1
            while i < n and source[i].isdigit():
                i += 1
            if i < n and source[i] == ".":
                i += 1
                while i < n and source[i].isdigit():
                    i += 1
            if i < n and source[i] in "eE":
                save = i
                i += 1
                if i < n and source[i] in "+-":
                    i += 1
                if i < n and source[i].isdigit():
                    while i < n and source[i].isdigit():
                        i += 1
                else:
                    i = save
            if i < n and source[i] == "i":  # número imaginario simple (1i)
                i += 1
                tokens.append(Token("NUMBER", source[start:i], line))
            else:
                tokens.append(Token("NUMBER", source[start:i], line))
            prev_significant = "NUMBER"
            continue

        # identificadores / palabras clave
        if c.isalpha() or c == "_":
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            word = source[start:i]
            ttype = word if word in KEYWORDS else "IDENT"
            tokens.append(Token(ttype, word, line))
            prev_significant = ttype if ttype != "IDENT" else "IDENT"
            continue

        # strings con comillas simples (con '' como escape) o dobles
        if c == "'" and not last_allows_transpose():
            i += 1
            start = i
            buf = []
            while i < n:
                if source[i] == "'":
                    if i + 1 < n and source[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    break
                if source[i] == "\n":
                    raise LexError(f"Cadena sin cerrar en línea {line}")
                buf.append(source[i])
                i += 1
            i += 1  # cerrar comilla
            tokens.append(Token("STRING", "".join(buf), line))
            prev_significant = "STRING"
            continue

        if c == '"':
            i += 1
            buf = []
            while i < n and source[i] != '"':
                if source[i] == "\\" and i + 1 < n:
                    buf.append(source[i + 1])
                    i += 2
                    continue
                buf.append(source[i])
                i += 1
            i += 1
            tokens.append(Token("STRING", "".join(buf), line))
            prev_significant = "STRING"
            continue

        # operadores
        matched = False
        for op in OPERATORS:
            if source.startswith(op, i):
                if op == "'" and last_allows_transpose():
                    tokens.append(Token("'", "'", line))
                    i += 1
                    prev_significant = "'"
                    matched = True
                    break
                tokens.append(Token(op, op, line))
                if op == "(":
                    paren_depth += 1
                elif op == ")":
                    paren_depth = max(0, paren_depth - 1)
                elif op in ("[", "{"):
                    bracket_depth += 1
                elif op in ("]", "}"):
                    bracket_depth = max(0, bracket_depth - 1)
                i += len(op)
                prev_significant = op
                matched = True
                break
        if matched:
            continue

        raise LexError(f"Carácter inesperado {c!r} en línea {line}")

    tokens.append(Token("NEWLINE", "\n", line))
    tokens.append(Token("EOF", None, line))
    return tokens
