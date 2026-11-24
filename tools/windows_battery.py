#!/usr/bin/env python3
"""Checks for the four cache windows: smelting, tanning, silver casting and the churn.

WHAT THIS HAS TO ANCHOR AGAINST, AND WHY IT IS NOT THE CACHE FILE. The ancient-spellbook round
could check its generated panel against scripts/interfaces/inter_267.if, because that file stayed
in the tree as the generator's input. These six panels were ADOPTED instead - renamed and moved -
so the cache file is gone, and a check that reads only the adopted file would be checking the
generator against itself.

So every group below anchors on something this round did not write:

  - the 377 loc configs, which say op2=Smelt on seven furnaces and op1=Churn on two dairy churns
  - the 377 npc config, which says op3=Trade on Ellis
  - scripts/_unpack/727/all.inv, which carries Jagex's own seven silvercast_* inventories, one per
    slot of the Silver Casting panel, each stocking the product that slot shows
  - smelting.struct, which has the level, the ores and the experience for all eight bars
  - tanner.constant, which has both tanners' prices

    python3 tools/windows_battery.py
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
FAILED = []
GROUP = ['']


def group(t):
    GROUP[0] = t
    print(t)


def ok(msg, extra=''):
    print('  ok   %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))


def bad(msg, extra=''):
    print('  FAIL %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))
    FAILED.append('%s / %s' % (GROUP[0], msg))


def check(cond, msg, extra=''):
    (ok if cond else bad)(msg, extra)


def read(p):
    return open(p, encoding='utf-8', errors='ignore').read()


def nocomment(t):
    """Strip // comments. Three rounds have had a check find the very thing its own comment quoted."""
    return re.sub(r'//[^\n]*', '', t)


def blocks(text):
    out = []
    for b in re.split(r'\n(?=\[)', text):
        m = re.match(r'\[([^\]]+)\]', b)
        if m:
            out.append((m.group(1), dict(re.findall(r'^(\w+)=(.*)$', b, re.M)), b))
    return out


SPEC = json.load(open('tools/adoptspec.json', encoding='utf-8'))
PANELS = {p['iface']: p for p in SPEC['panels']}
RS2 = {}
for dp, _, fs in os.walk('scripts'):
    if '_unpack' in dp:
        continue
    for f in fs:
        if f.endswith('.rs2'):
            # keyed with forward slashes, so the lookups below work on Windows as well as in CI
            RS2[os.path.join(dp, f).replace(os.sep, '/')] = read(os.path.join(dp, f))
ALLRS2 = nocomment('\n'.join(RS2.values()))
LOC = read('scripts/_unpack/377/all.loc')
NPC = read('scripts/_unpack/377/all.npc')
INV727 = read('scripts/_unpack/727/all.inv')
LOCPACK = set(l.strip().split('=', 1)[1] for l in open('pack/loc.pack') if '=' in l)
OBJPACK = set(l.strip().split('=', 1)[1] for l in open('pack/obj.pack') if '=' in l)
INVPACK = set(l.strip().split('=', 1)[1] for l in open('pack/inv.pack') if '=' in l)


# ---------------------------------------------------------------- 1
group('1. the ops the cache advertises, which is why this round exists')
smelt_locs = [n for n, kv, _ in blocks(LOC) if kv.get('op2') == 'Smelt' and n in LOCPACK]
check(len(smelt_locs) == 7, 'furnaces in the loc pack that say op2=Smelt', len(smelt_locs))
check(re.search(r'\[oploc2,_smithing_furnace\]', ALLRS2) is not None,
      'and oploc2 on the smithing_furnace category is answered now', 'yes')
cats = {n: re.search(r'^category=(\w+)$', b, re.M).group(1)
        for n, kv, b in blocks(LOC) if re.search(r'^category=(\w+)$', b, re.M)}
check(all(cats.get(n) == 'smithing_furnace' for n in smelt_locs),
      'every one of them is in the smithing_furnace category, which is what the trigger covers',
      'all %d' % len(smelt_locs))
