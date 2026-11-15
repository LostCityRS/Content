#!/usr/bin/env python3
"""Declared data that nothing reads, and script reads of data nothing declares.

    python3 tools/deaddata.py
    python3 tools/deaddata.py --kind param
    python3 tools/deaddata.py --quiet

A REPORT, NOT A VERDICT. It exits 0 whatever it finds, and it is not in the CI matrix, for the
same reason climbladders.ts in the engine is not a gate: nobody has yet decided which of these
findings is a bug. opsweep, orphans and ifselect each earned their baseline by being read through
once and triaged; this one has not been, and a ratchet banked before anyone has looked at its
output just freezes whatever was true on the day it was written.

WHAT IT LOOKS FOR. The three static ratchets all ask the same shape of question about OPTIONS - a
click with no script, a script no click can reach, a button whose handler disagrees with the cache.
None of them asks it about DATA. A param declared and populated across two hundred objs that no
script ever queries is work someone did for nothing, and more interestingly, a param that scripts
DO query but nothing ever sets is a script reading a default forever, which is a bug wearing the
costume of working code.

So each kind of declaration is sorted into:

  read, never set     a script asks for it and nothing supplies it, so the read always returns the
                      declared default. The bug-shaped bucket, and the reason this exists.
  set, never read     configs carry the data and no script looks at it. Dead weight, sometimes a
                      half-finished feature, sometimes a rename that missed its readers.
  neither             declared and then forgotten entirely.

HOW A READ IS RECOGNISED, and the one thing to be careful of. Params are read through oc_param,
npc_param, loc_param, struct_param, nc_param, lc_param and inv_totalparam, enums through enum and
its variants, db columns through the table:column spelling that db_getfield and db_find both use.
Rather than parse those call sites, this counts a NAME MENTIONED AS A WHOLE WORD anywhere in a
.rs2, which is deliberately generous: it would rather call a dead thing live than the reverse,
because a false "dead" claim sends somebody deleting content that works. Every bucket here is a
floor, not a count.

DBROWS ARE NOT SWEPT, on purpose. A dbrow is found by querying its table, not by being named, so
"no script mentions this row" is true of nearly all 2,102 of them and means nothing at all. The
table and its columns are the things a script names, so those are what this checks.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')

# Config extensions that can carry `param=<name>,<value>` or otherwise populate data.
CONFIG_EXTS = ('.obj', '.loc', '.npc', '.inv', '.struct', '.dbrow', '.enum', '.param', '.seq', '.spotanim', '.varp', '.varbit')


def walk(exts):
    """Every file under scripts/ with one of these extensions."""
    for base, _dirs, files in os.walk(SCRIPTS):
        for f in files:
            if f.endswith(exts):
                yield os.path.join(base, f)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read()


def declarations(ext):
    """Every [name] declared in files of one extension, as name -> relative path."""
    out = {}
    for path in walk((ext,)):
        rel = os.path.relpath(path, ROOT)
        for line in read(path).splitlines():
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                out.setdefault(line[1:-1], rel)
    return out


def dbtable_columns():
    """(table, column) -> relative path, for every column of every dbtable."""
    out = {}
    for path in walk(('.dbtable',)):
        rel = os.path.relpath(path, ROOT)
        table = None
        for line in read(path).splitlines():
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                table = line[1:-1]
            elif line.startswith('column=') and table:
                col = line[len('column='):].split(',')[0].strip()
                if col:
                    out.setdefault((table, col), rel)
    return out


def corpus(exts):
    """One blob of every file with these extensions, for whole-word searching."""
    return '\n'.join(read(p) for p in walk(exts))


def words(blob):
    """Every identifier-ish token in a blob, as a set, EXCLUDING local variables and constants.

    The lookbehind is the whole point and was learned the hard way. RuneScript spells a local as
    $name and a constant as ^name, and a plain \\w+ match tokenises $fail_coord to fail_coord - so
    the agility param `fail_coord`, which no script reads, was reported as "read by a script, never
    set" on the strength of a local variable and a proc parameter that merely share its name. That
    is the bug-shaped bucket polluted by a name collision, which is worse than a miss: it sends
    somebody investigating a param that was simply forgotten.
    """
    return set(re.findall(r'(?<![\w$^])([A-Za-z_][A-Za-z0-9_]*)', blob))


def param_assignments(blob):
    """Names appearing as `param=<name>,...` in config text - the param being set."""
    return set(re.findall(r'^\s*param\s*=\s*([A-Za-z_][A-Za-z0-9_]*)', blob, re.MULTILINE))


def param_values(blob):
    """The VALUE side of `param=<name>,<value>`, which is how an enum or struct gets referenced.

    Needed because a param whose type is enum or struct holds another declaration's name, and that
    is a reference no script contains. Without this, all 54 fishing_movement_*_enum tables read as
    unreachable on the strength of nothing but `enum(...)` never naming them literally - while
    all.npc names each one as `param=fishing_movement_enum,fishing_movement_catherby_enum` against
    the npc that uses it. The script reaches them through the param, one indirection away.
    """
    return set(re.findall(
        r'^\s*param\s*=\s*[A-Za-z_][A-Za-z0-9_]*\s*,\s*([A-Za-z_][A-Za-z0-9_]*)',
        blob, re.MULTILINE))


def bucket(declared, read_names, set_names):
    """Sort declarations into the three buckets."""
    read_never_set, set_never_read, neither = [], [], []
    for name, where in sorted(declared.items()):
        is_read = name in read_names
        is_set = name in set_names
        if is_read and not is_set:
            read_never_set.append((name, where))
        elif is_set and not is_read:
            set_never_read.append((name, where))
        elif not is_read and not is_set:
            neither.append((name, where))
    return read_never_set, set_never_read, neither


def show(title, rows, note, quiet, limit=25):
    print('-- %s: %d' % (title, len(rows)))
    if rows and note:
        print('   %s' % note)
    if not quiet:
        for name, where in rows[:limit]:
            print('     %-44s %s' % (name, where))
        if len(rows) > limit:
            print('     ... and %d more' % (len(rows) - limit))
    print('')


def main():
    args = sys.argv[1:]
    quiet = '--quiet' in args
    only = None
    if '--kind' in args:
        i = args.index('--kind')
        if i + 1 < len(args):
            only = args[i + 1]

    rs2 = corpus(('.rs2',))
    rs2_words = words(rs2)
    config_blob = corpus(CONFIG_EXTS)
    assigned = param_assignments(config_blob)
    values = param_values(config_blob)
    config_words = words(config_blob)
    # Anything a script names, or that a config hands to a param, is reachable.
    reachable = rs2_words | values

    print('reading %d .rs2 and the config files beside them' % sum(1 for _ in walk(('.rs2',))))
    print('')

    if only in (None, 'param'):
        declared = declarations('.param')
        # A param is "set" when a config assigns it by name. Struct params are assigned the same way.
        rns, snr, nei = bucket(declared, rs2_words, assigned)
        print('=== PARAMS (%d declared) ===' % len(declared))
        show('read by a script, never set by any config', rns,
             'each of these reads the declared default and always will', quiet)
        show('set by a config, never mentioned in any script', snr,
             'data someone populated that nothing queries', quiet)
        show('neither set nor read', nei, 'declared and forgotten', quiet)

    if only in (None, 'enum'):
        declared = declarations('.enum')
        orphaned = sorted((n, w) for n, w in declared.items() if n not in reachable)
        print('=== ENUMS (%d declared) ===' % len(declared))
        show('no script names it and no param hands it to one', orphaned,
             'an enum is reached by name or through an enum-typed param, so neither means no reader',
             quiet)

    if only in (None, 'struct'):
        declared = declarations('.struct')
        orphaned = sorted((n, w) for n, w in declared.items() if n not in reachable)
        print('=== STRUCTS (%d declared) ===' % len(declared))
        show('no script names it and no param hands it to one', orphaned,
             'nothing can reach these', quiet)

    if only in (None, 'db'):
        cols = dbtable_columns()
        dbrow_blob = corpus(('.dbrow',))
        populated = set(re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=', dbrow_blob, re.MULTILINE))
        # Two very different things, and the first version of this conflated them under a note
        # claiming "every row fills it in" - which was not true of any of the four it found.
        filled_unread, empty_unread = [], []
        for (table, col), where in sorted(cols.items()):
            if ('%s:%s' % (table, col)) in rs2:
                continue
            if col in populated:
                filled_unread.append(('%s:%s' % (table, col), where))
            else:
                empty_unread.append(('%s:%s' % (table, col), where))
        print('=== DBTABLE COLUMNS (%d declared across %d tables) ===' % (
            len(cols), len({t for t, _ in cols})))
        show('rows fill this column in and no script reads it', filled_unread,
             'data someone typed out that nothing queries', quiet)
        show('no script reads it and no row fills it in', empty_unread,
             'a declared column that was never used at either end', quiet)

    print('a report, not a verdict: nothing here is asserted and the exit code is always 0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
