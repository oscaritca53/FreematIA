"""Nodos del árbol de sintaxis abstracta (AST)."""


class Node:
    pass


class Program(Node):
    def __init__(self, statements):
        self.statements = statements


class ExprStatement(Node):
    def __init__(self, expr, suppress):
        self.expr = expr
        self.suppress = suppress


class Assign(Node):
    def __init__(self, targets, expr, suppress):
        self.targets = targets  # lista de nodos lvalue (Name o Index)
        self.expr = expr
        self.suppress = suppress


class MultiAssign(Node):
    """[a, b] = f(x)"""
    def __init__(self, targets, expr, suppress):
        self.targets = targets
        self.expr = expr
        self.suppress = suppress


class If(Node):
    def __init__(self, branches, else_body):
        self.branches = branches  # lista de (cond, body)
        self.else_body = else_body


class For(Node):
    def __init__(self, var, iterable, body):
        self.var = var
        self.iterable = iterable
        self.body = body


class While(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class Switch(Node):
    def __init__(self, expr, cases, otherwise):
        self.expr = expr
        self.cases = cases  # lista de (valor_expr, body)
        self.otherwise = otherwise


class TryCatch(Node):
    def __init__(self, try_body, catch_var, catch_body):
        self.try_body = try_body
        self.catch_var = catch_var
        self.catch_body = catch_body


class Break(Node):
    pass


class Continue(Node):
    pass


class Return(Node):
    pass


class FunctionDef(Node):
    def __init__(self, name, params, outputs, body):
        self.name = name
        self.params = params
        self.outputs = outputs
        self.body = body


# ---------- expresiones ----------

class Num(Node):
    def __init__(self, value):
        self.value = value


class Str(Node):
    def __init__(self, value):
        self.value = value


class Name(Node):
    def __init__(self, name):
        self.name = name


class Colon(Node):
    """':' usado como índice completo"""
    pass


class EndExpr(Node):
    """palabra clave 'end' dentro de un índice"""
    pass


class Range(Node):
    def __init__(self, start, step, stop):
        self.start = start
        self.step = step
        self.stop = stop


class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class Transpose(Node):
    def __init__(self, operand):
        self.operand = operand


class MatrixLiteral(Node):
    def __init__(self, rows):
        self.rows = rows  # lista de listas de expresiones


class CellLiteral(Node):
    def __init__(self, rows):
        self.rows = rows


class Index(Node):
    """name(args) o name{args} — puede ser indexación o llamada a función"""
    def __init__(self, target, args, brace=False):
        self.target = target
        self.args = args
        self.brace = brace


class Field(Node):
    """target.field"""
    def __init__(self, target, field):
        self.target = target
        self.field = field


class AnonFunc(Node):
    def __init__(self, params, body):
        self.params = params
        self.body = body
