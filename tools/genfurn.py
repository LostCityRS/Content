#!/usr/bin/env python3
"""Generate the whole furniture layer from tools/furnspec.json.

WRITES
  scripts/skill_construction/configs/poh_furniture.enum   the six item tables + the family names
  scripts/skill_construction/configs/construction.varp    the ^poh_furn_slots storage varps
  scripts/skill_construction/configs/construction.constant  the ^poh_fam_* block and the counts
  pack/varp.pack                                          ids for any varp that is new
  scripts/skill_construction/scripts/poh_furniture.rs2     all of it

WHY GENERATED. 238 pieces means a 238-case switch for the loc, another for the model, 238 removal
triggers and six enum tables of 238 rows, all of which have to agree with each other and with the
hotspot list. Twelve families were hand-checkable; fifty-one are not.

THE RULES, all in one place because they are the tunable part and not cache data:
  wood    the loc's own name when it says one (Oak bench, Gilded wardrobe -> mahogany), otherwise
          split positionally across the family's tiers
  level   family base + 7 per wood step + 3 per tier within that wood
  planks  one count per family, the same at every tier, as OSRS mostly does
  xp      planks x the per-plank value in construction.constant - not a table at all

WHAT IT CHECKS BEFORE WRITING ANYTHING (it refuses rather than emitting something that will not
compile or will not work):
  - every loc exists in poh.loc, carries op5=Remove, and is used by exactly one family
  - every hotspot id exists, is category=poh_hotspot, and carries the shape the family declares -
    a wrong shape puts loc_add on a different LAYER and the hotspot is not replaced, so you get the
    furniture AND the hotspot standing in the same tile
  - no hotspot is a door hotspot, and no hotspot is claimed twice
  - every item number fits the 8-bit item field
  - the labels inside a family are distinct, because a menu with two identical rows is a coin toss
"""

import collections, json, os, re, sys

# HOW MANY ROWS THE SKILL GUIDE'S LIST HOLDS, and so how many pieces one of its pages can show.
# skill_guide.if has lvl1..lvl40 / name1..name40 and ~skillguide_row's switch stops at 40, so 40 is
# a hard ceiling rather than a preference; the bands are packed to 36 to leave room for a family
# gaining a tier without having to re-band.
GUIDE_PAGE = 36
# Buttons available for bands. The interface has btn1..btn13 and the guide spends one of them on
# its Rooms page, so twelve is the real limit.
GUIDE_BANDS_MAX = 12


def guide_bands(items):
    """Contiguous level bands covering 1..99, each holding at most GUIDE_PAGE pieces.

    The Construction guide cannot be paged by room the way OSRS pages it: there are sixteen rooms
    and only thirteen buttons, and the chapel alone has 45 pieces against a 40-row list. So it is
    paged by level, which is what the interface's own Level/Advancement columns are for, and the
    boundaries are computed from the spec rather than written down - add a family and the bands
    move by themselves instead of silently overflowing a page.
    """
    counts = collections.Counter(i['level'] for i in items)
    bands, start = [], 1
    while start <= 99:
        end, n = start, 0
        while end <= 99 and n + counts[end] <= GUIDE_PAGE:
            n += counts[end]
            end += 1
        if end == start:
            # One level holds more pieces than a page. Nothing in the spec does this today; if
            # something ever does, the band is emitted anyway and the battery check below fails
            # loudly rather than the guide dropping rows on the floor.
            end = start + 1
        bands.append((start, end - 1))
        start = end
    # The last band owns everything up to 99 so a piece added above it still has a page.
    bands[-1] = (bands[-1][0], 99)
    assert len(bands) <= GUIDE_BANDS_MAX, (
        '%d level bands needed but only %d buttons are free - the guide has outgrown the interface'
        % (len(bands), GUIDE_BANDS_MAX))
    for lo, hi in bands:
        n = sum(counts[l] for l in range(lo, hi + 1))
        assert n <= 40, 'level band %d-%d holds %d pieces, past the 40-row list' % (lo, hi, n)
    return bands

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'furnspec.json')

def read(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')

def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2

def write(p, lines, nl=None):
    path = os.path.join(ROOT, p)
    if nl is None:
        nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))

def cfg(path):
    """A .loc / .npc style config file -> {name: {key: first value}}."""
    out = {}
    for b in re.split(r'\n(?=\[)', read(path)):
        m = re.match(r'\[(\w+)\]', b)
        if not m:
            continue
        d = {}
        for l in b.split('\n')[1:]:
            if '=' in l:
                k, v = l.split('=', 1)
                d.setdefault(k, v)
        out[m.group(1)] = d
    return out

def packmap(p):
    out = {}
    for l in read(p).split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[n] = int(i)
    return out

# --------------------------------------------------------------------------- the rules

WOOD = {1: 'Wooden', 2: 'Oak', 3: 'Teak', 4: 'Mahogany'}
WOOD_PLANK = {1: 'planks', 2: 'oak planks', 3: 'teak planks', 4: 'mahogany planks'}
# The plank obj behind each wood, and the experience one of them pays. Both were literals in two
# places (a switch in the .rs2 and the constants) until the garden arrived needing materials that are
# not planks at all; now every piece carries its materials and its experience as data, and these are
# what the plank families' rows are built from.
# BASIC PLANKS ARE woodplank, NOT plank. 377 already had a plank - obj 960, woodplank, name
# "Plank" - and the Construction import added a second, 8187, with the same name and description.
# Observatory Quest, Horror from the Deep's bridge and Dragon Slayer's hull all check woodplank, so
# handing out 8187 meant standing in front of the Observatory Professor holding three planks and
# being told to come back with three planks. Commit 6e425140 moved the sawmill and all 55 rows of
# poh_furniture.enum onto woodplank - but not this table, which is what WRITES those rows, so the
# next regenerate put them all back and nothing would have noticed until a house refused a plank.
# The three higher woods have only one obj each and are unaffected.
WOOD_OBJ = {1: 'woodplank', 2: 'oak_plank', 3: 'teak_plank', 4: 'mahogany_plank'}
XP_WOOD = {1: 29, 2: 60, 3: 90, 4: 140}

# The three sizes the first twelve families used. Kept verbatim: the wood decides the level and the
# plank type, so changing a split would move items that are already standing in someone's house.
LEGACY_SPLIT = {3: [1, 2, 3], 6: [1, 2, 2, 3, 3, 4], 7: [1, 2, 2, 3, 3, 4, 4]}

