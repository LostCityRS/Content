"""Symbol and signature battery for the two new .rs2 files, from claude/rs2-compile-traps.md."""
import struct, re, sys, os
import json as _json
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['scripts/skill_construction/scripts/poh.rs2', 'scripts/skill_construction/scripts/poh_test.rs2',
         'scripts/skill_construction/scripts/poh_portal.rs2', 'scripts/skill_construction/scripts/poh_build.rs2',
         'scripts/skill_construction/scripts/sawmill.rs2',
         'scripts/skill_construction/scripts/poh_furniture.rs2',
         'scripts/skill_construction/scripts/poh_menus.rs2',
         'scripts/skill_construction/scripts/poh_furn_ops.rs2',
         'scripts/skill_construction/scripts/poh_tablets.rs2',
         'scripts/skill_construction/scripts/poh_portal_chamber.rs2',
         'scripts/skill_construction/scripts/poh_combat_ring.rs2',
         'scripts/skill_construction/scripts/poh_combat.rs2',
         'scripts/skill_construction/scripts/poh_rug.rs2',
         'scripts/skill_construction/scripts/poh_decor.rs2',
         'scripts/skill_construction/scripts/poh_stores.rs2',
         'scripts/skill_construction/scripts/poh_hedge.rs2']
fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def before(hay, a, b):
    """a appears before b - and False rather than an exception when either is missing.

    A CHECK WHOSE OWN CONDITION RAISES IS A CRASH, NOT A CHECK. hay.index(x) throws when x is
    gone, which is exactly what a mutation removes: the battery blew up, the mutation harness
    counted the non-zero exit as caught, and no check had fired. Five were found that way in one
    afternoon, and each was hiding the fact that nothing asserted the thing was there at all.
    """
    return a in hay and b in hay and hay.index(a) < hay.index(b)

def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

src = {f: read(f) for f in FILES}
def strip(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    out = []
    for line in t.split('\n'):
        line = re.sub(r'"[^"]*"', '""', line)
        out.append(line.split('//')[0])
    return '\n'.join(out)
clean = {f: strip(t) for f, t in src.items()}
alltext = '\n'.join(clean.values())

print('1. balance')
for f, t in clean.items():
    check(t.count('(') == t.count(')'), '%s parens %d/%d' % (os.path.basename(f), t.count('('), t.count(')')))
    check(t.count('{') == t.count('}'), '%s braces %d/%d' % (os.path.basename(f), t.count('{'), t.count('}')))

print('2. no @label jump inside a proc (trap 5b)')
bad = []
for f, t in clean.items():
    cur = None
    for ln in t.split('\n'):
        m = re.match(r'^\[(\w+),', ln)
        if m: cur = m.group(1)
        if re.search(r'@\w+[;(]', ln) and cur == 'proc': bad.append((f, ln.strip()))
check(not bad, 'none, got %s' % bad)

print('3. declared scripts are unique, and nothing is declared twice')
decl = re.findall(r'^\[(\w+),(\w+)\]', alltext, re.M)
check(len(decl) == len(set(decl)), 'no duplicate [kind,name] in the new files')
names = {n for k, n in decl}
kinds = {}
for k, n in decl:
    kinds[k] = kinds.get(k, 0) + 1
print('   declares: ' + ', '.join('%d %s' % (v, k) for k, v in sorted(kinds.items())))

print('4. every ~proc call resolves')
# Against the WHOLE repo, not just these files: poh_portal.rs2 talks to the shared dialogue procs
# (~chatnpc, ~p_choice2) and a whitelist would only record that I believed they exist.
repo_procs = set()
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if fn.endswith('.rs2'):
            with open(os.path.join(root, fn), encoding='utf-8', errors='replace') as fh:
                repo_procs |= set(re.findall(r'^\[(?:proc|label|debugproc),(\w+)\]', fh.read(), re.M))
called = set(re.findall(r'~(\w+)', alltext))
unknown = sorted(called - names - repo_procs)
check(not unknown, 'unresolved: %s' % unknown)

print('5. every %varp resolves against pack/varp.pack')
varps = {l.split('=', 1)[1] for l in open(C + '/pack/varp.pack').read().split('\n') if '=' in l}
used = set(re.findall(r'%(\w+)', alltext))
check(not (used - varps), 'unresolved: %s' % sorted(used - varps))
print('   uses: ' + ', '.join(sorted(used)))

print('6. every ^constant resolves')
# Against every .constant in the repo, for the same reason check 4 walks every .rs2: this round
# reaches into the spell book's constants (^varrock_teleport, ^enchant_lvl1) and the quest ones
# (^elena_complete), and a hand-kept list of files would only record which ones I remembered.
consts = set()
for _root, _, _fs in os.walk(os.path.join(C, 'scripts')):
    for _fn in _fs:
        if _fn.endswith('.constant'):
            consts |= set(re.findall(r'^\^(\w+)\s*=', read(os.path.relpath(os.path.join(_root, _fn), C)), re.M))
consts |= set(re.findall(r'^\^(\w+)\s*=', read('scripts/engine.constant'), re.M))
usedc = set(re.findall(r'\^(\w+)', alltext))
check(not (usedc - consts), 'unresolved: %s' % sorted(usedc - consts))

print('7. every enum name resolves')
# pack/enum.pack is GENERATED and gitignored - deploy.sh deletes it before every build - so the
# .enum sources are the only honest answer to "what will exist after the build". This used to
# prefer the pack when one happened to be lying around, and a STALE pack then reported twelve
# perfectly good tables as unresolved (and would just as happily have passed a table that had
# since been deleted). The sources are what the packer reads; read those, always.
enums = set()
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if fn.endswith('.enum'):
            with open(os.path.join(root, fn), encoding='utf-8', errors='replace') as fh:
                enums |= set(re.findall(r'^\[(\w+)\]', fh.read(), re.M))
usede = set(re.findall(r'enum\(\s*\w+\s*,\s*\w+\s*,\s*(\w+)\s*,', alltext))
check(not (usede - enums), 'unresolved: %s (used %s)' % (sorted(usede - enums), sorted(usede)))

print('8. the poh_hotspot category is really defined')
# pack/category.pack is GENERATED and gitignored - categories come from category= lines in the
# configs, so the pack in a working copy can be older than the content and proves nothing.
locs = read('scripts/skill_construction/configs/poh_templates.loc')
check(locs.count('category=poh_hotspot') > 0,
      '%d locs carry category=poh_hotspot' % locs.count('category=poh_hotspot'))

print('9. every command call matches its engine.rs2 signature')
sig = {}
for m in re.finditer(r'^\[command,(\w+)\]\s*(\(([^)]*)\))?\s*(\(([^)]*)\))?', read('scripts/engine.rs2'), re.M):
    name, args, rets = m.group(1), m.group(3), m.group(5)
    if args is None:
        sig[name] = (None, None)
    else:
        n = 0 if args.strip() == '' else len([a for a in args.split(',') if a.strip()])
        sig[name] = (n, (rets or '').strip())
def top_args(s):
    """split a call's argument text on top-level commas"""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip(): out.append(cur)
    return out
bad = []
for f, t in clean.items():
    body = '\n'.join(l for l in t.split('\n') if not l.startswith('[command,'))
    for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', body):
        name = m.group(1)
        if name not in sig: continue
        want = sig[name][0]
        if want is None: continue
        # find the matching close paren
        i = m.end(); depth = 1
        while i < len(body) and depth:
            if body[i] == '(': depth += 1
            elif body[i] == ')': depth -= 1
            i += 1
        got = len(top_args(body[m.end():i - 1]))
        if got != want:
            bad.append('%s: %s takes %d, given %d' % (os.path.basename(f), name, want, got))
check(not bad, 'arity mismatches: %s' % bad)
used_cmds = sorted({m.group(1) for f, t in clean.items() for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', t) if m.group(1) in sig})
print('   commands used: ' + ', '.join(used_cmds))

print('10. no bare call to a command that returns something (trap 2)')
bad = []
for f, t in clean.items():
    for ln in t.split('\n'):
        s2 = ln.strip()
        m = re.match(r'^(\w+)\(.*\);$', s2)
        if m and m.group(1) in sig and sig[m.group(1)][1]:
            bad.append('%s: %s' % (os.path.basename(f), s2))
check(not bad, 'discarded returns: %s' % bad)

print('11. line endings')
for f in FILES + ['scripts/skill_construction/configs/poh_rooms.enum',
                  'scripts/skill_construction/configs/poh_furniture.enum',
                  'scripts/skill_construction/interfaces/poh_roommenu.if',
    'scripts/skill_construction/interfaces/poh_tabletmenu.if',
                  'scripts/skill_construction/interfaces/poh_furnmenu.if',
                  'scripts/skill_construction/configs/construction.varp',
                  'scripts/skill_construction/configs/construction.constant',
                  'scripts/skill_construction/configs/poh_portal.loc',
                  'scripts/skill_construction/configs/poh_portal.npc',
                  'maps/m46_50.jm2']:
    b = open(os.path.join(C, f), 'rb').read()
    # .gitattributes sets `* text=auto`, so the repo stores LF and a Windows working copy has
    # CRLF. Either is correct; a file with SOME of each is a hand edit that will diff whole.
    crlf, lf = b.count(b'\r\n'), b.count(b'\n')
    check(b'\r\r' not in b and crlf in (0, lf), '%s has one line ending throughout (%s)'
          % (os.path.basename(f), 'CRLF' if crlf else 'LF'))
for f in ['pack/varp.pack', 'pack/loc.pack', 'pack/npc.pack', 'pack/interface.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))

print('12. pack ids are unique, and the new ones sit above what was there')
# Not contiguity: varp.pack is missing id 746 upstream and has always built fine. What matters is
# that nothing is claimed twice and that the ids added here were free.
# 1150-1152 are three debug varps that exist only in the laptop's working copy, so they are not
# in this list and the check does not demand contiguity - see the note above.
NEW = {'pack/varp.pack': list(range(876, 1150)) + [1153],
       'pack/loc.pack': [15296, 15297], 'pack/npc.pack': [3920, 3921, 3922, 3923]}
for f in ['pack/varp.pack', 'pack/loc.pack', 'pack/npc.pack']:
    ids = [int(l.split('=', 1)[0]) for l in open(os.path.join(C, f)).read().split('\n') if '=' in l]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(all(ids.count(i) == 1 for i in NEW[f]), '%s: every id added here appears exactly once' % os.path.basename(f))
    # Was `== max(NEW[f])`, i.e. "the POH round is still the newest thing in this pack". That was
    # true when it was written and is a landmine for every round after it - bank tabs added varps
    # 1154-1162 and it went red for a reason that had nothing to do with Construction. The part
    # worth keeping is that this round's block is present, unduplicated and not stranded above the
    # top of the file, which >= still says.
    check(max(ids) >= max(NEW[f]), '%s: the new block is not stranded above the top of the file' % os.path.basename(f))

# =========================================================================== the portal round

def packmap(f):
    out = {}
    for l in open(os.path.join(C, f)).read().split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[n] = int(i)
    return out

LOCS = packmap('pack/loc.pack')
NPCS = packmap('pack/npc.pack')
MODELS = set(packmap('pack/model.pack'))
SEQS = set(packmap('pack/seq.pack'))
OBJS = set(packmap('pack/obj.pack'))

def blocks(text):
    """[name] -> {key: [values]} for a config file"""
    out, cur = {}, None
    for line in text.split('\n'):
        line = line.split('//')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            cur = line.strip('[]')
            out[cur] = {}
        elif '=' in line and cur:
            k, v = line.split('=', 1)
            out[cur].setdefault(k, []).append(v)
    return out

print('13. the new locs and npc are registered and used by name')
LOCCFG = blocks(read('scripts/skill_construction/configs/poh_portal.loc'))
NPCCFG = blocks(read('scripts/skill_construction/configs/poh_portal.npc'))
check(sorted(LOCCFG) == ['poh_exit_portal', 'poh_house_portal'], 'poh_portal.loc defines %s' % sorted(LOCCFG))
check(sorted(NPCCFG) == ['poh_estate_agent'], 'poh_portal.npc defines %s' % sorted(NPCCFG))
for n in LOCCFG:
    check(n in LOCS, '%s is in loc.pack (id %s)' % (n, LOCS.get(n)))
for n in NPCCFG:
    check(n in NPCS, '%s is in npc.pack (id %s)' % (n, NPCS.get(n)))

print('14. every model, anim and obj the round names really exists')
# The loc packer looks up the bare name first and falls back to name_8 (LocConfig.ts); npc models
# are looked up as written.
for n, cfg in LOCCFG.items():
    for k in ('model', 'model2', 'model3', 'model4', 'model5'):
        for v in cfg.get(k, []):
            check(v in MODELS or (v + '_8') in MODELS, '%s %s=%s resolves' % (n, k, v))
    for v in cfg.get('anim', []):
        check(v in SEQS, '%s anim=%s is in seq.pack' % (n, v))
for n, cfg in NPCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^(model|head)\d+$', k):
            for v in vs:
                check(v in MODELS, '%s %s=%s resolves' % (n, k, v))
# The trailing [,)] is load-bearing: without it `inv_add(inv, enum(int, obj, ...))` reports that
# there is no obj called "enum". A name followed by "(" is a call, not an item.
objs_used = set(re.findall(r'inv_(?:total|del|add)\(\s*\w+\s*,\s*(\w+)\s*[,)]', alltext))
for o in sorted(objs_used):
    check(o in OBJS, 'obj %s is in obj.pack' % o)

CONSTF = read('scripts/skill_construction/configs/construction.constant')
print('15. six towns: a portal on the map in each, on free tiles, next to where leaving lands you')
# There were five more of these as of the Relocate round, and the thing that makes them checkable is
# that the SAME anchor is written down twice - once in the .jm2 and once in poh_loc_portal, which is
# what the click test compares loc_coord against. If those two ever disagree, the portal in that town
# stops opening anybody's house and nothing else notices.
LOCENUM = read('scripts/skill_construction/configs/poh_locations.enum')

def coordtable(txt, name):
    b = txt.split('[%s]' % name)[1].split('\n[')[0]
    out = {}
    for m in re.finditer(r'^val=(\d+),(\d+)_(\d+)_(\d+)_(\d+)_(\d+)$', b, re.M):
        out[int(m.group(1))] = tuple(int(g) for g in m.groups()[1:])
    return out

PORTAL_AT = coordtable(LOCENUM, 'poh_loc_portal')
EXIT_AT = coordtable(LOCENUM, 'poh_loc_exit')
NTOWN = int(re.search(r'^\^poh_location_count\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(sorted(PORTAL_AT) == list(range(NTOWN)), 'poh_loc_portal covers all %d towns' % NTOWN)
check(sorted(EXIT_AT) == list(range(NTOWN)), 'poh_loc_exit covers all %d towns' % NTOWN)
check(len(set(PORTAL_AT.values())) == NTOWN, 'no two towns share a portal tile')
check(len(set(EXIT_AT.values())) == NTOWN, 'no two towns share a landing tile')

def readmap(mx, mz):
    sec, land, mlocs, mnpcs = None, {}, {}, {}
    for line in read('maps/m%d_%d.jm2' % (mx, mz)).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= ').strip(); continue
        if ':' not in line:
            continue
        head, data = line.split(':', 1)
        parts = head.split()
        if len(parts) != 3:
            continue
        lv, x, z = (int(v) for v in parts)
        d = data.split()
        if sec == 'LOC':
            v = [int(t) for t in d]
            mlocs.setdefault((lv, x, z), []).append((v[0], v[1] if len(v) > 1 else 10, v[2] if len(v) > 2 else 0))
        elif sec == 'NPC':
            mnpcs.setdefault((lv, x, z), []).append(int(d[0]))
        elif sec == 'MAP':
            land[(lv, x, z)] = d
    return land, mlocs, mnpcs

PW = int(LOCCFG['poh_house_portal'].get('width', ['1'])[0])
PL = int(LOCCFG['poh_house_portal'].get('length', ['1'])[0])
TOWNS = []          # (town, mx, mz, anchor, angle, covered, land, mlocs, mnpcs)
for town in sorted(PORTAL_AT):
    lv, mx, mz, lx, lz = PORTAL_AT[town]
    land, mlocs, mnpcs = readmap(mx, mz)
    hits = [(k, e) for k, es in mlocs.items() for e in es if e[0] == LOCS['poh_house_portal']]
    check(len(hits) == 1, 'town %d (m%d_%d) has exactly one house portal on the map, got %d'
          % (town, mx, mz, len(hits)))
    if len(hits) != 1:
        continue
    (plv, px, pz), (_, pshape, pangle) = hits[0]
    check((plv, px, pz) == (lv, lx, lz),
          'town %d: the map and poh_loc_portal name the same tile (%s vs %s)'
          % (town, (plv, px, pz), (lv, lx, lz)))
    check(pshape == 10, 'town %d: it is centrepiece_straight (shape %d)' % (town, pshape))
    w, l = (PL, PW) if pangle % 2 else (PW, PL)
    covered = {(plv, px + dx, pz + dz) for dx in range(w) for dz in range(l)}
    for t in sorted(covered):
        others = [e for e in mlocs.get(t, []) if e[0] != LOCS['poh_house_portal'] and e[1] != 22]
        check(not others, 'town %d: tile %s carries nothing else that blocks: %s' % (town, t[1:], others))
        check(t in land, 'town %d: tile %s is real ground' % (town, t[1:]))
        # Flag bit 4 is the client's remove-roofs flag - it marks every tile under a roof, and it is
        # the only thing in the map that says INDOORS. "No solid loc on the footprint" does not:
        # walls sit on tile boundaries, so the inside of a house reads as ten free tiles, and the
        # Taverley portal was placed in the middle of somebody's kitchen on exactly that reasoning.
        flags = 0
        for tok in land.get(t, []):
            if tok.startswith('f') and tok[1:].isdigit():
                flags = int(tok[1:])
        check(not flags & 4, 'town %d: tile %s is outdoors (flag %d)' % (town, t[1:], flags))
    elv, emx, emz, ex, ez = EXIT_AT[town]
    check((emx, emz) == (mx, mz), 'town %d: the landing tile is on the portal\'s own square' % town)
    check((elv, ex, ez) not in covered, 'town %d: leaving does not land you inside the portal' % town)
    check(any(abs(ex - x) + abs(ez - z) == 1 for (_, x, z) in covered),
          'town %d: leaving lands you next to the portal, at %d,%d' % (town, ex, ez))
    check((elv, ex, ez) in land, 'town %d: the landing tile is real ground' % town)
    agents = [k for k, ids in mnpcs.items() for i in ids if i == NPCS['poh_estate_agent']]
    check(len(agents) == 1, 'town %d: exactly one estate agent stands there, got %d' % (town, len(agents)))
    for t in agents:
        check(t not in covered, 'town %d: the estate agent does not stand inside the portal' % town)
    TOWNS.append((town, mx, mz, (plv, px, pz), pangle, covered, land, mlocs, agents))

check(LOCS['poh_exit_portal'] not in
      [e[0] for _, _, _, _, _, _, _, ml, _ in TOWNS for es in ml.values() for e in es],
      'the exit portal is NOT on any map - it is spawned inside the house')

print('16. inside the house: the exit portal fits in a garden')
CONST = read('scripts/skill_construction/configs/construction.constant')
def const(name):
    m = re.search(r'^\^%s\s*=\s*(-?\d+)\s*$' % name, CONST, re.M)
    return int(m.group(1)) if m else None
EX, EZ = const('poh_exit_portal_x'), const('poh_exit_portal_z')
SX, SZ = const('poh_spawn_x'), const('poh_spawn_z')
DUR = const('poh_loc_duration')
check(DUR is not None and DUR >= 1, '^poh_loc_duration=%s (the engine rejects 0)' % DUR)
ewidth = int(LOCCFG['poh_exit_portal'].get('width', ['1'])[0])
elength = int(LOCCFG['poh_exit_portal'].get('length', ['1'])[0])
ecov = {(EX + dx, EZ + dz) for dx in range(ewidth) for dz in range(elength)}
check(all(0 <= x <= 7 and 0 <= z <= 7 for x, z in ecov), 'it stays inside the room: %s' % sorted(ecov))
check((SX, SZ) not in ecov, 'it does not stand on the tile the player lands on')
check(min(abs(SX - x) + abs(SZ - z) for x, z in ecov) == 1, 'it is next to that tile')

# the garden template itself: everything in that zone must be grass decor or a hotspot, or the
# portal could land on top of something solid.
tmpl = re.search(r'^\^poh_templates_a\s*=\s*(\d+)_(\d+)_(\d+)_(\d+)_(\d+)', CONST, re.M)
gz = None
for m in re.finditer(r'^val=(\d+),(\d+)$', read('scripts/skill_construction/configs/poh_rooms.enum'), re.M):
    if int(m.group(1)) == const('poh_room_garden'):
        gz = int(m.group(2))
        break
check(gz is not None and tmpl is not None, 'the garden template zone is %s of m%s_%s' % (gz, tmpl and tmpl.group(2), tmpl and tmpl.group(3)))
if gz is not None and tmpl is not None:
    tlv, tmx, tmz = int(tmpl.group(1)), int(tmpl.group(2)), int(tmpl.group(3))
    gx0, gz0 = (gz // 8) * 8, (gz % 8) * 8
    hotspots = set()
    TL = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
    TLIDS = packmap('pack/loc.pack')
    for n, cfg in TL.items():
        if 'poh_hotspot' in cfg.get('category', []):
            hotspots.add(TLIDS.get(n))
    tsec, tlocs = None, {}
    for line in read('maps/m%d_%d.jm2' % (tmx, tmz)).split('\n'):
        if line.startswith('===='):
            tsec = line.strip('= ')
            continue
        if tsec != 'LOC' or ':' not in line:
            continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        d = [int(v) for v in data.split()]
        tlocs.setdefault((lv, x, z), []).append((d[0], d[1] if len(d) > 1 else 10))
    blockers = []
    for x, z in sorted(ecov | {(SX, SZ)}):
        for lid, shape in tlocs.get((tlv, gx0 + x, gz0 + z), []):
            if shape != 22 and lid not in hotspots:
                blockers.append((x, z, lid, shape))
    check(not blockers, 'no solid template loc under the exit portal or the landing tile: %s' % blockers)

print('17. ~poh_enter and ~poh_build are always called with the build-mode flag')
bad = []
for f, t in clean.items():
    for m in re.finditer(r'~(poh_enter|poh_build)\b(\()?', t):
        if m.group(2) is None:
            bad.append('%s: bare ~%s' % (os.path.basename(f), m.group(1)))
check(not bad, 'no bare calls: %s' % bad)
check(re.search(r'^\[proc,poh_enter\]\(boolean \$\w+\)', clean[FILES[0]], re.M) is not None,
      '[proc,poh_enter] takes a boolean')
check(re.search(r'^\[proc,poh_build\]\(boolean \$\w+\)\(coord\)', clean[FILES[0]], re.M) is not None,
      '[proc,poh_build] takes a boolean and returns a coord')

print('18. %poh_owned is a gate, not something entering grants')
enter_body = clean[FILES[0]].split('[proc,poh_enter]')[1].split('[proc,')[0]
check('%poh_owned = 0' in enter_body and 'return' in enter_body,
      'poh_enter turns away a player who owns nothing')
check('%poh_owned = 1' not in enter_body, 'poh_enter does not hand out ownership')

print('19. the imported OSRS art: every model, frame and base actually on disk')
# claude/osrs-cache.md's pre-ship sweep, narrowed to this round. A name in a .pack is not a file:
# every earlier import batch was checked this way before it shipped, and this one has three chained
# registries behind it (seq -> anim -> animset/base) where a miss shows up in game as an invisible
# loc rather than an error.
ON_DISK = set()
for root, _, fs in os.walk(os.path.join(C, 'models')):
    for fn in fs:
        if fn.endswith('.ob2'): ON_DISK.add(fn[:-4])
ANIMS = set(packmap('pack/anim.pack'))
ANIMSETS = set(packmap('pack/animset.pack'))
BASES = set(packmap('pack/base.pack'))
SUFFIX = ['_1', '_2', '_3', '_4', '_q', '_w', '_r', '_e', '_t', '_5', '_8', '_9',
          '_a', '_s', '_d', '_f', '_g', '_h', '_z', '_x', '_c', '_v', '_0']

named = []
for n, cfg in LOCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^model\d*$', k): named += [(n, k, v, True) for v in vs]
for n, cfg in NPCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^(model|head)\d+$', k): named += [(n, k, v, False) for v in vs]
for n, k, v, is_loc in named:
    hit = v in ON_DISK or (is_loc and any((v + sfx) in ON_DISK for sfx in SUFFIX))
    check(hit, '%s %s=%s has a .ob2 on disk' % (n, k, v))

SEQF = 'scripts/skill_construction/configs/poh_portal.seq'
seqs_declared = set(re.findall(r'^\[(\w+)\]', read(SEQF), re.M))
anims_used = {v for cfg in LOCCFG.values() for v in cfg.get('anim', [])}
for a in sorted(anims_used):
    check(a in seqs_declared or a in SEQS, '%s is declared (poh_portal.seq) or already in seq.pack' % a)
    check(a in SEQS, '%s is registered in seq.pack' % a)

frames = re.findall(r'^frame\d+=(\S+)$', read(SEQF), re.M)
check(len(frames) > 0, 'poh_portal.seq names %d frames' % len(frames))
delays = re.findall(r'^delay\d+=', read(SEQF), re.M)
check(len(delays) == len(frames), 'every frame has a delay (%d/%d)' % (len(delays), len(frames)))
sets_needed = set()
for f in frames:
    check(f in ANIMS, 'frame %s is in anim.pack' % f)
    sets_needed.add(f.rsplit('_', 1)[0])
for st_ in sorted(sets_needed):
    check(st_ in ANIMSETS, '%s is in animset.pack' % st_)
    check(st_.replace('anim_', 'base_', 1) in BASES, '%s base is in base.pack' % st_)
    path = os.path.join(C, 'models', st_ + '.anim')
    check(os.path.exists(path) and os.path.getsize(path) > 0, '%s.anim is on disk' % st_)

print('20. no pack gained a CR, a duplicate name or a duplicate id')
for f in ['pack/model.pack', 'pack/anim.pack', 'pack/animset.pack', 'pack/base.pack',
          'pack/seq.pack', 'pack/loc.pack', 'pack/npc.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))
    rows = [l for l in b.decode().split('\n') if '=' in l]
    ids = [l.split('=', 1)[0] for l in rows]; nms = [l.split('=', 1)[1] for l in rows]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(len(set(nms)) == len(nms), '%s has no duplicate name' % os.path.basename(f))

print('21. the ground under each of the six portals is what was signed off in game')
# THE CHECK THE FIRST PORTAL EARNED, now generalised. The OSRS house portal is five tiles wide -
# every variant in the cache is - and a 377 loc sits at ONE height with the ground running through
# it. The first Rimmington placements sat across a bank falling h35 to h12: buried at one end,
# floating at the other.
#
# A tile with no explicit h in the .jm2 is NOT unknown: the client generates it (World.method32) and
# tools/terrain377.py is that function transcribed, so every tile here has a height. Validated
# against the map itself - where an explicit tile borders a generated one the two agree closely.
#
# IT IS NO LONGER A THRESHOLD. The Rimmington round set the limit at a spread of 4 and that turned
# out to be one town's answer, not a law: Corey stood on all six of these in game and accepted
# spreads up to 32, because the portal model carries a chunky rock base that sits on a slope
# convincingly. What a number CAN do is notice a placement drifting onto ground nobody looked at, so
# each town records the spread that was actually judged and the check is that it has not moved.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain377 import height_of

# town -> the height spread under the footprint as approved in game, 2026-09-14.
APPROVED_SPREAD = {0: 4, 1: 5, 2: 4, 3: 17, 4: 3, 5: 10}

def groundfn(land, mx, mz):
    def g(lv, x, z):
        d = land.get((lv, x, z))
        if d:
            for tok in d:
                if tok.startswith('h') and tok[1:].isdigit():
                    return int(tok[1:])
        return height_of(mx * 64 + x, mz * 64 + z)
    return g

# The transcription has to be right, or every number below is decoration. Measured where an explicit
# tile borders a generated one, against the same noise sampled 37 tiles away as a control.
#
# IT IS NOT EQUALLY GOOD EVERYWHERE, and that is worth knowing rather than averaging away.
# Rimmington - the square it was validated on - comes out at a ratio near 4. Yanille and Brimhaven
# are nearer 1.2, because those squares are so heavily hand-edited that most explicit/generated
# seams fall on a wall or a cliff where the two genuinely differ. Eight of Yanille's ten portal
# tiles are generated, so its spread below is the softest number here - which is exactly why these
# placements were judged by eye in game and the spread is recorded rather than thresholded.
seams, ctrl, ratios = [], [], []
for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    exp = {}
    for (lv, x, z), d in land.items():
        if lv != 0:
            continue
        h = next((int(t[1:]) for t in d if t.startswith('h') and t[1:].isdigit()), None)
        exp[(x, z)] = h
    ss, cc = [], []
    for (x, z), h in exp.items():
        if h is None:
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in exp and exp[n] is None:
                ss.append(abs(h - height_of(mx * 64 + n[0], mz * 64 + n[1])))
                cc.append(abs(h - height_of(mx * 64 + n[0] + 37, mz * 64 + n[1] + 37)))
    if ss:
        ratios.append((town, len(ss), sum(ss) / len(ss), sum(cc) / len(cc)))
    seams += ss; ctrl += cc
for town, n, m1, m2 in ratios:
    print('       town %d: %5d seams, mean %.2f vs %.2f shifted (x%.2f)' % (town, n, m1, m2, m2 / m1))
rim = [r for r in ratios if r[0] == 0]
if rim:
    check(rim[0][2] < rim[0][3] / 2,
          'terrain377 still tracks the square it was validated on: Rimmington %.2f vs %.2f'
          % (rim[0][2], rim[0][3]))
mean = sum(seams) / len(seams) if seams else 99
cmean = sum(ctrl) / len(ctrl) if ctrl else 0
check(mean < cmean * 0.6, 'and beats shifted noise across all six: %d seams, mean %.2f vs %.2f'
      % (len(seams), mean, cmean))

for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    g = groundfn(land, mx, mz)
    hs = [g(*t) for t in sorted(covered)]
    spread = max(hs) - min(hs)
    want = APPROVED_SPREAD.get(town)
    check(spread == want, 'town %d: the footprint spread is the %s that was looked at (got %d, h%d..%d)'
          % (town, want, spread, min(hs), max(hs)))
    ah = g(*anchor)
    elv, emx, emz, ex, ez = EXIT_AT[town]
    check(abs(g(elv, ex, ez) - ah) <= 12,
          'town %d: the landing tile is within 12 of the portal\'s own tile (h%d vs h%d)'
          % (town, g(elv, ex, ez), ah))
    for t in agents:
        check(abs(g(*t) - ah) <= 12, 'town %d: the estate agent stands within 12 of it (h%d vs h%d)'
              % (town, g(*t), ah))

print('22. each portal is turned the way it was turned in game')
# Angle is FACING, and which angle faces which way was settled by looking, not by reading the model:
# rotation 0 is north, 1 east, 2 south, 3 west. (claude/poh-portal-placement.md had it 180 out - it
# reasoned from the swirl sitting south of the frame's centre in model space.) The footprint swaps
# width and length on an odd angle, which is what makes the wide face run north-south.
APPROVED_ANGLE = {0: 3, 1: 3, 2: 2, 3: 2, 4: 3, 5: 0}
FACING = {0: 'north', 1: 'east', 2: 'south', 3: 'west'}
for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    check(pangle == APPROVED_ANGLE.get(town),
          'town %d: angle %d, facing %s - the one that was approved (%s)'
          % (town, pangle, FACING[pangle], APPROVED_ANGLE.get(town)))
    xs = {x for lv, x, z in covered}; zs = {z for lv, x, z in covered}
    w, l = (PL, PW) if pangle % 2 else (PW, PL)
    check(len(xs) == w and len(zs) == l,
          'town %d: the footprint really is %d by %d on the ground' % (town, w, l))

print('23. build mode: every door hotspot has a trigger, and nothing else does')
# The click has to resolve to a grid cell and a side, and only a door hotspot carries both. A
# "Door space" or a "Centrepiece space" wired to the same proc would compute a side of 0 and dead-end.
TEMPL = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
doors = sorted(n for n, cfg in TEMPL.items() if (cfg.get('name') or [''])[0] == 'Door hotspot')
trig = sorted(re.findall(r'^\[oploc5,(\w+)\]', clean[FILES[3]], re.M))
check(trig == doors, '%d door hotspot locs, %d triggered, same set: %s'
      % (len(doors), len(trig), 'yes' if trig == doors else sorted(set(doors) ^ set(trig))))
for n in trig:
    check(n in LOCS, '%s is registered in loc.pack' % n)
    check('poh_hotspot' in (TEMPL.get(n, {}).get('category') or []), '%s carries category=poh_hotspot' % n)
    check('Build' in (TEMPL.get(n, {}).get('op5') or []), '%s has op5=Build for the trigger to fire on' % n)

print('24. build mode: the tables are complete and the idioms are ones this repo has compiled')
ENUMF = read('scripts/skill_construction/configs/poh_rooms.enum')
tables = {}
cur = None
for line in ENUMF.split('\n'):
    line = line.split('//')[0].strip()
    if line.startswith('['):
        cur = line.strip('[]'); tables[cur] = {}
    else:
        m = re.match(r'^val=(\d+),(.*)$', line)
        if m and cur: tables[cur][int(m.group(1))] = m.group(2)
COUNT = const('poh_room_count')
check(COUNT == 16, '^poh_room_count is %s' % COUNT)
for t in ('poh_room_zone', 'poh_room_doors', 'poh_room_name', 'poh_room_cost', 'poh_room_level'):
    check(t in tables, '%s exists' % t)
    have = sorted(tables.get(t, {}))
    check(have == list(range(1, COUNT + 1)), '%s covers every room type 1..%d' % (t, COUNT))
for i, v in tables.get('poh_room_cost', {}).items():
    check(int(v) > 0, 'room %d costs something (%s)' % (i, v))
for i, v in tables.get('poh_room_level', {}).items():
    check(1 <= int(v) <= 99, 'room %d has a sane level (%s)' % (i, v))

# the four idioms that have no precedent in this repo, per claude/rs2-compile-traps.md
bad = []
for f, t in clean.items():
    if 'def_string' in t: bad.append('%s: def_string' % os.path.basename(f))
    if 'while (true)' in t: bad.append('%s: while (true)' % os.path.basename(f))
    if re.search(r'\)\(string\)', t): bad.append('%s: a proc returning a string' % os.path.basename(f))
    if re.search(r'<\$\w+>', src[f]): bad.append('%s: interpolating a string variable' % os.path.basename(f))
check(not bad, 'no unproven idiom: %s' % bad)

print('25. build mode: the money and the grid are touched in the right order')
bd = clean[FILES[3]]
click = bd.split('[proc,poh_hotspot_click]')[1].split('\n[')[0]
check(before(click, 'inv_del', '~poh_room_set'), 'the coins go before the room does')
check(before(click, '~poh_room_rot_for', 'inv_del'), 'the rotation is re-checked before charging')
check(before(click, 'inv_total', 'inv_del'), 'the purse is checked before it is emptied')
check('~poh_furn_restore' in click and before(click, '~poh_place_zone', '~poh_furn_restore'),
      'the furniture - the exit portal included - is re-laid after the room changes')
rm = bd.split('[proc,poh_remove_room]')[1].split('\n[')[0]
check('~poh_room_total <= 1' in rm, 'the last room cannot be removed')
check('~poh_player_in_cell' in rm, 'you cannot remove the room you are standing in')
check('~poh_joined_count' in rm and '> 1' in rm, 'only a leaf room can be removed')
check('~poh_furn_restore' in rm, 'the furniture is re-laid after a removal too')
# and the room holding the last way out cannot be taken out at all, or the portal goes with it
check('~poh_furn_count_cell_item' in rm and '^poh_furn_exit_portal' in rm,
      'the room with the only exit portal in it is refused')
check(before(rm, '~poh_furn_count_cell_item', '~p_choice2'),
      'that refusal comes before the player is asked to confirm')

print('26. the sawmill: the items, the npc and where he stands')
OBJCFG = blocks(read('scripts/skill_construction/configs/construction.obj'))
SAWNPC = blocks(read('scripts/skill_construction/configs/sawmill.npc'))
check(sorted(OBJCFG) == ['bolt_of_cloth', 'cert_bolt_of_cloth', 'mahogany_plank', 'oak_plank',
                         'plank', 'saw', 'teak_plank'],
      'construction.obj defines %s' % sorted(OBJCFG))
# THE COUNTER IS A SHOP NOW (construction_supplies.inv), so there is no ^sawmill_cost_cloth left to
# price the cloth against: the shop works off each obj's own cost, 130% to buy and 50% to sell. What
# still has to hold is that the cost is THERE. A stocked obj with no cost is one the shop hands over
# for nothing, and that is the whole reason the hammer stayed in dialogue when the saw and the cloth
# moved onto the counter - see ^sawmill_cost_hammer in construction.constant.
SAWSHOP = blocks(read('scripts/skill_construction/configs/construction_supplies.inv'))
COUNTER = [vs[0].split(',')[0] for k, vs in SAWSHOP.get('construction_supplies', {}).items()
           if re.match(r'^stock\d+$', k)]
check(sorted(COUNTER) == ['bolt_of_cloth', 'nails', 'nails_bronze', 'nails_iron', 'saw'],
      'Construction Supplies stocks the OSRS five: %s' % sorted(COUNTER))
for n in OBJCFG:
    check(n in OBJS, '%s is in obj.pack' % n)
    for v in (OBJCFG[n].get('model') or []):
        check(v in MODELS and v in ON_DISK, '%s model=%s is packed and on disk' % (n, v))
    for k in ('manwear', 'womanwear'):
        for v in (OBJCFG[n].get(k) or []):
            mv = v.split(',')[0]
            check(mv in MODELS and mv in ON_DISK, '%s %s=%s is packed and on disk' % (n, k, mv))
check('sawmill_operator' in SAWNPC and 'sawmill_operator' in NPCS, 'sawmill_operator is in npc.pack')
for k, vs in SAWNPC.get('sawmill_operator', {}).items():
    if re.match(r'^(model|head)\d+$', k):
        for v in vs:
            check(v in MODELS and v in ON_DISK, 'sawmill_operator %s=%s is packed and on disk' % (k, v))
# the importer leaves a TODO on every block it cannot fill; none may ship
left = re.findall(r'^// TODO by hand:.*$', read('scripts/skill_construction/configs/construction.obj'), re.M)
check(not left, 'no unanswered importer TODO line left in construction.obj: %s' % left)
# no dead op: every op the sawmill npc declares has a trigger
sw = clean[FILES[4]]
ops = sorted(int(k[2:]) for k in SAWNPC.get('sawmill_operator', {}) if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),sawmill_operator\]', sw, re.M))
check(ops == trig, 'every op the sawmill operator has is wired: declares %s, triggers %s' % (ops, trig))

SAWMAP = 'maps/m51_54.jm2'
sec = None; spots = []
for line in read(SAWMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if sec != 'NPC' or ':' not in line: continue
    head, data = line.split(':', 1)
    lv, x, z = (int(v) for v in head.split())
    if int(data) == NPCS['sawmill_operator']: spots.append((lv, x, z))
check(len(spots) == 1, 'the sawmill operator is placed exactly once, got %d' % len(spots))

print('27. the sawmill: the fees are the cache\'s own, and nothing is free')
for name, c in (('plank', 'sawmill_fee_plank'), ('oak_plank', 'sawmill_fee_oak'),
                ('teak_plank', 'sawmill_fee_teak'), ('mahogany_plank', 'sawmill_fee_mahogany')):
    fee = const(c)
    cost = OBJCFG[name].get('cost')
    check(fee is not None and fee > 0, '^%s is %s' % (c, fee))
    if cost:
        check(int(cost[0]) == fee, '%s: the fee (%s) is the item\'s own cache cost (%s)' % (name, fee, cost[0]))
# THE HAMMER IS THE ONLY ONE LEFT. The saw and the bolt of cloth are shop stock and are priced off
# their own cost, so a ^sawmill_cost_* for either would be a second price that could disagree with
# the counter's. Their absence is asserted, not just un-asserted: putting one back is how the
# operator ends up selling the same saw twice at two prices.
check((const('sawmill_cost_hammer') or 0) > 0,
      '^sawmill_cost_hammer is %s' % const('sawmill_cost_hammer'))
for c in ('sawmill_cost_saw', 'sawmill_cost_cloth'):
    check(const(c) is None, '^%s is gone, because the counter prices that off the obj' % c)
# every log and plank the script names resolves, and the pairing is log -> its own plank
pairs = re.findall(r'~sawmill_cut\((\w+), (\w+), \^(\w+)\)', sw)
check(len(pairs) == 4, 'four log/plank pairs, got %d' % len(pairs))
# THE BASIC PLANK IS woodplank AND THAT IS THE POINT. 377 shipped obj 960 "Plank", the
# Construction import added obj 8187 with the same name and description, and the sawmill handed out
# 8187 - while Observatory Quest, Horror from the Deep's bridge and Dragon Slayer's hull all check
# 960. Buying three planks and being told to come back with three planks was the reported bug.
# 6e425140 moved the sawmill and all 55 poh_furn_mat rows onto woodplank; this used to assert the
# opposite, which is how a check outlives the decision it was written for.
for log, plank, fee in pairs:
    check(log in OBJS, '%s is in obj.pack' % log)
    check(plank in OBJS, '%s is in obj.pack' % plank)
    check(plank in OBJCFG or plank == 'woodplank',
          '%s is a plank this build hands out' % plank)
    check(const(fee) is not None, '^%s resolves' % fee)
    stem = plank.replace('_plank', '')
    check(log.startswith(stem) or (plank == 'woodplank' and log == 'logs'),
          '%s is cut from %s' % (plank, log))
check(('logs', 'woodplank') in [(l, p) for l, p, _ in pairs],
      'plain logs cut into woodplank - the obj the quests check, not the import\'s duplicate')
check(not any(p == 'plank' for _, p, _ in pairs),
      '...and obj 8187 is not handed out by the sawmill')

# AND THE SAME THING EVERYWHERE ELSE THAT SPENDS A PLANK. The hand-fix reached the enum and the
# sawmill but not the two files that WRITE the enum, so a regenerate put all 55 rows back - caught
# by the idempotence check below, but only after the fact. These two hold the inputs.
GENF = read('tools/genfurn.py')
check("WOOD_OBJ = {1: 'woodplank'" in GENF,
      "genfurn.py's WOOD_OBJ starts at woodplank, or a regenerate reverts every plank row")
SPEC = read('tools/furnspec.json')
check('"plank",' not in SPEC,
      'and furnspec.json names no bare plank either: %s'
      % (SPEC.count('"plank",') or 'none'))
cut = sw.split('[proc,sawmill_cut]')[1].split('\n[')[0]
check(before(cut, 'inv_del', 'inv_add'), 'the logs and the coins go before the planks arrive')
check('inv_total(inv, coins)' in cut, 'the purse is read before it is charged')
check('divide($coins, $fee)' in cut, 'a half-funded batch is cut down, not refused')

print('28. furniture: the tables, the triggers and the bit layout')
FURN = read('scripts/skill_construction/configs/poh_furniture.enum')
ftab = {}
cur = None
for line in FURN.split('\n'):
    line = line.split('//')[0].strip()
    if line.startswith('['):
        cur = line.strip('[]'); ftab[cur] = {}
    else:
        m = re.match(r'^val=(\d+),(.*)$', line)
        if m and cur: ftab[cur][int(m.group(1))] = m.group(2)
N = const('poh_furn_items')
SLOTS = const('poh_furn_slots')
check(N and N > 0, '^poh_furn_items is %s' % N)
for t in ('poh_furn_fam', 'poh_furn_name', 'poh_furn_level', 'poh_furn_wood', 'poh_furn_planks',
          'poh_furn_xp', 'poh_furn_mat1', 'poh_furn_mat1n', 'poh_furn_need'):
    check(sorted(ftab.get(t, {})) == list(range(1, N + 1)), '%s covers every item 1..%d' % (t, N))
# aggregates, not a line each: %d items would bury everything else in the run
bad = [(i, v) for i, v in ftab['poh_furn_wood'].items() if not 0 <= int(v) <= 4]
check(not bad, 'every item has a wood, or 0 for the garden: %s' % (bad[:3] or '0..4 throughout'))
# A plank family costs planks and a garden family costs something else; what every piece has is a
# first material, a count and an experience number.
planky = {i for i, v in ftab['poh_furn_wood'].items() if int(v)}
bad = [(i, v) for i, v in ftab['poh_furn_planks'].items() if i in planky and int(v) <= 0]
check(not bad, 'every plank piece costs planks: %s' % (bad[:3] or '%d of them' % len(planky)))
bad = [(i, v) for i, v in ftab['poh_furn_planks'].items() if i not in planky and int(v) != 0]
check(not bad, 'a garden piece costs no planks: %s' % (bad[:3] or '%d of them' % (N - len(planky))))
bad = [(i, v) for i, v in ftab['poh_furn_mat1n'].items() if int(v) <= 0]
check(not bad, 'no piece costs zero of its material: %s' % (bad[:3] or 'all %d' % N))
bad = [(i, v) for i, v in ftab['poh_furn_xp'].items() if int(v) <= 0]
check(not bad, 'every piece pays experience: %s' % (bad[:3] or 'all %d' % N))
bad = [(i, v) for i, v in ftab['poh_furn_mat1'].items() if v not in OBJS]
bad += [(i, v) for i, v in ftab.get('poh_furn_mat2', {}).items() if v not in OBJS]
check(not bad, 'every material is an obj that exists: %s' % (bad[:3] or 'all of them'))
check(sorted(ftab.get('poh_furn_mat2', {})) == sorted(ftab.get('poh_furn_mat2n', {})),
      'the second material and its count go together: %d pieces need two'
      % len(ftab.get('poh_furn_mat2', {})))
bad = [(i, v) for i, v in ftab['poh_furn_level'].items() if not 1 <= int(v) <= 99]
check(not bad, 'every level is reachable: %s (highest %d)'
      % (bad[:3] or 'all 1..99', max(int(v) for v in ftab['poh_furn_level'].values())))
# labels have to tell two tiers of the SAME family apart, or the menu is a coin toss
byfam = {}
for i, f in ftab['poh_furn_fam'].items():
    byfam.setdefault(int(f), []).append(ftab['poh_furn_name'][i])
bad = [(f, [n for n in names if names.count(n) > 1]) for f, names in sorted(byfam.items())
       if len(names) != len(set(names))]
check(not bad, '%d families, every one with a distinct label per tier: %s'
      % (len(byfam), bad[:2] or 'no family repeats a label'))

fu = clean[FILES[5]]
ops = clean['scripts/skill_construction/scripts/poh_furn_ops.rs2']
def procbody(src, name):
    return src.split('[proc,%s]' % name, 1)[1].split('\n[', 1)[0]
show = procbody(fu, 'poh_furn_show')
showlit = procbody(fu, 'poh_furn_show_lit')
# A case is either a loc_add literal or a hand-off to a proc. The portal frames are the only
# hand-offs so far: which loc a frame goes down as depends on where it has been directed, so the
# answer is a runtime one (see poh_portal_chamber.rs2). Both forms count as placing the item -
# what this check is for is that no item number is missing from the switch.
placed = sorted(int(m) for m in re.findall(r'^    case (\d+) : (?:loc_add|~\w+)\(', show, re.M))
check(placed == list(range(1, N + 1)), '~poh_furn_show places every item 1..%d' % N)
# the lit twins are a SUBSET, and every one of them has to be an item that really can be lit
litcase = sorted(int(m) for m in re.findall(r'^    case (\d+) : loc_add\(', showlit, re.M))
lightable = sorted(int(m) for m in re.findall(r'^    case (\d+) : return\(true\);',
                   procbody(ops, 'poh_furn_lightable'), re.M)) if '[proc,poh_furn_lightable]' in ops else litcase
check(litcase and set(litcase) <= set(placed),
      '~poh_furn_show_lit covers %d of the %d pieces, all of them real items' % (len(litcase), N))
# every loc it places is registered, and every one is a real furniture loc from poh.loc
POHLOC = blocks(read('scripts/skill_construction/configs/poh.loc'))
# The exit portal is the garden's level-1 centrepiece, and it lives in the portal round's config.
POHLOC.update(blocks(read('scripts/skill_construction/configs/poh_portal.loc')))
# ...and the costume room's five storage spaces are a rev-474 import with its own config too.
POHLOC.update(blocks(read('scripts/skill_construction/configs/poh_costume_storage.loc')))
placements = re.findall(r'loc_add\(\$spot, (\w+), \$angle, (\w+),', fu)
bad = [l for l, _ in placements if l not in LOCS]
check(not bad, 'every placed loc is in loc.pack: %s' % (bad[:3] or '%d checked' % len(placements)))
bad = [l for l, _ in placements if l not in POHLOC]
check(not bad, 'every placed loc is a real furniture loc: %s' % (bad[:3] or 'all of them'))
bad = [l for l, _ in placements if 'Remove' not in (POHLOC.get(l, {}).get('op5') or [])]
check(not bad, 'every placed loc carries op5=Remove: %s' % (bad[:3] or 'all of them'))
# a piece can only be taken out if its own op5 is wired
# the lit twins are placed by poh_furniture.rs2 and taken out by poh_furn_ops.rs2, so both files
# poh_portal_chamber.rs2 is a third source: the twenty-one directed portals are placed from
# ~poh_portal_loc rather than from a loc_add literal in the show switch, and they are taken out
# through ~poh_portal_remove, which clears the destination before handing over to ~poh_furn_remove.
# Both sides have to be counted or the check reads a house-visible loc as unremovable.
pc = clean['scripts/skill_construction/scripts/poh_portal_chamber.rs2']
rm = sorted(set(re.findall(r'^\[oploc5,(\w+)\]\s*\n?~poh_furn_remove;', fu + '\n' + ops, re.M))
            | set(re.findall(r'^\[oploc5,(\w+)\]\s*\n?~poh_portal_remove;', pc, re.M)))
placed_locs = sorted({m.group(1) for m in re.finditer(r'loc_add\(\$spot, (\w+), \$angle,', fu)}
                     | {m.group(1) for m in re.finditer(r'^    case \d+ : return\((\w+)\);', pc, re.M)})
check(rm == placed_locs, 'every placeable piece has a Remove trigger: %d placed, %d wired'
      % (len(placed_locs), len(rm)))
# and a lit twin nobody can take out is a piece of furniture welded to the floor
POHLOC2 = blocks(read('scripts/skill_construction/configs/poh.loc'))
POHLOC2.update(blocks(read('scripts/skill_construction/configs/poh_costume_storage.loc')))
bad = [l for l in {m.group(1) for m in re.finditer(r'loc_add\(\$spot, (\w+), \$angle,', showlit)}
       if 'Remove' not in (POHLOC2.get(l, {}).get('op5') or [])]
check(not bad, 'every lit twin carries op5=Remove: %s' % (bad[:3] or 'all of them'))
# hotspot triggers pass a family and nothing looks one up
hot = re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_furn_click\(\^poh_fam_(\w+)\);', fu, re.M)
check(len(hot) > 0, '%d furniture hotspot triggers' % len(hot))
bad = [l for l, _ in hot if l not in LOCS]
check(not bad, 'every hotspot trigger names a loc in loc.pack: %s' % (bad[:3] or 'all %d' % len(hot)))
bad = [f for _, f in hot if const('poh_fam_' + f) is None]
check(not bad, 'every ^poh_fam_* it passes resolves: %s' % (bad[:3] or 'all of them'))
bad = [l for l, _ in hot if 'poh_hotspot' not in (TEMPL.get(l, {}).get('category') or [])]
check(not bad, 'every one is category=poh_hotspot: %s' % (bad[:3] or 'all of them'))
check(len({l for l, _ in hot} & set(doors)) == 0, 'no door hotspot is wired to furniture')
check(len({l for l, _ in hot}) == len(hot), 'no hotspot is wired twice')

# THE ONE THIS ROUND EARNED. loc_add's shape decides which LAYER the loc lands on, and World.changeLoc
# only replaces a loc already on that layer. Place a centrepiece on a grounddecor hotspot and you get
# the furniture AND the hotspot standing in the same tile. So every family's shape has to be the shape
# its own hotspots carry in the six style squares - read from the maps, not assumed.
SHAPES = {0: 'wall_straight', 4: 'walldecor_straight_nooffset', 5: 'walldecor_straight_offset',
          10: 'centrepiece_straight', 11: 'centrepiece_diagonal', 22: 'grounddecor'}
mapshape = {}
for mp in ('maps/m29_79.jm2', 'maps/m30_79.jm2'):
    sec = None
    for l in read(mp).split('\n'):
        if l.startswith('===='):
            sec = l.strip('= '); continue
        if sec != 'LOC' or ':' not in l:
            continue
        d = (l.split(':', 1)[1].split() + ['10', '0'])[:3]
        mapshape.setdefault(int(d[0]), set()).add(SHAPES.get(int(d[1]), d[1]))
# The shape a family is placed with, per item. Most cases carry it as a literal in the show
# switch; a case that hands off to a proc carries it in that proc instead, so the proc is read
# rather than the item being skipped - skipping it would let a hand-off family be placed with the
# wrong shape and the check would still say every hotspot was verified.
itemshape = dict((int(a), b) for a, b in
    re.findall(r'^    case (\d+) : loc_add\(\$spot, \w+, \$angle, (\w+),', fu, re.M))
def _proc_body(name):
    for f in FILES:
        if '[proc,%s]' % name in clean[f]:
            return clean[f].split('[proc,%s]' % name, 1)[1].split('\n[', 1)[0]
    return ''
def _shapes_reachable(name, seen=None):
    """Every locshape a proc can place with, following the helpers it calls.

    A hand-off proc does not have to carry a loc_add of its own: the combat ring lays 36 tiles of
    three different shapes through ~poh_ring_wall / _corner / _mat, so the shapes are one level
    down. Following the calls is what keeps this a real check rather than a skipped one."""
    seen = seen if seen is not None else set()
    if name in seen:
        return set()
    seen.add(name)
    body = _proc_body(name)
    out = set()
    for m in re.finditer(r'loc_add\(', body):
        args, depth, cur, i = [], 0, '', m.end()
        while i < len(body):
            ch = body[i]
            if ch == '(':
                depth += 1; cur += ch
            elif ch == ')' and depth == 0:
                args.append(cur); break
            elif ch == ')':
                depth -= 1; cur += ch
            elif ch == ',' and depth == 0:
                args.append(cur); cur = ''
            else:
                cur += ch
            i += 1
        if len(args) > 3:
            out.add(args[3].strip())
    for callee in set(re.findall(r'~(\w+)\(', body)):
        out |= _shapes_reachable(callee, seen)
    return out
handoff = {}
for a, proc in re.findall(r'^    case (\d+) : ~(\w+)\(\$spot, \$angle,', fu, re.M):
    sh = _shapes_reachable(proc)
    check(bool(sh), '~%s places its pieces with a shape this can read' % proc)
    handoff.setdefault(proc, sh)
    itemshape[int(a)] = sorted(sh)[0] if len(sh) == 1 else None
famshape = {}
for i, f in ftab['poh_furn_fam'].items():
    famshape.setdefault(int(f), set()).add(itemshape[i])
# A family whose hand-off places more than one shape cannot be held to "one shape per family" -
# it is held to group 59 instead, which reads every tile it lays back against the template.
_spec = _json.load(open(os.path.join(C, 'tools/furnspec.json')))
MULTISHAPE = {const('poh_fam_' + k['key']) for k in _spec['families']
              if k.get('show') and len(_shapes_reachable(k['show'])) > 1}
for f in MULTISHAPE:
    famshape.pop(f, None)
ALLOWED = {('chair', 15214), ('chair', 15215)}   # see shape_allowances in tools/furnspec.json
bad = []
for loc, fam in hot:
    want = famshape.get(const('poh_fam_' + fam), set())
    have = mapshape.get(LOCS[loc], set())
    if len(want) != 1:
        bad.append((fam, 'places %s - a family must have ONE shape' % sorted(want)))
    elif not (want & have) and (fam, LOCS[loc]) not in ALLOWED:
        bad.append((fam, '%d: places %s, template has %s' % (LOCS[loc], sorted(want), sorted(have))))
check(not bad, 'every family is placed with its hotspots\' own shape: %s'
      % (bad[:3] or '%d hotspots checked' % len(hot)))

# the bit layout has to be gapless and fit an int. The item number is in TWO ranges: the low byte at
# ^poh_furn_bit_item and the high seven above the lit bit, so that widening it from 8 bits could not
# move a field any existing save had already written.
bits = [(const('poh_furn_bit_rx'), 3), (const('poh_furn_bit_rz'), 3), (const('poh_furn_bit_lx'), 3),
        (const('poh_furn_bit_lz'), 3), (const('poh_furn_bit_angle'), 2), (const('poh_furn_bit_item'), 8),
        (const('poh_furn_bit_lit'), 1)]
hi_w = int(re.search(r'\^poh_furn_bit_item_hi \+ (\d+)\)', src['scripts/skill_construction/scripts/poh_furniture.rs2']).group(1)) + 1
bits.append((const('poh_furn_bit_item_hi'), hi_w))
at = 0; ok = True
for off, w in bits:
    if off != at: ok = False
    at = off + w
check(ok, 'the packed fields are contiguous from bit 0: %s' % bits)
check(at <= 31, 'a piece fits an int (%d bits)' % at)
check(N < (1 << (8 + hi_w)), '%d items fit the %d-bit item number (low byte plus %d above the lit bit)'
      % (N, 8 + hi_w, hi_w))
check(const('poh_furn_bit_item_hi') > const('poh_furn_bit_lit'),
      'the item high byte is above the lit bit, so an old record reads 0 there')
check(SLOTS and SLOTS <= 256, '^poh_furn_slots is %s' % SLOTS)
varps = {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l}
missing = [i for i in range(SLOTS) if ('poh_furn_%d' % i) not in varps]
check(not missing, 'every furniture slot has a varp: missing %s' % missing[:5])
gs = sorted(int(m) for m in re.findall(r'^    case (\d+) : return\(%poh_furn_\d+\);', fu, re.M))
ss = sorted(int(m) for m in re.findall(r'^    case (\d+) : %poh_furn_\d+ = \$value;', fu, re.M))
check(gs == list(range(SLOTS)) and ss == list(range(SLOTS)), 'get and set cover all %d slots' % SLOTS)
for m in re.finditer(r'case (\d+) : return\(%poh_furn_(\d+)\);', fu):
    if m.group(1) != m.group(2): check(False, 'get case %s reads varp %s' % (m.group(1), m.group(2)))
for m in re.finditer(r'case (\d+) : %poh_furn_(\d+) = \$value;', fu):
    if m.group(1) != m.group(2): check(False, 'set case %s writes varp %s' % (m.group(1), m.group(2)))

# A trigger declared twice will not compile, and 238 generated [oploc5] on names as ordinary as
# loc_13581 is exactly how you collide with something in another skill. Checked repo-wide, not just
# in these files, because the collision would be with a file nobody was looking at.
seen_trig = {}
dup_trig = []
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if not fn.endswith('.rs2'):
            continue
        fp = os.path.join(root, fn)
        with open(fp, encoding='utf-8', errors='replace') as fh:
            for m in re.finditer(r'^\[(\w+),([\w+.]+)\]', fh.read().replace('\r\n', '\n'), re.M):
                if m.group(1) in ('proc', 'label', 'debugproc', 'command', 'queue', 'timer'):
                    continue
                k = m.groups()
                if k in seen_trig:
                    dup_trig.append((k, seen_trig[k], fp))
                seen_trig[k] = fp
check(not dup_trig, 'no trigger is declared twice anywhere in the repo: %s'
      % (dup_trig[:2] or '%d checked' % len(seen_trig)))

print('29. furniture: materials leave before the thing arrives, and a room takes its own with it')
# The body lives in ~poh_furn_click_at now: ~poh_furn_click is the unanchored door into it, and
# an anchored family (the combat ring) passes the tile its piece is stored at instead.
clickb = fu.split('[proc,poh_furn_click_at]')[1].split('\n[')[0]
check('~poh_furn_click_at($fam, -1, -1);' in fu.split('[proc,poh_furn_click]')[1].split('\n[')[0],
      '~poh_furn_click still exists and is the unanchored door')
check('if ($ax >= 0) {' in clickb, 'and an anchor overrides the clicked tile rather than adding a path')
check(before(clickb, '~poh_furn_have', '~poh_furn_take'), 'the materials are counted before they are taken')
check(before(clickb, '~poh_furn_take', '~poh_furn_show'), 'the materials go before the furniture appears')
check(clickb.count('~poh_furn_have') >= 2, 'the materials are re-checked after the menu suspends')
# The xp used to be a bare stat_advance; it goes through ~construction_xp now so the carpenter's
# outfit gets its bonus and can turn up. What matters here is unchanged: the piece is saved first.
check(before(clickb, '~poh_furn_set', '~construction_xp'),
      'it is saved before the xp is paid')
check('inv_total(inv, hammer)' in clickb and 'inv_total(inv, saw)' in clickb, 'a hammer and a saw are required')
check('~poh_furn_free' in clickb and clickb.count('~poh_furn_free') >= 2, 'a free slot is re-checked after the menu suspends')
rmb = fu.split('[proc,poh_furn_remove]')[1].split('\n[')[0]
check('~poh_furn_set($slot, 0)' in rmb and '~poh_furn_relay' in rmb, 'removing clears the slot and re-lays the room')
bd = clean[FILES[3]]
check('~poh_furn_clear_cell' in bd, 'removing a ROOM clears its furniture too')
pb = clean[FILES[0]]
check('~poh_furn_restore' in pb, '~poh_build puts the furniture back')
build_body = pb.split('[proc,poh_build]')[1].split('\n[')[0]
check(before(build_body, '~poh_furn_restore', 'instance_loccategory'),
      'furniture is placed BEFORE the hotspots are hidden, so it changes them in place')

print('39. what the furniture does: every trigger is on an op the loc really has')
# A trigger on an op the loc does not carry is not an error - it simply never fires, which is the
# quietest kind of broken. The op TEXT has to match the kind too: [oploc1] on a "light" family must
# be a loc whose op1 really says Light.
FSPEC = _json.load(open(os.path.join(C, 'tools/furnspec.json')))
KINDOP = {'sit': 'Sit-on', 'light': 'Light', 'altar': 'Pray', 'jingle': 'Play',
          'observe': 'Observe', 'talk': 'Talk-to', 'preen': 'Preen',
          'wardrobe': 'Change-clothes', 'costume': 'Open'}


OPSRC = src['scripts/skill_construction/scripts/poh_furn_ops.rs2']
fired = sorted(set(re.findall(r'^\[oploc1,(\w+)\]', OPSRC, re.M)))
bad = [l for l in fired if not (POHLOC.get(l, {}).get('op1') or [])]
check(not bad, 'every [oploc1] is on a loc that carries an op1: %s' % (bad[:3] or '%d checked' % len(fired)))
want = {}
for f in FSPEC['families']:
    if 'op1' in f:
        for l in f.get('locs') or [pc['loc'] for pc in f.get('pieces', [])]:
            want[l] = (f['key'], f['op1']['kind'])
bad = [(l, want[l][1], (POHLOC[l].get('op1') or ['?'])[0]) for l in fired
       if want[l][1] in KINDOP and (POHLOC[l].get('op1') or ['?'])[0] != KINDOP[want[l][1]]]
check(not bad, 'the kind matches the op the loc advertises: %s' % (bad[:3] or 'all of them'))
check(sorted(want) == fired, 'every family with an op1 in the spec has a trigger for every tier: %d'
      % len(fired))
# the altar's use-item trigger is on the altars and nothing else
users = sorted(set(re.findall(r'^\[oplocu,(\w+)\]', OPSRC, re.M)))
altars = sorted(l for l in want if want[l][1] == 'altar')
check(users == altars, 'the offer-bones trigger is on the %d altars and nothing else: %s'
      % (len(altars), users[:3] if users != altars else 'yes'))
check('oc_param($bone, bone_exp)' in OPSRC,
      'it tests bone_exp, the same param burying uses, rather than a list of bones')

print('30. the build windows: registered, in file order, and the old chat panel gone')
IFACE = {}
for l in read('pack/interface.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); IFACE[n] = int(i)
order = [int(l) for l in read('pack/interface.order').split('\n') if l.strip()]
check(len(order) == len(set(order)), 'interface.order has no duplicate id')
check(set(IFACE.values()) == set(order), 'interface.pack and interface.order hold the same id set')
check(not [n for n in IFACE if n.startswith('poh_buildmenu')], 'poh_buildmenu is out of interface.pack')
check(not os.path.exists(os.path.join(C, 'scripts/skill_construction/interfaces/poh_buildmenu.if')),
      'poh_buildmenu.if is deleted')
check('poh_buildmenu' not in alltext, 'no script still names poh_buildmenu')

def parse_if(path):
    """-> file order, and each component's key/values. Same grammar as PackShared.ts."""
    o, coms, cur = [], {}, None
    for line in read(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('['):
            cur = line[1:line.index(']')]; coms[cur] = {}; o.append(cur)
        elif '=' in line and cur:
            k, v = line.split('=', 1); coms[cur][k] = v
    return o, coms

MENUS = 'scripts/skill_construction/scripts/poh_menus.rs2'
menu = clean[MENUS]
IFF = {}
for w in ('poh_roommenu', 'poh_furnmenu', 'poh_tabletmenu'):
    o, coms = parse_if('scripts/skill_construction/interfaces/%s.if' % w)
    IFF[w] = (o, coms)
    check(len(o) == len(set(o)), '%s.if has %d distinct components' % (w, len(set(o))))
    check(w in IFACE, '%s is in interface.pack' % w)
    want = [IFACE[w] + 1 + i for i in range(len(o))]
    got = [IFACE.get('%s:%s' % (w, c)) for c in o]
    check(got == want, '%s: its components are numbered in file order from %d' % (w, IFACE[w] + 1))
    used = sorted(set(re.findall(r'%s:(\w+)' % w, menu)))
    for c in used:
        check(c in coms, '%s: the script drives :%s, which the .if defines' % (w, c))

print('31. the build windows: the client only obeys these on the right kind of component')
# THE CHECK THIS ROUND EARNED. Client.drawInterface tests hide on the LAYER it is drawing and
# never on a child, so if_sethide on a text or a model does nothing at all - which is what the
# chat panel did, and why its empty slots stayed on screen. The other three are the same class
# of mistake: a call whose component is the wrong type fails silently rather than loudly.
for w, (o, coms) in IFF.items():
    for c in sorted(set(re.findall(r'if_sethide\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'layer',
              '%s:%s is a LAYER, so if_sethide can hide it' % (w, c))
    for c in sorted(set(re.findall(r'if_setmodel\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'model', '%s:%s is a model component' % (w, c))
    for c in sorted(set(re.findall(r'if_setangle\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'model', '%s:%s is a model component' % (w, c))
    for c in sorted(set(re.findall(r'if_settext\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'text', '%s:%s is a text component' % (w, c))
    for c in sorted(set(re.findall(r'if_addresumebutton\(%s:(\w+)\)' % w, menu))):
        bt = coms.get(c, {}).get('buttontype')
        check(bt == 'normal', '%s:%s is buttontype=normal, so a click can resume the script' % (w, c))
    for c in sorted(set(re.findall(r'case %s:(\w+) :' % w, menu))):
        check(c in coms, '%s: switch_component names :%s, which exists' % (w, c))

print('32. the build windows: nothing is drawn outside the window')
# The window is the smithing frame's box. Text or a border past it hangs over bare viewport,
# which is exactly what put More and Cancel off the bottom of the chat panel last round.
WIN = (12, 20, 500, 320)
for w, (o, coms) in IFF.items():
    out = []
    for c in o:
        d = coms[c]
        if d.get('type') == 'graphic':
            continue        # the frame's studs deliberately straddle the edge
        x, y = int(d.get('x', 0)), int(d.get('y', 0))
        cw, ch = int(d.get('width', 0)), int(d.get('height', 0))
        if 'layer' in d:
            p = coms[d['layer']]
            x += int(p['x']); y += int(p['y'])
            if d.get('type') == 'model':
                # a model component is deliberately twice its icon's height (see genmenus.py);
                # what must fit is the icon, which is its top half
                ch = ch // 2
        if x < WIN[0] or y < WIN[1] or x + cw > WIN[2] or y + ch > WIN[3]:
            out.append((c, x, y, cw, ch))
    check(not out, '%s: every component is inside %s: %s' % (w, WIN, out[:3] or 'all inside'))

print('33. the model icons are framed by their own geometry, and land inside their row')
sys.path.insert(0, os.path.join(C, 'tools'))
import ifmodels
MODELS_BY_ID = {}
for l in read('pack/model.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); MODELS_BY_ID[int(i)] = n

def table(proc, pat=r'case (\d+) : return\((\d+)\);'):
    body = menu.split('[proc,%s]' % proc)[1].split('\n[')[0]
    return {int(a): int(b) for a, b in re.findall(pat, body)}

room_model, room_zoom = table('poh_room_model'), table('poh_room_zoom')
furn_model = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);',
              clean[FILES[5]].split('[proc,poh_furn_model]')[1].split('\n[')[0])}
furn_zoom = table('poh_furn_zoom')
check(sorted(room_model) == list(range(1, COUNT + 1)),
      '~poh_room_model answers for every room 1..%d' % COUNT)
check(sorted(room_zoom) == sorted(room_model), '~poh_room_zoom covers the same rooms')
check(sorted(furn_zoom) == sorted(furn_model), '~poh_furn_zoom covers every item ~poh_furn_model does')

XAN, YAN = const('poh_menu_xan'), const('poh_menu_yan')
# the pictures are turned face-on, so the zoom that frames them was solved with THEIR camera and
# has to be measured with it too
def cam_table(proc, dflt):
    body = menu.split('[proc,%s]' % proc)[1].split('\n[')[0]
    return {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', body)}, dflt
fam_xan, _ = cam_table('poh_furn_xan', XAN)
fam_yan, _ = cam_table('poh_furn_yan', YAN)
FAMOF = {int(k): int(v) for k, v in ftab['poh_furn_fam'].items()}
def camera(label, k):
    if label != 'furniture':
        return XAN, YAN
    f = FAMOF[k]
    return fam_xan.get(f, XAN), fam_yan.get(f, YAN)
for label, models, zooms, comp, win in [
        ('room', room_model, room_zoom, 'r0model', 'poh_roommenu'),
        ('furniture', furn_model, furn_zoom, 's0model', 'poh_furnmenu')]:
    d = IFF[win][1][comp]
    row = IFF[win][1][d['layer']]
    rw, rh = int(row['width']), int(row['height'])
    cw, ch = int(d['width']), int(d['height'])
    # the client centres the model on the component and clips it to the LAYER: at the bottom
    # only (Pix3D's rasterisers clamp to Pix2D.bottom and to nothing else), so anything that
    # overruns the top or the sides is drawn over whatever is next to it
    cx, cy = int(d['x']) + cw // 2, int(d['y']) + ch // 2
    bad = []
    for k in sorted(models):
        name = MODELS_BY_ID.get(models[k])
        path = ifmodels.ob2path(name) if name else None
        if path is None:
            bad.append((k, models[k], name, 'no .ob2'))
            continue
        m = ifmodels.R.Model(path)
        hw, rise, drop = ifmodels.extent(m, cw, ch, *camera(label, k), zooms[k])
        if cx - hw < 0 or cx + hw > rw or cy - rise < 0 or cy + drop > rh:
            bad.append((k, name, 'x %.0f..%.0f of %d, y %.0f..%.0f of %d'
                        % (cx - hw, cx + hw, rw, cy - rise, cy + drop, rh)))
    check(not bad, '%s: all %d icons are drawn inside their %dx%d row: %s'
          % (label, len(models), rw, rh, bad[:3] or 'all inside'))

# AND THE ANGLE, which nothing here looked at. The checks above are about ZOOM - whether the icon
# fits its row - and a mutation that changed a family's camera ANGLE in furnspec.json survived all
# of them. It had never been caught: the mutation edited the generated poh_menus.rs2, so the
# battery's own regenerate overwrote it before anything could look, and group 38 fired instead.
#
# The invariant is real. Every family in furnspec.json's camera list is on it for ONE reason - a
# framed picture has no depth, so it is turned face-on - which means they share one camera. A
# family with its own angle is either a mistake or a reason that is no longer written down.
_CAMS = {k: v for k, v in _json.loads(read('tools/furnspec.json'))['cameras'].items() if k != '_'}
_distinct = sorted({tuple(v) for v in _CAMS.values()})
check(len(_distinct) == 1,
      'the families turned face-on all use the same camera, because they are all on that list '
      'for the same reason: %s' % (_distinct if len(_distinct) != 1 else '%d families at %s'
                                   % (len(_CAMS), _distinct[0])))
# And the generated switch really says what the spec says, per family rather than in aggregate.
_XAN = procbody(read('scripts/skill_construction/scripts/poh_menus.rs2'), 'poh_furn_xan')
_FAMKEYS = [f['key'] for f in _json.loads(read('tools/furnspec.json'))['families']]
_wrong = []
for _k, _v in sorted(_CAMS.items()):
    _n = _FAMKEYS.index(_k) + 1
    if 'case %d : return(%d);' % (_n, _v[0]) not in _XAN:
        _wrong.append('%s wants %d at case %d' % (_k, _v[0], _n))
check(not _wrong,
      'and the generated angle switch carries each one at its own family number: %s'
      % (_wrong[:3] or 'all %d' % len(_CAMS)))

print('34. the room prices are written twice and say the same thing')
ROOMS = read('scripts/skill_construction/configs/poh_rooms.enum')
def enumtable(txt, name):
    b = txt.split('[%s]' % name)[1]
    b = b.split('\n[')[0]
    return {int(m.group(1)): m.group(2) for m in re.finditer(r'^val=(\d+),(.*)$', b, re.M)}
cost = enumtable(ROOMS, 'poh_room_cost')
costtext = enumtable(ROOMS, 'poh_room_cost_text')
check(sorted(cost) == sorted(costtext), 'poh_room_cost_text covers every room poh_room_cost does')
wrong = [(k, cost[k], costtext.get(k)) for k in cost
         if (costtext.get(k) or '').replace(',', '') != cost[k]]
check(not wrong, 'every grouped price is its own number: %s' % (wrong[:3] or 'all agree'))
FAMS = enumtable(read('scripts/skill_construction/configs/poh_furniture.enum'), 'poh_fam_name')
NFAM = len(re.findall(r'^\^poh_fam_\w+\s*=', read('scripts/skill_construction/configs/construction.constant'), re.M))
check(sorted(FAMS) == list(range(1, NFAM + 1)), 'poh_fam_name names all %d hotspot families' % NFAM)

print('38. the furniture generator still produces exactly what is checked in')
kept2 = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/configs/poh_furniture.enum',
    'scripts/skill_construction/configs/construction.varp',
    'scripts/skill_construction/configs/construction.constant',
    'scripts/skill_construction/scripts/poh_furniture.rs2',
    'scripts/skill_construction/scripts/poh_furn_ops.rs2',
    'scripts/skill_construction/configs/poh_flatpacks.obj',
    'pack/obj.pack',
    'pack/varp.pack']}
# poh_flatpacks.obj and obj.pack belong in that list for a reason that cost an afternoon: this
# group runs genfurn.py IN PLACE, so any generated file missing from kept2 is quietly rewritten
# here and every later group reads the regenerated copy. Group 52's obj.pack check could not go
# red because group 38 had already undone the break. A generated file that is not listed above
# is not checked by anything - it is un-checkable.
#
# poh_furn_ops.rs2 joined them the same way, and it had been missing since the day it was split
# out: a mutation that rewired a cape rack to open the magic wardrobe's storage was regenerated
# away here and the battery came out green. Every trigger in the build lives in that file.
import subprocess as _sp
r = _sp.run([sys.executable, os.path.join(C, 'tools/genfurn.py'), str(SLOTS)],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/genfurn.py runs clean' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
moved = [f for f in kept2 if open(os.path.join(C, f), 'rb').read() != kept2[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept2[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
# and the varps a save already holds must never be renumbered under it
vp = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in read('pack/varp.pack').split('\n') if '=' in l}
check(all(vp.get('poh_furn_%d' % i) == 894 + i for i in range(64)),
      'poh_furn_0..63 still have the ids the first 64-slot houses were saved with')

print('36. every string these windows can show fits the box it is shown in')
# Not hypothetical: the chat panel's names ran into each other at 90px, and its More and
# Cancel fell off the bottom. The fonts here are the client's own sheets and the advance rule
# is PixFont's, so these widths are the widths the client will draw.
import ifrender
FURNE = read('scripts/skill_construction/configs/poh_furniture.enum')
TABLE_ = read('scripts/skill_construction/configs/poh_tablets.enum')
TABE = {t: enumtable(TABLE_, t) for t in
        ('poh_tab_obj', 'poh_tab_name', 'poh_tab_spell', 'poh_tab_level', 'poh_tab_need',
         'poh_lectern_name')}
rname, rlvl, rcost = (enumtable(ROOMS, t) for t in ('poh_room_name', 'poh_room_level', 'poh_room_cost_text'))
fneed = enumtable(FURNE, 'poh_furn_need')
fname, flvl, fplank, fwood = (enumtable(FURNE, t) for t in
                              ('poh_furn_name', 'poh_furn_level', 'poh_furn_planks', 'poh_wood_name'))
SHOWN = [
    ('poh_roommenu', 'r0name', ['%s: Lvl %s' % (rname[k], rlvl[k]) for k in rname]),
    ('poh_roommenu', 'r0cost', ['%s coins' % rcost[k] for k in rcost]),
    ('poh_furnmenu', 's0lvl',  ['Level %s' % flvl[k] for k in flvl]),
    ('poh_furnmenu', 's0name', [fname[k] for k in fname]),
    ('poh_furnmenu', 's0need', list(fneed.values())),
    ('poh_furnmenu', 'title',  list(FAMS.values())),
    ('poh_tabletmenu', 't0name', list(TABE['poh_tab_name'].values())),
    ('poh_tabletmenu', 't0need', list(TABE['poh_tab_need'].values())),
    ('poh_tabletmenu', 't0lvl',  ['Level %s' % v for v in TABE['poh_tab_level'].values()]),
    ('poh_tabletmenu', 'title',  list(TABE['poh_lectern_name'].values())),
]
for win, comp, strings in SHOWN:
    d = IFF[win][1][comp]
    f = ifrender.font(d.get('font', 'p12_full'))
    w = int(d['width'])
    over = sorted(((f.width(t) - w, t) for t in strings if f.width(t) > w), reverse=True)
    check(not over, '%s:%s fits %dpx: widest is %dpx (%s)%s'
          % (win, comp, w, max(f.width(t) for t in strings),
             max(strings, key=f.width), '' if not over else ' OVER by %d: %s' % over[0]))
# and the fixed text the .if itself carries
for win, (o, coms) in IFF.items():
    over = []
    for c in o:
        t = coms[c].get('text')
        if not t or coms[c].get('type') != 'text':
            continue
        f = ifrender.font(coms[c].get('font', 'p12_full'))
        if f.width(t) > int(coms[c]['width']):
            over.append((c, t, f.width(t), int(coms[c]['width'])))
    check(not over, '%s: its own labels fit: %s' % (win, over or 'all fit'))

print('37. the dim/highlight tags are ones the client actually knows')
# PixFont.evaluateTag returns -1 for anything it does not recognise and drawStringTag then just
# swallows the five characters: an unknown tag is INVISIBLE, not an error, and the run silently
# keeps the previous colour. A typo would show as "the greying stopped working" and nothing else.
KNOWN = {'red', 'gre', 'blu', 'yel', 'cya', 'mag', 'whi', 'bla', 'lre', 'dre', 'dbl',
         'or1', 'or2', 'or3', 'gr1', 'gr2', 'gr3', 'str', 'end'}
TINTS = read('scripts/skill_construction/configs/poh_menus.enum')
STATES = {n: v for n, v in re.findall(r'^\^(poh_state_\w+)\s*=\s*(\d+)$',
                                     read('scripts/skill_construction/configs/construction.constant'), re.M)}
check(len(STATES) == 3, 'there are %d ^poh_state_* constants: %s' % (len(STATES), sorted(STATES)))
for t in ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'):
    rows = enumtable(TINTS, t)
    check(sorted(rows) == sorted(int(v) for v in STATES.values()),
          '%s answers for every ^poh_state_* and nothing else' % t)
    bad = [(k, v) for k, v in rows.items()
           if not re.fullmatch(r'@(\w{3})@', v) or re.fullmatch(r'@(\w{3})@', v).group(1) not in KNOWN]
    check(not bad, '%s: every value is a tag PixFont.evaluateTag knows: %s' % (t, bad or 'all known'))
# and the rows really use them - a table nothing reads is not a feature
for win, comp, tables in [('poh_roommenu', 'r0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need')),
                          ('poh_furnmenu', 's0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need')),
                          ('poh_tabletmenu', 't0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'))]:
    proc = {'poh_roommenu': 'poh_room_row0', 'poh_furnmenu': 'poh_furn_slot0',
            'poh_tabletmenu': 'poh_tab_row0'}[win]
    # src, not clean: `clean` blanks string literals and the enum lookups live inside if_settext's
    body = src[MENUS].split('[proc,%s]' % proc)[1].split('\n[')[0]
    for t in tables:
        check(t in body, '%s: %s reads %s' % (win, proc, t))
    check('^poh_state_locked' in body and '^poh_state_poor' in body,
          '%s: %s sets both the poor and the locked state' % (win, proc))

print('35. the generator still produces exactly what is checked in')
import subprocess, filecmp, tempfile, shutil
kept = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/interfaces/poh_roommenu.if',
    'scripts/skill_construction/interfaces/poh_tabletmenu.if',
    'scripts/skill_construction/interfaces/poh_furnmenu.if',
    'scripts/skill_construction/scripts/poh_menus.rs2',
    'pack/interface.pack', 'pack/interface.order',
    'scripts/skill_construction/configs/poh_rooms.enum',
    'scripts/skill_construction/configs/poh_furniture.enum']}
spec = os.path.join(C, 'tools/menuspec.json')
if os.path.exists(spec):
    r = subprocess.run([sys.executable, os.path.join(C, 'tools/genmenus.py'), spec],
                       capture_output=True, text=True, cwd=C)
    check(r.returncode == 0, 'tools/genmenus.py runs clean' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
    fresh = {f: open(os.path.join(C, f), 'rb').read() for f in kept}
    same = [f for f in kept if fresh[f] != kept[f]]
    for f in same:
        open(os.path.join(C, f), 'wb').write(kept[f])
    check(not same, 're-running it changes nothing: %s' % (same or 'byte-identical'))
    # ONE KIND OF LINE ENDING PER FILE, and the writer has to be what guarantees it.
    #
    # HEAD is a single entry of the rs2 line list holding forty lines of its own, so a writer that
    # joins straight onto nl leaves those forty as LF while every other line becomes CRLF. Mixed
    # output is invisible here on Linux (nl is \n either way) and invisible to git anywhere, because
    # git stores the blob normalised - so the check above went red on Windows only, with an EMPTY
    # git diff, on 2026-09-15, the first day the laptop had a Python to run this with. Two checks
    # because one of them cannot fire on Linux: the bytes, and the writer that produces them.
    mixed = [os.path.basename(f) for f, b in fresh.items()
             if b.count(b'\r\n') and b.count(b'\n') - b.count(b'\r\n')]
    check(not mixed, 'and every file it writes has one kind of line ending: %s'
          % (mixed or 'all %d uniform' % len(fresh)))
    writer = read('tools/genmenus.py').split("rs2 = rs2_room(", 1)[1]
    check("text = nl.join(rs2).replace('\\r\\n', '\\n')" in writer,
          'the rs2 writer normalises before it converts, which is what keeps that true')
else:
    check(False, 'tools/menuspec.json is missing, so the generator cannot be re-run')

# THE ONE THAT MATTERS: if_setmodel takes a raw id, so every literal in ~poh_furn_model has to still
# be the model.pack id of the model its own loc names. model.pack is append-only in practice, but
# "in practice" is not a check.
MODELS_BY_ID = {}
for l in read('pack/model.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); MODELS_BY_ID[int(i)] = n
SUF = ['', '_8', '_1', '_2', '_3', '_4', '_q', '_w', '_r', '_e', '_t', '_5', '_9',
       '_a', '_s', '_d', '_f', '_g', '_h', '_z', '_x', '_c', '_v', '_0']
mbody = clean[FILES[5]].split('[proc,poh_furn_model]')[1].split('\n[')[0]
cases = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', mbody)}
check(sorted(cases) == list(range(1, N + 1)), '~poh_furn_model answers for every item 1..%d' % N)
placer = clean[FILES[5]].split('[proc,poh_furn_show]')[1].split('\n[')[0]
loc_of = {int(a): b for a, b in re.findall(r'case (\d+) : loc_add\(\$spot, (\w+),', placer)}
# A hand-off case names a proc instead of a loc; the item's own loc is then the one the spec gave
# it, which is what the menu icon has to be whoever ends up placing it.
_spec_loc = {}
for _f in _json.load(open(os.path.join(C, 'tools/furnspec.json')))['families']:
    for _i, _l in enumerate(_f.get('locs') or [_p['loc'] for _p in _f.get('pieces', [])]):
        _spec_loc.setdefault(_f['key'], []).append(_l)
_byitem = {}
for _i, _fam in ftab['poh_furn_fam'].items():
    _byitem.setdefault(int(_fam), []).append(_i)
for _famnum, _items in _byitem.items():
    _key = next((k for k in _spec_loc if const('poh_fam_' + k) == _famnum), None)
    if _key is None:
        continue
    for _n, _item in enumerate(sorted(_items)):
        if _item not in loc_of and _n < len(_spec_loc[_key]):
            loc_of[_item] = _spec_loc[_key][_n]
wrong = []
for item, mid in sorted(cases.items()):
    loc = loc_of.get(item)
    want_model = (POHLOC.get(loc, {}).get('model') or [None])[0]
    have = MODELS_BY_ID.get(mid)
    if want_model is None or have is None or have not in [want_model + s for s in SUF]:
        wrong.append((item, loc, want_model, mid, have))
check(not wrong, 'every raw model id is still its own loc\'s model: %d checked, %s'
      % (len(cases), wrong[:3] or 'all correct'))

print('40. the tablets say exactly what the spell rows say')
# A tablet IS a spell, stored. Its level, its runes and the experience making it pays are copied
# into the enum tables because the window cannot run a db_find per row - so this reads them back
# out of magic_spell_table and fails if the two have drifted. The copy is the risk this check
# exists for; nothing else about a tablet is duplicated anywhere.
import json as _json
TSPEC = _json.load(open(os.path.join(C, 'tools/tabletspec.json')))
TABS = TSPEC['tablets']
SPELLROW = {}
for _b in read('scripts/skill_magic/configs/magic_spells.dbrow').split('\n['):
    _m = re.search(r'data=spell,\^(\w+)', _b)
    if not _m:
        continue
    _d = {}
    for _l in _b.split('\n'):
        if _l.startswith('data='):
            _k, _v = _l[5:].split(',', 1)
            _d.setdefault(_k, []).append(_v)
    SPELLROW[_m.group(1)] = _d
RUNEWORD = TSPEC['rune_words']
def _runes(name):
    p = SPELLROW[name]['runesrequired'][0].split(',')
    return [(p[i], int(p[i + 1])) for i in range(0, len(p) - 1, 2) if p[i] != 'null']
check(len(TABS) == const('poh_tab_items'),
      '^poh_tab_items is %d, the number of tablets in the spec' % const('poh_tab_items'))
check(sorted(TABE['poh_tab_name']) == list(range(1, len(TABS) + 1)),
      'the tablet tables are numbered 1..%d with no gaps' % len(TABS))
bad = [t['spell'] for t in TABS if t['spell'] not in SPELLROW]
check(not bad, 'every tablet names a spell that has a magic_spell_table row: %s' % (bad or 'all 14'))
bad = [(n + 1, TABE['poh_tab_level'][n + 1], SPELLROW[t['spell']]['levelrequired'][0])
       for n, t in enumerate(TABS)
       if TABE['poh_tab_level'][n + 1] != SPELLROW[t['spell']]['levelrequired'][0]]
check(not bad, 'poh_tab_level is the spell row\'s levelrequired: %s' % (bad[:3] or 'all 14 agree'))
bad = []
for n, t in enumerate(TABS):
    want = ', '.join(['%d %s' % (c, RUNEWORD[o]) for o, c in _runes(t['spell'])] + ['1 soft clay'])
    if TABE['poh_tab_need'][n + 1] != want:
        bad.append((t['key'], TABE['poh_tab_need'][n + 1], want))
check(not bad, 'poh_tab_need is the spell row\'s runes plus the clay: %s' % (bad[:3] or 'all 14 agree'))
bad = [t['key'] for n, t in enumerate(TABS)
       if TABE['poh_tab_spell'][n + 1] != '^' + t['spell']]
check(not bad, 'poh_tab_spell names the same spell the spec does: %s' % (bad or 'all 14'))
# and each kind needs the field its break path reads
bad = [t['key'] for t in TABS if t['kind'] == 'teleport' and 'tele_coord' not in SPELLROW[t['spell']]]
check(not bad, 'every teleport tablet\'s spell row carries a tele_coord: %s' % (bad or 'all 6'))
bad = [t['key'] for t in TABS if t['kind'] in ('convert', 'enchant')
       and 'convertobj' not in SPELLROW[t['spell']]]
check(not bad, 'every enchant and bones tablet\'s row carries a convertobj: %s' % (bad or 'all 7'))
TABRS = clean['scripts/skill_construction/scripts/poh_tablets.rs2']
check('~staff_runes' not in TABRS,
      'making a tablet does NOT go through ~staff_runes - a staff pays for casting, not for binding')
check('~give_spell_xp' not in TABRS and 'stat_advance(magic' in TABRS,
      'making pays the spell row\'s own experience, and reads it from the row')
mk = TABRS.split('[proc,poh_tab_make]')[1].split('\n[')[0]
check(before(mk, 'inv_del(inv, softclay', 'inv_add(inv,'),
      'the clay and the runes go before the tablet arrives')
for prc in ('poh_tab_teleport', 'poh_tab_gohome'):
    body = TABRS.split('[proc,%s]' % prc)[1].split('\n[')[0]
    check('~wilderness_level(coord) > 20' in body, '%s keeps the level 20 wilderness ceiling' % prc)
    check('~pre_tele_checks(coord)' in body, '%s runs the same pre-tele checks a spell does' % prc)
for prc in ('poh_tab_teleport', 'poh_tab_gohome', 'poh_tab_convert', 'poh_tab_enchant'):
    body = TABRS.split('[proc,%s]' % prc)[1].split('\n[')[0]
    check('stat(magic)' not in body, '%s asks for no Magic level - a tablet is broken, not cast' % prc)
    check('stat_advance' not in body, '%s pays no experience' % prc)
    check('inv_total(inv, $tab) < 1' in body, '%s re-checks the tablet is still held' % prc)

print('41. the tablet objs are the real OSRS ones, and they stack')
OBJTAB = blocks(read('scripts/skill_construction/configs/poh_tablets.obj'))
check(sorted(OBJTAB) == sorted(t['obj'] for t in TABS),
      'poh_tablets.obj defines exactly the %d tablets in the spec' % len(TABS))
bad = [n for n in OBJTAB if n not in OBJS]
check(not bad, 'every tablet obj is in obj.pack: %s' % (bad or 'all %d' % len(OBJTAB)))
bad = [TABE['poh_tab_obj'][n + 1] for n, t in enumerate(TABS)
       if TABE['poh_tab_obj'][n + 1] != t['obj']]
check(not bad, 'poh_tab_obj names the spec\'s objs: %s' % (bad or 'all 14'))
# STACKABLE is the point of the round: OSRS tablets stack, and a lectern that makes ten of them
# is only useful if they land in one slot.
bad = [n for n in OBJTAB if OBJTAB[n].get('stackable', [None])[0] != 'yes']
check(not bad, 'every tablet is stackable: %s' % (bad or 'all %d' % len(OBJTAB)))
# Each one is its own OSRS model, on disk and in model.pack - a name in a pack is not a file, and a
# miss shows up in game as an invisible item rather than an error (claude/osrs-cache.md).
mods = {n: OBJTAB[n].get('model', [None])[0] for n in OBJTAB}
want = {t['obj']: t['model'] for t in TABS}
check(mods == want, 'every tablet carries the model the spec imported for it: %s'
      % ('all %d, one each' % len(want) if mods == want
         else sorted(k for k in want if mods.get(k) != want[k])))
check(len(set(mods.values())) == len(mods),
      'no two tablets share a model: %d distinct' % len(set(mods.values())))
bad = [m for m in mods.values() if m not in MODELS]
check(not bad, 'every tablet model is registered in model.pack: %s' % (bad or 'all 14'))
bad = [m for m in mods.values() if not os.path.exists(os.path.join(C, 'models/obj/%s.ob2' % m))]
check(not bad, 'every tablet model is a file on disk: %s' % (bad or 'all 14'))
# no recolour anywhere: the art is the real item, so there is nothing to tint
bad = [n for n in OBJTAB if any(k.startswith('recol') for k in OBJTAB[n])]
check(not bad, 'no tablet recolours anything any more: %s' % (bad or 'none of them'))
# the icon camera is the cache's own, field for field
bad = []
for t in TABS:
    for k, v in t['icon'].items():
        if OBJTAB[t['obj']].get(k, [None])[0] != str(v):
            bad.append('%s %s' % (t['obj'], k))
check(not bad, 'every tablet keeps the 2d camera the OSRS config gave it: %s' % (bad or 'all 14'))
bad = [t['obj'] for t in TABS if OBJTAB[t['obj']].get('name', [None])[0] != t['name']]
check(not bad, 'every obj name is the OSRS name: %s' % (bad or 'all 14'))
# iop1 exactly on the ones that do something by themselves
want_break = {t['obj'] for t in TABS if t['kind'] != 'enchant'}
have_break = {n for n in OBJTAB if OBJTAB[n].get('iop1', [None])[0] == 'Break'}
check(want_break == have_break,
      'Break is on the nine tablets that need no target, and only those: %s'
      % (sorted(want_break ^ have_break) or 'exact'))
# and the triggers match the ops - a trigger on an op the obj does not carry never fires
fired1 = set(re.findall(r'^\[opheld1,(\w+)\]', TABRS, re.M))
firedu = set(re.findall(r'^\[opheldu,(\w+)\]', TABRS, re.M))
check(fired1 == want_break, 'every [opheld1] is on a tablet that carries iop1=Break: %s'
      % (sorted(fired1 ^ want_break) or 'exact'))
check(firedu == {t['obj'] for t in TABS if t['kind'] == 'enchant'},
      'the five enchant tablets are the [opheldu] ones and have no Break')

print('42. the lectern window and the seven lecterns')
LECT = TSPEC['lecterns']
MAXT = const('poh_tab_max')
over = [(l['name'], len(l['tablets'])) for l in LECT if len(l['tablets']) > MAXT]
check(not over, 'no lectern lists more than ^poh_tab_max (%d) tablets: %s'
      % (MAXT, over or 'largest is %d' % max(len(l['tablets']) for l in LECT)))
check(len([c for c in IFF['poh_tabletmenu'][0] if re.fullmatch(r'row\d+', c)]) == MAXT,
      'poh_tabletmenu has exactly %d rows, one per listable tablet' % MAXT)
nth = TABRS.split('[proc,poh_tab_nth]')[1].split('\n[')[0]
got = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', nth)}
idx = {t['key']: n + 1 for n, t in enumerate(TABS)}
want = {l['tier'] * MAXT + i: idx[k] for l in LECT for i, k in enumerate(l['tablets'])}
check(got == want, '~poh_tab_nth is exactly the spec\'s seven lists: %d entries%s'
      % (len(want), '' if got == want else ' MISMATCH %s' % sorted(set(got.items()) ^ set(want.items()))[:3]))
check(sorted(TABE['poh_lectern_name']) == sorted(l['tier'] for l in LECT),
      'poh_lectern_name names all %d lecterns' % len(LECT))
# Study really opens it, on every lectern, and the loc really carries that op
studies = {int(a): int(b) for a, b in
           re.findall(r'\[oploc1,poh_lectern_?(\d)\]\n~poh_tab_pick\((\d)\);',
                      src['scripts/skill_construction/scripts/poh_furn_ops.rs2'])}
check(studies == {l['tier']: l['tier'] for l in LECT},
      'all seven lecterns Study their own tier: %s' % (studies if len(studies) != 7 else 'yes'))
bad = [l['loc'] for l in LECT if (POHLOC.get(l['loc'], {}).get('op1') or [None])[0] != 'Study']
check(not bad, 'every lectern loc really advertises op1=Study: %s' % (bad or 'all seven'))
# the row procs drive the window through if_setobject, which is the obj path and not if_setmodel
row0 = src[MENUS].split('[proc,poh_tab_row0]')[1].split('\n[')[0]
check('if_setobject(' in row0 and 'if_setmodel(' not in row0,
      'the icons come from if_setobject, which takes the obj and reads its own 2d camera')
scale = int(re.search(r'if_setobject\(poh_tabletmenu:t0model, .*, (\d+)\);', row0).group(1))
d = IFF['poh_tabletmenu'][1]['t0model']
rowc = IFF['poh_tabletmenu'][1][d['layer']]
cw, ch = int(d['width']), int(d['height'])
cx, cy = int(d['x']) + cw // 2, int(d['y']) + ch // 2
# Fourteen models with fourteen cameras now, so every one is measured, not just the first. The
# zoom is what if_setobject works out: the obj's own 2dzoom x 100 / scale.
worst, bad = None, []
for t in TABS:
    zoom = int(t['icon']['2dzoom']) * 100 // scale
    hw, rise, drop = ifmodels.extent(ifmodels.R.Model(
        os.path.join(C, 'models/obj/%s.ob2' % t['model'])), cw, ch,
        int(t['icon'].get('2dxan', 0)), int(t['icon'].get('2dyan', 0)), zoom)
    if not (cx - hw >= 0 and cx + hw <= int(rowc['width'])
            and cy - rise >= 0 and cy + drop <= int(rowc['height'])):
        bad.append('%s x %.0f..%.0f y %.0f..%.0f' % (t['obj'], cx - hw, cx + hw, cy - rise, cy + drop))
    if worst is None or (rise + drop) > worst[0]:
        worst = (rise + drop, t['obj'], hw, rise, drop)
check(not bad, 'all %d tablet icons at scale %d land inside their %sx%s row: %s'
      % (len(TABS), scale, rowc['width'], rowc['height'],
         bad or 'tallest is %s at %.0f x %.0f, y %.0f..%.0f'
         % (worst[1], worst[2] * 2, worst[0], cy - worst[3], cy + worst[4])))

print('43. the tablet generator still produces exactly what is checked in')
kept3 = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/configs/poh_tablets.obj',
    'scripts/skill_construction/configs/poh_tablets.enum',
    'scripts/skill_construction/scripts/poh_tablets.rs2',
    'scripts/skill_construction/configs/construction.constant',
    'scripts/skill_combat/configs/magic/spells.constant',
    'scripts/skill_magic/configs/magic_spells.dbrow',
    'pack/obj.pack']}
r = _sp.run([sys.executable, os.path.join(C, 'tools/gentablets.py')],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/gentablets.py runs clean'
      + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
moved = [f for f in kept3 if open(os.path.join(C, f), 'rb').read() != kept3[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept3[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
op = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in read('pack/obj.pack').split('\n') if '=' in l}
check(op.get('saw') == 8191 and min(op[t['obj']] for t in TABS) == 8192,
      'the tablets took the ids after the saw, and nothing already in a bank moved')

print('44. breaking a tablet plays the tablet-break animation, not the spell')
# The whole point of the round: every break path used to play the CAST - human_castteleport and
# teleport_casting for a teleport, the enchant's own pair for an enchant - which is the animation
# for casting the spell, not for smashing a tablet. One proc plays OSRS's break pair now.
BRK = TSPEC['break']
BRKSEQ = 'scripts/skill_construction/configs/poh_tab_break.seq'
BRKSPOT = 'scripts/skill_construction/configs/poh_tab_break.spotanim'
banim = TABRS.split('[proc,poh_tab_breakanim]')[1].split('\n[')[0] if '[proc,poh_tab_breakanim]' in TABRS else ''
check('anim(%s, 0);' % BRK['anim'] in banim,
      '~poh_tab_breakanim plays %s' % BRK['anim'])
check('spotanim_pl(%s, %d, 0);' % (BRK['spot'], BRK['height']) in banim,
      '~poh_tab_breakanim plays %s at height %d' % (BRK['spot'], BRK['height']))
for proc in ('poh_tab_teleport', 'poh_tab_gohome', 'poh_tab_convert', 'poh_tab_enchant'):
    body = TABRS.split('[proc,%s]' % proc)[1].split('\n[')[0]
    check('~poh_tab_breakanim;' in body, '~%s breaks with the break animation' % proc)
    bad = re.findall(r'anim\((human_castteleport|teleport_casting|\$anim|\$spotanim)', body)
    check(not bad, '~%s plays no cast animation of its own: %s' % (proc, bad or 'none'))
check('~player_teleport_normal' not in TABRS,
      'nothing calls ~player_teleport_normal, which would play the cast (it teleports via ~p_telejump_safe)')
check('~p_telejump_safe(' in TABRS, 'the teleport still goes through ~p_telejump_safe, with its own checks')
# the art chain, the same sweep as check 19: a name in a pack is not a file
seqd = set(re.findall(r'^\[(\w+)\]', read(BRKSEQ), re.M))
check(BRK['anim'] in seqd and BRK['spot'] in seqd,
      'poh_tab_break.seq declares both %s and %s' % (BRK['anim'], BRK['spot']))
check(BRK['anim'] in SEQS and BRK['spot'] in SEQS, 'both are registered in seq.pack')
SPOTS = set(packmap('pack/spotanim.pack'))
spotcfg = blocks(read(BRKSPOT))
check(BRK['spot'] in spotcfg and BRK['spot'] in SPOTS,
      '%s is a spotanim config and is in spotanim.pack' % BRK['spot'])
smodel = spotcfg[BRK['spot']].get('model', [None])[0]
check(smodel in MODELS, 'the break graphic model %s is in model.pack' % smodel)
check(os.path.exists(os.path.join(C, 'models/spot/%s.ob2' % smodel)),
      '%s.ob2 is on disk' % smodel)
check(spotcfg[BRK['spot']].get('anim', [None])[0] in SEQS,
      'the break graphic animates on a seq that is registered')
bframes = re.findall(r'^frame\d+=(\S+)$', read(BRKSEQ), re.M)
bdelays = re.findall(r'^delay\d+=', read(BRKSEQ), re.M)
check(len(bframes) > 0 and len(bdelays) == len(bframes),
      'every one of the %d break frames has a delay' % len(bframes))
ANIMS2 = set(packmap('pack/anim.pack'))
ANIMSETS2 = set(packmap('pack/animset.pack'))
BASES2 = set(packmap('pack/base.pack'))
bad = [f for f in bframes if f not in ANIMS2]
check(not bad, 'every break frame is in anim.pack: %s' % (bad or 'all %d' % len(bframes)))
for st_ in sorted({f.rsplit('_', 1)[0] for f in bframes}):
    check(st_ in ANIMSETS2, '%s is in animset.pack' % st_)
    check(st_.replace('anim_', 'base_', 1) in BASES2, '%s base is in base.pack' % st_)
    fp = os.path.join(C, 'models', st_ + '.anim')
    check(os.path.exists(fp) and os.path.getsize(fp) > 0, '%s.anim is on disk' % st_)

print('45. Make 1 / 5 / 10 / X')
QSTEPS = TSPEC['quantities']['steps']
QMAX = const('poh_tab_qty_max')
order, coms = IFF['poh_tabletmenu']
btns = ['qty%d' % n for n in QSTEPS] + ['qtyx']
missing = [b for b in btns + ['qtylabel'] if b not in coms]
check(not missing, 'the window has a button for every quantity: %s' % (missing or ', '.join(btns)))
bad = [b for b in btns if coms[b].get('buttontype') != 'normal']
check(not bad, 'every quantity button is a button: %s' % (bad or 'all %d' % len(btns)))
bad = [b for b in btns if coms[b].get('type') != 'text' or 'layer' in coms[b]]
check(not bad, 'each is a top-level text component, so if_settext really reaches it: %s' % (bad or 'all four'))
# they must not sit under the rows, or a click lands on both
rowtop = min(int(coms[c]['y']) for c in coms if re.fullmatch(r'row\d+', c))
bad = [b for b in btns if int(coms[b]['y']) + int(coms[b]['height']) > rowtop]
check(not bad, 'the buttons sit above the first row (y %d): %s' % (rowtop, bad or 'all four'))
pick = src[MENUS].split('[proc,poh_tab_pick]')[1].split('\n[')[0]
bad = [b for b in btns if 'if_addresumebutton(poh_tabletmenu:%s);' % b not in pick]
check(not bad, 'every quantity button is a resume target: %s' % (bad or 'all four'))
for n in QSTEPS:
    check('case poh_tabletmenu:qty%d : %%poh_tab_qty = %d;' % (n, n) in pick,
          'clicking %d sets the quantity to %d' % (n, n))
check('case poh_tabletmenu:qtyx : ~poh_tab_qty_ask;' in pick, 'X asks for a number')
ask = src[MENUS].split('[proc,poh_tab_qty_ask]')[1].split('\n[')[0]
check('p_countdialog;' in ask, 'Make X uses p_countdialog, the prompt Cook X uses')
check('if (last_int < 1) {' in ask, 'a cancelled prompt (0) leaves the quantity alone')
check('if (%poh_tab_qty > ^poh_tab_qty_max) {' in ask, 'Make X is clamped to ^poh_tab_qty_max (%d)' % QMAX)
draw = src[MENUS].split('[proc,poh_tab_qty_draw]')[1].split('\n[')[0]
bad = [b for b in btns if 'if_settext(poh_tabletmenu:%s, "@whi@' % b not in draw]
check(not bad, 'every button is redrawn white before one is picked out: %s' % (bad or 'all four'))
check(draw.count('@gre@') == len(QSTEPS) + 1,
      'exactly one of the %d can be green at a time' % len(btns))
TAGS = set(re.findall(r'@(\w{3})@', draw))
check(TAGS <= KNOWN, 'the quantity tints are tags PixFont.evaluateTag knows: %s' % sorted(TAGS))
# the making loop: bounded, and it stops at the first refusal rather than repeating the message
mk = TABRS.split('[proc,poh_tab_make_n]')[1].split('\n[')[0]
check('while ($i < $count & $i < ^poh_tab_qty_max) {' in mk,
      'the make loop is bounded by both the count and ^poh_tab_qty_max')
check('if (~poh_tab_make($tab) = false) {' in mk and 'return;' in mk,
      'it stops at the first tablet it cannot make')
check('[proc,poh_tab_make](int $tab)(boolean)' in TABRS,
      '~poh_tab_make answers whether it made one')
check('while (true)' not in TABRS and 'def_string' not in TABRS,
      'no unproven idiom in the tablet script (claude/rs2-compile-traps.md)')
# the window comes down before the animation and the loop puts it back
after = pick.split('if ($pick > 0) {')[1]
check(before(after, 'if_close;', '~poh_tab_make_n('),
      'the window closes before the tablets are made, so the animation is visible')
# the quantity lives in a temp varp: it is a setting for this visit, not part of the house
check('poh_tab_qty' in varps, '%poh_tab_qty is registered in varp.pack')
qvarp = blocks(read('scripts/skill_construction/configs/construction.varp')).get('poh_tab_qty', {})
check('scope' not in qvarp, '%poh_tab_qty is temp - it is a setting, not part of the saved house')
p12q = ifrender.font('b12_full')
wide = max((p12q.width(str(n)) for n in list(QSTEPS) + [QMAX]))
check(wide <= int(coms['qty1']['width']),
      'the widest number a quantity button can show is %dpx in a %spx box' % (wide, coms['qty1']['width']))

def ftabn(loc):
    """The item number of the piece built from this loc, out of ~poh_furn_show's own switch."""
    m = re.search(r'case (\d+) : loc_add\(\$spot, %s, ' % loc, fu)
    return int(m.group(1)) if m else None

print('46. the garden: the supplier, her prices, and the way out')
GNPC = blocks(read('scripts/skill_construction/configs/poh_garden.npc'))
GINV = read('scripts/skill_construction/configs/poh_garden.inv')
GRS = read('scripts/skill_construction/scripts/poh_garden.rs2')
GOBJ = blocks(read('scripts/skill_construction/configs/poh_garden_mats.obj'))
sup = GNPC.get('poh_garden_supplier', {})
check(bool(sup) and 'poh_garden_supplier' in NPCS, 'the Garden supplier is a config and is in npc.pack')
# her art, all the way to the files: a name in a pack is not a model on disk
ON_DISK2 = set()
for root, _, fs in os.walk(os.path.join(C, 'models')):
    for fn in fs:
        if fn.endswith('.ob2'): ON_DISK2.add(fn[:-4])
mods = [v for k, vs in sup.items() if re.match(r'^(model|head)\d+$', k) for v in vs]
check(len(mods) == 11, 'she has %d models and chatheads' % len(mods))
bad = [m for m in mods if m not in MODELS]
check(not bad, 'every one is in model.pack: %s' % (bad or 'all %d' % len(mods)))
bad = [m for m in mods if m not in ON_DISK2]
check(not bad, 'every one is a .ob2 on disk: %s' % (bad or 'all %d' % len(mods)))
# no dead op, and no op without a trigger
ops = sorted(int(k[2:]) for k in sup if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),poh_garden_supplier\]', GRS, re.M))
check(ops == trig, 'every op she has is wired: declares %s, triggers %s' % (ops, trig))
# the comment at the top of the file mentions it too, so count the calls rather than the mentions
check(len(re.findall(r'^\s*~openshop_activenpc;$', GRS, re.M)) == 2,
      'both ways in open her own shop through her npc params')
# the shop: her params, the inv, and the prices
check((sup.get('param') or []) and any(v == 'owned_shop,poh_garden_shop' for v in sup['param']),
      'she owns poh_garden_shop')
prm = dict(v.split(',', 1) for v in sup.get('param', []))
check(prm.get('shop_sell_multiplier') == str(const('poh_garden_sell')),
      'her selling multiplier is ^poh_garden_sell (%s)' % const('poh_garden_sell'))
check(prm.get('shop_buy_multiplier') == str(const('poh_garden_buy')),
      'her buying multiplier is ^poh_garden_buy (%s)' % const('poh_garden_buy'))
check(prm.get('shop_delta') == '0', 'shop_delta is 0, so the price does not drift off the OSRS number')
check('[poh_garden_shop]' in GINV and 'restock=yes' in GINV, 'poh_garden_shop restocks')
# THE ONE THE BUILD CAUGHT: an inv needs an id in pack/inv.pack before an npc param can name it.
# Without it the packer says "Invalid property value: param=owned_shop,..." and carries on, so the
# shop simply would not open in game.
INVS = set(packmap('pack/inv.pack'))
check('poh_garden_shop' in INVS, 'poh_garden_shop has an id in inv.pack')
stock = dict((m.group(2), (int(m.group(3)), int(m.group(4))))
             for m in re.finditer(r'^stock(\d+)=(\w+),(\d+),(\d+)$', GINV, re.M))
check(len(stock) == 23, 'she stocks %d things' % len(stock))
GOBJ.update(blocks(read('scripts/skill_construction/configs/poh_formal_mats.obj')))
bad = [k for k in stock if k not in GOBJ]
check(not bad, 'every line of stock is one of the garden materials: %s' % (bad or 'all 23'))
bad = [(k, v) for k, v in stock.items() if v != (20, 100)]
check(not bad, 'twenty of each, restocking a unit a minute: %s' % (bad or 'all 23'))
# THE PRICES ARE THE CACHE'S: the wiki's numbers are knowledge, the costs are data, and the
# multiplier is what ties them together. If they ever disagree, one of the three moved.
#
# THESE WERE THE BUY COLUMN UNTIL 2026-09-15 - 400 for a bagged dead tree, which is what the shop
# pays FOR one, not what it charges. The constant, the npc param and this table all said the same
# wrong thing, so all three agreed and the check passed. Every number below is now the sell column
# of the item's own shop row, and the Garden Centre's sell column is simply the item's value.
WIKI = {'poh_bag_dead_tree': 1000, 'poh_bag_nice_tree': 2000, 'poh_bag_oak_tree': 5000,
        'poh_bag_willow_tree': 10000, 'poh_bag_maple_tree': 15000, 'poh_bag_yew_tree': 20000,
        'poh_bag_magic_tree': 50000, 'poh_bag_plant_1': 1000, 'poh_bag_plant_2': 5000,
        'poh_bag_plant_3': 10000,
        # the six flowers, which were buildable and unobtainable until this round
        'poh_bag_flower': 5000, 'poh_bag_daffodils': 10000, 'poh_bag_bluebells': 15000,
        'poh_bag_sunflower': 5000, 'poh_bag_marigolds': 10000, 'poh_bag_roses': 15000,
        # and the seven hedges
        'poh_bag_thorny_hedge': 5000, 'poh_bag_nice_hedge': 10000,
        'poh_bag_small_box_hedge': 15000, 'poh_bag_topiary_hedge': 20000,
        'poh_bag_fancy_hedge': 25000, 'poh_bag_tall_fancy_hedge': 50000,
        'poh_bag_tall_box_hedge': 100000}
check(sorted(WIKI) == sorted(stock), 'and the table below covers exactly what she stocks')
bad = []
for k, want in WIKI.items():
    cost = int((GOBJ.get(k, {}).get('cost') or ['0'])[0])
    got = cost * const('poh_garden_sell') // 1000
    buy = cost * const('poh_garden_buy') // 1000
    if got != want or buy != want * 2 // 5:
        bad.append((k, cost, got, want))
check(not bad, 'every price comes out at the OSRS number, and the buy-back at 40%% of it: %s'
      % (bad[:3] or 'all 23, 1,000-100,000 coins'))
# where she stands: once, on a tile with nothing solid on it
GMAP = 'maps/m46_52.jm2'
sec = None; spots = []; solid = {}
for line in read(GMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCS['poh_garden_supplier']: spots.append((lv, x, z))
    if sec == 'LOC':
        d = data.split()
        if (len(d) < 2 or int(d[1]) != 22) and lv == 0: solid.setdefault((x, z), []).append(int(d[0]))
check(len(spots) == 1, 'she is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    check(lv == 0 and (x, z) not in solid,
          'her tile (local %d,%d = %d,%d) carries nothing solid' % (x, z, 2944 + x, 3328 + z))
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in solid]
    check(not ring, 'and neither do the eight tiles around her: %s' % (ring or 'all clear'))

print('47. the garden: the centrepiece, and the exit portal that lives in it')
GFAMS = [f for f in FSPEC['families'] if f.get('room') == 'garden']
check(len(GFAMS) == 7, 'seven garden families: %s' % [f['key'] for f in GFAMS])
GHOT = {h for f in GFAMS for h in f['hotspots']}
want = {LOCS['loc474_153%d' % n] for n in range(61, 68)}
check(GHOT == want, 'they claim exactly the garden\'s seven hotspots')
# every garden piece: a real material, a level and an experience number that rise with the tier
for f in GFAMS:
    lv = [p['level'] for p in f['pieces']]
    xp = [p['xp'] for p in f['pieces']]
    check(lv == sorted(lv), '%s: levels rise (%s)' % (f['key'], lv))
    check(xp == sorted(xp), '%s: experience rises (%s)' % (f['key'], xp))
    bad = [m for p in f['pieces'] for m in p['mats'] if m[0] not in OBJS]
    check(not bad, '%s: every material exists (%s)' % (f['key'], bad or 'yes'))
# the exit portal is the level-1 centrepiece, and the only piece that is
cp = next(f for f in GFAMS if f['key'] == 'centrepiece')
first = cp['pieces'][0]
check(first['loc'] == 'poh_exit_portal' and first['level'] == 1,
      'the exit portal is the centrepiece you can build at level 1')
check(const('poh_furn_exit_portal') == ftabn('poh_exit_portal'),
      '^poh_furn_exit_portal (%s) is that piece\'s own item number' % const('poh_furn_exit_portal'))
check('Remove' in (POHLOC.get('poh_exit_portal', {}).get('op5') or []),
      'the portal carries op5=Remove, so it can be replaced by a pond')
# the tile it goes on, read out of all six template squares rather than remembered
CPID = LOCS['loc474_15361']
tiles, angles = set(), set()
for sq, levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    sec = None
    for line in read('maps/%s.jm2' % sq).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= '); continue
        if sec != 'LOC' or ':' not in line: continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        d = data.split()
        if int(d[0]) != CPID or lv not in levels or not (0 <= x < 8 and 8 <= z < 16): continue
        tiles.add((x % 8, z % 8)); angles.add((sq, lv, int(d[2]) if len(d) > 2 else 0))
check(tiles == {(const('poh_garden_cp_x'), const('poh_garden_cp_z'))},
      'every style has its Centrepiece space at ^poh_garden_cp_x/z (%s)' % sorted(tiles))
turned = {lv for sq, lv, a in angles if a and sq == 'm29_79'}
check(turned == {0} and all(a == 0 for sq, lv, a in angles if (sq, lv) != ('m29_79', 0)),
      'only style 0 has it turned, which is what ~poh_garden_cp_angle says')
ang = GRS.split('[proc,poh_garden_cp_angle]')[1].split('\n[')[0]
check('%poh_style = 0' in ang and 'return(1);' in ang and 'return(0);' in ang,
      '~poh_garden_cp_angle answers 1 for style 0 and 0 for the rest')
# the grant, and the guards around it
ens = GRS.split('[proc,poh_ensure_exit]')[1].split('\n[')[0]
check('~poh_furn_count_item(^poh_furn_exit_portal) > 0' in ens,
      'a house that already has a portal is left alone')
check('~poh_furn_at(' in ens, 'a centrepiece that is already built on is left alone')
check('~poh_furn_pack(' in ens and '^poh_garden_cp_x' in ens,
      'the portal is stored as furniture on the centrepiece tile')
check('stat(construction)' not in ens and 'inv_del' not in ens,
      'the first one is free and needs no level - OSRS starts a house with it built')
pohrs = clean[FILES[0]]
ent = pohrs.split('[proc,poh_enter]')[1].split('\n[')[0]
check('~poh_ensure_exit' in ent and before(ent, '~poh_ensure_exit', '~poh_build'),
      '~poh_enter makes sure of the portal before it builds the house')
check('~poh_spawn_exit' not in pohrs + clean[FILES[3]],
      'nothing loc_adds a loose portal any more')
rmf = fu.split('[proc,poh_furn_remove]')[1].split('\n[')[0]
check('^poh_furn_exit_portal' in rmf and '~poh_furn_count_item' in rmf,
      'the last exit portal cannot be taken out')

print('48. the Stonemason, and the formal garden he supplies')
SNPC = blocks(read('scripts/skill_construction/configs/poh_stone.npc'))
SINV = read('scripts/skill_construction/configs/poh_stone.inv')
SRS = read('scripts/skill_construction/scripts/poh_stone.rs2')
mason = SNPC.get('poh_stonemason', {})
check(bool(mason) and 'poh_stonemason' in NPCS, 'the Stonemason is a config and is in npc.pack')
mods = [v for k, vs in mason.items() if re.match(r'^(model|head)\d+$', k) for v in vs]
bad = [m for m in mods if m not in MODELS or m not in ON_DISK2]
check(mods and not bad, 'all %d of his models are in model.pack and on disk: %s' % (len(mods), bad or 'yes'))
check((mason.get('readyanim') or [''])[0].startswith('dwarf'),
      'he animates as the dwarf he is (%s)' % (mason.get('readyanim') or ['?'])[0])
ops = sorted(int(k[2:]) for k in mason if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),poh_stonemason\]', SRS, re.M))
check(ops == trig, 'every op he has is wired: declares %s, triggers %s' % (ops, trig))
check(len(re.findall(r'^\s*~openshop_activenpc;$', SRS, re.M)) == 2, 'both ways in open his store')
prm = dict(v.split(',', 1) for v in mason.get('param', []))
check(prm.get('owned_shop') == 'poh_stone_shop', 'he owns poh_stone_shop')
check('poh_stone_shop' in INVS, 'poh_stone_shop has an id in inv.pack')
check(prm.get('shop_sell_multiplier') == str(const('poh_stone_sell')),
      'his selling multiplier is ^poh_stone_sell (%s)' % const('poh_stone_sell'))
check(prm.get('shop_buy_multiplier') == str(const('poh_stone_buy')),
      'his buying multiplier is ^poh_stone_buy (%s)' % const('poh_stone_buy'))
check(prm.get('shop_delta') == '0', 'a fixed-price shop, like the Garden Centre')
sstock = dict((m.group(2), (int(m.group(3)), int(m.group(4))))
              for m in re.finditer(r'^stock(\d+)=(\w+),(\d+),(\d+)$', SINV, re.M))
check(len(sstock) == 4, 'the Stonemason stocks what he is meant to: %d things' % len(sstock))
bad = [k for k in sstock if k not in OBJS]
check(not bad, 'every line of stock is a real obj: %s' % (bad or ', '.join(sstock)))
# the OSRS prices again: their cache costs are exactly twice what he charges
# Gold leaf joined them when the gilded furniture arrived - the opulent rug and the gilded wall
# decoration are made of it, and it is priced the same way, coming out at OSRS's own 130,000.
# MAGIC STONE joined them for the costume room's cape rack, whose top tier is one magic stone at
# level 99 - the same thing it is for in OSRS. It is its own obj rather than 377's unpriced
# placeholder, and it is priced by the same arithmetic: OSRS's own 4,000,000.
SWIKI = {'limestonebrick': 26, 'poh_marble_block': 325000, 'gold_leaf': 130000,
         'magic_stone': 975000}
ALLOBJ = dict(OBJCFG)
ALLOBJ.update(blocks(read('scripts/skill_construction/configs/poh_formal_mats.obj')))
ALLOBJ.update(blocks(read('scripts/_unpack/377/all.obj')))

# EVERY LINE CONSTRUCTION SUPPLIES STOCKS CARRIES A COST, checked here rather than up in group 26
# because this is where the lookup covering all.obj exists - three of its five lines are 377 objs.
# A shop prices off the obj's own cost, so a stocked obj with no cost is one the counter gives away.
# That is not hypothetical: the hammer has no cost in the cache, and it is the reason the hammer
# stayed in the operator's dialogue at ^sawmill_cost_hammer when the saw and the cloth moved onto
# the counter. Putting it on the shelf would hand out free hammers and trip this.
for _n in COUNTER:
    check(int((ALLOBJ.get(_n, {}).get('cost') or ['0'])[0]) > 0,
          'Construction Supplies: %s carries a cost for the counter to price it off' % _n)
bad = []
for k, want in SWIKI.items():
    cost = int((ALLOBJ.get(k, {}).get('cost') or ['0'])[0])
    got = cost * const('poh_stone_sell') // 1000
    if got != want:
        bad.append((k, cost, got, want))
check(not bad, 'all four come out at the OSRS price: %s'
      % (bad[:3] or '26, 325,000, 130,000 and 975,000 coins'))
check(sorted(sstock) == sorted(SWIKI), 'and he stocks exactly those four')
# OSRS's own quantities. The first three restock a unit a minute, like the Garden Centre; a magic
# stone is a 4,000,000gp item and restocks a tenth as fast.
SQTY = {'limestonebrick': (1000, 100), 'poh_marble_block': (20, 100),
        'gold_leaf': (20, 100), 'magic_stone': (10, 100)}
bad = [(k, v) for k, v in sstock.items() if v != SQTY.get(k)]
check(not bad, 'a thousand bricks, twenty blocks, twenty leaves and ten stones: %s'
      % (bad or 'all four lines'))
# where he stands: western Keldagrim, on nothing, with room around him
KMAP = 'maps/m44_159.jm2'
sec = None; spots = []; ksolid = set()
for line in read(KMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCS['poh_stonemason']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if len(d) < 2 or int(d[1]) != 22: ksolid.add((x, z))
check(len(spots) == 1, 'he is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in ksolid]
# VALUES AFTER THE CLAIM, NOT INSIDE IT - a mutation's label is a check's wording, so a number
# in the middle of a claim makes a label that names nothing the moment the number moves. Fifth
# time this rule has come up; tools/mutate_labels.py is what keeps finding it.
    check(lv == 0 and not ring, 'his tile and the eight around it are clear: (%d,%d) %s'
          % (2816 + x, 10176 + z, ring or 'all nine'))

print('49. the formal garden room, and what goes in it')
FGFAMS = [f for f in FSPEC['families'] if f.get('room') == 'formal garden']
check(len(FGFAMS) == 7, 'seven formal garden families: %s' % [f['key'] for f in FGFAMS])
FGHOT = {h for f in FGFAMS for h in f['hotspots']}
# Every hotspot the room places is claimed now: the centrepiece, the four flower spaces, the
# fencing and the three Hedging tiles. The hedge was the last of them, and it was waiting on seven
# bagged hedges - which turned out to need no import at all, because every bagged anything in OSRS
# is the same sack model this repo already has.
check(FGHOT == {LOCS['loc474_15368'], LOCS['loc474_15369']}
              | {LOCS['loc474_1537%d' % n] for n in (0, 1, 2, 3, 4, 5, 6)},
      'they claim the centrepiece, the four flower spaces, the fencing and the hedging')
check(all((TEMPL.get({v: k for k, v in LOCS.items()}[h], {}).get('category') or [''])[0]
          == 'poh_hotspot' for h in FGHOT),
      'and every one of them really is a hotspot loc')
# the room is real: its zone, its doors and its price
check(const('poh_room_formal_garden') == 16 and COUNT == 16,
      'the formal garden is room type %s of %s' % (const('poh_room_formal_garden'), COUNT))
ZONE = enumtable(ROOMS, 'poh_room_zone'); DOORS = enumtable(ROOMS, 'poh_room_doors')
check(int(ZONE[16]) == 2 * 8 + 1,
      'its template zone is the one the templates are drawn in: 2,1 packs to %s' % ZONE[16])
# the door mask, read out of all six template squares rather than believed
DOORIDS = {LOCS['loc474_%d' % n] for n in range(15305, 15318)}
sides = set()
for sq, levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    sec = None
    for line in read('maps/%s.jm2' % sq).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= '); continue
        if sec != 'LOC' or ':' not in line: continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        if int(data.split()[0]) not in DOORIDS or lv not in levels: continue
        if not (16 <= x < 24 and 8 <= z < 16): continue
        lx, lz = x - 16, z - 8
        sides.add(1 if lz == 7 else 2 if lx == 7 else 4 if lz == 0 else 8 if lx == 0 else 0)
check(0 not in sides and sum(sides) == int(DOORS[16]),
      'its door mask is the sides the six template squares actually have doors on: %s against %s'
      % (DOORS[16], sum(sides)))
check(int(enumtable(ROOMS, 'poh_room_level')[16]) == 55
      and int(enumtable(ROOMS, 'poh_room_cost')[16]) == 75000,
      'level 55 and 75,000 coins, as in OSRS')
# the centrepiece: a way out at level 1, then the gazebo and the three fountains
fc = next(f for f in FGFAMS if f['key'] == 'formalcentre')
check(fc['pieces'][0]['loc'] == 'poh_exit_portal' and fc['pieces'][0]['level'] == 1,
      'a formal garden can hold a way out too, at level 1')
marble = [p for p in fc['pieces'] if any(m[0] == 'poh_marble_block' for m in p['mats'])]
check(len(marble) == 3 and [len(p['mats']) for p in marble] == [1, 1, 1],
      'the three fountains are the marble ones: %s' % [p['label'] for p in marble])
check([m[1] for p in marble for m in p['mats']] == [1, 2, 3],
      'one, two and three blocks, as OSRS charges')
check('poh_exit_portal' in {k for k in FSPEC.get('loc_allowances', {}) if k != '_'},
      'the portal being in two families is a named allowance, not an accident')
# one removal trigger per loc, or it would not compile
dup = [l for l in re.findall(r'^\[oploc5,(\w+)\]', fu, re.M)]
check(len(dup) == len(set(dup)), 'no loc has two removal triggers: %d triggers' % len(dup))


# ============================================================================ 50
print('50. the windows are built once per click, not once per row (the instruction budget)')
# ScriptRunner allows a script 500,000 opcodes and does NOT reset the count across the
# p_pausebutton a window waits on, so everything a player does with one window comes out of one
# budget. The room window used to ask "what is the nth room that fits" seven times a page, each
# question walking the whole room ladder and each rung scanning all 64 grid slots: 913,000 opcodes
# over three pages, and "branch Too many instructions" thrown out of poh.rs2 on More rooms.
# claude/poh-menu-opcount.md has the measurements and how they were taken.
poh = clean[FILES[0]]
bd = clean[FILES[3]]
mn = clean[FILES[6]]
cp = poh.split('[proc,poh_can_place]', 1)[1].split('\n[', 1)[0]
check('~poh_room_total' not in cp and '~poh_house_empty' in cp,
      '~poh_can_place asks ~poh_house_empty, not ~poh_room_total')
he = poh.split('[proc,poh_house_empty]', 1)[1].split('\n[', 1)[0]
check('^poh_type_mask' in he and '~poh_word_get' in he,
      'and ~poh_house_empty masks whole layout words rather than decoding slots')
# re.search(...).group(1) raises on None, which is the same crash-not-a-check as a bare .index:
# removing the constant blew the battery up instead of failing this.
_tm = re.search(r'\^poh_type_mask\s*=\s*(\d+)', CONST)
check(_tm and int(_tm.group(1)) == 0x3f3f3f3f,
      '^poh_type_mask covers the four 6-bit type fields of a word, nothing else')
check('return(false)' in he, 'it stops at the first room it finds')
fm = bd.split('[proc,poh_fit_mask]', 1)[1].split('\n[', 1)[0]
check('~poh_room_fits' in fm and '$bit = calc($bit * 2)' in fm,
      '~poh_fit_mask turns the ladder into one bitmask')
nf = bd.split('[proc,poh_nth_fit]', 1)[1].split('\n[', 1)[0]
check('~poh_' not in nf, '~poh_nth_fit calls nothing - it just reads bits')
RC = int(re.search(r'\^poh_room_count\s*=\s*(\d+)', CONST).group(1))
check(RC <= 31,
      'the room types all fit in the bits of one mask, whose ceiling is 31: %d of them' % RC)
pick = mn.split('[proc,poh_pick_room]', 1)[1].split('\n[', 1)[0]
check('[proc,poh_pick_room](int $mask)(int)' in mn,
      '~poh_pick_room is handed the mask rather than the cell it is for')
check('~poh_fit_mask' not in pick and '~poh_nth_room' not in pick,
      'and derives nothing while paging')
ROWS_ = int(re.search(r'\^poh_menu_rows\s*=\s*(\d+)', CONST).group(1))
check(pick.count('~poh_nth_fit') == ROWS_ + 1,
      'it reads its %d rows and the More rooms button straight out of the mask' % ROWS_)
hc = bd.split('[proc,poh_hotspot_click]', 1)[1].split('\n[', 1)[0]
check(hc.count('~poh_fit_mask') == 1, 'the click builds the mask exactly once')
check('~poh_nth_room' not in alltext, 'the per-row walk is gone from the build, not just unused')

# ============================================================================ 51
print('51. and the furniture window pages by arithmetic, for the same reason')
fn = fu.split('[proc,poh_furn_nth]', 1)[1].split('\n[', 1)[0]
check('while' not in fn, '~poh_furn_nth does not walk every piece in the game per row')
check('poh_fam_first' in fn and 'poh_fam_last' in fn, "it adds the row to the family's first piece")
ffirst = enumtable(FURNE, 'poh_fam_first')
flast = enumtable(FURNE, 'poh_fam_last')
ffam = enumtable(FURNE, 'poh_furn_fam')
byfam = {}
for item, f in ffam.items():
    byfam.setdefault(int(f), []).append(int(item))
check(len(ffirst) == len(byfam) and len(flast) == len(byfam),
      'every one of the %d families has a first and a last' % len(byfam))
bad = [f for f, items in byfam.items()
       if sorted(items) != list(range(int(ffirst[f]), int(flast[f]) + 1))]
check(not bad, "and each family's pieces really are consecutive - the arithmetic depends on it")
check(all(sorted(byfam[f])[0] == int(ffirst[f]) for f in byfam),
      'first is the lowest piece id in the family')
check(all(sorted(byfam[f])[-1] == int(flast[f]) for f in byfam),
      'last is the highest')

# ============================================================================ 52
print('52. flatpacks: 84 items on 15 shared models, and the enum that joins them')
FLATOBJ = read('scripts/skill_construction/configs/poh_flatpacks.obj')
import json as _json
_spec = _json.load(open(os.path.join(C, 'tools/furnspec.json')))
flatkeys = [f['key'] for f in _spec['families'] if f.get('flatpack')]
check(len(flatkeys) == 15, '15 families are marked flatpackable (%d)' % len(flatkeys))

flatblocks = re.findall(r'^\[(poh_flat_\w+)\]', FLATOBJ, re.M)
check(len(flatblocks) == len(set(flatblocks)), 'no flatpack obj is declared twice')
missing = [n for n in flatblocks if n not in OBJS]
check(not missing, 'every flatpack obj is registered in obj.pack: %s' % missing[:4])

# the enum is the join, and it must name exactly the blocks in the .obj - no more, no fewer
flatenum = enumtable(FURNE, 'poh_furn_flat')
check(sorted(flatenum.values()) == sorted(flatblocks),
      'poh_furn_flat names exactly the %d objs in poh_flatpacks.obj' % len(flatblocks))
check('default=null' in FURNE.split('[poh_furn_flat]', 1)[1].split('\n[', 1)[0],
      'poh_furn_flat declares default=null - a namedobj enum answers obj 0 without it')

# every piece of a flatpackable family has one, and no piece of any other family does
ffam2 = enumtable(FURNE, 'poh_furn_fam')
famname = enumtable(FURNE, 'poh_fam_name')
famnum = {v: int(k) for k, v in famname.items()}
speclabel = {f['key']: f['label'] for f in _spec['families']}
want = {famnum[speclabel[k]] for k in flatkeys if speclabel[k] in famnum}
should = {int(i) for i, f in ffam2.items() if int(f) in want}
check(set(int(i) for i in flatenum) == should,
      'exactly the %d pieces of those families have a flatpack (%d in the table)'
      % (len(should), len(flatenum)))

# the models: 15 files, all registered, all referenced
mdl = sorted(set(re.findall(r'^model=(obj_poh_flat_\w+)', FLATOBJ, re.M)))
check(len(mdl) == 15, '15 distinct models carry them (%d)' % len(mdl))
check(all(m in MODELS for m in mdl), 'every one is in model.pack')
check(all(os.path.exists(os.path.join(C, 'models/obj', m + '.ob2')) for m in mdl),
      'and every one has an .ob2 on disk')

# the workbench is not itself flatpackable, and the Work-at triggers exist for all five tiers
check('workbench' not in flatkeys, 'a workbench cannot be flatpacked')
FLATRS = read('scripts/skill_construction/scripts/poh_flatpacks.rs2')
POHLOC = read('scripts/skill_construction/configs/poh.loc')
for loc in ('loc_13704', 'loc_13705', 'loc_13706', 'loc_13707', 'loc_13708'):
    blk = POHLOC.split('[%s]' % loc, 1)[1].split('\n[', 1)[0]
    check('op1=Work-at' in blk, '%s carries op1=Work-at' % loc)
    check('[oploc1,%s]' % loc in FLATRS, '%s has an oploc1 - a trigger on an op that is not there never fires' % loc)

# ============================================================================ 53
print('53. redecorating: six styles, six template levels, and prices that are OSRS\'s')
STYLEE = read('scripts/skill_construction/configs/poh_styles.enum')
stab = enumtable(STYLEE, 'poh_style_name')
slvl = enumtable(STYLEE, 'poh_style_level')
scost = enumtable(STYLEE, 'poh_style_cost')
check(sorted(stab) == list(range(6)), 'poh_style_name covers 0-5 with no gaps')
check(sorted(slvl) == list(range(6)), 'poh_style_level covers 0-5')
check(sorted(scost) == list(range(6)), 'poh_style_cost covers 0-5')
# A miss on any of these is a real answer without default=: style 0 is Basic wood, level 0 reads as
# "no requirement" and cost 0 reads as free. That is rule 17's lesson in a table it does not cover.
for t in ('poh_style_name', 'poh_style_level', 'poh_style_cost'):
    blk = STYLEE.split('[%s]' % t, 1)[1].split('\n[', 1)[0]
    check('default=null' in blk, '%s declares default=null - a miss must not answer style 0' % t)
lv = [int(slvl[i]) for i in range(6)]
cs = [int(scost[i]) for i in range(6)]
check(lv == sorted(lv) and cs == sorted(cs), 'the ladder only ever goes up: %s at %s' % (lv, cs))
check(lv == [1, 10, 20, 30, 40, 50], "the levels are OSRS's own: %s" % lv)
check(cs == [5000, 5000, 7500, 10000, 15000, 25000], "and so are the prices: %s" % cs)

# ~poh_style_origin has to answer a DIFFERENT template square/level for each of the six, or two
# styles are the same house and one of the prices buys nothing.
POHRS = read('scripts/skill_construction/scripts/poh.rs2')
org = POHRS.split('[proc,poh_style_origin]', 1)[1].split('\n[', 1)[0]
cases = re.findall(r'case (\d+|default) : return\(([^;]+)\);', org)
check(len(cases) == 6, '~poh_style_origin answers all six styles (%d cases)' % len(cases))
check(len({c[1].strip() for c in cases}) == 6,
      'each style is cut from a different square and level: %d distinct origins' % len({c[1].strip() for c in cases}))
check('^poh_templates_a' in org and '^poh_templates_b' in org, 'both template squares are used')

# the dialogue: every style reachable, the charge taken once, and the level tested before the coins
PORTRS = read('scripts/skill_construction/scripts/poh_portal.rs2')
pick = PORTRS.split('[proc,poh_style_pick]', 1)[1].split('\n[', 1)[0]
named = {int(m) for m in re.findall(r'poh_style_name, (\d)\)', pick)}
check(named == set(range(6)), 'the two menu pages between them offer all six styles: %s' % sorted(named))
check('while (true)' not in pick, 'the pager is a bounded loop - while (true) has no precedent here')
do = PORTRS.split('[proc,poh_redecorate_to]', 1)[1].split('\n[', 1)[0]
check(before(do, 'stat(construction)', 'inv_del'),
      'redecorating tests the level before it takes the coins')
check(do.count('inv_del(inv, coins') == 1, 'the coins come out exactly once')
check(do.count('inv_total(inv, coins)') == 2,
      'the purse is re-checked AFTER the confirm box - it is a suspend, and coins can leave during it')
check(do.index('%poh_style = $style') > do.index('inv_del'), 'and the style only changes once it is paid for')
check('$style = %poh_style' in do, 'buying the style you already have is refused')

# ============================================================================ 54
print('54. relocating: six towns, one of them yours, and five that say so')
lname = enumtable(LOCENUM, 'poh_loc_name')
llvl = enumtable(LOCENUM, 'poh_loc_level')
lcost = enumtable(LOCENUM, 'poh_loc_cost')
check(sorted(lname) == list(range(6)), 'poh_loc_name covers 0-5')
for t in ('poh_loc_name', 'poh_loc_level', 'poh_loc_cost', 'poh_loc_exit', 'poh_loc_portal'):
    blk = LOCENUM.split('[%s]' % t, 1)[1].split('\n[', 1)[0]
    check('default=null' in blk, '%s declares default=null - a miss must not answer town 0' % t)
lv = [int(llvl[i]) for i in range(6)]
cs = [int(lcost[i]) for i in range(6)]
check(lv == [1, 10, 20, 30, 40, 50], "the levels are OSRS's own: %s" % lv)
check(cs == [5000, 5000, 7500, 10000, 15000, 25000], "and so are the prices: %s" % cs)
check(lname[0] == 'Rimmington', 'town 0 is Rimmington - a save written before %poh_location existed reads 0')

# the varp has to be perm and registered, or every house moves back on logout
VARPF = read('scripts/skill_construction/configs/construction.varp')
vblk = VARPF.split('[poh_location]', 1)[1].split('\n[', 1)[0]
check('scope=perm' in vblk, '%poh_location is scope=perm')
check(before(VARPF, '[poh_location]', '// ---- furniture'),
      'and it sits ABOVE the furniture marker - genfurn.py truncates the file there')
check('poh_location' in {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l},
      'it is registered in varp.pack')

# the click: five portals that are not yours must not open your house
PORTRS2 = read('scripts/skill_construction/scripts/poh_portal.rs2')
clk = PORTRS2.split('[proc,poh_portal_click]', 1)[1].split('\n[', 1)[0]
check('loc_coord' in clk and 'poh_loc_portal' in clk,
      'the click compares loc_coord against poh_loc_portal')
check(before(clk, 'mes(', '~poh_enter'),
      'and refuses before it enters, rather than entering and then complaining')
check('[oploc1,poh_house_portal]' in PORTRS2 and '~poh_enter' not in
      PORTRS2.split('[oploc1,poh_house_portal]', 1)[1].split('\n\n', 1)[0],
      'the trigger goes through the check, not straight to ~poh_enter')

# the move itself
mv = PORTRS2.split('[proc,poh_relocate_to]', 1)[1].split('\n[', 1)[0]
check(before(mv, 'stat(construction)', 'inv_del'),
      'and moving house tests the level before it takes the coins')
check(mv.count('inv_del(inv, coins') == 1, 'the coins come out exactly once')
check(mv.count('inv_total(inv, coins)') == 2, 'the purse is re-checked after the confirm box')
check(before(mv, '~poh_free', '%poh_location = $town'),
      'the instance is freed BEFORE the move - someone standing in their house would come out the wrong door')
check('$town = %poh_location' in mv, 'moving to where you already are is refused')
pick = PORTRS2.split('[proc,poh_location_pick]', 1)[1].split('\n[', 1)[0]
named = {int(m) for m in re.findall(r'poh_loc_name, (\d)\)', pick)}
check(named == set(range(6)), 'the two menu pages between them offer all six towns: %s' % sorted(named))

# leaving has to follow the house, and the fallback has to be a real place
POHRS2 = read('scripts/skill_construction/scripts/poh.rs2')
check('p_telejump(^poh_exit)' not in POHRS2, 'nothing teleports to the hardcoded Rimmington exit any more')
ec = POHRS2.split('[proc,poh_exit_coord]', 1)[1].split('\n[', 1)[0]
check('poh_loc_exit' in ec and '^poh_exit' in ec,
      'the exit reads the table and falls back to the constant if it answers null')
check(POHRS2.count('~poh_exit_coord') >= 2, 'both leaving and logging in use it')

# ============================================================================ 55
print('55. the costume chest, the wardrobe and the mounted glory')
COST = read('scripts/skill_construction/configs/poh_costume.enum')
citem = enumtable(COST, 'poh_costume_item')
csetn = enumtable(COST, 'poh_costume_set_name')
cfirst = enumtable(COST, 'poh_costume_set_first')
clast = enumtable(COST, 'poh_costume_set_last')
NITEM = int(re.search(r'^\^poh_costume_items\s*=\s*(\d+)', CONSTF, re.M).group(1))
NSET = int(re.search(r'^\^poh_costume_sets\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(sorted(citem) == list(range(NITEM)), 'poh_costume_item is 0..%d with no gaps' % (NITEM - 1))
check(sorted(csetn) == list(range(NSET)), 'poh_costume_set_name covers all %d sets' % NSET)
check(len(set(citem.values())) == NITEM, 'no item is listed twice')
check(all(o in OBJS for o in citem.values()), 'every one is in obj.pack: %s'
      % ([o for o in citem.values() if o not in OBJS][:3] or 'all %d' % NITEM))

# THE LIST IS DERIVED, AND THIS IS WHERE IT IS RE-DERIVED. Everything in the chest has to be a clue
# reward, and every clue reward that is a god/trimmed/gold/heraldic VARIANT has to be in the chest -
# otherwise a reward added to the tables later is quietly unstorable and nobody finds out.
rewards = set()
for f in sorted(os.listdir(os.path.join(C, 'scripts/minigames/game_trail/scripts'))):
    d = os.path.join(C, 'scripts/minigames/game_trail/scripts', f)
    if not os.path.isdir(d):
        continue
    for g in sorted(os.listdir(d)):
        if not g.endswith('_reward.rs2'):
            continue
        txt = '\n'.join(l.split('//')[0] for l in
                        open(os.path.join(d, g), newline='').read().replace('\r\n', '\n').split('\n'))
        rewards |= set(re.findall(r'inv_add\(trail_rewardinv,\s*([a-z0-9_]+)', txt))
check(len(rewards) > 100, 'the three clue reward tables were found and parsed (%d objs)' % len(rewards))
notreward = [o for o in citem.values() if o not in rewards]
check(not notreward, 'everything in the chest is a treasure trail reward: %s' % (notreward[:3] or 'all of them'))
variant = {o for o in rewards if re.search(r'_(trim|gold|guthix|saradomin|zamorak)$|heraldic', o)}
missing = sorted(variant - set(citem.values()))
check(not missing, 'and every god/trimmed/gold/heraldic reward is in it: %s' % (missing or 'all %d' % len(variant)))
# The other half of the rule, and the one that covers the seventeen costume pieces no name pattern
# can describe: a costume is something clues are the ONLY source of. If a shop stocks it, it is
# ordinary kit and the chest is not where it belongs - that is what keeps this from drifting into a
# second bank one plausible-looking item at a time.
stocked = set()
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for g in files:
        if not g.endswith('.inv'):
            continue
        for line in open(os.path.join(root, g), newline='').read().replace('\r\n', '\n').split('\n'):
            m = re.match(r'^stock\d*=([a-z0-9_]+)', line.strip())
            if m:
                stocked.add(m.group(1))
check(len(stocked) > 500, 'the shop stock lists were found (%d objs)' % len(stocked))
sold = sorted(o for o in citem.values() if o in stocked)
check(not sold, 'and nothing in the chest is something a shop sells: %s' % (sold[:3] or 'none of the %d' % NITEM))

# the set windows have to tile the item list exactly, or a set silently holds the wrong pieces
spans = [(int(cfirst[i]), int(clast[i])) for i in range(NSET)]
check(spans[0][0] == 0, 'the first set starts at item 0')
check(spans[-1][1] == NITEM - 1, 'the last set ends at item %d' % (NITEM - 1))
check(all(a <= b for a, b in spans), 'no set ends before it starts')
check(all(spans[i + 1][0] == spans[i][1] + 1 for i in range(NSET - 1)),
      'the sets are consecutive and leave no item out: %s' % spans[:3])

INV = read('scripts/skill_construction/configs/poh_costume.inv')
blk = INV.split('[poh_costume_store]', 1)[1]
check('scope=perm' in blk, 'poh_costume_store is scope=perm - the whole point is that it survives logout')
check('size=%d' % NITEM in blk, 'and it has exactly one slot per item (size=%d)' % NITEM)
check('poh_costume_store' in {l.split('=', 1)[1] for l in read('pack/inv.pack').split('\n') if '=' in l},
      'it is registered in inv.pack')
ccap = enumtable(COST, 'poh_costume_cap')
caps = [int(ccap[t]) for t in sorted(ccap)]
check(sorted(ccap) == [1, 2, 3, 4], 'every chest tier has a capacity')
check(caps == sorted(caps) and caps[-1] == NITEM,
      'the capacities only go up and the best chest holds the lot: %s' % caps)

COSTRS = read('scripts/skill_construction/scripts/poh_costume.rs2')
# comments stripped: both these files TALK about the things they must not contain
COSTCODE = '\n'.join(l.split('//')[0] for l in COSTRS.split('\n'))
check('while (true)' not in COSTCODE, 'the set pager is a bounded loop')
st = COSTRS.split('[proc,poh_costume_store]', 1)[1].split('\n[', 1)[0]
check('inv_total(poh_costume_store, $item) = 0' in st,
      'storing puts ONE of each in - a second gold-trimmed platebody is not part of a costume')
check('$held < $cap' in st, 'and it stops at the capacity of the chest that was clicked')
wd = COSTRS.split('[proc,poh_costume_withdraw]', 1)[1].split('\n[', 1)[0]
check('inv_freespace(inv) > 0' in wd, 'withdrawing checks for room and leaves the rest in the chest')

# the wardrobe, and the tutorial handler it has to share
WARD = COSTRS.split('[proc,poh_wardrobe]', 1)[1].split('\n[', 1)[0]
check('allowdesign(true)' in WARD and 'if_openmain(player_kit)' in WARD,
      'the wardrobe opens the character-design screen')
TUT = read('scripts/tutorial/scripts/tutorial.rs2')
q = TUT.split('[queue,tutorial_designed_character]', 1)[1].split('\n[', 1)[0]
check('if (%tutorial = ^newbie_basics_instructor_start)' in q,
      'the shared close handler only advances a player who is still IN the tutorial - a wardrobe '
      'must not reset a finished one')
check('allowdesign(false)' in q and q.index('allowdesign(false)') > q.index('}'),
      'and it always turns allowdesign back off, guarded or not')
TUTCODE = '\n'.join(l.split('//')[0] for l in TUT.split('\n'))
check(TUTCODE.count('[if_close,player_kit]') == 1,
      'there is exactly one close handler in the repo - two is a build error')

# the mounted glory
GLORY = read('scripts/skill_construction/scripts/poh_glory.rs2')
check('[oploc1,poh_trophy_amuletofglory_4]' in GLORY, 'the glory trigger is on the amulet trophy')
TROPHY = blocks(read('scripts/skill_construction/configs/poh.loc'))
check((TROPHY.get('poh_trophy_amuletofglory_4', {}).get('op1') or [''])[0] == 'Rub',
      'which is the only one of the three trophies that carries op1=Rub')
for n in ('poh_trophy_antidragonbreath_4', 'poh_trophy_legendscape_4'):
    check(not (TROPHY.get(n, {}).get('op1') or []), '%s really has no op1' % n)
for n in ('poh_trophy_antidragonbreath_4', 'poh_trophy_legendscape_4'):
    check(n not in GLORY, '%s has no op1, so it gets no trigger' % n)
check('~poh_free' in GLORY, 'and the instance is freed on the way out, or it holds a slot until logout')
AOG = read('scripts/general/scripts/enchanted_jewellry/amulet_of_glory.rs2')
check('[proc,glory_teleport]' in AOG, 'the choice and the teleport are a proc now')
AOGCODE = '\n'.join(l.split('//')[0] for l in AOG.split('\n'))
lab = AOGCODE.split('[label,amulet_of_glory_interface]', 1)[1].split('\n[', 1)[0]
tel = AOGCODE.split('[proc,glory_teleport]', 1)[1].split('\n[', 1)[0]
check('inv_setslot' in lab and 'inv_setslot' not in tel,
      'the charge is eaten by the LABEL - a loc trigger has no last_slot worth writing to')

# ============================================================================ 56
print('56. every op a piece of house furniture advertises is answered by something')
# THE POINT OF THE LAST ROUND. A trigger on an op a loc does not carry never fires, which check 39
# has covered since the furniture round - this is the other direction, and it is the one that was
# never checked: an op the loc DOES carry with no trigger anywhere is a click that does nothing,
# and a click that does nothing is indistinguishable from a bug.
#
# Not every op has to be an activity. Several of these answer "you need someone else in the house"
# or "those items do not exist in this world yet" - which is the honest answer and still an answer.
GAMES = read('scripts/skill_construction/scripts/poh_games.rs2')
LOCCFG2 = blocks(read('scripts/skill_construction/configs/poh.loc'))
TEMPL2 = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
OPFILES = [read('scripts/skill_construction/scripts/poh_furn_ops.rs2'), GAMES,
           read('scripts/skill_construction/scripts/poh_costume.rs2'),
           read('scripts/skill_construction/scripts/poh_glory.rs2'),
           read('scripts/skill_construction/scripts/poh_flatpacks.rs2'),
           read('scripts/skill_construction/scripts/poh_furniture.rs2'),
           read('scripts/skill_construction/scripts/poh_tablets.rs2'),
           read('scripts/skill_construction/scripts/poh_build.rs2'),
           read('scripts/skill_construction/scripts/poh_portal.rs2'),
           read('scripts/skill_construction/scripts/poh_portal_chamber.rs2'),
           read('scripts/skill_construction/scripts/poh_combat_ring.rs2'),
           read('scripts/skill_construction/scripts/poh_combat.rs2')]
TRIG = set()
for t in OPFILES:
    TRIG |= set(re.findall(r'^\[oploc([1-5]),(\w+)\]', t, re.M))

# only the locs the furniture actually places - poh.loc also holds hotspots and scenery
FAM = _json.load(open(os.path.join(C, 'tools/furnspec.json')))['families']
# the spec carries a family's pieces either as a flat "locs" list or as "pieces" objects
placed = sorted({l for f in FAM for l in
                 (f.get('locs') or [p['loc'] for p in f.get('pieces', [])])})
check(len(placed) > 200, 'the spec places %d locs' % len(placed))
dead = []
for l in placed:
    cfg = LOCCFG2.get(l) or TEMPL2.get(l) or {}
    for k in cfg:
        m = re.match(r'^op([1-5])$', k)
        # "hidden" is the cache's own word for an option slot that carries no menu entry. There is
        # nothing to click, so there is nothing to answer.
        if m and cfg[k][0] != 'hidden' and (m.group(1), l) not in TRIG:
            dead.append('%s %s=%s' % (l, k, cfg[k][0]))
check(not dead, 'no op on a placed piece is a dead click: %s' % (dead[:6] or 'all %d answered' % len(TRIG)))

# the two that are real activities
check(len(re.findall(r'^\[oploc1,poh_archery_target', GAMES, re.M)) == 2, 'both archery targets shoot')
check(len(re.findall(r'^\[oploc1,poh_dartboard', GAMES, re.M)) == 2, 'both dartboards throw')
shoot = GAMES.split('[proc,poh_range_shoot]', 1)[1].split('\n[', 1)[0]
check(before(shoot, 'inv_del', 'random(100)'),
      'the ammunition is spent before the roll - a miss has to cost something')
check(shoot.count('stat_advance(ranged') == 2, 'and the experience is only paid on a hit or a bullseye')
arch = GAMES.split('[proc,poh_archery]', 1)[1].split('\n[', 1)[0]
check('attackrange' in arch, 'the target asks for a bow by attackrange, not by a list of bows')

AMMO = read('scripts/skill_construction/configs/poh_games.enum')
ammo = enumtable(AMMO, 'poh_range_ammo')
fx = enumtable(AMMO, 'poh_range_fx')
check(sorted(ammo) == sorted(fx), 'every piece of ammunition has a launch effect')
check(all(o in OBJS for o in ammo.values()), 'every one is in obj.pack')
SPOT = set(packmap('pack/spotanim.pack'))
check(all(v in SPOT for v in fx.values()), 'every launch effect is in spotanim.pack: %s'
      % ([v for v in fx.values() if v not in SPOT][:3] or 'all %d' % len(fx)))
# and it is the RIGHT one. Every launch spotanim in the cache is its ammunition's name with _launch
# on the end, so the two tables can be checked against each other rather than just for existence -
# without this, a dart that launches an arrow passes everything.
wrongfx = sorted(ammo[i] for i in ammo if fx.get(i) != ammo[i] + '_launch')
check(not wrongfx, 'and it is the effect for that ammunition: %s' % (wrongfx[:3] or 'all %d match' % len(fx)))
AF = int(re.search(r'^\^poh_arrow_first\s*=\s*(\d+)', CONSTF, re.M).group(1))
AL = int(re.search(r'^\^poh_arrow_last\s*=\s*(\d+)', CONSTF, re.M).group(1))
DF = int(re.search(r'^\^poh_dart_first\s*=\s*(\d+)', CONSTF, re.M).group(1))
DL = int(re.search(r'^\^poh_dart_last\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(AL + 1 == DF and DL == max(ammo), 'the arrow and dart ranges tile the table with no gap')
check(all(ammo[i].endswith('_arrow') for i in range(AF, AL + 1)), 'the arrow range really is arrows')
check(all(ammo[i].endswith('_dart') for i in range(DF, DL + 1)), 'and the dart range really is darts')

# every one of these is inside somebody's house
#
# poh_needs_company IS NOT ONE OF THE OWN-HOUSE ONES, and was not meant to be from the day guests
# could use the owner's furniture (f3fb1661). Everything else here writes to the house, so it is
# the owner's; this one only says why a games room game cannot be played, which is as true for a
# guest as for the owner - and telling a guest "You can only use that in your own house" when they
# click the hangman chest would be a worse answer than the one they came for. So it takes
# ~poh_in_house(loc_coord), the read-only test, and the check is for a house test rather than for
# that house test. Still a check: without one the op fires on the loc outside any instance.
HOUSE_GUARD = {'poh_needs_company': '~poh_in_house(loc_coord)'}
for proc in ('poh_archery', 'poh_darts', 'poh_lever_pull', 'poh_needs_company', 'poh_no_parts',
             'poh_prize_chest'):
    body = GAMES.split('[proc,%s]' % proc, 1)[1].split('\n[', 1)[0]
    guard = HOUSE_GUARD.get(proc, '~poh_in_own_house')
    check(guard in body, '%s checks you are in %s' % (proc, 'a house' if proc in HOUSE_GUARD else 'your own house'))

# ============================================================================ 57
print('57. the windows resolve, in all six styles')
# THE BUG THIS EARNED. poh_dynamic_window shipped as a single loc whose model is a wall with a
# window-shaped HOLE in it and whose desc read "This should have resolved!". There are 116 of them
# per style in the templates, so every house had 116 holes in its walls.
#
# A multiloc shell with no entry at the current value renders nothing and carries no ops, so the
# table has to be COMPLETE - all 6 styles times 9 kinds - and each child has to be the window for
# the style its index claims, or a stone house grows wooden windows.
WSTYLE = ['rimmington', 'lumbridge', 'pollnivneach', 'rellekka', 'brimhaven', 'yanille']
WKIND = ['shutters', 'bob', 'saradomin', 'guthix', 'zamorak',
         'bob2', 'saradomin2', 'guthix2', 'zamorak2']
NKIND = int(re.search(r'^\^poh_window_kinds\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(NKIND == len(WKIND), '^poh_window_kinds is %d' % NKIND)
wblk = read('scripts/skill_construction/configs/poh.loc').split('[poh_dynamic_window]', 1)[1].split('\n[', 1)[0]
check('multivar=poh_window_state' in wblk, 'it is a multiloc over poh_window_state')
kids = {int(m.group(1)): m.group(2) for m in re.finditer(r'^multiloc=(\d+),(\w+)$', wblk, re.M)}
check(sorted(kids) == list(range(6 * NKIND)),
      'all %d states are listed with no gap (%d found)' % (6 * NKIND, len(kids)))
wrong = [(i, kids[i], 'poh_%s_window_%s' % (WSTYLE[i // NKIND], WKIND[i % NKIND]))
         for i in sorted(kids) if kids[i] != 'poh_%s_window_%s' % (WSTYLE[i // NKIND], WKIND[i % NKIND])]
check(not wrong, 'each child is the window for its own style and kind: %s' % (wrong[:2] or 'all %d' % len(kids)))
check(all(k in LOCS for k in kids.values()), 'every child is in loc.pack: %s'
      % ([k for k in kids.values() if k not in LOCS][:3] or 'all of them'))
check('This should have resolved' not in wblk, 'and the placeholder description is gone')

# the varp, the varbit, and the one proc that writes them
VB = read('scripts/skill_construction/configs/construction.varbit').split('[poh_window_state]', 1)[1]
check('basevar=poh_window' in VB, 'poh_window_state reads %poh_window')
bits = (int(re.search(r'endbit=(\d+)', VB).group(1)) - int(re.search(r'startbit=(\d+)', VB).group(1)) + 1)
check(2 ** bits > 6 * NKIND - 1, 'and it is %d bits, enough for %d states' % (bits, 6 * NKIND))
check('poh_window' in {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l},
      '%poh_window is in varp.pack')
check('poh_window_state' in {l.split('=', 1)[1] for l in read('pack/varbit.pack').split('\n') if '=' in l},
      'poh_window_state is in varbit.pack')
vwin = read('scripts/skill_construction/configs/construction.varp').split('[poh_window]', 1)[1].split('\n[', 1)[0]
check('scope=perm' in vwin, 'and it is perm - a house does not reglaze itself on logout')
POHRS3 = read('scripts/skill_construction/scripts/poh.rs2')
ref = POHRS3.split('[proc,poh_window_refresh]', 1)[1].split('\n[', 1)[0]
check('%poh_style * ^poh_window_kinds' in ref, 'the refresh is style * kinds + choice')
writers = [f for f in ('scripts/skill_construction/scripts/poh.rs2',
                       'scripts/skill_construction/scripts/poh_portal.rs2',
                       'scripts/skill_construction/scripts/poh_test.rs2',
                       'scripts/skill_construction/scripts/poh_menus.rs2',
                       'scripts/skill_construction/scripts/poh_furniture.rs2')
           if '%poh_window =' in read(f)]
check(writers == ['scripts/skill_construction/scripts/poh.rs2'],
      'and it is the ONLY thing that writes %%poh_window: %s' % writers)
for f, why in (('scripts/skill_construction/scripts/poh_portal.rs2', 'redecorating'),
               ('scripts/skill_construction/scripts/poh.rs2', 'buying a house'),
               ('scripts/skill_construction/scripts/poh_test.rs2', '::~pohstyle')):
    check('~poh_window_refresh' in read(f), '%s calls it - the windows are part of the style' % why)

# the sit, which was playing beside the chair rather than on it
SIT = read('scripts/skill_construction/scripts/poh_furn_ops.rs2').split('[proc,poh_furn_sit]', 1)[1].split('\n[', 1)[0]
check('p_walk($seat)' in SIT, 'sitting walks onto the chair - an oploc1 click only gets you adjacent')
check('facesquare' in SIT, 'and turns to face the way the chair faces')
check(before(SIT, 'p_walk', 'anim('), 'before the pose plays, not after')
check(len(re.findall(r'~poh_furn_sit\(', read('scripts/skill_construction/scripts/poh_furn_ops.rs2'))) == 24,
      'all 24 seats go through it')


print('58. the portal chamber: three portals, seven destinations, and where they lead')
PC = read('scripts/skill_construction/scripts/poh_portal_chamber.rs2')
DESTS = ['varrock', 'lumbridge', 'falador', 'camelot', 'ardougne', 'yanille', 'trollheim']

# The four tables. EVERY ONE needs a default, because 0 - undirected - is a value all of them are
# genuinely read with: it is what a frame nobody has pointed anywhere holds, and what every save
# written before %poh_portals existed reads. An enum with no default returns 0 on a miss, and
# coord 0 is a real tile in the far south-west of the map.
DENUM = {}
for b in re.split(r'\n(?=\[)', read('scripts/skill_construction/configs/poh_portal_dest.enum')):
    m = re.match(r'\[(\w+)\]', b)
    if not m:
        continue
    d = {'val': {}}
    for l in b.split('\n')[1:]:
        if l.startswith('val='):
            k, v = l[4:].split(',', 1)
            d['val'][int(k)] = v
        elif '=' in l:
            k, v = l.split('=', 1)
            d.setdefault(k, v)
    DENUM[m.group(1)] = d
for t in ('poh_portal_name', 'poh_portal_level', 'poh_portal_coord', 'poh_portal_cost'):
    check(t in DENUM, '%s exists' % t)
    check(DENUM.get(t, {}).get('default') is not None,
          '%s has a default - 0 is a value it is really read with' % t)
    check(sorted(DENUM.get(t, {}).get('val', {})) == list(range(1, 8)),
          '%s covers all seven destinations with no gap' % t)

# the constants are 1..7 and the three portal indices are 0..2, because both index bit ranges
for n, d in enumerate(DESTS, start=1):
    check(const('poh_portal_' + d) == n, '^poh_portal_%s is %d' % (d, n))
check([const('poh_portal_' + k) for k in ('north', 'east', 'west')] == [0, 1, 2],
      'the three portal spaces are 0, 1, 2 - they index %poh_portals three bits at a time')

# THE CHECK THAT MATTERS: the level and the coord are the matching teleport spell's own, not new
# numbers. A portal is that spell made permanent, so if the two ever disagree the portal is either
# easier than the spell or lands somewhere the spell does not.
SPELLS = {}
cur = None
for l in read('scripts/skill_magic/configs/magic_spells.dbrow').split('\n'):
    l = l.strip()
    m = re.match(r'^\[magic_spell_teleport_(\w+)\]$', l)
    if m:
        cur = m.group(1); SPELLS[cur] = {}
    elif cur and l.startswith('data='):
        k, v = l[5:].split(',', 1)
        SPELLS[cur].setdefault(k, v)
SPELLNAME = {'yanille': 'watchtower'}
bad = []
for n, d in enumerate(DESTS, start=1):
    sp = SPELLS.get(SPELLNAME.get(d, d), {})
    if sp.get('levelrequired') != DENUM['poh_portal_level']['val'].get(n):
        bad.append((d, 'level', sp.get('levelrequired'), DENUM['poh_portal_level']['val'].get(n)))
    if sp.get('tele_coord') != DENUM['poh_portal_coord']['val'].get(n):
        bad.append((d, 'coord', sp.get('tele_coord'), DENUM['poh_portal_coord']['val'].get(n)))
check(not bad, 'every level and landing coord is its own teleport spell\'s: %s'
      % (bad[:3] or 'all seven, both columns'))

# ~poh_portal_loc is 3 tiers x 8 states with no gap, and - the check worth having - each case
# returns the loc for the destination its index claims. A table that merely EXISTS would let a
# marble portal to Camelot come up as the teak one to Falador and nothing would notice.
LOCCASE = {int(a): b for a, b in re.findall(r'^    case (\d+) : return\((\w+)\);', PC, re.M)}
check(sorted(LOCCASE) == list(range(8, 32)),
      'the loc table is three tiers of eight with no gap: %d cases' % len(LOCCASE))
TIERWORD = {1: 'teak', 2: 'mag', 3: 'marble'}
bad = []
for tier in (1, 2, 3):
    for dest in range(8):
        loc = LOCCASE.get(tier * 8 + dest)
        if loc is None:
            continue
        want = 'empty' if dest == 0 else DESTS[dest - 1]
        # Trollheim's three came into the cache under fairy-ring names; their display name is what
        # says which they are, so that is what is checked rather than the symbol
        if want == 'trollheim':
            ok = (POHLOC2.get(loc, {}).get('name') or [''])[0] == 'Trollheim Portal'
        else:
            ok = loc.startswith('poh_portal_%s_' % TIERWORD[tier]) and loc.endswith('_' + want)
        if not ok:
            bad.append((tier, want, loc))
check(not bad, 'and every one is its own tier\'s loc for its own destination: %s'
      % (bad[:3] or '24 checked'))

# the three offsets from the focus are the template's own, not remembered
SPOTS = {}
for sq, zone in (('m29_79', 12),):
    sec = None
    for l in read('maps/%s.jm2' % sq).split('\n'):
        if l.startswith('===='):
            sec = l.strip('= '); continue
        if sec != 'LOC' or ':' not in l:
            continue
        head, rest = l.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        nm = {v: k for k, v in LOCS.items()}.get(int(rest.split()[0]))
        if lv == 0 and (x // 8) * 8 + (z // 8) == zone and nm in TEMPL2:
            got = (TEMPL2[nm].get('name') or [''])[0]
            if got in ('Portal space', 'Centrepiece space'):
                SPOTS.setdefault(got, []).append((x % 8, z % 8))
check(sorted(SPOTS.get('Portal space', [])) == [(0, 3), (3, 7), (7, 3)],
      'the three Portal spaces are where ~poh_portal_spot thinks: %s' % sorted(SPOTS.get('Portal space', [])))
check(SPOTS.get('Centrepiece space') == [(3, 3)],
      'and the focus is at (3,3), which is what the offsets are measured from: %s' % SPOTS.get('Centrepiece space'))
for want, expr in ((0, 3), (3, 7), (7, 3)) and [((0, 3), 'movecoord($focus, -3, 0, 0)'),
                                               ((3, 7), 'movecoord($focus, 0, 0, 4)'),
                                               ((7, 3), 'movecoord($focus, 4, 0, 0)')]:
    check(expr in PC, '%s is reached as %s' % (want, expr))

# the runes are checked and taken in the same amounts. Taking more than was checked is a silent
# theft; taking less is a free portal.
def runes(proc, pat):
    body = PC.split('[proc,%s]' % proc, 1)[1].split('\n[', 1)[0]
    out, cur = {}, None
    for l in body.split('\n'):
        m = re.match(r'\s*case \^poh_portal_(\w+) :', l)
        if m:
            cur = m.group(1); out[cur] = []
        for r, n in re.findall(pat, l):
            if cur:
                out[cur].append((r, int(n)))
    return {k: sorted(v) for k, v in out.items()}
have = runes('poh_portal_runes_have', r'inv_total\(inv, (\w+)\) >= (\d+)')
take = runes('poh_portal_runes_take', r'inv_del\(inv, (\w+), (\d+)\)')
check(sorted(have) == sorted(DESTS) and have == take,
      'every destination checks exactly the runes it takes: %s'
      % ([d for d in set(have) | set(take) if have.get(d) != take.get(d)] or 'all seven agree'))
# and the printed cost says the same thing the code does
bad = []
for n, d in enumerate(DESTS, start=1):
    txt = DENUM['poh_portal_cost']['val'].get(n, '')
    for rune, qty in have.get(d, []):
        if '%d %s' % (qty, rune.replace('rune', '')) not in txt:
            bad.append((d, rune, qty, txt))
check(not bad, 'and the message names the same runes and amounts: %s' % (bad[:3] or 'all seven'))

# %poh_portals is written in one place, the way %poh_window is
writers = [f for f in ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
                       'scripts/skill_construction/scripts/poh.rs2',
                       'scripts/skill_construction/scripts/poh_furniture.rs2',
                       'scripts/skill_construction/scripts/poh_portal.rs2')
           if '%poh_portals =' in read(f)]
check(writers == ['scripts/skill_construction/scripts/poh_portal_chamber.rs2'],
      'only ~poh_portal_set writes %%poh_portals: %s' % writers)
check(len(re.findall(r'%poh_portals = ', PC)) == 1, 'and it writes it once')
check('scope=perm' in read('scripts/skill_construction/configs/construction.varp')
      .split('[poh_portals]', 1)[1].split('[', 1)[0],
      '%poh_portals is perm - a directed portal has to still be directed next login')

# every directed portal can be taken out again, and taking it out forgets where it led
ENTER = sorted(set(re.findall(r'^\[oploc1,(\w+)\] ~poh_portal_enter\(', PC, re.M)))
REMOVE = sorted(set(re.findall(r'^\[oploc5,(\w+)\] ~poh_portal_remove;', PC, re.M)))
check(len(ENTER) == 21, 'all 21 directed portals answer Enter: %d' % len(ENTER))
check(ENTER == REMOVE, 'and every one of them can be taken out again')
check('~poh_portal_set(~poh_portal_index($spot), 0)' in PC,
      'taking the last piece out of a Portal space forgets where it led')


print('59. the combat ring: 36 tiles under one piece, turned with the room')
CR = read('scripts/skill_construction/scripts/poh_combat_ring.rs2')
CB = read('scripts/skill_construction/scripts/poh_combat.rs2')

# It is generated, so the first thing to check is that it is in step with the templates it is
# generated from. Same shape as group 38: re-run in place, compare bytes, put the file back.
_before = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_combat_ring.rs2'), 'rb').read()
r = _sp.run([sys.executable, os.path.join(C, 'tools/gencombatring.py')],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/gencombatring.py runs clean'
      + ('' if r.returncode == 0 else ': ' + (r.stdout + r.stderr)[-400:]))
_after = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_combat_ring.rs2'), 'rb').read()
if _after != _before:
    open(os.path.join(C, 'scripts/skill_construction/scripts/poh_combat_ring.rs2'), 'wb').write(_before)
check(_after == _before, 're-running it changes nothing: byte-identical'
      if _after == _before else 're-running it CHANGES the file - it is out of step with the templates')

# THE CHECK THAT MATTERS: every tile the ring lays is a tile the template really has a Combat ring
# space on, at that shape and that angle. A rope one square out, or a mat placed as a wall, is
# invisible to every other check here and obvious in game.
TEMPLATE_RING = set()
for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    sec = None
    for l in read('maps/%s.jm2' % _sq).split('\n'):
        if l.startswith('===='):
            sec = l.strip('= '); continue
        if sec != 'LOC' or ':' not in l:
            continue
        head, rest = l.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        pp = rest.split()
        nm = {v: k for k, v in LOCS.items()}.get(int(pp[0]))
        shape = int(pp[1]) if len(pp) > 1 else 10
        angle = int(pp[2]) if len(pp) > 2 else 0
        if lv in _levels and (x // 8) * 8 + (z // 8) == 28 \
                and (TEMPL2.get(nm, {}).get('name') or [''])[0] == 'Combat ring space':
            TEMPLATE_RING.add((x % 8, z % 8, shape, angle))
SHAPEOF = {'poh_ring_wall': 0, 'poh_ring_corner': 3, 'poh_ring_mat': 22}
laid = {}
for proc, x, z, angle, loc in re.findall(
        r'~(poh_ring_wall|poh_ring_corner|poh_ring_mat)\(\$base, \$rot, (-?\d+), (-?\d+), (\d+), (\w+)\);', CR):
    ring = CR[:CR.index('~%s($base, $rot, %s, %s, %s, %s);' % (proc, x, z, angle, loc))]
    ring = ring.rsplit('[proc,poh_ring_', 1)[1].split(']', 1)[0]
    laid.setdefault(ring, []).append((int(x), int(z), SHAPEOF[proc], int(angle), loc))
bad = [(k, t[:4]) for k, v in laid.items() for t in v if t[:4] not in TEMPLATE_RING]
check(not bad, 'every tile laid is a template tile, at its shape and its angle: %s'
      % (bad[:3] or '%d placements over %d rings' % (sum(len(v) for v in laid.values()), len(laid))))
for ring in ('boxing', 'fencing', 'combat'):
    tiles = [(t[0], t[1], t[2]) for t in laid.get(ring, [])]
    check(len(tiles) == 36 and len(set(tiles)) == 36,
          '%s covers 36 tiles, each once: %d' % (ring, len(tiles)))
check(len(laid.get('beam', [])) == 3, 'the balance beam is three tiles: %d' % len(laid.get('beam', [])))
check(len({t[1] for t in laid.get('beam', [])}) == 1,
      'and they are in one row, which is what a beam is')

# the rotation is the engine's, not something close to it (GameMap.rotateZoneX/Z + newAngle)
for want in ('case 1 : return(movecoord($base, $z, 0, calc(7 - $x)));',
             'case 2 : return(movecoord($base, calc(7 - $x), 0, calc(7 - $z)));',
             'case 3 : return(movecoord($base, calc(7 - $z), 0, $x));'):
    check(want in CR, 'the zone rotation matches the engine: %s' % want.split(':')[0].strip())
check('return(modulo(calc($angle + $rot), 4));' in CR, 'and so does the angle')

# the anchor has to be a tile nothing else can ever occupy, or the ring and a chair fight over a slot
# THE ANCHOR RULE, for every anchored family rather than just this one. An anchored piece takes
# one furniture slot per room, keyed by a fixed tile, so that tile must carry no hotspot in any
# room the family appears in - otherwise two pieces want the same slot and one of them silently
# cannot be built. It is checked here against the templates, not asserted.
_famroomhot = {}
for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    _sec = None
    for _l in read('maps/%s.jm2' % _sq).split('\n'):
        if _l.startswith('===='):
            _sec = _l.strip('= '); continue
        if _sec != 'LOC' or ':' not in _l:
            continue
        _h, _r = _l.split(':', 1)
        _lv, _x, _z = (int(v) for v in _h.split())
        _n = {v: k for k, v in LOCS.items()}.get(int(_r.split()[0]))
        if _lv in _levels and (TEMPL2.get(_n, {}).get('category') or [''])[0] == 'poh_hotspot':
            _famroomhot.setdefault((_x // 8) * 8 + (_z // 8), set()).add((_x % 8, _z % 8))
anchored = [f for f in _spec['families'] if f.get('anchor')]
check(sorted(f['key'] for f in anchored)
      == ['chapelwindow', 'combat_ring', 'fence', 'hedge', 'rug', 'thronefloor'],
      'the anchored families are %s' % sorted(f['key'] for f in anchored))
_zoneof = {}
for _l in read('scripts/skill_construction/configs/poh_rooms.enum').split('\n'):
    pass
for _f in anchored:
    _zones = set()
    for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
        _sec = None
        for _l in read('maps/%s.jm2' % _sq).split('\n'):
            if _l.startswith('===='):
                _sec = _l.strip('= '); continue
            if _sec != 'LOC' or ':' not in _l:
                continue
            _h, _r = _l.split(':', 1)
            _lv, _x, _z = (int(v) for v in _h.split())
            if _lv in _levels and int(_r.split()[0]) in _f['hotspots']:
                _zones.add((_x // 8) * 8 + (_z // 8))
    _clash = [z for z in _zones if tuple(_f['anchor']) in _famroomhot.get(z, set())]
    check(not _clash,
          '%s anchors where no hotspot of its own stands: at %s, across %d rooms %s'
          % (_f['key'], tuple(_f['anchor']), len(_zones), _clash or 'clear'))
# An anchored family has the tile in TWO places: furnspec.json, where the click reads it, and a
# constant, where the removal proc reads it. If those two ever drift the piece is stored at one
# tile and looked for at another, and it simply cannot be taken out again - which nothing else
# here would notice, because both halves are internally consistent.
check(const('poh_rug_anchor') == 7 and next(f for f in _spec['families'] if f['key'] == 'rug')['anchor'] == [7, 7],
      '^poh_rug_anchor and the spec\'s anchor are the same tile: %d vs %s'
      % (const('poh_rug_anchor'), next(f for f in _spec['families'] if f['key'] == 'rug')['anchor']))
check('~poh_furn_at($rx, $rz, 0, 0)' in CR,
      'removal looks the slot up at the anchor, not under the tile that was clicked')

# every loc the ring can put down can be taken out again, and by the ring's own remover
RINGLOCS = sorted({t[4] for v in laid.values() for t in v})
rm = set(re.findall(r'^\[oploc5,(\w+)\] ~poh_combat_ring_remove;', CR, re.M))
rm |= set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_combat_ring_remove;', fu, re.M))
check(sorted(rm) == RINGLOCS, 'all %d ring locs are wired to ~poh_combat_ring_remove: %s'
      % (len(RINGLOCS), sorted(set(RINGLOCS) ^ rm) or 'every one'))
check(not (set(re.findall(r'^\[oploc5,(\w+)\] ~poh_combat_ring_remove;', CR, re.M))
           & set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_combat_ring_remove;', fu, re.M))),
      'and no loc is wired in both files - a trigger declared twice does not compile')

# the sixteen hotspots are the VISIBLE ones. Three of the nineteen are zero-length models: they
# render nothing and cannot be clicked, so wiring them would be wiring a click that cannot happen.
_fam = next(f for f in _spec['families'] if f['key'] == 'combat_ring')
check(len(_fam['hotspots']) == 16, 'the family takes the 16 visible hotspots: %d' % len(_fam['hotspots']))
_empty = 0
for _n, _d in TEMPL2.items():
    if (_d.get('name') or [''])[0] != 'Combat ring space':
        continue
    _m = (_d.get('model') or [''])[0].split(',')[0]
    _sz = [os.path.getsize(os.path.join(C, 'models/loc', _f)) for _f in os.listdir(os.path.join(C, 'models/loc'))
           if _f.startswith(_m + '_') and _f.endswith('.ob2')]
    if _sz and max(_sz) <= 32:
        _empty += 1
        check(LOCS[_n] not in _fam['hotspots'],
              '%s has an empty model and is not wired as a hotspot' % _n)
check(_empty == 3, 'three of the nineteen are empty models - beam and pedestal tiles: %d' % _empty)

# the cloth exists, is sold, and is what the rings are actually built out of
check('bolt_of_cloth' in {l.split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l},
      'bolt_of_cloth is in obj.pack')
# Off his counter, not out of his dialogue - COUNTER is group 26's reading of
# construction_supplies.inv. What this check is for is unchanged: the rings are built out of cloth,
# so cloth has to be buyable somewhere.
check('bolt_of_cloth' in COUNTER, 'and the sawmill operator sells it off his counter')
_mats = {p['loc']: p['mats'] for p in _fam['pieces']}
check(sum(1 for m in _mats.values() if any(x[0] == 'bolt_of_cloth' for x in m)) == 3,
      'three of the four ring types are built out of it')

# and the honest ops, which are the point of not leaving them dead
for _p in ('poh_ring_climb', 'poh_ring_beam_stand', 'poh_ring_beam_down'):
    check('[proc,%s]' % _p in CB, '%s is answered' % _p)
_stand = CB.split('[proc,poh_ring_beam_stand]', 1)[1].split('\n[', 1)[0]
check('p_walk(loc_coord)' in _stand and before(_stand, 'p_walk', 'anim('),
      'standing on the beam walks onto it before the pose plays, as the chairs do')


print('60. rugs, curtains and wall decoration - and the gold leaf they are made of')
RG = read('scripts/skill_construction/scripts/poh_rug.rs2')

# generated, so first: is it in step with the templates it came from
_before = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_rug.rs2'), 'rb').read()
r = _sp.run([sys.executable, os.path.join(C, 'tools/genrugs.py')], capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/genrugs.py runs clean'
      + ('' if r.returncode == 0 else ': ' + (r.stdout + r.stderr)[-400:]))
_after = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_rug.rs2'), 'rb').read()
if _after != _before:
    open(os.path.join(C, 'scripts/skill_construction/scripts/poh_rug.rs2'), 'wb').write(_before)
check(_after == _before, 're-running it changes nothing: byte-identical' if _after == _before
      else 're-running it CHANGES the file - it is out of step with the templates')

# the three hotspot ghosts, and the claim that tier one's pieces ARE them. That is what names
# corner, side and middle; without it the kinds are a guess and a rug comes up inside out.
def _geo(model):
    d = os.path.join(C, 'models/loc')
    fs = [f for f in os.listdir(d) if f.startswith(model + '_') and f.endswith('.ob2')]
    if not fs:
        return None
    b = open(os.path.join(d, sorted(fs)[0]), 'rb').read()
    return _struct.unpack_from('>HHB', b, len(b) - 18)[:2] if len(b) >= 18 else None
import struct as _struct
_hot = {n: _geo((d.get('model') or [''])[0].split(',')[0])
        for n, d in TEMPL2.items() if (d.get('name') or [''])[0] == 'Rug space'}
_kinds = {g for g in _hot.values() if g and g != (0, 0)}
check(len(_kinds) == 3, 'the rug hotspots come in three geometries: %s' % sorted(_kinds))
_t1 = [_geo((POHLOC2[l].get('model') or [''])[0].split(',')[0])
       for l in ('loc_13588', 'loc_13589', 'loc_13590')]
check(sorted(x for x in _t1 if x) == sorted(_kinds),
      'and the first tier IS those three models, vertex for vertex: %s' % _t1)
KG = dict(zip(('corner', 'side', 'middle'), _t1))

# every tile the rug lays is a template Rug space tile, at that tile's own angle, and the kind it
# is given is the kind the rectangle and the ghost both say
TEMPLATE_RUG = {}
for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    _sec = None
    for _l in read('maps/%s.jm2' % _sq).split('\n'):
        if _l.startswith('===='):
            _sec = _l.strip('= '); continue
        if _sec != 'LOC' or ':' not in _l:
            continue
        _h, _r = _l.split(':', 1)
        _lv, _x, _z = (int(v) for v in _h.split())
        _p = _r.split()
        _n = {v: k for k, v in LOCS.items()}.get(int(_p[0]))
        if _lv in _levels and (TEMPL2.get(_n, {}).get('name') or [''])[0] == 'Rug space':
            _zone = (_x // 8) * 8 + (_z // 8)
            TEMPLATE_RUG.setdefault(_zone, {})[(_x % 8, _z % 8)] = (_n, int(_p[2]) if len(_p) > 2 else 0)
_zoneroom = {}
_sec = None
for _l in read('scripts/skill_construction/configs/poh_rooms.enum').split('\n'):
    _l = _l.strip()
    if _l.startswith('['):
        _sec = _l[1:-1]; continue
    if _l.startswith('val=') and _sec == 'poh_room_zone':
        _a, _b = _l[4:].split(',', 1)
        _zoneroom[int(_a)] = int(_b)
KINDNUM = {'^poh_rug_corner': 'corner', '^poh_rug_side': 'side', '^poh_rug_middle': 'middle'}
bad, total = [], 0
for _m in re.finditer(r'\[proc,poh_rug_(\w+)\]\(coord \$base, int \$rot, int \$tier\)\n((?:~poh_rug_lay[^\n]*\n)+)', RG):
    _room = _m.group(1)
    _rt = next((t for t, nm in
                ((t, v) for t, v in
                 ((int(a), b) for a, b in re.findall(r'^val=(\d+),(.+)$',
                  read('scripts/skill_construction/configs/poh_rooms.enum'), re.M)))
                if re.sub(r'\W+', '_', nm.lower()) == _room), None)
    if _rt is None or _rt not in _zoneroom:
        continue
    _tiles = TEMPLATE_RUG.get(_zoneroom[_rt], {})
    _xs = [t[0] for t in _tiles]; _zs = [t[1] for t in _tiles]
    _x0, _x1, _z0, _z1 = min(_xs), max(_xs), min(_zs), max(_zs)
    check(len(_tiles) == (_x1 - _x0 + 1) * (_z1 - _z0 + 1),
          '%s: its %d rug tiles are the whole %dx%d rectangle' % (_room, len(_tiles), _x1 - _x0 + 1, _z1 - _z0 + 1))
    for _x, _z, _a, _k in re.findall(r'~poh_rug_lay\(\$base, \$rot, (\d+), (\d+), (\d+), \$tier, (\^\w+)\);', _m.group(2)):
        _x, _z, _a = int(_x), int(_z), int(_a)
        total += 1
        if (_x, _z) not in _tiles:
            bad.append((_room, _x, _z, 'not a rug tile')); continue
        _n, _ang = _tiles[(_x, _z)]
        if _ang != _a:
            bad.append((_room, _x, _z, 'angle %d, template says %d' % (_a, _ang))); continue
        _want = 'corner' if (_x in (_x0, _x1) and _z in (_z0, _z1)) else \
                ('side' if (_x in (_x0, _x1) or _z in (_z0, _z1)) else 'middle')
        if KINDNUM.get(_k) != _want:
            bad.append((_room, _x, _z, '%s, rectangle says %s' % (_k, _want))); continue
        _g = _hot.get(_n)
        if _g and _g != (0, 0) and _g != KG[_want]:
            bad.append((_room, _x, _z, 'ghost %s, kind %s' % (_g, _want)))
check(not bad, 'every rug tile is the template\'s, at its angle and its kind: %s'
      % (bad[:3] or '%d tiles over five rooms' % total))
check(total == 122, 'and that is all 122 of them: %d' % total)

# the piece table: three tiers of three, each returning its own tier's loc
_rl = dict((int(a), b) for a, b in re.findall(r'^    case (\d+) : return\((\w+)\);', RG, re.M))
check(sorted(_rl) == [4, 5, 6, 8, 9, 10, 12, 13, 14],
      'the rug table is three tiers of three with no gap: %s' % sorted(_rl))
TIERLOC = {1: ('loc_13588', 'loc_13589', 'loc_13590'), 2: ('loc_13591', 'loc_13592', 'loc_13593'),
           3: ('loc_13594', 'loc_13595', 'loc_13596')}
bad = [(k, v) for k, v in _rl.items() if v != TIERLOC[k // 4][k % 4]]
check(not bad, 'and every case is its own tier\'s piece for its own kind: %s' % (bad or '9 checked'))

# all nine can be taken out again, and none twice
_rm = set(re.findall(r'^\[oploc5,(\w+)\] ~poh_rug_remove;', RG, re.M))
_rmf = set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_rug_remove;', fu, re.M))
check(sorted(_rm | _rmf) == sorted(l for v in TIERLOC.values() for l in v),
      'all nine rug locs are wired to ~poh_rug_remove: %s' % sorted((_rm | _rmf)))
check(not (_rm & _rmf), 'and none of them is wired in both files')
check('~poh_furn_at($rx, $rz, ^poh_rug_anchor, ^poh_rug_anchor)' in RG,
      'removal looks the slot up at the anchor, not under the tile that was clicked')
check('movecoord($spot, calc(0 - ^poh_rug_anchor), 0, calc(0 - ^poh_rug_anchor))' in RG,
      'and the anchor is stepped back to the zone corner before the table is read')

# curtains and wall decoration: plain ladders, but their materials have to be real and their
# hotspots have to be ones nothing else already owns
for _key, _n in (('curtain', 3), ('walldecor', 2), ('rug', 13)):
    _f = next(f for f in _spec['families'] if f['key'] == _key)
    check(len(_f['hotspots']) == _n, '%s takes %d hotspots: %d' % (_key, _n, len(_f['hotspots'])))
    _bad = [m[0] for p in _f['pieces'] for m in p['mats'] if m[0] not in OBJS]
    check(not _bad, '%s is built out of real objs: %s' % (_key, _bad or 'all of them'))
_gold = [p['label'] for f in _spec['families'] for p in f.get('pieces', [])
         if any(m[0] == 'gold_leaf' for m in p['mats'])]
check(sorted(_gold) == ['Gilded cape rack', 'Gilded decoration', 'Gilded wardrobe', 'Opulent rug'],
      'gold leaf is what the gilded pieces are made of: %s' % sorted(_gold))


print('61. the fence, the throne room floor, the chapel windows - and every multiloc\'s ops')
DC = read('scripts/skill_construction/scripts/poh_decor.rs2')

_before = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_decor.rs2'), 'rb').read()
r = _sp.run([sys.executable, os.path.join(C, 'tools/gendecor.py')], capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/gendecor.py runs clean'
      + ('' if r.returncode == 0 else ': ' + (r.stdout + r.stderr)[-400:]))
_after = open(os.path.join(C, 'scripts/skill_construction/scripts/poh_decor.rs2'), 'rb').read()
if _after != _before:
    open(os.path.join(C, 'scripts/skill_construction/scripts/poh_decor.rs2'), 'wb').write(_before)
check(_after == _before, 're-running it changes nothing: byte-identical' if _after == _before
      else 're-running it CHANGES the file - it is out of step with the templates')

# THE CLASS THIS ROUND FOUND. A multiloc shell shows its ACTIVE CHILD's options, so a child with
# op5=Remove gives the shell a Remove - and poh_dynamic_window is placed 116 times in every house.
# Nothing answered it, so every window in every house has been printing the engine's "Nothing
# interesting happens". Check 56 could not see it: it sweeps the locs the SPEC places, and a shell
# the template places is not one of those.
_shells = {}
for _n, _d in POHLOC2.items():
    _kids = [v.split(',', 1)[1] for v in (_d.get('multiloc') or [])]
    if _kids:
        _shells[_n] = _kids
check(len(_shells) >= 1, 'poh.loc has %d multiloc shells' % len(_shells))
_placed_ids = set()
for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    _sec = None
    for _l in read('maps/%s.jm2' % _sq).split('\n'):
        if _l.startswith('===='):
            _sec = _l.strip('= '); continue
        if _sec == 'LOC' and ':' in _l:
            _placed_ids.add(int(_l.split(':', 1)[1].split()[0]))
_dead = []
for _n, _kids in _shells.items():
    if LOCS.get(_n) not in _placed_ids:
        continue
    _ops = set()
    for _k in _kids:
        for _key, _v in (POHLOC2.get(_k) or {}).items():
            _m = re.match(r'^op([1-5])$', _key)
            if _m and _v[0] != 'hidden':
                _ops.add((_m.group(1), _v[0]))
    for _num, _label in sorted(_ops):
        if (_num, _n) not in TRIG and not any((_num, _k) in TRIG for _k in _kids):
            _dead.append('%s op%s=%s (from a child)' % (_n, _num, _label))
check(not _dead, 'every op a placed multiloc shows through its children is answered: %s'
      % (_dead[:4] or '%d shells checked' % len([n for n in _shells if LOCS.get(n) in _placed_ids])))
check('[oploc5,poh_dynamic_window]' in DC, 'and the house windows answer their own Remove')

# the three new pieces, back against the templates
def _tilesof(name, room):
    out = {}
    for _sq, _levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
        _sec = None
        for _l in read('maps/%s.jm2' % _sq).split('\n'):
            if _l.startswith('===='):
                _sec = _l.strip('= '); continue
            if _sec != 'LOC' or ':' not in _l:
                continue
            _h, _r = _l.split(':', 1)
            _lv, _x, _z = (int(v) for v in _h.split())
            _p = _r.split()
            _n = {v: k for k, v in LOCS.items()}.get(int(_p[0]))
            if _lv in _levels and (TEMPL2.get(_n, {}).get('name') or [''])[0] == name:
                out[(_x % 8, _z % 8)] = (int(_p[1]) if len(_p) > 1 else 10,
                                         int(_p[2]) if len(_p) > 2 else 0)
    return out
SH = {'poh_fence_wall': 0, 'poh_fence_corner': 2, 'poh_thronefloor_mat': 22, 'poh_window_pane': 0}
for _proc, _name, _want in (('poh_fence_wall|poh_fence_corner', 'Fencing', 20),
                            ('poh_thronefloor_mat', 'Floor space', 4),
                            ('poh_window_pane', 'Window space', 6)):
    _t = _tilesof(_name, {'Fencing': 'Formal garden', 'Floor space': 'Throne room',
                          'Window space': 'Chapel'}[_name])
    _calls = re.findall(r'~(' + _proc + r')\(\$base, \$rot, (\d+), (\d+), (\d+)', DC)
    check(len(_calls) == _want, '%s lays %d tiles: %d' % (_name, _want, len(_calls)))
    _bad = []
    for _p, _x, _z, _a in _calls:
        _k = (int(_x), int(_z))
        if _k not in _t:
            _bad.append((_k, 'not a template tile')); continue
        if _t[_k][1] != int(_a):
            _bad.append((_k, 'angle %s, template says %d' % (_a, _t[_k][1]))); continue
        if SH[_p] != _t[_k][0]:
            _bad.append((_k, '%s, template shape %d' % (_p, _t[_k][0])))
    check(not _bad, 'and every one is the template\'s tile, shape and angle: %s' % (_bad[:3] or 'all of them'))

# the window table is the shell's own child order, or building one picks a different window
_wl = dict((int(a), b) for a, b in re.findall(r'^    case (\d+) : return\((poh_\w+_window_\w+)\);', DC, re.M))
_kids = [v.split(',', 1)[1] for v in (POHLOC2['poh_dynamic_window'].get('multiloc') or [])]
check(len(_wl) == 54 and [_wl.get(i) for i in range(54)] == _kids,
      'the 54-window table is poh_dynamic_window\'s own child order: %s'
      % ('yes' if [_wl.get(i) for i in range(54)] == _kids else 'NO'))
check('%poh_window = calc(%poh_style * ^poh_window_kinds + $choice);' in DC,
      'building a chapel window reglazes the whole house')

# the throne floor art is one per style, named after the same six towns the windows are
_fl = dict((int(a), b) for a, b in re.findall(r'^    case (\d+) : return\((poh_floordecor_\w+)\);', DC, re.M))
check(len(_fl) == 6 and all(_fl[i] == 'poh_floordecor_' + t for i, t in enumerate(
    ['rimmington', 'lumbridge', 'pollnivneach', 'rellekka', 'brimhaven', 'yanille'])),
    'the throne room floor has one piece per house style, in %%poh_style order: %s' % _fl)

# every loc the three can put down comes out again, by its own remover, and none twice
for _key, _proc, _n in (('fence', 'poh_fence_remove', 7), ('thronefloor', 'poh_thronefloor_remove', 6),
                        ('chapelwindow', 'poh_window_remove', 54)):
    _here = set(re.findall(r'^\[oploc5,(\w+)\] ~%s;' % _proc, DC, re.M))
    _there = set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~%s;' % _proc, fu, re.M))
    check(len(_here | _there) == _n, '%s: all %d locs are removable: %d' % (_key, _n, len(_here | _there)))
    check(not (_here & _there), '%s: none of them is wired in both files' % _key)

# the anchors are the spec's, written into the generated file from there and nowhere else
for _key, _proc in (('fence', 'poh_fence_place'), ('thronefloor', 'poh_thronefloor_place'),
                    ('chapelwindow', 'poh_window_place')):
    _a = next(f for f in _spec['families'] if f['key'] == _key)['anchor']
    check('movecoord($spot, %d, 0, %d);' % (-_a[0], -_a[1]) in
          DC.split('[proc,%s]' % _proc, 1)[1].split('\n[', 1)[0],
          '%s steps back from the spec\'s own anchor %s' % (_key, tuple(_a)))


print('62. the costume room\'s five storage spaces')

# One mechanism, five spaces, and everything about them is generated from two spec files. What this
# group is for is the seams between them: the item list against the objs that exist, against the
# treasure chest's own list and against itself; the windows into that list against each other; the
# capacities against the furniture; and the furniture against the art it was imported with.

import subprocess as _sp62
_ST = 'scripts/skill_construction/configs/poh_store.enum'
_SI = 'scripts/skill_construction/configs/poh_store.inv'
_kept62 = {f: open(os.path.join(C, f), 'rb').read() for f in (_ST, _SI)}
_r62 = _sp62.run([sys.executable, os.path.join(C, 'tools/genstores.py')],
                 capture_output=True, text=True, cwd=C)
check(_r62.returncode == 0, 'tools/genstores.py runs clean'
      + ('' if _r62.returncode == 0 else ': ' + _r62.stderr[-400:]))
_moved62 = [f for f in _kept62 if open(os.path.join(C, f), 'rb').read() != _kept62[f]]
for f in _moved62:
    open(os.path.join(C, f), 'wb').write(_kept62[f])
check(not _moved62, 're-running it changes nothing: %s' % (_moved62 or 'byte-identical'))

_STORE = read(_ST)
_items = enumtable(_STORE, 'poh_store_item')
_sname = enumtable(_STORE, 'poh_store_name')
_sfirst = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_first').items()}
_slast = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_last').items()}
_setfirst = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_setfirst').items()}
_setlast = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_setlast').items()}
_setname = enumtable(_STORE, 'poh_store_set_name')
_sf = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_set_first').items()}
_sl = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_set_last').items()}
_cap = {k: int(v) for k, v in enumtable(_STORE, 'poh_store_cap').items()}
_N62 = len(_items)

check(sorted(_items) == list(range(_N62)), 'poh_store_item is %d rows with no gap' % _N62)
_bad = [o for o in _items.values() if o not in OBJS]
check(not _bad, 'every one of them is a real obj: %s' % (_bad[:3] or 'all %d' % _N62))
_dupe = sorted({o for o in _items.values() if list(_items.values()).count(o) > 1})
check(not _dupe, 'and none of them is in two stores: %s' % (_dupe[:3] or 'all distinct'))

# The treasure chest is the OTHER storage in this room, and an item in both would be storable twice
# and lost once - the fancy dress box gave up the three berets and the highwayman mask for this.
_chest = set(enumtable(read('scripts/skill_construction/configs/poh_costume.enum'),
                       'poh_costume_item').values())
_both = sorted(set(_items.values()) & _chest)
check(not _both, 'nothing is in both a storage space and the treasure chest: %s'
      % (_both[:3] or 'the two lists are disjoint'))

# The five stores tile the item list exactly: no gap (an item nothing can reach) and no overlap
# (an item two spaces both claim).
_nst = len(_sname)
check(sorted(_sfirst) == sorted(_slast) == sorted(_sname) == list(range(_nst)),
      'all %d stores have a name and a window' % _nst)
_tile = [(_sfirst[i], _slast[i]) for i in range(_nst)]
check(_tile[0][0] == 0 and _tile[-1][1] == _N62 - 1
      and all(_tile[i][1] + 1 == _tile[i + 1][0] for i in range(_nst - 1)),
      'the five windows tile poh_store_item with no gap and no overlap: %s' % _tile)
_stile = [(_setfirst[i], _setlast[i]) for i in range(_nst)]
check(_stile[0][0] == 0 and _stile[-1][1] == len(_setname) - 1
      and all(_stile[i][1] + 1 == _stile[i + 1][0] for i in range(_nst - 1)),
      'and the set windows tile the %d sets the same way: %s' % (len(_setname), _stile))

# ...and inside each store, the sets tile that store's run. A set that straddles two stores would
# let "take out a set" hand you the wardrobe's robes from the cape rack.
_bad = []
for _i in range(_nst):
    _runs = [(_sf[j], _sl[j]) for j in range(_setfirst[_i], _setlast[_i] + 1)]
    if (not _runs or _runs[0][0] != _sfirst[_i] or _runs[-1][1] != _slast[_i]
            or any(_runs[k][1] + 1 != _runs[k + 1][0] for k in range(len(_runs) - 1))
            or any(a > b for a, b in _runs)):
        _bad.append((_sname[_i], _runs))
check(not _bad, 'every store\'s sets tile its own run and nothing else: %s'
      % (_bad or 'all %d sets' % len(_setname)))

# The inv is one slot per item, perm, and has an id - the three ways it could be right in the config
# and still do nothing in game.
_inv = blocks(read(_SI))['poh_store_inv']
check(int(_inv['size'][0]) == _N62, 'poh_store_inv holds one of each: size=%s' % _inv['size'][0])
check(_inv['scope'][0] == 'perm', 'and it is scope=perm, so it survives a logout')
check('poh_store_inv' in INVS, 'and it has an id in inv.pack')

# Capacity is keyed store x 8 + tier, and what makes it right is the furniture: a row per tier that
# exists, none for a tier that does not, rising, and the top tier holding the whole list.
_spec62 = _json.load(open(os.path.join(C, 'tools/furnspec.json')))['families']
_sspec = _json.load(open(os.path.join(C, 'tools/storespec.json')))['stores']
check(len(_sspec) == _nst, 'storespec has all %d stores' % _nst)
_bad = []
for _i, _st in enumerate(_sspec):
    _f = next((f for f in _spec62 if f['key'] == _st['family']), None)
    _nt = len(_f['pieces']) if _f else 0
    _want = list(range(1, _nt + 1))
    _got = sorted(t - _i * 8 for t in _cap if t // 8 == _i)
    _n = _slast[_i] - _sfirst[_i] + 1
    if _got != _want:
        _bad.append((_st['key'], 'tiers %s vs %s' % (_got, _want)))
    elif _cap[_i * 8 + _nt] != _n:
        _bad.append((_st['key'], 'top tier holds %d of %d' % (_cap[_i * 8 + _nt], _n)))
    elif any(_cap[_i * 8 + t] > _cap[_i * 8 + t + 1] for t in range(1, _nt)):
        _bad.append((_st['key'], 'capacity falls'))
check(not _bad, 'every tier of every space has a capacity, rising to the whole list: %s'
      % (_bad or [(_sname[i], [_cap[i * 8 + t] for t in sorted(x - i * 8 for x in _cap if x // 8 == i)])
                  for i in range(_nst)]))

# The furniture itself: the art came out of the rev-474 cache in its own config, and a piece whose
# footprint disagrees with its hotspot's stands through a wall.
_SL = blocks(read('scripts/skill_construction/configs/poh_costume_storage.loc'))
_TL = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
_byid = {v: k for k, v in LOCS.items()}
_bad, _nloc = [], 0
for _i, _st in enumerate(_sspec):
    _f = next(f for f in _spec62 if f['key'] == _st['family'])
    _hot = _SL.get(_byid.get(_f['hotspots'][0])) or _TL.get(_byid.get(_f['hotspots'][0]))
    for _pc in _f['pieces']:
        _nloc += 1
        _d = _SL.get(_pc['loc'])
        if _d is None:
            _bad.append((_pc['loc'], 'not in poh_costume_storage.loc'))
            continue
        if 'op1' not in _d:
            _bad.append((_pc['loc'], 'no op1 - it would be a dead click'))
        if 'Remove' not in (_d.get('op5') or []):
            _bad.append((_pc['loc'], 'no op5=Remove'))
        if _pc['loc'] not in LOCS:
            _bad.append((_pc['loc'], 'no id in loc.pack'))
        for _k in ('width', 'length'):
            if (_d.get(_k) or ['1'])[0] != (_hot.get(_k) or ['1'])[0]:
                _bad.append((_pc['loc'], '%s %s, but its hotspot is %s'
                             % (_k, (_d.get(_k) or ['1'])[0], (_hot.get(_k) or ['1'])[0])))
check(not _bad, 'all %d pieces are real, clickable, removable and hotspot-shaped: %s'
      % (_nloc, _bad[:3] or 'all of them'))

# The hotspots are the costume room's own six minus the chest's, each used once.
_hot62 = [f['hotspots'][0] for f in _spec62 if f['key'] in {s['family'] for s in _sspec}]
check(len(set(_hot62)) == _nst, 'the five spaces take five different hotspots: %s' % sorted(_hot62))
_chesthot = next(f['hotspots'] for f in _spec62 if f['key'] == 'treasurechest')
check(not (set(_hot62) & set(_chesthot)), 'and none of them is the treasure chest\'s')
_rooms = {f['room'] for f in _spec62 if f['key'] in {s['family'] for s in _sspec}}
check(_rooms == {'costume room'}, 'all five are in the costume room: %s' % sorted(_rooms))

# APPEND-ONLY. A family's position in the spec is its id and an item's position is the number
# written into a player's saved furniture, so these five had to go on the END however they read -
# inserting them beside the treasure chest, where they belong, renumbered 292 existing items and
# quietly rearranged every house already standing.
_keys62 = [f['key'] for f in _spec62]
# The five were the last five when they shipped; the hedge has been appended since, which is fine -
# appending is the rule. What must never change is WHERE they are, because a family's position is
# its id and an item's position is the number in a player's save. 74 to 78 are literals on purpose:
# they are the baseline, and a family inserted anywhere before them moves all five and fires this.
check([_keys62.index(s['family']) + 1 for s in _sspec] == [74, 75, 76, 77, 78],
      'the five families are still ids 74-78: %s'
      % [_keys62.index(s['family']) + 1 for s in _sspec])

# Every trigger the generator emitted points at the right store. This is the seam that would fail
# silently: a cape rack wired to store 1 opens, works, and holds robes.
_fo = read('scripts/skill_construction/scripts/poh_furn_ops.rs2')
_ITEMN = {}
_n62 = 0
for _f in _spec62:
    for _pc in (_f.get('pieces') or _f.get('locs')):
        _n62 += 1
        _ITEMN[_pc['loc'] if isinstance(_pc, dict) else _pc] = _n62
_bad = []
for _i, _st in enumerate(_sspec):
    _f = next(f for f in _spec62 if f['key'] == _st['family'])
    for _pc in _f['pieces']:
        _m = re.search(r'^\[oploc1,%s\]\s*\n~poh_store_open\((\d+), (\d+)\);$' % _pc['loc'],
                       _fo, re.M)
        if not _m:
            _bad.append((_pc['loc'], 'no ~poh_store_open trigger'))
        elif (int(_m.group(1)), int(_m.group(2))) != (_i, _ITEMN[_pc['loc']]):
            _bad.append((_pc['loc'], 'opens store %s item %s, wanted %d %d'
                         % (_m.group(1), _m.group(2), _i, _ITEMN[_pc['loc']])))
check(not _bad, 'every piece opens its own store at its own item number: %s'
      % (_bad[:3] or 'all %d' % _nloc))
check(len(re.findall(r'~poh_store_open\(', _fo)) == _nloc,
      'and nothing else calls ~poh_store_open')

# The store bound inside the paging proc. Without it, a full cape rack's "More sets..." walks
# straight on into the magic wardrobe's sets, because they are one flat table.
_STS = src['scripts/skill_construction/scripts/poh_stores.rs2']
_nth = _STS.split('[proc,poh_store_nth]', 1)[1].split('\n[', 1)[0]
check('poh_store_setlast' in _nth,
      '~poh_store_nth stops at its own store\'s last set, not at the end of the table')
_take = _STS.split('[proc,poh_store_take]', 1)[1].split('\n[', 1)[0]
check('poh_store_setfirst' in _take and re.findall(r'def_int \$home = ([^;]+);', _take) == ['$from'],
      'and "More sets..." wraps to its own store\'s first set, not to set 0')
for _proc, _tbl in (('poh_store_count', 'poh_store_first'), ('poh_store_put', 'poh_store_first'),
                    ('poh_store_check', 'poh_store_setfirst')):
    _b = _STS.split('[proc,%s]' % _proc, 1)[1].split('\n[', 1)[0]
    check(_tbl in _b and 'poh_store_' + _tbl.split('_')[-1].replace('first', 'last') in _b,
          '~%s only ever looks inside its own store' % _proc)

# The magic stone exists because the level-99 cape rack does, and nothing else uses one.
check('magic_stone' in OBJS, 'magic_stone has an id in obj.pack')
check('cert_magic_stone' in OBJS, 'and so does its noted twin')
_uses = [(f['key'], p['label']) for f in _spec62 for p in f.get('pieces', [])
         if any(m[0] == 'magic_stone' for m in p['mats'])]
check(_uses == [('caperack', 'Magic cape rack')],
      'one magic stone, for the level-99 cape rack: %s' % _uses)
_top = next(p for p in next(f for f in _spec62 if f['key'] == 'caperack')['pieces']
            if p['label'] == 'Magic cape rack')
check(_top['level'] == 99 and _top['mats'] == [['magic_stone', 1]],
      'level 99, one stone: %s, %s' % (_top['level'], _top['mats']))

# Levels: OSRS's own, and rising within each space.
_OSRS = {'caperack': [54, 63, 72, 81, 90, 99], 'magicwardrobe': [42, 51, 60, 69, 78, 87, 96],
         'armourcase': [46, 64, 82], 'toybox': [50, 68, 86], 'fancydress': [44, 62, 80]}
_bad = [(k, [p['level'] for p in next(f for f in _spec62 if f['key'] == k)['pieces']], v)
        for k, v in _OSRS.items()
        if [p['level'] for p in next(f for f in _spec62 if f['key'] == k)['pieces']] != v]
check(not _bad, 'the build levels are OSRS\'s own: %s' % (_bad or '54-99, 42-96, 46-82, 50-86, 44-80'))

# ...and the experience is the repo's one rule, planks x the wood, for every piece made of planks.
_XP = {'oak_plank': const('poh_xp_oak'), 'teak_plank': const('poh_xp_teak'),
       'mahogany_plank': const('poh_xp_mahogany'), 'plank': const('poh_xp_plank')}
_bad = [(f['key'], p['label'], p['xp'], p['mats'][0][1] * _XP[p['mats'][0][0]])
        for f in _spec62 if f['key'] in _OSRS for p in f['pieces']
        if p['mats'][0][0] in _XP and p['xp'] != p['mats'][0][1] * _XP[p['mats'][0][0]]]
check(not _bad, 'and the experience is planks x the wood, as everywhere else: %s'
      % (_bad[:3] or 'every plank piece'))

def _tiles63(name, room):
    """Every placement of a named hotspot in a named room, per style square, as template tiles."""
    _byid = {v: k for k, v in LOCS.items()}
    _z2r, _rn, _sec = {}, {}, None
    for l in read('scripts/skill_construction/configs/poh_rooms.enum').split('\n'):
        l = l.strip()
        if l.startswith('['):
            _sec = l[1:-1]; continue
        if l.startswith('val='):
            a, b = l[4:].split(',', 1)
            if _sec == 'poh_room_zone':
                _z2r[int(b)] = int(a)
            if _sec == 'poh_room_name':
                _rn[int(a)] = b
    per = {}
    for sq, levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
        sec = None
        for l in read('maps/%s.jm2' % sq).split('\n'):
            if l.startswith('===='):
                sec = l.strip('= '); continue
            if sec != 'LOC' or ':' not in l:
                continue
            head, rest = l.split(':', 1)
            lv, x, z = (int(v) for v in head.split())
            p = rest.split()
            n = _byid.get(int(p[0]))
            if lv not in levels or _rn.get(_z2r.get((x // 8) * 8 + (z // 8))) != room:
                continue
            if (TEMPL.get(n, {}).get('name') or [''])[0] != name:
                continue
            per.setdefault((sq, lv), {})[(x % 8, z % 8)] = (
                int(p[1]) if len(p) > 1 else 10, int(p[2]) if len(p) > 2 else 0)
    sigs = {k: sorted(v.items()) for k, v in per.items()}
    first = sorted(sigs)[0]
    return sorted(per[first].items()), [k for k, v in sigs.items() if v != sigs[first]]



print('63. hedging, and nothing buildable out of something you cannot get')

# ---------------------------------------------------------------- nothing unobtainable
#
# THE CHECK THIS GROUP EXISTS FOR. The formal garden shipped with six flowerbeds that cost a bagged
# flower, and NOTHING IN THE GAME SOLD ONE - the six objs were imported, priced and left out of the
# shop, and the comment in poh_garden.inv explaining why they were left out had gone stale the day
# the formal garden round wired the hotspots. Six buildable things, unbuildable, for a week, and
# every other check in this file passed the whole time.
#
# So: every obj any family names as a material is either stocked by a shop in this repo, or is in
# the table below with the script that makes it - and that script has to actually mention it. The
# table is not an allowlist; a plank nobody mills goes red the same as a flower nobody sells.
MADE = {
    # woodplank, not plank: the sawmill cuts obj 960 (see group 27). Left as 'plank' this passed
    # anyway - on the word "plank" appearing in a COMMENT in sawmill.rs2, since \bplank\b does not
    # match inside "woodplank" or "sawmill_fee_plank" - which is a check agreeing with itself.
    'woodplank':      'skill_construction/scripts/sawmill.rs2',
    'oak_plank':      'skill_construction/scripts/sawmill.rs2',
    'teak_plank':     'skill_construction/scripts/sawmill.rs2',
    'mahogany_plank': 'skill_construction/scripts/sawmill.rs2',
    'molten_glass':   'skill_crafting/scripts/glass/glass.rs2',
    'softclay':       'skill_crafting/scripts/pottery/pottery.rs2',
    'steel_bar':      'skill_smithing/scripts/smelting/smelting.rs2',
}
_stocked = {}
for _root, _dirs, _fs in os.walk(os.path.join(C, 'scripts')):
    for _fn in _fs:
        if not _fn.endswith('.inv'):
            continue
        for _m in re.finditer(r'^stock\d+=(\w+),', read(os.path.join(_root, _fn)[len(C) + 1:]), re.M):
            _stocked.setdefault(_m.group(1), set()).add(_fn)
_mats = sorted({m[0] for f in _spec['families'] for p in f.get('pieces', [])
                for m in p['mats']}
               | {'woodplank', 'oak_plank', 'teak_plank', 'mahogany_plank'})
_orphan = [m for m in _mats if m not in _stocked and m not in MADE]
check(not _orphan, 'every material is bought somewhere or made somewhere: %s'
      % (_orphan or '%d of them' % len(_mats)))
_notmade = [(m, f) for m, f in MADE.items()
            if m in _mats and not re.search(r'\b%s\b' % re.escape(m), read('scripts/' + f))]
check(not _notmade, 'and every "made" one is really named by the script that makes it: %s'
      % (_notmade or 'all %d' % len([m for m in MADE if m in _mats])))
_bought = [m for m in _mats if m in _stocked]
# 31, not 30: the bolt of cloth comes off Construction Supplies' shelf now rather than out of the
# sawmill operator's dialogue, so it left the MADE table above and joined this count. Before that it
# was 30 and not 29 because the basic plank is woodplank, which a shop stocks, where the import's
# `plank` was bought nowhere. Both moves are the material set being corrected, not a shop changing.
check(len(_bought) == 31, '%d of them come off a shop shelf' % len(_bought))
# ...and the six that started this are among them
_flowers = ['poh_bag_flower', 'poh_bag_daffodils', 'poh_bag_bluebells',
            'poh_bag_sunflower', 'poh_bag_marigolds', 'poh_bag_roses']
check(all(f in _stocked for f in _flowers),
      'the six formal-garden flowers are buyable: %s'
      % sorted({s for f in _flowers for s in _stocked.get(f, ['NOWHERE'])}))

# ---------------------------------------------------------------- the hedge itself
_kept63 = {f: open(os.path.join(C, f), 'rb').read()
           for f in ['scripts/skill_construction/scripts/poh_hedge.rs2']}
_r63 = _sp.run([sys.executable, os.path.join(C, 'tools/genhedge.py')],
               capture_output=True, text=True, cwd=C)
check(_r63.returncode == 0, 'tools/genhedge.py runs clean'
      + ('' if _r63.returncode == 0 else ': ' + (_r63.stdout + _r63.stderr)[-400:]))
_moved63 = [f for f in _kept63 if open(os.path.join(C, f), 'rb').read() != _kept63[f]]
for f in _moved63:
    open(os.path.join(C, f), 'wb').write(_kept63[f])
check(not _moved63, 're-running it changes nothing: %s' % (_moved63 or 'byte-identical'))

HG = clean['scripts/skill_construction/scripts/poh_hedge.rs2']
_hfam = next(f for f in _spec['families'] if f['key'] == 'hedge')
check(len(_hfam['pieces']) == 7, 'seven tiers: %d' % len(_hfam['pieces']))
check([p['level'] for p in _hfam['pieces']] == [56, 60, 64, 68, 72, 76, 80],
      'at OSRS\'s levels: %s' % [p['level'] for p in _hfam['pieces']])
check([p['xp'] for p in _hfam['pieces']] == [70, 100, 122, 141, 158, 223, 316],
      'and OSRS\'s experience: %s' % [p['xp'] for p in _hfam['pieces']])
check(all(len(p['mats']) == 1 and p['mats'][0][1] == 1 for p in _hfam['pieces']),
      'one bag each, which is the whole cost in OSRS too')

# the twenty tiles, re-derived from the templates the same way the generator does
_ht, _hbad = _tiles63('Hedging', 'Formal garden')
check(not _hbad, 'the hedge is laid the same in every style square: %s' % (_hbad or 'all six'))
check(len(_ht) == 20, 'twenty perimeter tiles: %d' % len(_ht))
_ft, _ = _tiles63('Fencing', 'Formal garden')
check({t for t, _ in _ht} == {t for t, _ in _ft},
      'the same twenty the fence uses - two hotspots per tile, on two layers')
check(all(sh == 10 for _, (sh, _a) in _ht), 'all of them on the ground layer, not the wall')
check(all(sh in (0, 2) for _, (sh, _a) in _ft), 'and the fence on the wall layer, which is why both fit')

# every tile the generator emitted is one of those twenty, at its own angle and kind
_laid = re.findall(r'^~poh_hedge_lay\(\$base, \$rot, (\d+), (\d+), (\d+), \$tier, \^poh_hedge_(\w+)\);$',
                   HG, re.M)
check(len(_laid) == 20, '~poh_hedge_place lays twenty: %d' % len(_laid))
_want = {t: a for t, (sh, a) in _ht}
_bad = [(int(x), int(z)) for x, z, a, k in _laid
        if (int(x), int(z)) not in _want or _want[(int(x), int(z))] != int(a)]
check(not _bad, 'each at the template\'s own tile and angle: %s' % (_bad[:3] or 'all twenty'))
check(sum(1 for _x, _z, _a, k in _laid if k == 'corner') == 4,
      'four of them corners: %d' % sum(1 for _x, _z, _a, k in _laid if k == 'corner'))

# THE KINDS ARE THE GHOSTS'. The thorny hedge's three models are the three hotspot models, so the
# order of a tier's triple in poh.loc is named rather than assumed - and the kind a tile takes is
# whichever Hedging hotspot the template put there.
_POHLOC63 = blocks(read('scripts/skill_construction/configs/poh.loc'))
def _geo63(model):
    d = os.path.join(C, 'models/loc')
    fs = [f for f in os.listdir(d) if f.startswith(model + '_') and f.endswith('.ob2')]
    if not fs:
        return None
    b = open(os.path.join(d, sorted(fs)[0]), 'rb').read()
    return struct.unpack_from('>HHB', b, len(b) - 18)[:2] if len(b) >= 18 else None
_ghost63 = [_geo63((TEMPL['loc474_%d' % n].get('model') or [''])[0].split(',')[0])
            for n in (15370, 15372, 15371)]
_t1 = [_geo63((_POHLOC63['loc_%d' % n].get('model') or [''])[0].split(',')[0])
       for n in (13456, 13457, 13458)]
check(_t1 == _ghost63 and None not in _t1,
      'the thorny hedge IS the three ghosts, which is what names the kinds: %s vs %s'
      % (_t1, _ghost63))

# the table is 7 x 3 with no gap, and every loc in it is a real removable Hedge
_tbl = re.findall(r'^    case (\d+) : return\((\w+)\);', HG.split('[proc,poh_hedge_loc]', 1)[1]
                  .split('\n[', 1)[0], re.M)
check([int(a) for a, _ in _tbl] == list(range(21)), '~poh_hedge_loc is 21 cases with no gap')
_bad = [l for _, l in _tbl if 'Remove' not in (_POHLOC63.get(l, {}).get('op5') or [])
        or (_POHLOC63.get(l, {}).get('name') or [''])[0] != 'Hedge']
check(not _bad, 'all 21 are removable Hedge locs in poh.loc: %s' % (_bad[:3] or 'all of them'))
check(len({l for _, l in _tbl}) == 21, 'and no loc is used by two tiers')

# removal is split between the two generators and declared exactly once each - a duplicate trigger
# is a hard build error, and a missing one is a dead Remove on a hedge you cannot take out.
_here = set(re.findall(r'^\[oploc5,(\w+)\] ~poh_hedge_remove;$', HG, re.M))
_there = set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_hedge_remove;$', fu, re.M))
check(len(_here | _there) == 21 and not (_here & _there),
      'all 21 are removable, none twice: %d here, %d in poh_furn_ops' % (len(_here), len(_there)))
check(_there == {p['loc'] for p in _hfam['pieces']},
      'poh_furn_ops owns exactly the seven the spec names')

# the anchor is the spec's, and it is NOT the fence's - both can stand in one garden
check('movecoord($spot, %d, 0, %d);' % (-_hfam['anchor'][0], -_hfam['anchor'][1])
      in HG.split('[proc,poh_hedge_place]', 1)[1].split('\n[', 1)[0],
      'it steps back from the spec\'s own anchor %s' % (tuple(_hfam['anchor']),))
_fencea = next(f for f in _spec['families'] if f['key'] == 'fence')['anchor']
check(_hfam['anchor'] != _fencea,
      'and it is not the fence\'s %s, so a garden can store one of each' % (tuple(_fencea),))
check(tuple(_hfam['anchor']) not in _famroomhot.get(int(enumtable(ROOMS, 'poh_room_zone')[16]), set()),
      'and nothing is ever built on it')


print('64. the skilling outfits, and the funnel they are found through')

# All 47 pieces were imported, six outfits had their experience bonus wired, and not one piece
# could be obtained by any means - tools/obtainable.py found it. Seven have a source now: a roll
# inside the same proc that applies the outfit's own bonus, so every repeatable action in those
# skills rolls, at a chance proportional to what the action was worth.

OUTFITS = ['prospector', 'angler', 'lumberjack', 'pyromancer', 'eye', 'smiths', 'carpenters',
           'graceful', 'rogue', 'zealots', 'hunter']
XPPROC = {'prospector': ('mining_xp', 'mining'), 'angler': ('fishing_xp', 'fishing'),
          'lumberjack': ('woodcutting_xp', 'woodcutting'), 'pyromancer': ('firemaking_xp', 'firemaking'),
          'eye': ('runecraft_xp', 'runecraft'), 'smiths': ('smithing_xp', 'smithing'),
          'carpenters': ('construction_xp', 'construction'),
          # Graceful, Rogue and Zealot's give no experience bonus in OSRS, so their procs have no
          # $extra to add. They exist for the roll alone.
          'graceful': ('agility_xp', 'agility'), 'rogue': ('thieving_xp', 'thieving'),
          'zealots': ('prayer_xp', 'prayer'),
          # Guild hunter, the last one to get a source: its four pieces were imported with the OSRS
          # gear and sat unobtainable until Hunter became a stat (2026-09-22).
          'hunter': ('hunter_xp', 'hunter')}
NOBONUS = ('graceful', 'rogue', 'zealots')
OSLOTS = ['hat', 'torso', 'legs', 'feet', 'hands', 'back']
OX = read('scripts/skilling_outfits/scripts/outfit_xp.rs2')
OD = read('scripts/skilling_outfits/scripts/outfit_drop.rs2')
OE = read('scripts/skilling_outfits/configs/outfits.enum')
OC = read('scripts/skilling_outfits/configs/outfits.constant')
OOBJ = blocks(read('scripts/skilling_outfits/configs/outfits.obj'))
OOBJ.update(blocks(read('scripts/general/configs/gear_474.obj')))

def _oconst(n):
    m = re.search(r'^\^%s\s*=\s*(-?\d+)\s*$' % n, OC, re.M)
    return int(m.group(1)) if m else None

check([_oconst('outfit_' + o) for o in OUTFITS] == list(range(len(OUTFITS))),
      'the outfits are numbered from zero with no gap: %s' % [_oconst('outfit_' + o) for o in OUTFITS])
# Values AFTER the claim, not inside it. A mutation harness matches a check by its wording, so a
# number interpolated into the claim changes the claim whenever the number moves - and a mutation
# aimed at this check stopped matching it for exactly that reason. Third time this session.
check(_oconst('outfit_count') == len(OUTFITS) and _oconst('outfit_pieces') == len(OSLOTS),
      '^outfit_count and ^outfit_pieces are every outfit and the six slots: got %s and %s'
      % (_oconst('outfit_count'), _oconst('outfit_pieces')))

PIECE = enumtable(OE, 'outfit_piece')
ONAME = enumtable(OE, 'outfit_name')
check(sorted(ONAME) == list(range(len(OUTFITS))), 'every outfit has a name for the message')
_bad = [v for v in PIECE.values() if v not in OBJS]
check(not _bad, 'every piece is a real obj: %s' % (_bad or 'all %d' % len(PIECE)))
check(len(set(PIECE.values())) == len(PIECE), 'and no piece is in two outfits')

# WHAT THE TABLE SHOULD HOLD, worked out from the obj configs and not from the table: every obj in
# outfits.obj whose name starts with the outfit's own prefix, placed at the slot its own wearpos
# says. Reading the enum to decide what the enum should say would check nothing. Guild hunter is
# excluded because it has no source and no index - and so is hunter_hood, which belongs to the
# Hunter camo outfit rather than the guild one.
_want = {}
for _n, _b in OOBJ.items():
    _pre = next((o for o in OUTFITS if _n.startswith(o + '_')), None)
    if _pre is None:
        continue
    _wp = (_b.get('wearpos') or [None])[0]
    if _wp in OSLOTS:
        _want[_n] = _oconst('outfit_' + _pre) * len(OSLOTS) + OSLOTS.index(_wp)
_got = {v: k for k, v in PIECE.items()}
_missing = sorted(n for n in _want if n not in _got)
_wrong = sorted((n, _got[n], _want[n]) for n in _want if n in _got and _got[n] != _want[n])
check(not _missing, 'every piece of the ten outfits is in the table: %s'
      % (_missing or 'all %d' % len(_want)))
check(not _wrong, '...each at its own wearpos slot in hat/torso/legs/feet/hands/back order: %s'
      % (_wrong[:3] or 'all %d' % len(_want)))
_extra = sorted(n for n in _got if n not in _want)
check(not _extra, '...and the table holds nothing else: %s' % (_extra or 'nothing'))
# The Smiths' uniform is the one with no headpiece, and Graceful the only one with six.
check(_oconst('outfit_smiths') * len(OSLOTS) not in PIECE,
      "the Smiths' uniform has no hat slot, because it has no headpiece")
check(sum(1 for k in PIECE if k // len(OSLOTS) == _oconst('outfit_graceful')) == 6,
      'Graceful is the six-piece one, which is why the stride is six')
check(sum(1 for k in PIECE if k // len(OSLOTS) == _oconst('outfit_rogue')) == 5,
      '...and the Rogue outfit the five-piece one')

# every xp proc rolls for its own outfit, and rolls on the PRE-bonus xp
_bad = []
for o in OUTFITS:
    proc, stat = XPPROC[o]
    m = re.search(r'\[proc,%s\]\(int \$xp\)\n(.*?)(?=\n\[|\Z)' % proc, OX, re.S)
    if not m:
        _bad.append((proc, 'no such proc')); continue
    body = m.group(1)
    if '~outfit_roll(^outfit_%s, $xp);' % o not in body:
        _bad.append((proc, 'does not roll for %s on the pre-bonus xp' % o))
    # The three with no OSRS bonus award the plain amount; the seven with one add $extra. Checking
    # the right shape per outfit is the point - a bonus proc quietly dropped from one of the seven
    # would otherwise pass as "one of the three".
    if o in NOBONUS:
        if 'stat_advance(%s, $xp);' % stat not in body:
            _bad.append((proc, 'does not award %s plainly' % stat))
        if '$extra' in body or '~outfit_xp_bonus' in body:
            _bad.append((proc, 'applies a bonus OSRS does not give'))
    else:
        if 'stat_advance(%s, calc($xp + $extra));' % stat not in body:
            _bad.append((proc, 'does not award %s with its bonus' % stat))
        if '~outfit_xp_bonus' not in body:
            _bad.append((proc, 'does not read its own bonus'))
check(not _bad, 'every experience proc rolls for its own outfit: %s' % (_bad[:3] or 'all %d' % len(OUTFITS)))
check(len(re.findall(r'~outfit_roll\(', OX)) == len(OUTFITS),
      'one roll per proc and no more: %d' % len(re.findall(r'~outfit_roll\(', OX)))

# THE FUNNEL. A skilling script that calls stat_advance directly gets neither the bonus nor a roll,
# which is how the carpenter's outfit could have been wired and still never turn up. Every direct
# call for these seven skills has to be a quest lump sum - finishing Heroes' Quest is not twenty
# hours of mining - and the four that are not in scripts/quests are named here with the reason.
DIRECT_OK = {
    'scripts/areas/area_ardougne_east/scripts/caroline.rs2': 'the Fishing Contest reward',
    # A quest lump sum that happens to live in an area file rather than under scripts/quests -
    # finishing Regicide is not five hours on an agility course, so it does not roll.
    'scripts/areas/area_ardougne_east/scripts/king_lathas.rs2': 'the Regicide reward',
    # A staff-only debugproc that grants experience for testing. It is deliberately NOT routed
    # through ~hunter_xp: a test grant is not a skilling action and must not roll for a Guild
    # hunter piece, which would put the outfit in a tester's bank without anyone catching anything.
    'scripts/skill_hunter/scripts/hunter_debug.rs2': 'the ::hunter test grant',
    # A one-off lump for building a unique, not a skilling action repeated for hours: attaching a
    # draconic visage to an anti-dragon shield pays OSRS's Smithing experience once per shield and
    # there is only ever one shield's worth of visages. It is the same case as the quest lumps
    # above, and routing it through ~smithing_xp would hand it the Smiths' uniform bonus and a roll
    # for the uniform off a single click.
    'scripts/dragonfire_shield/scripts/dragonfire_shield.rs2': 'the draconic visage lump',
}
_direct = []
for _root, _dirs, _fs in os.walk(os.path.join(C, 'scripts')):
    for _fn in _fs:
        if not _fn.endswith('.rs2'):
            continue
        _rel = os.path.join(_root, _fn)[len(C) + 1:].replace('\\', '/')
        if _rel.endswith('outfit_xp.rs2') or _rel == 'scripts/engine.rs2':
            continue
        for _m in re.finditer(r'stat_advance\((mining|fishing|woodcutting|firemaking|runecraft|'
                              r'smithing|construction|agility|thieving|prayer|hunter),', read(_rel)):
            if _rel.startswith('scripts/quests/') or _rel in DIRECT_OK:
                continue
            _direct.append((_rel, _m.group(1)))
check(not _direct, 'nothing outside a quest awards these skills directly: %s'
      % (sorted(set(_direct))[:3] or 'every repeatable action goes through the procs'))

# the construction one is the newest and the whole reason the carpenter's outfit works
check('~construction_xp(' in read('scripts/skill_construction/scripts/poh_furniture.rs2'),
      'building furniture goes through ~construction_xp')
check("'~construction_xp(enum(int, int, poh_furn_xp, $item));'," in read('tools/genfurn.py'),
      '...and genfurn.py is what writes it, so a regenerate keeps it')

# a piece you already own is never given again - in the pack, worn OR banked
for _proc in ('outfit_missing', 'outfit_roll'):
    _b = OD.split('[proc,%s]' % _proc, 1)[1].split('\n[', 1)[0]
    check('~obj_gettotal(' in _b, '~%s counts what you own everywhere, not just your pack' % _proc)
check('inv_total(bank,' in read('scripts/general/scripts/misc/inv_procs.rs2')
      .split('[proc,obj_gettotal]', 1)[1].split('\n[', 1)[0],
      '...and ~obj_gettotal really does read the bank')
# full hands do not lose it
check('obj_add(coord,' in OD.split('[proc,outfit_give]', 1)[1].split('\n[', 1)[0],
      'a piece found with a full inventory goes on the floor rather than nowhere')

# the rate is one number and it is a constant
check(_oconst('outfit_roll_xp') and 'random(^outfit_roll_xp)' in OD,
      'the chance is xp/^outfit_roll_xp (%s), and that is the only number in it'
      % _oconst('outfit_roll_xp'))
check(not re.search(r'random\((\d+)\)', OD.split('[proc,outfit_roll]', 1)[1].split('\n[', 1)[0]),
      'no bare number in the roll')

# ---- AND THE END-TO-END ONE: ask the sweep, not the code
_sw = _sp.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
              capture_output=True, text=True, cwd=C)
check(_sw.returncode == 0, 'tools/obtainable.py runs clean'
      + ('' if _sw.returncode == 0 else ': ' + _sw.stderr[-300:]))
_hard = _sw.stdout.split('NOTHING ANYWHERE MENTIONS THESE', 1)[-1].split('MENTIONED, BUT', 1)[0]
_stillorphan = [p for p in PIECE.values() if re.search(r'\b%s\b' % re.escape(p), _hard)]
check(not _stillorphan, 'and it agrees every piece in the table is obtainable now: %s'
      % (_stillorphan[:4] or 'all %d of them' % len(PIECE)))
# THE GUILD HUNTER SET HAS A SOURCE NOW, and this check moved with it for the third time. It first
# asserted the four pieces were in the real orphan list; then that a written reason excused them in
# the by-design list; now that they are in NEITHER, because Hunter became a stat on 2026-09-22 and
# butterfly netting rolls for them the way every other outfit is found. The shape of the check is
# the same each time: ask the sweep where they are, and require the spec to agree.
_GUILD_HUNTER = ['hunter_headwear', 'hunter_top', 'hunter_legs', 'hunter_boots']
_nospec = _json.loads(read('tools/nosourcespec.json'))['objs']
_stillexcused = [k for k, v in _nospec.items()
                 if set(_GUILD_HUNTER) & set([k] + v.get('also', []))]
check(not _stillexcused,
      'no guild hunter piece is excused in nosourcespec.json any more - they are found while '
      'training Hunter, and an excuse left behind is how a stale reason outlives its reason: %s'
      % (_stillexcused or 'none of the four'))
_bydesign = _sw.stdout.split('BUILT WITH NO SOURCE ON PURPOSE', 1)[-1].split('NOTHING ANYWHERE', 1)[0]
check(not any(re.search(r'\b%s\b' % p, _bydesign) for p in _GUILD_HUNTER),
      'and the sweep no longer puts any of them in its by-design section')
# The cape's hood was the last Hunter piece shut off, specced in nosourcespec.json until the cape
# opened on 2026-09-23 (box traps, bird snares, the Hunting expert). It is sold with the cape now, so
# an excuse left behind for it would be exactly the stale reason this section exists to catch.
check('hunter_hood' not in _nospec,
      "the Hunter cape's hood is no longer excused - the Hunting expert sells it with the cape")

# A STORAGE LIST IS NOT A MENTION EITHER. Excluding the costume room from the SOURCE rule was not
# enough: it still counted as a mention, which demotes an obj out of "nothing anywhere mentions
# these" and into "worth a glance, not a bug list". That hid seventeen unobtainable objs, two of
# them Graceful pieces.
#
# THIS USED TO ASK THE QUESTION OF THE MIME SET and cannot any more. Every orphan is specced now,
# and a spec entry outranks both lists - so reverting the fix moves nothing, the check went red on
# correct code, and the mutation written for it "passed" only because the check could no longer
# pass at all. A check that cannot pass is exactly as useless as one that cannot fail, and it
# fools the harness in the same way.
#
# So the rule is asked of an input this check builds, which needs no live case to exist. Same
# technique as the path-separator check: give the function the shape it is meant to strip and see
# whether it strips it.
sys.path.insert(0, os.path.join(C, 'tools'))
import obtainable as _ob
_probe = '\n'.join(['[poh_store_item]', 'val=0,a_thing_only_stored', '', '[something_else]',
                     'val=0,a_thing_really_mentioned'])
_stripped = _ob.without_storage_lists(_probe)
check('a_thing_only_stored' not in _stripped and 'a_thing_really_mentioned' in _stripped,
      'the mention scan drops a name that only a costume room storage list names, and keeps one '
      'any other table names')
check('poh_store_item' in _ob.STORAGE_LISTS and 'poh_costume_item' in _ob.STORAGE_LISTS,
      'and both storage lists are the ones it drops')
check(re.search(r're\.findall\(.*without_storage_lists\(read\(rel\)\)',
                read('tools/obtainable.py')),
      'with the stripping wired into the mention scan itself, not just available to it')


print('64b. what the three outfits that pay no experience do instead')

# Graceful, the Rogue outfit and Zealot's robes pay no experience bonus, in OSRS or here. This is
# the group for what they pay instead. Two of the three are scripts hooking one action at the
# moment it resolves; the third is two numbers the engine already reads, and the checks below are
# as much about keeping it that way as about the numbers being right.

OEFF = read('scripts/skilling_outfits/scripts/outfit_effects.rs2')
BURY = read('scripts/skill_prayer/scripts/bury_bone.rs2')
THIEF = read('scripts/skill_thieving/scripts/thieving.rs2')
FURNOPS = read('scripts/skill_construction/scripts/poh_furn_ops.rs2')
GENFURN = read('tools/genfurn.py')
OEFF_CODE = strip(OEFF)

# ---- GRACEFUL: a continuous effect, so not a script at all
_GRACE_PIECES = ('graceful_hood', 'graceful_top', 'graceful_legs', 'graceful_gloves',
                 'graceful_boots', 'graceful_cape')
check(not [g for g in _GRACE_PIECES if g in OEFF_CODE],
      'Graceful is not scripted: no piece of it is named in any proc, because its weight and its '
      'recovery are numbers the engine reads and not an action to hook: %s'
      % ([g for g in _GRACE_PIECES if g in OEFF_CODE] or 'none of the six'))

# ---- GRACEFUL: the numbers, checked where they can be checked WITHOUT a build
# The artefact check below is the authority on what the server reads, and it needs data/pack to
# exist - which it does not in the sandbox, where nothing compiles. So these read the configs and
# tools/gracefulspec.json instead. They are not a substitute for the artefact check: they cannot
# see whether a negative weight survived p2. They are the half that still runs when it cannot.
_GSPEC = _json.load(open(os.path.join(C, 'tools/gracefulspec.json')))
_OBJ = read('scripts/skilling_outfits/configs/outfits.obj')

def _gobj(name):
    """The weight in grams and the energy_restore percent that outfits.obj gives one piece.

    Returns (None, None) when the block or either line is missing, so a caller says FAIL rather
    than raising - a check whose condition raises is a crash and not a check.
    """
    m = re.search(r'^\[' + re.escape(name) + r'\]$', _OBJ, re.M)
    if not m:
        return None, None
    nxt = re.search(r'^\[', _OBJ[m.end():], re.M)
    blk = _OBJ[m.end():m.end() + nxt.start()] if nxt else _OBJ[m.end():]
    blk = strip(blk)
    w = re.findall(r'^weight=(-?\d+)kg$', blk, re.M)
    r = re.findall(r'^param=energy_restore,(\d+)$', blk, re.M)
    if len(w) != 1 or len(r) != 1:
        return None, None
    return int(w[0]) * 1000, int(r[0])

_GCFG = {g: _gobj(g) for g in _GRACE_PIECES}

# THE SPEC HAS TO ADD UP BEFORE IT IS WORTH COMPARING ANYTHING TO IT. Its own claimed total is
# checked against its own per-piece numbers, so a spec edited in one field alone is caught here
# rather than making every check below wrong in the same direction.
_swant = _GSPEC['result']['per_piece_pct']
check(sorted(_swant) == sorted(_GRACE_PIECES),
      'the spec names all six Graceful pieces and nothing else: %s'
      % (sorted(set(_swant) ^ set(_GRACE_PIECES)) or 'exactly the six'))
check(sum(_swant.values()) == _GSPEC['result']['total_pct'],
      "the spec's per-piece numbers add up to the total it claims, so its own arithmetic is not "
      'taken on trust: %s against %s' % (sum(_swant.values()), _GSPEC['result']['total_pct']))
check(_GSPEC['result']['total_pct'] == 50,
      'and that total is the 50 percent Corey asked for by name, not OSRS\'s %s: %s'
      % (_GSPEC['osrs']['full_set_total_pct'], _GSPEC['result']['total_pct']))
check(_GSPEC['osrs']['full_set_total_pct'] == 30
      and sum(_GSPEC['osrs']['per_piece_pct'].values()) == 20,
      'with OSRS\'s own figures recorded beside it as the thing being departed from - 20 per '
      'piece and 30 for the set, off the wiki: %s and %s'
      % (sum(_GSPEC['osrs']['per_piece_pct'].values()), _GSPEC['osrs']['full_set_total_pct']))

# THE CONFIGS AGREE WITH THE SPEC, piece by piece. Named per piece rather than as one total,
# because two pieces swapped would leave the total right and the outfit wrong.
_gbad = ['%s: config %s, spec %s' % (g, _GCFG[g][1], _swant[g])
         for g in _GRACE_PIECES if _GCFG[g][1] != _swant[g]]
check(not _gbad,
      "each piece's energy_restore in outfits.obj is the number the spec derived for it: %s"
      % (_gbad[:3] or 'all six agree'))
check(all(v[1] is not None for v in _GCFG.values())
      and sum(v[1] for v in _GCFG.values()) == _GSPEC['result']['total_pct'],
      'and the six together come to the full-set total, read out of the config: %s'
      % (sum(v[1] for v in _GCFG.values() if v[1] is not None)))

# THE SHAPE, checked off the config's OWN weight lines rather than off the spec. This is the
# tie-break that decided which of the four 3%-in-OSRS pieces take 8 and which take 7, and it is
# the reason that choice is a property and not a preference: a bigger weight reduction never
# recovers less, and two pieces that reduce the same weight recover the same.
_pairs = [(w, r, g) for g, (w, r) in _GCFG.items() if w is not None]
check(len(_pairs) == 6, 'all six Graceful blocks carry one weight= and one energy_restore line, '
                        'so the shape below is read off the file: %d of 6' % len(_pairs))
_mono = [(a[2], b[2]) for a in _pairs for b in _pairs
         if a[0] < b[0] and a[1] < b[1]]          # a takes MORE weight off but recovers LESS
check(not _mono,
      'recovery never goes down as the weight reduction goes up, which is OSRS\'s own ordering '
      'at a finer grain: %s' % (_mono[:3] or 'monotonic across all six'))
_ties = [(a[2], b[2]) for a in _pairs for b in _pairs
         if a[0] == b[0] and a[1] != b[1] and a[2] < b[2]]
check(not _ties,
      'and two pieces that take the same weight off recover the same, so nothing was decided by '
      'taste: %s' % (_ties[:3] or 'every tie matched'))

# THE WEIGHTS ARE STILL OSRS'S. This round changed the recovery and nothing else, and -25kg is
# the number the earlier round took off the wiki.
_wbad = ['%s: config %s, OSRS %s' % (g, _GCFG[g][0], int(_GSPEC['osrs']['weight_kg'][g] * 1000))
         for g in _GRACE_PIECES if _GCFG[g][0] != int(_GSPEC['osrs']['weight_kg'][g] * 1000)]
check(not _wbad,
      "every piece's weight= is still exactly OSRS's, because this round changed the recovery and "
      'nothing else: %s' % (_wbad[:3] or 'all six unchanged'))

# NOBODY ELSE CARRIES THE PARAM, config-side. The artefact check says the same thing about the
# packed table; this one still answers when there is no packed table to read.
# WALK THE TREE, not this battery's own FILES list - src{} is a fixed handful and "no other obj
# carries it" is a claim about every .obj there is.
def _walk(ext):
    for _root, _dirs, _files in os.walk(os.path.join(C, 'scripts')):
        for _fn in _files:
            if _fn.endswith(ext):
                _fp = os.path.join(_root, _fn)
                yield os.path.relpath(_fp, C), strip(read(os.path.relpath(_fp, C)))

_allobj = {}
_objfiles = 0
for _rel, _t in _walk('.obj'):
    _objfiles += 1
    _cur = None
    for _line in _t.split('\n'):
        _m = re.match(r'^\[(\w+)\]$', _line)
        if _m:
            _cur = _m.group(1)
        elif _cur and re.match(r'^param=energy_restore,', _line):
            _allobj[_cur] = _rel
check(_objfiles > 1 and 'graceful_hood' in _allobj,
      'the sweep below actually walked the obj configs and found the Graceful pieces in them, so '
      'an empty result means nothing else carries the param rather than that nothing was read: '
      '%d files' % _objfiles)
# THE COLOUR VARIANTS ARE THE SAME SIX PIECES. graceful_colours.obj recolours all six nine times
# over, and a recolour is the base piece in another colour - same model, same weight, same
# energy_restore. Counting them as "another obj carrying the param" was wrong; letting anything
# named graceful_* carry it would be wrong the other way, since a variant whose numbers drifted
# from its base would pay more in Varrock's colours than in Draynor's. So they are checked against
# their base rather than exempted, and the packed-table half of this is in tools/objpacked.py.
_vbase = {n: b for n in _allobj for b in _GRACE_PIECES if n != b and n.startswith(b + '_')}
_extra = sorted(n for n in _allobj if n not in _GRACE_PIECES and n not in _vbase)
check(not _extra,
      'and no obj config in the tree carries energy_restore but the six and their colours, so the '
      'bonus cannot be picked up from something unintended: %s' % (_extra[:5] or 'the six and their colours'))
_CFGS = {}
for _rel, _t in _walk('.obj'):
    _cur = None
    for _line in _t.split('\n'):
        _m = re.match(r'^\[(\w+)\]$', _line)
        if _m:
            _cur = _m.group(1)
        elif _cur and re.match(r'^(weight|param=energy_restore)=?', _line) and '=' in _line:
            _k, _v = _line.split('=', 1)
            if _k == 'weight':
                _CFGS.setdefault(_cur, {})['weight'] = _v.strip()
            elif _line.startswith('param=energy_restore,'):
                _CFGS.setdefault(_cur, {})['pct'] = _line.split(',', 1)[1].strip()
check(len(_vbase) >= 6,
      'the obj configs carry the Graceful colour variants, so the comparison below is against '
      'something rather than against an empty list: %d' % len(_vbase))
_vdrift = ['%s %s, %s has %s' % (n, _CFGS.get(n, {}).get(k), b, _CFGS.get(b, {}).get(k))
           for n, b in sorted(_vbase.items()) for k in ('weight', 'pct')
           if _CFGS.get(n, {}).get(k) != _CFGS.get(b, {}).get(k)]
check(not _vdrift,
      "and each colour carries its base piece's weight and energy_restore exactly: %s"
      % (_vdrift[:3] or 'all %d match their base' % len(_vbase)))

# THE DEPARTURE IS WRITTEN DOWN WHERE SOMEBODY WOULD LOOK, and says both numbers. A departure
# this size that is only in a spec file is a departure nobody reading the configs will find.
_GCONST = read('scripts/skilling_outfits/configs/outfits.constant')
check('50%' in _GCONST and '30%' in _GCONST and 'DEPARTURE' in _GCONST,
      "outfits.constant's Graceful note says what this build pays and what OSRS pays, and calls "
      'the difference a departure')
check('+50%' in OEFF and '30%' in OEFF.split('GRACEFUL IS NOT IN THIS FILE', 1)[0],
      'and the header of outfit_effects.rs2, which lists what the three unpaid outfits give '
      'instead, carries the same two numbers')
check('gracefulspec.json' in _GCONST,
      'and points at the spec that holds the arithmetic, so the next person changing the number '
      'finds the reasoning rather than re-deriving it')

# AND IT IS STILL NOT A SCRIPT. The check above says no piece is NAMED in outfit_effects.rs2;
# this one says the param itself is read by no rs2 anywhere - the moment a script reads it, the
# engine has stopped being the only thing that knows the number.
_rs2files = 0
_ineff = []
for _rel, _t in _walk('.rs2'):
    _rs2files += 1
    if 'energy_restore' in _t:
        _ineff.append(_rel)
_ineff.sort()
check(_rs2files > 100,
      'and that sweep read the whole script tree rather than a handful, so the result below means '
      'something: %d .rs2 files' % _rs2files)
check(not _ineff,
      'and no script anywhere reads energy_restore - it is the engine\'s number, and a script '
      'reading it would be a second place for it to drift: %s'
      % ([os.path.basename(f) for f in _ineff][:3] or 'no script reads it'))

# ASK THE ARTEFACT, NOT THE CONFIG. tools/objpacked.py decodes data/pack/server/obj.dat - the file
# the server loads - and checks the six weights and params there. The config saying weight=-3kg
# is not evidence that a negative weight survives p2; this is. It needs a build to have run.
_op = _sp.run([sys.executable, os.path.join(C, 'tools/objpacked.py')],
              capture_output=True, text=True, cwd=C)
check(_op.returncode == 0,
      "the packed obj table agrees about Graceful's weights and its energy_restore params, read "
      'out of the artefact the server loads rather than the config it was built from'
      # INCLUDE THE "nothing to read" LINE, not just the FAIL lines. objpacked exits 2 with a
      # plain sentence when the packed table or a generated pack file is not there - which is
      # every fresh clone before a build - and without this the battery printed a FAIL with an
      # empty explanation and read like a real disagreement about the numbers.
      + ('' if _op.returncode == 0 else ':\n' + '\n'.join(
          l for l in _op.stdout.split('\n')
          if 'FAIL' in l or l.startswith('no '))[:400]))

# ---- GRACEFUL: and the engine end of it
# The engine clone is a sibling, under either of the two names it goes by. If it is not there this
# FAILS rather than skipping: a check that quietly passes when it could not look is the certcheck.ts
# mistake, and it is worse than no check.
_EROOTS = ([os.environ['LOSTCITY_ENGINE']] if os.environ.get('LOSTCITY_ENGINE') else []) \
    + [os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')]
_ENG = next((os.path.join(r, 'src/engine/entity/Player.ts') for r in _EROOTS
             if os.path.exists(os.path.join(r, 'src/engine/entity/Player.ts'))), None)
check(_ENG is not None,
      'the engine source is reachable, so the half of Graceful that lives in it can be checked '
      'at all rather than skipped: tried %s' % ', '.join(_EROOTS))
if _ENG:
    _PL = open(_ENG, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    check("ParamType.getId('energy_restore')" in _PL,
          'the engine reads the bonus from the energy_restore param by name, so it knows nothing '
          'about which outfit a piece belongs to')
    check(re.search(r'if \(inv\.type === InvType\.WORN && restoreParam !== -1\) \{\s*\n\s*'
                    r'this\.runrestore \+= ParamHelper\.getIntParam', _PL),
          'and sums it over WORN equipment only, so carrying a piece in your pack does nothing')
    check('this.runrestore = 0;' in _PL and 'calculateRunWeight() {' in _PL
          and 'this.runrestore = 0;' in _PL.split('calculateRunWeight() {', 1)[1].split('\n    }', 1)[0],
          'recomputed inside calculateRunWeight, which is the function that already runs at every '
          'moment worn equipment changes, so the number cannot go stale')
    check(re.search(r'const recovered = natural \+ \(\(\(natural \* this\.runrestore\) / 100\) \| 0\);', _PL),
          'and applied to the natural recovery as a whole-percent scale of it')
    # THE ONE PLACE IT MUST NOT BE APPLIED, and the handler lives in a different file - the first
    # version of this check looked in Player.ts, found the word HEALENERGY in the COMMENT saying
    # the bonus does not belong there, and went red on correct code. A check has to read the thing
    # it is talking about.
    _OPS = os.path.join(os.path.dirname(_ENG), '../script/handlers/PlayerOps.ts')
    check(os.path.exists(_OPS),
          'the HEALENERGY handler is where it can be read, so the next check is about code')
    if os.path.exists(_OPS):
        _PO = open(_OPS, encoding='utf-8', newline='').read().replace('\r\n', '\n')
        _hbody = _PO.split('[ScriptOpcode.HEALENERGY]', 1)[1].split('\n    },', 1)[0]
        check('runrestore' not in _hbody,
              'but an energy potion is not scaled by it, because a potion is not you catching '
              'your breath')

    # AND A MODEL OF THE TWO BRANCHES, so the in-game check has numbers rather than a feeling.
    # tools/gracefulsim.py quotes all four lines of updateEnergy()'s arithmetic and refuses to
    # print anything if any of them has moved, so a zero exit here is a statement about the
    # engine's current source and not about a copy of it made once.
    _gs = _sp.run([sys.executable, os.path.join(C, 'tools/gracefulsim.py')],
                  capture_output=True, text=True, cwd=C,
                  env=dict(os.environ, LOSTCITY_ENGINE=os.path.dirname(
                      os.path.dirname(os.path.dirname(os.path.dirname(_ENG))))))
    check(_gs.returncode == 0,
          "gracefulsim.py still recognises every line of updateEnergy() it models, so the tick "
          'counts the in-game check compares against are the ones this engine produces'
          + ('' if _gs.returncode == 0 else ': ' + (_gs.stdout.strip().split('\n') or [''])[0][:200]))

# ---- ROGUE OUTFIT: doubled pickpocket loot
_after = strip(THIEF).split('[proc,pick_pocket_check_for_reward]', 1)[1].split('\n[', 1)[0]
check('~rogue_doubles' in _after and strip(THIEF).count('~rogue_doubles') == 1,
      'a pickpocket asks the Rogue outfit whether its loot doubles, and it is the only thing that '
      'asks - so stalls, chests and trapped chests are untouched the way OSRS leaves them')
check('* $multiplier' in _after and _after.count('~rogue_doubles') == 1,
      'the roll happens once for the theft rather than once per item in the pocket')
_rw = OEFF_CODE.split('[proc,rogue_worn]', 1)[1].split('\n[', 1)[0]
_RSLOT = {'rogue_mask': 'hat', 'rogue_top': 'torso', 'rogue_trousers': 'legs',
          'rogue_gloves': 'hands', 'rogue_boots': 'feet'}
_rbad = [p for p, sl in _RSLOT.items()
         if 'inv_getobj(worn, ^wearpos_%s) = %s' % (sl, p) not in _rw]
check(not _rbad,
      'all five Rogue pieces are counted, each looked for in the slot it is actually worn in: %s'
      % (_rbad or 'all five'))
_rc = OEFF_CODE.split('[proc,rogue_double_chance]', 1)[1].split('\n[', 1)[0]
check('^rogue_full_pieces' in _rc and '^rogue_double_full' in _rc
      and '^rogue_double_pct' in _rc,
      "the fifth piece is worth more than the other four: the full set returns its own constant "
      'rather than five times the per-piece one')
check(not re.search(r'random\(\d+\)\s*<\s*\d', OEFF_CODE),
      'and no chance in this file is a bare number against a bare number')

# ---- ZEALOT'S ROBES: the remains may survive
_zs = OEFF_CODE.split('[proc,zealots_saves]', 1)[1].split('\n[', 1)[0]
_ZSLOT = {'zealots_helm': 'hat', 'zealots_top': 'torso', 'zealots_bottom': 'legs',
          'zealots_boots': 'feet'}
_zbad = [p for p, sl in _ZSLOT.items()
         if 'inv_getobj(worn, ^wearpos_%s) = %s' % (sl, p) not in _zs]
check(not _zbad,
      "every Zealot's piece is looked for in its own slot: %s" % (_zbad or 'all four'))
check(_zs.count('random(^zealots_save_denom)') == 4,
      'and each of them rolls separately, which is what makes the set a shade under five percent '
      'instead of exactly five: %s rolls' % _zs.count('random(^zealots_save_denom)'))

# BOTH bone paths, and the experience paid either way. The altar one is GENERATED, so the check is
# on the generator as well - a hand edit to poh_furn_ops.rs2 is undone by the next regenerate.
for _lbl, _txt in (('burying a bone', BURY), ('offering one at the altar', FURNOPS)):
    _t = strip(_txt)
    check('~zealots_saves' in _t,
          "Zealot's robes get their chance when %s" % _lbl)
    check(re.search(r'if \(\$saved = false\) \{\s*\n\s*inv_del', _t),
          'and the remains are only used up when they did not save it, %s' % _lbl)
    check(re.search(r'\n~prayer_xp|\n\s*~prayer_xp', _t) and not re.search(
              r'if \(\$saved = false\) \{[^}]*~prayer_xp', _t, re.S),
          'while the experience is paid whichever way it went, %s' % _lbl)
check('~zealots_saves' in GENFURN,
      'and genfurn.py is what writes the altar call, so a regenerate keeps it')


print('65. the checkers can go red')

# A CHECK THAT CANNOT FAIL IS WORSE THAN NO CHECK: it reads as coverage and is not. Two rules in
# rs2check.py have shipped inert - check 11 read its line variable one statement early and reported
# every hit one line late, and check 17 matched a block header with a pattern a header never
# satisfies - and the repo printed 0 ERROR through both. The same week, group 48's magic stone
# price check compared the price against the number I had written down, and group 62's "More
# sets..." check passed on a proc that wrapped to the wrong set.
#
# rs2check --selftest now builds a miniature content tree, breaks one thing per rule, and asserts
# every rule fires ON THE RIGHT LINE and none fires on correct code. This runs it, so it cannot be
# forgotten - and so "0 ERROR" means sixteen rules looked, not that sixteen rules exist.
_st = _sp.run([sys.executable, os.path.join(C, 'tools/rs2check.py'), '--selftest'],
              capture_output=True, text=True, cwd=os.path.join(C, 'scripts'))
_last = [l for l in _st.stdout.strip().split('\n') if l.startswith('selftest:')]
check(_st.returncode == 0, 'rs2check --selftest: %s'
      % (_last[0][10:] if _last else (_st.stdout + _st.stderr)[-200:]))
# The count comes from the tool's own ALL_RULES rather than a number written here, so adding a
# rule does not need this edited - and a rule quietly disappearing still fails, because the two
# have to agree.
_declared = len(re.findall(r'^    (?:\d+|"\w+"):\s+\("', read('tools/rs2check.py'), re.M))
_fired = re.findall(r'^  rule (\S+)\s+fired', _st.stdout, re.M)
check(_declared > 0 and len(_fired) == _declared,
      'every rule rs2check declares fired: %d of %d' % (len(_fired), _declared))
check('DID NOT FIRE' not in _st.stdout, 'and none of them is inert')
check('FALSE POSITIVE' not in _st.stdout, 'and none of them fires on correct code')

# the guard that makes a missing pack loud rather than silent. Rules 14 and 14b read
# `known = T["packs"].get(pack)` and then `if known and ...`, so an absent synth.pack disables
# every sound_synth check in the repo and the tool still prints 0 ERROR.
# Checked by RUNNING it with a pack taken away, not by reading the source for the message - the
# first version of this check read the text, and a mutation that turned the guard off without
# touching the message walked straight past it.
import tempfile as _tf, shutil as _sh
_gd = _tf.mkdtemp(prefix='rs2check_packguard_')
try:
    _sh.copytree(os.path.join(C, 'scripts'), os.path.join(_gd, 'scripts'),
                 ignore=_sh.ignore_patterns('*.rs2', '*.dbrow', '*.obj', '*.npc', '*.loc',
                                            '*.inv', '*.varp', '*.varbit', '*.constant'))
    _sh.copyfile(os.path.join(C, 'scripts/engine.rs2'), os.path.join(_gd, 'scripts/engine.rs2'))
    os.makedirs(os.path.join(_gd, 'pack'))
    for _f in os.listdir(os.path.join(C, 'pack')):
        if _f.endswith('.pack') and _f != 'synth.pack':
            _sh.copyfile(os.path.join(C, 'pack', _f), os.path.join(_gd, 'pack', _f))
    _sh.copyfile(os.path.join(C, 'tools/rs2check.py'), os.path.join(_gd, 'rs2check.py'))
    _g = _sp.run([sys.executable, os.path.join(_gd, 'rs2check.py')],
                 capture_output=True, text=True, cwd=os.path.join(_gd, 'scripts'))
finally:
    _sh.rmtree(_gd, ignore_errors=True)
check(_g.returncode != 0 and 'synth.pack is missing or empty' in (_g.stdout + _g.stderr),
      'with synth.pack taken away it STOPS rather than printing 0 ERROR: %s'
      % ((_g.stdout + _g.stderr).strip().split(chr(10))[-1][:70] or 'no output'))


print('66. the slayer imbues')

# The imbued pair are the plain pair with one thing changed, so every check here is a COMPARISON
# against the plain item rather than a number written down twice. The exception is the price, which
# is not derivable from anything - OSRS charges 1,250,000 Nightmare Zone points and there is no
# Nightmare Zone - so it is a constant, and the check is that it is a constant.
_SL = read('scripts/skill_slayer/scripts/black_mask.rs2')
_HL = read('scripts/skill_slayer/scripts/slayer_helm.rs2')
_RW = read('scripts/skill_slayer/scripts/slayer_rewards.rs2')
_IOBJ = blocks(read('scripts/skill_slayer/configs/black_mask.obj'))
_IOBJ.update(blocks(read('scripts/general/configs/osrs_items.obj')))

# WHICH IMBUED TWIN SHARES ITS PARENT'S ART IS NOT A RULE - it is two different answers, and the
# cache is the authority. OSRS's Black mask (i), obj 11784, is model 15615, the same as the plain
# mask; its Slayer helmet (i), obj 11865, is model 42702 where the plain one is 42707 - a grey eye
# instead of a red one. This check shipped asserting the first answer for both, which is how the
# imbued helmet spent a round wearing the wrong model.
for _a, _b, _shares in (('black_mask', 'black_mask_i', True),
                        ('slayer_helm', 'slayer_helm_i', False)):
    check(_b in OBJS, '%s has an id in obj.pack' % _b)
    _p, _i = _IOBJ.get(_a, {}), _IOBJ.get(_b, {})
    _same = (_p.get('model') == _i.get('model') and _p.get('manwear') == _i.get('manwear'))
    check(_same == _shares,
          '%s %s the plain item\'s models, which is what the OSRS cache does'
          % (_b, 'reuses' if _shares else 'has its own, not'))
    _pd = {k: v for k, v in _p.items() if k == 'param'}
    _defs = lambda d: sorted(x for x in (d.get('param') or []) if 'defence' in x)
    check(_defs(_p) == _defs(_i), '%s keeps the plain item\'s defences exactly: %s'
          % (_b, _defs(_i) if _defs(_i) == _defs(_p) else (_defs(_p), _defs(_i))))

# the two stat differences, both read off the wiki rather than assumed
#
# THE MASK'S IMBUE KEEPS ITS PENALTIES, and this check used to assert the opposite. The imbued mask
# shipped without the plain one's -3 magic attack and -1 ranged attack, which made imbuing a mask a
# quiet upgrade to those two stats; that was item 3 of 17981c26 ("Black mask (i), found by the same
# sweep, was missing the plain mask's -3 magic attack and -1 ranged attack") and the config has
# carried them since 2026-10-03. The check went on asking for the bug. An imbue buys the damage
# bonus on task, not a better helmet, so the two must match exactly - which is the stronger
# statement and the one made here.
_atk = lambda n: sorted(x for x in (_IOBJ.get(n, {}).get('param') or []) if 'attack' in x)
check(_atk('black_mask') == ['magicattack,-3', 'rangeattack,-1']
      and _atk('black_mask_i') == _atk('black_mask'),
      'the imbue KEEPS the mask\'s attack penalties, so it is not a stat upgrade (plain %s, '
      'imbued %s)' % (_atk('black_mask'), _atk('black_mask_i')))
check(_atk('slayer_helm') == [] and _atk('slayer_helm_i') == ['magicattack,3', 'rangeattack,3'],
      'and ADDS +3 magic and +3 ranged attack to the helmet: %s' % _atk('slayer_helm_i'))

# ONE DOOR PER INHERITANCE, and each reads a PARAM rather than listing names - which is what makes
# the eight call sites elsewhere need no edit, and what made adding two recoloured helmets in the
# round after this one cost no change here at all. The doors were a list of four when this group
# was written; group 67 is where the param table is checked, and this is the half that matters
# here: the imbued items are marked imbued and the plain ones are not.
_door = _SL.split('[proc,black_mask_on_task]', 1)[1].split('\n[', 1)[0]
check('oc_param($hat, slayer_headgear)' in _door,
      'the melee bonus door asks what the item IS, not which item it is')
_worn = _HL.split('[proc,slayer_helm_worn]', 1)[1].split('\n[', 1)[0]
check('oc_param($hat, slayer_helmet)' in _worn,
      'and the protections door does the same')
_users = 0
for _root, _dirs, _fs in os.walk(os.path.join(C, 'scripts')):
    for _fn in _fs:
        if _fn.endswith('.rs2'):
            _users += len(re.findall(r'~slayer_helm_worn', read(os.path.join(_root, _fn)[len(C) + 1:])))
check(_users >= 8, 'and %d call sites inherit it without naming an item themselves' % _users)

# the imbued-only proc shares the on-task test rather than repeating it
_imb = _SL.split('[proc,black_mask_imbued_on_task]', 1)[1].split('\n[', 1)[0]
check('~black_mask_on_task' in _imb,
      'the ranged/magic door reuses the melee door\'s on-task test, so they cannot drift')
# ...and the set of things it answers true for is whatever carries slayer_imbued. Which items
# those are is group 67's business; what matters here is that the PLAIN pair do not carry it, so
# buying the imbue actually buys something.
check('oc_param($hat, slayer_imbued)' in _imb, 'and asks only whether the item is imbued')
_pl = blocks(read('scripts/skill_slayer/configs/black_mask.obj'))
_pl.update(blocks(read('scripts/general/configs/osrs_items.obj')))
_wrong = [k for k in ('black_mask', 'slayer_helm')
          if any('slayer_imbued' in v for v in (_pl.get(k, {}).get('param') or []))]
check(not _wrong, 'and neither plain item claims to be imbued: %s' % (_wrong or 'correct'))

# 15% = 23/20, in both combat paths, on the roll AND the max hit
for _f, _label in (('scripts/skill_combat/scripts/player/player_ranged.rs2', 'ranged'),
                   ('scripts/skill_combat/scripts/player/player_magic.rs2', 'magic')):
    _t = read(_f)
    check('~black_mask_imbued_on_task' in _t, 'the %s path asks about the imbue' % _label)
    check('$mask_num = 23;' in _t and '$mask_div = 20;' in _t,
          '...at 23/20, which is the 15%% OSRS gives (%s)' % _label)
    check('~player_npc_hit_roll_boosted(' in _t and '~player_npc_hit_roll(' not in _t,
          '...on every roll in the file, not some of them (%s)' % _label)
    check('scale($mask_num, $mask_div,' in _t, '...and on the max hit too (%s)' % _label)
# every block that reads $mask_num declares it - the mistake made writing this round, where a
# multi-target proc read the single-target cast's local
# Written first with an `or True` on the end, which made it unfailable - the exact thing group 65
# exists to stop, committed forty lines under a comment about it. Counted properly now: every
# block that READS $mask_num must also DECLARE it, which is what the cross-proc mistake broke.
_bad66 = []
for _f66 in ('scripts/skill_combat/scripts/player/player_magic.rs2',
             'scripts/skill_combat/scripts/player/player_ranged.rs2',
             'scripts/skill_combat/scripts/player/player_melee.rs2'):
    for _blk in re.split(r'\n(?=\[)', read(_f66)):
        if '$mask_num' in _blk and 'def_int $mask_num' not in _blk:
            _bad66.append((_f66.split('/')[-1], _blk.split(chr(10))[0][:40]))
check(not _bad66, 'every block that reads $mask_num declares it: %s'
      % (_bad66 or 'all four'))
check(_sp.run([sys.executable, os.path.join(C, 'tools/rs2check.py')],
              capture_output=True, text=True,
              cwd=os.path.join(C, 'scripts')).returncode == 0,
      '...which rule 18 is what proves, and it is green')

# ---- THE SCROLL OF IMBUING replaced the 1,250-point service ----
#
# What made the old price checkable was that it was one constant spent in one place. What makes the
# scroll checkable is different and better: THE PAIRING IS DATA, so these checks walk the obj table
# rather than reading a script. A pair that only points one way is the one mistake this shape can
# make, and it is the first check below.
_SC = read('scripts/skill_slayer/configs/slayer.constant')
_RE = read('scripts/skill_slayer/configs/slayer_rewards.enum')
_IS = read('scripts/skill_slayer/scripts/imbue_scroll.rs2')
check(not re.search(r'\^slayer_imbue_cost|\^slayer_buy_imbue|slayer_do_imbue', _SC + _RW),
      'the points imbue is gone: no price constant, no Buy row constant, no purchase proc')

# Every obj in the tree, so the pairing is checked against ALL of it and not against a list of the
# items this round happened to think of.
_ALLOBJ = {}
for _root66, _d66, _fs66 in os.walk(os.path.join(C, 'scripts')):
    for _fn66 in _fs66:
        if _fn66.endswith('.obj'):
            _ALLOBJ.update(blocks(read(os.path.join(_root66, _fn66)[len(C) + 1:])))
_param66 = lambda n, k: next((v.split(',', 1)[1] for v in (_ALLOBJ.get(n, {}).get('param') or [])
                              if v.startswith(k + ',')), None)
_into = {n: _param66(n, 'imbue_into') for n in _ALLOBJ if _param66(n, 'imbue_into')}
_from = {n: _param66(n, 'imbue_from') for n in _ALLOBJ if _param66(n, 'imbue_from')}
_oneway = ([('%s -> %s, which has no imbue_from back' % (a, b)) for a, b in _into.items()
            if _from.get(b) != a]
           + [('%s <- %s, which has no imbue_into out' % (a, b)) for b, a in _from.items()
              if _into.get(a) != b])
check(not _oneway,
      'every imbue pair points both ways - %d plain items naming their twin and the same %d twins '
      'naming them back: %s' % (len(_into), len(_from), _oneway or 'all paired'))
# ...and it is the whole list this build can have: the mask, the helmet and its fourteen colours,
# and the four Fremennik rings. Anything else with a param would be an item that can be imbued and
# was never thought about; anything missing would be one the scroll silently refuses.
# The magic shortbow is the one addition past OSRS's scroll list, asked for on 2026-09-21: OSRS
# imbues it with its own Nightmare Zone scroll, and this build has one scroll for everything.
_WANT66 = ({'black_mask', 'slayer_helm', 'berzerker_ring', 'warrior_ring', 'ranger_ring',
            'seer_ring', 'magic_shortbow'}
           | {n for n in _ALLOBJ
              if re.fullmatch(r'slayer_helm_[a-z]+', n) and n != 'slayer_helm_i'})
check(set(_into) == _WANT66,
      'and they are the %d items OSRS\'s scroll list leaves this build: %s'
      % (len(_WANT66), sorted(set(_into) ^ _WANT66) or 'exactly those'))

# THE FOUR RINGS DOUBLE THEIR OWN PLAIN RING, which is what the wiki says the imbue does - and
# doubled off THIS build's rings, not off OSRS's. OSRS's Seers ring (i) is +12/+12 because its
# plain ring is +6/+6; ours is +4/+4, so ours is +8/+8, and copying the 12 would have made the
# imbued ring three times the ring it is an imbue of. So this is a COMPARISON, like every other
# check in this group.
_stats66 = lambda n: {v.split(',')[0][6:]: int(v.split(',')[1])
                      for v in (_ALLOBJ.get(n, {}).get('param') or [])
                      if re.match(r'param=\w*(attack|defence|bonus),-?\d+$', 'param=' + v)}
_ringbad = []
for _r66 in ('berzerker_ring', 'warrior_ring', 'ranger_ring', 'seer_ring'):
    _pp, _ii = _stats66(_r66), _stats66(_r66 + '_i')
    if _ii != {k: v * 2 for k, v in _pp.items()} or not _pp:
        _ringbad.append((_r66, _pp, _ii))
check(not _ringbad, 'each imbued ring is its plain ring doubled, stat for stat: %s'
      % (_ringbad or 'all four'))
# ...and wears ITS OWN MESH. OSRS gives the four imbued rings models 21847-21850 where the plain
# rings are 9930-9933 - the same topology with a pale, silvered band. They shipped pointing at the
# plain rings' models, which is the same assumption that put the imbued slayer helmet in the plain
# helmet's art a round earlier: "the imbued twin looks the same" is not a rule, it is a lookup.
# blocks() gives every key as a LIST, so these compare against one-element lists - the same
# shape the model comparison at the top of this group uses.
_artbad = [_r66 for _r66 in ('berzerker_ring', 'warrior_ring', 'ranger_ring', 'seer_ring')
           if _ALLOBJ.get(_r66 + '_i', {}).get('model') != ['obj_%s_i' % _r66]
           or 'obj_%s_i' % _r66 not in MODELS]
check(not _artbad,
      'and wears its own imported mesh rather than the plain ring\'s: %s'
      % (_artbad or 'all four'))
# The cache also gives an imbued ring the PLAIN ring's examine text, word for word - so a "(i)"
# suffix or an invented "It has been imbued." sentence is a change the cache does not make.
_descbad = [_r66 for _r66 in ('berzerker_ring', 'warrior_ring', 'ranger_ring', 'seer_ring')
            if _ALLOBJ.get(_r66 + '_i', {}).get('desc') != _ALLOBJ.get(_r66, {}).get('desc')]
check(not _descbad, "...and the plain ring's examine text, which is what the cache does: %s"
      % (_descbad or 'all four'))

# UNCHARGING, AND WHICH ITEMS GET IT - which is the cache's answer and not "all of them". OSRS's
# Black mask (i) and its four imbued rings carry Uncharge; NOT ONE slayer helmet in the cache does,
# of any colour - all twenty-six are Wear / Check / Disassemble. A helmet is uncharged by taking it
# apart into its imbued mask and uncharging that, which this build already does. The first version
# of this round invented an iop5=Uncharge for fifteen helmets before anyone read the cache, so the
# check is now the set, spelled out, and the helmets' route checked separately.
_ALLRS2 = ''
for _root66, _d66, _fs66 in os.walk(os.path.join(C, 'scripts')):
    for _fn66 in _fs66:
        if _fn66.endswith('.rs2'):
            _ALLRS2 += read(os.path.join(_root66, _fn66)[len(C) + 1:])
_unch = set(re.findall(r'\[opheld\d,(\w+)\] @imbue_uncharge;', _ALLRS2))
_WANTUNCH = {'black_mask_i', 'berzerker_ring_i', 'warrior_ring_i', 'ranger_ring_i', 'seer_ring_i',
             'magic_shortbow_i'}  # the bow: this build's scroll comes back out of everything it imbues
check(_unch == _WANTUNCH,
      'Uncharge is on the five items the cache gives it to - the mask and the four rings - and on '
      'nothing else: %s' % (sorted(_unch ^ _WANTUNCH) or 'exactly those'))
# ...and the op sits in the slot the cache puts it in, which is 4, with 3 left empty
_slots66 = set(re.findall(r'\[opheld(\d),\w+\] @imbue_uncharge;', _ALLRS2))
_iop66 = {n for n in _WANTUNCH if _ALLOBJ.get(n, {}).get('iop4') == ['Uncharge']}
check(_slots66 == {'4'} and _iop66 == _WANTUNCH,
      '...in op slot 4, where OSRS puts it, and the trigger is on the same slot as the op: %s'
      % (sorted(_WANTUNCH - _iop66) or 'all five'))
# THE HELMETS' ROUTE OUT. No Uncharge op, so the scroll comes back out of a helmet the way OSRS
# does it: Disassemble hands the imbued mask back, and the mask is what uncharges. Both halves of
# that already exist and are checked below - this is the check that the helmets have not quietly
# been left with no route at all.
_helms66 = sorted(n for n in _from if n.startswith('slayer_helm'))
_hasop = [n for n in _helms66
          if any(v == ['Uncharge'] for v in _ALLOBJ.get(n, {}).values())]
# 16 since 12 October: the Gravedigger, the Undertaker's ornament kit result, which is a helmet
# like any other and carries the imbue pairing like any other
check(len(_helms66) == 16 and not _hasop and '[opheld4,slayer_helm_i]' in _HL,
      'and no imbued helmet has one - all %d get the scroll back out through Disassemble, which is '
      'what the cache says and what OSRS does: %s' % (len(_helms66), _hasop or 'none of them'))
# ONE TRIGGER ON THE SCROLL, not twenty on the items - but an imbueable item may already have an
# [opheldu] of its own, and then the engine finds THAT one when the item is the clicked half
# (network/game/client/handler/OpHeldUHandler.ts looks the trigger up on the clicked obj first).
# The black mask has one, for assembling a slayer helmet, and this check is what found it: without
# a handoff the scroll worked in one click order and said "nothing interesting happens" in the
# other. So the claim is not "no item has one" - it is that any item which does hands the scroll
# on, which is checkable by following the trigger to its body.
_shadow = []
for _n66 in _into:
    _m = re.search(r'\[opheldu,%s\](?: @(\w+);)?' % _n66, _ALLRS2)
    if not _m:
        continue
    _body = (_ALLRS2.split('[label,%s]' % _m.group(1), 1)[1].split('\n[', 1)[0]
             if _m.group(1) else _ALLRS2[_m.end():].split('\n[', 1)[0])
    if 'slayer_imbue_scroll' not in _body:
        _shadow.append(_n66)
check('[opheldu,slayer_imbue_scroll]' in _IS and not _shadow,
      'the use is one trigger on the scroll, and the one imbueable item with an [opheldu] of its '
      'own hands the scroll on rather than swallowing it: %s'
      % (_shadow or 'black_mask does'))
# and the two procs read the param rather than naming a pair - which is what makes the fourteen
# colours cost this file nothing
check('oc_param($target, imbue_into)' in _IS and 'oc_param($item, imbue_from)' in _IS
      and not re.search(r'(?m)^\s*(if|switch).*black_mask', _IS),
      'and both halves read the param, so no pair is named in the script')
# ...and an item that is already imbued is TOLD so. "Nothing interesting happens" on a black mask
# (i) is the one wrong target a player will actually pick, and with a drop this rare, leaving them
# unsure whether the scroll was spent is worse than the wasted click.
check('is already imbued.")' in _IS and 'oc_param($target, imbue_from)' in _IS,
      'and an item that is already imbued says so rather than nothing interesting happening')

# WHERE IT COMES FROM. Weighted by hitpoints, not flat per kill: flat would make Turael's rats the
# fastest scroll farm in the game, which is the mistake ^bottomless_roll_xp exists not to make.
_TK = read('scripts/skill_slayer/scripts/slayer_task.rs2')
_SUP66 = read('scripts/skill_slayer/scripts/superiors.rs2')
check(re.search(r'random\(\^imbue_scroll_hitpoints\) >= npc_basestat\(hitpoints\)', _IS)
      is not None,
      'the drop is weighted by the kill\'s hitpoints, the same quantity the kill pays Slayer xp for')
_q66 = [_b for _b in re.split(r'\n(?=\[)', _TK)
        if _b.startswith('[queue,progress_task]') or _b.startswith('[queue,progress_task_split]')]
check(len(_q66) == 2 and all('~imbue_scroll_kill_roll' in _b for _b in _q66),
      'and it is rolled from both on-task kill queues - the whole kill and the split one - and '
      'from nowhere else: %d of 2, %d calls in the tree'
      % (sum('~imbue_scroll_kill_roll' in _b for _b in _q66),
         _ALLRS2.count('~imbue_scroll_kill_roll;')))
check(_ALLRS2.count('~imbue_scroll_kill_roll;') == 2,
      '...so an off-task kill can never give one')
check('~imbue_scroll_superior_roll;' in _SUP66
      and re.search(r'random\(\^imbue_scroll_superior_odds\) ! 0', _IS) is not None,
      'a superior rolls a flat rate of its own on top of that, which is what makes it an '
      'increased rate rather than just a bigger monster')
_r66a = re.search(r'^\^imbue_scroll_hitpoints\s*=\s*(\d+)\s*$', _SC, re.M)
_r66b = re.search(r'^\^imbue_scroll_superior_odds\s*=\s*(\d+)\s*$', _SC, re.M)
check(_r66a and _r66b and not re.search(r'\b(%s|%s)\b' % (_r66a.group(1), _r66b.group(1)), _IS),
      'both rates are constants and neither value is written again in the script: %s'
      % ((_r66a.group(1) if _r66a else '?') + ' hitpoints, 1/' + (_r66b.group(1) if _r66b else '?')))

# assembly carries the imbue in both directions - a helmet built from an imbued mask is imbued,
# and taking it apart gives the imbued mask back rather than spending what was paid for
check('[proc,slayer_helm_mask]' in _HL and 'inv_del(inv, $mask, 1);' in _HL,
      'assembly uses whichever mask is in the pack')
check('$helm = slayer_helm_i;' in _HL, '...and an imbued mask makes an imbued helmet')
check('[opheld4,slayer_helm_i] @slayer_helm_split(black_mask_i);' in _HL
      and '[opheld4,slayer_helm] @slayer_helm_split(black_mask);' in _HL,
      'and disassembly hands back the mask that went in')
check(_HL.count('[label,slayer_helm_split]') == 1 and _HL.count('[label,slayer_helm_check]') == 1,
      'both helmets share one Check and one Disassemble body')

# and the sweep agrees they can be got
_sw66 = _sp.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
                capture_output=True, text=True, cwd=C)
# BOTH of the sweep's lists. The first version read only "nothing anywhere mentions these", and an
# item that stopped being given out but was still named by its own config and its own triggers
# lands in the OTHER list - which is the softer, easier-to-miss half, and exactly what a broken
# imbue would look like.
_both66 = _sw66.stdout.split('NOTHING ANYWHERE MENTIONS THESE', 1)[-1]
# NOTE: this rides on the sweep's loose half and has no mutation in poh_mutate.py - see the note
# there. It catches an item nothing references at all, which is the shape the 47 skilling outfit
# pieces were in; it cannot catch a circular source, because the sweep does not follow calls.
check(not re.search(r'\bblack_mask_i\b|\bslayer_helm_i\b', _both66),
      'tools/obtainable.py finds a real source for both imbued items, not just a mention')


print('67. every slayer helmet colour, with OSRS\'s own art')

# Fourteen colours, each in a plain and an imbued form. The FIRST version of this round made a
# colour by putting two recolour pairs on the plain helmet's model, which only repainted the mask
# and the strap; OSRS's variants are separately authored meshes. So the checks below are about
# ART IDENTITY - that each colour really carries its own imported models and not the plain
# helmet's - and about everything that is NOT art still being inherited unchanged.

import subprocess as _sp67
_HSPEC = _json.load(open(os.path.join(C, 'tools/slayerhelmspec.json')))
_kept67 = {f: open(os.path.join(C, f), 'rb').read() for f in (
    'scripts/skill_slayer/configs/slayer_helm_colours.obj',
    'scripts/skill_slayer/configs/slayer_helm.param',
    'scripts/skill_slayer/scripts/slayer_helm_colours.rs2',
    'pack/obj.pack')}
_r67 = _sp67.run([sys.executable, os.path.join(C, 'tools/genslayerhelm.py')],
                 capture_output=True, text=True, cwd=C)
check(_r67.returncode == 0, 'tools/genslayerhelm.py runs clean'
      + ('' if _r67.returncode == 0 else ': ' + (_r67.stdout + _r67.stderr)[-300:]))
_moved67 = [f for f in _kept67 if open(os.path.join(C, f), 'rb').read() != _kept67[f]]
for f in _moved67:
    open(os.path.join(C, f), 'wb').write(_kept67[f])
check(not _moved67, 're-running it changes nothing, obj.pack included: %s'
      % (_moved67 or 'byte-identical'))

_HOBJ = blocks(read('scripts/skill_slayer/configs/slayer_helm_colours.obj'))
_PLAIN = blocks(read('scripts/general/configs/osrs_items.obj'))
_COL = _HSPEC['colours']
_WITH = [c for c in _COL if 'source' in c]
_WITHOUT = [c for c in _COL if 'source' not in c]
_names67 = lambda c: ['slayer_helm_%s' % c['key'], 'slayer_helm_%s_i' % c['key']]
check(len(_HOBJ) == len(_COL) * 2 == 28,
      '%d helmets: one plain and one imbued for each of %d colours' % (len(_HOBJ), len(_COL)))
# THE NAMES ARE SPELLED OUT ON PURPOSE, so that a colour gaining a source is reviewed rather than
# absorbed. Black joined green and red when the King Black Bonnet unlock was added: a Kbd heads on
# a slayer helmet for 1,000 Slayer points, the head being the King Black Dragon's own 1/128 drop.
# The other eleven are in slayerhelmspec.json with no source block and nothing in this build drops
# their heads, which obtainable.py prints in its own section rather than filtering out.
check(len(_WITH) == 3 and sorted(c['key'] for c in _WITH) == ['black', 'green', 'red'],
      'three of them can be obtained - %s - and %d cannot'
      % (', '.join(sorted(c['key'] for c in _WITH)), len(_WITHOUT)))

# ---- everything that is not art is the plain helmet's, unchanged
_ART = ('model', 'manwear', 'womanwear', 'manhead', 'womanhead',
        '2dzoom', '2dxan', '2dyan', '2dxof', '2dyof', 'name', 'desc')
_bad = []
for _c in _COL:
    for _imb in (False, True):
        _k = 'slayer_helm_%s%s' % (_c['key'], '_i' if _imb else '')
        _d = _HOBJ.get(_k)
        _p = _PLAIN['slayer_helm_i' if _imb else 'slayer_helm']
        if _d is None:
            _bad.append((_k, 'missing')); continue
        if _k not in OBJS:
            _bad.append((_k, 'no id in obj.pack'))
        # iop5 is in the list because the imbued half inherits Uncharge and the plain half must
        # not have it: comparing against the plain source gets both halves right at once.
        for _f in ('wearpos', 'wearpos2', 'wearpos3', 'weight', 'cost', 'members', 'tradeable',
                   'category', 'iop2', 'iop3', 'iop4', 'iop5'):
            if _d.get(_f) != _p.get(_f):
                _bad.append((_k, '%s differs from the plain helmet' % _f))
        # slayer_, imbue_ and ornament_ params are per-item by design - what a colour IS, which
        # colour it imbues into, and which kit it takes. The ornament pair is the Undertaker's
        # Gravedigger kit, and gravedigger_kit.obj's header is explicit that the pairing lives on
        # the BASE item only: "what does this item become" has one answer, "what does this kit
        # make" does not. No coloured helmet takes the kit, so no coloured helmet carries the pair,
        # and comparing it against the plain helmet's would ask all 28 to. Everything else is the
        # plain helmet's, and that is what is compared.
        _skip66 = ('slayer_', 'imbue_', 'ornament_')
        _dp = sorted(x for x in (_d.get('param') or []) if not x.startswith(_skip66))
        _pp = sorted(x for x in (_p.get('param') or []) if not x.startswith(_skip66))
        if _dp != _pp:
            _bad.append((_k, 'combat params differ from the plain helmet'))
check(not _bad, 'each inherits every stat, op and gate from the plain helmet: %s'
      % (_bad[:3] or 'all 28'))

# ---- and the ART is its own. This is the check the recolour version could not have passed.
_bad = []
_plainmodels = set(_PLAIN['slayer_helm'].get('model') or [])
for _c in _COL:
    _stem = 'obj_slayer_helm_%s' % _c['models']
    for _k in _names67(_c):
        _d = _HOBJ[_k]
        if _d.get('model') != [_stem]:
            _bad.append((_k, 'model is %s, not %s' % (_d.get('model'), _stem)))
        if set(_d.get('model') or []) & _plainmodels:
            _bad.append((_k, 'still wearing the plain helmet\'s model'))
        for _f, _want in (('manwear', '%s_manwear,0' % _stem),
                          ('womanwear', '%s_womanwear,0' % _stem),
                          ('manhead', '%s_manhead' % _stem),
                          ('womanhead', '%s_womanhead' % _stem)):
            if _d.get(_f) != [_want]:
                _bad.append((_k, '%s is %s, not %s' % (_f, _d.get(_f), _want)))
check(not _bad, 'every colour carries its OWN five models, not the plain helmet\'s: %s'
      % (_bad[:3] or 'all 14 sets'))

# the model files exist, are registered, and parse
sys.path.insert(0, os.path.join(C, 'tools'))
from ob2render import Model as _M67, rgb15_to_hsl16 as _r15
_MODELS = set(packmap('pack/model.pack'))
_bad, _geom = [], {}
for _c in _COL:
    for _suf in ('', '_manwear', '_womanwear', '_manhead', '_womanhead'):
        _nm = 'obj_slayer_helm_%s%s' % (_c['models'], _suf)
        _path = os.path.join(C, 'models/obj/%s.ob2' % _nm)
        if _nm not in _MODELS:
            _bad.append((_nm, 'not in pack/model.pack')); continue
        if not os.path.exists(_path):
            _bad.append((_nm, 'no file on disk')); continue
        try:
            _m = _M67(_path)
            if len(_m.colour) == 0:
                _bad.append((_nm, 'no faces'))
            _geom.setdefault(_c['models'], {})[_suf] = (len(_m.colour), open(_path, 'rb').read())
        except Exception as _e:
            _bad.append((_nm, 'will not parse: %s' % _e))
check(not _bad, 'all %d model files are packed, present and parse: %s'
      % (len(_COL) * 5, _bad[:3] or 'yes'))

# THE GEOMETRY IS THE ANCHOR. Everything above compares the config against the spec, so a colour
# pointed at the WRONG model set would be self-consistent and nothing would notice - the OSRS cache
# that would settle it is not on this machine. slayerhelmspec.json records each colour's vertex and
# face counts as they came out of the importer; this measures the shipped files against them.
_bad = []
for _c in _COL:
    for _suf, _lbl in (('', 'inv'), ('_manwear', 'manwear'),
                       ('_womanwear', 'womanwear'), ('_manhead', 'manhead')):
        _m = _M67(os.path.join(C, 'models/obj/obj_slayer_helm_%s%s.ob2' % (_c['models'], _suf)))
        _want = _c['geom'][_lbl]
        if [int(_m.vcount), int(_m.fcount)] != _want:
            _bad.append((_c['key'], _lbl, [int(_m.vcount), int(_m.fcount)], _want))
check(not _bad, 'every model is the shape the import recorded for it: %s' % (_bad[:3] or 'all 56'))
_fp = {}
for _c in _COL:
    _fp.setdefault(tuple(tuple(v) for v in _c['geom'].values()), []).append(_c['key'])
_twins = sorted(v for v in _fp.values() if len(v) > 1)
check(_twins == [['oathplate', 'radiant']],
      'and no two colours are secretly the same mesh, bar the one that is: %s' % _twins)

# DIFFERENT MESHES, not the same one renamed. The bytes are the source here, not the spec.
_sets = {k: v.get('', (0, b''))[1] for k, v in _geom.items()}
_plainbytes = open(os.path.join(C, 'models/obj/obj_slayer_helm.ob2'), 'rb').read()
_dupe = [k for k, b in _sets.items() if b == _plainbytes]
check(not _dupe, 'no colour is the plain helmet\'s mesh under another name: %s' % (_dupe or 'none'))
_seen67 = {}
for _k, _b in sorted(_sets.items()):
    _seen67.setdefault(_b, []).append(_k)
_shared = [v for v in _seen67.values() if len(v) > 1]
check(not _shared, 'and no two model SETS are identical: %s' % (_shared or 'all %d differ' % len(_sets)))
# radiant is declared as a repaint of oathplate and must stay one
_rad = next((c for c in _COL if c['key'] == 'radiant'), None)
check(_rad is not None and _rad['models'] == 'oathplate' and len(_rad['recol']) == 10,
      'radiant is a ten-pair repaint of the oathplate model, which is what OSRS does too')

# ---- recolour pairs: only where OSRS itself has them, and every source hits a real face
_bad, _npairs = [], 0
for _c in _COL:
    _d = _HOBJ['slayer_helm_%s' % _c['key']]
    _got = [(int((_d.get('recol%ds' % _n) or [0])[0]), int((_d.get('recol%dd' % _n) or [0])[0]))
            for _n in range(1, len(_c['recol']) + 1)]
    if _got != [tuple(x) for x in _c['recol']]:
        _bad.append((_c['key'], 'pairs do not match the spec'))
    if _d.get('recol%ds' % (len(_c['recol']) + 1)):
        _bad.append((_c['key'], 'more pairs in the config than in the spec'))
    _npairs += len(_c['recol'])
    # A SOURCE THAT MATCHES NO FACE DOES NOTHING, SILENTLY - the bug that made the first version of
    # this round render three identical helmets. The model's own face colours are the check.
    _faces = set()
    for _suf in ('', '_manwear', '_womanwear', '_manhead'):
        _faces |= set(int(x) for x in
                      _M67(os.path.join(C, 'models/obj/obj_slayer_helm_%s%s.ob2'
                                        % (_c['models'], _suf))).colour)
    for _s, _dst in _c['recol']:
        if _r15(_s) not in _faces:
            _bad.append((_c['key'], 'recolour source %d paints no face of its own model' % _s))
check(not _bad, '%d recolour pairs, all hitting real faces: %s' % (_npairs, _bad[:3] or 'yes'))
check(sorted(c['key'] for c in _COL if c['recol']) == ['oathplate', 'radiant', 'twisted'],
      'and only the three OSRS recolours carry any: oathplate, radiant, twisted')

# the plain imbued helmet got its own model too, which it did not have before
check(_PLAIN['slayer_helm_i'].get('model') == ['obj_slayer_helm_i']
      and _PLAIN['slayer_helm_i'].get('model') != _PLAIN['slayer_helm'].get('model'),
      'the plain imbued helmet is OSRS obj 11865\'s own model, not the plain one renamed')

# ---- membership is the three params, and nothing names an item
_PARAM = blocks(read('scripts/skill_slayer/configs/slayer_helm.param'))
check(sorted(_PARAM) == ['slayer_headgear', 'slayer_helmet', 'slayer_imbued'],
      'three params: %s' % sorted(_PARAM))
_MASKS = blocks(read('scripts/skill_slayer/configs/black_mask.obj'))
_bad = []
for _k, _want in [('black_mask', ('slayer_headgear',)),
                  ('black_mask_i', ('slayer_headgear', 'slayer_imbued')),
                  ('slayer_helm', ('slayer_headgear', 'slayer_helmet')),
                  ('slayer_helm_i', ('slayer_headgear', 'slayer_helmet', 'slayer_imbued'))]:
    _d = _MASKS.get(_k) or _PLAIN.get(_k) or {}
    _got = tuple(sorted(v.split(',')[0] for v in (_d.get('param') or []) if v.startswith('slayer_')))
    if _got != tuple(sorted(_want)):
        _bad.append((_k, _got, tuple(sorted(_want))))
for _c in _COL:
    for _imb in (False, True):
        _k = 'slayer_helm_%s%s' % (_c['key'], '_i' if _imb else '')
        _want = ('slayer_headgear', 'slayer_helmet') + (('slayer_imbued',) if _imb else ())
        _got = tuple(sorted(v.split(',')[0] for v in (_HOBJ[_k].get('param') or [])
                            if v.startswith('slayer_')))
        if _got != tuple(sorted(_want)):
            _bad.append((_k, _got, tuple(sorted(_want))))
check(not _bad, 'every piece declares exactly what it is: %s' % (_bad[:2] or 'all 32'))
check('slayer_helmet' not in str(_MASKS['black_mask'].get('param')),
      'and a bare black mask is not a helmet - no earmuffs in it')

# the three doors read params and name no item at all, so a colour needs no edit
_BM67 = read('scripts/skill_slayer/scripts/black_mask.rs2')
_HM67 = read('scripts/skill_slayer/scripts/slayer_helm.rs2')
for _proc, _src, _param in (('black_mask_on_task', _BM67, 'slayer_headgear'),
                            ('black_mask_imbued_on_task', _BM67, 'slayer_imbued'),
                            ('slayer_helm_worn', _HM67, 'slayer_helmet')):
    _body = _src.split('[proc,%s]' % _proc, 1)[1].split('\n[', 1)[0]
    check('oc_param($hat, %s)' % _param in _body,
          '~%s reads %s' % (_proc, _param))
    check(not re.search(r'\$hat = (?:black_mask|slayer_helm)', _body)
          and 'inv_total(worn, slayer_helm' not in _body,
          '...and names no item, so a new colour needs no edit here')

# ---- the two that can be made: unlock, head, and the imbue surviving
_RC67 = read('scripts/skill_slayer/scripts/slayer_helm_colours.rs2')
for _c in _WITH:
    _s = _c['source']
    _b = _RC67.split('[label,slayer_recolour_%s]' % _c['key'], 1)[1].split('\n[', 1)[0]
    check('~slayer_has_unlock(%d)' % _s['bit'] in _b,
          '%s needs its unlock (bit %d)' % (_c['key'], _s['bit']))
    check('inv_del(inv, %s, 1);' % _s['head'] in _b, '...and uses up the %s' % _s['head'])
    check('$into = slayer_helm_%s_i;' % _c['key'] in _b,
          '...and an imbued helmet stays imbued through it')
# ONE trigger per OBTAINABLE colour, and none at all for the rest: [opheldu,X] normalises the
# direction, so a second is a duplicate, and a duplicate trigger does not compile.
_trig = re.findall(r'^\[opheldu,(\w+)\]', _RC67, re.M)
check(sorted(_trig) == sorted(c['source']['head'] for c in _WITH),
      'one [opheldu] per obtainable colour and no others: %s' % _trig)
check(not [c for c in _WITHOUT if 'slayer_recolour_%s]' % c['key'] in _RC67],
      'nothing pretends the other %d can be made' % len(_WITHOUT))

# disassembly hands back what went in - six things for a colour with a head, five for one without
for _c in _WITH:
    check('@slayer_helm_split_coloured(black_mask, %s)' % _c['source']['head'] in _RC67
          and '@slayer_helm_split_coloured(black_mask_i, %s)' % _c['source']['head'] in _RC67,
          '%s disassembles back into its parts AND its head' % _c['key'])
# PER ITEM, not per colour. Reading the colour name out of the trigger and comparing SETS let a
# black helmet route to the head version while its imbued twin routed to the headless one - the set
# still said 'black' and the check still passed. Every one of the 28 is named here.
_want4 = {}
for _c in _COL:
    for _k in _names67(_c):
        _mask = 'black_mask_i' if _k.endswith('_i') else 'black_mask'
        _want4[_k] = ('@slayer_helm_split_coloured(%s, %s);' % (_mask, _c['source']['head'])
                      if 'source' in _c else '@slayer_helm_split_headless(%s);' % _mask)
_bad = [k for k, v in _want4.items() if ('[opheld4,%s] %s' % (k, v)) not in _RC67]
check(not _bad, 'all %d disassemble into exactly what went into them, the %d with no head giving '
      'back five things rather than six: %s' % (len(_want4), len(_WITHOUT) * 2, _bad[:3] or 'yes'))
check('inv_freespace(inv) < 5' in _RC67 and 'inv_freespace(inv) < 4' in _RC67,
      '...and each asks for the right amount of room first')

# ---- the drops are OSRS's own rates, on the right monsters
for _c, _file, _rate in ((next(c for c in _COL if c['key'] == 'red'),
                          'scripts/drop_tables/scripts/abyssal_demon.rs2', 6000),
                         (next(c for c in _COL if c['key'] == 'green'),
                          'scripts/drop_tables/scripts/kalphite_queen.rs2', 128)):
    _t = read(_file)
    check('random(%d) = 0' % _rate in _t and _c['source']['head'] in _t,
          '%s drops at 1/%d, which is OSRS\'s own rate' % (_c['source']['head'], _rate))

# the unlocks cost what OSRS charges, and the menu and the switch agree
_RW67 = read('scripts/skill_slayer/scripts/slayer_rewards.rs2')
# The chat menu that held these is gone: the Cosmetics tab reads them out of three parallel
# tables, so the name, the bit and the price can no longer be written in two places and drift.
# Only the colours with a source are unlockable - the other twelve are ::give only and have no row.
_CN = dict(re.findall(r'^val=(\d+),(.*)$',
           _RE.split('[slayer_cosmetic_name]', 1)[1].split('\n[', 1)[0], re.M))
_CB = dict(re.findall(r'^val=(\d+),(-?\d+)$',
           _RE.split('[slayer_cosmetic_bit]', 1)[1].split('\n[', 1)[0], re.M))
_CC = dict(re.findall(r'^val=(\d+),(-?\d+)$',
           _RE.split('[slayer_cosmetic_cost]', 1)[1].split('\n[', 1)[0], re.M))
check(len(_CN) == len(_WITH),
      'the Cosmetics tab is exactly the colours you can unlock: %d rows, %d with a source'
      % (len(_CN), len(_WITH)))
for _c in _WITH:
    _s = _c['source']
    _row = [k for k, v in _CN.items() if v.strip() == _s['unlock']]
    check(len(_row) == 1, '%s is one row of the Cosmetics tab' % _s['unlock'])
    if len(_row) == 1:
        check(int(_CB[_row[0]]) == _s['bit'] and int(_CC[_row[0]]) == _s['cost'],
              '...on bit %d for %d points, the numbers the recolour itself reads'
              % (_s['bit'], _s['cost']))
check('enum(int, int, slayer_cosmetic_cost, $i)' in _RW67
      and 'enum(int, int, slayer_cosmetic_bit, $i)' in _RW67,
      'and buying one spends and sets whatever those tables say, never a copy')
check(all(_c['source']['cost'] == 1000 for _c in _WITH),
      'both at OSRS\'s own 1,000 - this price did not have to be invented')
_bits = [_c['source']['bit'] for _c in _WITH]
check(len(set(_bits)) == len(_bits) and all(b not in (0, 1, 2, 3, 4) for b in _bits),
      'on unlock bits nothing else uses: %s' % _bits)

# ---- and the sweep agrees about which ones you can get. RUN IT, do not read it.
_sw67 = _sp67.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
                  capture_output=True, text=True, cwd=C)
_out67 = _sw67.stdout
_hard67 = _out67.split('NOTHING ANYWHERE MENTIONS THESE', 1)[-1]
_design67 = _out67.split('BUILT WITH NO SOURCE ON PURPOSE', 1)[-1].split('====')[1]
_gettable = [c['source']['head'] for c in _WITH] + [n for c in _WITH for n in _names67(c)]
_orph = [n for n in _gettable if re.search(r'\b%s\b' % n, _hard67)]
check(not _orph, 'the sweep finds a source for all %d obtainable objs: %s'
      % (len(_gettable), _orph or 'heads and both colours'))
_expect67 = sorted(n for c in _WITHOUT for n in _names67(c))
_listed67 = sorted(re.findall(r'\b(slayer_helm_\w+)', _design67))
check(_listed67 == _expect67,
      'and names the other %d as deliberate, by name: %s'
      % (len(_expect67), 'yes' if _listed67 == _expect67 else set(_expect67) ^ set(_listed67)))
check('WARNING:' not in _design67,
      'with no disagreement between the spec and what the game can actually give out')


print('68. every obj can be got, or says why not')

# THE SWEEP'S REAL LIST IS EMPTY, and that is the claim this group is here to keep true. 107 objs
# had no source and no reason on file; each now has one or the other. The value is not the empty
# list - it is that the next obj to land in it stands out instead of joining a crowd.

_NOSPEC = _json.loads(read('tools/nosourcespec.json'))
_specced = set()
for _k, _v in _NOSPEC['objs'].items():
    _specced.add(_k)
    _specced.update(_v.get('also', []))

_realcount = re.search(r'NOTHING ANYWHERE MENTIONS THESE \((\d+)\)', _sw.stdout)
check(_realcount and int(_realcount.group(1)) == 0,
      'no obj in the game is unobtainable without a reason recorded for it: the sweep\'s real '
      'list holds %s' % (_realcount.group(1) if _realcount else 'no count at all'))

# A REASON, NOT JUST A NAME. A spec entry with no why is the thing this file exists to prevent -
# it excuses the obj and tells the next round nothing, which is how the same grep gets done twice.
_nowhy = sorted(k for k, v in _NOSPEC['objs'].items() if len(v.get('why', '')) < 40)
check(not _nowhy, 'and every entry that excuses one says why, at more than a few words: %s'
      % (_nowhy or 'all %d of them' % len(_NOSPEC['objs'])))
_nosrc = sorted(k for k, v in _NOSPEC['objs'].items() if 'osrs_source' not in v)
check(not _nosrc, 'and what OSRS does instead, so the departure is visible: %s'
      % (_nosrc or 'all of them'))


# THE DUPLICATE SECATEURS, which is the one entry whose whole purpose is a check. The working
# magic secateurs are fairy_enchanted_secateurs (7409); magic_secateurs (8109) came in with a
# later-cache import, does nothing, and sits one autocomplete away from the one that works. It is
# not deleted, because removing an obj id would leave a character who was ::given one holding an
# item the server no longer defines - so this is what closes the trap instead.
# Every .rs2 and every config in the tree, because the point is that NOTHING names it - a
# hand-listed set of files would be a check that passes by looking in the wrong places.
_ALLSRC = []
for _dp, _dn, _fn in os.walk(os.path.join(C, 'scripts')):
    if '_unpack' in _dp:
        continue
    for _f in _fn:
        if _f.rsplit('.', 1)[-1] in ('rs2', 'obj', 'enum', 'dbrow', 'inv', 'npc', 'param'):
            _ALLSRC.append(os.path.join(_dp, _f)[len(C) + 1:].replace(chr(92), '/'))
# ITS OWN CONFIG BLOCK IS NOT A USE, and the first version of this check counted it - the
# [magic_secateurs] header is the definition, so the check went red on exactly the state it is
# meant to describe. The block is cut out of each file before looking.
def _without_block(text, name):
    out, skip = [], False
    for line in text.split('\n'):
        t = line.split('//')[0].strip()
        if t.startswith('[') and t.endswith(']'):
            skip = t[1:-1] == name
        if not skip:
            out.append(line)
    return '\n'.join(out)

_names_it = sorted(set(
    rel for rel in _ALLSRC
    if re.search(r'(?<![\w+])magic_secateurs(?![\w+])',
                 _without_block(read(rel), 'magic_secateurs'))))
check(not _names_it,
      'nothing in the game wires the duplicate magic secateurs - the working ones are '
      'fairy_enchanted_secateurs: %s' % (_names_it or 'no script names it'))
check(re.search(r'(?<![\w+])fairy_enchanted_secateurs(?![\w+])',
                read('scripts/skill_farming/scripts/farming_actions.rs2')),
      'and the ones the farming bonus reads are the working ones')

# ---- THE TWO RANDOM EVENTS THAT DESTROYED TOOLS
# Both found by the sweep, neither an orphan problem: an unobtainable dragon axe handle was the
# symptom of a lost-axe event that could not put a dragon axe back together.
_LOSTAXE = read('scripts/macro events/scripts/woodcutting/macro_event_lost_axe.rs2')
_LOSTPICK = read('scripts/macro events/scripts/mining/macro_event_lost_pickaxe.rs2')

check(re.search(r'\$axe_head = null\) \{\s*\n\s*return;', strip(_LOSTAXE)),
      'the lost-axe event leaves the axe alone when it has no head to drop')
check(re.search(r'\$pickaxe_head = null\) \{\s*\n\s*return;', strip(_LOSTPICK)),
      'and the lost-pickaxe event does the same - which was not hypothetical: it deleted a dragon '
      'pickaxe, handed back a handle and dropped nothing, because obj_add is silent on a null obj')

# Every tool the checkers can return has to have a head, or the guard above is doing the work a
# config should. Asked of the checkers themselves, so a tool added to one is covered.
_AXES = read('scripts/skill_woodcutting/configs/axes/axes.obj')
_axenames = re.findall(r'^\[(\w*axe)\]', _AXES, re.M)
_AXEB = blocks(_AXES)
_WOODCUT = read('scripts/skill_woodcutting/scripts/woodcut.rs2')
_headless = [a for a in _axenames
             if re.search(r'return \(%s\);' % a, _WOODCUT)
             and 'axe_head' not in ','.join(_AXEB.get(a, {}).get('param', []))]
check(not _headless,
      'every axe the woodcutting checker can hand back names an axe_head, so the event has '
      'something to drop for all of them: %s' % (_headless or 'all of them'))

# The dragon axe is the only one with its own handle art, and before this round the head of a lost
# dragon axe could not be reattached by any means - a 55,000gp axe destroyed in silence.
check('axe_handle,macro_hatchethandle_dragon' in ','.join(_AXEB['dragon_axe'].get('param', [])),
      'the dragon axe names its own handle, which is what gives that handle a source at all')
_sw_axe = strip(_LOSTAXE)
check(_sw_axe.count('macro_dragon_hatchethead') >= 3,
      'and the dragon head is accepted by both handles and by its own opheldu, so a lost dragon '
      'axe can be put back together: named %s times' % _sw_axe.count('macro_dragon_hatchethead'))
_heads = re.findall(r'^\[(macro_\w*hatchethead)\]', read('scripts/macro events/configs/antimacro.obj'), re.M)
_unaccepted = []
for _handle in ('macro_hatchethandle', 'macro_hatchethandle_dragon'):
    _sw = _sw_axe.split('[opheldu,%s]' % _handle, 1)[1].split('\n[', 1)[0]
    _unaccepted += ['%s on %s' % (h, _handle) for h in _heads if h not in _sw]
check(not _unaccepted,
      'and every axe head in the game is accepted by BOTH handles, not just the heads that '
      'existed when it was written - asked of each switch on its own, because searching the whole '
      'file let a head missing from one of them be found in the other: %s'
      % (_unaccepted or 'all %d heads, both handles' % len(_heads)))

# ---- THE GREEGREES were the one gap left as a gap on purpose, and are not any more: group 69
# checks the recipe that closed it. What is left here is that nobody re-adds the excuse.
check(not [k for k, v in _NOSPEC['objs'].items() if 'greegree' in k],
      'no greegree is excused as sourceless any more, because Zooknock makes all eight')

print('69. eight greegrees, one recipe, and the animations the cache asked for')

# Monkey Madness stage 3 made exactly ONE of its eight greegrees, so a player could finish the
# quest and never see seven of its rewards - even though all eight were fully configured, each with
# its own param=mm_transmog_npc. The relic decides the head; the head's own param decides the
# monkey. This group is about keeping those two facts in one table.

MMOBJ = read('scripts/quests/quest_mm/configs/quest_mm.obj')
MMGREE = read('scripts/quests/quest_mm/configs/mm_greegree.enum')
MMRS = read('scripts/quests/quest_mm/scripts/mm_stage3.rs2')
ALLNPC = read('scripts/_unpack/377/all.npc')

_rows = dict(re.findall(r'^val=(\w+),(\w+)$', MMGREE, re.M))
_greegrees = sorted(re.findall(r'^\[(mm_monkey_greegree_\w+)\]', MMOBJ, re.M))
check(len(_greegrees) == 8, 'all eight greegrees are configured: %d' % len(_greegrees))
check(sorted(_rows.values()) == _greegrees,
      'and every one of them has a relic that makes it, with no greegree left out and none '
      'invented: %s' % (sorted(set(_rows.values()) ^ set(_greegrees)) or 'all eight'))

_objnames = {l.strip().split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l}
_notreal = sorted(n for n in list(_rows) + list(_rows.values()) if n not in _objnames)
check(not _notreal, 'every relic and every head in the table is a real obj: %s'
                    % (_notreal[:3] or 'all %d' % (len(_rows) * 2)))

# ONE HEAD PER FORM. Two greegrees pointing at the same transmogrification npc would mean one of
# the eight monkeys could never be worn, which is the shape of the bug this round closed.
_forms = dict(re.findall(r'^\[(mm_monkey_greegree_\w+)\]\n(?:(?!\[).*\n)*?'
                         r'param=mm_transmog_npc,(\w+)$', MMOBJ, re.M))
check(len(_forms) == 8, 'each greegree names the monkey it turns you into: %d of 8' % len(_forms))
check(len(set(_forms.values())) == 8,
      'and no two of them name the same monkey, so every form is reachable: %d distinct'
      % len(set(_forms.values())))

# ---- THE ANIMATION TABLE, PINNED TO THE CACHE
# Content cannot read an npc's walkanim - nc_param, nc_name, nc_size and nc_vislevel exist, the
# anims do not - so ~mm_monkey_bas carries a copy of what the cache already knows. That is a
# duplicate, and the one thing a duplicate needs is something that fails when it drifts. The eight
# forms use FOUR different sets, and hardcoding one of them is how the only greegree there used to
# be got animated as the wrong size of monkey.
_bas = MMRS.split('[proc,mm_monkey_bas]', 1)[1].split('\n[', 1)[0]
_cases = re.findall(r'case ([\w, ]+) : ~mm_bas\((\w+), (\w+), (\w+)\);', _bas)
_want, _runs = {}, {}
for _names, _ready, _walk, _run in _cases:
    for _n in [x.strip() for x in _names.split(',')]:
        _want[_n] = (_ready, _walk)
        _runs[_n] = _run
_drift = []
for _form in sorted(set(_forms.values())):
    _blk = ALLNPC.split('[%s]' % _form, 1)
    if len(_blk) < 2:
        _drift.append('%s is not in the cache at all' % _form)
        continue
    _blk = _blk[1].split('\n[', 1)[0]
    _cr = re.search(r'^readyanim=(\S+)$', _blk, re.M)
    _cw = re.search(r'^walkanim=(\S+)$', _blk, re.M)
    _got = _want.get(_form)
    if not _got:
        _drift.append('%s has no case in ~mm_monkey_bas' % _form)
    elif not (_cr and _cw) or _got != (_cr.group(1), _cw.group(1)):
        _drift.append('%s: table says %s, the cache says %s'
                      % (_form, _got, (_cr and _cr.group(1), _cw and _cw.group(1))))
check(not _drift,
      "every form's animation set is the one that form's own npc config asks for, read out of the "
      'cache rather than trusted: %s' % (_drift[:2] or 'all %d forms' % len(set(_forms.values()))))
check(len({v for v in _want.values()}) >= 4,
      'and they are not all the same set, which is the mistake this replaced: %d distinct sets'
      % len({v for v in _want.values()}))

# ---- AND THE RUN IS A RUN WHERE THERE IS ONE.
# bas_set's last slot is the running animation and ~mm_bas used to be handed the walk for it, along
# with the turn - so a running monkey ambled and a monkey turning on the spot played a walk cycle
# going nowhere. The cache has m_monkey_run and m_gorilla_run and neither was referenced anywhere
# in the build. The seq names cannot be read out of all.npc - npcs have no run field - so what is
# pinned here is the rule: a form whose family HAS a run uses it, and the two families that do not
# (the small Karamjan monkey and the zombies) fall back to their walk.
_ALLSEQ = read('scripts/_unpack/377/all.seq')
_runbad = []
for _form, _run in sorted(_runs.items()):
    if '[%s]' % _run not in _ALLSEQ:
        _runbad.append('%s runs with %s, which is not a seq' % (_form, _run))
        continue
    _family = _want[_form][1].rsplit('_', 1)[0]          # m_monkey_walk -> m_monkey
    _own = '[%s_run]' % _family
    if _own in _ALLSEQ and _run != '%s_run' % _family:
        _runbad.append('%s has %s_run and does not use it' % (_form, _family))
check(not _runbad,
      'every form runs with its own family run seq where the cache has one, and its walk where it '
      'does not: %s' % (_runbad[:2] or 'all %d forms' % len(_runs)))
check(not re.search(r'~bas_set\(\$ready, \$walk,', MMRS),
      "and the turn slot is the ready, not the walk - a monkey turning on the spot used to play a "
      'whole walk cycle going nowhere')

# ---- THE RECIPE reads the table rather than naming a head
_carve = MMRS.split('[label,mm_zooknock_carve]', 1)[1].split('\n[', 1)[0]
check('enum(obj, namedobj, mm_greegree_for,' in _carve,
      'the carve reads which head to make out of the table')
check(not re.search(r'inv_add\(inv, mm_monkey_greegree_\w+', _carve),
      'and names no greegree of its own, so a ninth needs no code')
check(before(_carve, 'inv_del(inv, mm_monkey_talisman', 'inv_add(inv, $head'),
      'the talisman and the relic are spent before the head is granted, in one block with no '
      'pausing call between them')
_after = MMRS.split('if (%mm_main >= ^mm_has_greegree) {', 1)[1].split('\nif (', 1)[0]
check('@mm_zooknock_carve;' in _after,
      'and Zooknock carves again after the quest is over, which is what makes the other seven '
      'reachable at all')
check('~mm_greegree_relic_held = null' in _after,
      '...but only when you have brought him something to work, so a bare hello still gets a line')

# ---- EVERY RELIC IS OBTAINABLE, asked of the sweep rather than assumed
_sw69 = _sp.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
                capture_output=True, text=True, cwd=C)
check(_sw69.returncode == 0, 'tools/obtainable.py runs clean')
_hard69 = _sw69.stdout.split('NOTHING ANYWHERE MENTIONS THESE', 1)[-1].split('MENTIONED, BUT', 1)[0]
_unget = sorted(r for r in _rows if re.search(r'\b%s\b' % r, _hard69))
check(not _unget, 'and every relic the table asks for can be got: %s'
                  % (_unget or 'all %d' % len(_rows)))

# THE TWO NEW DROPS ARE JUSTIFIED BY THE CACHE'S OWN MODELS, not by a guess. The bearded gorilla's
# bones came off nothing: the guard wearing the bearded body (npc_1438) dropped the normal
# gorilla's.
#
# THE NINJA GUARD DROPS SMALL, which is the opposite of what this check first asked for. 757c2065
# ("The arrest that left you standing outside") went through the whole cast and found the guards
# were dropping MEDIUM ninja bones when they should not: medium belongs to the seven named ninja
# monkeys - Kruk, the Duke and the five Padulah-and-company - and the guard wearing npc_1441 drops
# small, like the archers wearing the same body. The check follows the content it was written to
# watch, rather than the arrangement that was there before it was looked at.
for _npc, _bones, _body in (('mm_religious_trapdoor_guard', 'mm_bearded_gorilla_monkey_bones', 'npc_1438'),
                            ('mm_monkey_guard', 'mm_small_ninja_monkey_bones', 'npc_1441')):
    _blk = ALLNPC.split('[%s]' % _npc, 1)[1].split('\n[', 1)[0]
    check('param=death_drop,%s' % _bones in _blk,
          '%s drops %s' % (_npc, _bones))
    check(re.search(r'^model\d*=%s' % _body, _blk, re.M),
          '...and wears the %s body those bones came off, which is why they are its drop' % _body)

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
