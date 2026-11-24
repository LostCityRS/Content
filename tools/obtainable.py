#!/usr/bin/env python3
"""Every obj in pack/obj.pack that nothing in the game can give you.

The bug this is for has bitten four times now: the black mask and the dragon pickaxe were built and
had no source for days, and six formal-garden flowers were buildable out of a bagged flower that no
shop sold. Battery group 63 catches it for Construction materials. This is the whole obj table.

AN OBJ IS OBTAINABLE if any of these names it:

  a shop          stockN= in any .inv
  a script        inv_add / inv_addall / inv_changeslot / npc_giveitem / obj_add / obj_addall /
                  inv_moveitem's destination, anywhere in scripts/
  the ground      an OBJ line in any maps/*.jm2
  a note          certlink= from an obtainable obj, or certtemplate (a note is its base item)
  a multiloc-ish  an obj built out of another by a recipe the script names (covered by the script
                  rule above - this is not a separate case, just a reminder that inv_add is it)

ONE THING IS DELIBERATELY UNOBTAINABLE and says so: twelve of the fourteen slayer helmet colours
exist only to be looked at with ::give, because the monsters that drop their heads are not in this
era. They are read out of tools/slayerhelmspec.json - the colours with no "source" block - and
printed in their own section rather than being filtered out, so the list stays honest and so the
day black gets a source, this tool notices the spec disagrees with the game.

Everything else is reported, grouped, so the interesting ones can be told from the noise. MOST OF
THE OUTPUT IS NOISE and that is expected: a 377 cache carries thousands of objs this server has no
content for. What matters is the objs THIS REPO went to the trouble of defining - the ones in
scripts/**/configs/*.obj rather than scripts/_unpack - because somebody meant those to exist.

    python3 tools/obtainable.py              # the summary and the repo-defined orphans
    python3 tools/obtainable.py --all        # every orphan, including the cache's own
"""
import os, re, sys, io, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return io.open(os.path.join(ROOT, p), encoding='utf-8', errors='replace', newline='').read()


# A STORAGE table is not a source, and it is not a mention either. poh_store_item and
# poh_costume_item list what the costume room will PUT AWAY for you, which says nothing about
# whether you can get one. Reading them as sources once hid a carpenter's shirt that no shop sold
# behind a fancy dress box that would happily store it - and excluding them from `given` alone was
# not enough: they still counted as a MENTION, which demotes an obj from "nothing anywhere mentions
# these" to "worth a glance, not a bug list". That quietly hid seventeen more, including two
# Graceful pieces, the mime set, the lederhosen, the frog mask and the zombie set.
# A table that LISTS objs is not a table that GIVES them. Each of these names objs for a reason that
# tells you nothing about whether a player can get one, and reading them as sources hides exactly the
# items this tool exists to find:
#   poh_store_item / poh_costume_item  what the costume room will put away for you. This one hid a
#                                      carpenter's shirt that no shop sells behind a box that stores it.
#   collection_log_items               the collection log's display order. collection_log.rs2 reads it
#                                      to draw the window and to count what the player's own
#                                      collection_log inv already holds; it hands out nothing, so
#                                      every item in the log "had a source" - which is to say the log
#                                      was reporting itself as the way to get them.
#   macro_pillory_symbol               the fifteen colour-and-shape cubes stamped on the pillory
#                                      cage's tumblers. macro_event_pillory.rs2 passes them to an
#                                      interface to be DRAWN; nobody is ever handed one, and
#                                      nosourcespec.json has said so in as many words for as long as
#                                      the cubes have been in the tree.
#   macro_quiz_item                    the quiz master's twelve answer pictures. macro_event_quiz.rs2
#                                      picks three of them per question and hands them to ~multiobj3
#                                      to be drawn as the choices. The prize is the mystery box; not
#                                      one of the pictures is ever handed over.
#   macro_digger_goods                 the sixteen grave goods. macro_event_gravedigger.rs2 reads
#                                      them into macro_digger_coffin_inv, which is transmitted to
#                                      the coffin interface and cleared - see DISPLAY_INVS below.
#                                      The event's reward is the costume, in macro_digger_reward_obj,
#                                      which IS a source and is read as one.
#   macro_digger_symbol                the five "Its a symbol" stones. ~macro_digger_stone_show
#                                      puts one on an interface so the player can read it off; the
#                                      stone itself never leaves the script.
#
# Note the granularity: these are enum BLOCK names, not file names, and macro_events_gravedigger.enum
# is why. One file holds both macro_digger_goods, which gives out nothing, and
# macro_digger_reward_obj, which is the only way to get the gravedigger costume. Excluding by file
# would have hidden the costume; excluding by block keeps it.
STORAGE_LISTS = ('poh_store_item', 'poh_costume_item', 'collection_log_items', 'macro_pillory_symbol',
                 'macro_quiz_item', 'macro_digger_goods', 'macro_digger_symbol')

