"""Battery for the rune pouch.

The feature is not "an item that holds runes" - it is "every spell in the game now looks in two
places". So most of what is checked here is the NEGATIVE: that no rune read and no rune spend
anywhere in the magic path still looks only in the inventory. One missed site is a spell that says
you have no runes while the pouch is full.

    python3 tools/pouch_battery.py
"""
import json, os, re, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

MAGIC = read('scripts/skill_magic/scripts/magic.rs2')
POUCH = read('scripts/storage_items/scripts/rune_pouch.rs2')
STORAGE = read('scripts/storage_items/scripts/storage_items.rs2')
OBJ = read('scripts/storage_items/configs/rune_pouch.obj')
INV = read('scripts/storage_items/configs/storage_items.inv')
CONST = read('scripts/storage_items/configs/rune_pouch.constant')
ENUM = read('scripts/storage_items/configs/rune_pouch.enum')
ALCH = read('scripts/skill_magic/scripts/spells/alchemy.rs2')
UI = read('scripts/storage_items/scripts/rune_pouch_ui.rs2')
LOGIN = read('scripts/login_logout/scripts/login.rs2')
MAINIF = read('scripts/storage_items/interfaces/rune_pouch_main.if')
SIDEIF = read('scripts/storage_items/interfaces/rune_pouch_side.if')
MIRRORIF = read('scripts/storage_items/interfaces/rune_pouch_mirror.if')
IFPACK = read('pack/interface.pack')
LEATHER = read('scripts/skill_crafting/scripts/leather/leather.rs2')
DEATH = read('scripts/player/scripts/death.rs2')

def const(n):
    m = re.search(r'\^' + n + r'\s*=\s*(\d+)', CONST)
    return int(m.group(1)) if m else None

def block(txt, name):
    return txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in txt else ''

def objblock(name):
    b = block(OBJ, name)
    return dict(l.split('=', 1) for l in b.split('\n') if '=' in l and not l.startswith('//'))

# ============================================================================ 1
print('1. one store, and the item in your hand decides how much of it you can reach')
iv = block(INV, 'rune_pouch_store')
check('size=4' in iv, 'the store has four slots')
check('scope=perm' in iv, 'and survives a logout')
check('stackall=yes' in iv, 'and stacks, so 16,000 of a rune is one slot')
plain, divine = objblock('rune_pouch'), objblock('divine_rune_pouch')
check(plain.get('param') == 'pouch_slots,3', 'the rune pouch reaches three of them')
check(divine.get('param') == 'pouch_slots,4', 'the divine one reaches four')
check('[proc,rune_pouch_slots]' in POUCH and 'oc_param($pouch, pouch_slots)' in POUCH,
      'and one proc reads that number rather than each caller knowing it')
slots = block(POUCH, 'proc,rune_pouch_slots')
check('return(0);' in slots, 'carrying no pouch answers 0')
kinds = code(block(POUCH, 'proc,rune_pouch_kinds_used'))
check('inv_size(rune_pouch_store)' in kinds, 'kinds-used walks the whole store...')
fill = code(block(POUCH, 'proc,rune_pouch_fill'))
check('~rune_pouch_kinds_used < $slots' in fill,
      '...and Fill compares it against what the pouch can reach, which is what stops the plain '
      'pouch touching the fourth slot')
check('$inside > 0 |' in fill, 'a rune already inside tops up without needing a slot')
check('^rune_pouch_max_per_rune - $inside' in fill, 'and the cap is per kind, not per pouch')
check(const('rune_pouch_max_per_rune') == 16000, 'that cap is OSRS\'s 16,000')

# ============================================================================ 2
print('2. NOTHING in the magic path still looks only in the inventory')
mc = code(MAGIC)
# the only inv_total/inv_del of a rune allowed in magic.rs2 are the ones INSIDE the two new procs
for proc in ('proc,rune_total', 'proc,rune_del'):
    check('[' + proc + ']' in MAGIC, '~%s exists' % proc.split(',')[1])
inside = code(block(MAGIC, 'proc,rune_total')) + code(block(MAGIC, 'proc,rune_del'))
outside = mc
for b in ('proc,rune_total', 'proc,rune_del'):
    outside = outside.replace(code(block(MAGIC, b)), '')
stray = re.findall(r'inv_(?:total|del)\((?:inv|rune_pouch_store), [^)]*', outside)
check(not stray, 'no rune is read or spent straight from the inventory outside those two: %s'
      % (stray or 'none'))
