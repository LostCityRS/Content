#!/usr/bin/env python3
"""Break the four-windows round on purpose, one thing at a time, and check that the check that
goes red is the one that is supposed to.

THE RULES THIS HARNESS FOLLOWS, all of them paid for by an earlier round:

  - COUNTING EXIT CODES IS NOT MUTATION TESTING. A mutation that trips some other check is not
    caught; it is a coincidence. Every entry names the check it expects and the run reports which
    check actually fired.
  - A MUTATION NEEDS AN ANCHOR UNIQUE TO THE THING IT IS MUTATING. str.replace takes the first
    match, so an anchor that appears twice breaks the wrong one and the real check stays green.
    Every anchor is asserted unique before it is applied.
  - A LABEL IS THE CHECK'S WORDING, NOT THE MUTATION'S. tools/mutate_labels.py audits that.

    python3 tools/windows_mutate.py
"""
import json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(tempfile.gettempdir(), 'windows_mutate_work')

# (file, find, replace, the wording of the check that must go red)
MUTS = [
    ('tools/adoptspec.json', '"column": "bronze",\n            "obj": "bronze_bar"',
     '"column": "bronze",\n            "obj": "iron_bar"',
     'the icon over the bronze column is set to a bronze bar'),
    ('tools/adoptspec.json', '"column": "silver",',
     '"column": "steel",',
     'and left to right they are the spec order, which is NOT the struct file order'),
    ('scripts/skill_smithing/configs/smelting/smelting.struct', '[smelting_runite_bar]',
     '[smelting_runite_bar_x]',
     'every column has a smelting_struct block'),
    ('scripts/skill_smithing/scripts/smelting/smelting.rs2', '~smelt_bar($struct, $bar, true);',
     '~displaymessage(^dm_default);',
     'and so does the use-an-ore-on-the-furnace path'),
    ('tools/genwindows.py', "'~smelt_bar($struct, $bar, false);',",
     "'anim(human_furnace, 0);',",
     "smelt_window.rs2 does not do 'anim(human_furnace' itself"),
    # The hold, in both directions. Flipping either argument is the regression DeathPlateau-Bugs#85
    # was: the window holding the player for every bar is a run that cannot be stopped, and the ore
    # path not holding is one bar per click as fast as a player can click.
    ('tools/genwindows.py', "'~smelt_bar($struct, $bar, false);',",
     "'~smelt_bar($struct, $bar, true);',",
     'and the window asks NOT to be held, so the run can be stopped'),
    ('scripts/skill_smithing/scripts/smelting/smelting.rs2', '~smelt_bar($struct, $bar, true);',
     '~smelt_bar($struct, $bar, false);',
     'while one ore on the furnace still pays its own delay'),
    ('scripts/areas/area_alkharid/configs/tanner.constant', '^werewolftanner_soft_leather_cost = 2',
     '^werewolftanner_soft_leather_cost = 1',
     'Canifis charges more for every hide'),
    ('scripts/areas/area_alkharid/configs/tanner.constant', '^werewolftanner_dragonhide_cost = 45',
     '^werewolftanner_dragonhide_cost = 21',
     'and not by a fixed markup, which is why both constants are read rather than one plus an offset'),
    ('tools/genwindows.py', "          'if (%tan_window_canifis = true) {',",
     "          'if (npc_type = werewolftanner) {',",
     'tan_window.rs2 reads npc_type exactly once'),
    # Anchored on the block header as well as the field: the file's own comment explains why
    # scope=temp is there, so 'scope=temp' alone appears twice and the harness refuses it. Fourth
    # time a check or a mutation in this project has found its own comment.
    ('scripts/skill_crafting/configs/leather/tan_window.varp', '[tan_window_canifis]\ntype=boolean\n',
     '[tan_window_canifis]\n',
     'and it is type=boolean, because the script reads it as one'),
    ('scripts/skill_crafting/configs/leather/tan_window.varp', '[tan_window_canifis]\ntype=boolean\nscope=temp',
     '[tan_window_canifis]\ntype=boolean\nscope=perm',
     'and that varp is scope=temp protect=no, the pair skill_guide.varp carries for the same reason'),
    ('tools/genwindows.py', "'if_sethide(tan_window:cell%d, true);' % i]",
     "'if_sethide(tan_window:cell%d, false);' % i]",
     'cell 7 is hidden rather than left dead'),
    ('tools/adoptspec.json', '"inv": "silvercast_tiara"',
     '"inv": "silvercast_sickle"',
     'silvercast_sickle stocks the obj the spec says that slot shows'),
    ('scripts/skill_crafting/configs/jewellery/jewellery.struct', '[tiara]\nparam=product,tiara',
     '[tiara_x]\nparam=product,tiara',
     'tiara has a crafting_jewelry struct'),
    ('scripts/skill_smithing/scripts/smelting/smelting.rs2', 'case silver_bar : ~silver_casting_open;',
     'case silver_bar : @craft_silver;',
     'the old cascade is no longer what a silver bar reaches'),
    # RETARGETED (2026-11-24, DeathPlateau-Bugs#89). This row used to swap the condition for
    # `if p['obj']:`, and it was reported as "a mutation no check catches". It was worse than that:
    # every one of the seven products has an obj AND has a struct or a handler, so BOTH forms of
    # the condition are true for all seven and the generated silver_casting.rs2 came out
    # byte-identical. No check could have caught it, because nothing changed. Proven by applying
    # the mutation to a clean tree and diffing the generated file.
    #
    # Dropping the handler half does change the output: the three products whose recipe a quest
    # owns - lightning_rod, silvthrill_rod, demonic_sigil - lose their transmit and fall into the
    # else branch. The old disjunction check stayed green for that too, so windows_battery.py now
    # carries the correspondence this row expects.
    ('tools/genwindows.py', "        if p['struct'] or p.get('handler'):\n            b += ['if (inv_total(inv, %s) > 0) {' % p['mould'],",
     "        if p['struct']:\n            b += ['if (inv_total(inv, %s) > 0) {' % p['mould'],",
     "lightning_rod's slot is filled in exactly when a struct or a quest owns its recipe"),
    ('tools/adoptspec.json', '"pot_of_cream": 460',
     '"pot_of_cream": 470',
     'every route from milk to cheese pays the same, and milk -> cream -> cheese does'),
    ('tools/genwindows.py', "                        % (src, p['obj'], p['level'], p['from'][src]))",
     "                        % (src, p['obj'], p['level'] + (1 if src == 'pot_of_cream' else 0), p['from'][src]))",
     'butter asks the same Cooking level whatever it was churned from'),
    ('tools/genwindows.py', "        b += ['[oploc1,%s]' % loc, '~churn_open;', '']",
     "        b += ['[oploc1,%s_x]' % loc, '~churn_open;', '']",
     'oploc1 on loc_10093 is answered now'),
    ('tools/genwindows.py', "    b = ['[opnpc3,ellis_tanner]', '~tan_window_open;', '']",
     "    b = ['[opnpc3,ellis_tanner_x]', '~tan_window_open;', '']",
     'and opnpc3 on Ellis is answered now'),
    ('scripts/areas/area_canafis/scripts/sbott.rs2', '[opnpc3,werewolftanner]',
     '[opnpc3,werewolftanner]\n~tan_window_open;\n\n[opnpc3,werewolftanner]',
     'the Canifis tanner still has exactly one opnpc3 - a duplicate trigger is a build error'),
    ('tools/genadopt.py', "        for n in p['_names']:",
     "        for n in p['_names'][:-1]:",
     'every smelt_window component is packed'),
    ('tools/genwindows.py', "def write(rel, head, body):",
     "import random\ndef write(rel, head, body):\n    head = head + ['%d' % random.randrange(9999)]",
     're-running them changes nothing: byte-identical'),
]


