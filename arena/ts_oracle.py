"""TalentSearch Round-4 oracle: naive reference parser/scorer + pool generator.
Correctness-first, speed-irrelevant. grade4.py compares candidate apps to this.
Kept deliberately independent from any indexed implementation.
"""
import datetime as dt
import random
import re

REF_DATE = dt.date(2026, 8, 1)

# ---------- tokenizer / parser (naive recursive descent) ----------

TOKEN_RE = re.compile(r'''
    \s*(?:
      (?P<lparen>\() | (?P<rparen>\)) |
      (?P<quoted>"[^"]*") |
      (?P<word>[^\s()"]+)
    )''', re.VERBOSE)


class QueryError(Exception):
    def __init__(self, msg, pos):
        super().__init__(msg)
        self.pos = pos


def tokenize(q):
    toks, i = [], 0
    while i < len(q):
        m = TOKEN_RE.match(q, i)
        if not m or m.end() == m.start():
            raise QueryError("bad token", i)
        if m.lastgroup == "lparen":
            toks.append(("(", m.start("lparen")))
        elif m.lastgroup == "rparen":
            toks.append((")", m.start("rparen")))
        elif m.lastgroup == "quoted":
            toks.append(("term:" + m.group("quoted")[1:-1].strip().lower(), m.start("quoted")))
        else:
            toks.append((m.group("word"), m.start("word")))
        i = m.end()
    return toks


def parse(q):
    toks = tokenize(q)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else (None, len(q))

    def take():
        t = peek(); pos[0] += 1; return t

    def parse_or():
        node = parse_and()
        while peek()[0] and peek()[0].upper() == "OR":
            take()
            node = ("or", node, parse_and())
        return node

    def parse_and():
        parts = [parse_unary()]
        while True:
            t, _ = peek()
            if t is None or t == ")" or t.upper() == "OR":
                break
            if t.upper() == "AND":
                take()
                continue
            parts.append(parse_unary())
        node = parts[0]
        for p in parts[1:]:
            node = ("and", node, p)
        return node

    def parse_unary():
        t, p = peek()
        if t is None:
            raise QueryError("unexpected end of query", p)
        if t.upper() == "NOT":
            take()
            return ("not", parse_unary())
        if t == "(":
            take()
            node = parse_or()
            t2, p2 = peek()
            if t2 != ")":
                raise QueryError("expected )", p2)
            take()
            return node
        if t == ")":
            raise QueryError("unexpected )", p)
        take()
        return parse_pred(t, p)

    node = parse_or()
    if pos[0] != len(toks):
        raise QueryError("trailing input", peek()[1])
    return node


NUM_PRED_RE = re.compile(r"^(salary|years)(<=|>=)(\d+)$", re.I)
SKILL_YEARS_RE = re.compile(r"^skill:([^><]+)(?:>=(\d+))?$", re.I)


def parse_pred(tok, p):
    if tok.startswith("term:"):
        return ("term", tok[5:])
    m = NUM_PRED_RE.match(tok)
    if m:
        return ("num", m.group(1).lower(), m.group(2), int(m.group(3)))
    low = tok.lower()
    m = SKILL_YEARS_RE.match(tok)
    if m:
        return ("skill", m.group(1).strip().lower(), int(m.group(2)) if m.group(2) else None)
    for field in ("location", "remote", "level", "tag"):
        if low.startswith(field + ":"):
            val = tok[len(field) + 1:].strip().lower()
            if not val:
                raise QueryError("empty value for " + field, p)
            if field == "remote":
                if val not in ("true", "false"):
                    raise QueryError("remote wants true/false", p)
                return ("remote", val == "true")
            return (field, val)
    if ":" in tok:
        raise QueryError("unknown field", p)
    return ("term", low)


# ---------- candidate normalization / matching ----------

