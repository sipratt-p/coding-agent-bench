"""Reference: POSIX leftmost-longest regex engine (Thompson NFA simulation)."""


class _State:
    __slots__ = ("eps", "trans")

    def __init__(self):
        self.eps = []          # epsilon successors
        self.trans = []        # (predicate, next_state)


def _parse(pattern):
    """Recursive-descent parse -> (start, accept) NFA fragment. Raises ValueError."""
    pos = [0]
    n = len(pattern)

    anchored_start = pattern.startswith("^")
    anchored_end = pattern.endswith("$") and not pattern.endswith("\\$")
    src = pattern[1 if anchored_start else 0: n - 1 if anchored_end else n]
    n = len(src)

    def peek():
        return src[pos[0]] if pos[0] < n else None

    def take():
        c = peek()
        pos[0] += 1
        return c

    def frag_atom():
        c = peek()
        if c is None or c in ")|*+?^$":
            raise ValueError(f"unexpected {c!r} at {pos[0]}")
        if c == "(":
            take()
            f = frag_alt()
            if peek() != ")":
                raise ValueError("unbalanced (")
            take()
            return f
        if c == "[":
            take()
            negate = peek() == "^"
            if negate:
                take()
            chars = set()
            prev = None
            closed = False
            while (c2 := peek()) is not None:
                take()
                if c2 == "]":
                    closed = True
                    break
                if c2 == "-" and prev is not None and peek() not in (None, "]"):
                    hi = take()
                    chars.update(chr(x) for x in range(ord(prev), ord(hi) + 1))
                    prev = None
                else:
                    chars.add(c2)
                    prev = c2
            if not closed:
                raise ValueError("unterminated class")
            s, a = _State(), _State()
            if negate:
                s.trans.append((lambda ch, cs=frozenset(chars): ch not in cs, a))
            else:
                s.trans.append((lambda ch, cs=frozenset(chars): ch in cs, a))
            return s, a
        take()
        s, a = _State(), _State()
        if c == ".":
            s.trans.append((lambda ch: True, a))
        else:
            s.trans.append((lambda ch, lit=c: ch == lit, a))
        return s, a

    def frag_quant():
        f = frag_atom()
        while (c := peek()) in ("*", "+", "?"):
            take()
            if peek() in ("*", "+", "?"):
                raise ValueError("double quantifier")
            s0, a0 = f
            s, a = _State(), _State()
            if c == "*":
                s.eps += [s0, a]
                a0.eps += [s0, a]
            elif c == "+":
                s.eps.append(s0)
                a0.eps += [s0, a]
            else:
                s.eps += [s0, a]
                a0.eps.append(a)
            f = (s, a)
        return f

    def frag_concat():
        f = frag_quant()
        while peek() is not None and peek() not in ")|":
            g = frag_quant()
            f[1].eps.append(g[0])
            f = (f[0], g[1])
        return f

    def frag_alt():
        parts = [frag_concat() if peek() not in (None, "|", ")") else _empty()]
        while peek() == "|":
            take()
            parts.append(frag_concat() if peek() not in (None, "|", ")") else _empty())
        if len(parts) == 1:
            return parts[0]
        s, a = _State(), _State()
        for ps, pa in parts:
            s.eps.append(ps)
            pa.eps.append(a)
        return s, a

    def _empty():
        s = _State()
        return s, s

    if n == 0:
        s = _State()
        frag = (s, s)
    else:
        frag = frag_alt()
        if pos[0] != n:
            raise ValueError("trailing input (unbalanced?)")
    return frag, anchored_start, anchored_end


def _closure(states):
    out = set()
    stack = list(states)
    while stack:
        s = stack.pop()
        if s in out:
            continue
        out.add(s)
        stack.extend(s.eps)
    return out


def regex_match(pattern, text):
    (start_state, accept), anch_s, anch_e = _parse(pattern)
    starts = [0] if anch_s else range(len(text) + 1)
    for start in starts:
        cur = _closure([start_state])
        best = start if accept in cur and (not anch_e or start == len(text)) else None
        i = start
        while i < len(text) and cur:
            ch = text[i]
            nxt = set()
            for st in cur:
                for pred, dst in st.trans:
                    if pred(ch):
                        nxt.add(dst)
            cur = _closure(nxt)
            i += 1
            if accept in cur and (not anch_e or i == len(text)):
                best = i
        if best is not None:
            return (start, best)
    return None