def run(entry, i):
    path, find, repl, label = entry
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(ROOT, W, ignore=shutil.ignore_patterns('.git', '__pycache__', 'data'))
    p = os.path.join(W, path)
    t = open(p, encoding='utf-8').read()
    n = t.count(find)
    if n != 1:
        return ('SKIP', 'anchor appears %d times, not once' % n)
    open(p, 'w', encoding='utf-8').write(t.replace(find, repl, 1))
    for tool in ('tools/genadopt.py', 'tools/genwindows.py'):
        subprocess.run([sys.executable, tool], cwd=W, capture_output=True, text=True)
    r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'windows_battery.py')], cwd=W,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return ('GREEN', 'the battery still passed')
    # The battery prints "FAIL <message>: <extra>" and a message can itself contain a colon, so
    # a split on the first one truncates the label and every such mutation reads as OTHER.
    fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
    if any(f == label or f.startswith(label + ':') for f in fired):
        return ('red', 'caught by its own check')
    if fired:
        return ('OTHER', 'caught by %r instead' % fired[0])
    return ('CRASH', (r.stderr.strip().split('\n') or [''])[-1][:90])


def main():
    seen = {}
    bad = 0
    for i, e in enumerate(MUTS, 1):
        state, why = run(e, i)
        if state != 'red':
            bad += 1
        print('  %-6s %-62s %s' % (state, e[3][:62], why))
        seen[e[3]] = state
    print()
    if bad:
        print('%d of %d mutations were not caught by the check they name' % (bad, len(MUTS)))
        sys.exit(1)
    print('every mutation was caught, each by its own check')


if __name__ == '__main__':
    main()
