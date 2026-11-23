"""Battery for Recipe for Disaster's sub-quest rewards.

WHY THIS FILE EXISTS. Until 1 November the quest paid one quest point per sub-quest and nothing
else: not a single stat_advance in ten sub-quests, and no reward scroll, where every other quest
in the build ends on ~send_quest_complete. It was reported on the Mountain Dwarf and was true of
all nine. Nothing asserted any of it, so nothing noticed.

The numbers below are Old School's, from the wiki's per-sub-quest reward lists cross-checked
against its Quest experience rewards table. They are written here as data rather than read out of
the script, so a change to the script that quietly alters a payout fails this instead of shipping.

ONE ROW IS CONTESTED and it is a filing error rather than a number: the wiki's Full guide lists
Skrach's four 1,500s under Evil Dave. The sub-quest pages and the experience table agree with each
other against it, and Dave's own page gives 7,000 Cooking and nothing else.

    python3 tools/rfd_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

# name -> the experience that sub-quest hands over, by skill, IN THE WIKI'S OWN NUMBERS.
# stat_advance takes TENTHS of a point, so these are compared against ten times themselves -
# kept in the published figures here because that is what the reward scrolls print and what a
# reader can check against a wiki page. The quest shipped these as whole numbers against
# scrolls promising ten times as much, so every sub-quest paid a tenth of what it advertised
# and a player on 10x got exactly the 1x figure (DeathPlateau-Bugs#70).
#
# THIS BATTERY COULD NOT HAVE CAUGHT THAT, because it was never wired into
# .github/workflows/content.yml - written for RFD's rewards, and not run once. It is in the
# workflow now.
REWARDS = {
    'cook':    {},
    'dwarf':   {'cooking': 1000, 'slayer': 1000},
    'goblins': {'cooking': 1000, 'farming': 1000, 'crafting': 1000},
    'pirate':  {'cooking': 1000, 'crafting': 1000, 'fishing': 1000, 'smithing': 1000},
    'guide':   {'cooking': 2500, 'magic': 2500},
    'dave':    {'cooking': 7000},
    'ogre':    {'woodcutting': 1500, 'cooking': 1500, 'crafting': 1500, 'ranged': 1500},
    'varze':   {'cooking': 4000, 'hitpoints': 4000},
    'monkey':  {'cooking': 10000, 'agility': 10000},
}

QUEST = read('scripts/quests/quest_100/scripts/quest_100.rs2')
REWARD_PROC = QUEST.split('[proc,hundred_subquest_reward]', 1)[-1].split('[proc,hundred_subquest_scroll]', 1)[0]

# ---- the payouts
shipped = {}
cur = None
for line in REWARD_PROC.split('\n'):
    m = re.match(r'\s*case \^hundred_bit_(\w+) :', line)
    if m:
        cur = m.group(1); shipped[cur] = {}
        continue
    m = re.match(r'\s*stat_advance\((\w+), (\d+)\);', line)
    if m and cur:
        shipped[cur][m.group(1)] = int(m.group(2))

check(set(shipped) == set(REWARDS),
      'every sub-quest but the finale has a reward case: %s'
      % (sorted(set(REWARDS) ^ set(shipped)) or '%d of %d' % (len(shipped), len(REWARDS))))
for name in sorted(REWARDS):
    want = {k: v * 10 for k, v in REWARDS[name].items()}   # tenths, which is what stat_advance takes
    check(shipped.get(name) == want,
          '  %-8s pays %s' % (name, REWARDS[name] or 'a quest point and nothing else')
          + ('' if shipped.get(name) == want else ' - wanted %s in tenths, ships %s' % (want, shipped.get(name))))

# ---- THE FINALE MUST NOT BE IN THERE. hundred_culinaromancer.rs2 sets that bit and then opens
# its own ~send_quest_complete; a case here would put a second scroll on top of it.
check('^hundred_bit_culinaromancer' not in REWARD_PROC,
      'the Culinaromancer has no case - it opens its own quest-complete scroll and a case here '
      'would announce the finale twice')

# ---- every sub-quest actually reaches the award, and the award reaches the reward
SCRIPTS = os.path.join(C, 'scripts/quests/quest_100/scripts')
awarded = set()
for f in sorted(os.listdir(SCRIPTS)):
    if not f.endswith('.rs2'): continue
    for m in re.findall(r'~hundred_award_subquest\(\^hundred_bit_(\w+)\)', read('scripts/quests/quest_100/scripts/' + f)):
        awarded.add(m)
check(awarded == set(REWARDS) | {'culinaromancer'},
      'all ten sub-quests call ~hundred_award_subquest: %s'
      % (sorted((set(REWARDS) | {'culinaromancer'}) ^ awarded) or '10 of 10'))
check('~hundred_subquest_reward($bit);' in QUEST,
      '...and ~hundred_award_subquest pays the reward out, rather than only setting the bit - '
      'which is what it did before')

# ---- the scroll must not mark the whole quest done
SCROLL = QUEST.split('[proc,hundred_subquest_scroll]', 1)[-1]
check('if_setcolour' not in SCROLL and 'send_quest_complete' not in SCROLL,
      "the sub-quest scroll does not recolour the quest list or call ~send_quest_complete: "
      'Recipe for Disaster is ONE list entry with ten steps, and either would paint it green '
      'on the first sub-quest')

print()
print('A step the player cannot guess has to be named somewhere they will read it')
# THE BUG. Freeing the Lumbridge Guide needs a cake of guidance, and the only thing in the build
# that makes one is Wizard Traiborn. The journal said "a cake tin and a range will do the rest",
# the plinth turned a plain cake away with "he needs something with more direction in it", and
# Traiborn's name appeared NOWHERE a player could read it - not in the journal, not in the
# inspect text, not in the refusal. The enchantment was added after the journal was written and
# the journal was never told. So the quest asked for an item and withheld the one instruction
# needed to make it (DeathPlateau-Bugs#62).
GUIDE = read('scripts/quests/quest_100/scripts/hundred_guide.rs2')

# Player-visible text only: strip whole-line comments, so a name that lives in a code comment -
# which is where Traiborn's only mention used to be - does not count as having told anybody.
_visible = '\n'.join(l for l in GUIDE.split('\n') if not l.lstrip().startswith('//'))

check('hundred_cake_of_guidance' in _visible and 'inv_add(inv, hundred_cake_of_guidance' in _visible,
      'the cake of guidance is made in this file and nowhere else')
check('Traiborn' in _visible,
      'and Traiborn, the only one who makes it, is named in text a player can read')

# THE MOMENT OF CONFUSION, which is where the hint has to be. A player who followed the journal
# arrives here holding exactly the wrong cake; this branch knew that and would not say what a
# right one was.
_a, _b = 'if (last_useitem = cake) {', 'if (last_useitem ! hundred_cake_of_guidance)'
_plain = _a in GUIDE and _b in GUIDE and GUIDE.index(_a) < GUIDE.index(_b)
check(_plain, 'the plinth still turns a plain cake away before the real one')
_branch = GUIDE.split('if (last_useitem = cake) {', 1)[1].split('}', 1)[0] if 'if (last_useitem = cake) {' in GUIDE else ''
check('Traiborn' in _branch,
      '...and that refusal now says who can fix it, instead of only that it is wrong')

# AND THE JOURNAL ANSWERS THE QUESTION IN FRONT OF THE PLAYER rather than one fixed block. RFD's
# journal appends every sub-quest still open, so a long entry for each runs the page off the
# bottom - which is why this is three states and not five more lines.
# STOP AT THE NEXT PROC. This slice ran to end of file, and Traiborn's own two procs sit BELOW
# the journal in this file - so it swallowed them, and the checks below passed on his name and
# on an inv_total that belonged to his chat rather than to the journal. A mutation that blanked
# the journal's plain-cake branch was not caught until this was narrowed.
_journal = GUIDE.split('[proc,hundred_guide_journal]', 1)[1]
_journal = re.split(r'\n\[(?:proc|label|op|if_)', _journal)[0]
check('inv_total(inv, hundred_cake_of_guidance)' in _journal,
      'the journal knows when the cake is already made, and says to go and use it')
check('inv_total(inv, cake)' in _journal,
      '...and when a plain cake is in the bag, which is the state that dead-ended')
check(_journal.count('Traiborn') >= 2,
      '...and names Traiborn in both of the states that need him')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
