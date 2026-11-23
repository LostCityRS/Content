#!/usr/bin/env python3
"""
Every quest's reward scroll against what the quest actually pays.

WHY THIS EXISTS. A reward line is a string a human typed; stat_advance takes TENTHS of a point.
Nothing ties the two together, so a quest written with the scroll's own number pays a tenth of what
it promises, and one written with the tenths figure in the scroll promises a tenth of what it pays.
Both build, both complete, both show the right scroll. Three were found by hand:

  Priest in Peril    stat_advance(prayer, 1406)    paid 140.6 against a 1,406 scroll
  Desert Treasure    stat_advance(magic, 2000000)  paid 200,000 against a 20,000 scroll
  Watchtower         stat_advance(magic, 153000)   paid 15,300 against a 15,250 scroll

The first was reported by a player as the XP rate not working, which is exactly what it looks like:
a tenth of the reward, times the 10x rate, is the reward. The multiplier was never involved.

AND THE SCROLL HAS TO ACTUALLY SHOW THE LINES. ~send_quest_complete switches on the quest and three
quests had a case of their own pointing at a malformed interface, where $rewardtext was never
written at all - the reward list was a dead argument no player ever saw. Group 2 holds that shut.

Run: python tools/questxp_battery.py
"""
import os, re, glob, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(C)

ok = bad = 0
def check(cond, what):
    global ok, bad
    if cond:
        ok += 1
        print('  ok   %s' % what)
    else:
        bad += 1
        print('  FAIL %s' % what)

SKILLS = set('attack defence strength hitpoints ranged prayer magic cooking woodcutting fletching '
             'fishing firemaking crafting smithing mining herblore agility thieving slayer farming '
             'runecraft construction hunter'.split())

def read(p):
    return open(p, encoding='utf-8', errors='replace').read()

RS2 = [f for f in glob.glob('scripts/**/*.rs2', recursive=True) if '/_unpack/' not in f]
SRC = {f: read(f) for f in RS2}

# ^name = N, with or without a trailing comment. Requiring end-of-line here is a mistake I made
# once already: it reads every constant that carries a note as undefined, and then every quest
# whose reward is a named constant looks like it pays nothing.
CONST = {}
for f in glob.glob('scripts/**/*.constant', recursive=True):
    for m in re.finditer(r'^\^(\w+)\s*=\s*(-?\d+)\b', read(f), re.M):
        CONST[m.group(1)] = int(m.group(2))

def value(tok):
    tok = tok.strip()
    if tok.isdigit():
        return int(tok)
    return CONST.get(tok[1:]) if tok.startswith('^') else None

# THE SCROLL ROUNDS, in two places, and both are correct as written: the reward is a half point and
# the scroll cannot show it. Listed with the exact grant so the rounding is pinned and a change to
# either side still has to come through here.
HALF_POINTS = {
    ('quest_horror.rs2', 'strength'): 46625,
    ('quest_horror.rs2', 'ranged'): 46625,
    ('quest_horror.rs2', 'magic'): 46625,
    ('quest_rd.rs2', 'prayer'): 10005,
    ('quest_rd.rs2', 'herblore'): 10005,
    ('quest_rd.rs2', 'agility'): 10005,
}