churn_locs = [n for n, kv, _ in blocks(LOC) if kv.get('op1') == 'Churn' and n in LOCPACK]
check(sorted(churn_locs) == sorted(PANELS['churn_milk']['content']['locs']),
      'the dairy churns the spec names are exactly the locs that say op1=Churn', churn_locs)
for n in churn_locs:
    check(('[oploc1,%s]' % n) in ALLRS2, 'oploc1 on %s is answered now' % n, 'yes')
ellis = [kv for n, kv, _ in blocks(NPC) if n == 'ellis_tanner'][0]
check(ellis.get('op3') == 'Trade', "Ellis's own npc config says op3=Trade", ellis.get('op3'))
check('[opnpc3,ellis_tanner]' in ALLRS2, 'and opnpc3 on Ellis is answered now', 'yes')
check(ALLRS2.count('[opnpc3,werewolftanner]') == 1,
      'the Canifis tanner still has exactly one opnpc3 - a duplicate trigger is a build error', 1)


# ---------------------------------------------------------------- 2
group('2. the smelt window is the eight bars the game already knows how to smelt')
structs = [n for n, _, _ in blocks(read('scripts/skill_smithing/configs/smelting/smelting.struct'))]
bars = PANELS['smelt_window']['content']['bars']
want = ['smelting_%s' % b['obj'] for b in bars]
check(all(w in structs for w in want), 'every column has a smelting_struct block', len(want))
check(len(bars) == 8, 'eight columns', len(bars))
panel = read('scripts/skill_smithing/interfaces/smelt_window.if')
btn = {}
for n, kv, _ in blocks(panel):
    m = re.match(r'^Smelt (X|10|5|1) @lre@([A-Za-z]+)$', kv.get('option', ''))
    if m:
        btn.setdefault(m.group(2).lower(), []).append((n, int(kv['x'])))
check(len(btn) == 8, "the panel's own option text names eight bars", sorted(btn))
xs = sorted((v[0][1], k) for k, v in btn.items())
check([k for _, k in xs] == [b['column'] for b in bars],
      'and left to right they are the spec order, which is NOT the struct file order',
      ' '.join(k for _, k in xs))
check([n for n, _, _ in blocks(read('scripts/skill_smithing/configs/smelting/smelting.struct'))
       ].index('smelting_steel_bar') < structs.index('smelting_silver_bar'),
      'the struct file really does list steel before silver, which the panel does the other way',
      'yes')
icons = [n for n, kv, _ in blocks(panel) if kv.get('type') == 'model']
check(len(icons) == 8, 'eight icon components', len(icons))
sw = RS2['scripts/skill_smithing/scripts/smelting/smelt_window.rs2']
# WHICH BAR EACH ICON SHOWS, WITHOUT READING THE SPEC THE GENERATOR WROTE FROM. An earlier version
# asserted icon<i> is set to bars[i]['obj'] - both sides of which came out of adoptspec.json, so a
# spec that said bronze's icon was an iron bar passed. The panel decides instead: an icon belongs
# to the button column at the same x, that button's option text says which bar it is, and the obj
# the rs2 sets has to be that bar. bronze -> bronze_bar, adamant -> adamantite_bar, rune ->
# runite_bar: the column word is a prefix of the obj name in all eight cases.
icon_x = sorted(int(kv['x']) for n, kv, _ in blocks(panel) if kv.get('type') == 'model')
icon_name = {int(kv['x']): n for n, kv, _ in blocks(panel) if kv.get('type') == 'model'}
for col, xcol in ((k, x) for x, k in xs):
    near = min(icon_x, key=lambda ix: abs(ix - xcol))
    m = re.search(r'if_setobject\(smelt_window:%s, (\w+), ' % icon_name[near], sw)
    # Three characters, not a full prefix: the Rune column's bar is runite_bar and the Adamant
    # column's is adamantite_bar, so "the column word starts the obj name" is false for two of the
    # eight. A first draft of this check used five characters and went red on Rune - which is the
    # rule about a hand-written pattern producing a false negative, met for the fourth time.
    shared = len(os.path.commonprefix([col, m.group(1)])) if m else 0
    check(shared >= 3, 'the icon over the %s column is set to a %s bar' % (col, col),
          m.group(1) if m else 'not set')