# A DISPLAY INV is not a source either, for the same reason a storage list is not: the obj goes in
# and the player cannot take it out again. inv_add names it, so without this the inv_add rule below
# reports the obj as obtainable.
#   collection_log                     the tally behind the collection log window. collection_log.rs2
#                                      adds to it and reads inv_total off it to colour a row in;
#                                      nothing deletes from it or moves anything out of it, ever.
#                                      Reading it as a source means the log reports itself as the way
#                                      to get everything it lists.
#   macro_digger_coffin_inv            the coffin's contents on the gravedigger puzzle's interface.
#                                      Only inv_clear, inv_add and inv_transmit touch it. This is the
#                                      skull and the pile of bones: nothing else in the game names
#                                      them, so the puzzle's own scenery was their only "source".
DISPLAY_INVS = ('collection_log', 'macro_digger_coffin_inv')

# The same thing in dbrow form: collection_log.dbrow is generated from collectionlogspec.json and is
# the pages of the log, nothing more.
LISTING_DBROWS = ('collection_log.dbrow',)


def without_storage_lists(text):
    """The file with any STORAGE_LISTS enum block removed, for the loose mention scan."""
    out, skip = [], False
    for line in text.split('\n'):
        s = line.split('//')[0].strip()
        if s.startswith('[') and s.endswith(']'):
            skip = s[1:-1] in STORAGE_LISTS
        if not skip:
            out.append(line)
    return '\n'.join(out)


def packnames(p):
    out = {}
    for l in read(p).split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[int(i)] = n.strip()
    return out


def configs(pattern):
    """[name] -> {key: value} across every matching config, with the file it came from."""
    out, where = {}, {}
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith(pattern):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            cur = None
            for l in read(rel).split('\n'):
                l = l.split('//')[0].strip()
                if l.startswith('[') and l.endswith(']'):
                    cur = l[1:-1]
                    out.setdefault(cur, {})
                    where.setdefault(cur, rel)
                elif cur and '=' in l:
                    k, v = l.split('=', 1)
                    out[cur].setdefault(k, v)
    return out, where


def enclosing(text, pos):
    """The [script,header] an offset sits under, so a source can be named finer than its file.

    obtainable.py's own report stays file-level, because that is the useful grain for a human
    reading it. This is for tools/nosourcespec.json's "ignore": the bottomless compost bucket adds
    its own two items to make the icon follow the contents, which is a swap and not a source, and
    a whole-file exemption there would also excuse a REAL source added to that file later.
    """
    last = ''
    for m in re.finditer(r'^\[([^\]\n]+)\]', text[:pos], re.M):
        last = m.group(1)
    return last