# The four checks go through ~spell_rune_enough, which counts an element's combination runes as
# well (~element_rune_total) - and every count in there is a ~rune_total, never the pack alone.
#
# TWO PROCS ASK THE QUESTION, not one, and counting the calls across the whole file instead of per
# proc is why this check failed for as long as that was true. ~check_spell_requirements is the one
# that tells the player what is missing; ~spell_requirements_met is the same test without the
# messages, for a spell the game picks on the player's behalf - the twinflame staff's weakness
# autocast, where a failure means "cast the one they chose" rather than "say you have no runes".
# Both have to go through ~spell_rune_enough or the silent one answers out of the inventory alone.
for proc in ('proc,check_spell_requirements', 'proc,spell_requirements_met'):
    asked = re.findall(r'~spell_rune_enough\(\$rune(\d)', code(block(MAGIC, proc)))
    check(asked == ['1', '2', '3', '4'],
          'all four rune checks in ~%s go through ~spell_rune_enough...' % proc.split(',')[1])
ert = code(block(MAGIC, 'proc,element_rune_total'))
check(ert.count('~rune_total(') == 17,
      '...which counts through ~rune_total: 4 kinds for each element, and the rune itself otherwise')
# The spends: the four elements and six combination runes together, from ~spell_element_bill,
# and every other rune one at a time - all through ~rune_del.
dsr = code(block(MAGIC, 'proc,delete_spell_runes'))
check(len(re.findall(r'~rune_del\(\$rune\d', dsr)) == 4,
      'and all four non-elemental spends through ~rune_del...')
check(all('~rune_del(%srune, $%s)' % (r, r) in dsr for r in
          ('air', 'water', 'earth', 'fire', 'mist', 'dust', 'mud', 'smoke', 'steam', 'lava')),
      '...as are the elements and combination runes the bill comes to')
# and the same for the one place outside magic.rs2 that counted runes for a spell
check('~spell_rune_spend($spell_data, $item)' in code(ALCH),
      'alching a rune asks the cast what it will take, the same way the cast pays')
check(not re.findall(r'inv_total\(inv, (nature|fire)rune\)', code(ALCH)),
      '...and no longer counts the pack alone')

# ============================================================================ 3
print('3. with no pouch, the two procs are exactly what the file did before')
rt = code(block(MAGIC, 'proc,rune_total'))
check('if (~rune_pouch_slots = 0) {' in rt and 'return(inv_total(inv, $rune));' in rt,
      '~rune_total short-circuits to the old expression when no pouch is carried')
check('$rune = null' in rt, 'and a null rune is 0 rather than a lookup')
rd = code(block(MAGIC, 'proc,rune_del'))
check('min(inv_total(inv, $rune), $count)' in rd, '~rune_del takes what it can from the pack...')
check(rd.index('inv_del(inv, $rune, $loose)') < rd.index('inv_del(rune_pouch_store, $rune, $rest)'),
      '...before it touches the pouch, which is the conservative order')
check('$count - $loose' in rd, 'and the pouch covers exactly the shortfall')
check('$rune = null | $count < 1' in rd, 'nothing is spent for a null rune or a zero cost')

# ============================================================================ 4
print('4. the pouch holds every rune a spell in this repo can ask for')
allowed = re.findall(r'^val=\d+,(\w+)$', block(ENUM, 'rune_pouch_runes'), re.M)
check(len(allowed) == const('rune_pouch_kinds'),
      'the enum has as many kinds as the constant claims: %d and %d'
      % (len(allowed), const('rune_pouch_kinds')))
check(len(set(allowed)) == len(allowed), 'and no rune twice')
needed = set()
for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
    for fn in files:
        if not fn.endswith('.dbrow'): continue
        t = read(os.path.join(dirpath, fn)[len(C) + 1:])
        if 'magic_spell_table' not in t and 'magic_combat' not in t: continue
        for m in re.findall(r'data=(?:runesrequired|rune4),([\w,]+)', t):
            needed |= {x for x in m.split(',') if not x.isdigit() and x != 'null'}
missing = sorted(needed - set(allowed))
check(not missing, 'every rune a spell needs is one the pouch holds: %s'
      % (missing or '%d runes over %d spells' % (len(needed), len(allowed))))