check(len([1 for n, kv, _ in blocks(panel) if kv.get('buttontype') == 'normal']) == 32,
      'thirty-two smelt buttons', 32)
setto = re.findall(r'if_setobject\(smelt_window:icon\d+, (\w+), ', sw)
check(len(setto) == len(set(setto)) == 8, 'and eight different bars, one per icon', len(set(setto)))


# ---------------------------------------------------------------- 3
group('3. one smelt, not two')
sm = RS2['scripts/skill_smithing/scripts/smelting/smelting.rs2']
check(nocomment(sm).count('[proc,smelt_bar]') == 1, '~smelt_bar is defined once', 1)
callers = sorted(p for p, t in RS2.items() if '~smelt_bar(' in nocomment(t))
check(len(callers) == 2, 'and called from exactly two places - the ore path and the window',
      ', '.join(os.path.basename(c) for c in callers))
# The window must not carry its own copy of the act. An earlier version of this check counted
# copies across "every file with smelting in its path", which also caught cannonballs.rs2 - a
# different recipe that legitimately has its own animation and its own xp call. A check that goes
# red on correct code gets switched off, so it asks the narrow question instead.
for line in ('anim(human_furnace', '~smithing_xp(', 'inv_add(inv, $bar', 'struct_param($struct, productexp)'):
    check(line not in nocomment(sw),
          'smelt_window.rs2 does not do %r itself' % line, 'yes')
check(nocomment(sw).count('~smelt_bar(') == 1, 'it calls ~smelt_bar once and does the rest through it', 1)
check(nocomment(sm).count('~smelt_bar(') == 1, 'and so does the use-an-ore-on-the-furnace path', 1)
# THE ONE ARGUMENT THE TWO PATHS DISAGREE ON, and the whole of DeathPlateau-Bugs#85. ~smelt_bar's
# p_delay sets player.delayed, and MoveClickHandler throws away a move click while that is set, so
# a batch that held the player for every bar could not be stopped. One click for one bar can afford
# the hold; the window's queue paces itself and must not ask for it. tools/sim/smeltstop.ts measures
# the consequence against the running engine - this is here so that flipping the argument back is
# caught by the content's own checks before it reaches a sim.
check('~smelt_bar($struct, $bar, false);' in nocomment(sw),
      'and the window asks NOT to be held, so the run can be stopped', 'false')
check('~smelt_bar($struct, $bar, true);' in nocomment(sm),
      'while one ore on the furnace still pays its own delay', 'true')


# ---------------------------------------------------------------- 4
group('4. the tanner, and both tanners charging their own prices')
con = read('scripts/areas/area_alkharid/configs/tanner.constant')
tw = RS2['scripts/skill_crafting/scripts/leather/tan_window.rs2']
rows = PANELS['tan_window']['content']['rows']
for r in rows:
    for key in ('alkharid', 'canifis'):
        check(('^%s =' % r[key]) in con, '%s is a real constant' % r[key], 'yes')
        check(('^' + r[key]) in tw, 'and the window reads it', 'yes')
check(len(set(r['alkharid'] for r in rows)) == 3, 'three distinct Al Kharid prices', 3)
vals = {m.group(1): int(m.group(2)) for m in re.finditer(r'\^(\w+) = (\d+)', con)}
pairs = [(vals[r['alkharid']], vals[r['canifis']]) for r in rows]
check(all(c > a for a, c in pairs), 'Canifis charges more for every hide', pairs)
soft = vals[rows[0]['canifis']] - vals[rows[0]['alkharid']]
hide = vals[rows[2]['canifis']] - vals[rows[2]['alkharid']]
check(soft != hide,
      'and not by a fixed markup, which is why both constants are read rather than one plus an offset',
      'soft +%d, dragonhide +%d' % (soft, hide))