def split(n):
    if n in LEGACY_SPLIT:
        return LEGACY_SPLIT[n]
    if n == 1:
        return [1]
    if n == 2:
        return [1, 2]
    return [min(4, 1 + i * 4 // n) for i in range(n)]

def wood_from_name(nm):
    l = nm.lower()
    if 'mahogany' in l or 'gilded' in l or 'opulent' in l:
        return 4
    if 'teak' in l:
        return 3
    if 'oak' in l:
        return 2
    if 'wooden' in l:
        return 1
    return None

SHAPE_INDEX = ['centrepiece_straight', 'centrepiece_diagonal',
               'walldecor_straight_offset', 'grounddecor']

# How wide a name may be, measured in the client's own font. Read out of the window rather than
# typed, so moving the slot columns moves this with them.
def _box(com):
    src = read('scripts/skill_construction/interfaces/poh_furnmenu.if')
    b = src.split('[%s]' % com)[1].split('\n[')[0]
    return (int(re.search(r'^width=(\d+)$', b, re.M).group(1)),
            re.search(r'^font=(\w+)$', b, re.M).group(1))

NAME_PX, NAME_FONT = _box('s0name')
# The needs column is a different width in a different font, so it needs its own measure - the
# garden's "5 limestone, 5 soft clay" is the first materials line long enough to care.
NEED_PX, NEED_FONT = _box('s0need')

def width(s, font=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ifrender
    return ifrender.font(font or NAME_FONT).width(s)

# --------------------------------------------------------------------------- build the tables

def build():
    spec = json.load(open(SPEC))
    fams = spec['families']
    global OVERRIDE, SHARED
    OVERRIDE = {k: v for k, v in spec.get('labels', {}).items() if k != '_'}
    # Locs that really are buildable in more than one hotspot. Only the exit portal so far: it is the
    # level-1 centrepiece of BOTH gardens, as it is in OSRS, and the two centrepieces are otherwise
    # completely different lists. Anything not named here and claimed twice is still an error.
    SHARED = {k: v for k, v in spec.get('loc_allowances', {}).items() if k != '_'}
    P = cfg('scripts/skill_construction/configs/poh.loc')
    # The exit portal is a centrepiece like any other, and it lives in the portal round's own config.
    P.update(cfg('scripts/skill_construction/configs/poh_portal.loc'))
    # ...and so do the costume room's five storage spaces, imported from rev 474 in their own round.
    P.update(cfg('scripts/skill_construction/configs/poh_costume_storage.loc'))
    T = cfg('scripts/skill_construction/configs/poh_templates.loc')
    LOCS = packmap('pack/loc.pack')
    byid = {v: k for k, v in LOCS.items()}
    MODELS = packmap('pack/model.pack')

    err = []
    seen_loc, seen_hot = {}, {}
    items = []
    for fi, f in enumerate(fams, start=1):
        if f['shape'] not in SHAPE_INDEX:
            err.append('%s: shape %s is not one of %s' % (f['key'], f['shape'], SHAPE_INDEX))
        for h in f['hotspots']:
            nm = byid.get(h)
            d = T.get(nm, {})
            if nm is None or d.get('category') != 'poh_hotspot':
                err.append('%s: hotspot %d is not a poh_hotspot loc' % (f['key'], h))
            elif d.get('name') == 'Door hotspot':
                err.append('%s: hotspot %d is a DOOR hotspot' % (f['key'], h))
            if h in seen_hot:
                err.append('hotspot %d claimed by both %s and %s' % (h, seen_hot[h], f['key']))
            seen_hot[h] = f['key']
        if 'pieces' in f:
            # A family whose pieces are not a wood ladder - the garden's trees and plants, where the
            # material is a bagged plant and the level, the experience and the cost are OSRS's own
            # per piece. Each row says exactly what it is; nothing here is derived.
            OBJS = packmap('pack/obj.pack')
            for t, pc in enumerate(f['pieces'], start=1):
                loc = pc['loc']
                d = P.get(loc)
                if d is None:
                    err.append('%s: %s is not in poh.loc' % (f['key'], loc))
                    continue
                if d.get('op5') != 'Remove':
                    err.append('%s: %s has no op5=Remove' % (f['key'], loc))
                if loc in seen_loc and loc not in SHARED:
                    err.append('%s used by both %s and %s' % (loc, seen_loc[loc], f['key']))
                seen_loc[loc] = f['key']
                mats = [(m[0], m[1]) for m in pc['mats']]
                if not 1 <= len(mats) <= 2:
                    err.append('%s/%s: %d materials, and the tables hold two'
                               % (f['key'], loc, len(mats)))
                for obj, n in mats:
                    if obj not in OBJS:
                        err.append('%s/%s: %s is not in obj.pack' % (f['key'], loc, obj))
                    if n < 1:
                        err.append('%s/%s: %s x%d' % (f['key'], loc, obj, n))
                label = pc.get('label', OVERRIDE.get(loc, d.get('name', '?')))
                if width(label) > NAME_PX:
                    err.append('%s: "%s" is %dpx in the window\'s %dpx name column'
                               % (f['key'], label, width(label), NAME_PX))
                if width(pc['need'], NEED_FONT) > NEED_PX:
                    err.append('%s: "%s" is %dpx in the window\'s %dpx needs column'
                               % (f['key'], pc['need'], width(pc['need'], NEED_FONT), NEED_PX))
                model = resolve_model(P[loc].get('model', '').split(',')[0], MODELS)
                if model is None:
                    err.append('%s: no model.pack entry for %s' % (f['key'], loc))
                items.append(dict(n=len(items) + 1, fam=fi, famkey=f['key'], tier=t, loc=loc,
                                  label=label, wood=0, level=pc['level'], planks=0,
                                  xp=pc['xp'], mats=mats, need=pc['need'],
                                  model=model, modelid=MODELS.get(model, 0)))
            labels = [it['label'] for it in items if it['fam'] == fi]
            if len(set(labels)) != len(labels):
                err.append('%s: two pieces share a label: %s' % (f['key'], labels))
            continue
        raw = []
        for t, loc in enumerate(f['locs'], start=1):
            d = P.get(loc)
            if d is None:
                err.append('%s: %s is not in poh.loc' % (f['key'], loc))
                continue
            if d.get('op5') != 'Remove':
                err.append('%s: %s has no op5=Remove' % (f['key'], loc))
            if loc in seen_loc:
                err.append('%s used by both %s and %s' % (loc, seen_loc[loc], f['key']))
            seen_loc[loc] = f['key']
            raw.append((t, loc, OVERRIDE.get(loc, d.get('name', '?'))))
        sp = split(len(raw))
        woods = [wood_from_name(nm) or sp[i] for i, (t, loc, nm) in enumerate(raw)]
        # A menu label has to tell two tiers apart, and the loc's own name often cannot - seven locs
        # in a row all called "Bed". So: the loc's name when it is unique inside its family, the wood
        # in front of it when it is not, and a numeral after that when even the wood does not separate
        # them (two oak tables). Families whose names are already distinct - Firepit, Small oven, Iron
        # range - keep the cache's own words, and so does a name that already says its wood, or the
        # two Oak tables would come out as "Oak oak table".
        dupe_name = {nm: [x[2] for x in raw].count(nm) for _, _, nm in raw}
        base_labels = []
        for (t, loc, nm), w in zip(raw, woods):
            plain = dupe_name[nm] == 1 or wood_from_name(nm) is not None
            base_labels.append(nm if plain else '%s %s' % (WOOD[w], nm[0].lower() + nm[1:]))
        # ...and if the wood in front makes it too long for the window's name column, fall back to a
        # numeral instead. "Mahogany clockmaker's bench" is 171px in a 126px box; check 36 catches it
        # in the battery, but by then it is already shipped, so decide it here.
        if any(width(b) > NAME_PX for b in base_labels):
            base_labels = [nm for _, _, nm in raw]
        dupe = {b: base_labels.count(b) for b in base_labels}
        used = {}
        for i, ((t, loc, nm), w, bl) in enumerate(zip(raw, woods, base_labels)):
            if dupe[bl] > 1:
                used[bl] = used.get(bl, 0) + 1
                label = '%s %d' % (bl, used[bl])
            else:
                label = bl
            pos = sum(1 for ww in woods[:i] if ww == w)
            level = f['base'] + 7 * (w - 1) + 3 * pos
            model = resolve_model(P[loc].get('model', '').split(',')[0], MODELS)
            if model is None:
                err.append('%s: no model.pack entry for %s' % (f['key'], loc))
            items.append(dict(n=len(items) + 1, fam=fi, famkey=f['key'], tier=t, loc=loc,
                              label=label, wood=w, level=level, planks=f['planks'],
                              xp=f['planks'] * XP_WOOD[w],
                              mats=[(WOOD_OBJ[w], f['planks'])],
                              need='%d %s' % (f['planks'], WOOD_PLANK[w]),
                              model=model, modelid=MODELS.get(model, 0)))
        labels = [it['label'] for it in items if it['fam'] == fi]
        if len(set(labels)) != len(labels):
            err.append('%s: two tiers share a label: %s' % (f['key'], labels))
        for l in labels:
            if width(l) > NAME_PX:
                err.append('%s: "%s" is %dpx in the window\'s %dpx name column'
                           % (f['key'], l, width(l), NAME_PX))
    CEILING = (1 << (ITEM_LO + ITEM_HI)) - 1
    if len(items) > CEILING:
        err.append('%d items, but the item number is %d bits - %d is the ceiling'
                   % (len(items), ITEM_LO + ITEM_HI, CEILING))
    if err:
        print('\n'.join('  ERROR ' + e for e in err))
        raise SystemExit('%d problems in furnspec.json; nothing written' % len(err))
    return fams, items

def resolve_model(base, MODELS):
    """The model.pack name behind a loc's `model=`. The loc packer registers a model under its own
    name or under name_<suffix> (LocConfig.ts), so `osrsloc_4525` is in the pack as
    `osrsloc_4525_8` - and the shortest suffixed name is the model itself, where a longer one is
    the loc's SECOND model (`osrsloc_4525_2_8`). Exact name first, then the shortest suffix."""
    if not base:
        return None
    if base in MODELS:
        return base
    c = sorted((n for n in MODELS if n.startswith(base + '_')), key=lambda n: (len(n), n))
    return c[0] if c else None

# --------------------------------------------------------------------------- shapes vs the map

def map_shapes():
    """Every shape each hotspot loc is actually placed with in the six style squares."""
    SHAPE = {0:'wall_straight',1:'wall_diagonalcorner',2:'wall_l',3:'wall_squarecorner',
             4:'walldecor_straight_nooffset',5:'walldecor_straight_offset',
             6:'walldecor_diagonal_offset',7:'walldecor_diagonal_nooffset',
             8:'walldecor_diagonal_both',9:'wall_diagonal',10:'centrepiece_straight',
             11:'centrepiece_diagonal',22:'grounddecor'}
    out = {}
    for p in ('maps/m29_79.jm2', 'maps/m30_79.jm2'):
        sec = None
        for l in read(p).split('\n'):
            if l.startswith('===='):
                sec = l.strip('= ')
                continue
            if sec != 'LOC' or ':' not in l:
                continue
            data = (l.split(':', 1)[1].split() + ['10', '0'])[:3]
            out.setdefault(int(data[0]), set()).add(SHAPE.get(int(data[1]), data[1]))
    return out

# --------------------------------------------------------------------------- emit

# The packed record. APPEND ONLY, and only above bit 21: a save written before a field existed has
# zero in it, so a new field at the top is free and a field inserted anywhere else would misread
# every house that already exists. `lit` went in at 22 for exactly that reason - an old record reads
# as unlit, which is what it was.
BITS = [('rx', 3), ('rz', 3), ('lx', 3), ('lz', 3), ('angle', 2), ('item', 8), ('lit', 1),
        ('item_hi', 7)]

# `item` is the low byte and `item_hi` the high seven bits, which is why the item field is not one
# range: 238 pieces filled 8 bits to within 17 and the garden needed sixty more. The high byte went
# ABOVE `lit` rather than next to `item`, so a record written when items were 8 bits has 0 up there
# and still decodes to the same piece. ~poh_furn_pack splits the value and ~poh_furn_item puts it
# back together; nothing else ever reads the two halves separately.
ITEM_LO, ITEM_HI = 8, 7

def emit_enum(fams, items, path):
    o = ['// Everything that can be built into a furniture hotspot, one row per buildable thing.',
         '//',
         '// GENERATED by tools/genfurn.py from tools/furnspec.json - %d pieces across %d families is'
         % (len(items), len(fams)),
         '// six tables that have to agree with each other, with %d hotspot triggers and with %d'
         % (sum(len(f['hotspots']) for f in fams), len(items)),
         '// removal triggers. Edit the spec, not this file.',
         '//',
         '// poh_furn_name is the loc\'s OWN name= out of poh.loc - the 474 import brought the furniture',
         '// in with its real names attached, so these are data, not memory. Where a family gives several',
         '// tiers the same name (seven locs all called "Bed"), the wood of its planks disambiguates; a',
         '// name that already says its wood is left alone.',
         '//',
         '// poh_furn_level and poh_furn_wood are a RULE, not OSRS\'s table, and are the tunable part:',
         '//   wood   - taken from the loc\'s name when it says one, otherwise split positionally',
         '//   level  - family base + 7 per wood step + 3 per tier within that wood',
         '//   planks - one count per family, the same at every tier, as OSRS mostly does',
         '// Experience is not a table at all: it is planks x the per-plank value in construction.constant.',
         '']
    def table(name, out, rows, head=None, default=None):
        if head:
            o.extend(head)
        o.append('[%s]' % name)
        o.append('inputtype=int')
        o.append('outputtype=%s' % out)
        if default is not None:
            o.append('default=%s' % default)
        o.extend('val=%s,%s' % r for r in rows)
        o.append('')
    table('poh_furn_fam', 'int', [(i['n'], i['fam']) for i in items])
    table('poh_furn_name', 'string', [(i['n'], i['label']) for i in items])
    table('poh_furn_level', 'int', [(i['n'], i['level']) for i in items])
    table('poh_furn_wood', 'int', [(i['n'], i['wood']) for i in items])
    table('poh_furn_planks', 'int', [(i['n'], i['planks']) for i in items],
          ['// How many planks a piece costs, or 0 for the garden, whose materials are not planks.',
           '// What is actually spent is poh_furn_mat1/mat2 below; this is kept because the plank',
           '// families\' own rule is worth being able to read back.'])
    table('poh_furn_xp', 'int', [(i['n'], i['xp'] * 10) for i in items],
          ['// The Construction experience for building one, IN TENTHS OF A POINT, which is what',
           '// stat_advance takes. These were OSRS\'s whole numbers until now - 87 for a wooden chair',
           '// rather than 870 - so every piece in the house paid a tenth of its experience, and a',
           '// player on 10x received exactly the 1x amount and reported the multiplier as broken',
           '// (DeathPlateau-Bugs#66, #63). The rate was never the problem.',
           '//',
           '// So: the wiki number x 10, done here rather than in the source tables so that every',
           '// row stays readable as the number its wiki page gives. For a plank family that number',
           '// is planks x the per-plank value; for the garden it is OSRS\'s own for that piece. One',
           '// table either way, so the click does not have to know which kind of family it is in.'])
    # WHICH PIECES ALSO PAY FARMING. A garden piece built from a bagged plant, tree or flower pays
    # its Construction experience AGAIN in Farming: the wiki says both in one breath for each of
    # them - bagged plant 1 is "31 experience to both Construction and Farming", bagged plant 3 is
    # 100 to both, bagged nice tree 44 to both. The garden paid Construction only (#65).
    #
    # DERIVED FROM need, NOT A LIST KEPT BY HAND, so it cannot drift from what the garden actually
    # plants: a new bagged piece is flagged by adding it, and nothing else.
    #
    # A FLAG RATHER THAN A SECOND COLUMN OF NUMBERS, because the two amounts are the same one and a
    # copy would be a second place for it to go wrong. The caller reads poh_furn_xp once, pays twice.
    table('poh_furn_garden', 'int',
          [(i['n'], 1) for i in items if 'bagged' in i['need'].lower()],
          ['// 1 for a piece planted from a bagged plant, tree or flower, which pays its Construction',
           '// experience again in Farming; absent (0) for everything else. Three of these are verified',
           '// against their own wiki pages - bagged plant 1, bagged plant 3 and bagged nice tree, so',
           '// one plant, one tall plant and one tree - and the rest follow the rule those three state.'],
          default=0)
    table('poh_furn_mat1', 'namedobj', [(i['n'], i['mats'][0][0]) for i in items],
          ['// WHAT A PIECE COSTS. Two materials are enough for everything the game asks for: planks for',
           '// the inside of a house, a bagged plant for a tree, and the two-material centrepieces',
           '// (5 limestone bricks and 5 soft clay for the imp statue). namedobj, not obj: inv_del wants',
           '// a namedobj and namedobj widens to obj, so one table feeds inv_total and inv_del both.',
           '// default=null even though every piece has a row: a namedobj enum with no default answers',
           '// 0 on a miss, and obj 0 is mcannonremains. rs2check rule 17.'],
          default='null')
    table('poh_furn_mat1n', 'int', [(i['n'], i['mats'][0][1]) for i in items])
    table('poh_furn_mat2', 'namedobj',
          [(i['n'], i['mats'][1][0]) for i in items if len(i['mats']) > 1],
          ['// The second material, for the few pieces that need one. Absent rows answer null, which is',
           '// what ~poh_furn_have and ~poh_furn_take test for - so "one material" needs no flag.'],
          default='null')
    table('poh_furn_mat2n', 'int', [(i['n'], i['mats'][1][1]) for i in items if len(i['mats']) > 1])
    table('poh_furn_need', 'string', [(i['n'], i['need']) for i in items],
          ['// The materials as the window writes them, measured against its 126px column by the',
           '// generator. "4 oak planks", "1 bagged yew tree", "5 limestone, 5 soft clay".'])
    table('poh_furn_tier', 'int', [(i['n'], i['tier']) for i in items],
          ['// Which step of its own family a piece is, 1-based. The altar reads it to work out what it',
           '// pays for a set of bones.'])
    table('poh_wood_name', 'string',
          [(i['n'], WOOD_PLANK[i['wood']]) for i in items if i['wood']],
          ['// The plank type a piece is made of, worded for a sentence ("4 oak planks"). The garden is',
           '// not made of planks and has no row here; what the window actually prints is poh_furn_need.'],
          default='null')
    table('poh_fam_name', 'string', [(n, f['label']) for n, f in enumerate(fams, 1)],
          ['// What the Furniture creation window calls each hotspot family, for its title bar.'])

    def guide_room(room):
        parts = [p.strip() for p in room.split(',') if p.strip()]
        if len(parts) != 1:
            return 'Several rooms'
        return parts[0][:1].upper() + parts[0][1:]

    table('poh_fam_room', 'string',
          [(n, guide_room(f['room'])) for n, f in enumerate(fams, 1)],
          ['// Which room a family\'s hotspots are in, for the skill guide to put after a piece\'s name',
           '// ("Oak bed (Bedroom)"). The spec\'s own room field, which until now only the docs read.',
           '// The five families whose hotspots appear in more than one room say "Several rooms"',
           '// rather than listing them: a rug space is in five, and the name column is 280px.'])

    bands = guide_bands(items)
    table('poh_guide_lo', 'int', [(n, lo) for n, (lo, _) in enumerate(bands, 1)],
          ['// The skill guide\'s level bands - see guide_bands() in tools/genfurn.py for why the',
           '// Construction guide is paged by level and not by room. Band n covers poh_guide_lo(n)',
           '// to poh_guide_hi(n) inclusive, and the bands are contiguous from 1 to 99. Only the',
           '// button labels read these; what a page actually draws is the slice below.'])
    table('poh_guide_hi', 'int', [(n, hi) for n, (_, hi) in enumerate(bands, 1)])

    # EVERY PIECE IN LEVEL ORDER, so a guide page is a slice and not a search. The obvious way to
    # draw band 80-99 is to walk levels 80..99 and, for each, walk all 351 pieces looking for it -
    # 7,000 iterations for one page, which is the shape of thing that killed the room window
    # (claude/poh-menu-opcount.md). Sorting here instead makes a page cost one pass over its own
    # rows, at most GUIDE_PAGE of them. Ties are broken by piece number so the order is stable.
    order = sorted(items, key=lambda i: (i['level'], i['n']))
    table('poh_guide_order', 'int', [(n, i['n']) for n, i in enumerate(order, 1)],
          ['// The pieces in level order: poh_guide_order(n) is the nth piece by level. The skill',
           '// guide walks a slice of this and reads the piece tables through it.'])
    at = {}
    for n, i in enumerate(order, 1):
        at.setdefault(i['level'], n)
    firsts, lasts = [], []
    pos = 1
    for bn, (lo, hi) in enumerate(bands, 1):
        count = sum(1 for i in order if lo <= i['level'] <= hi)
        firsts.append((bn, pos))
        lasts.append((bn, pos + count - 1))
        pos += count
    assert pos - 1 == len(items), 'the bands do not cover every piece'
    table('poh_guide_first', 'int', firsts,
          ['// Where each band starts and ends inside poh_guide_order. A band with no pieces would',
           '// have last < first, which the guide reads as an empty page rather than as an error.'])
    table('poh_guide_last', 'int', lasts)
    # A family's pieces are consecutive because this generator writes them family by family, which is
    # what lets ~poh_furn_nth be two lookups instead of a walk down all %d rows. Asserted here as well
    # as in poh_battery.py check 51: if the spec ever interleaves families, the window would list the
    # wrong things, so this has to fail at generation rather than in someone's house.
    first, last = {}, {}
    for i in items:
        first.setdefault(i['fam'], i['n'])
        last[i['fam']] = i['n']
    for fam in first:
        span = [i['n'] for i in items if i['fam'] == fam]
        assert span == list(range(first[fam], last[fam] + 1)), 'family %s is not contiguous' % fam
    table('poh_fam_first', 'int', sorted(first.items()),
          ['// The first and last piece of each family. ~poh_furn_nth adds the row number to the first',
           '// and stops at the last, so paging the Furniture window costs the same whatever family it is',
           '// showing. It used to walk every piece in the game per row per page - the room window died of',
           '// exactly that (claude/poh-menu-opcount.md) and this one was on its way there.'])
    table('poh_fam_last', 'int', sorted(last.items()))
    flat = {f['key'] for f in fams if f.get('flatpack')}
    table('poh_flat_fam', 'int',
          [(k, fi) for k, fi in enumerate(
              [i + 1 for i, f in enumerate(fams) if f.get('flatpack')], start=1)],
          ['// The flatpackable families, numbered 1..n, for the Work-at grid to page through.',
           '// NO default= here and that is deliberate: this one is an int table and 0 is the answer',
           '// the pager wants for "past the end" - the same thing ~poh_furn_nth returns. rs2check',
           '// rule 17 only flags the types where 0 is a real npc, obj, loc, seq or spotanim.'])
    table('poh_furn_flat', 'namedobj',
          [(i['n'], flat_name(i)) for i in items if i['famkey'] in flat],
          ['// Which flatpack each piece has, for the pieces that have one. A row is ABSENT for every',
           '// piece in a family that cannot be flatpacked, so default=null is what says "this one',
           '// cannot" - and it has to be there, because a namedobj enum with no default answers 0 on',
           '// a miss and obj 0 is mcannonremains. rs2check rule 17.'],
          default='null')
    write(path, o)

FLAT_HEAD = """// The flatpacks: one obj per buildable piece in a family that can be flatpacked.
//
// GENERATED by tools/genfurn.py from the "flatpack": true families in tools/furnspec.json.
//
// FIFTEEN MODELS CARRY EIGHTY-FOUR ITEMS. That is not a shortcut - it is what OSRS does. Every
// flatpack in that game shares one model per family and is told apart by its name alone, and every
// one of the 91 of them carries the same icon camera (2dzoom=1762, 2dxan=512), the same 1000g weight
// and the same 10gp value. The models here are the real ones, re-encoded out of the rev240 cache by
// tools/models/osrs2ob2.py: obj_poh_flat_<family>.
//
// The examine is OSRS's own, and it is also how the set was FOUND. A flatpack is not called
// "Oak chair (flatpack)" in the cache - it is called "Oak chair", exactly like the piece. The only
// thing separating the 91 flatpacks from everything else is the examine string
// "How does it all fit in there?".
//
// The NAME is this build's own label for the piece, not OSRS's name for its own tier. Our ladders
// are not theirs - our chair family runs Wooden / Oak 1 / Oak 2 / Teak 1 / Teak 2 / Mahogany 1 /
// Mahogany 2 where OSRS runs Crude / Wooden / Rocking / Oak / Oak arm / Teak arm / Mahogany arm -
// so borrowing their strings would put the wrong name on the wrong piece. The flatpack is called
// what the Furniture window calls the thing it builds."""


def flat_name(it):
    return 'poh_flat_%s_%d' % (it['famkey'], it['tier'])


def emit_flatpacks(fams, items, ids,
                   path='scripts/skill_construction/configs/poh_flatpacks.obj'):
    flat = {f['key'] for f in fams if f.get('flatpack')}
    o = FLAT_HEAD.split('\n') + ['']
    n = 0
    for it in items:
        if it['famkey'] not in flat:
            continue
        o += ['[%s]' % flat_name(it),
              'name=%s' % it['label'],
              'desc=How does it all fit in there?',
              'model=obj_poh_flat_%s' % it['famkey'],
              '2dzoom=1762',
              '2dxan=512',
              'members=yes',
              'weight=1000g',
              'cost=10',
              '']
        n += 1
    write(path, o)
    return n


def emit_flatpack_pack(fams, items, path='pack/obj.pack'):
    """obj.pack is id=name, dense from 0. Re-running must reuse the ids it already handed out -
    a flatpack is in somebody's bank and anything imported after this round sits above it."""
    rows = [(int(l.split('=', 1)[0]), l.split('=', 1)[1]) for l in read(path).split('\n') if '=' in l]
    flat = {f['key'] for f in fams if f.get('flatpack')}
    mine = [flat_name(it) for it in items if it['famkey'] in flat]
    have = {n: i for i, n in rows}
    out = {i: n for i, n in rows if n not in set(mine)}
    nxt = max(i for i, _ in rows) + 1      # past EVERY id, not just the ones being kept
    for n in mine:
        if n in have:
            out[have[n]] = n
        else:
            out[nxt] = n
            nxt += 1
    if len(out) != len(set(out.values())):
        raise SystemExit('obj.pack would have a duplicate name')
    write(path, ['%d=%s' % (i, out[i]) for i in sorted(out)], nl='\n')
    return {n: i for i, n in out.items() if n in set(mine)}


def emit_varp(fams, items, slots, path):
    o = read(path).split('\n')
    cut = next(i for i, l in enumerate(o) if l.startswith('// ---- furniture'))
    o = o[:cut]
    o += ['// ---- furniture (skill_construction/scripts/poh_furniture.rs2) ----',
          '//',
          '// One piece each, packed into %d bits: the room cell in the grid (%d+%d), the tile inside that'
          % (sum(w for _, w in BITS), BITS[0][1], BITS[1][1]),
          '// room (%d+%d), the angle (%d) and which of the %d buildable things it is (%d low bits plus %d'
          % (BITS[2][1], BITS[3][1], BITS[4][1], len(items), ITEM_LO, ITEM_HI),
          '// above the lit bit - see the note in tools/genfurn.py).',
          '//',
          '// %d of them, which is the ceiling on how much furniture one house can hold. The save writes' % slots,
          '// varps sparsely by id, so an unfurnished house costs nothing and only what is actually built',
          '// is ever written - which is why the ceiling can be raised without costing anyone anything.',
          '//',
          '// Perm: this is the house.', '']
    for i in range(slots):
        o += ['[poh_furn_%d]' % i, 'scope=perm', '']
    write(path, o)

def emit_varp_pack(slots, path='pack/varp.pack'):
    rows = [(int(l.split('=', 1)[0]), l.split('=', 1)[1]) for l in read(path).split('\n') if '=' in l]
    keep = [(i, n) for i, n in rows if not re.fullmatch(r'poh_furn_\d+', n)]
    have = {n: i for i, n in rows}
    nxt = max(i for i, _ in rows) + 1      # past EVERY id, not just the ones being kept
    for s in range(slots):
        n = 'poh_furn_%d' % s
        if n in have:                       # never renumber one that already exists: it is in a save
            keep.append((have[n], n))
        else:
            keep.append((nxt, n))
            nxt += 1
    keep.sort()
    ids = [i for i, _ in keep]
    if len(set(ids)) != len(ids):
        raise SystemExit('varp.pack would have a duplicate id')
    write(path, ['%d=%s' % kv for kv in keep], nl='\n')
    return keep

def emit_constant(fams, items, slots, path='scripts/skill_construction/configs/construction.constant'):
    src = read(path).split('\n')
    a = next(i for i, l in enumerate(src) if l.startswith('// ---- furniture'))
    b = next(i for i, l in enumerate(src) if l.startswith('// ---- the build windows'))
    block = ['// ---- furniture (poh_furniture.rs2) ----',
             '// GENERATED by tools/genfurn.py from tools/furnspec.json, along with the varps, the enum',
             '// tables and all of poh_furniture.rs2.',
             '//',
             '// How many pieces one house can hold, and how many buildable things there are.',
             '^poh_furn_slots = %d' % slots,
             '^poh_furn_items = %d' % len(items),
             '',
             '// How many level bands the skill guide pages into (poh_guide_lo/hi in the enum). One',
             '// more button than this is used, for the Rooms page, and the interface has thirteen.',
             '^poh_guide_bands = %d' % len(guide_bands(items)),
             '',
             '// The bit layout of one packed piece. %d bits, so it fits an int with room to spare.'
             % sum(w for _, w in BITS)]
    bit = 0
    for name, width in BITS:
        block.append('^poh_furn_bit_%s = %d' % (name, bit))
        bit += width
    block += ['',
              '// Construction experience per plank. OSRS\'s furniture xp is very nearly planks x this, so it',
              '// is one rule rather than %d rows of remembered numbers - and it is the obvious thing to tune.' % len(items),
              '^poh_xp_plank = 29',
              '^poh_xp_oak = 60',
              '^poh_xp_teak = 90',
              '^poh_xp_mahogany = 140',
              '',
              '',
              '// ---- what the furniture does (poh_furn_ops.rs2) ----',
              '// What a house altar pays for bones, as a percentage of the burying experience: the base for',
              '// the plainest altar, a step per tier above it, and a bonus for every lit thing in the same',
              '// room. OSRS pays 250% to 350% and another 50% a burner. NOT cache data - tune away.',
              '^poh_altar_base = 250',
              '^poh_altar_step = 15',
              '^poh_altar_burner = 25',
              '',
              '// The furniture families, one per hotspot kind. A hotspot\'s trigger passes its own family in,',
              '// so nothing has to look one up. NEVER REORDER: item numbers follow family order and item',
              '// numbers are what is stored in a save.']
    for n, f in enumerate(fams, 1):
        block.append('^poh_fam_%s = %d' % (f['key'], n))
    portal = next((i['n'] for i in items if i['loc'] == 'poh_exit_portal'), None)
    if portal is None:
        raise SystemExit('no piece is built from poh_exit_portal - the garden centrepiece needs one')
    block += ['',
              '// The exit portal, as a piece of furniture. It is the garden\'s level-1 centrepiece, which',
              '// is where OSRS puts it, and ~poh_ensure_exit hands one out free to any house that has no',
              '// portal yet. ~poh_furn_remove will not take out the last one: that is the whole reason',
              '// this number is a constant rather than something the remove path works out.',
              '^poh_furn_exit_portal = %d' % portal]
    block.append('')
    write(path, src[:a] + block + src[b:])

RS2_HEAD = '''// Furniture: building into a hotspot, and remembering what was built.
//
// GENERATED by tools/genfurn.py from tools/furnspec.json. {items} pieces across {fams} families means a
// {items}-case switch for the loc, another for the model, {items} removal triggers and six enum tables of
// {items} rows, all of which have to agree with each other and with the {hots} hotspot triggers. Twelve
// families were hand-checkable; fifty-one are not. Edit the spec, not this file.
//
// WHERE IT LIVES. {slots} perm varps, one piece each, packed into {bits} bits - the room cell (3+3), the
// tile inside that room (3+3), the angle (2) and which of the {items} buildable things it is (8+7). The
// tile inside the zone is what identifies the hotspot, and it is exactly what loc_coord gives, so
// nothing has to enumerate hotspots or number them. Same trick as the room grid: the save writes
// varps sparsely by id, so an unfurnished house costs nothing. No engine change, no save bump.
//
// HOW IT APPEARS. loc_add at the hotspot's own coord and angle. World.changeLoc swaps the type in
// place, so the hotspot BECOMES the furniture - and it then survives instance_loccategory(...,
// poh_hotspot, false), because that only removes locs whose TYPE's category is poh_hotspot, which
// the furniture's is not. ~poh_build places furniture after the zone loop and before the hide.
//
// TAKING IT BACK OUT re-lays the whole zone rather than trying to put the hotspot back. The template
// is the exact truth about what was there; reconstructing it from a family id would be a guess, and
// several of these families have more than one hotspot loc.
//
// THE SHAPE IS NOT STORED. Every piece of a family is placed with one shape, a literal in the switch
// below, so it can only ever be placed as the shape its own hotspot carries - correct by
// construction rather than by bookkeeping. genfurn.py checks each family's shape against the six
// style squares and refuses to emit a family whose shape would land on a different LAYER from its
// hotspot, because then the hotspot would not be replaced and both would stand in the same tile.
'''

def emit_rs2(fams, items, slots, path='scripts/skill_construction/scripts/poh_furniture.rs2'):
    byfam = {f['key']: f for f in fams}
    o = RS2_HEAD.format(items=len(items), fams=len(fams), slots=slots,
                        bits=sum(w for _, w in BITS),
                        hots=sum(len(f['hotspots']) for f in fams)).split('\n')
    o += ['// =========================================================================== storage', '',
          '// %d cases because RuneScript cannot index a varp by number.' % slots,
          '[proc,poh_furn_get](int $i)(int)', 'switch_int ($i) {']
    o += ['    case %d : return(%%poh_furn_%d);' % (i, i) for i in range(slots)]
    o += ['    case default : return(0);', '}', '',
          "// The same, for the house the player is standing in: their own, or as a guest the owner's",
          '// (skill_construction/scripts/poh_guests.rs2) - read through the uid the guest kept.',
          '[proc,poh_furn_get_here](int $i)(int)',
          'if (%poh_instance ! null) {', '    return(~poh_furn_get($i));', '}',
          'if (%poh_visiting = null | .finduid(%poh_host) = false) {', '    return(0);', '}',
          'switch_int ($i) {']
    o += ['    case %d : return(.%%poh_furn_%d);' % (i, i) for i in range(slots)]
    o += ['    case default : return(0);', '}', '',
          '[proc,poh_furn_set](int $i, int $value)', 'switch_int ($i) {']
    o += ['    case %d : %%poh_furn_%d = $value;' % (i, i) for i in range(slots)]
    o += ['    case default : return;', '}', '']
    o += ['[proc,poh_furn_pack](int $rx, int $rz, int $lx, int $lz, int $angle, int $item)(int)',
          'def_int $v = 0;']
    for name, width in BITS:
        if name == 'lit':
            continue                     # never set at build time; ~poh_furn_light flips it later
        if name == 'angle':
            o.append('$v = setbit_range_toint($v, modulo($angle, 4), ^poh_furn_bit_angle, calc(^poh_furn_bit_angle + %d));' % (width - 1))
        elif name == 'item':
            o.append('// the item number is split: the low byte here, the high seven above the lit bit.')
            o.append('$v = setbit_range_toint($v, modulo($item, %d), ^poh_furn_bit_item, calc(^poh_furn_bit_item + %d));'
                     % (1 << ITEM_LO, width - 1))
        elif name == 'item_hi':
            o.append('return(setbit_range_toint($v, divide($item, %d), ^poh_furn_bit_item_hi, calc(^poh_furn_bit_item_hi + %d)));'
                     % (1 << ITEM_LO, width - 1))
        else:
            o.append('$v = setbit_range_toint($v, $%s, ^poh_furn_bit_%s, calc(^poh_furn_bit_%s + %d));'
                     % (name, name, name, width - 1))
    o += ['', '[proc,poh_furn_field](int $v, int $bit, int $width)(int)',
          'return(getbit_range($v, $bit, calc($bit + $width - 1)));', '',
          '// The item number, back out of its two halves. Every reader goes through this: a record from',
          '// before the high byte existed has 0 there and comes back as the same piece it always was.',
          '[proc,poh_furn_item](int $v)(int)',
          'return(calc(~poh_furn_field($v, ^poh_furn_bit_item, %d) + ~poh_furn_field($v, ^poh_furn_bit_item_hi, %d) * %d));'
          % (ITEM_LO, ITEM_HI, 1 << ITEM_LO), '',
          '// The slot holding the piece on this tile, or -1. A linear scan over %d is nothing - switch_int' % slots,
          '// is a jump table, not a chain of comparisons - and it is the only lookup this design needs.',
          '[proc,poh_furn_at](int $rx, int $rz, int $lx, int $lz)(int)',
          'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '            if (~poh_furn_field($v, ^poh_furn_bit_lx, 3) = $lx & ~poh_furn_field($v, ^poh_furn_bit_lz, 3) = $lz) {',
          '                return($i);', '            }', '        }', '    }',
          '    $i = calc($i + 1);', '}', 'return(-1);', '',
          '[proc,poh_furn_free]()(int)', 'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {', '    if (~poh_furn_get($i) = 0) {', '        return($i);',
          '    }', '    $i = calc($i + 1);', '}', 'return(-1);', '',
          '// How many of one piece the house holds. Used for the exit portal, which is the one piece a',
          '// house must not run out of.',
          '[proc,poh_furn_count_item](int $item)(int)', 'def_int $i = 0;', 'def_int $n = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_item($v) = $item) {', '            $n = calc($n + 1);', '        }',
          '    }', '    $i = calc($i + 1);', '}', 'return($n);', '',
          '// ...and how many of it are in one room, which is what build mode asks before it lets a room',
          '// be taken out: the room goes with its furniture in it.',
          '[proc,poh_furn_count_cell_item](int $rx, int $rz, int $item)(int)',
          'def_int $i = 0;', 'def_int $n = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '            if (~poh_furn_item($v) = $item) {', '                $n = calc($n + 1);', '            }',
          '        }', '    }', '    $i = calc($i + 1);', '}', 'return($n);', '',
          '// Everything in one room goes when the room does.',
          '[proc,poh_furn_clear_cell](int $rx, int $rz)', 'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {', '    def_int $v = ~poh_furn_get($i);', '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '            ~poh_furn_set($i, 0);', '        }', '    }', '    $i = calc($i + 1);', '}', '',
          '// =========================================================================== materials', '',
          '// What a piece costs is a pair of tables, not a switch over wood: the garden is built out of',
          '// bagged plants and the two-material centrepieces out of limestone and clay, and a rule that',
          '// only knew about planks could not say any of that. Every family goes through these two, so',
          '// there is one place where materials are checked and one where they are spent.',
          '[proc,poh_furn_have](int $item)(boolean)',
          'if (inv_total(inv, enum(int, namedobj, poh_furn_mat1, $item)) < enum(int, int, poh_furn_mat1n, $item)) {',
          '    return(false);', '}',
          'def_namedobj $second = enum(int, namedobj, poh_furn_mat2, $item);',
          'if ($second ! null) {',
          '    if (inv_total(inv, $second) < enum(int, int, poh_furn_mat2n, $item)) {',
          '        return(false);', '    }', '}',
          'return(true);', '',
          '[proc,poh_furn_take](int $item)',
          'inv_del(inv, enum(int, namedobj, poh_furn_mat1, $item), enum(int, int, poh_furn_mat1n, $item));',
          'def_namedobj $second = enum(int, namedobj, poh_furn_mat2, $item);',
          'if ($second ! null) {',
          '    inv_del(inv, $second, enum(int, int, poh_furn_mat2n, $item));', '}', '',
          '// =========================================================================== putting it there', '',
          '// One case per buildable thing. The loc AND its shape are literals here, so a piece can only ever',
          '// be placed as the shape its own hotspot was - there is no shape to store and none to get wrong.',
          '//',
          '// A piece that has been lit goes down as its lit twin instead, which is what makes a fire still',
          '// be burning after you build a room somewhere else in the house.',
          '[proc,poh_furn_show](int $item, coord $spot, int $angle, int $lit)',
          'if ($lit = 1) {',
          '    if (~poh_furn_show_lit($item, $spot, $angle) = true) {',
          '        return;',
          '    }',
          '}',
          'switch_int ($item) {']
    for i in items:
        f = byfam[i['famkey']]
        # A family with "show" does not go down as a fixed loc. The portal frames are the only
        # ones so far: a directed portal is the same built piece wearing its destination, so which
        # loc lands is a runtime question and the proc is the one that answers it. The TIER is
        # passed because that is what the three frames differ by.
        if f.get('show'):
            o.append('    case %d : ~%s($spot, $angle, %d);' % (i['n'], f['show'], i['tier']))
        else:
            o.append('    case %d : loc_add($spot, %s, $angle, %s, ^poh_loc_duration);'
                     % (i['n'], i['loc'], f['shape']))
    o += ['    case default : return;', '}', '',
          '// The lit twin of anything that can be lit, and false for everything else.',
          '[proc,poh_furn_show_lit](int $item, coord $spot, int $angle)(boolean)',
          'switch_int ($item) {']
    for i in items:
        f = byfam[i['famkey']]
        op = f.get('op1') or {}
        if op.get('kind') == 'light':
            o.append('    case %d : loc_add($spot, %s, $angle, %s, ^poh_loc_duration); return(true);'
                     % (i['n'], op['lit'][i['tier'] - 1], f['shape']))
    o += ['    case default : return(false);', '}', '']
    return o, byfam

def emit_rs2_tail(fams, items, byfam):
    o = ['// Lay every saved piece back into a freshly built house. Called from ~poh_build after the rooms and',
         '// before the hotspots are hidden, so each piece lands on the hotspot it belongs to and changes it.',
         '[proc,poh_furn_restore](coord $base)', 'def_int $i = 0;',
         'while ($i < ^poh_furn_slots) {', '    def_int $v = ~poh_furn_get($i);', '    if ($v ! 0) {',
         '        def_int $rx = ~poh_furn_field($v, ^poh_furn_bit_rx, 3);',
         '        def_int $rz = ~poh_furn_field($v, ^poh_furn_bit_rz, 3);',
         '        if (~poh_room_type($rx, $rz) = 0) {',
         '            // its room is gone - so is it', '            ~poh_furn_set($i, 0);',
         '        } else {',
         '            def_coord $spot = movecoord($base, calc((^poh_grid_origin + $rx) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lx, 3)), 0, calc((^poh_grid_origin + $rz) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lz, 3)));',
         '            ~poh_furn_show(~poh_furn_item($v), $spot, ~poh_furn_field($v, ^poh_furn_bit_angle, 2), ~poh_furn_field($v, ^poh_furn_bit_lit, 1));',
         '        }', '    }', '    $i = calc($i + 1);', '}', '',
         '// ONE ROOM\'S PIECES, for ~poh_furn_relay. ~poh_furn_restore above lays the whole house back and',
         '// is right to: it is called after a BUILD, when every zone has just been replaced. A relay',
         '// replaces ONE zone, so only one room\'s locs were wiped, and re-adding the other two',
         '// hundred-odd pieces of a furnished house is work whose every loc_add is a client update for a',
         '// loc that is already there.',
         '//',
         '// Reported as "when removing a item in poh there is a loding delay" (DeathPlateau-Bugs#64). The',
         '// delay is this: taking out one chair re-placed the whole house.',
         '//',
         '// It still scans all ^poh_furn_slots, because the slots are not grouped by room and a piece\'s',
         '// room is a field inside its packed value - the saving is in the loc_adds, which is where the',
         '// cost is. Same shape as ~poh_furn_at and ~poh_furn_clear_cell above.',
         '//',
         '// NO "its room is gone" BRANCH, unlike ~poh_furn_restore: the caller has just re-laid this room,',
         '// so the room is there by construction.',
         '[proc,poh_furn_restore_room](coord $base, int $rx, int $rz)', 'def_int $i = 0;',
         'while ($i < ^poh_furn_slots) {', '    def_int $v = ~poh_furn_get($i);', '    if ($v ! 0) {',
         '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
         '            def_coord $spot = movecoord($base, calc((^poh_grid_origin + $rx) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lx, 3)), 0, calc((^poh_grid_origin + $rz) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lz, 3)));',
         '            ~poh_furn_show(~poh_furn_item($v), $spot, ~poh_furn_field($v, ^poh_furn_bit_angle, 2), ~poh_furn_field($v, ^poh_furn_bit_lit, 1));',
         '        }', '    }', '    $i = calc($i + 1);', '}', '',
         '// Re-lay one room and put its furniture back. The template is the truth about what a hotspot was, so',
         '// taking something out is a re-lay rather than an attempt to reconstruct the hotspot by hand.',
         '[proc,poh_furn_relay](int $rx, int $rz)',
         '~poh_place_zone(%poh_instance, $rx, $rz);',
         '~poh_furn_restore_room(%poh_instance, $rx, $rz);', '',
         '// =========================================================================== the menu', '',
         '// The nth (0-based) piece in this family, whatever the player\'s level. The window shows the whole',
         '// family and dims the tiers above you - see ~poh_furn_slot0 - so the level is not a filter here.',
         '//',
         '// Two lookups, because a family\'s pieces are consecutive (poh_fam_first/last, asserted by the',
         '// generator and by battery check 51). The walk this replaces read all %d rows per window row per'
         % len(items),
         '// page, which is the shape that cost the room window its instruction budget.',
         '[proc,poh_furn_nth](int $fam, int $n)(int)',
         'def_int $item = calc(enum(int, int, poh_fam_first, $fam) + $n);',
         'if ($item > enum(int, int, poh_fam_last, $fam)) {', '    return(0);', '}',
         'return($item);', '',
         '// =========================================================================== what the window shows', '',
         '// The model each piece is shown by in poh_furnmenu: the first model its loc names, resolved',
         '// through model.pack. if_setmodel takes a RAW id, not a symbol, so these are numbers - and',
         '// battery check 30 reads every one back out of model.pack and fails if a name ever moves under',
         '// them. The zoom that frames each of these is ~poh_furn_zoom, next to the window it fills.',
         '[proc,poh_furn_model](int $item)(int)', 'switch_int ($item) {']
    for i in items:
        o.append('    case %d : return(%d);   // %s' % (i['n'], i['modelid'], i['model']))
    o += ['    case default : return(0);', '}', '',
          '// =========================================================================== the click', '',
          '[proc,poh_furn_click](int $fam)',
          '~poh_furn_click_at($fam, -1, -1);', '',
          '// A family with an ANCHOR is stored at a fixed tile of the room rather than at the tile that',
          '// was clicked. Only a piece that covers more than one tile needs it: the combat ring has',
          '// sixteen hotspots and one ring, so whichever you click it has to be stored, found and',
          '// removed in the same place, and the anchor is a tile nothing is ever built on.',
          '[proc,poh_furn_click_at](int $fam, int $ax, int $az)',
          'if (%poh_instance = null) {', '    mes("You can only build in your own house.");', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'if (instance_find($spot) ! %poh_instance) {',
          '    mes("You can only build in your own house.");', '    return;', '}',
          'if (inv_total(inv, hammer) < 1 | inv_total(inv, saw) < 1) {',
          '    mes("You need a hammer and a saw to build furniture.");', '    return;', '}',
          'def_int $angle = loc_angle;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $lx = modulo($gx, 8);', 'def_int $lz = modulo($gz, 8);',
          'if ($ax >= 0) {',
          '    $spot = movecoord($spot, calc($ax - $lx), 0, calc($az - $lz));',
          '    $lx = $ax;', '    $lz = $az;', '    $angle = 0;', '}',
          'if (~poh_furn_free < 0) {',
          '    mes("Your house is as full of furniture as it will hold.");', '    return;', '}',
          'def_int $item = ~poh_furn_pick($fam, "Select what you want to build");',
          'if ($item = 0) {', '    mes("There\'s nothing you can build here yet.");', '    return;', '}',
          '// A flatpack is spent in place of the materials, and it is PREFERRED when you hold both -',
          '// it is the scarcer thing and the message says which was used. The experience does not',
          '// change either way: in OSRS the xp is paid for putting the furniture together, which is',
          '// what makes a flatpack worth buying, and making one at the workbench pays none.',
          'def_namedobj $flat = enum(int, namedobj, poh_furn_flat, $item);',
          'def_int $useflat = 0;',
          'if ($flat ! null) {',
          '    if (inv_total(inv, $flat) > 0) {', '        $useflat = 1;', '    }', '}',
          'if ($useflat = 0 & ~poh_furn_have($item) = false) {',
          '    mes("You need <enum(int, string, poh_furn_need, $item)> to build that.");',
          '    return;', '}',
          '// re-check after the menu: it suspends, and the slot or the materials can go while it is open',
          'def_int $slot = ~poh_furn_free;',
          'if ($slot < 0 | ~poh_furn_at($rx, $rz, $lx, $lz) ! -1) {',
          '    mes("Something is in the way.");', '    return;', '}',
          'if ($useflat = 1) {',
          '    if (inv_total(inv, $flat) < 1) {', '        $useflat = 0;', '    }', '}',
          'if ($useflat = 0 & ~poh_furn_have($item) = false) {',
          '    mes("You need <enum(int, string, poh_furn_need, $item)> to build that.");',
          '    return;', '}',
          'if ($useflat = 1) {',
          '    inv_del(inv, $flat, 1);',
          '} else {',
          '    ~poh_furn_take($item);',
          '}',
          '~poh_furn_set($slot, ~poh_furn_pack($rx, $rz, $lx, $lz, $angle, $item));',
          '~poh_furn_show($item, $spot, $angle, 0);',
          # Through ~construction_xp, not stat_advance, so the carpenter's outfit pays its bonus
          # and a piece of it can turn up - the same funnel the other six skilling outfits ride on.
          #
          # Read ONCE into $cxp, because the garden pays the same number a second time in Farming
          # and two reads would be two places for it to drift. Farming gets the base amount, not
          # $cxp plus the carpenter's bonus, because that outfit is a Construction outfit.
          'def_int $cxp = enum(int, int, poh_furn_xp, $item);',
          '~construction_xp($cxp);',
          '// A garden piece pays the same again in Farming - OSRS gives both for a bagged plant.',
          'if (enum(int, int, poh_furn_garden, $item) = 1) {',
          '    stat_advance(farming, $cxp);',
          '}',
          'if ($useflat = 1) {',
          '    mes("You assemble the <enum(int, string, poh_furn_name, $item)> from its flatpack.");',
          '} else {',
          '    mes("You build the <enum(int, string, poh_furn_name, $item)>.");',
          '}', '',
          '// Taking a piece out. No refund and no materials back, as in OSRS.',
          '[proc,poh_furn_remove]',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $slot = ~poh_furn_at($rx, $rz, modulo($gx, 8), modulo($gz, 8));',
          'if ($slot < 0) {', '    mes("That isn\'t yours to take out.");', '    return;', '}',
          'def_int $item = ~poh_furn_item(~poh_furn_get($slot));',
          '// The last way out of a house stays where it is. OSRS refuses this too, and here it would',
          '// leave the player sealed in an instance with no portal and no door to Rimmington.',
          'if ($item = ^poh_furn_exit_portal) {',
          '    if (~poh_furn_count_item(^poh_furn_exit_portal) < 2) {',
          '        mes("That is the only way out of your house - you had better leave it there.");',
          '        return;', '    }', '}',
          'def_int $option = ~p_choice2("Take out the <enum(int, string, poh_furn_name, $item)>.", 1, "Leave it.", 2);',
          'if ($option ! 1) {', '    return;', '}',
          '~poh_furn_set($slot, 0);', '~poh_furn_relay($rx, $rz);',
          'mes("You take out the <enum(int, string, poh_furn_name, $item)>. The materials are gone.");', '',
          '// =========================================================================== triggers',
          '//',
          '// Each hotspot passes its own family in, so nothing has to look one up from a loc id. The hotspot',
          '// locs and the shapes they are placed at were read out of the six style squares, not assumed.', '']
    byid = {v: k for k, v in packmap('pack/loc.pack').items()}
    for f in fams:
        for h in f['hotspots']:
            if f.get('anchor'):
                o += ['[oploc5,%s]' % byid[h],
                      '~poh_furn_click_at(^poh_fam_%s, %d, %d);' % (f['key'], *f['anchor']), '']
            else:
                o += ['[oploc5,%s]' % byid[h], '~poh_furn_click(^poh_fam_%s);' % f['key'], '']
    o += ['// One per buildable LOC: every piece keeps its own op5=Remove from poh.loc. Per loc and not',
          '// per piece, because a loc can be buildable in two hotspots (the exit portal is the',
          '// centrepiece of both gardens) and a trigger declared twice does not compile.', '']
    # A family may name its OWN removal proc. The combat ring does: it stands on 36 tiles and is
    # stored at the room's anchor rather than under the piece you clicked, so ~poh_furn_remove -
    # which looks the slot up under the clicked tile - would never find it.
    for loc, fam in dict((i['loc'], byfam[i['famkey']]) for i in items).items():
        o += ['[oploc5,%s]' % loc, '~%s;' % fam.get('remove', 'poh_furn_remove'), '']
    return o

OPS_HEAD = """// What the furniture DOES. One [oploc1] per piece, generated from the op1 block of each family in
// tools/furnspec.json.
//
// Every op these locs carry sits at op1 - checked across all {n} pieces - so the trigger is always
// oploc1 and there is no per-family index to get wrong. The op's WORDS are in the spec too: a
// generator that invents flavour text is a generator nobody can review.
//
// WHAT IS NOT HERE. Study (lecterns) is teleport tablets and needs the tablet objs; Work-at
// (workbenches) is flatpacks and needs one obj per piece of furniture; Craft, Open, Change-clothes,
// Upgrade, Activate, Set-up, Shoot-at, Throw-at, Challenge-mode, Pull, Use and Make-helmet each need
// new objects, a new interface, or a servant. The spec says so next to each family.
"""

def q(s):
    return '"%s"' % s.replace('"', "'")

def emit_ops(fams, items, byfam, path='scripts/skill_construction/scripts/poh_furn_ops.rs2'):
    lit_items = [i for i in items if (byfam[i['famkey']].get('op1') or {}).get('kind') == 'light']
    o = OPS_HEAD.format(n=len(items)).split('\n')

    o += ['// =========================================================================== lighting', '',
          '// Lighting is REMEMBERED - bit %d of the packed record - so a fire is still burning after you'
          % dict((n, sum(w for _, w in BITS[:i])) for i, (n, w) in enumerate(BITS))['lit'],
          '// build a room somewhere else and the house is laid out again. A record written before this',
          '// field existed has 0 there, which reads as unlit, which is what it was.',
          '[proc,poh_furn_light](string $mes)',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {',
          '    if (~poh_in_house(loc_coord) = true) {',
          '        mes("Only the owner of the house can light that.");', '    }',
          '    return;', '}',
          'if (inv_total(inv, tinderbox) < 1) {',
          '    mes("You need a tinderbox to light that.");', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $slot = ~poh_furn_at(calc(divide($gx, 8) - ^poh_grid_origin), calc(divide($gz, 8) - ^poh_grid_origin), modulo($gx, 8), modulo($gz, 8));',
          'if ($slot < 0) {', '    return;', '}',
          'def_int $v = ~poh_furn_get($slot);',
          'if (~poh_furn_field($v, ^poh_furn_bit_lit, 1) = 1) {',
          '    mes("It is already lit.");', '    return;', '}',
          '~poh_furn_set($slot, setbit_range_toint($v, 1, ^poh_furn_bit_lit, ^poh_furn_bit_lit));',
          'anim(human_pickupfloor, 0);',
          'sound_synth(tinderbox_strike, 1, 0);',
          '~poh_furn_show_lit(~poh_furn_item($v), $spot, ~poh_furn_field($v, ^poh_furn_bit_angle, 2));',
          'mes($mes);', '',
          '// =========================================================================== the altar', '',
          '// What the altar pays for a set of bones, as a percentage of what burying them gives. OSRS pays',
          '// 250% at a plain altar and 350% at the best one, and another 50% for each of the two burners',
          '// beside it. NOT cache data - the tunable part, like the room prices.',
          '[proc,poh_furn_altar_bonus](int $item)(int)',
          'def_int $pct = calc(^poh_altar_base + calc(enum(int, int, poh_furn_tier, $item) - 1) * ^poh_altar_step);',
          'return(calc($pct + ~poh_furn_lit_in_room * ^poh_altar_burner));', '',
          '// How many lit things stand in the room the player is standing in. A linear scan, like every',
          '// other question this design asks about the furniture.',
          "// A guest reads the owner's furniture: the burners their bones are offered by are the owner's.",
          '[proc,poh_furn_lit_in_room]()(int)',
          'def_coord $base = ~poh_here;',
          'if ($base = null) {', '    return(0);', '}',
          'def_int $rx = calc(divide(calc(coordx(coord) - coordx($base)), 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide(calc(coordz(coord) - coordz($base)), 8) - ^poh_grid_origin);',
          'def_int $i = 0;', 'def_int $n = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get_here($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_lit, 1) = 1) {',
          '            if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '                $n = calc($n + 1);', '            }', '        }', '    }',
          '    $i = calc($i + 1);', '}', 'return($n);', '',
          '// Anything with a bone_exp param may be offered, which is the same test burying uses - so a bone',
          '// added to the game later works here without this file knowing it exists.',
          '[proc,poh_furn_offer](int $item)',
          'if (~poh_in_house(loc_coord) = false) {', '    return;', '}',
          'def_obj $bone = last_useitem;',
          'if (oc_param($bone, bone_exp) <= 0) {',
          '    mes("The gods have no use for that.");', '    return;', '}',
          'def_int $pct = ~poh_furn_altar_bonus($item);',
          # Zealot's robes may leave the remains intact, here exactly as when burying them. The
          # experience is paid either way - see skill_prayer/scripts/bury_bone.rs2, which is the
          # other half of this and the one a person is more likely to find first.
          'def_boolean $saved = ~zealots_saves;',
          'if ($saved = false) {',
          '    inv_del(inv, $bone, 1);',
          '}',
          'anim(human_pray, 0);',
          'sound_synth(prayer_recharge, 1, 0);',
          # Through ~prayer_xp so the altar rolls for a Zealot's piece like every other Prayer
          # action. A direct stat_advance here is how the carpenter's outfit could have been
          # wired and still never turned up - see skilling_outfits/scripts/outfit_xp.rs2.
          '~prayer_xp(calc(oc_param($bone, bone_exp) * $pct / 100));',
          'if ($saved = true) {',
          '    mes("You offer the bones. The gods are pleased, and your robes preserve them.");',
          '} else {',
          '    mes("You offer the bones. The gods are pleased.");',
          '}', '',
          '// =========================================================================== sitting', '',
          '// 377 HAS NO SEATED STATE, so this is a pose and not something the engine holds: the seq',
          '// plays once and the player stands back up. What it can do is play in the right PLACE.',
          '// An oploc1 click walks the player adjacent to the loc, which is why Sit-on used to leave',
          '// them standing beside an empty chair; p_walk puts them on the tile and facesquare turns',
          '// them the way the chair faces.',
          '//',
          '// human_sitting_chair is the right animation and always was - four npcs in all.npc carry',
          '// it as their readyanim, which is a seated idle by definition.',
          '[proc,poh_furn_sit](seq $seq, string $mes)',
          'if (~poh_in_house(loc_coord) = false) {',
          '    mes("You can only use that in a house you are in.");', '    return;', '}',
          'def_coord $seat = loc_coord;',
          'def_int $angle = loc_angle;',
          'p_walk($seat);',
          'p_arrivedelay;',
          '// the tile the chair looks at: angle 0 is north, and the cycle is N E S W',
          'switch_int ($angle) {',
          '    case 0 : facesquare(movecoord($seat, 0, 0, 1));',
          '    case 1 : facesquare(movecoord($seat, 1, 0, 0));',
          '    case 2 : facesquare(movecoord($seat, 0, 0, -1));',
          '    case default : facesquare(movecoord($seat, -1, 0, 0));',
          '}',
          'anim($seq, 0);',
          'mes($mes);', '',
          '// =========================================================================== the triggers', '']

    KIND = {}
    def add(fam, item, lines):
        KIND.setdefault(fam, []).append((item, lines))
    for i in items:
        f = byfam[i['famkey']]
        op = f.get('op1')
        if not op:
            continue
        k = op['kind']
        if k == 'sit':
            # ON the chair, not beside it. An oploc1 click walks the player ADJACENT to the loc, so
            # the seated pose used to play with the player standing next to an empty chair, which is
            # what it looked like in game. ~poh_furn_sit walks onto the tile and turns to face the
            # way the chair faces first.
            body = ['~poh_furn_sit(%s, %s);' % (op['seq'], q(op['mes']))]
        elif k == 'light':
            body = ['~poh_furn_light(%s);' % q(op['mes'])]
        elif k == 'altar':
            body = ['@pray_at_altar(stat_base(prayer));']
        elif k == 'jingle':
            body = ['midi_jingle(%s);' % q(op['midi']), 'mes(%s);' % q(op['mes'])]
        elif k == 'clock':
            body = ['mes("The clock says it is <tostring(divide(modulo(map_clock, 6000), 250))> o\'clock.");']
        elif k == 'observe':
            body = ['switch_int (random(%d)) {' % len(op['lines'])]
            for n, l in enumerate(op['lines']):
                body.append('    case %d : mes(%s);' % (n, q(l)))
            body.append('    case default : mes(%s);' % q(op['lines'][0]))
            body.append('}')
        elif k == 'talk':
            body = ['mes(%s);' % q(op['lines'][min(i['tier'], len(op['lines'])) - 1])]
        elif k == 'preen':
            body = ['anim(%s, 0);' % op['seq'], 'mes(%s);' % q(op['mes'])]
        elif k == 'mes':
            body = ['mes(%s);' % q(l) for l in op['lines']]
        elif k == 'direct':
            body = ['~poh_portal_direct;']
        elif k == 'wardrobe':
            body = ['~poh_wardrobe;']
        elif k == 'store':
            # The five costume-room storage spaces. They all go through one set of procs; which
            # store this is decides the window into poh_store_item, and the piece decides the
            # capacity the same way the treasure chest's does.
            body = ['~poh_store_open(%d, %d);' % (op['store'], i['n'])]
        elif k == 'costume':
            # the piece is passed in so its tier can set the capacity, the same way the altar's
            # offer trigger passes the piece it is standing on
            body = ['~poh_costume_open(%d);' % i['n']]
        elif k == 'study':
            # The lectern window, and the only op1 whose body depends on WHICH piece it is: a
            # lectern's tier is which of the seven it is, and that is what decides its tablet list.
            body = ['~poh_tab_pick(%d);' % i['tier']]
        else:
            raise SystemExit('unknown op kind %r on %s' % (k, f['key']))
        o += ['[oploc1,%s]' % i['loc']] + body + ['']
        if k == 'light':
            o += ['[oploc5,%s]' % op['lit'][i['tier'] - 1], '~poh_furn_remove;', '']
        if k == 'altar':
            o += ['[oplocu,%s]' % i['loc'], '~poh_furn_offer(%d);' % i['n'], '']
    write(path, o)
    return lit_items

