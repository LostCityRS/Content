"""Every quest's REQUIREMENTS and REWARDS, as the build has them and as the OSRS wiki has them.

Wanted! was shipped twice with the wrong rewards - 18,000 Magic and 5,000 Hitpoints, then the right
5,000 Slayer - and nobody could say which of the other hundred-and-eight were wrong the same way,
because the facts live in three different places and none of them is a table:

    the QUEST POINTS are the fourth argument to ~send_quest_complete
    the EXPERIENCE is whatever stat_advance calls sit in the same script block as that call, in
        TENTHS - stat_advance(slayer, 50000) is the wiki's 5,000
    the REWARD TEXT is a pipe-separated string in the sixth argument, written by hand, and is the
        thing a player actually reads - so it can disagree with both of the above
    the REQUIREMENTS are guard clauses scattered through whichever script starts the quest

This reads all four out of the content, reads the same four off the wiki, and prints the
disagreements.

    python tools/questaudit.py                 every quest, differences only
    python tools/questaudit.py -v              every quest, whether it differs or not
    python tools/questaudit.py wanted deal     just those
    python tools/questaudit.py --json out.json the whole comparison, for another tool to read

WHAT IT CANNOT TELL YOU. The requirement scan is a grep for guard clauses, so a requirement
enforced somewhere unusual reads as missing, and a guard that is really about something else reads
as a requirement. Every requirement line is printed with the file and line it came from for that
reason. The wiki side is raw wikitext: a quest whose page names a requirement in prose rather than
in {{SCP}} is not seen either. Treat a row as "go and look", not as a verdict - the same rule
mapfloor.py's thinAir carries.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(CONTENT, 'scripts')
CACHE = os.path.join(CONTENT, '.wikicache')
UA = 'DeathPlateau-quest-audit/1.0 (private server content check)'

# Display name in questlist.if -> the wiki's own title, where they differ.
WIKI_TITLE = {
    'A Fairy Tale Pt. 1': 'Fairy Tale I - Growing Pains',
    'A Fairy Tale Pt. 2': 'Fairy Tale II - Cure a Queen',
    'Shilo Village': 'Shilo Village (quest)',
    'Scorpion Catcher': 'Scorpion Catcher',
    'Elemental Workshop': 'Elemental Workshop I',
    'Lost City': 'Lost City',
    'Observatory Quest': 'Observatory Quest',
    'The Hand in the Sand': 'The Hand in the Sand',
    'Mountain Daughter': 'Mountain Daughter',
    'Watch Tower': 'Watchtower',
    "Mourning's Ends Part 2": "Mourning's End Part II",
    "Mourning's Ends Part 1": "Mourning's End Part I",
    'Rune Mysteries Quest': 'Rune Mysteries',
    'Legend\'s Quest': "Legends' Quest",
    'Legends Quest': "Legends' Quest",
}

# SKILLS THE WIKI LISTS THAT THIS SERVER DOES NOT HAVE. Sailing was added to Old School in 2025 and
# its experience is now listed on quests from 2004, so a straight comparison says every one of them
# is missing a reward. Reported separately rather than silently dropped - a skill appearing here is
# a decision about the server's era, not a parsing detail.
NOT_OURS = ('sailing',)

# Not a skill at all. A reward listed as "overall" experience is a lamp the player spends
# where they like - The Great Brain Robbery's blessed lamp - so there is no stat_advance to
# find and comparing it reports a missing reward that is sitting in the player's inventory.
NOT_A_SKILL = ('overall',)

SKILLS = ('attack', 'defence', 'strength', 'hitpoints', 'ranged', 'prayer', 'magic', 'cooking',
          'woodcutting', 'fletching', 'fishing', 'firemaking', 'crafting', 'smithing', 'mining',
          'herblore', 'agility', 'thieving', 'slayer', 'farming', 'runecraft', 'runecrafting',
          'construction', 'hunter')


# ---------------------------------------------------------------- the content side
def read(path):
    return io.open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')


def walk(ext, root=SCRIPTS):
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith(ext):
                yield os.path.join(dirpath, fn)


def questlist():
    """component key -> the name the quest list draws, in list order."""
    out, key, body = {}, None, {}
    for line in read(os.path.join(SCRIPTS, 'interfaces', 'questlist.if')).split('\n'):
        line = line.strip()
        m = re.match(r'^\[([A-Za-z0-9_]+)\]$', line)
        if m:
            if key and 'text' in body and body.get('buttontype') == 'normal':
                out[key] = body['text']
            key, body = m.group(1), {}
            continue
        if '=' in line and not line.startswith('//'):
            k, v = line.split('=', 1)
            body[k.strip()] = v.strip()
    if key and 'text' in body and body.get('buttontype') == 'normal':
        out[key] = body['text']
    return out


def constants():
    """^name -> (value, defining file). Values stay strings; some are coords, not numbers."""
    out = {}
    for path in walk('.constant'):
        for line in read(path).split('\n'):
            m = re.match(r'^\^([A-Za-z0-9_]+)\s*=\s*([^/\n]+)', line.strip())
            if m:
                out[m.group(1)] = (m.group(2).strip(), path)
    return out


def resolve(token, consts, depth=0):
    """A literal, or a ^constant chased to one, or None."""
    token = token.strip()
    if re.match(r'^-?\d+$', token):
        return int(token)
    if token.startswith('^') and depth < 8:
        hit = consts.get(token[1:])
        if hit:
            return resolve(hit[0], consts, depth + 1)
    return None


def blocks(text):
    """[(header, body, first line number)] for every [trigger,name] block in a script."""
    out = []
    cur, head, start = [], None, 0
    for i, line in enumerate(text.split('\n'), 1):
        if re.match(r'^\[[a-z_]+,', line):
            if head:
                out.append((head, '\n'.join(cur), start))
            head, cur, start = line.strip(), [], i
        elif head:
            cur.append(line)
    if head:
        out.append((head, '\n'.join(cur), start))
    return out


def content_facts(keys):
    """key -> {qp, xp{skill:amount}, reward_text, where, requirements[]}."""
    consts = constants()
    # xp         granted in the same block as ~send_quest_complete - the completion reward
    # xp_elsewhere   granted anywhere else in the quest's own directory. Kept apart because the
    #                wiki lists only the completion reward, so experience paid out mid-quest (a
    #                lamp, a one-off training step) would otherwise read as a missing reward. A
    #                quest that pays its reward from a different script reads the same way, which
    #                is why this is reported rather than quietly added to the total.
    facts = {k: {'qp': None, 'xp': {}, 'xp_elsewhere': {}, 'reward_text': None, 'where': None,
                 'requirements': [], 'journal': None, 'endings': []} for k in keys}

    # which quest directory defines a given ^constant, so a guard naming another quest's
    # completion constant can be turned back into that quest
    dir_of_const = {}
    for name, (_v, path) in consts.items():
        rel = os.path.relpath(path, SCRIPTS).replace('\\', '/')
        if rel.startswith('quests/'):
            dir_of_const[name] = rel.split('/')[1]

    # a quest directory -> its questlist key, via the journal handler
    key_of_dir = {}
    for path in walk('.rs2'):
        rel = os.path.relpath(path, SCRIPTS).replace('\\', '/')
        text = read(path)
        for m in re.finditer(r'\[if_button,questlist:([A-Za-z0-9_]+)\]', text):
            k = m.group(1)
            if k in facts:
                facts[k]['journal'] = rel
                if rel.startswith('quests/'):
                    key_of_dir.setdefault(rel.split('/')[1], k)

    # the completion call, and the experience granted in the same block as it
    for path in walk('.rs2'):
        rel = os.path.relpath(path, SCRIPTS).replace('\\', '/')
        text = read(path)
        if '~send_quest_complete' not in text:
            continue
        for head, body, line0 in blocks(text):
            whole = head + '\n' + body
            m = re.search(r'~send_quest_complete\(\s*questlist:([A-Za-z0-9_]+)\s*,(.*?)\);',
                          whole, re.S)
            if not m:
                continue
            key = m.group(1)
            if key not in facts:
                continue
            args = split_args(m.group(2))
            f = facts[key]
            # ONE ENDING PER BLOCK, NEVER THE SUM. Temple of Ikov finishes for Armadyl or for
            # Lucien, each in its own [queue], each granting 10,500 Ranged and 8,000 Fletching -
            # and adding them together said the quest pays 21,000 and 16,000, which is twice what
            # its own reward scroll promises. It read as the clearest bug in the audit and there
            # was nothing wrong with it. Endings are alternatives: they are collected separately
            # and the quest agrees with the wiki if ANY of them does.
            ending = {'at': '%s:%d' % (rel, line0), 'xp': {}, 'qp': None, 'reward_text': None,
                      'comment': comment_above(whole, m.start())}
            if len(args) >= 3:
                ending['qp'] = resolve(args[2], consts)
            if len(args) >= 5:
                ending['reward_text'] = args[4].strip().strip('"')
            for sm in re.finditer(r'stat_advance\(\s*([a-z_]+)\s*,\s*([^)]+)\)', whole):
                amount = resolve(sm.group(2), consts)
                if amount is not None:
                    ending['xp'][sm.group(1)] = ending['xp'].get(sm.group(1), 0) + amount
            f['endings'].append(ending)
            f['where'] = ending['at']
            f['qp'] = ending['qp']
            f['reward_text'] = ending['reward_text']
            f['xp'] = ending['xp']

    # requirements and the rest of the experience: anywhere in the quest's own directory
    for path in walk('.rs2'):
        rel = os.path.relpath(path, SCRIPTS).replace('\\', '/')
        if not rel.startswith('quests/'):
            continue
        qdir = rel.split('/')[1]
        key = key_of_dir.get(qdir)
        if key is None:
            continue
        whole = read(path)
        for sm in re.finditer(r'stat_advance\(\s*([a-z_]+)\s*,\s*([^)]+)\)', whole):
            amount = resolve(sm.group(2), consts)
            if amount is None:
                continue
            f = facts[key]
            skill = sm.group(1)
            # the completion block's own calls are already counted
            if f['where'] and rel == f['where'].split(':')[0] and skill in f['xp']:
                continue
            f['xp_elsewhere'][skill] = f['xp_elsewhere'].get(skill, 0) + amount
        for i, line in enumerate(read(path).split('\n'), 1):
            s = line.strip()
            if s.startswith('//') or not s.startswith('if ('):
                continue
            # a skill level gate
            for sm in re.finditer(r'\bstat\((%s)\)\s*<\s*([^)\s&|]+)' % '|'.join(SKILLS), s):
                lvl = resolve(sm.group(2), consts)
                if lvl is not None:
                    facts[key]['requirements'].append(
                        {'kind': 'skill', 'skill': sm.group(1), 'level': lvl,
                         'at': '%s:%d' % (rel, i)})
            # a quest point gate
            for sm in re.finditer(r'%qp\s*<\s*([^)\s&|]+)', s):
                n = resolve(sm.group(1), consts)
                if n is not None:
                    facts[key]['requirements'].append(
                        {'kind': 'qp', 'points': n, 'at': '%s:%d' % (rel, i)})
            # another quest's completion
            for sm in re.finditer(r'%([A-Za-z0-9_]+)\s*(<|!|<>)\s*\^([A-Za-z0-9_]+)', s):
                cname = sm.group(3)
                if not cname.endswith('_complete'):
                    continue
                other = key_of_dir.get(dir_of_const.get(cname, ''), None)
                if other and other != key:
                    facts[key]['requirements'].append(
                        {'kind': 'quest', 'quest': other, 'via': cname,
                         'at': '%s:%d' % (rel, i)})
    for f in facts.values():
        seen, uniq = set(), []
        for r in f['requirements']:
            sig = tuple(sorted((k, v) for k, v in r.items() if k != 'at'))
            if sig not in seen:
                seen.add(sig)
                uniq.append(r)
        f['requirements'] = uniq
    return facts


def comment_above(text, pos):
    """The // comment block immediately above a position, which is where a deliberate departure
    from the wiki is written down. Swan Song pays 10,000 Fishing rather than the wiki's 50,000
    and says why in the three lines above the call: a November 2022 rebalance of a modern economy,
    and this server is 2006. A tool that cannot see that comment proposes undoing it."""
    # ANY comment in the block that mentions the wiki, not only the one directly above the call.
    # Swan Song's three lines sit above its stat_advance calls rather than above
    # ~send_quest_complete, so looking only upwards from the call found nothing and the audit went
    # on proposing a change that had already been considered and rejected in writing.
    out = []
    run = []
    for line in text.split(chr(10)):
        s = line.strip()
        if s.startswith('//'):
            run.append(s.lstrip('/ ').rstrip())
            continue
        if run:
            joined = ' '.join(run)
            if re.search(r'\bwiki\b|old school|osrs|20\d\d', joined, re.I):
                out.append(joined)
            run = []
    if run:
        joined = ' '.join(run)
        if re.search(r'\bwiki\b|old school|osrs|20\d\d', joined, re.I):
            out.append(joined)
    return ' | '.join(out)


def split_args(s):
    """Split a call's argument list on commas that are not inside quotes or brackets."""
    out, depth, quoted, cur = [], 0, False, ''
    for ch in s:
        if ch == '"':
            quoted = not quoted
        if not quoted:
            if ch in '([<':
                depth += 1
            elif ch in ')]>':
                depth -= 1
            elif ch == ',' and depth == 0:
                out.append(cur)
                cur = ''
                continue
        cur += ch
    out.append(cur)
    return out