objp = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/obj.pack').split('\n') if '=' in l)}
bad = [r for r in allowed if r not in objp]
check(not bad, 'and each is a real obj: %s' % (bad or 'all %d' % len(allowed)))
check('blankrune' not in allowed, 'rune essence is not a rune and does not go in, as in OSRS')

# ============================================================================ 5
print('5. Fill, Empty, Check and Destroy, on the helpers the other three storage items use')
# Check is the exception: it opens the window (group 8) rather than reading the contents out down
# the chatbox, so its trigger lives in rune_pouch_ui.rs2 and it reuses no storage helper.
for op, what, where in (('opheld1', 'Fill', POUCH), ('opheld2', 'Empty', POUCH),
                        ('opheld3', 'Check', UI), ('opheld5', 'Destroy', POUCH)):
    for item in ('rune_pouch', 'divine_rune_pouch'):
        check('[%s,%s]' % (op, item) in where, '%s has %s' % (item, what))
        check(objblock(item).get(op.replace('opheld', 'iop')) == what,
              '...and the obj advertises it')
for helper, what in (('~storage_empty_to_inv(rune_pouch_store', 'Empty'),
                     ('@storage_destroy(', 'Destroy')):
    check(POUCH.count(helper) == 2,
          '%s reuses the shared helper, for both pouches' % what)
check('~storage_empty_to_inv(rune_pouch_store' in UI,
      '...and the window\'s Empty button goes through the same helper as the item op')
for h in ('proc,storage_empty_to_inv', 'proc,storage_check', 'label,storage_destroy'):
    check('[' + h + ']' in STORAGE, '...which still exists: %s' % h.split(',')[1])

# ============================================================================ 6
print('6. the upgrade is OSRS\'s recipe, all four parts of it')
up = code(block(POUCH, 'label,rune_pouch_upgrade'))
check('stat_base(crafting) < ^rune_pouch_craft_level' in up, 'it wants the level, unboosted')
check(const('rune_pouch_craft_level') == 75, 'which is OSRS\'s 75 Crafting')
# The Thread of Elidinis, not ordinary thread. The first pass substituted plain thread, which
# made the recipe wrong rather than incomplete: the item exists in the OSRS cache and imports
# cleanly, so there was never a reason to stand something else in for it.
check('inv_del(inv, thread_of_elidinis, 1);' in up, 'it spends a Thread of Elidinis')
check(not re.search(r'inv_(del|total)\(inv, thread,', up),
      '...and not ordinary thread, which is a different item that must not work')
check('inv_total(inv, thread_of_elidinis) < 1' in up, '...and says so when you have none')
check('inv_del(inv, rune_pouch, 1);' in up and 'inv_add(inv, divine_rune_pouch, 1);' in up,
      'and swaps the pouch for the divine one')
check('stat_advance' not in up, 'and gives no experience, as OSRS gives none')
check('case rune_pouch : @rune_pouch_upgrade;' in LEATHER,
      'it hangs off the needle\'s own [opheldu,needle] switch')
# DECLARATIONS, NOT MENTIONS. This counted the string anywhere in the file, and then the Xerician
# robes round added a comment saying "[opheldu,needle] can only be declared once and this file owns
# it" - so the sentence explaining the rule broke the check that enforces it. A trigger is declared
# at the start of a line; a comment that names one never is. Fifth time a check in this project has
# been caught by its own prose.
check(len(re.findall(r'^\[opheldu,needle\]', LEATHER, re.M)) == 1,
      '...which is still declared once - a second would not compile')
check('[opheldu,rune_pouch]' in POUCH and 'last_useitem = needle' in POUCH,
      'and the pouch answers the other direction too')
rev = code(block(POUCH, 'opheld4,divine_rune_pouch'))
check('~rune_pouch_kinds_used > oc_param(rune_pouch, pouch_slots)' in rev,
      'Revert refuses while a fourth kind is inside rather than dropping it')
check('inv_add(inv, thread_of_elidinis, 1);' in rev,
      'and hands the Thread of Elidinis back, which is the one OSRS returns')