if __name__ == '__main__':
    SLOTS = int(sys.argv[1]) if len(sys.argv) > 1 else 256
    fams, items = build()
    shapes = map_shapes()
    bad = []
    for f in fams:
        # A family that hands its placement to a proc does not use its own shape for anything - the
        # proc lays each tile with that tile's own. The combat ring's sixteen hotspots are walls,
        # corners and ground decor all at once, so no single shape could be right here; what
        # replaces this check for it is battery group 59, which reads every emitted loc_add back
        # against the template and is the stronger test.
        if f.get('show'):
            continue
        for h in f['hotspots']:
            have = shapes.get(h, set())
            if f['shape'] not in have:
                bad.append((f['key'], h, f['shape'], sorted(have)))
    allowed = {(x['family'], x['hotspot']) for x in json.load(open(SPEC)).get('shape_allowances', [])}
    unexplained = [b for b in bad if (b[0], b[1]) not in allowed]
    for b in bad:
        print('  %s hotspot %d: family says %s, the templates say %s%s'
              % (b[0], b[1], b[2], b[3], '' if (b[0], b[1]) in allowed else '   <-- NOT ALLOWED'))
    if unexplained:
        raise SystemExit('%d hotspot shapes disagree with the templates and are not in '
                         'shape_allowances; nothing written' % len(unexplained))
    flatids = emit_flatpack_pack(fams, items)
    nflat = emit_flatpacks(fams, items, flatids)
    emit_enum(fams, items, 'scripts/skill_construction/configs/poh_furniture.enum')
    emit_varp(fams, items, SLOTS, 'scripts/skill_construction/configs/construction.varp')
    ids = emit_varp_pack(SLOTS)
    emit_constant(fams, items, SLOTS)
    head, byfam = emit_rs2(fams, items, SLOTS)
    write('scripts/skill_construction/scripts/poh_furniture.rs2', head + emit_rs2_tail(fams, items, byfam))
    lit = emit_ops(fams, items, byfam)
    print('%d pieces answer op1, %d of them can be lit' %
          (sum(1 for i in items if byfam[i['famkey']].get('op1')), len(lit)))
    print('%d flatpacks on %d shared models' % (nflat, len({f['key'] for f in fams if f.get('flatpack')})))
    print('%d families, %d items, %d hotspots, %d slots (varp ids up to %d)'
          % (len(fams), len(items), sum(len(f['hotspots']) for f in fams), SLOTS, max(i for i, _ in ids)))