def norm_cand(c):
    skills = {}
    for s in c.get("skills", []):
        n = str(s.get("name", "")).strip().lower()
        if n:
            skills[n] = max(skills.get(n, 0), float(s.get("years", 0)))
    return {
        "id": c["id"], "name": c["name"], "title": str(c.get("title", "")),
        "skills": skills,
        "location": str(c.get("location", "")).strip().lower(),
        "remote_ok": bool(c.get("remote_ok", False)),
        "salary": float(c.get("salary_expectation", 0)),
        "years_total": float(c.get("years_total", 0)),
        "level": str(c.get("level", "")).strip().lower(),
        "last_active": str(c.get("last_active", "1970-01-01")),
        "tags": {str(t).strip().lower() for t in c.get("tags", [])},
    }


def pred_matches(pred, c):
    kind = pred[0]
    if kind == "term":
        t = pred[1]
        return t in c["skills"] or t in c["title"].lower()
    if kind == "skill":
        name, min_y = pred[1], pred[2]
        if name not in c["skills"]:
            return False
        return True if min_y is None else c["skills"][name] >= min_y
    if kind == "num":
        val = c["salary"] if pred[1] == "salary" else c["years_total"]
        return val <= pred[3] if pred[2] == "<=" else val >= pred[3]
    if kind == "remote":
        return c["remote_ok"] == pred[1]
    if kind == "location":
        return c["location"] == pred[1]
    if kind == "level":
        return c["level"] == pred[1]
    if kind == "tag":
        return pred[1] in c["tags"]
    raise AssertionError(kind)


def eval_node(node, c):
    if node[0] == "and":
        return eval_node(node[1], c) and eval_node(node[2], c)
    if node[0] == "or":
        return eval_node(node[1], c) or eval_node(node[2], c)
    if node[0] == "not":
        return not eval_node(node[1], c)
    return pred_matches(node, c)


def positive_preds(node, out=None, under_not=False):
    if out is None:
        out = []
    if node[0] in ("and", "or"):
        positive_preds(node[1], out, under_not)
        positive_preds(node[2], out, under_not)
    elif node[0] == "not":
        positive_preds(node[1], out, True)
    elif not under_not:
        out.append(node)
    return out


def query_features(node):
    """Deduped positive terms/skill-preds + salary<=N / remote:true flags."""
    terms, skills = {}, {}
    salary_cap, remote_true = None, False
    for p in positive_preds(node):
        if p[0] == "term":
            terms[p[1]] = True
        elif p[0] == "skill":
            skills.setdefault(p[1], True)
        elif p[0] == "num" and p[1] == "salary" and p[2] == "<=":
            salary_cap = p[3] if salary_cap is None else min(salary_cap, p[3])
        elif p[0] == "remote" and p[1] is True:
            remote_true = True
    return terms, skills, salary_cap, remote_true


def days_since(iso):
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return 10 ** 6
    return (REF_DATE - d).days


def score(c, feats):
    terms, skills, salary_cap, remote_true = feats
    sk_pts = 0.0
    matched_skill_names = set()
    for name in skills:
        if name in c["skills"]:
            sk_pts += 10 + min(c["skills"][name], 10)
            matched_skill_names.add(name)
    title_pts = 0.0
    for t in terms:
        if t in c["skills"]:
            if t not in matched_skill_names:
                sk_pts += 10 + min(c["skills"][t], 10)
                matched_skill_names.add(t)
        elif t in c["title"].lower():
            title_pts += 5
    d = days_since(c["last_active"])
    rec = 15 if d <= 30 else 10 if d <= 90 else 5 if d <= 365 else 0
    sal = 0
    if salary_cap is not None:
        if c["salary"] <= 0.8 * salary_cap:
            sal = 5
        elif c["salary"] <= salary_cap:
            sal = 2
    rem = 3 if (remote_true and c["remote_ok"]) else 0
    total = round(sk_pts + title_pts + rec + sal + rem, 2)
    return total, {"skills": round(sk_pts, 2), "title": round(title_pts, 2),
                   "recency": rec, "salary_fit": sal, "remote": rem}