# WHERE THE THREAD COMES FROM. OSRS puts it in Tombs of Amascut, a raid with no content here, so
# it is a rare out of the top clue tier - there is no elite tier in this build, hard is the top.
TRAIL = read('scripts/minigames/game_trail/scripts/hard/trail_clue_hard_reward.rs2')
# IT IS IN THE ELITE AND MASTER TABLE, NOT THE HARD ONE, and that is deliberate. The hard rare
# table was Old School's own 158 as of 2026-10-04, which has no room for a raid drop - the rewrite
# that imported those 158 dropped the thread's row with it, and nothing noticed for ten days
# because the thread was out of nosourcespec.json by then and the sweep's loudest bucket does not
# print names. ~trail_clue_master_rare is the table for uniques with nowhere else to come from,
# which is exactly what the thread is, and the hard rare roll reaches it one time in eight.
rare = code(block(TRAIL, 'proc,trail_clue_master_rare'))
check('inv_add(trail_rewardinv, thread_of_elidinis, 1);' in rare,
      'the Thread of Elidinis is a rare reward out of the top clue tier')
check(TRAIL.count('thread_of_elidinis') == 1,
      'in exactly one place, so there is no second chance at it: %s'
      % TRAIL.count('thread_of_elidinis'))
# The case list and the random() bound have to agree or the last case is unreachable - which is
# how a reward gets added and never rolls. Counted, not assumed, for both tables: the hard one
# opens with its own random(8) for the branch into the master table, so the bound read here is the
# one the switch is actually written against, $random's, rather than the first random in the proc.
for proc in ('proc,trail_clue_hard_rare', 'proc,trail_clue_master_rare'):
    body = code(block(TRAIL, proc))
    cases = [int(m.group(1)) for m in re.finditer(r'^\s*case (\d+) :', body, re.M)]
    bound = int(re.search(r'\$random = random\((\d+)\)', body).group(1))
    check(cases == list(range(bound)),
          '~%s\'s cases run 0..n-1 against its own random bound, so the last row added to it can '
          'actually come up: %d cases against random(%d)'
          % (proc.split(',')[1], len(cases), bound))
# The REFUND still must not count as the source. It was excused by the spec's per-obj "ignore"
# while the thread was sourceless; an obj with a source cannot carry one, so it moved to the
# top-level not_a_source section - otherwise deleting the clue row would leave Revert looking
# like the source and the sweep would go on calling the thread obtainable.
nas = json.loads(read('tools/nosourcespec.json')).get('not_a_source', {})
check(nas.get('thread_of_elidinis') == ['rune_pouch.rs2:opheld4,divine_rune_pouch'],
      'and Revert is still named as not-a-source, at script grain: %s'
      % nas.get('thread_of_elidinis'))
check('thread_of_elidinis' not in json.loads(read('tools/nosourcespec.json'))['objs'],
      'with the thread out of the sourceless list entirely rather than in both')
check(objblock('divine_rune_pouch').get('iop4') == 'Revert', 'the divine pouch advertises Revert')
check('iop4' not in objblock('rune_pouch'), 'and the plain one has nothing to revert')

# ============================================================================ 7
print('7. what happens to the runes when you die is a decision, not an oversight')
check('inv_dropall(looting_bag_store' in DEATH,
      'the looting bag still drops its contents, as OSRS does')
check('rune_pouch_store' not in DEATH,
      'and the pouch keeps its runes, as the herb sack and seed box keep theirs - the one place '
      'this differs from OSRS PvP, deliberately')
check(objblock('rune_pouch').get('tradeable') == 'no'
      and objblock('divine_rune_pouch').get('tradeable') == 'no',
      'both pouches are untradeable, as in OSRS')

# ============================================================================ 8
print('8. the window: four slots you can take out of and a pack you can put in from')
check('[opheld3,rune_pouch] ~rune_pouch_open;' in UI
      and '[opheld3,divine_rune_pouch] ~rune_pouch_open;' in UI,
      'Check opens the window, for both pouches')
check('~storage_check(rune_pouch_store' not in POUCH,
      '...and no longer lists the contents down the chatbox instead')
check(objblock('rune_pouch').get('iop3') == 'Check'
      and objblock('divine_rune_pouch').get('iop3') == 'Check',
      '...which is still the op both items advertise')
op = code(block(UI, 'proc,rune_pouch_open'))
check('if ($slots = 0) {' in op, 'it does nothing when you are not carrying a pouch')
check('inv_transmit(rune_pouch_store, rune_pouch_main:pouch);' in op
      and 'inv_transmit(inv, rune_pouch_side:inv);' in op,
      'it transmits the store and your pack')
check('if_openmain_side(rune_pouch_main, rune_pouch_side);' in op,
      '...and opens them as a window and a sidebar, the way the bank does')
