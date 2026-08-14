"""Transpilador: recorre el AST y genera código Python equivalente,
apoyado en las funciones de m_runtime (importado como 'mrt' en el código
generado)."""
import m_ast as A

DIRECT_BINOPS = {
    "+": "+", "-": "-", ".*": "*", "./": "/", ".^": "**",
    "==": "==", "~=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "&": "&", "|": "|",
}


class TranspileError(Exception):
    pass


class Transpiler:
    def __init__(self):
        self.lines = []
        self.indent = 0

    # ---------- utilidades ----------
    def emit(self, code):
        self.lines.append(("    " * self.indent) + code)

    def gen_program(self, prog: A.Program):
        for stmt in prog.statements:
            self.gen_stmt(stmt)
        return "\n".join(self.lines)

    def gen_block(self, stmts):
        self.indent += 1
        if not stmts:
            self.emit("pass")
        for s in stmts:
            self.gen_stmt(s)
        self.indent -= 1

    # ---------- sentencias ----------
    def gen_stmt(self, node):
        if isinstance(node, A.ExprStatement):
            self._gen_expr_statement(node)
        elif isinstance(node, A.Assign):
            self._gen_assign(node)
        elif isinstance(node, A.MultiAssign):
            self._gen_multi_assign(node)
        elif isinstance(node, A.If):
            self._gen_if(node)
        elif isinstance(node, A.For):
            self._gen_for(node)
        elif isinstance(node, A.While):
            self._gen_while(node)
        elif isinstance(node, A.Switch):
            self._gen_switch(node)
        elif isinstance(node, A.TryCatch):
            self._gen_try(node)
        elif isinstance(node, A.Break):
            self.emit("break")
        elif isinstance(node, A.Continue):
            self.emit("continue")
        elif isinstance(node, A.Return):
            self.emit("return")
        elif isinstance(node, A.FunctionDef):
            self._gen_function(node)
        else:
            raise TranspileError(f"Sentencia no soportada: {type(node)}")

    def _gen_expr_statement(self, node: A.ExprStatement):
        if isinstance(node.expr, A.Name) and node.expr.name.startswith("__global__:"):
            names = node.expr.name.split(":", 1)[1]
            self.emit(f"global {names}")
            return
        code = self.gen_expr(node.expr)
        if node.suppress:
            self.emit(f"{code}")
        elif isinstance(node.expr, A.Name) and node.expr.name not in ("True", "False"):
            self.emit(f"__mdisplay__('{node.expr.name}', {code})")
        else:
            self.emit(f"_val = mrt.first({code})")
            self.emit("if _val is not None:")
            self.indent += 1
            self.emit("ans = _val")
            self.emit("__mdisplay__('ans', ans)")
            self.indent -= 1

    def _gen_assign(self, node: A.Assign):
        target = node.targets[0]
        value_code = f"mrt.first({self.gen_expr(node.expr)})"
        if isinstance(target, A.Name):
            self.emit(f"{target.name} = {value_code}")
            name_for_display = target.name
        elif isinstance(target, A.Index):
            base = target.target
            if not isinstance(base, A.Name):
                raise TranspileError("Asignación indexada compleja no soportada")
            idx_code = self._gen_index_args(target, is_lvalue=True)
            self.emit(
                f"{base.name} = mrt.set_index({base.name} if '{base.name}' in globals() else None, "
                f"({idx_code}), {value_code})"
            )
            name_for_display = base.name
        elif isinstance(target, A.Field):
            base = target.target
            if not isinstance(base, A.Name):
                raise TranspileError("Asignación de campo compleja no soportada")
            self.emit(
                f"{base.name} = mrt.set_field({base.name} if '{base.name}' in globals() else None, "
                f"{target.field!r}, {value_code})"
            )
            name_for_display = base.name
        else:
            raise TranspileError("Objetivo de asignación no soportado")

        if not node.suppress:
            self.emit(f"__mdisplay__('{name_for_display}', {name_for_display})")

    def _gen_multi_assign(self, node: A.MultiAssign):
        value_code = self.gen_expr(node.expr)
        n = len(node.targets)
        self.emit(f"_res = mrt.unpack({value_code}, {n})")
        for i, t in enumerate(node.targets):
            if t == "_":
                continue
            self.emit(f"{t} = _res[{i}]")
        if not node.suppress:
            for t in node.targets:
                if t != "_":
                    self.emit(f"__mdisplay__('{t}', {t})")

    def _gen_if(self, node: A.If):
        first = True
        for cond, body in node.branches:
            kw = "if" if first else "elif"
            self.emit(f"{kw} mrt.truthy({self.gen_expr(cond)}):")
            self.gen_block(body)
            first = False
        if node.else_body:
            self.emit("else:")
            self.gen_block(node.else_body)

    def _gen_for(self, node: A.For):
        it_code = self.gen_expr(node.iterable)
        self.emit(f"for {node.var} in mrt.iter_columns({it_code}):")
        self.gen_block(node.body)

    def _gen_while(self, node: A.While):
        self.emit(f"while mrt.truthy({self.gen_expr(node.cond)}):")
        self.gen_block(node.body)

    def _gen_switch(self, node: A.Switch):
        expr_code = self.gen_expr(node.expr)
        self.emit(f"_switch_val = {expr_code}")
        first = True
        for val, body in node.cases:
            kw = "if" if first else "elif"
            self.emit(f"{kw} mrt.switch_eq(_switch_val, {self.gen_expr(val)}):")
            self.gen_block(body)
            first = False
        if node.otherwise:
            self.emit("else:" if not first else "if True:")
            self.gen_block(node.otherwise)

    def _gen_try(self, node: A.TryCatch):
        self.emit("try:")
        self.gen_block(node.try_body)
        if node.catch_var:
            self.emit(f"except Exception as {node.catch_var}:")
        else:
            self.emit("except Exception:")
        self.gen_block(node.catch_body if node.catch_body else [A.ExprStatement(A.Name("None"), True)])

    def _gen_function(self, node: A.FunctionDef):
        params = ", ".join(node.params)
        self.emit(f"def {node.name}({params}):")
        self.indent += 1
        if not node.body:
            self.emit("pass")
        for s in node.body:
            self.gen_stmt(s)
        if node.outputs:
            real_outputs = [o for o in node.outputs if o != "_"]
            if len(real_outputs) == 1:
                self.emit(f"return {real_outputs[0]}")
            elif len(real_outputs) > 1:
                self.emit(f"return ({', '.join(real_outputs)})")
        self.indent -= 1
        self.emit(f"globals()['{node.name}'] = {node.name}")

    # ---------- expresiones ----------
    def gen_expr(self, node, end_ctx=None):
        if isinstance(node, A.Num):
            v = node.value
            if v.endswith("i") or v.endswith("j"):
                return f"complex(0, {v[:-1]})"
            return v
        if isinstance(node, A.Str):
            return repr(node.value)
        if isinstance(node, A.Name):
            if node.name == "class":
                return "class_"
            return node.name
        if isinstance(node, A.EndExpr):
            if end_ctx is None:
                raise TranspileError("'end' usado fuera de un índice")
            target_code, axis, nargs = end_ctx
            return f"mrt.dim_end({target_code}, {axis}, {nargs})"
        if isinstance(node, A.Colon):
            return "mrt.COLON"
        if isinstance(node, A.Range):
            start = self.gen_expr(node.start, end_ctx)
            step = self.gen_expr(node.step, end_ctx) if node.step is not None else "None"
            stop = self.gen_expr(node.stop, end_ctx)
            return f"mrt.range_({start}, {step}, {stop})"
        if isinstance(node, A.BinOp):
            return self._gen_binop(node, end_ctx)
        if isinstance(node, A.UnaryOp):
            operand = self.gen_expr(node.operand, end_ctx)
            if node.op == "+":
                return f"(+{operand})"
            if node.op == "-":
                return f"(-{operand})"
            if node.op == "~":
                return f"mrt.lnot({operand})"
        if isinstance(node, A.Transpose):
            return f"mrt.transpose({self.gen_expr(node.operand, end_ctx)})"
        if isinstance(node, A.MatrixLiteral):
            rows_code = ",".join(
                "[" + ",".join(self.gen_expr(e, end_ctx) for e in row) + "]"
                for row in node.rows
            )
            return f"mrt.build_matrix([{rows_code}])"
        if isinstance(node, A.CellLiteral):
            rows_code = ",".join(
                "[" + ",".join(self.gen_expr(e, end_ctx) for e in row) + "]"
                for row in node.rows
            )
            return f"mrt.build_cell([{rows_code}])"
        if isinstance(node, A.AnonFunc):
            params = ", ".join(node.params)
            body_code = self.gen_expr(node.body, None)
            return f"(lambda {params}: {body_code})"
        if isinstance(node, A.Index):
            return self._gen_index(node, end_ctx)
        if isinstance(node, A.Field):
            target_code = self.gen_expr(node.target, end_ctx)
            return f"mrt.get_field({target_code}, {node.field!r})"
        raise TranspileError(f"Expresión no soportada: {type(node)}")

    def _gen_binop(self, node: A.BinOp, end_ctx):
        left = self.gen_expr(node.left, end_ctx)
        right = self.gen_expr(node.right, end_ctx)
        op = node.op
        if op in DIRECT_BINOPS:
            return f"({left} {DIRECT_BINOPS[op]} {right})"
        if op == "&&":
            return f"(mrt.truthy({left}) and mrt.truthy({right}))"
        if op == "||":
            return f"(mrt.truthy({left}) or mrt.truthy({right}))"
        if op == "*":
            return f"mrt.mtimes({left}, {right})"
        if op == "/":
            return f"mrt.mrdivide({left}, {right})"
        if op == "\\":
            return f"mrt.mldivide({left}, {right})"
        if op == "^":
            return f"mrt.mpower({left}, {right})"
        raise TranspileError(f"Operador no soportado: {op}")

    def _gen_index_args(self, node: A.Index, is_lvalue=False):
        target_code = self.gen_expr(node.target)
        nargs = len(node.args)
        parts = []
        for i, arg in enumerate(node.args):
            ctx = (target_code, i, nargs)
            if isinstance(arg, A.Colon):
                parts.append("mrt.COLON")
            else:
                parts.append(self.gen_expr(arg, ctx))
        return ", ".join(parts)

    def _gen_index(self, node: A.Index, end_ctx):
        target_code = self.gen_expr(node.target, end_ctx)
        args_code = self._gen_index_args(node)
        return f"mrt.get({target_code}, {args_code})"


def transpile(program: A.Program) -> str:
    return Transpiler().gen_program(program)