def search(pool_norm, q, page=1, page_size=20):
    node = parse(q) if q.strip() else None
    matched = [c for c in pool_norm if node is None or eval_node(node, c)]
    feats = query_features(node) if node is not None else ({}, {}, None, False)
    rows = []
    for c in matched:
        s, br = score(c, feats)
        rows.append((s, c["last_active"], c["id"], c, br))
    rows.sort(key=lambda r: (-r[0], tuple(-ord(ch) for ch in r[1]), r[2]))
    page_size = min(page_size, 100)
    start = (page - 1) * page_size
    sliced = rows[start:start + page_size]
    return {
        "total": len(rows), "page": page, "page_size": page_size,
        "has_next": start + page_size < len(rows),
        "results": [{"id": c["id"], "name": c["name"], "title": c["title"],
                     "score": s, "breakdown": br} for s, la, i, c, br in sliced],
    }


def facets(pool_norm, q):
    node = parse(q) if q.strip() else None
    matched = [c for c in pool_norm if node is None or eval_node(node, c)]
    sk, loc = {}, {}
    for c in matched:
        for n in c["skills"]:
            sk[n] = sk.get(n, 0) + 1
        if c["location"]:
            loc[c["location"]] = loc.get(c["location"], 0) + 1
    top = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return {"skills": [list(kv) for kv in top(sk)],
            "locations": [list(kv) for kv in top(loc)]}


# ---------- deterministic pool generator ----------

SKILL_NAMES = ["python", "pytorch", "sql", "go", "rust", "react", "typescript",
               "kubernetes", "terraform", "aws", "gcp", "spark", "kafka",
               "sourcing", "ats", "figma", "swift", "java", "c++", "machine learning"]
TITLES = ["ML Engineer", "Backend Engineer", "Data Engineer", "Recruiter",
          "Platform Engineer", "Frontend Engineer", "DevOps Engineer",
          "Engineering Manager", "Machine Learning Researcher", "Full-Stack Engineer"]
LOCATIONS = ["Berlin", "London", "New York", "Remote", "Austin", "Toronto",
             "Amsterdam", "Singapore", "Lisbon", "Warsaw"]
LEVELS = ["junior", "mid", "senior", "staff"]
TAGS = ["contractor", "open-source", "ex-faang", "founder", "phd", "bootcamp"]


def gen_pool(n, seed=4242):
    rng = random.Random(seed)
    pool = []
    for i in range(1, n + 1):
        nsk = rng.randint(2, 6)
        names = rng.sample(SKILL_NAMES, nsk)
        lvl = rng.choices(LEVELS, weights=[2, 4, 3, 1])[0]
        base_year = {"junior": 1, "mid": 3, "senior": 6, "staff": 9}[lvl]
        skills = [{"name": nm, "years": max(0, base_year + rng.randint(-2, 4))}
                  for nm in names]
        yt = base_year + rng.randint(0, 5)
        pool.append({
            "id": i,
            "name": f"Cand {i:06d}",
            "title": f"{rng.choice(LEVELS).title()} {rng.choice(TITLES)}",
            "skills": skills,
            "location": rng.choice(LOCATIONS),
            "remote_ok": rng.random() < 0.55,
            "salary_expectation": rng.randrange(60000, 240001, 5000),
            "years_total": yt,
            "level": lvl,
            "last_active": (REF_DATE - dt.timedelta(days=rng.randint(0, 700))).isoformat(),
            "tags": rng.sample(TAGS, rng.randint(0, 2)),
        })
    return pool


PERF_QUERIES = [
    "skill:python>=3", "location:berlin remote:true", "python OR go",
    '"machine learning" AND level:senior', "skill:rust salary<=150000",
    "(skill:react OR skill:typescript) AND NOT tag:contractor",
    "kafka years>=5", "level:staff", "sourcing OR ats", "skill:kubernetes>=2 location:london",
    "NOT remote:true salary>=100000 skill:java", "spark AND aws", "tag:phd",
    '(python OR "machine learning") AND salary<=180000',
    "skill:terraform location:amsterdam", "go years<=4", "level:junior remote:true",
    "skill:swift OR skill:figma", "aws AND gcp AND NOT level:junior",
    "tag:open-source skill:python", "c++ years>=8", "location:warsaw OR location:lisbon",
    "react NOT skill:typescript", "salary<=90000", "skill:sql>=5 level:mid",
]
