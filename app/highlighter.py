"""Resaltado de sintaxis para archivos .m (MATLAB/FreeMat)."""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


KEYWORDS = [
    "function", "end", "if", "elseif", "else", "for", "while", "switch",
    "case", "otherwise", "break", "continue", "return", "global",
    "try", "catch", "true", "false",
]

BUILTINS = [
    "zeros", "ones", "eye", "rand", "randn", "linspace", "size", "length",
    "numel", "isempty", "disp", "fprintf", "printf", "sprintf", "error",
    "warning", "figure", "plot", "hold", "xlabel", "ylabel", "title",
    "legend", "grid", "subplot", "sum", "mean", "max", "min", "sort",
    "find", "abs", "sqrt", "exp", "log", "sin", "cos", "tan", "mod", "rem",
    "floor", "ceil", "round", "class",
]


class PythonHighlighter(QSyntaxHighlighter):
    """Nombre de clase mantenido por compatibilidad con el resto de la app."""
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        kw_fmt = _fmt("#00008b", bold=True)
        for kw in KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))
        fn_fmt = _fmt("#7a3e9d")
        for fn in BUILTINS:
            self.rules.append((QRegularExpression(rf"\b{fn}\b(?=\()"), fn_fmt))
        self.rules.append((QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), _fmt("#098658")))
        self.rules.append((QRegularExpression(r"'[^']*'"), _fmt("#a31515")))
        self.rules.append((QRegularExpression(r'"[^"]*"'), _fmt("#a31515")))
        self.rules.append((QRegularExpression(r"%.*"), _fmt("#008000", italic=True)))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