# THE POINTER, WHICH COST A BUILD. npc_type needs the active_npc pointer. [opnpc3,...] has it and
# [if_button,...] does not, so the first version of this window asked npc_type inside ~tan_window_cost
# - reached from all 32 buttons - and the server build refused it 32 times over.
#
# A general rs2check rule for this was written and MEASURED before being dropped: following every
# button-family trigger through its calls to a read of npc_type gives NINE hits on a tree that
# compiles, all of them through ~chatnpc, which is allowed there for a reason this round did not
# work out. Second pointer lint attempted and abandoned; the compiler is the checker, and the fact
# that this sandbox cannot run one is the real gap rather than a missing rule. So the check below
# is narrow and about this round's own files, where it cannot cry wolf.
check(nocomment(tw).count('npc_type') == 1,
      'tan_window.rs2 reads npc_type exactly once', nocomment(tw).count('npc_type'))
opener = nocomment(tw).split('[proc,tan_window_open]', 1)[-1].split('\n[', 1)[0]
check('npc_type' in opener,
      'and it is inside [proc,tan_window_open], which an opnpc3 trigger reaches with the npc still in scope',
      'yes')
check('%tan_window_canifis' in nocomment(tw),
      'the answer is kept in a varp so the buttons never have to ask', 'yes')
for f, t in RS2.items():
    if 'tan_window' in f or 'smelt_window' in f or 'silver_casting' in f or 'churn' in f:
        after = nocomment(t).split('[if_button', 1)[-1] if '[if_button' in t else ''
        check('npc_type' not in after,
              'nothing after the first button trigger in %s reads npc_type' % os.path.basename(f), 'yes')
# nocomment, because that file's own comment explains WHY scope=temp is there - so a check reading
# the raw text stays green when the block itself is changed. Third time in this round that a check
# or a mutation has found its own comment instead of its code.
vp = nocomment(read('scripts/skill_crafting/configs/leather/tan_window.varp'))
check('scope=temp' in vp and 'protect=no' in vp,
      'and that varp is scope=temp protect=no, the pair skill_guide.varp carries for the same reason',
      'yes')
# A VARP IS AN int UNLESS IT SAYS type=boolean, and this one is read and written as a boolean. The
# first version left the type off and the build refused three lines in one file. rs2check rule 24
# is the general version; this is the local one.
check('type=boolean' in vp, 'and it is type=boolean, because the script reads it as one', 'yes')
tp = read('scripts/skill_crafting/interfaces/tan_window.if')
cells = [n for n, kv, _ in blocks(tp) if kv.get('type') == 'layer']
check(len(cells) == 8, 'the panel has eight cells', 8)
check(len(rows) == 6, 'six of them are tannable in this build', len(rows))
for i in (7, 8):
    check('if_sethide(tan_window:cell%d, true);' % i in tw,
          'cell %d is hidden rather than left dead' % i, 'yes')
for r in rows:
    check(r['hide'] in OBJPACK and r['leather'] in OBJPACK,
          '%s -> %s are both packed objs' % (r['hide'], r['leather']), 'yes')


# ---------------------------------------------------------------- 5
group("5. silver casting: Jagex's own seven inventories name the seven slots")
prods = PANELS['silver_casting']['products']
inv_stock = {n: kv.get('stock1', '').split(',')[0] for n, kv, _ in blocks(INV727)}
for p in prods:
    check(p['inv'] in INVPACK, '%s has an inv id' % p['inv'], 'yes')
for p in prods:
    if p['inv'] in inv_stock:
        check(inv_stock[p['inv']] == p['obj'],
              "%s stocks the obj the spec says that slot shows" % p['inv'],
              '%s' % inv_stock[p['inv']])
check(len(prods) == 7, 'seven products', 7)
check(all(p['obj'] in OBJPACK for p in prods), 'and all seven objs are in the obj pack', 'yes')
wired = [p for p in prods if p['struct']]
check(len(wired) == 4, 'four are wired, because four have a Crafting recipe to read', len(wired))
js = read('scripts/skill_crafting/configs/jewellery/jewellery.struct')
sn = [n for n, _, _ in blocks(js)]
for p in wired:
    check(p['struct'] in sn, '%s has a crafting_jewelry struct' % p['key'], p['struct'])