print('1. every advertised XP number is ten times itself in tenths, somewhere the quest can reach')
seen = 0
# TWO CALL SHAPES, and the second one cost nine reward lists their check. Recipe for Disaster is a
# single quest-list entry with ten sub-quests, so it CANNOT call ~send_quest_complete - that proc's
# last act is to paint the entry green and print "Quest complete!", which the first sub-quest
# finished would do for the whole quest - and it has its own ~hundred_subquest_scroll instead.
# Reading only the standard call left all nine of its reward lists unexamined, and every one of
# them was paying a tenth of what it printed: stat_advance(cooking, 1000) under a scroll promising
# 1,000 Cooking XP (#70, reported on the goblin generals, true of all nine).
#
# So the shapes are listed rather than assumed. A quest that needs a third one has to add it here,
# which is the point: a scroll this sweep cannot read is a reward nobody is checking.
SCROLLS = ('send_quest_complete', 'hundred_subquest_scroll')
for f in sorted(RS2):
    if not any('~%s' % _s in SRC[f] for _s in SCROLLS):
        continue
    base = os.path.basename(f)
    for call in re.finditer(r'~(?:%s)\((.*?)\);' % '|'.join(SCROLLS), SRC[f], re.S):
        args = call.group(1)
        txts = re.findall(r'"((?:[^"\\]|\\.)*)"', args)
        if not txts:
            continue
        qlist = re.search(r'questlist:(\w+)', args)
        qlist = qlist.group(1) if qlist else None
        # WHERE THE GRANT MAY LIVE. Not the completion block, and not even the quest's own folder:
        # Watchtower pays from [oploc1,watchleverup] and Sea Slug pays from caroline.rs2 under
        # areas/area_ardougne_east. Both of those read as "this quest grants nothing" to a sweep
        # scoped any tighter than this, which is how I first mis-scored them.
        qdir = f.split('/scripts/')[0]
        scope = set(glob.glob(qdir + '/scripts/*.rs2')) | \
                ({g for g in RS2 if 'questlist:%s' % qlist in SRC[g]} if qlist else set())
        pool = ''.join(SRC[g] for g in sorted(scope))
        for line in re.finditer(r'([\d,]+)\s*([A-Za-z]+)\s*(?:XP|xp|Xp|experience)', txts[-1]):
            skill = line.group(2).lower()
            if skill not in SKILLS:
                continue
            seen += 1
            advertised = int(line.group(1).replace(',', ''))
            grants = sorted({v for m in re.finditer(r'stat_advance\(%s,\s*([^)]+)\)' % skill, pool)
                             for v in [value(m.group(1))] if v is not None})
            want = HALF_POINTS.get((base, skill), advertised * 10)
            why = ' (a half point, rounded down on the scroll)' if (base, skill) in HALF_POINTS else ''
            check(want in grants,
                  '%s: %s advertises %s and pays %s%s' % (base, skill, line.group(1), want, why)
                  if want in grants else
                  '%s: %s advertises %s, so expected stat_advance %s, found %s%s'
                  % (base, skill, line.group(1), want, grants or 'nothing', why))
check(seen >= 150, 'and there were %d reward lines to check' % seen)

print('')
print('2. the scroll a quest is sent to actually writes the reward lines it was handed')
Q = read('scripts/general/scripts/quests.rs2')
body = Q.split('[proc,send_quest_complete]', 1)[1].split('\n[', 1)[0]
# ONLY THE FIRST switch, and only as far as its own default. The proc has a second
# switch_component further down for the "Congratulations!" line, and `case default` is INDENTED -
# splitting on a line-anchored '\ncase default' runs straight past the first switch into the
# second and reads troll_love as a bespoke scroll case.
switch = re.split(r'\n\s*case default', body.split('switch_component ($component) {', 1)[1])[0]
bespoke = sorted(set(re.findall(r'case ((?:questlist:\w+(?:,\s*)?)+)\s*:', switch)))
named = sorted({n for group in bespoke for n in re.findall(r'questlist:(\w+)', group)})

# THE ONE THAT IS STILL LIKE THIS, and deliberately so. questscroll_itgronigen is 1689 with
# "children" at 1690/1692/1695/1696 - non-contiguous, the same shape as the interfaces Gertrude's
# Cat, Sea Slug and Watchtower were taken off - and its case opens the interface without writing
# anything into it, so the Observatory's reward list is a dead argument too. It is left alone
# because giving it the default branch changes how that quest's scroll LOOKS, which is a decision
# about the game and not a bug fix. Listed here so it cannot be joined quietly.
KNOWN_BESPOKE = ['itgronigen']
check(named == KNOWN_BESPOKE,
      'only %s still has a scroll case of its own, got %s' % (KNOWN_BESPOKE, named))

# and the default branch, which everything else now takes, writes all five reward slots
for com in range(10, 15):
    check('if_settext(inter_238:com_%d, split_get(0, %d));' % (com, com - 10) in body,
          'the default branch writes reward slot com_%d' % com)
check('split_init($rewards, 200, 5, q8_full);' in body,
      'and splits the reward text into those five')

print('')
print('ALL PASS' if not bad else '%d FAILED' % bad)
sys.exit(1 if bad else 0)