# ---------------------------------------------------------------- the wiki side
def fetch(page):
    # THE CACHE KEY HAS TO KEEP THE PAGES APART. Stripping every non-word character made
    # "Heroes Quest" and "Heroes' Quest" the same file: the first is a redirect to the second, the
    # redirect was written to HeroesQuest.wiki, and following it then read that same file straight
    # back. Heroes' Quest came out with no rewards at all, so all twelve experience rewards the
    # build grants read as "the wiki does not list this".
    safe = re.sub(r'[^A-Za-z0-9_]', lambda m: '%%%02X' % ord(m.group(0)), page)
    path = os.path.join(CACHE, safe[:120] + '.wiki')
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return read(path)
    url = 'https://oldschool.runescape.wiki/w/' + urllib.parse.quote(page) + '?action=raw'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode('utf-8', 'ignore')
    os.makedirs(CACHE, exist_ok=True)
    io.open(path, 'w', encoding='utf-8').write(text)
    time.sleep(0.5)
    return text


def template(text, name):
    """The body of {{name ...}}, brace-matched."""
    i = text.find('{{' + name)
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(text):
        if text.startswith('{{', j):
            depth += 1
            j += 2
            continue
        if text.startswith('}}', j):
            depth -= 1
            j += 2
            if depth == 0:
                return text[i:j]
            continue
        j += 1
    return None


