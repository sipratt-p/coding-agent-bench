"""Reference solution for the Chunk-Split Streaming JSON Parser (validates the grader)."""


class StreamParser:
    WS = " \t\r\n"

    def __init__(self):
        self._buf = ""          # unconsumed text of the current (incomplete) value
        self._closed = False

    def feed(self, chunk):
        self._buf += chunk
        out = []
        while True:
            self._buf = self._buf.lstrip(self.WS)
            if not self._buf:
                break
            val, end, complete = self._try_parse(self._buf)
            if not complete:
                break
            out.append(val)
            self._buf = self._buf[end:]
        return out

    def close(self):
        self._closed = True
        rest = self._buf.lstrip(self.WS)
        if not rest:
            return
        # A bare number can be completed by EOF; anything else incomplete = error.
        val, end, complete = self._try_parse(rest + " ")
        if not complete:
            raise ValueError("incomplete value at end of stream")
        if rest[end:].strip(self.WS):
            raise ValueError("trailing garbage at end of stream")

    # --- single-value incremental parse: returns (value, consumed_chars, complete)
    # Raises ValueError on definite malformation; complete=False when the text is
    # a valid prefix but not yet a full value.
    def _try_parse(self, s):
        val, i = self._parse_value(s, 0)
        if i is None:
            return None, 0, False
        # numbers must not be immediately followed by alnum
        return val, i, True

    def _parse_value(self, s, i):
        if i >= len(s):
            return None, None
        c = s[i]
        if c == "{":
            return self._parse_obj(s, i)
        if c == "[":
            return self._parse_arr(s, i)
        if c == '"':
            return self._parse_str(s, i)
        if c in "-0123456789":
            return self._parse_num(s, i)
        for lit, v in (("true", True), ("false", False), ("null", None)):
            if lit.startswith(s[i:i + len(lit)]):
                if s[i:i + len(lit)] == lit:
                    j = i + len(lit)
                    if j < len(s) and (s[j].isalnum() or s[j] == "_"):
                        raise ValueError("bad literal")
                    if j >= len(s):
                        return None, None  # might still be growing... but full match at buffer end:
                    return v, j
                # partial prefix of a literal
                if len(s) - i < len(lit):
                    return None, None
        raise ValueError(f"unexpected character {c!r}")

    def _skip_ws(self, s, i):
        while i < len(s) and s[i] in self.WS:
            i += 1
        return i

    def _parse_obj(self, s, i):
        i += 1
        obj = {}
        i2 = self._skip_ws(s, i)
        if i2 >= len(s):
            return None, None
        if s[i2] == "}":
            return obj, i2 + 1
        i = i2
        while True:
            i = self._skip_ws(s, i)
            if i >= len(s):
                return None, None
            if s[i] != '"':
                raise ValueError("object key must be a string")
            key, i = self._parse_str(s, i)
            if i is None:
                return None, None
            i = self._skip_ws(s, i)
            if i >= len(s):
                return None, None
            if s[i] != ":":
                raise ValueError("expected ':' in object")
            i = self._skip_ws(s, i + 1)
            v, i = self._parse_value(s, i)
            if i is None:
                return None, None
            obj[key] = v
            i = self._skip_ws(s, i)
            if i >= len(s):
                return None, None
            if s[i] == ",":
                i += 1
                continue
            if s[i] == "}":
                return obj, i + 1
            raise ValueError("expected ',' or '}' in object")

    def _parse_arr(self, s, i):
        i += 1
        arr = []
        i2 = self._skip_ws(s, i)
        if i2 >= len(s):
            return None, None
        if s[i2] == "]":
            return arr, i2 + 1
        i = i2
        while True:
            i = self._skip_ws(s, i)
            v, i = self._parse_value(s, i)
            if i is None:
                return None, None
            arr.append(v)
            i = self._skip_ws(s, i)
            if i >= len(s):
                return None, None
            if s[i] == ",":
                i += 1
                i = self._skip_ws(s, i)
                if i < len(s) and s[i] == "]":
                    raise ValueError("trailing comma in array")
                continue
            if s[i] == "]":
                return arr, i + 1
            raise ValueError("expected ',' or ']' in array")

    _ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            "n": "\n", "r": "\r", "t": "\t"}

    def _parse_str(self, s, i):
        i += 1
        out = []
        while True:
            if i >= len(s):
                return None, None
            c = s[i]
            if c == '"':
                return "".join(out), i + 1
            if c == "\\":
                if i + 1 >= len(s):
                    return None, None
                e = s[i + 1]
                if e in self._ESC:
                    out.append(self._ESC[e])
                    i += 2
                elif e == "u":
                    if i + 6 > len(s):
                        return None, None
                    hexs = s[i + 2:i + 6]
                    if len(hexs) < 4:
                        return None, None
                    try:
                        out.append(chr(int(hexs, 16)))
                    except ValueError:
                        raise ValueError("bad \\u escape")
                    i += 6
                else:
                    raise ValueError(f"bad escape \\{e}")
            else:
                out.append(c)
                i += 1

    def _parse_num(self, s, i):
        j = i
        if j < len(s) and s[j] == "-":
            j += 1
        digits0 = j
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == digits0:
            if j >= len(s):
                return None, None
            raise ValueError("bad number")
        is_float = False
        if j < len(s) and s[j] == ".":
            is_float = True
            j += 1
            d1 = j
            while j < len(s) and s[j].isdigit():
                j += 1
            if j == d1:
                if j >= len(s):
                    return None, None
                raise ValueError("bad number: missing fraction digits")
        if j < len(s) and s[j] in "eE":
            is_float = True
            j += 1
            if j < len(s) and s[j] in "+-":
                j += 1
            d2 = j
            while j < len(s) and s[j].isdigit():
                j += 1
            if j == d2:
                if j >= len(s):
                    return None, None
                raise ValueError("bad number: missing exponent digits")
        if j >= len(s):
            return None, None  # number may still be growing
        if s[j].isalnum() or s[j] == "_":
            raise ValueError("number followed by alphanumeric")
        text = s[i:j]
        return (float(text) if is_float else int(text)), j
