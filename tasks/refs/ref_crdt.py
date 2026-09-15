"""Reference: RGA text CRDT with tombstones, buffering, idempotence."""


class Replica:
    def __init__(self, site_id: str):
        self.site = site_id
        self.counter = 0
        self.nodes = []            # list of dicts: id, origin, ch, deleted
        self.by_id = {}            # id-tuple -> index refreshed lazily
        self.seen = set()          # op keys for idempotence
        self.pending = []          # buffered ops

    # ---------- helpers ----------
    def _index_of(self, ident):
        for i, nd in enumerate(self.nodes):
            if nd["id"] == ident:
                return i
        return None

    def _visible_nodes(self):
        return [nd for nd in self.nodes if not nd["deleted"]]

    def text(self):
        return "".join(nd["ch"] for nd in self.nodes if not nd["deleted"])

    # ---------- local ops ----------
    def local_insert(self, pos, ch):
        vis = self._visible_nodes()
        origin = None if pos == 0 else list(vis[pos - 1]["id"])
        self.counter += 1
        op = {"type": "insert", "id": [self.counter, self.site],
              "origin": origin, "ch": ch}
        self._place(op)
        self.seen.add(self._key(op))
        return op

    def local_delete(self, pos):
        vis = self._visible_nodes()
        target = vis[pos]
        op = {"type": "delete", "target": list(target["id"])}
        target["deleted"] = True
        self.seen.add(self._key(op))
        return op

    # ---------- remote ----------
    @staticmethod
    def _key(op):
        if op["type"] == "insert":
            return ("i", tuple(op["id"]))
        return ("d", tuple(op["target"]))

    def apply(self, op):
        if self._key(op) in self.seen:
            return
        if self._try_apply(op):
            self.seen.add(self._key(op))
            self._drain()
        else:
            self.pending.append(op)

    def _drain(self):
        progressed = True
        while progressed:
            progressed = False
            for op in list(self.pending):
                if self._key(op) in self.seen:
                    self.pending.remove(op)
                    progressed = True
                elif self._try_apply(op):
                    self.seen.add(self._key(op))
                    self.pending.remove(op)
                    progressed = True

    def _try_apply(self, op):
        if op["type"] == "insert":
            ident = tuple(op["id"])
            if ident in {tuple(nd["id"]) for nd in self.nodes}:
                return True
            origin = tuple(op["origin"]) if op["origin"] is not None else None
            if origin is not None and self._index_of(list(origin)) is None:
                return False
            self.counter = max(self.counter, op["id"][0])
            self._place(op)
            return True
        else:
            idx = self._index_of(op["target"])
            if idx is None:
                return False
            self.nodes[idx]["deleted"] = True
            return True

    # ---------- RGA placement ----------
    def _place(self, op):
        new_id = tuple(op["id"])
        origin = tuple(op["origin"]) if op["origin"] is not None else None
        o_idx = -1 if origin is None else self._index_of(list(origin))
        # positions of each node's origin, in the CURRENT sequence
        idx_of = {tuple(nd["id"]): i for i, nd in enumerate(self.nodes)}

        def origin_idx(nd):
            if nd["origin"] is None:
                return -1
            return idx_of[tuple(nd["origin"])]

        i = o_idx + 1
        while i < len(self.nodes):
            m = self.nodes[i]
            m_oidx = origin_idx(m)
            if m_oidx < o_idx:
                break                      # left our origin's subtree region
            if m_oidx == o_idx:
                if tuple(m["id"]) > new_id:
                    # skip m and its whole subtree (contiguous nodes whose
                    # origin index >= i)
                    j = i + 1
                    while j < len(self.nodes) and origin_idx(self.nodes[j]) >= i:
                        j += 1
                    i = j
                    continue
                break                      # sibling with smaller id: go before it
            i += 1                          # inside a skipped/unrelated subtree
        self.nodes.insert(i, {"id": list(new_id), "origin": op["origin"],
                              "ch": op.get("ch", ""), "deleted": False})