def fields(body):
    """{name: value} for a template, split on the pipes at ITS OWN brace depth.

    A regex with a lookahead for the next "|field =" does not work here and the way it fails is
    quiet: Dragon Slayer's qp came back as the whole rest of the template, and stripping the
    non-digits out of that gave 2186501865060 rather than 2. Nested templates and wiki links carry
    their own pipes, so depth is the only thing that separates a field from a link's caption.
    """
    inner = body[2:-2] if body.startswith('{{') else body
    parts, depth, cur = [], 0, ''
    i = 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two in ('{{', '[['):
            depth += 1
            cur += two
            i += 2
            continue
        if two in ('}}', ']]'):
            depth -= 1
            cur += two
            i += 2
            continue
        if inner[i] == '|' and depth == 0:
            parts.append(cur)
            cur = ''
            i += 1
            continue
        cur += inner[i]
        i += 1
    parts.append(cur)
    out = {}
    for p in parts[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            out[k.strip().lower()] = v.strip()
    return out


def field(body, name):
    return fields(body).get(name)


def num(s):
    s = s.replace(',', '').strip()
    return int(s) if re.match(r'^\d+$', s) else None


def wiki_facts(title):
    page = WIKI_TITLE.get(title, title)
    text = fetch(page)
    seen = set()
    while text.lstrip().upper().startswith('#REDIRECT') and page not in seen:
        seen.add(page)
        m = re.search(r'\[\[([^\]|#]+)', text)
        if not m:
            break
        page = m.group(1).strip()
        text = fetch(page)
    out = {'page': page, 'qp': None, 'xp': {}, 'reqs_skill': {}, 'reqs_quest': [],
           'reqs_qp': None, 'rewards_raw': None, 'requirements_raw': None, 'later_xp': {},
           'release_year': None}

    # THE RELEASE YEAR DECIDES WHETHER A REWARD IS ORIGINAL OR A LATER ADDITION. This server plays
    # 2006-era content as it played in 2006, so a 2004 quest that Old School gave extra experience
    # to in 2016 keeps the 2004 reward; a quest released after 2006 was ported from Old School in
    # the first place and matches the wiki.
    box = template(text, 'Infobox Quest')
    if box:
        rel = fields(box).get('release', '')
        ym = re.findall(r'(19|20)\d\d', rel)
        m2 = re.search(r'((?:19|20)\d\d)', rel)
        if m2:
            out['release_year'] = int(m2.group(1))

    det = template(text, 'Quest details')
    if det:
        req = field(det, 'requirements')
        if req:
            out['requirements_raw'] = req
            for m in re.finditer(r'\{\{SCP\|([A-Za-z ]+)\|([\d,]+)', req):
                skill, lvl = m.group(1).strip().lower(), num(m.group(2))
                if lvl is None:
                    continue
                if skill == 'quest':
                    out['reqs_qp'] = lvl
                elif skill not in NOT_OURS:
                    out['reqs_skill'][skill] = max(out['reqs_skill'].get(skill, 0), lvl)
            for m in re.finditer(r'\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]', req):
                out['reqs_quest'].append(m.group(1).strip())

    rew = template(text, 'Quest rewards')
    if rew:
        qp = field(rew, 'qp')
        if qp:
            out['qp'] = num(re.sub(r'[^\d,]', '', qp))
        body = field(rew, 'rewards')
        if body:
            out['rewards_raw'] = body
            for m in re.finditer(r'\{\{SCP\|([A-Za-z ]+)\|([\d,]+)', body):
                skill, amt = m.group(1).strip().lower(), num(m.group(2))
                if amt is None or skill == 'quest':
                    continue
                if skill in NOT_A_SKILL:
                    continue
                if skill in NOT_OURS:
                    out['later_xp'][skill] = out['later_xp'].get(skill, 0) + amt
                else:
                    out['xp'][skill] = out['xp'].get(skill, 0) + amt
    return out


# ---------------------------------------------------------------- the comparison
def norm_skill(s):
    return {'runecrafting': 'runecraft'}.get(s, s)


def compare_one(key, name, c, w, ending):
    """[(what, ours, theirs)] for ONE of the quest's endings."""
    bad = []
    if ending is None:
        bad.append(('quest points', 'no ~send_quest_complete found', w['qp']))
        return bad
    if w['qp'] is not None and ending['qp'] != w['qp']:
        bad.append(('quest points', ending['qp'], w['qp']))

    ours = {norm_skill(k): v // 10 for k, v in ending['xp'].items()}
    other = {norm_skill(k): v // 10 for k, v in c['xp_elsewhere'].items()}
    theirs = {norm_skill(k): v for k, v in w['xp'].items()}
    for skill in sorted(set(ours) | set(theirs)):
        a, b = ours.get(skill), theirs.get(skill)
        if a == b:
            continue
        # the same number, paid somewhere else in the quest, is not a missing reward
        if a is None and other.get(skill) == b:
            continue
        note = '' if a is not None else (
            ' (%s elsewhere in the quest)' % other[skill] if skill in other else '')
        bad.append(('%s xp' % skill, (a if a is not None else '-'),
                    ('%s%s' % (b if b is not None else '-', note))))

    rs = {norm_skill(r['skill']): r['level'] for r in c['requirements'] if r['kind'] == 'skill'}
    ws = {norm_skill(k): v for k, v in w['reqs_skill'].items()}
    for skill in sorted(set(rs) | set(ws)):
        a, b = rs.get(skill), ws.get(skill)
        if a != b:
            bad.append(('%s required' % skill, a if a is not None else '-',
                        b if b is not None else '-'))

    # DOES THE QUEST GRANT WHAT ITS OWN SCROLL PROMISES? This needs no view about which era a
    # reward belongs to: the sixth argument to ~send_quest_complete is what the player reads on
    # the reward screen, and if it says 7,175 Fishing XP then 7,175 Fishing XP had better be
    # awarded. A disagreement here is a bug whichever way it is resolved.
    text = ending.get('reward_text') or ''
    promised = {}
    for m in re.finditer(r'([\d,]+)\s*([A-Za-z]+)\s*(?:XP|experience)', text, re.I):
        amt, skill = num(m.group(1)), norm_skill(m.group(2).lower())
        if amt is not None and skill in SKILLS:
            promised[skill] = promised.get(skill, 0) + amt
    for skill in sorted(set(promised) | set(ours)):
        a, b = ours.get(skill), promised.get(skill)
        if b is None or a == b:
            continue
        if a is None and other.get(skill) == b:
            continue
        bad.append(('%s xp SCROLL SAYS' % skill, a if a is not None else '-', b))

    cq = next((r['points'] for r in c['requirements'] if r['kind'] == 'qp'), None)
    if (cq or 0) != (w['reqs_qp'] or 0):
        bad.append(('quest points required', cq if cq is not None else '-',
                    w['reqs_qp'] if w['reqs_qp'] is not None else '-'))
    return bad


def compare(key, name, c, w):
    """The quest agrees if ANY of its endings does; otherwise the closest ending's differences."""
    if not c['endings']:
        return compare_one(key, name, c, w, None), None
    scored = [(compare_one(key, name, c, w, e), e) for e in c['endings']]
    scored.sort(key=lambda se: len(se[0]))
    return scored[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('only', nargs='*', help='questlist keys; default is all of them')
    ap.add_argument('-v', '--verbose', action='store_true', help='print every quest, not only the ones that differ')
    ap.add_argument('--json', help='write the whole comparison here')
    a = ap.parse_args()

    ql = questlist()
    keys = [k for k in ql if not a.only or k in a.only]
    if a.only:
        missing = set(a.only) - set(ql)
        if missing:
            print('not in the quest list: %s' % ', '.join(sorted(missing)))
    facts = content_facts(list(ql))

    report, differ = {}, 0
    for key in sorted(keys, key=lambda k: ql[k]):
        name = ql[key]
        try:
            w = wiki_facts(name)
        except Exception as e:
            print('%-30s could not be read from the wiki: %s' % (name, e))
            continue
        c = facts[key]
        bad, ending = compare(key, name, c, w)
        report[key] = {'name': name, 'wiki_page': w['page'], 'content': c, 'wiki': w,
                       'differences': bad}
        if bad:
            differ += 1
        if bad or a.verbose:
            print('\n%s  (%s)  %s' % (name, key, w['page']))
            if c['where']:
                print('    completes at %s' % c['where'])
            if len(c['endings']) > 1:
                print('    %d endings; the closest is shown' % len(c['endings']))
            for what, ours, theirs in bad:
                print('    %-24s ours %-18s wiki %s' % (what, ours, theirs))
            if ending and ending.get('comment'):
                print('    the code says: %s' % ending['comment'][:300])
            if a.verbose and not bad:
                print('    agrees')
    print('\n%d quests checked, %d differ from the wiki' % (len(keys), differ))
    if a.json:
        io.open(a.json, 'w', encoding='utf-8').write(json.dumps(report, indent=1))
        print('wrote %s' % a.json)
    return 1 if differ else 0


if __name__ == '__main__':
    sys.exit(main())