sv = RS2['scripts/skill_crafting/scripts/jewellery/silver_casting.rs2']
check(nocomment(sv).count('[oplocu,') == 0,
      'silver_casting.rs2 declares no oplocu of its own - smelting.rs2 owns that trigger', 0)
check('~silver_casting_open;' in nocomment(sm), 'and the silver_bar case calls into it', 'yes')
check('@craft_silver;' not in nocomment(sm), 'the old cascade is no longer what a silver bar reaches', 'yes')
for p in prods:
    for side in ('make', 'need'):
        check('if_sethide(silver_casting:%s_%s,' % (side, p['key']) in sv,
              'the %s layer for %s is driven' % (side, p['key']), 'yes')
# WHICH SLOTS GET FILLED IN, and the one thing no check here was holding. tools/genwindows.py
# decides it with `if p['struct'] or p.get('handler')`: a product whose recipe is owned either by a
# crafting struct or by a quest gets the LIVE slot - its mould is transmitted and the make/need
# layers flip on whether the player holds it - and anything else stays on the need side for good.
#
# NOTHING PINNED THAT CORRESPONDENCE, which is DeathPlateau-Bugs#89. The check below is a
# disjunction - "never transmitted OR has the quest button" - and lightning_rod satisfies it through
# its button whichever side of the condition it lands on. So the half of the test that reads
# `p.get('handler')` could be dropped and every check in this file stayed green.
#
# This one fails the moment a product's slot disagrees with the reason it has one, in either
# direction: a live slot for a product nothing owns a recipe for, or a dead slot for one that does.
#
# IT IS ALSO RIGHT FOR A SHAPE THE DATA DOES NOT CURRENTLY HAVE. All seven products have a struct
# or a handler today, so the generator's else branch is unreachable and the old mutation row aimed
# at that condition could not change a single byte of the output - which is why no check caught it
# and why the row has been retargeted rather than re-pointed at a new check. A product added later
# with neither wants no transmit, and this asks for exactly that without being touched.
for p in prods:
    live = 'inv_transmit(%s,' % p['inv'] in sv
    owned = bool(p['struct']) or bool(p.get('handler'))
    check(live == owned,
          "%s's slot is filled in exactly when a struct or a quest owns its recipe" % p['key'],
          'yes')

for p in prods:
    if not p['struct']:
        # A WINDOW SLOT WITH NO CRAFTING STRUCT HAS TWO HONEST SHAPES, not one. It can stay dark -
        # nothing transmits it and nothing hands its mould out - or a quest can own it: In Aid of
        # the Myreque hands out burgh_rod_clay and drives silvthrill_rod from this window, with the
        # slot's own [inv_button1] going to @myreque2_cast_rod. What is broken is a slot a player
        # can click with nothing behind it, so the transmit has to come with that button.
        _trans = 'inv_transmit(%s,' % p['inv'] in sv
        _button = '[inv_button1,silver_casting:slot_%s]' % p['key'] in sv
        check(not _trans or _button,
              '%s is either never transmitted or has the quest button that owns its click' % p['key'],
              'yes')
        if p['mould']:
            # NAMED is not GIVEN OUT. An earlier version of this grepped for the mould's name
            # anywhere in the scripts, so wiring the product - which reads the mould to decide
            # which layer to show - tripped this check rather than the one about transmitting.
            #
            # AND "NOBODY HANDS IT OUT" IS NO LONGER THE ONLY RIGHT ANSWER. Two of these three
            # moulds are handed out now - Dr Fenkenstrain gives the conductor mould and the Agrith
            # quest gives the sigil mould - and both quests carry their own recipe on the mould's
            # [opheldu], because a quest step has no Crafting level or experience for this window
            # to copy. So what has to hold is one of two things: either nothing hands the mould
            # out, or whatever does also owns a recipe for it. A mould a player can hold with no
            # recipe anywhere is the broken case, and that is what this catches.
            # A quest can also carry the recipe on THIS WINDOW's button for the slot instead of on
            # the mould - which is what In Aid of the Myreque does with burgh_rod_clay - so that
            # counts as a recipe too.
            _given = re.search(r'inv_add\([^)]*\b%s\b' % p['mould'], ALLRS2) is not None
            _recipe = re.search(r'\[opheldu,%s\]' % p['mould'], ALLRS2) is not None or _button
            check(not _given or _recipe,
                  'nothing hands out %s, or what does owns a recipe for it - on the mould\'s '
                  '[opheldu] or on this window\'s button for the slot' % p['mould'], 'yes')

            # AND THE WINDOW MAY NOT LIE ABOUT A MOULD THE PLAYER IS HOLDING. The check above is
            # satisfied by a recipe existing ANYWHERE, which is how this panel spent months telling
            # a player with the conductor mould in their bag that they needed one: both quest slots
            # were pinned to the need side with if_sethide(make_X, true) regardless of inventory,
            # on the grounds that their quests were not in the build. Both were
            # (DeathPlateau-Bugs#67).
            #
            # So: if something hands the mould out, this slot has to READ it. A slot nobody can
            # ever reach is honest only while its mould is unobtainable.
            if _given:
                check('if (inv_total(inv, %s) > 0) {' % p['mould'] in sv,
                      '...and because %s is obtainable, the %s slot flips on holding it rather '
                      'than claiming you need one' % (p['mould'], p['key']), 'yes')