def apply_ignores(given, detail):
    """Take the adds that are swaps rather than sources out of `given`, per nosourcespec.json.

    The bottomless compost bucket swaps its own empty item for its own filled one so the icon
    follows the contents. Both halves of that swap are an inv_add, and reading them as sources
    would mean the tool insisted the bucket is obtainable while nothing in the game hands one out.
    So the spec names the script they live in and they stop counting - for the whole report, not
    just for the by-design section, because a false source is a false source everywhere.

    A source is only dropped when EVERY add it covers is named, so a REAL source added to an
    already-named file still counts and is still reported as a disagreement with the spec.

    Two places say this: an "ignore" inside an objs entry, for an obj with no source at all, and
    the top-level "not_a_source", for an obj that HAS one. The bucket and the Thread of Elidinis
    moved from the first to the second the day they were given real sources, and the reason the
    second exists is that without it their swap and their refund would have become the source.
    """
    path = os.path.join(ROOT, 'tools', 'nosourcespec.json')
    if not os.path.exists(path):
        return
    spec = json.loads(read('tools/nosourcespec.json'))
    # An obj that HAS a source can still be added by something that is not one - a swap, a refund.
    # Those live in their own section, because the per-obj "ignore" below only travels with a
    # sourceless obj and both of the current ones stopped being sourceless. Without this, a
    # refund quietly becomes the source and deleting the real one goes unnoticed.
    pairs = [(obj, set(tags)) for obj, tags in spec.get('not_a_source', {}).items()]
    pairs += [(obj, set(d.get('ignore', [])))
              for nm, d in spec['objs'].items() if d.get('ignore')
              for obj in [nm] + d.get('also', [])]
    for obj, ignore in pairs:
        if not ignore:
            continue
        for src in sorted(given.get(obj, ())):
            tags = {x for x in detail.get(obj, ()) if x.split(':', 1)[0] == src}
            if tags and tags <= ignore:
                given[obj].discard(src)
        if obj in given and not given[obj]:
            del given[obj]


def byexception(given):
    """The objs this repo built on purpose with nothing to give them out.

    Read from tools/slayerhelmspec.json rather than listed here, so a colour added to the spec is
    covered without touching this file and - more to the point - so a colour that GAINS a source
    cannot sit in an exception list forever. If the game can give you one, that is reported as a
    disagreement instead of quietly excusing it.
    """
    names, wrong = set(), []

    # ---- the pets whose skill this server does not have yet, out of tools/petspec.json. A pet
    # marked wired=false there has nothing that can give you one; if something does, that is a
    # disagreement to report rather than an exception to keep.
    pet_path = os.path.join(ROOT, 'tools', 'petspec.json')
    if os.path.exists(pet_path):
        pets = json.loads(read('tools/petspec.json'))
        for nm, d in pets['skill'].items():
            item = nm + '_item'
            if d.get('wired'):
                continue
            if item in given:
                wrong.append('%s is wired=false in petspec.json, but something in the game gives '
                             'you one - update the spec' % item)
            else:
                names.add(item)

    # ---- the one-offs, out of tools/nosourcespec.json
    one_path = os.path.join(ROOT, 'tools', 'nosourcespec.json')
    if os.path.exists(one_path):
        for nm, d in json.loads(read('tools/nosourcespec.json'))['objs'].items():
            for obj in [nm] + d.get('also', []):
                if obj in given:
                    wrong.append('%s is listed in nosourcespec.json, but %s gives you one - '
                                 'update the spec' % (obj, ', '.join(sorted(given[obj]))))
                else:
                    names.add(obj)

    spec_path = os.path.join(ROOT, 'tools', 'slayerhelmspec.json')
    if not os.path.exists(spec_path):
        return names, wrong
    spec = json.loads(read('tools/slayerhelmspec.json'))
    for c in spec['colours']:
        pair = ('slayer_helm_%s' % c['key'], 'slayer_helm_%s_i' % c['key'])
        if 'source' in c:
            continue
        for nm in pair:
            if nm in given:
                wrong.append('%s has no "source" in slayerhelmspec.json, but something in the game '
                             'gives you one - update the spec' % nm)
            else:
                names.add(nm)
    return names, wrong


