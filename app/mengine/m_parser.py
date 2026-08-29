"""Parser recursive-descent para el subconjunto de sintaxis MATLAB/FreeMat."""
from .m_lexer import tokenize
from . import m_ast as A

BLOCK_ENDERS = {"end", "elseif", "else", "case", "otherwise", "catch", "EOF"}


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    # ---------- utilidades de token ----------
    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.toks):
            return self.toks[-1]
        return self.toks[idx]

    def cur(self):
        return self.toks[self.pos]

    def advance(self):
        tok = self.toks[self.pos]
        if tok.type != "EOF":
            self.pos += 1
        return tok

    def check(self, ttype):
        return self.cur().type == ttype

    def expect(self, ttype):
        if not self.check(ttype):
            tok = self.cur()
            raise ParseError(f"Se esperaba '{ttype}' pero se encontró '{tok.type}' ({tok.value!r}) en línea {tok.line}")
        return self.advance()

    def skip_separators(self):
        while self.cur().type in (",", ";", "NEWLINE"):
            self.advance()

    def consume_terminator(self):
        """Consume separadores de sentencia; devuelve True si alguno fue ';'."""
        suppress = False
        while self.cur().type in (",", ";", "NEWLINE"):
            if self.cur().type == ";":
                suppress = True
            self.advance()
        return suppress

    # ---------- programa ----------
    def parse_program(self):
        stmts = []
        self.skip_separators()
        while not self.check("EOF"):
            stmts.append(self.parse_statement())
            self.skip_separators()
        return A.Program(stmts)

    def parse_block(self, stop_types):
        stmts = []
        self.skip_separators()
        while self.cur().type not in stop_types and not self.check("EOF"):
            stmts.append(self.parse_statement())
            self.skip_separators()
        return stmts

    # ---------- sentencias ----------
    def parse_statement(self):
        t = self.cur().type
        if t == "function":
            return self.parse_function_def()
        if t == "if":
            return self.parse_if()
        if t == "for":
            return self.parse_for()
        if t == "while":
            return self.parse_while()
        if t == "switch":
            return self.parse_switch()
        if t == "try":
            return self.parse_try()
        if t == "break":
            self.advance()
            self.consume_terminator()
            return A.Break()
        if t == "continue":
            self.advance()
            self.consume_terminator()
            return A.Continue()
        if t == "return":
            self.advance()
            self.consume_terminator()
            return A.Return()
        if t == "global":
            self.advance()
            names = []
            while self.check("IDENT"):
                names.append(self.advance().value)
            self.consume_terminator()
            return A.ExprStatement(A.Name("__global__:" + ",".join(names)), True)
        return self.parse_assign_or_expr()

    def parse_function_def(self):
        self.expect("function")
        outputs = []
        if self.check("["):
            self.advance()
            while not self.check("]"):
                if self.check("~"):
                    self.advance()
                    outputs.append("_")
                else:
                    outputs.append(self.expect("IDENT").value)
                if self.check(","):
                    self.advance()
            self.expect("]")
            self.expect("=")
        elif self.check("IDENT") and self.peek(1).type == "=":
            outputs.append(self.advance().value)
            self.advance()  # '='
        name = self.expect("IDENT").value
        params = []
        if self.check("("):
            self.advance()
            while not self.check(")"):
                params.append(self.expect("IDENT").value)
                if self.check(","):
                    self.advance()
            self.expect(")")
        self.consume_terminator()
        body = self.parse_block({"end", "function", "EOF"})
        if self.check("end"):
            self.advance()
            self.consume_terminator()
        return A.FunctionDef(name, params, outputs, body)

    def parse_if(self):
        self.expect("if")
        cond = self.parse_expr()
        self.consume_terminator()
        body = self.parse_block({"elseif", "else", "end"})
        branches = [(cond, body)]
        while self.check("elseif"):
            self.advance()
            c = self.parse_expr()
            self.consume_terminator()
            b = self.parse_block({"elseif", "else", "end"})
            branches.append((c, b))
        else_body = []
        if self.check("else"):
            self.advance()
            self.consume_terminator()
            else_body = self.parse_block({"end"})
        self.expect("end")
        self.consume_terminator()
        return A.If(branches, else_body)

    def parse_for(self):
        self.expect("for")
        var = self.expect("IDENT").value
        self.expect("=")
        iterable = self.parse_expr()
        self.consume_terminator()
        body = self.parse_block({"end"})
        self.expect("end")
        self.consume_terminator()
        return A.For(var, iterable, body)

    def parse_while(self):
        self.expect("while")
        cond = self.parse_expr()
        self.consume_terminator()
        body = self.parse_block({"end"})
        self.expect("end")
        self.consume_terminator()
        return A.While(cond, body)

    def parse_switch(self):
        self.expect("switch")
        expr = self.parse_expr()
        self.consume_terminator()
        self.skip_separators()
        cases = []
        while self.check("case"):
            self.advance()
            val = self.parse_expr()
            self.consume_terminator()
            body = self.parse_block({"case", "otherwise", "end"})
            cases.append((val, body))
        otherwise = []
        if self.check("otherwise"):
            self.advance()
            self.consume_terminator()
            otherwise = self.parse_block({"end"})
        self.expect("end")
        self.consume_terminator()
        return A.Switch(expr, cases, otherwise)

    def parse_try(self):
        self.expect("try")
        self.consume_terminator()
        try_body = self.parse_block({"catch", "end"})
        catch_var = None
        catch_body = []
        if self.check("catch"):
            self.advance()
            if self.check("IDENT"):
                catch_var = self.advance().value
            self.consume_terminator()
            catch_body = self.parse_block({"end"})
        self.expect("end")
        self.consume_terminator()
        return A.TryCatch(try_body, catch_var, catch_body)

    # ---------- asignación / expresión ----------
    def _looks_like_multi_assign(self):
        """Escanea hacia adelante desde '[' para ver si es [a,b,~] = expr."""
        if not self.check("["):
            return False
        depth = 0
        j = self.pos
        while j < len(self.toks):
            tt = self.toks[j].type
            if tt == "[":
                depth += 1
            elif tt == "]":
                depth -= 1
                if depth == 0:
                    break
            elif tt not in ("IDENT", "~", ",", "NEWLINE"):
                return False
            j += 1
        else:
            return False
        return j + 1 < len(self.toks) and self.toks[j + 1].type == "="

    def parse_assign_or_expr(self):
        if self._looks_like_multi_assign():
            self.expect("[")
            targets = []
            while not self.check("]"):
                if self.check("~"):
                    self.advance()
                    targets.append("_")
                else:
                    targets.append(self.expect("IDENT").value)
                if self.check(","):
                    self.advance()
            self.expect("]")
            self.expect("=")
            expr = self.parse_expr()
            suppress = self.consume_terminator()
            return A.MultiAssign(targets, expr, suppress)

        expr = self.parse_expr()
        if self.check("="):
            self.advance()
            rhs = self.parse_expr()
            suppress = self.consume_terminator()
            return A.Assign([expr], rhs, suppress)
        suppress = self.consume_terminator()
        return A.ExprStatement(expr, suppress)

    # ---------- expresiones (precedencia) ----------
    def parse_expr(self):
        return self.parse_or_sc()

    def parse_or_sc(self):
        left = self.parse_and_sc()
        while self.check("||"):
            self.advance()
            right = self.parse_and_sc()
            left = A.BinOp("||", left, right)
        return left

    def parse_and_sc(self):
        left = self.parse_or_ew()
        while self.check("&&"):
            self.advance()
            right = self.parse_or_ew()
            left = A.BinOp("&&", left, right)
        return left

    def parse_or_ew(self):
        left = self.parse_and_ew()
        while self.check("|"):
            self.advance()
            right = self.parse_and_ew()
            left = A.BinOp("|", left, right)
        return left

    def parse_and_ew(self):
        left = self.parse_relational()
        while self.check("&"):
            self.advance()
            right = self.parse_relational()
            left = A.BinOp("&", left, right)
        return left

    def parse_relational(self):
        left = self.parse_range()
        while self.cur().type in ("==", "~=", "<", ">", "<=", ">="):
            op = self.advance().type
            right = self.parse_range()
            left = A.BinOp(op, left, right)
        return left

    def parse_range(self):
        first = self.parse_additive()
        if self.check(":"):
            self.advance()
            second = self.parse_additive()
            if self.check(":"):
                self.advance()
                third = self.parse_additive()
                return A.Range(first, second, third)
            return A.Range(first, None, second)
        return first

    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.cur().type in ("+", "-"):
            op = self.advance().type
            right = self.parse_multiplicative()
            left = A.BinOp(op, left, right)
        return left

    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.cur().type in ("*", "/", "\\", ".*", "./", ".\\"):
            op = self.advance().type
            right = self.parse_unary()
            left = A.BinOp(op, left, right)
        return left

    def parse_unary(self):
        if self.cur().type in ("+", "-", "~"):
            op = self.advance().type
            operand = self.parse_unary()
            return A.UnaryOp(op, operand)
        return self.parse_power()

    def parse_power(self):
        left = self.parse_postfix()
        while self.cur().type in ("^", ".^"):
            op = self.advance().type
            right = self.parse_unary()  # permite -2^2 correctamente a la derecha
            left = A.BinOp(op, left, right)
        return left

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.check("("):
                self.advance()
                args = self._parse_arg_list(")")
                self.expect(")")
                node = A.Index(node, args, brace=False)
            elif self.check("{"):
                self.advance()
                args = self._parse_arg_list("}")
                self.expect("}")
                node = A.Index(node, args, brace=True)
            elif self.check("."):
                self.advance()
                field = self.expect("IDENT").value
                node = A.Field(node, field)
            elif self.cur().type in ("'", ".'"):
                self.advance()
                node = A.Transpose(node)
            else:
                break
        return node

    def _parse_arg_list(self, closer):
        args = []
        if self.check(closer):
            return args
        while True:
            if self.check(":") and self.peek(1).type in (",", closer):
                self.advance()
                args.append(A.Colon())
            else:
                args.append(self.parse_expr())
            if self.check(","):
                self.advance()
                continue
            break
        return args

    def parse_primary(self):
        tok = self.cur()

        if tok.type == "NUMBER":
            self.advance()
            return A.Num(tok.value)

        if tok.type == "STRING":
            self.advance()
            return A.Str(tok.value)

        if tok.type == "end":
            self.advance()
            return A.EndExpr()

        if tok.type in ("true", "false"):
            self.advance()
            return A.Name("True" if tok.type == "true" else "False")

        if tok.type == "IDENT":
            self.advance()
            return A.Name(tok.value)

        if tok.type == "@":
            self.advance()
            if self.check("("):
                self.advance()
                params = []
                while not self.check(")"):
                    params.append(self.expect("IDENT").value)
                    if self.check(","):
                        self.advance()
                self.expect(")")
                body = self.parse_expr()
                return A.AnonFunc(params, body)
            name = self.expect("IDENT").value
            return A.Name(name)

        if tok.type == "(":
            self.advance()
            e = self.parse_expr()
            self.expect(")")
            return e

        if tok.type == "[":
            return self._parse_matrix()

        if tok.type == "{":
            return self._parse_cell()

        raise ParseError(f"Token inesperado '{tok.type}' ({tok.value!r}) en línea {tok.line}")

    def _parse_matrix(self):
        self.expect("[")
        rows = [[]]
        while not self.check("]"):
            if self.cur().type in (";", "NEWLINE"):
                self.advance()
                if rows[-1]:
                    rows.append([])
                continue
            if self.check(","):
                self.advance()
                continue
            rows[-1].append(self.parse_or_sc())
        self.expect("]")
        rows = [r for r in rows if r]
        return A.MatrixLiteral(rows)

    def _parse_cell(self):
        self.expect("{")
        rows = [[]]
        while not self.check("}"):
            if self.cur().type in (";", "NEWLINE"):
                self.advance()
                if rows[-1]:
                    rows.append([])
                continue
            if self.check(","):
                self.advance()
                continue
            rows[-1].append(self.parse_or_sc())
        self.expect("}")
        rows = [r for r in rows if r]
        return A.CellLiteral(rows)


def parse(source: str) -> A.Program:
    tokens = tokenize(source)
    return Parser(tokens).parse_program()