# ---------------------------------------------------------------- 6
group('6. the churn, and the three panels being the three inputs')
c = PANELS['churn_milk']['content']
ch = RS2['scripts/skill_cooking/scripts/churn/churn.rs2']
for iface, src in c['inputs'].items():
    pn = read(PANELS[iface]['dst'])
    n = len([1 for _, kv, _ in blocks(pn) if kv.get('option', '').startswith('Churn ')])
    made = [p for p in c['products'] if src in p['from']]
    check(n == len(made), '%s has %d buttons and %s makes %d things'
          % (iface, n, src, len(made)), n)
    check(src in OBJPACK, '%s is a packed obj' % src, 'yes')
for p in c['products']:
    check(p['obj'] in OBJPACK, '%s is a packed obj' % p['obj'], 'yes')
    lv = set()
    for src in p['from']:
        m = re.search(r'@churn_go\(%s, %s, (\d+), (\d+)\);' % (src, p['obj']), ch)
        check(m is not None, '%s from %s is wired' % (p['key'], src), 'yes')
        if m:
            lv.add(int(m.group(1)))
            check(int(m.group(2)) == p['from'][src],
                  'and pays the experience its wiki page gives', m.group(2))
    check(len(lv) == 1 and lv.pop() == p['level'],
          "%s asks the same Cooking level whatever it was churned from" % p['key'], p['level'])
cheese = [p for p in c['products'] if p['key'] == 'cheese'][0]
check(cheese['from']['bucket_milk'] > cheese['from']['pot_of_cream'] > cheese['from']['pot_of_butter'],
      'cheese pays less the further along the chain you start', list(cheese['from'].values()))
# EVERY ROUTE FROM MILK TO CHEESE PAYS THE SAME 640. An earlier version of this check asserted the
# long way round pays MORE - it does not, it pays exactly the same, and the wiki's own figures say
# so. That is a much better check than the one it replaced, because it ties all six numbers
# together: get any one of them wrong and one of the three routes stops adding up.
byk = {p['key']: p for p in c['products']}
routes = {
    'milk -> cheese': [byk['cheese']['from']['bucket_milk']],
    'milk -> butter -> cheese': [byk['butter']['from']['bucket_milk'],
                                 byk['cheese']['from']['pot_of_butter']],
    'milk -> cream -> cheese': [byk['cream']['from']['bucket_milk'],
                                byk['cheese']['from']['pot_of_cream']],
    'milk -> cream -> butter -> cheese': [byk['cream']['from']['bucket_milk'],
                                          byk['butter']['from']['pot_of_cream'],
                                          byk['cheese']['from']['pot_of_butter']],
}
for name, legs in routes.items():
    check(sum(legs) == byk['cheese']['from']['bucket_milk'],
          'every route from milk to cheese pays the same, and %s does' % name,
          '%s = %d' % (' + '.join(str(x) for x in legs), sum(legs)))


