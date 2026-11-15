#!/usr/bin/env python3
"""Every skill guide, checked against the interface it is drawn on and the items it names.

    python3 tools/guidecheck.py          from the content root

WHY THIS EXISTS. A skill guide is a list of ~skillguide_row calls, and the ROW NUMBER IS THE
COMPONENT it writes: row 3 is skill_guide:lvl3 and skill_guide:name3. Nothing checks that the
numbers are sensible, and two ways of getting them wrong are silent:

  * the same row written twice - the later call overwrites the earlier, so an entry is simply
    never drawn. The fletching guide had EIGHT rows numbered 3; the ogre arrow and six of the
    seven brutal arrows were invisible, and the page looked complete because row 3 had something
    in it.
  * a row past 40 - skill_guide.if has lvl1..lvl40 and ~skillguide_row's switch stops there, so
    the call does nothing at all.

It also checks the things a guide can be wrong about rather than malformed: an obj no .obj file
declares, and - for the guides whose listed level IS a requirement on the item - a level that
disagrees with the item's own levelrequire.

WHAT IT DELIBERATELY ALLOWS is in EXEMPT below. Two guides are not in level order on purpose and
say so in their own headers.
"""
import collections
import glob
import re
import sys

ROW = re.compile(r'~skillguide_row\(\s*(\d+)\s*,\s*\$\w+\s*,\s*(\d+|\^[a-z_0-9]+)\s*,'
                 r'\s*([a-z_0-9+]+)\s*,\s*"([^"]*)"')
PROC = re.compile(r'^\[(?:proc|label),([a-z_0-9]+)\]')
CONST = re.compile(r'^\^([a-z_0-9]+)\s*=\s*(-?\d+)\s*$')

# The interface's own limit: skill_guide.if has forty rows and ~skillguide_row's switch stops at 40.
ROWS = 40

# Pages that are NOT in level order, on purpose, with the reason each gives for it.
EXEMPT = {
    'hitpoints_guide_best': 'the left column is "Heals", not a level - relabelled by the guide',
    'hitpoints_guide_good': 'as hitpoints_guide_best',
    'hitpoints_guide_basic': 'as hitpoints_guide_best',
    'hitpoints_guide_potions': 'as hitpoints_guide_best',
    'hunter_guide_butterflies': 'two labelled groups on one page: the butterflies, then the implings'
}

# Guides whose listed level is a requirement carried by the item itself. A making guide is not one
# of these: fletching says what level MAKES a rune arrow, levelrequire says what level FIRES it.
WIELD = {'attack_guide', 'defence_guide', 'ranged_guide', 'woodcutting_guide', 'mining_guide'}


def load_constants():
    out = {}
    for path in glob.glob('scripts/**/*.constant', recursive=True):
        for line in open(path, encoding='utf-8', errors='replace'):
            m = CONST.match(line.split('//')[0].strip())
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def load_objs():
    known, levelreq, cur = set(), {}, None
    for path in glob.glob('scripts/**/*.obj', recursive=True):
        for line in open(path, encoding='utf-8', errors='replace'):
            s = line.strip()
            m = re.match(r'^\[([^\]]+)\]$', s)
            if m:
                cur = m.group(1)
                known.add(cur)
                continue
            m = re.match(r'^param=levelrequire,(\d+)$', s)
            if m and cur:
                levelreq[cur] = int(m.group(1))
    return known, levelreq


def guide_files():
    return sorted(set(glob.glob('scripts/skill_*/scripts/*_guide.rs2')) |
                  set(glob.glob('scripts/skill_*/scripts/*/*_guide.rs2')))


def check():
    consts = load_constants()
    known, levelreq = load_objs()
    complaints = []
    pages = {}

    for path in guide_files():
        cur = None
        for n, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
            m = PROC.match(line)
            if m:
                cur = m.group(1)
                continue
            m = ROW.search(line.split('//')[0])
            if not m:
                continue
            tok = m.group(2)
            level = consts.get(tok[1:]) if tok.startswith('^') else int(tok)
            pages.setdefault((path, cur), []).append(
                (int(m.group(1)), level, m.group(3), m.group(4), n))

    for (path, proc), rows in sorted(pages.items()):
        where = '%s %s' % (path, proc)
        idx = [r[0] for r in rows]

        for row, count in sorted(collections.Counter(idx).items()):
            if count > 1:
                names = [r[3] for r in rows if r[0] == row]
                complaints.append('%s: row %d is written %d times, so only "%s" is drawn (%s)'
                                  % (where, row, count, names[-1], ', '.join(names[:-1])))

        past = sorted({i for i in idx if i > ROWS})
        if past:
            complaints.append('%s: row(s) %s are past the %d-row list and are never drawn'
                              % (where, past, ROWS))

        gaps = sorted(set(range(1, max(idx) + 1)) - set(idx)) if idx else []
        if gaps:
            complaints.append('%s: row(s) %s are never set, leaving a blank line mid-page'
                              % (where, gaps))

        unresolved = [r[3] for r in rows if r[1] is None]
        if unresolved:
            complaints.append('%s: level constant does not resolve for %s' % (where, unresolved))
        elif proc not in EXEMPT:
            ordered = sorted(rows)
            for i in range(1, len(ordered)):
                if ordered[i][1] < ordered[i - 1][1]:
                    complaints.append('%s: row %d "%s" (%d) comes after row %d "%s" (%d)'
                                      % (where, ordered[i][0], ordered[i][3], ordered[i][1],
                                         ordered[i - 1][0], ordered[i - 1][3], ordered[i - 1][1]))
                    break

        base = path.split('/')[-1][:-4]
        for _, level, obj, name, line_no in rows:
            if obj not in known:
                complaints.append('%s:%d: "%s" names obj %s, which no .obj declares'
                                  % (path, line_no, name, obj))
            elif base in WIELD and obj in levelreq and level is not None \
                    and levelreq[obj] != level and not (levelreq[obj] == 0 and level == 1):
                complaints.append('%s:%d: "%s" says level %d, but the item requires %d'
                                  % (path, line_no, name, level, levelreq[obj]))

    return complaints, len(pages), sum(len(v) for v in pages.values())


if __name__ == '__main__':
    problems, pagecount, rowcount = check()
    for line in problems:
        print('  ' + line)
    print('%d guide(s), %d page(s), %d row(s): %d problem(s)'
          % (len(guide_files()), pagecount, rowcount, len(problems)))
    sys.exit(1 if problems else 0)
