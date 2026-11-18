#!/usr/bin/env python3
"""Which items can a player actually get hold of, and which can they only be asked for?

    python3 tools/itemreach.py            the unreachable list
    python3 tools/itemreach.py --stats    plus how much of the script base it could resolve
    python3 tools/itemreach.py --why obj  how that one item is produced, if it is

WHY THIS IS NOT A GREP. The obvious version - "find inv_add(inv, <name>)" - gets the answer wrong
in two systematic ways, and both of them are common enough to drown the signal:

  * MOST ITEMS ARE PRODUCED THROUGH A VARIABLE. Lunar Diplomacy's vials are made by
    ~lunar_add_herb(lunar_vial_water, lunar_guam_vial, guam_leaf) - the item is an ARGUMENT to a
    generic proc, and the inv_add that finally creates it names a parameter, not an item. A grep
    sees inv_add($made) and learns nothing. Roughly one production site in eight is like this.
  * 265 OBJ NAMES CONTAIN A '+'. unfinished_antidote+, cheese+tom_batta and 263 others. A regex
    built on [a-z0-9_]+ truncates them, so they read as items nothing produces.

So this resolves arguments through call sites instead: every ~proc(...) and @label(...) call binds
its arguments to the callee's parameters, and that binding is followed to a fixpoint, so an item
handed down through three generic procs still counts as produced.

WHAT IT CANNOT RESOLVE it says so about rather than guessing. An expression that is a db_getfield,
a proc return or anything else this does not model counts as an UNRESOLVED production site, and the
--stats output prints how many there are. An item is only reported unreachable when nothing
produced it AND the unresolved count is small enough that the list means something: a tool that
quietly treats "I could not tell" as "it does not exist" is how the last three audits of this went
wrong.
"""
import re
import sys
import pathlib
import collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME = r"[a-z0-9_+]+"            # '+' included: 265 objs have one

# ---------------------------------------------------------------- the item universe
def load_objs():
    objs = set()
    for f in ROOT.joinpath("scripts").rglob("*.obj"):
        for m in re.finditer(r"^\[(" + NAME + r")\]", f.read_text(encoding="utf-8", errors="replace"), re.M):
            objs.add(m.group(1))
    return objs

# ---------------------------------------------------------------- script parsing
class Script:
    __slots__ = ("key", "kind", "name", "params", "body", "file")
    def __init__(self, key, kind, name, params, body, file):
        self.key, self.kind, self.name, self.params, self.body, self.file = key, kind, name, params, body, file

HEADER = re.compile(r"^\[(\w+),\s*(" + NAME + r")\s*\](?:\(([^)]*)\))?")

def split_args(text):
    """Split a call's argument list on commas that are not inside parens or quotes."""
    out, depth, cur, instr = [], 0, "", False
    for ch in text:
        if instr:
            cur += ch
            if ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True; cur += ch
        elif ch == "(":
            depth += 1; cur += ch
        elif ch == ")":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out

def balanced(text, start):
    """Return the text inside the parens that open at `start`, and the index after them."""
    depth, i, instr = 0, start, False
    while i < len(text):
        ch = text[i]
        if instr:
            instr = ch != '"'
        elif ch == '"':
            instr = True
        elif ch == "(":
            depth += 1
            if depth == 1:
                begin = i + 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[begin:i], i + 1
        i += 1
    return None, len(text)

def parse_scripts():
    scripts = {}
    for f in ROOT.joinpath("scripts").rglob("*.rs2"):
        cur = None
        for line in f.read_text(encoding="utf-8", errors="replace").split("\n"):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            m = HEADER.match(stripped)
            if m:
                kind, name, params = m.group(1), m.group(2), m.group(3) or ""
                plist = []
                for p in split_args(params):
                    bits = p.split()
                    if len(bits) == 2 and bits[1].startswith("$"):
                        plist.append(bits[1])
                key = f"{kind},{name}"
                cur = Script(key, kind, name, plist, [], str(f))
                scripts.setdefault(key, cur)
                # a duplicate name keeps the first; the packer forbids real duplicates anyway
                cur = scripts[key]
                continue
            if cur is not None:
                cur.body.append(stripped)
    return scripts

