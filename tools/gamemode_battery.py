"""Battery for the XP rate modes: realism, 5x and 10x.

WHAT IS ACTUALLY AT RISK HERE, and it is not the arithmetic. It is that the multiplier sits in ONE
place and that the choice cannot be remade. There are 288 stat_advance call sites across 122
content files and no wrapper they pass through, so the rate lives in Player.addXp - which means
half of what this checks is in the ENGINE repo, and a content battery can only read its source.
That is exactly the half most likely to be left behind, since it is a separate checkout.

The other half is the lock. A mode that can be changed later is a button that says "give me ten
times the experience", so the checks about ~xprate_choose refusing to ask are the ones that matter
most, and they are written from both sides: the early returns are there, and the interface opens
after them.

    python3 tools/gamemode_battery.py [path/to/Engine-TS]
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(C), 'engine')

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')
def readat(root, p):
    f = os.path.join(root, p)
    return open(f, newline='').read().replace('\r\n', '\n') if os.path.exists(f) else None

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt): return '\n'.join(l.split('//')[0] for l in txt.split('\n'))
def block(txt, n):
    return txt.split('[' + n + ']', 1)[1].split('\n[', 1)[0] if '[' + n + ']' in txt else ''
def varpblock(txt, n):
    """A .varp block ends at the first BLANK LINE, not at the next [name]. block() would run on
    through the comment that introduces the next block - which is how adding [xp_locked] made the
    'xp_rate is not transmitted' check go red over a comment about xp_locked."""
    if '[' + n + ']' not in txt:
        return ''
    out = []
    for l in txt.split('[' + n + ']', 1)[1].split('\n')[1:]:
        if not l.strip() or l.startswith('['):
            break
        out.append(l)
    return '\n'.join(out)

CONST = read('scripts/gamemodes/configs/gamemode.constant')
VARP = read('scripts/gamemodes/configs/gamemode.varp')
RS2 = read('scripts/gamemodes/scripts/xprate.rs2')
IF = read('scripts/gamemodes/interfaces/xprate_choose.if')
GEN = read('tools/genxpratechooser.py')
GUIDE = read('scripts/tutorial/scripts/guides/runescape_guide.rs2')
VARPPACK = read('pack/varp.pack')
IPACK = read('pack/interface.pack')
IORDER = read('pack/interface.order')
QUESTC = read('scripts/general/configs/quest.constant')

def const(txt, n):
    m = re.search(r'(?m)^\^' + n + r' = (\d+)\s*(?://.*)?$', txt)
    return int(m.group(1)) if m else None

def ifcoms(txt):
    out = {}
    for chunk in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', chunk)
        if m:
            out[m.group(1)] = dict(re.findall(r'(?m)^(\w+)=(.*)$', chunk))
    return out

IFC = ifcoms(IF)

# ============================================================================ 1
print('1. the rates, and the one that means "never chosen"')
RATES = {n: const(CONST, 'xprate_' + n) for n in ('unset', 'realism', '5x', '10x')}
check(RATES['unset'] == 0,
      '"never chosen" is 0, which is what a varp reads as before anybody touches it (%s)'
      % RATES['unset'])
check(RATES['realism'] == 1,
      'realism is 1x - the authentic rate, so it is what the server already did (%s)'
      % RATES['realism'])
check(RATES['5x'] == 5 and RATES['10x'] == 10, '5x is 5 and 10x is 10 (%s, %s)'
      % (RATES['5x'], RATES['10x']))
check(RATES['unset'] not in (RATES['realism'], RATES['5x'], RATES['10x']),
      'no mode uses the "never chosen" value, or choosing it would not stick')
check(len({RATES['realism'], RATES['5x'], RATES['10x']}) == 3,
      'and no two modes share a rate, or one of them would be unreachable')
check(const(CONST, 'xprate_modes') == 3, 'there are three modes')

# ============================================================================ 2
print('2. where the rate lives')
xp = varpblock(VARP, 'xp_rate')
check('scope=perm' in xp, "the rate is perm - it is the account's for good")
check('transmit' not in xp,
      '...and NOT transmitted: the window is only ever open while the rate is unset, so the '
      'client has nothing to do with the number')
check('1176=xp_rate' in VARPPACK, '...and registered in pack/varp.pack, or the packer never sees it')
check('%xp_rate' in code(RS2), 'the scripts read it by name')

# ============================================================================ 3
print('3. the multiplier, which is in the engine because there is nowhere else for it')
PLAYER = readat(ENGINE, 'src/engine/entity/Player.ts')
if PLAYER is None:
    check(False, 'the engine repo is not beside content - pass its path as argv[1]')
else:
    check('const multi = allowMulti ? Environment.NODE_XPRATE * this.xpRate() : 1;' in PLAYER,
          "addXp multiplies by the player's own rate as well as the world's")
    check(len(re.findall(r'const multi = allowMulti', PLAYER)) == 1,
          '...in exactly one place, which is the whole point of putting it there')
    rate = PLAYER.split('xpRate(): number {', 1)[1].split('\n    }', 1)[0] if 'xpRate(): number {' in PLAYER else ''
    check(rate != '', 'Player.xpRate() exists')
    check("VarPlayerType.getId('xp_rate')" in rate,
          '...and finds the varp by NAME, so content owns which varp it is')
    check('Player.xpRateVarp === -2' in rate and 'private static xpRateVarp: number = -2;' in PLAYER,
          '...looked up lazily behind a -2 sentinel, because the configs are not loaded when the '
          'class is')
    check('if (Player.xpRateVarp < 0) {\n            return 1;' in rate,
          '...and a MISSING varp reads as 1x, not as zero experience for everybody')
    check('if (!rate || rate < 1) {\n            return 1;' in rate,
          '...and so does 0, which is every character that existed before this - they are untouched')
    check('Math.min(rate, 100)' in rate,
          '...with an upper rail, because a perm varp written wrong would otherwise be unbounded')
    # the one caller that must NOT be multiplied
    CHEAT = readat(ENGINE, 'src/network/game/client/handler/ClientCheatHandler.ts')
    check(CHEAT is not None and 'player.addXp(stat, getExpByLevel(parseInt(args[1])), false);' in CHEAT,
          'setting a level still passes allowMulti=false, so ::setlevel 50 is level 50 and not 500')
    check('allowMulti: boolean = true' in PLAYER,
          '...and everything else gets the multiplier by default')

# AND NOTHING IN THE CONTENT DOES IT A SECOND TIME. The strong version of this: %xp_rate appears
# in exactly one place in the whole content tree - the file that owns it - so no skill can be
# quietly multiplying on top of the engine. Two earlier drafts of this check were wrong: one
# flagged every multiply() inside a stat_advance (arrows.rs2 multiplies a COUNT by an xp value),
# and one flagged this file's own proc.
users = []
for dp, dn, fn in os.walk(os.path.join(C, 'scripts')):
    for f in fn:
        if not f.endswith(('.rs2', '.constant', '.varp')):
            continue
        full = os.path.join(dp, f)
        rel = full[len(C) + 1:].replace(os.sep, '/')
        if rel.startswith('scripts/gamemodes/'):
            continue
        if '%xp_rate' in code(open(full, newline='', errors='replace').read()):
            users.append(rel)
check(not users,
      'and %%xp_rate is read nowhere else in the content tree, so no skill multiplies on top of '
      'the engine: %s' % (users or 'only scripts/gamemodes/'))

# ============================================================================ 4
print('4. the lock, which is the only thing keeping this a choice')
ch = code(block(RS2, 'proc,xprate_choose'))
check('if (%xp_rate ! ^xprate_unset) {' in ch and 'return;' in ch,
      'a rate already chosen is not asked for again')
check('if (%tutorial >= ^tutorial_complete) {' in ch,
      '...and a finished tutorial is never asked at all, so a maxed account cannot walk back to '
      'the island and pick 10x')
check(const(QUESTC, 'tutorial_complete') is not None,
      '...against the tutorial\'s own constant (%s)' % const(QUESTC, 'tutorial_complete'))
check(0 <= ch.find('%tutorial >= ^tutorial_complete') < ch.find('if_openmain'),
      '...and BOTH of those come before the window opens, or the lock is decoration')
check('if_openmain(xprate_choose);' in ch, 'the chooser opens as a main modal')
for i in range(3):
    check('if_addresumebutton(xprate_choose:pick%d);' % i in ch,
          '...and box %d is a resume button, or clicking it does nothing' % i)
check('p_pausebutton;' in ch and 'switch_component (last_com)' in ch,
      '...and p_pausebutton waits for the click inside the npc script')
picks = re.findall(r'case xprate_choose:pick(\d) : ~xprate_set\(\^xprate_(\w+)\);', ch)
check([p[0] for p in picks] == ['0', '1', '2'],
      'all three boxes are handled: %s' % [p[0] for p in picks])
check(sorted(const(CONST, 'xprate_' + p[1]) for p in picks) == [1, 5, 10],
      '...and between them they set the three rates: %s'
      % sorted(const(CONST, 'xprate_' + p[1]) for p in picks))
st = code(block(RS2, 'proc,xprate_set'))
check('%xp_rate = $rate;' in st, 'choosing writes the rate')
check('cannot be changed later' in block(RS2, 'proc,xprate_set'),
      '...and says so, because a permanent choice made silently is a complaint later')

# ============================================================================ 5
print('5. asked before any experience can be earned')
g = code(GUIDE)
check('~xprate_choose;' in g, 'the RuneScape Guide asks')
check(0 <= g.find('~xprate_choose;') < g.find('switch_int(%tutorial)'),
      '...before the switch on %tutorial, so the welcome, the come-back label AND the '
      'skip-the-tutorial branch are all covered by one call')
check(g.count('~xprate_choose;') == 1,
      '...once, not once per branch')
check('newbie_basics_instructor' in GUIDE,
      'and he is the basics instructor, who stands in the first room')
check('stat_advance' not in code(GUIDE),
      '...and his own script awards no experience, so the asking happens before any is earned')
TUTC = read('scripts/tutorial/configs/tutorial.constant')
_last_basics = const(TUTC, 'newbie_basics_instructor_interacted_with_door')
_first_skill = const(TUTC, 'newbie_survival_instructor_cut_tree')
check(_last_basics is not None and _first_skill is not None and _last_basics < _first_skill,
      '...and every step of his comes before the first skilling step, by the tutorial\'s own '
      'progress numbers (%s < %s)' % (_last_basics, _first_skill))

# ============================================================================ 6
print('6. the window')
boxes = [n for n in IFC if re.fullmatch(r'pick\d', n)]
check(len(boxes) == 3, 'three boxes (%d)' % len(boxes))
for n in sorted(boxes):
    b = IFC[n]
    check(b.get('type') == 'rect' and b.get('buttontype') == 'normal',
          '%s is a normal button, not a select one' % n)
    check(b.get('option', '').startswith('Choose'), '...with a Choose option')
    check(b.get('overcolour'), '...and a hover colour, which a rect honours')
# THE TRAP THIS AVOIDS: a buttontype=select rect over the whole box takes the click and shows its
# own option, so it would swallow the one p_pausebutton is waiting for and suspend the script
# forever. The first draft did exactly that.
check('buttontype=select' not in IF,
      'nothing in the window is a select button - one covering a box would swallow the click '
      'p_pausebutton waits for')
check('pushvar,xp_rate' not in IF,
      '...and nothing highlights a chosen mode, because the window never opens with one chosen')
check(IFC.get('close', {}).get('buttontype') == 'close',
      'there IS a close button: closing leaves the rate at 0, which reads as 1x, and the guide '
      'asks again - a mandatory window with no way out can strand a player')
names = ['xprate_choose'] + ['xprate_choose:%s' % n for n in re.findall(r'(?m)^\[(\w+)\]$', IF)]
packed = dict(l.split('=', 1)[::-1] for l in IPACK.split('\n') if l)
missing = [n for n in names if n not in packed]
check(not missing, 'every component is in pack/interface.pack (%s)' % (missing[:3] or 'all %d' % len(names)))
order = {l.strip() for l in IORDER.split('\n') if l.strip()}
check(all(packed[n] in order for n in names if n in packed),
      '...and in pack/interface.order - an id in one and not the other packs type -1 and the '
      'client throws on load')
for i, label in enumerate(('Realism', '5x', '10x')):
    check(IFC.get('name%d' % i, {}).get('text') == label,
          'box %d is labelled %s' % (i, label))
check('rate0' in IFC and 'rate1' not in IFC and 'rate2' not in IFC,
      'only the Realism box carries a separate rate line - on the others the name already IS the '
      'multiplier, and a box saying "5x" over "5x" says one thing twice')
check(IFC.get('rate0', {}).get('text') == '%dx' % RATES['realism'],
      "...and it reads the constant's value (%s)" % IFC.get('rate0', {}).get('text'))
check('two modes share a rate' in GEN and 'never chosen' in GEN,
      'the generator refuses to emit two modes at one rate, or a mode at the unset value')
# the drop-rate line: empty in the .if and written from the constants on every open, so a change to
# a boost reaches the chooser and the client (which wipes server-set text) is handed it every show
for i, mode in enumerate(('realism', '5x', '10x')):
    check(IFC.get('drops%d' % i, {}).get('text', None) == '',
          'box %d has a drop-rate line, empty in the .if (the script fills it)' % i)
    check('if_settext(xprate_choose:drops%d, ~droprate_boost_line(^droprate_boost_%s));' % (i, mode) in ch,
          '...filled from ^droprate_boost_%s' % mode)
check(0 <= ch.find('if_openmain(xprate_choose);') < ch.find('if_settext(xprate_choose:drops0')
      < ch.find('p_pausebutton;'),
      '...after the window opens and before the script waits on it')
check('Every rate exactly as' not in IF,
      'the Realism blurb no longer says EVERY rate is Old School\'s - its drop rates are boosted')

# ============================================================================ 7
print('7. the test hook')
dbg = code(block(RS2, 'debugproc,xprate'))
check('queue(xprate_debug_set, 0, $rate);' in dbg,
      'the debugproc QUEUES its write: ClientCheatHandler runs a debugproc with '
      'executeScript(script, false), so it has no protected access - the same rule that crashed '
      'the Barrows chest out of its [if_close]')
check('%xp_rate' not in dbg,
      '...and does not write the varp inline, which is a build error rather than a surprise')
q = code(block(RS2, 'queue,xprate_debug_set'))
check('%xp_rate = $rate;' in q, '...and the queue is what writes it')

# ============================================================================ 8
print('8. the lock bits are the engine\'s own stat order, read from the engine')
# THE ANCHOR. Everything else about the lock is this round's own work checking this round's own
# work; the bit layout is the one thing with an outside source, and it is the one thing that
# silently ruins the feature if it drifts - a wrong bit locks the wrong skill and nothing errors.
# ParamConfig.ts is the list the PACKER resolves a `stat` symbol through, so it is what decides
# what number the engine's addXp is handed.
PARAMCFG = readat(ENGINE, 'tools/pack/config/ParamConfig.ts')
XPLOCK = read('scripts/gamemodes/scripts/xplock.rs2')
GENLOCK = read('tools/genxplock.py')
STATSIF = read('scripts/interfaces/stats.if')
# How many stats this build has. Read from the engine when it is beside us, and counted from the
# ^xplock_ constants when it is not, so section 10 below stops being a number that has to be edited
# by hand every time a skill is added - it was still 22 the day Hunter became 23.
NSTATS = len([k for k, _ in re.findall(r'(?m)^\^xplock_([a-z]+) = (\d+)$', CONST) if k != 'skills'])
if PARAMCFG is None:
    check(False, 'the engine repo is not beside content - pass its path as argv[1]')
else:
    m = re.search(r'const stats: \(string \| null\)\[\] = \[(.*?)\];', PARAMCFG, re.S)
    check(m is not None, 'ParamConfig.ts still declares the stat list the packer resolves through')
    engine_stats = re.findall(r"'([a-z]+)'", m.group(1)) if m else []
    mine = dict((k, int(v)) for k, v in re.findall(r'(?m)^\^xplock_([a-z]+) = (\d+)$', CONST)
                if k != 'skills')
    check(len(engine_stats) == len(mine),
          'there is one ^xplock_ constant per stat: %d constants, %d stats'
          % (len(mine), len(engine_stats)))
    wrong = [(k, v, engine_stats.index(k) if k in engine_stats else None)
             for k, v in sorted(mine.items()) if engine_stats[v:v + 1] != [k]]
    check(not wrong, 'every ^xplock_ bit is that skill\'s own index in the engine\'s list: %s'
          % (wrong[:3] or 'all %d agree' % len(mine)))
    check(const(CONST, 'xplock_skills') == len(engine_stats),
          '^xplock_skills is the number of stats the engine has')
    # and the generator's transcription of that list is the same list
    g = re.search(r'STAT_ORDER = \[(.*?)\]', GENLOCK, re.S)
    gen_stats = re.findall(r"'([a-z]+)'", g.group(1)) if g else []
    check(gen_stats == engine_stats,
          'tools/genxplock.py\'s STAT_ORDER is the engine\'s list, in order')
    NSTATS = len(engine_stats)

# ============================================================================ 9
print('9. the engine refuses a locked skill\'s experience, and only that')
lk = varpblock(VARP, 'xp_locked')
check('scope=perm' in lk, "the lock is perm - it is the account's until the player lifts it")
check('transmit' not in lk, '...and not transmitted: the client never reads it')
if PLAYER is None:
    check(False, 'the engine repo is not beside content')
else:
    guard = 'if (allowMulti && this.xpLocked(stat)) {'
    check(guard in PLAYER, 'addXp asks whether the skill is locked')
    check(PLAYER.index(guard) < PLAYER.index('const multi = allowMulti'),
          '...before it works out the multiplier, so a locked skill costs nothing to refuse')
    check(PLAYER.index('if (xp == 0) {') < PLAYER.index(guard),
          '...and after the zero-xp early out, so a no-op cannot print a warning')
    lock = PLAYER.split('xpLocked(stat: number): boolean {', 1)[1].split('\n    }', 1)[0] \
        if 'xpLocked(stat: number): boolean {' in PLAYER else ''
    check(lock != '', 'Player.xpLocked() exists')
    check("VarPlayerType.getId('xp_locked')" in lock,
          '...and finds the varp by NAME, so content owns which varp it is')
    check('Player.xpLockedVarp === -2' in lock and 'private static xpLockedVarp: number = -2;' in PLAYER,
          '...behind the same -2 sentinel xp_rate uses')
    check('Player.xpLockedVarp < 0' in lock and 'return false;' in lock,
          '...and a MISSING varp locks nothing, rather than locking everything')
    check('>>> stat) & 1' in lock,
          '...testing bit `stat` itself, so the engine keeps no table of its own')
    check('stat >= PLAYER_STAT_COUNT' in lock,
          '...with the stat id railed, because a bitmask shifted past 31 wraps')
    # ::setlevel must still work on a locked skill - it is not the player earning anything
    check('player.addXp(stat, getExpByLevel(parseInt(args[1])), false);' in (CHEAT or ''),
          '::setlevel still passes allowMulti=false, so it works on a locked skill')
    warn = PLAYER.split('private warnXpLocked(stat: number): void {', 1)[1].split('\n    }', 1)[0] \
        if 'private warnXpLocked(stat: number): void {' in PLAYER else ''
    check(warn != '', 'it says so rather than refusing in silence')
    check('World.currentTick - last < 100' in warn,
          '...at most once a minute a skill, so training a locked skill is not a wall of text')
    check('private xpLockWarned: Int32Array = new Int32Array(PLAYER_STAT_COUNT);' in PLAYER,
          '...throttled by a plain field sized to the stat count, not by a varp')

# ============================================================================ 10
print('10. the stats tab: %d second options that cannot become the left click' % NSTATS)
IFS = []
for chunk in re.split(r'(?m)^(?=\[)', STATSIF):
    mm = re.match(r'\[(\w+)\]', chunk)
    if mm:
        IFS.append((mm.group(1), dict(re.findall(r'(?m)^(\w+)=(.*)$', chunk))))
pos = {n: i for i, (n, _) in enumerate(IFS)}
byn = dict(IFS)
locks = [n for n, _ in IFS if n.startswith('xplock_')]
guides = [(n, d) for n, d in IFS if d.get('buttontype') == 'normal' and 'overlayer' in d
          and not n.startswith('xplock_')]
check(len(locks) == len(guides) == NSTATS,
      'one lock button per skill box: %d locks, %d boxes, %d stats'
      % (len(locks), len(guides), NSTATS))
bad = [n for n in locks if 'option' not in byn[n] or byn[n].get('buttontype') != 'normal']
check(not bad, 'every one is a normal button with an option: %s' % (bad or 'all %d' % NSTATS))
# THE CHECK THIS ROUND EXISTS FOR. Client.java: the left-click action is menuOption[menuSize - 1],
# the LAST option appended, and components are walked in child order - so a lock button after its
# guide button would make LOCKING the left click on a skill box.
late = []
for n in locks:
    same = [g for g, d in guides if d['overlayer'] == byn[n]['overlayer']]
    if not same or pos[n] > pos[same[0]]:
        late.append(n)
check(not late, 'each one is emitted BEFORE its guide button, so left click still opens the '
                'guide: %s' % (late or 'all %d' % NSTATS))
def guide_for(n):
    same = [g for g, d in guides if d['overlayer'] == byn[n]['overlayer']]
    return same[0] if same else None
geom = [n for n in locks
        if guide_for(n) is None
        or any(byn[n][k] != byn[guide_for(n)][k] for k in ('x', 'y', 'width', 'height'))]
check(not geom, 'each one covers exactly its own skill box: %s' % (geom or 'all %d' % NSTATS))
names = [byn[n]['option'] for n in locks]
check(len(set(names)) == len(names), 'no two say the same thing: %d distinct' % len(set(names)))
packed = dict(l.split('=', 1)[::-1] for l in IPACK.split('\n') if '=' in l)
missing = [n for n in locks if 'stats:' + n not in packed]
check(not missing, 'every one has an id in interface.pack: %s' % (missing or 'all %d' % NSTATS))
ordered = {l.strip() for l in IORDER.split('\n') if l.strip()}
missing = [n for n in locks if packed.get('stats:' + n) not in ordered]
check(not missing, '...and is in interface.order: %s' % (missing or 'all %d' % NSTATS))
driven = sorted(set(re.findall(r'\[if_button,stats:(\w+)\]', XPLOCK)))
check(driven == sorted(locks), 'every button has a trigger and every trigger has a button')
# the label each trigger rewrites has to belong to that skill's OWN hover panel
crossed = []
for n in locks:
    body = XPLOCK.split('[if_button,stats:%s]' % n, 1)[1].split('\n[', 1)[0]
    ov = byn[n]['overlayer']
    for lab in set(re.findall(r'if_settext\(stats:(\w+),', body)):
        if byn.get(lab, {}).get('layer') != ov:
            crossed.append((n, lab))
check(not crossed, 'and rewrites a label inside its own skill\'s hover panel: %s'
      % (crossed[:3] or 'all %d' % NSTATS))
# THE CHECK THE BUILD EARNED. An [if_button] is handed active_player and NOT p_active_player
# (claude/rs2-player-pointer-contexts.md). Without p_finduid these bodies fail TWICE: ~p_choice2
# reaches p_pausebutton, which is a build error, and writing a protect=yes varp from an
# unprotected script compiles clean and drops the connection when it runs. Nothing offline caught
# it - the server build did, on all 22 at once.
unprot = []
for n in locks:
    body = XPLOCK.split('[if_button,stats:%s]' % n, 1)[1].split('\n[', 1)[0]
    lines = [l for l in code(body).split('\n') if l.strip()]
    if not lines or lines[0].strip() != 'if (p_finduid(uid) = true) {':
        unprot.append(n)
check(not unprot, 'and takes protected access FIRST, because an [if_button] is not handed it: %s'
      % (unprot[:3] or 'all %d' % NSTATS))
# THE CHECK THE SECOND DEPLOY EARNED. A type=text with no font= packs as fonts[255] and kills the
# CLIENT on load - "loaderror Unpacking interfaces 95" - with no server-side symptom at all.
# rs2check rule 20 holds this repo-wide now; this one is here because these 22 are the components
# that taught it.
IF_FONTS = {'p11_full', 'p12_full', 'b12_full', 'q8_full'}
nofont = [n for n in locks if byn[n].get('font') not in IF_FONTS]
check(not nofont, 'and names a font the packer knows, or the client dies unpacking interfaces: %s'
      % (nofont[:3] or 'all %d' % NSTATS))
outside = [n for n in locks
           if re.search(r'(?m)^%xp_locked = ', code(XPLOCK.split('[if_button,stats:%s]' % n, 1)[1]
                                                    .split('\n[', 1)[0]))]
check(not outside, '...with every %%xp_locked write inside that branch, not beside it: %s'
      % (outside[:3] or 'all %d' % NSTATS))
lkv = varpblock(VARP, 'xp_locked')
check('protect=no' not in lkv,
      '...so the varp stays protected rather than being opened up to get round it')

# ============================================================================ 11
print('11. a lock never waives a requirement')
# Corey's constraint, as a check rather than a claim. A lock can only become a loophole if
# something branches on it, so the strong version is that nothing outside the file that owns it
# can see it at all - the same shape as the %xp_rate check above.
readers, writers = [], []
for dp, dn, fn in os.walk(os.path.join(C, 'scripts')):
    for f in fn:
        if not f.endswith(('.rs2', '.constant', '.varp')):
            continue
        rel = os.path.join(dp, f)[len(C) + 1:].replace(os.sep, '/')
        if rel.startswith('scripts/gamemodes/'):
            continue
        txt = code(open(os.path.join(C, rel), newline='', errors='replace').read())
        if '%xp_locked' in txt:
            readers.append(rel)
        if re.search(r'\^xplock_', txt):
            writers.append(rel)
check(not readers, '%%xp_locked is read nowhere else in the content tree: %s'
      % (readers or 'only scripts/gamemodes/'))
check(not writers, 'and no ^xplock_ constant is used outside it either: %s'
      % (writers or 'only scripts/gamemodes/'))
check('stat(' not in code(XPLOCK), 'xplock.rs2 never reads a level, so it cannot gate on one')
check('~xplock_restore;' in code(read('scripts/login_logout/scripts/login.rs2')),
      'login re-marks the tab, because the client loads its text from the cache')
rest = code(block(XPLOCK, 'proc,xplock_restore'))
check('if (%xp_locked = 0) {' in rest,
      '...and sends nothing at all for an account with nothing locked')

# ============================================================================ 12
print('12. the generator still produces exactly what is checked in')
import subprocess as _sp
kept = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/interfaces/stats.if',
    'scripts/gamemodes/scripts/xplock.rs2',
    'scripts/gamemodes/configs/gamemode.constant',
    'scripts/gamemodes/configs/gamemode.varp',
    'pack/interface.pack',
    'pack/interface.order']}
r = _sp.run([sys.executable, os.path.join(C, 'tools/genxplock.py')], capture_output=True,
            text=True, cwd=C)
check(r.returncode == 0, 'tools/genxplock.py runs clean'
      + ('' if r.returncode == 0 else ': ' + (r.stderr or r.stdout)[-400:]))
moved = [f for f in kept if open(os.path.join(C, f), 'rb').read() != kept[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
# WHAT THIS ACTUALLY CARES ABOUT is that xp_locked was APPENDED and never inserted, because a
# varp id is part of what a save file means and inserting one moves every varp above it. The first
# version asserted it was the LAST line in varp.pack, which is a proxy that stops being true the
# moment any later round adds a varp - the boss kill counts took 1178 and up, and this check went
# red on correct code. It pins the id instead.
_vp = {n: int(i) for i, n in re.findall(r'^(\d+)=(\S+)$', VARPPACK, re.M)}
check(_vp.get('xp_locked') == 1177,
      'xp_locked is still varp 1177, the id it was appended at, so nothing has been inserted '
      'under it - a varp id is part of what a save file means. (Later rounds append ABOVE it; '
      'the boss kill counts took 1178 and up.): %s' % _vp.get('xp_locked'))
check(_vp.get('xp_rate') == 1176,
      '...and xp_rate is still 1176, the id before it, for the same reason: %s'
      % _vp.get('xp_rate'))
_vpl = [l for l in VARPPACK.split('\n') if l.strip()]
check(len(set(l.split('=', 1)[0] for l in _vpl)) == len(_vpl), 'no varp id is used twice')
check(len(_vp) == len(_vpl), '...and no varp NAME is used twice either')

# ============================================================ the drop-rate boost
print()
print("-- drop-rate boost: the monster's own table, never the rare drop table")
DROPRS = read('scripts/gamemodes/scripts/droprate.rs2')
DEATH = read('scripts/skill_combat/scripts/npc/npc_death.rs2')
CONST = read('scripts/gamemodes/configs/gamemode.constant')
DBROW = read('scripts/drop_tables/configs/npc_drops.dbrow')
DBTABLE = read('scripts/drop_tables/configs/npc_drops.dbtable')

def const(n):
    m = re.search(r'^\^%s\s*=\s*(-?\d+)\s*$' % n, CONST, re.M)
    return int(m.group(1)) if m else None

# the percentages, and which way round they go
r1, r5, r10 = const('droprate_boost_realism'), const('droprate_boost_5x'), const('droprate_boost_10x')
check((r1, r5, r10) == (25, 7, 0), 'realism +25%%, 5x +7%%, 10x nothing: %s' % [r1, r5, r10])
check('droprate_bonus_' not in CONST and not os.path.exists(os.path.join(C, 'scripts/gamemodes/configs/droprate.enum')),
      'the old rare-table roll counts and their gate are gone')

# the proc rolls the bonus list and nothing else
b = DROPRS.split('[proc,droprate_bonus]', 1)[1].split('\n[', 1)[0]
check('~ultrarare_getitem' not in code(DROPRS) and '~megararetable' not in code(DROPRS),
      'the boost never touches the shared rare table')
check('npc_findhero' in b and 'npc_drops:bonus' in b and b.index('npc_findhero') < b.index('npc_drops:bonus'),
      'it finds the hero - whose %xp_rate it is - before it reads the bonus list')
check('scale($percent, 100, $chance)' in b and 'random(^droprate_units)' in b,
      "each row at its own chance times the boost, in the generator's units")
check(const('droprate_units') == 10000000, '^droprate_units is BONUS_UNITS, ten million')
check('while (true)' not in code(b), 'the loop is bounded by the row count')
g = DROPRS.split('[proc,droprate_give]', 1)[1].split('\n[', 1)[0]
# A PET GOES THROUGH THE FUNNEL, which is a stronger statement than the two calls this used to ask
# for. ~pet_receive (npc/scripts/follower.rs2) is the one proc that hands any pet over: it refuses
# one the player owns anywhere, puts it in the pack or at Probita's if something is already
# following, and announces it - so the boost's pet keeps every rule a boss drop's does because it
# is the same code. ~pet_receive_later rather than ~pet_receive because this runs as the npc, and
# the varp the funnel writes is the killer's.
check('~pet_receive_later($obj, 0)' in g,
      "a pet is handed to ~pet_receive, queued on the killer because this runs as the npc")
check('~pet_owned' not in g and '~broadcast_pet' not in g,
      '...and does not keep a second copy of the funnel\'s rules beside it')
check(all(x in g for x in ('~trail_easycluedrop(1, $at)', '~trail_mediumcluedrop(1, $at)', '~trail_hardcluedrop(1, $at)')),
      "a clue goes through its tier's own proc, one clue at a time")
check('collection_log_item_index' in g and '~broadcast_drop($obj)' in g,
      'a collection log item is announced and logged, as the tables do their rares')
# TWO PROCS: the one the ROLL reads, which honours %droprate_override, and the one the DISPLAYS
# read, which is the account's mode and nothing else. The split is the whole point - an override
# must not appear on the pages that tell a player what their mode gives - so each is asserted for
# what only it is allowed to do. '[proc,droprate_boost_percent]' matches the first only: the
# closing bracket keeps it from catching _mode.
rolls = DROPRS.split('[proc,droprate_boost_percent]', 1)[1].split('\n[', 1)[0]
modes = DROPRS.split('[proc,droprate_boost_percent_mode]', 1)[1].split('\n[', 1)[0]
check('%droprate_override' in rolls and 'return(~droprate_boost_percent_mode)' in code(rolls),
      'the roll reads the override, and falls back to the mode when there is none')
check('%droprate_override' not in modes,
      '...and the mode knows nothing about it, so a display cannot leak one')
check('^droprate_boost_realism' in modes.split('return(')[-1],
      'realism is the DEFAULT branch, so ^xprate_unset (0) gets the boost too')
check('^xprate_10x' in modes and '^xprate_5x' in modes,
      'and it compares against the same rate constants the engine multiplies by')

# WHICH PROC EACH DISPLAY READS, which is the half no behavioural test can see: the two return
# the same number on every account without an override - that is every account but one - so a
# display reading the roll's looks correct everywhere except the single account anybody would
# ever check it with. Engine-TS tools/sim/droprateoverride.ts asserts this from its side too;
# it is cheap, and this is the repo the scripts live in.
for _path, _who in (('scripts/questtab/scripts/questtab.rs2', "the quest tab's stats page"),
                    ('scripts/drop_tables/scripts/npc_drops.rs2', "the drop table viewer's subtitle"),
                    ('scripts/gamemodes/scripts/gamemode_info.rs2', 'the game mode explanation')):
    _calls = [l for l in code(read(_path)).split('\n') if '~droprate_boost_percent' in l]
    check(bool(_calls) and all('~droprate_boost_percent_mode' in l for l in _calls),
          _who + " reads the mode's boost, never the roll's")

# the data: the bonus column, and nothing in it that the rare table owns
check('column=bonus,namedobj,int,int,int,int,LIST' in DBTABLE, 'npc_drops has its bonus column')
bon = re.findall(r'^data=bonus,(\w+),(\d+),(\d+),(\d+),(\d)$', DBROW, re.M)
check(len(bon) > 1000, '%d bonus rows across the tables' % len(bon))
check(all(0 < int(c) < 10000000 and int(lo) <= int(hi) for _, lo, hi, c, _k in bon),
      'every chance is under one, and every amount a range the right way round')
rows = {}
cur = None
for line in DBROW.split('\n'):
    m = re.match(r'^\[(\w+)\]$', line)
    if m:
        cur = rows.setdefault(m.group(1), {'drop': [], 'bonus': []})
    elif line.startswith('data=drop,') and cur is not None:
        cur['drop'].append(line.split(',')[1])
    elif line.startswith('data=bonus,') and cur is not None:
        cur['bonus'].append(line.split(',')[1])
check(all(set(r['bonus']) <= set(r['drop']) for r in rows.values()),
      'a bonus row is only ever for something that table already drops')
gd = rows.get('npc_drops_superior_greater_abyssal', {'drop': [], 'bonus': []})
check('dragon_med_helm' in gd['drop'] and 'dragon_med_helm' not in gd['bonus'] and 'rune_spear' not in gd['bonus'],
      "the greater abyssal demon's rare-table items are listed, and not boosted")
check('abyssal_whip' in gd['bonus'] and 'abyssal_head' in gd['bonus'],
      '...while its own whip and head are')
check(all(r['bonus'].count(o) <= r['drop'].count(o) for r in rows.values() for o in set(r['bonus'])),
      'and never more bonus rows for an item than drop rows')

# one hook, in the funnel, beside the two that are already there
check(DEATH.count('~droprate_bonus;') == 1, 'the hook is in [proc,npc_death] exactly once')
check('~boss_kill_record' in DEATH and
      DEATH.index('~boss_kill_record') < DEATH.index('~droprate_bonus'),
      'next to the other two hooks that use that funnel for the same reason')
SHARED = read('scripts/drop_tables/scripts/shared_droptables.rs2')
check('droprate' not in SHARED, 'shared_droptables.rs2 knows nothing about the boost')
check('%xp_rate' not in code(DEATH), 'the death funnel never reads %xp_rate itself')

# the generator still produces what is checked in
import subprocess as _sp2
r2 = _sp2.run([sys.executable, os.path.join(C, 'tools/gennpcdrops.py'), '--check'],
              capture_output=True, text=True, cwd=C)
# THE LAST 300 CHARACTERS WERE THE WRONG 300. --check prints every npc whose death script it could
# not read a literal drop out of, then the one line that matters - "out of date: <file>" - so the
# tail of its output was the middle of that list and the failure read as "%upass". The out-of-date
# lines are quoted instead, which is what somebody reading this has to act on.
_stale = [l for l in (r2.stderr or r2.stdout).split('\n') if l.startswith('out of date:')]
check(r2.returncode == 0 and 'wrote' not in r2.stdout.split('gennpcdrops:')[0],
      'tools/gennpcdrops.py --check: the drop data is what the death scripts say'
      + ('' if r2.returncode == 0
         else ': ' + '; '.join(_stale) if _stale else ': ' + (r2.stderr or r2.stdout)[-200:]))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
