"""Write quest_requirement.dbrow - what every quest needs before you can start it.

The requirements used to exist only as guard clauses scattered through whichever script starts the
quest. That is enough to stop a player, and no use for anything else: the quest journal could not
say what you were missing, tools/questaudit.py had to grep for `stat(x) <` and could not tell an
entry requirement from a gate halfway through, and the two could drift apart without either one
looking wrong.

So the requirements are declared once, here, and the journal and the audit both read them.

    python3 tools/genquestreq.py            rewrite the rows from the wiki
    python3 tools/genquestreq.py --check    fail if the file on disk is not what the wiki says

WHAT COMES FROM WHERE. The quest list and its display names come from
scripts/interfaces/questlist.if. The requirements come from the OSRS wiki's
{{Quest details|requirements=}}, which writes a skill as {{SCP|Mining|40}}, a quest point total as
{{SCP|Quest|32}} and a prerequisite quest as a [[link]]. A linked quest this build has is written
as its questlist component so the journal can name it the way the quest list does; a linked quest
it has not - a miniquest, or something never built - is kept as plain text, because telling a
player to finish something that does not exist here is worse than not mentioning it. Anything the
wiki says in prose is kept as prose.

AND THE ERA RULE APPLIES HERE TOO. A requirement Old School added to a pre-2006 quest long after
the fact is still a requirement that quest did not have in 2006. OVERRIDE below is where a quest
departs from the wiki on purpose, with the reason written next to it; nothing else may.
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import questaudit as Q  # noqa: E402

OUT = os.path.join(Q.SCRIPTS, 'quests', 'configs', 'quest_requirement.dbrow')

# key -> {'skills': {...}, 'qp': n, 'quests': [...], 'other': [...]} replacing the wiki's answer.
# A quest only appears here with a reason.
OVERRIDE = {}

# Wiki quest titles this build knows under a different name, so a prerequisite link resolves.
ALIAS = {
    'Fairy Tale I - Growing Pains': 'A Fairy Tale Pt. 1',
    'Fairy Tale II - Cure a Queen': 'A Fairy Tale Pt. 2',
    'Watchtower': 'Watch Tower',
    'Shilo Village (quest)': 'Shilo Village',
    'Elemental Workshop I': 'Elemental Workshop',
    "Mourning's End Part I": "Mourning's Ends Part 1",
    "Mourning's End Part II": "Mourning's Ends Part 2",
    'Rune Mysteries': 'Rune Mysteries Quest',
    'Dragon Slayer I': 'Dragon Slayer',
    'Desert Treasure I': 'Desert Treasure',
    "Legends' Quest": 'Legends Quest',
    'Heroes’ Quest': 'Heroes Quest',
    "Heroes' Quest": 'Heroes Quest',
}

# A line of prose that is not a requirement to START the quest.
PROSE_SKIP = re.compile(
    r'\b(recommended|able to defeat|ability to defeat|optional|highly recommended)\b', re.I)


def clean(s):
    """Wikitext to something a quest journal can print."""
    s = re.sub(r'\{\{SCP\|([A-Za-z ]+)\|([\d,]+)[^}]*\}\}', r'\2 \1', s)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]', r'\1', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' *:').strip()


def requirements(key, name, names_to_key):
    w = Q.wiki_facts(name)
    if key in OVERRIDE:
        got = dict(OVERRIDE[key])
        got.setdefault('skills', {})
        got.setdefault('quests', [])
        got.setdefault('other', [])
        got.setdefault('qp', 0)
        return got, w
    # COMBAT IS NOT A SKILL. The wiki writes a combat-level requirement as {{SCP|Combat|85}}, which
    # looks exactly like a skill requirement and is not one - there is no `combat` stat for the
    # build to pack, and `data=skills,combat,85` stops the build with "double-check the reference
    # exists". It becomes a line of prose, which is all the journal can do with it anyway.
    out = {'skills': {}, 'qp': w['reqs_qp'] or 0, 'quests': [], 'other': []}
    for skill, lvl in w['reqs_skill'].items():
        s = Q.norm_skill(skill)
        if s in Q.SKILLS:
            out['skills'][s] = lvl
        else:
            out['other'].append('%s level %d' % (skill.title(), lvl))
    raw = w['requirements_raw'] or ''
    for line in raw.split('\n'):
        stripped = line.strip()
        if not stripped.startswith('*'):
            continue
        # DIRECT REQUIREMENTS ONLY. The wiki nests a prerequisite's own prerequisites under it, so
        # Wanted! lists Recruitment Drive and then Black Knights' Fortress and Druidic Ritual
        # beneath it. Those are things you needed to finish Recruitment Drive; telling a player
        # who is looking at Wanted! that it requires six quests is true only in the sense that
        # everything requires Cook's Assistant. One star is a requirement, two is a quest in a
        # "complete the following" list, three and deeper is somebody else's requirement.
        depth = len(stripped) - len(stripped.lstrip('*'))
        if depth > 2:
            continue
        text = clean(stripped)
        if not text or PROSE_SKIP.search(text):
            continue
        links = re.findall(r'\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]', stripped)
        handled = False
        for link in links:
            title = ALIAS.get(link.strip(), link.strip())
            if title in names_to_key:
                k = names_to_key[title]
                if k != key and k not in out['quests']:
                    out['quests'].append(k)
                handled = True
        if handled:
            continue
        # A SKILL LINE IS ALREADY A SKILL. clean() turns {{SCP|Agility|20}} into "20 Agility", so
        # a line that is a skill requirement plus a sentence of explanation came out as
        # "20 Agility Entering the Mountain Camp initially requires 10 Agility." - the level is
        # already in the skills column and the rest is a footnote. Strip the part that is already
        # recorded and keep only what is left, if what is left says anything.
        m = re.match(r'^([\d,]+)\s+([A-Za-z]+)\b(.*)$', text)
        if m:
            lvl, skill, rest = Q.num(m.group(1)), m.group(2).lower(), m.group(3)
            if skill == 'quest':
                continue                       # the quest-point total, already a column
            if skill == 'combat':
                out['other'].append('Combat level %s' % lvl)
                continue
            if out['skills'].get(Q.norm_skill(skill)) == lvl:
                text = rest.strip(' .,-:')
            if not text or len(text.split()) < 3:
                continue
        if re.match(r'^Completion of the following quests?:?$', text, re.I):
            continue
        if text and len(text.split()) >= 2:
            out['other'].append(text)
    return out, w


def quoted(s):
    """A dbrow splits a data line on commas, so any string that contains one has to be quoted -
    "quote it or reword", as rs2check puts it. Quest names rarely need it; the prose requirement
    lines do, because the wiki writes things like "the elemental runic altars (Air, Fire, Water,
    Earth)". The quotes themselves cannot survive inside the value, so they become apostrophes.
    """
    s = s.replace('"', "'")
    return '"%s"' % s if (',' in s or '"' in s) else s


def render(ql, rows):
    L = []
    L.append('// GENERATED by tools/genquestreq.py from the OSRS wiki - do not hand-edit.')
    L.append('//   python3 tools/genquestreq.py')
    L.append('//')
    L.append('// WHAT A QUEST NEEDS BEFORE IT CAN BE STARTED. One row per quest, read by')
    L.append('// ~quest_requirements_text so the journal can print them and by the start gate so it')
    L.append('// can enforce them - the same row for both, which is the point. The table is in')
    L.append('// quest_requirement.dbtable.')
    for key in sorted(rows, key=lambda k: ql[k]):
        r = rows[key]
        L.append('')
        L.append('// %s' % ql[key])
        L.append('[quest_req_%s]' % key)
        L.append('table=quest_requirement')
        L.append('data=quest,questlist:%s' % key)
        L.append('data=name,%s' % quoted(ql[key]))
        if r['qp']:
            L.append('data=questpoints,%d' % r['qp'])
        for skill in sorted(r['skills']):
            L.append('data=skills,%s,%d' % (skill, r['skills'][skill]))
        for other in r['quests']:
            # the name travels with the component: a component carries no text a script can read
            # back, and the journal has to print the quest under the name the quest list draws
            L.append('data=quests,questlist:%s,%s' % (other, quoted(ql[other])))
        for line in r['other']:
            L.append('data=other,%s' % quoted(line))
    return '\n'.join(L) + '\n'


COMPLETE_OUT = os.path.join(Q.SCRIPTS, 'quests', 'scripts', 'quest_complete_generated.rs2')


def render_complete():
    """~quest_component_complete, from the table ~questlist_recolour already keeps.

    The journal needs to say whether a prerequisite quest is finished, and it has a component -
    which is all the dbrow can hold, since a varp cannot be named by data. quests.rs2 already
    writes down, once, which varp and which constant belong to each questlist component; this
    turns that same list into a lookup instead of a second copy maintained by hand.
    """
    text = Q.read(os.path.join(Q.SCRIPTS, 'general', 'scripts', 'quests.rs2'))
    seen = {}
    # The progress and the completion value are whole EXPRESSIONS, not always a varp and a
    # constant: Clock Tower passes ~get_cog_progress, Elemental Workshop compares against
    # sub(pow(2, ^elemental_workshop_complete), 1). Matching only %varp quietly dropped four
    # quests, and a prerequisite pointing at a dropped one would have been red for ever.
    for m in re.finditer(r'~questlist_row\(\s*questlist:(\w+)\s*,\s*(.+?)\s*,\s*(.+?)\s*,\s*\$send\s*\)',
                         text):
        seen[m.group(1)] = (m.group(2), m.group(3))   # last one wins: Shield of Arrav's else branch
    L = ['// GENERATED by tools/genquestreq.py from ~questlist_recolour in',
         '// general/scripts/quests.rs2 - do not hand-edit.',
         '//   python3 tools/genquestreq.py',
         '//',
         '// IS THIS QUEST FINISHED, given only its quest list component? The quest journal needs',
         '// to colour a prerequisite green or red and all it has is the component, because that is',
         '// the only thing quest_requirement.dbrow can hold - data cannot name a varp. Rather than',
         '// keep a second list of varps by hand, this is built from the one ~questlist_recolour',
         '// already has, so a quest cannot be in one and missing from the other.',
         '[proc,quest_component_complete](component $quest)(boolean)',
         'switch_component ($quest) {']
    for key in sorted(seen):
        varp, const = seen[key]
        L.append('    case questlist:%s :' % key)
        L.append('        if (%s >= %s) {' % (varp, const))
        L.append('            return(true);')
        L.append('        }')
    L.append('}')
    L.append('return(false);')
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()

    ql = Q.questlist()
    names_to_key = {}
    for k, n in ql.items():
        names_to_key[n] = k
        names_to_key.setdefault(Q.WIKI_TITLE.get(n, n), k)
    rows, skipped = {}, []
    for key, name in sorted(ql.items(), key=lambda kv: kv[1]):
        try:
            rows[key], _w = requirements(key, name, names_to_key)
        except Exception as e:
            skipped.append('%s (%s)' % (name, e))
    text = render(ql, rows)
    comp = render_complete()
    if a.check:
        for path, want in ((OUT, text), (COMPLETE_OUT, comp)):
            have = Q.read(path) if os.path.exists(path) else ''
            if have.replace('\r\n', '\n') != want:
                print('%s is out of date - run tools/genquestreq.py'
                      % os.path.relpath(path, Q.CONTENT))
                return 1
        print('the generated quest requirement files are current')
        return 0
    io.open(COMPLETE_OUT, 'w', encoding='utf-8', newline='\n').write(comp)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(text)
    print('wrote %s - %d quests' % (os.path.relpath(OUT, Q.CONTENT), len(rows)))
    for s in skipped:
        print('  skipped: %s' % s)
    withreq = sum(1 for r in rows.values() if r['skills'] or r['qp'] or r['quests'] or r['other'])
    print('  %d have at least one requirement, %d have none' % (withreq, len(rows) - withreq))
    return 0


if __name__ == '__main__':
    sys.exit(main())
