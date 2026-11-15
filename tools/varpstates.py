#!/usr/bin/env python3
"""Quest states a script tests for and nothing ever sets.

    python3 tools/varpstates.py
    python3 tools/varpstates.py --var mm_main
    python3 tools/varpstates.py --all

A REPORT, NOT A VERDICT. Exits 0, not in the CI matrix, same as deaddata.py and shoparbitrage.py.

A quest in this codebase is a number in a varp and a pile of branches that read it. Walk into the
right room at stage 4 and something happens; at stage 5 something else does. That makes each quest
a state machine written down in two halves that nobody checks against each other, and there are two
ways for the halves to disagree:

  tested, never set     a branch waits for a stage no line of script ever assigns. The player can
                        never be in that state, so the branch is dead - a conversation that cannot
                        happen, a door that cannot open. This is the bucket worth reading.
  set, never tested     a stage gets assigned and no branch tests for it by equality. Usually fine,
                        because ranges do the work: `if (%var < 3)` covers 0, 1 and 2 without
                        naming them. Reported only under --all, and it is not evidence of anything
                        on its own.

THE FALSE POSITIVE THIS IS BUILT TO AVOID. A varp written anywhere through something other than a
literal - `%var = $stage`, `%var = add(%var, 1)`, or a proc that takes the value as an argument -
has values this cannot see, and every equality test against it would look unreachable. So any varp
with even ONE non-literal write is dropped from the analysis entirely and listed separately under
--all. That is deliberately blunt: a varp half of whose writes are computed would need the values
tracing through the callers, and a tool that guesses there would produce exactly the kind of
confident nonsense that sends somebody hunting a bug that is not there.

Bitfield varps are dropped too. A name ending _bits holds several flags at once and is read through
bit helpers rather than compared to a whole number, so "state 5" means nothing for one.

WHY THE BRACKET MATTERS. `=` is assignment at the start of a statement and equality inside a
condition - the same character doing both jobs, which is why this reads position rather than
pattern: a line whose first token is the varp is a write, and a varp appearing anywhere else in a
line is a read.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')

LITERAL = re.compile(r'^-?\d+$')


def rs2_files():
    for base, _dirs, files in os.walk(SCRIPTS):
        for f in files:
            if f.endswith('.rs2'):
                yield os.path.join(base, f)


def main():
    args = sys.argv[1:]
    show_all = '--all' in args
    only = None
    if '--var' in args:
        i = args.index('--var')
        if i + 1 < len(args):
            only = args[i + 1]

    written = {}      # var -> {value: [where]}
    tested = {}       # var -> {value: [where]}
    dynamic = {}      # var -> [where] for writes this cannot read

    # PAREN DEPTH IS THE WHOLE TEST, and it took three wrong answers to get here. `=` is assignment
    # at statement level and equality inside a condition, so position in the line is what separates
    # them - but "the line starts with %var" is not that position. Both of these assign, and neither
    # starts with the varp:
    #
    #   [if_button,bank_main:com_99] %bankinsert = 0;
    #   case eagle_bronze_feather : %eaglespeak_door_bronze = 1;
    #
    # while `if (%bankinsert = 1)` compares. What actually distinguishes them is that a comparison
    # lives inside brackets and an assignment does not, so each occurrence is judged by the paren
    # depth at its own position. That also gets `if (%a = 1) %b = 2;` right, counting the first as a
    # test and the second as a write, which no prefix-stripping rule managed.
    occur_re = re.compile(r'%([a-z0-9_]+)\s*=\s*([^;)]*)')

    for path in rs2_files():
        rel = os.path.relpath(path, ROOT)
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            for n, raw in enumerate(fh, 1):
                line = raw.split('//')[0].strip()
                if not line or '%' not in line:
                    continue
                where = '%s:%d' % (rel, n)

                for m in occur_re.finditer(line):
                    var, rhs = m.group(1), m.group(2).strip()
                    before = line[:m.start()]
                    depth = before.count('(') - before.count(')')
                    if depth > 0:
                        # Inside brackets: a comparison, so this is a state being tested for.
                        if LITERAL.match(rhs):
                            tested.setdefault(var, {}).setdefault(int(rhs), []).append(where)
                    elif LITERAL.match(rhs):
                        written.setdefault(var, {}).setdefault(int(rhs), []).append(where)
                    else:
                        dynamic.setdefault(var, []).append(where)

    usable = sorted(
        v for v in set(written) | set(tested)
        if v not in dynamic and not v.endswith('_bits')
    )
    if only:
        usable = [v for v in usable if v == only]

    unreachable = []
    for var in usable:
        # ZERO IS ALWAYS REACHABLE. A varp has no default= line in any .varp file; it starts at 0
        # and that is the state every player is in before the quest begins. Testing for 0 therefore
        # needs no write at all, and counting it as unreachable condemned every "have you started
        # this yet" branch in the codebase.
        w = set(written.get(var, {})) | {0}
        for val, wheres in sorted(tested.get(var, {}).items()):
            if val not in w:
                unreachable.append((var, val, wheres, sorted(w - {0})))

    print('%d varps written or tested with a literal; %d usable after dropping %d with computed '
          'writes and the _bits bitfields'
          % (len(set(written) | set(tested)), len(usable), len(dynamic)))
    print('')

    print('-- states a script tests for that nothing ever sets: %d' % len(unreachable))
    if unreachable:
        print('   each of these branches waits for a value the quest cannot reach')
        print('')
    for var, val, wheres, w in unreachable:
        print('   %%%s = %d' % (var, val))
        print('     tested at   %s' % ', '.join(wheres[:3]) + ('' if len(wheres) <= 3 else ', ...'))
        print('     ever set to %s' % (', '.join(str(x) for x in w) if w else '(nothing at all)'))
    print('')

    if show_all:
        print('-- set but never tested by equality (ranges usually cover these; weak evidence)')
        for var in usable:
            t = set(tested.get(var, {}))
            extra = sorted(set(written.get(var, {})) - t)
            if extra:
                print('   %%%-28s set to %s, never compared to %s'
                      % (var, ','.join(str(x) for x in extra), ','.join(str(x) for x in extra)))
        print('')
        print('-- dropped for having writes this cannot read: %d' % len(dynamic))
        for var in sorted(dynamic)[:30]:
            print('   %%%-28s e.g. %s' % (var, dynamic[var][0]))
        print('')

    print('a report, not a verdict: nothing here is asserted and the exit code is always 0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
