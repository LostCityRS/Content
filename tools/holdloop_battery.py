#!/usr/bin/env python3
"""Every `while` loop that holds the player with p_delay, and whether that was on purpose.

WHY THIS EXISTS. p_delay does not yield. It sets player.delayed, and MoveClickHandler and its
fifteen siblings THROW AWAY a click made while that is set rather than deferring it. So a repeat
paced with p_delay cannot be stopped: the player clicks, the click is discarded, and the loop runs
to the bottom of their inventory.

That has now been reported by players twice - DeathPlateau-Bugs#39 at the chaos altar, "cant be
stopped until invo is empty", and DeathPlateau-Bugs#85 at the furnace, "you wont stop until out of
ores in inventory" - and found a third time by sweeping for it, in glassblowing, whose comment
said in as many words that p_delay "yields, so the player can walk away". Three places, one false
belief, written down as a feature each time. This is here so there is no fourth.

WHAT IT ASKS, AND WHAT IT DELIBERATELY DOES NOT. It flags one shape only: a `while` body with a
p_delay directly in it. That shape is always a lockout for the length of the loop, and the table
below records the ones where the lockout is the point.

It does NOT follow p_delay into procs the loop calls, and it does NOT look at repeats built from
p_oploc or a weak queue. Both were tried and both go red on correct code:

  - following calls flags skill_farming/farming_useitem.rs2's rake, skill_mining/mining.rs2 and
    skill_woodcutting/woodcut.rs2, which are the map_clock + p_oploc pattern the chaos altar fix
    was modelled ON - the reference implementations, reported as faults.
  - the weak-queue repeats in general_use/water_sources.rs2 and skill_prayer/ectofuntus.rs2 keep a
    p_delay(0) per pass ON PURPOSE, with a cadence of 2 chosen so that every other tick is
    undelayed and the player's click lands on it. water_sources.rs2 reasons the whole thing out in
    its own comment, MoveClickHandler included.

A check that goes red on correct code gets switched off, so this asks the narrow question. The
cost is honest and worth writing down: the furnace's own fault would NOT have been caught here,
because its hold lived in ~smelt_bar, a proc the loop called. tools/sim/smeltstop.ts and
tools/sim/batchstop.ts are what cover that, against the running engine.

    python3 tools/holdloop_battery.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
FAILED = []


def ok(msg, extra=''):
    print('  ok   %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))


def bad(msg, extra=''):
    print('  FAIL %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))
    FAILED.append(msg)


def check(cond, msg, extra=''):
    (ok if cond else bad)(msg, extra)


# ---------------------------------------------------------------------------------------------
# THE ONES WHERE HOLDING THE PLAYER IS THE POINT. Every entry needs a reason, because the only
# thing that separates these from the three that were bugs is intent, and intent has to be
# written down or the next person has to work it out again from scratch.
#
# A new entry here is a claim that a player being unable to move or click for the length of the
# loop is CORRECT. Scripted sequences qualify. A repeat that makes one item per pass does not.
DELIBERATE = {
    ('tutorial/scripts/skills/tut_woodcut.rs2', 'label,tut_woodcutting'):
        'one tree, not a batch: a ten-tick swing with its sound beats, inside a guided tutorial',
    ('quests/quest_viking/scripts/viking_olaf.rs2', 'label,viking_olaf_performance'):
        'a performance - four verses played to a crowd, which is a cutscene and not an action',
    ('quests/quest_zombiequeen/scripts/rashiliyia.rs2', 'label,rash_summon_minions'):
        'the boss summoning one to three minions, a tick each, as part of its own attack',
    ('quests/quest_ball/scripts/witch.rs2', 'ai_timer,nora_t_hagg'):
        'the witch casting on the player - an npc timer, and the hold is the spell landing',
    ('quests/quest_deserttreasure/scripts/dt_shadow.rs2', 'oploc1,fd_bandit_shutchest'):
        'three locks picked in sequence, bounded at three, and the sequence is the content',
    ('quests/quest_legends/scripts/legends_gate.rs2', 'label,open_legends_gate'):
        'one tick before a guard walks up and starts talking, inside a scripted approach',
    # THE THREE SELL-ALLS. These are the awkward ones and they are NOT settled: one tick per item
    # against a full pack is twenty-eight ticks rooted to the spot with every click discarded.
    # lunderwin.rs2 says in its own comment that Old School has no delay here and that RSC's was
    # copied on purpose, so changing it is a decision about how the game should play rather than a
    # defect to fix, and it is on DeathPlateau-Bugs#85 for Corey. Listed as deliberate because it
    # demonstrably was; listed with this note so it is not mistaken for settled.
    ('areas/area_lostcity/scripts/lunderwin.rs2', 'opnpc1,fairy_lunderwin'):
        'a sell-all paced one item per tick, copied from RSC on purpose - see the note above',
    ('areas/area_varrock/scripts/baraek.rs2', 'label,baraek_buy_fur'):
        'a sell-all paced one item per tick, the same idiom as lunderwin - see the note above',
    ('areas/area_varrock/scripts/baraek.rs2', 'label,baraek_grey_wolf_fur'):
        'a sell-all paced one item per tick, the same idiom as lunderwin - see the note above',
}


def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', line) for line in t.split('\n'))


def while_bodies(body):
    """Each `while (...) { ... }` body in this block, brace-matched."""
    out = []
    for w in re.finditer(r'\bwhile\s*\(', body):
        i = body.find('{', w.end())
        if i == -1:
            continue
        depth, j = 0, i
        while j < len(body):
            if body[j] == '{':
                depth += 1
            elif body[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(body[i:j])
    return out


found = set()
for root, _, files in os.walk('scripts'):
    for fn in sorted(files):
        if not fn.endswith('.rs2'):
            continue
        path = os.path.join(root, fn)
        text = strip_comments(open(path, encoding='utf-8', errors='replace').read())
        rel = os.path.relpath(path, 'scripts').replace(os.sep, '/')
        for m in re.finditer(r'^\[([^\]]+)\]([^\[]*)', text, re.M):
            head, block = m.group(1), m.group(2)
            if any('p_delay' in inner for inner in while_bodies(block)):
                found.add((rel, head))

print('1. no new loop holds the player')
new = sorted(found - set(DELIBERATE))
if new:
    for rel, head in new:
        bad('%s [%s] holds the player inside a while loop' % (rel, head),
            'pace it with a weak queue (see skill_crafting/scripts/glass/glass.rs2) or record it '
            'in DELIBERATE with a reason')
else:
    ok('every held loop in the content is one this file accounts for', len(found))

print('2. and every entry in the table is still there')
gone = sorted(set(DELIBERATE) - found)
if gone:
    for rel, head in gone:
        bad('%s [%s] is in DELIBERATE but no longer holds the player' % (rel, head),
            'remove the entry - a stale baseline is a check that has stopped asking anything')
else:
    ok('all %d deliberate holds still match the source' % len(DELIBERATE))

print('3. and each one says why')
missing = sorted(k for k, v in DELIBERATE.items() if not v or len(v) < 20)
for rel, head in missing:
    bad('%s [%s] has no real reason recorded' % (rel, head))
if not missing:
    ok('every deliberate hold carries a reason', len(DELIBERATE))

print()
if FAILED:
    print('%d FAILED' % len(FAILED))
    sys.exit(1)
print('ALL PASS')