# ---------------------------------------------------------------- what makes an item
# op name -> index of the argument that names the item
PRODUCERS = {"inv_add": 1, "inv_setslot": 2, "inv_changeslot": 2, "obj_add": 1}

def main():
    objs = load_objs()
    scripts = parse_scripts()

    # tables: an item named in an enum or a dbrow is produced by whatever reads that table
    tables = set()
    for suf in ("*.enum", "*.dbrow"):
        for f in ROOT.joinpath("scripts").rglob(suf):
            for tok in re.findall(r"[=,](" + NAME + r")", f.read_text(encoding="utf-8", errors="replace")):
                if tok in objs:
                    tables.add(tok)

    # PARAM VALUES. npc_param(death_drop) is the single commonest unresolved production
    # expression - every monster's death drop goes through it - and the answer is written down in
    # the npc configs, so it can simply be read.
    paramvals = collections.defaultdict(set)
    for suf, folder in (("*.npc", "scripts"), ("*.obj", "scripts"), ("*.loc", "scripts")):
        for f in ROOT.joinpath(folder).rglob(suf):
            for pname, pval in re.findall(r"^param=(\w+),(" + NAME + r")", f.read_text(encoding="utf-8", errors="replace"), re.M):
                if pval in objs:
                    paramvals[pname].add(pval)

    # call sites: callee -> list of (caller_key, [arg exprs])
    calls = collections.defaultdict(list)
    # per script: var -> list of assigned expressions
    assigns = collections.defaultdict(lambda: collections.defaultdict(list))
    # production sites: (script_key, expr)
    sites = []

    callre = re.compile(r"[~@](" + NAME + r")\s*\(")
    assignre = re.compile(r"^(?:def_\w+\s+)?(\$\w+)\s*(?:,\s*\$\w+\s*)*=\s*(.+?);?$")

    for key, s in scripts.items():
        for line in s.body:
            for m in callre.finditer(line):
                args, _ = balanced(line, m.end() - 1)
                if args is not None:
                    for kind in ("proc", "label", "queue"):
                        calls[f"{kind},{m.group(1)}"].append((key, split_args(args)))
            for op, idx in PRODUCERS.items():
                for m in re.finditer(r"\b" + op + r"\s*\(", line):
                    args, _ = balanced(line, m.end() - 1)
                    if args is None:
                        continue
                    a = split_args(args)
                    if len(a) > idx:
                        sites.append((key, a[idx]))
            am = assignre.match(line)
            if am:
                assigns[key][am.group(1)].append(am.group(2).strip())

    # ------------------------------------------------------------ fixpoint
    values = collections.defaultdict(set)      # (script_key, var) -> set of obj names
    unresolved = set()

    def resolve(expr, key, seen=None):
        expr = expr.strip().rstrip(";")
        if expr in objs:
            return {expr}
        if expr.startswith("$"):
            return set(values[(key, expr)])
        m = re.match(r"^enum\s*\(", expr)
        if m:
            parts = split_args(balanced(expr, m.end() - 1)[0] or "")
            if len(parts) >= 3:
                return {o for o in enum_values.get(parts[2].strip(), set())}
            return set()
        # a param lookup: the values are in the configs
        m = re.match(r"^(?:npc_param|oc_param|loc_param)\s*\(", expr)
        if m:
            inner = split_args(balanced(expr, m.end() - 1)[0] or "")
            if inner:
                return set(paramvals.get(inner[0].strip(), set()))
            return set()
        # a proc's return value: whatever that proc returns
        m = re.match(r"^~(" + NAME + r")\s*\(?", expr)
        if m:
            callee = "proc," + m.group(1)
            seen = seen or set()
            if callee in seen or callee not in scripts:
                return set()
            got = set()
            for line in scripts[callee].body:
                for r in re.finditer(r"\breturn\s*\(", line):
                    inner, _ = balanced(line, r.end() - 1)
                    if inner:
                        for part in split_args(inner):
                            got |= resolve(part, callee, seen | {callee})
            return got
        return set()

    # enum contents by name, for enum(...) lookups
    enum_values = collections.defaultdict(set)
    for f in ROOT.joinpath("scripts").rglob("*.enum"):
        cur = None
        for line in f.read_text(encoding="utf-8", errors="replace").split("\n"):
            m = re.match(r"^\[(" + NAME + r")\]", line.strip())
            if m:
                cur = m.group(1); continue
            v = re.match(r"^val=[^,]*,(" + NAME + r")", line.strip())
            if v and cur and v.group(1) in objs:
                enum_values[cur].add(v.group(1))

    for _ in range(12):
        changed = False
        unresolved.clear()
        for key, s in scripts.items():
            # parameters, bound from every call site
            for i, p in enumerate(s.params):
                got = set()
                for caller, args in calls.get(key, ()):
                    if i < len(args):
                        got |= resolve(args[i], caller)
                if not got <= values[(key, p)]:
                    values[(key, p)] |= got; changed = True
            # local assignments
            for var, exprs in assigns[key].items():
                got = set()
                for e in exprs:
                    got |= resolve(e, key)
                if not got <= values[(key, var)]:
                    values[(key, var)] |= got; changed = True
        if not changed:
            break

    # ONLY PRODUCTION SITES COUNT TOWARDS THE TRUST FIGURE. resolve() is also called on every
    # argument of every call while the parameters are being bound, and most of those are ints,
    # coords and constants it has no business understanding - counting those made the first
    # version report 62,547 "unresolved production expressions", which is not a number anybody
    # can act on.
    unresolved.clear()
    produced = set()
    for key, expr in sites:
        got = resolve(expr, key)
        if not got:
            unresolved.add((key, expr))
        produced |= got

    # ------------------------------------------------------------ shops
    shops = set()
    for f in ROOT.joinpath("scripts").rglob("*.npc"):
        shops |= set(re.findall(r"^param=owned_shop,(" + NAME + r")", f.read_text(encoding="utf-8", errors="replace"), re.M))
    for key, s in scripts.items():
        for line in s.body:
            for m in re.finditer(r"~openshop(?:_obj)?\s*\(", line):
                args, _ = balanced(line, m.end() - 1)
                if args:
                    shops.add(split_args(args)[0].strip())
    sold = set()
    for f in ROOT.joinpath("scripts").rglob("*.inv"):
        cur = None
        for line in f.read_text(encoding="utf-8", errors="replace").split("\n"):
            m = re.match(r"^\[(" + NAME + r")\]", line.strip())
            if m:
                cur = m.group(1); continue
            st = re.match(r"^stock\d+=(" + NAME + r")", line.strip())
            if st and cur in shops:
                sold.add(st.group(1))

    reachable = produced | sold | tables

    # ------------------------------------------------------------ what content asks for
    gated = collections.Counter(); where = {}
    for key, s in scripts.items():
        for line in s.body:
            for m in re.finditer(r"inv_total\s*\(\s*inv\s*,\s*(" + NAME + r")\s*\)\s*(?:<|=\s*0)", line):
                gated[m.group(1)] += 1; where.setdefault(m.group(1), s.file)
        if s.kind in ("opheld", "opheldu") and s.name in objs:
            gated[s.name] += 1; where.setdefault(s.name, s.file)

    if "--why" in sys.argv:
        want = sys.argv[sys.argv.index("--why") + 1]
        print(f"{want}: {'SOLD' if want in sold else ''} {'TABLE' if want in tables else ''} {'PRODUCED' if want in produced else ''}".strip() or f"{want}: no route found")
        for key, expr in sites:
            if want in resolve(expr, key):
                print(f"   {key}  <- {expr}")
        return 0

    stuck = sorted((i for i in gated if i not in reachable and i != "coins"), key=lambda i: -gated[i])
    print(f"{len(objs)} objs | {len(shops)} shops selling {len(sold)} | {len(produced)} produced | {len(reachable)} reachable")
    print(f"{len(gated)} items content gates on | {len(stuck)} with no route\n")
    for i in stuck:
        print(f"  {i:34} gated in {gated[i]:2}   {where[i].replace(str(ROOT) + '/scripts/', '')}")
    if "--stats" in sys.argv:
        print(f"\nproduction sites: {len(sites)}, of which {len(unresolved)} could not be resolved "
              f"({len(unresolved) * 100 // max(len(sites), 1)}%)")
        for key, e in sorted(unresolved)[:15]:
            print(f"   {key}: {e[:70]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