def main():
    objs = packnames('pack/obj.pack')
    byname = {v: k for k, v in objs.items()}
    cfg, where = configs('.obj')

    given = collections.defaultdict(set)
    # obj -> {'file.rs2:script,header'}, the same adds at a finer grain. Only nosourcespec.json's
    # "ignore" reads it; the report itself stays file-level.
    detail = collections.defaultdict(set)

    # ---- shops
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.inv'):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            for m in re.finditer(r'^stock\d+=(\w+),', read(rel), re.M):
                given[m.group(1)].add('shop:' + fn)

    # ---- scripts. inv_moveitem's DESTINATION is its second argument, so it is read separately.
    #
    # ~macro_event_give_obj is in here with the engine commands because it is one: every random
    # event pays out through it rather than calling inv_add itself, so without it the detector
    # cannot see a single random event reward. That is how the Kiss the Frog set - the token, the
    # mask and the four prince and princess pieces - stayed in nosourcespec.json for as long as it
    # took somebody to read the event, which is implemented and hands out all six. If another
    # give-wrapper of this shape turns up, it belongs on this list too; the test is that the proc's
    # whole job is to put its obj argument in the player's inv.
    ADD = re.compile(r'(?<![a-z0-9_])[.~]?'
                     r'(?:inv_add|inv_addall|inv_changeslot|npc_giveitem|obj_add|obj_addall'
                     r'|macro_event_give_obj)'
                     r'\(([^;]*?)\)\s*;', re.S)
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.rs2'):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            if rel == 'scripts/engine.rs2':
                continue
            t = read(rel)
            for m in ADD.finditer(t):
                # inv_add's first argument is the inv being written to. A write into a display inv
                # (see DISPLAY_INVS) is not a source - the obj goes in and never comes back out.
                if m.group(1).split(',')[0].strip() in DISPLAY_INVS:
                    continue
                for w in re.findall(r'([a-z][a-z0-9_+]{2,})', m.group(1)):
                    if w in byname:
                        given[w].add(fn)
                        detail[w].add('%s:%s' % (fn, enclosing(t, m.start())))
            for m in re.finditer(r'\binv_moveitem\(\s*\w+\s*,\s*\w+\s*,\s*(\w+)', t):
                if m.group(1) in byname:
                    given[m.group(1)].add(fn)

    # ---- the ground
    #
    # THIS RULE NEVER FIRED ONCE until 23 November 2026, and it is the one that most needed to.
    # read() keeps each file's own newlines, every .jm2 is CRLF, and `l.strip('= ')` strips only '='
    # and ' ' - so "==== OBJ ====\r" became "OBJ ====\r", never equalled 'OBJ', and the section was
    # skipped in every map in the game. 258 objs have a ground spawn and the audit called all of
    # them sourceless.
    #
    # It cost a wrong answer out loud: the Golem quest's letter was reported as unobtainable and
    # the quest as possibly unfinishable, when the letter lies in the sand at Uzer (m54_48.jm2,
    # local 23,20 - which is exactly where tools/sim/quest_golem_run.ts picks it up). Strip the
    # line, not just the padding.
    mapdir = os.path.join(ROOT, 'maps')
    for fn in sorted(os.listdir(mapdir)):
        if not fn.endswith('.jm2'):
            continue
        sec = None
        for l in read('maps/' + fn).split('\n'):
            l = l.strip()
            if l.startswith('===='):
                sec = l.strip('= ').strip(); continue
            if sec != 'OBJ' or ':' not in l:
                continue
            for p in l.split(':', 1)[1].split():
                if p.isdigit() and int(p) in objs:
                    given[objs[int(p)]].add('map:' + fn)
                    break

    # ---- a drop rolled through a variable. The god wars tables build $drop up a branch at a time
    # and add it once at the end, so the obj name is nowhere near the obj_add.
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.rs2') or fn == 'engine.rs2':
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            t = read(rel)
            if not re.search(r'\b(?:obj_add|inv_add|npc_giveitem)\(', t):
                continue
            for m in re.finditer(r'^\s*(?:def_(?:namedobj|obj)\s+)?\$\w+\s*=\s*(\w+)\s*;\s*$',
                                 t, re.M):
                if m.group(1) in byname:
                    given[m.group(1)].add(fn)

    # ---- an npc's own death drop, and any other obj a config param names
    npccfg, _ = configs('.npc')
    for name, d in npccfg.items():
        for k, v in d.items():
            pass
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.npc'):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            for m in re.finditer(r'^param=(?:death_drop|\w*drop\w*),(\w+)$', read(rel), re.M):
                if m.group(1) in byname:
                    given[m.group(1)].add('death drop:' + fn)

    # ---- a table of objs something reads: an enum whose output is an obj, or a dbrow column
    for suffix in ('.enum', '.dbrow'):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
            for fn in files:
                if not fn.endswith(suffix):
                    continue
                rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
                cur, isobj = None, False
                for l in read(rel).split('\n'):
                    l = l.split('//')[0].strip()
                    if l.startswith('['):
                        cur, isobj = l[1:-1], False
                    elif l.startswith('outputtype=') and l.split('=', 1)[1] in ('obj', 'namedobj'):
                        isobj = True
                    elif isobj and l.startswith('val='):
                        v = l.split(',', 1)[-1].strip()
                        # A STORAGE table is not a source. poh_store_item and poh_costume_item list
                        # what the costume room will PUT AWAY for you, which tells you nothing about
                        # whether you can get one - and reading them as sources hid a carpenter's
                        # shirt that no shop sells behind a fancy dress box that would store it.
                        if v in byname and cur not in STORAGE_LISTS:
                            given[v].add('table:' + fn)
                    elif suffix == '.dbrow' and '=' in l and fn not in LISTING_DBROWS:
                        for w in re.findall(r'([a-z][a-z0-9_+]{2,})', l.split('=', 1)[1]):
                            if w in byname:
                                given[w].add('dbrow:' + fn)

    # ---- a chain of charges. A slayer ring (8) is bought with points and rubbed down to (1) one
    # charge at a time, and each step is oc_param($ring, slayer_ring_next) - the next obj is named
    # by the CONFIG, not by the script. Same shape as a degrading item. So: an obj param that names
    # another obj passes obtainability along it, repeatedly until nothing new appears.
    chain = collections.defaultdict(set)
    for name, d in cfg.items():
        for k, v in d.items():
            if k != 'param':
                continue
        for l in (d.get('_params') or []):
            pass
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.obj'):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            cur = None
            for l in read(rel).split('\n'):
                l = l.split('//')[0].strip()
                if l.startswith('[') and l.endswith(']'):
                    cur = l[1:-1]
                elif cur and l.startswith('param=') and ',' in l:
                    v = l.split(',', 1)[1].strip()
                    if v in byname and v != cur:
                        chain[cur].add(v)
    moved = True
    while moved:
        moved = False
        for src, dsts in chain.items():
            if src not in given:
                continue
            for d in dsts:
                if d not in given:
                    given[d].add('param of ' + src)
                    moved = True

    # ---- notes. A note is its base item; if you can get the item you can get the note.
    for name, d in cfg.items():
        base = d.get('certlink')
        if base and base in given:
            given[name].add('note of ' + base)

    # ---- stack forms. countN=<obj>,<n> on a stackable obj names the model the CLIENT swaps in at
    # that size; nothing ever hands one out and nothing ever will, so they read as orphans while
    # being exactly as reachable as the base. The cache's own (coins_2, coins_3 ...) never showed up
    # here only because they live in scripts/_unpack, which this does not audit - so the rule was
    # missing rather than unnecessary, and the first stack item defined in the repo found that out.
    for name, d in cfg.items():
        if name not in given:
            continue
        for k, v in d.items():
            if re.fullmatch(r'count\d+', k):
                form = v.split(',')[0].strip()
                if form in byname:
                    given[form].add('stack form of ' + name)

    # ---- a result handed to a label or a proc, minus the storage lists (see STORAGE_LISTS). The
    # godswords are joined by
    # @godsword_join($a, $b, godsword_blade) - the obj that comes OUT is an argument, nowhere near
    # an inv_add - and following that properly means following every call. So instead: in a file
    # that gives items out at all, a bare mention of an obj name counts as "reachable, probably".
    # That is deliberately loose. It is the difference between the two lists below.
    loose = collections.defaultdict(set)
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            # .seq is in here because the skillcape emotes name their held props there and
            # nowhere else - a prop is not an item you can get, and should not read as one.
            if not fn.endswith(('.rs2', '.enum', '.dbrow', '.inv', '.npc',
                                '.param', '.seq', '.spotanim', '.struct')):
                continue
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:]
            if fn == 'engine.rs2':
                continue
            for w in set(re.findall(r'([a-z][a-z0-9_+]{2,})', without_storage_lists(read(rel)))):
                if w in byname:
                    loose[w].add(fn)

    # ---- the adds that are swaps and not sources, out of the spec, before anything reads `given`
    apply_ignores(given, detail)

    # ---- and what is left
    TEMPLATE = re.compile(r'template|^cert_|_cert$|^unused|^null')
    orphan = []
    for i, name in sorted(objs.items()):
        if name in given:
            continue
        d = cfg.get(name, {})
        if TEMPLATE.search(name) or d.get('certtemplate'):
            continue
        src = where.get(name, '')
        orphan.append((i, name, (d.get('name') or '?'), src))

    repo = [o for o in orphan if o[3] and '_unpack' not in o[3]]
    cache = [o for o in orphan if not o[3] or '_unpack' in o[3]]
    # Deliberately sourceless, declared in a spec rather than in a list here, so it cannot drift
    # away from what the generator actually built.
    bydesign, mismatch = byexception(given)
    onpurpose = [o for o in repo if o[1] in bydesign]
    repo = [o for o in repo if o[1] not in bydesign]
    hard = [o for o in repo if o[1] not in loose]
    soft = [o for o in repo if o[1] in loose]
    print('%d objs in obj.pack; %d have a source; %d do not' % (len(objs), len(given), len(orphan)))
    print('  %d of those are defined by a config in this repo' % len(repo))
    print('  %d are the 377 cache\'s own, which this server has no content for' % len(cache))
    print()
    if onpurpose or mismatch:
        print('==== BUILT WITH NO SOURCE ON PURPOSE (%d) ====' % len(onpurpose))
        print('Declared on purpose, out of three specs: slayer helmet colours with no "source"')
        print('block in slayerhelmspec.json, pets marked wired=false in petspec.json whose skill')
        print('or hook is not built yet, and the one-offs in nosourcespec.json. They exist so they')
        print('can be looked at with ::give. Not a bug list - but not hidden either.')
        print()
        for i, name, disp, src in sorted(onpurpose):
            print('    %5d  %-38s %s' % (i, name, disp))
        for m in mismatch:
            print('    WARNING: %s' % m)
        print()
    print('==== NOTHING ANYWHERE MENTIONS THESE (%d) ====' % len(hard))
    print('No script, table, shop, map or param names them. Nothing can give you one and nothing')
    print('can use one. These are the real ones.')
    print()
    byfile = collections.defaultdict(list)
    for i, name, disp, src in hard:
        byfile[src].append((i, name, disp))
    for src in sorted(byfile):
        print('%s  (%d)' % (src, len(byfile[src])))
        for i, name, disp in byfile[src]:
            print('    %5d  %-38s %s' % (i, name, disp))
        print()
    print('==== MENTIONED, BUT NEVER GIVEN OUT (%d) ====' % len(soft))
    print('Something names these, so they are probably reachable through a label argument or a')
    print('call this cannot follow - the godswords are joined by @godsword_join(.., .., <result>).')
    print('Worth a glance, not a bug list.')
    print()
    if '--soft' in sys.argv:
        byfile = collections.defaultdict(list)
        for i, name, disp, src in soft:
            byfile[src].append((i, name, disp, sorted(loose[name])[:3]))
        for src in sorted(byfile):
            print('%s  (%d)' % (src, len(byfile[src])))
            for i, name, disp, w in byfile[src]:
                print('    %5d  %-36s %-26s %s' % (i, name, disp, ', '.join(w)))
            print()
    if '--all' in sys.argv:
        print('---- the cache\'s own, for completeness ----')
        for i, name, disp, _ in cache:
            print('    %5d  %-38s %s' % (i, name, disp))


if __name__ == '__main__':
    # This prints hundreds of lines and is meant to be read through `| head` or `| grep`, which
    # closes the pipe and makes the next print raise. A SIGPIPE traceback once aborted a 474 import
    # half way through with nothing written; it is worth two lines to never see it again.
    try:
        main()
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        os._exit(0)