cl = code(block(UI, 'if_close,rune_pouch_main'))
check('inv_stoptransmit(rune_pouch_main:pouch);' in cl
      and 'inv_stoptransmit(rune_pouch_side:inv);' in cl, 'and stops both on close')
check('rune_pouch_mirror' not in cl,
      '...but NOT the mirror, which is not part of this window')
# taking out
for n, amt in ((1, '1'), (2, '5'), (3, '10'), (4, '^max_32bit_int')):
    check('[inv_button%d,rune_pouch_main:pouch] ~rune_pouch_remove(last_slot, %s);' % (n, amt) in UI,
          'Remove %s is wired to slot click %d' % (amt, n))
    check('[inv_button%d,rune_pouch_side:inv] ~rune_pouch_store_op(last_item, %s);' % (n, amt) in UI,
          '...and Store %s to the sidebar' % amt)
for i, o in enumerate(['Remove 1', 'Remove 5', 'Remove 10', 'Remove All'], 1):
    check('option%d=%s' % (i, o) in MAINIF, 'the window slot advertises %s' % o)
for i, o in enumerate(['Store 1', 'Store 5', 'Store 10', 'Store All'], 1):
    check('option%d=%s' % (i, o) in SIDEIF, 'the sidebar advertises %s' % o)
rm = code(block(UI, 'proc,rune_pouch_remove'))
check('if ($slot >= ~rune_pouch_slots) {' in rm,
      'a slot the carried pouch cannot reach will not empty - the plain pouch does not spill the '
      'divine one\'s fourth kind, which is the rule Revert already follows')
check('min($count, inv_total(rune_pouch_store, $rune))' in rm, '...and it never takes more than is there')
check('inv_freespace(inv) < 1 & inv_total(inv, $rune) < 1' in rm,
      '...and refuses when there is no room, unless the rune can stack onto one you hold')
check('~rune_pouch_refresh;' in rm, '...and repaints the labels afterwards')
# putting in
put = code(block(UI, 'proc,rune_pouch_put'))
check('~rune_pouch_accepts($obj) = false' in put, 'only a rune goes in')
check('$inside = 0 & ~rune_pouch_kinds_used >= ~rune_pouch_slots' in put,
      '...a new kind needs a slot the pouch can reach')
check('^rune_pouch_max_per_rune - $inside' in put, '...and the 16,000 cap still applies')
check('[opheldu,rune_pouch]' in POUCH and '[opheldu,divine_rune_pouch]' in POUCH,
      'a rune used on either pouch goes in, which is how anyone tries it first')
check(POUCH.count('~rune_pouch_put(last_useitem, ^max_32bit_int)') == 2,
      '...both through the same proc as the window: %d'
      % POUCH.count('~rune_pouch_put(last_useitem, ^max_32bit_int)'))
check('last_useitem = needle' in code(block(POUCH, 'opheldu,rune_pouch')),
      '...and the needle is still checked first, so the upgrade is not shadowed')
# the labels
ref = code(block(UI, 'proc,rune_pouch_refresh'))
slots = int(re.search(r'size=(\d+)', block(INV, 'rune_pouch_store')).group(1))
for i in range(slots):
    check('if_settext(rune_pouch_main:name%d, ~rune_pouch_slotname(%d));' % (i, i) in ref,
          'slot %d gets its rune name written under it' % i)
    check('[name%d]' % i in MAINIF, '...and the component exists')
check(ref.count('if_settext(rune_pouch_main:name') == slots,
      'one label per slot and no more: %d of %d'
      % (ref.count('if_settext(rune_pouch_main:name'), slots))
check('if_sethide(rune_pouch_main:locked, true);' in ref
      and 'if_sethide(rune_pouch_main:locked, false);' in ref,
      'the fourth slot is marked locked for the plain pouch')
check('type=layer' in block(MAINIF, 'locked'),
      '...on a LAYER, because if_sethide does nothing to anything else in this client')
for where in ('if_button,rune_pouch_main:fill', 'if_button,rune_pouch_main:empty',
              'proc,rune_pouch_store_op'):
    check('~rune_pouch_refresh' in code(block(UI, where)),
          '...repainted after %s' % where.split(',')[-1])

# ============================================================================ 9
print('9. the mirror, which is why a rune in the pouch can be cast at all')
check('[proc,rune_pouch_mirror_start]' in UI and
      'inv_transmit(rune_pouch_store, rune_pouch_mirror:runes);' in UI,
      'there is one proc that starts the mirror')
