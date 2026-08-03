"""Resaltado de sintaxis simple estilo IDE para el editor de código."""
import re
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
    "def", "return", "if", "elif", "else", "for", "while", "in", "import",
    "from", "as", "class", "try", "except", "finally", "with", "lambda",
    "pass", "break", "continue", "and", "or", "not", "is", "None", "True",
    "False", "yield", "global", "nonlocal", "raise", "assert", "del",
]


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        kw_fmt = _fmt("#c586c0", bold=True)
        for kw in KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        self.rules.append((QRegularExpression(r"\bdef\s+(\w+)"), _fmt("#dcdcaa")))
        self.rules.append((QRegularExpression(r"\b[A-Za-z_]\w*(?=\()"), _fmt("#dcdcaa")))
        self.rules.append((QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), _fmt("#b5cea8")))
        self.rules.append((QRegularExpression(r"'[^']*'"), _fmt("#ce9178")))
        self.rules.append((QRegularExpression(r'"[^"]*"'), _fmt("#ce9178")))
        self.rules.append((QRegularExpression(r"#.*"), _fmt("#6a9955", italic=True)))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