# ---------------------------------------------------------------- 7
group('7. every named component is answered, and every trigger names a real one')
for iface, p in PANELS.items():
    pn = read(p['dst'])
    names = set(n for n, _, _ in blocks(pn))
    used = set(re.findall(r'%s:(\w+)' % iface, ALLRS2))
    check(used <= names, 'every %s:<component> a script names exists' % iface,
          sorted(used - names) or 'all %d' % len(used))
    opts = set(n for n, kv, _ in blocks(pn) if kv.get('option') or kv.get('option1'))
    trig = set(re.findall(r'\[(?:if_button|inv_button\d),%s:(\w+)\]' % iface, ALLRS2))
    named = set(n for n in opts if not n.startswith('com_'))
    # A clickable inside a layer the server only ever hides cannot be clicked, so it cannot need a
    # trigger. That is the three unwired silver products: their layer is if_sethide'd true and
    # never false. Anything else without a trigger is a button that does nothing, which is the
    # exact fault this round exists to fix.
    parent = {n: kv['layer'] for n, kv, _ in blocks(pn) if kv.get('layer')}
    unreachable = set()
    for n in named - trig:
        lay = parent.get(n)
        if lay and ('if_sethide(%s:%s, true)' % (iface, lay)) in ALLRS2 \
                and ('if_sethide(%s:%s, false)' % (iface, lay)) not in ALLRS2:
            unreachable.add(n)
    check(named - trig - unreachable == set(),
          'every named clickable in %s that can be shown has a trigger' % iface,
          sorted(named - trig - unreachable) or 'all %d' % len(named - unreachable))
    if unreachable:
        check(True, 'and %d in %s are inside a layer that is never shown' % (len(unreachable), iface),
              sorted(unreachable))


# ---------------------------------------------------------------- 8
group('8. the pack, and each panel keeping the id it came with')
pack = [l.strip() for l in open('pack/interface.pack') if l.strip()]
order = [l.strip() for l in open('pack/interface.order') if l.strip()]
ids = [l.split('=', 1)[0] for l in pack]
nms = [l.split('=', 1)[1] for l in pack]
check(len(ids) == len(set(ids)), 'no duplicate interface id', len(ids))
check(len(nms) == len(set(nms)), 'no duplicate interface name', len(nms))
check(set(order) == set(ids), 'interface.order and interface.pack agree exactly', len(order))
byname = dict(zip(nms, ids))
for iface, p in PANELS.items():
    old = re.match(r'.*/(inter_(\d+))\.if$', p['src'])
    check(iface in byname, '%s has an id' % iface, byname.get(iface))
    check(old.group(1) not in byname, 'and %s no longer does' % old.group(1), 'gone')
    pn = read(p['dst'])
    names = [n for n, _, _ in blocks(pn)]
    got = [n for n in nms if n.startswith(iface + ':')]
    check(len(got) == len(names), 'every %s component is packed' % iface, len(got))
    check(not os.path.exists(p['src']), 'the cache file is gone, not duplicated', 'yes')


# ---------------------------------------------------------------- 9
group('9. the generators still produce exactly what is checked in')
before = {}
for p in PANELS.values():
    before[p['dst']] = read(p['dst'])
for f in ('scripts/skill_smithing/scripts/smelting/smelt_window.rs2',
          'scripts/skill_crafting/scripts/leather/tan_window.rs2',
          'scripts/skill_crafting/scripts/jewellery/silver_casting.rs2',
          'scripts/skill_cooking/scripts/churn/churn.rs2'):
    before[f] = read(f)
before['pack/interface.pack'] = read('pack/interface.pack')
for tool in ('tools/genadopt.py', 'tools/genwindows.py'):
    r = subprocess.run([sys.executable, tool], capture_output=True, text=True)
    check(r.returncode == 0, '%s runs clean' % tool, r.returncode)
same = [f for f in before if read(f) == before[f]]
check(len(same) == len(before), 're-running them changes nothing: byte-identical',
      '%d files' % len(same))


print()
if FAILED:
    print('%d FAILED' % len(FAILED))
    for f in FAILED:
        print('  ' + f)
    sys.exit(1)
print('ALL PASS')