check('~rune_pouch_mirror_start;' in code(LOGIN),
      '...and login starts it')
# It used to run for the whole session, and a player with NO pouch saw spells lit by runes they
# were not carrying. The mirror now follows the pouch: synced every tick, transmitted only while
# ~rune_pouch_slots says one is carried, and stopped - which empties the client's copy - otherwise.
sync = code(block(UI, 'proc,rune_pouch_mirror_sync'))
check('softtimer(rune_pouch_mirror_sync, 1);' in code(block(UI, 'proc,rune_pouch_mirror_start')) and
      '~rune_pouch_mirror_sync;' in code(block(UI, 'softtimer,rune_pouch_mirror_sync')),
      '...and re-checks it every tick')
check('~rune_pouch_slots > 0' in sync and sync.find('inv_transmit') < sync.find('inv_stoptransmit(rune_pouch_mirror:runes)'),
      '...transmitting it only while a pouch is carried, and stopping it when not')
check('type=inv' in MIRRORIF,
      'the mirror component is an inv - the client allocates invSlotObjId at unpack for type 2 and '
      'keeps those components through unloadCom, which is what makes it safe to count before '
      'anything has been transmitted')
check('rune_pouch_mirror:runes' in IFPACK, '...and it is in interface.pack for the packer to find')
check('option' not in MIRRORIF, '...with no options, because nothing ever clicks it')
check(re.search(r'width=%d\s*\nheight=1' % slots, MIRRORIF),
      '...and as many slots as the store has: %d' % slots)
# the ops themselves
# One check per interface rather than one for the whole run: a single gate means a mutation that
# breaks one spellbook is "caught" by a check that names a different one.
r = subprocess.run([sys.executable, os.path.join(C, 'tools/genpouchruneops.py'), '--check'],
                   capture_output=True, text=True, cwd=C)
state, raw = {}, []
for l in r.stdout.split('\n'):
    # The KEYS are normalised, so a separator difference cannot break the checks below on one
    # platform and pass on the other - which is exactly what it did: the generator printed
    # backslashes on Windows and this battery, looking for 'scripts/', saw no files at all.
    # The RAW lines are kept so the separator itself can still be checked, below, rather than
    # this normalisation quietly hiding a regression from the check that is meant to catch it.
    if l.replace(chr(92), '/').startswith('scripts/'):
        raw.append(l.split()[0])
        state[l.replace(chr(92), '/').split()[0]] = l.split()[-1]
# eight since the Lunar spellbook (skill_magic/interfaces/lunar_magic.if), which the generator found
# on its own - the point of this check
check(len(state) == 8,
      'eight interfaces count runes, and the generator finds them itself rather than being told: %d'
      % len(state))
for rel in sorted(state):
    check(state[rel] == 'unchanged',
          '%s counts every pack rune in the pouch too' % os.path.basename(rel))
check(all(chr(92) not in k for k in raw),
      '...and names them with POSIX separators, so the printout is the same on Windows as on '
      'Linux: %s' % (sorted(k for k in raw if chr(92) in k) or 'all forward slashes'))
check('scripts/skill_combat/interfaces/magic/staff_spells.if' in state,
      'the autocast panel is one of them - a hand-written list of the two spellbooks missed it, '
      'and only decoding the packed archive found that out')
runes = [l.split(',', 1)[1].strip() for l in ENUM.split('\n') if l.strip().startswith('val=')]
MAGICIF = read('scripts/skill_magic/interfaces/magic.if')
for r_ in ('airrune', 'lawrune', 'bloodrune'):
    check('inv_count,rune_pouch_mirror:runes,%s' % r_ in MAGICIF, '%s is counted in the pouch' % r_)
for notrune in ('banana', 'stafforb'):
    check('inv_count,rune_pouch_mirror:runes,%s' % notrune not in MAGICIF,
          '...and %s is not, being no kind of rune' % notrune)
worst = 0
for blk in re.split(r'(?m)^(?=\[)', MAGICIF + '\n' + read('scripts/skill_magic/interfaces/ancient_magic.if')):
    for j in range(1, 6):
        n = len([l for l in blk.split('\n') if l.startswith('script%dop' % j)])
        worst = max(worst, n)
check(worst <= 20, 'no script exceeds the packer\'s cap of 20 ops: worst is %d' % worst)

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
