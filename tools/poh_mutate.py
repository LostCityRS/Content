#!/usr/bin/env python3
"""Mutation test for the build-window checks in poh_battery.py and the two sims.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry
below breaks one thing the checkers claim to catch - in a throwaway copy of the tree, never in
place - and the named checker has to go red. Every mistake here is one that was actually made,
or one the 377 client fails silently on.

Naming the checker is half the point: a mutation caught by the wrong script means a check is
testing something other than what it says.

A MUTATION TO A SPEC FILE CANNOT BE RUN HERE and be worth anything. The battery re-runs the
generators in place, so any edit to tools/furnspec.json trips group 38 - "the generator still
produces what is checked in" - before the check under test can fire. Those entries go through
tools/poh_mutate_spec.py, which edits the spec, regenerates, and only then runs the battery, which
is the sequence a person would actually produce. They are still listed below so there is one list.

    python3 tools/poh_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The work tree is per-shard, so two shards on one machine do not overwrite each other's copy.
# In CI each shard is its own runner and it would not matter; locally it would, silently.
_shardtag = ''
for _k, _a in enumerate(sys.argv):
    if _a == '--shard' and _k + 1 < len(sys.argv):
        _shardtag = '_' + sys.argv[_k + 1].replace('/', 'of')
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'poh_mutate_work' + _shardtag)
# The real engine clone, under either name it goes by, handed to every checker through the
# environment - see the note beside the subprocess call.
ENGINE = next((os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')
               if os.path.exists(os.path.join(C, '..', e, 'src'))),
              os.path.join(C, '..', 'engine'))

MUTS = [
 # (file, find, replace, which check group must go red)
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[row0]\ntype=layer', '[row0]\ntype=overlay', '31 poh_roommenu:row0 is a LAYER, so if_sethide can hide it'),
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[r0box]\nlayer=row0\ntype=rect\nx=0\ny=0\nbuttontype=normal',
  '[r0box]\nlayer=row0\ntype=rect\nx=0\ny=0', '31 poh_roommenu:r0box is buttontype=normal, so a click can resume the script'),
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[cancel]\ntype=text\nx=272\ny=301', '[cancel]\ntype=text\nx=272\ny=321', '32 poh_roommenu: every component is inside (12, 20, 500, 320):'),
 # RETARGETED AT THE GENERATOR, AND ROUTED TO THE SPEC HARNESS. poh_furnmenu.if is generated and
 # the battery regenerates before it checks, so editing the .if was overwritten before "inside the
 # window" could look at it and group 38 fired instead - the mutation read as caught while nothing
 # it claims to test was tested. Moving it to genmenus.py is not enough on its own either: a
 # mutated generator makes the regenerated output differ from what is checked in, which is also
 # group 38. tools/poh_mutate_spec.py regenerates AND takes the new output as the baseline, which
 # is the only sequence where the check under test is the one that fires.
 ('tools/genmenus.py',
  "coms.append((p + 'name', dict(layer=L, type='text', x=96, y=11, width=126, height=14,",
  "coms.append((p + 'name', dict(layer=L, type='text', x=206, y=11, width=126, height=14,",
  '32 poh_furnmenu: every component is inside (spec)'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '[proc,poh_room_zoom](int $type)(int)\nswitch_int ($type) {\n    case 1 : return(5096);',
  '[proc,poh_room_zoom](int $type)(int)\nswitch_int ($type) {\n    case 1 : return(900);',
  '33 room: all 16 icons are drawn inside their 448x36 row:'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'case 5 : return(12550);   // poh_bed1_8', 'case 5 : return(12551);   // poh_bed1_8',
  '33 room: all 16 icons are drawn inside their 448x36 row:'),
 ('scripts/skill_construction/configs/poh_rooms.enum',
  'val=9,150,000', 'val=9,15,000', '34 every grouped price is its own number:'),
 ('scripts/skill_construction/configs/poh_furniture.enum',
  'val=12,Clock', 'val=13,Clock', '34 poh_fam_name names all 79 hotspot families'),
 ('pack/interface.order', '19242\n', '', '30 interface.pack and interface.order hold the same id set'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_sethide(poh_roommenu:row0, true);', 'if_sethide(poh_roommenu:r0name, true);',
  '31 is a LAYER, so if_sethide can hide it'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_settext(poh_roommenu:r0cost,', 'if_settext(poh_roommenu:row0,',
  '31 is a text component'),
 ('scripts/skill_construction/configs/poh_menus.enum',
  'val=2,@bla@', 'val=2,@gry@', '37 poh_tint_name: every value is a tag PixFont.evaluateTag knows:'),
 ('scripts/skill_construction/configs/poh_menus.enum',
  'val=0,@gre@\nval=1,@red@\nval=2,@bla@', 'val=0,@gre@\nval=1,@red@', '37 poh_tint_need answers for every ^poh_state_* and nothing else'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if (stat(construction) >= enum(int, int, poh_room_level, $pick)) {',
  'if (true) {', '6 the level gate at the click (build sim)'),
 ('scripts/skill_construction/scripts/poh_build.rs2',
  'if (~poh_room_rot_for($rx, $rz, $type, $side) < 0) {',
  'if (stat(construction) < enum(int, int, poh_room_level, $type)) {', '6 rooms listed whole (build sim)'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  'case 87 : loc_add($spot, poh_pet_1, $angle, grounddecor,',
  'case 87 : loc_add($spot, poh_pet_1, $angle, centrepiece_straight,',
  '28 every family is placed with its hotspots\' own shape:'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  'case 238 : loc_add($spot, poh_treasure_magic_chest, $angle, centrepiece_straight, ^poh_loc_duration);\n',
  '', '28 ~poh_furn_show places every item 1..351'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_furn_slots = 256', '^poh_furn_slots = 257', '28 every furniture slot has a varp'),
 # THROUGH THE SPEC HARNESS. This angle is furnspec.json's, and poh_menus.rs2 is generated from
 # it - so the only edit worth making is to the spec, regenerated, which is what
 # tools/poh_mutate_spec.py does. Marked (spec) so the plain harness skips it instead of reporting
 # group 38 and calling it caught.
 ('tools/furnspec.json',
  '"wallchart": [\n   120,\n   1536\n  ]', '"wallchart": [\n   150,\n   1536\n  ]',
  '33 the families turned face-on all use the same camera (spec)'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_furn_bit_lit = 22', '^poh_furn_bit_lit = 13', '1 the lit bit must sit above the old fields (furn sim)'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oploc1,poh_torch_1]', '[oploc2,poh_torch_1]', '39 every family with an op1 in the spec has a trigger for every tier:'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oplocu,poh_altar_saradomin_1]', '[oplocu,poh_lectern_1]', '39 the offer-bones trigger is on the 7 altars and nothing else:'),
 ('scripts/skill_construction/configs/poh.loc',
  '[loc_13610]\nname=Clay fireplace\ndesc=A fire burns cosily in the grate.\nmodel=loc_13609\nmodel2=loc_13610\nlength=2\nanim=fireplace\nanim=fire_effect\nforceapproach=east\nop5=Remove',
  '[loc_13610]\nname=Clay fireplace\ndesc=A fire burns cosily in the grate.\nmodel=loc_13609\nmodel2=loc_13610\nlength=2\nanim=fireplace\nanim=fire_effect\nforceapproach=east',
  '28 every placed loc carries op5=Remove:'),
 ('scripts/skill_construction/configs/poh_tablets.enum',
  'val=6,25', 'val=6,26', '40 poh_tab_level is the spell row\'s levelrequired:'),
 ('scripts/skill_construction/configs/poh_tablets.enum',
  'val=6,1 fire, 3 air, 1 law, 1 soft clay', 'val=6,1 fire, 2 air, 1 law, 1 soft clay',
  '40 poh_tab_need is the spell row\'s runes plus the clay:'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'return(db_getfield($d, magic_spell_table:runesrequired, 0));',
  'return(~staff_runes($d));',
  '40 making a tablet does NOT go through ~staff_runes - a staff pays for casting,'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'if (~wilderness_level(coord) > 20) {\n    mes("A mysterious force blocks your teleport!");\n    mes("You can\'t use this teleport after level 20 wilderness.");\n    return;\n}\nif (~pre_tele_checks(coord) = false) {\n    return;\n}\nif (inv_total(inv, $tab) < 1) {\n    return;\n}\ninv_del(inv, $tab, 1);\nmes("You break the tablet.");\ndef_dbrow $d',
  'if (~pre_tele_checks(coord) = false) {\n    return;\n}\nif (inv_total(inv, $tab) < 1) {\n    return;\n}\ninv_del(inv, $tab, 1);\nmes("You break the tablet.");\ndef_dbrow $d',
  '40 poh_tab_teleport keeps the level 20 wilderness ceiling'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465', 'model=obj_tab_lumbridge\n2dzoom=465',
  '41 every tablet carries the model the spec imported for it:'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465', 'model=obj_tab_norrock\n2dzoom=465',
  '41 every tablet carries the model the spec imported for it:'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'members=yes\nstackable=yes\nweight=1g\ncost=56', 'members=yes\nweight=1g\ncost=56',
  '41 every tablet is stackable:'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465\n2dxan=373', 'model=obj_tab_varrock\n2dzoom=1370\n2dxan=373',
  '41 every tablet keeps the 2d camera the OSRS config gave it:'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  '[opheld1,poh_tab_varrock]', '[opheld2,poh_tab_varrock]',
  '41 every [opheld1] is on a tablet that carries iop1=Break:'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oploc1,poh_lectern_7]\n~poh_tab_pick(7);', '[oploc1,poh_lectern_7]\n~poh_tab_pick(6);',
  '42 all seven lecterns Study their own tier: yes'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[t0model]\nlayer=row0\ntype=model\nx=4\ny=0\nwidth=34\nheight=28',
  '[t0model]\nlayer=row0\ntype=model\nx=4\ny=0\nwidth=34\nheight=44',
  '42 all 14 tablet icons at scale 90 land inside their 448x28 row:'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_setobject(poh_tabletmenu:t0model, enum(int, namedobj, poh_tab_obj, $tab), 90);',
  'if_setobject(poh_tabletmenu:t0model, enum(int, namedobj, poh_tab_obj, $tab), 220);',
  '42 all 14 tablet icons at scale'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'enum(int, namedobj, poh_tab_obj, $tab), 1);', 'enum(int, obj, poh_tab_obj, $tab), 1);',
  '15 an enum of the wrong type for the parameter (rs2check)'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'anim(poh_tab_break, 0);', 'anim(human_castteleport, 0);',
  '44 ~poh_tab_breakanim plays poh_tab_break'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'sound_synth(teleport_all, 1, 0);\n~poh_tab_breakanim;\np_delay(2);\n~p_telejump_safe($dest);',
  'sound_synth(teleport_all, 1, 0);\np_delay(2);\n~p_telejump_safe($dest);',
  '44 ~poh_tab_teleport breaks with the break animation'),
 ('scripts/skill_construction/configs/poh_tab_break.seq',
  'frame1=anim_osrs_10883_1', 'frame1=anim_osrs_10883_9',
  '44 every break frame is in anim.pack:'),
 ('scripts/skill_construction/configs/poh_tab_break.spotanim',
  'model=spot_poh_tab_break_gfx', 'model=spot_poh_tab_break_ghost',
  '44 the break graphic model spot_poh_tab_break_gfx is in model.pack'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[qty5]\ntype=text\nx=382\ny=46\nbuttontype=normal',
  '[qty5]\ntype=text\nx=382\ny=46',
  '45 poh_tabletmenu:qty5 is buttontype=normal, so a click can resume the script'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[qty10]\ntype=text\nx=420\ny=46', '[qty10]\ntype=text\nx=420\ny=66',
  '45 the buttons sit above the first row (y 62):'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '    if_addresumebutton(poh_tabletmenu:qty10);\n', '',
  '45 every quantity button is a resume target:'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if (%poh_tab_qty > ^poh_tab_qty_max) {', 'if (%poh_tab_qty > 100000) {',
  '45 Make X is clamped to ^poh_tab_qty_max (28)'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '        if_close;\n        ~poh_tab_make_n($pick, %poh_tab_qty);',
  '        ~poh_tab_make_n($pick, %poh_tab_qty);\n        if_close;',
  '45 the window closes before the tablets are made, so the animation is visible'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'weakqueue*(poh_tab_run, 0)($tab, min($count, ^poh_tab_qty_max));',
  'weakqueue*(poh_tab_run, 0)($tab, $count);',
  '45 the make loop is bounded by both the count and ^poh_tab_qty_max'),
 # THE HOLD, which is what DeathPlateau-Bugs#85 was: p_delay back in the run makes it a batch the
 # player cannot walk away from. On the generated file and not on tools/gentablets.py, for the
 # reason tools/poh_mutate_spec.py's header gives - a mutation to a generator trips "the generator
 # still produces what is checked in" before the check under test can fire.
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'if (~poh_tab_make($tab) = false) {\n    return;\n}',
  'if (~poh_tab_make($tab) = false) {\n    return;\n}\np_delay(2);',
  '45 and it never holds the player, so a Make 10 can be walked away from'),
 ('scripts/skill_construction/configs/construction.varp',
  '[poh_tab_qty]', '[poh_tab_qty]\nscope=perm',
  '45 %poh_tab_qty is temp - it is a setting, not part of the saved house'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_furn_bit_item_hi = 23', '^poh_furn_bit_item_hi = 13',
  '28 the item high byte moved into the range old saves already wrote (furn sim)'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  '~poh_furn_show(~poh_furn_item($v), $spot',
  '~poh_furn_show(~poh_furn_field($v, ^poh_furn_bit_item, 8), $spot',
  '28 a reader that sees only the low byte of the item number (furn sim)'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_garden_sell = 1000', '^poh_garden_sell = 900',
  '46 her selling multiplier is ^poh_garden_sell'),
 ('scripts/skill_construction/configs/poh_garden.npc',
  'param=shop_delta,0', 'param=shop_delta,1',
  '46 shop_delta is 0, so the price does not drift off the OSRS number'),
 ('scripts/skill_construction/configs/poh_garden.inv',
  'stock1=poh_bag_dead_tree,20,100', 'stock1=poh_bag_dead_tree,20,5',
  '46 twenty of each, restocking a unit a minute:'),
 ('pack/inv.pack',
  '407=poh_garden_shop', '407=poh_garden_shop_typo',
  '46 poh_garden_shop has an id in inv.pack'),
 ('maps/m46_52.jm2',
  '0 59 49: 3922', '0 56 49: 3922',
  '46 and neither do the eight tiles around her'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_garden_cp_x = 3', '^poh_garden_cp_x = 1',
  '47 every style has its Centrepiece space at ^poh_garden_cp_x/z ([(3, 3)])'),
 ('scripts/skill_construction/scripts/poh_garden.rs2',
  'if (~poh_furn_count_item(^poh_furn_exit_portal) > 0) {',
  'if (~poh_furn_count_item(^poh_furn_exit_portal) > 1) {',
  '47 a house that already has a portal is left alone'),
 ('scripts/skill_construction/scripts/poh.rs2',
  '~poh_ensure_exit;\n', '',
  '47 ~poh_enter makes sure of the portal before it builds the house'),
 ('tools/furnspec.json',
  '"loc": "poh_exit_portal",\n     "label": "Exit portal",\n     "level": 1,',
  '"loc": "poh_exit_portal",\n     "label": "Exit portal",\n     "level": 5,',
  '47 the exit portal is the centrepiece you can build at level 1'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_stone_sell = 1300', '^poh_stone_sell = 1200',
  '48 his selling multiplier is ^poh_stone_sell'),
 ('scripts/skill_construction/configs/poh_stone.inv',
  'stock2=poh_marble_block,20,100', 'stock2=poh_marble_block,20,5',
  '48 a thousand bricks, twenty blocks, twenty leaves and ten stones:'),
 ('maps/m44_159.jm2',
  '0 27 8: 3923', '0 27 15: 3923',
  '48 his tile and the eight around it are clear'),
 ('scripts/skill_construction/configs/poh_stone.npc',
  'param=owned_shop,poh_stone_shop', 'param=owned_shop,poh_garden_shop',
  '48 he owns poh_stone_shop'),
 ('scripts/skill_construction/configs/poh_rooms.enum',
  'val=16,15', 'val=16,7',
  '49 its door mask is the sides the six template squares actually have doors on'),
 ('scripts/skill_construction/configs/poh_rooms.enum',
  'val=16,17', 'val=16,18',
  '49 its template zone is the one the templates are drawn in'),
 ('scripts/skill_construction/configs/poh_rooms.enum',
  'val=16,75000', 'val=16,7500',
  '49 every grouped price is its own number:'),
 ('tools/furnspec.json',
  '"loc": "loc_13479",\n     "label": "Large fountain",\n     "level": 75,\n     "xp": 1000,\n     "mats": [\n      [\n       "poh_marble_block",\n       2\n      ]',
  '"loc": "loc_13479",\n     "label": "Large fountain",\n     "level": 75,\n     "xp": 1000,\n     "mats": [\n      [\n       "poh_marble_block",\n       1\n      ]',
  '49 one, two and three blocks, as OSRS charges'),
 ('scripts/skill_construction/scripts/poh.rs2',
  'if (~poh_house_empty = true) {', 'if (~poh_room_total = 0) {',
  '50 ~poh_can_place asks ~poh_house_empty, not ~poh_room_total'),
 ('scripts/skill_construction/scripts/poh.rs2',
  'if (and(~poh_word_get($i), ^poh_type_mask) ! 0) {', 'if (~poh_word_get($i) ! 0) {',
  '50 and ~poh_house_empty masks whole layout words rather than decoding slots'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_type_mask = 1061109567', '^poh_type_mask = -1',
  '50 ^poh_type_mask covers the four 6-bit type fields of a word, nothing else'),
 ('scripts/skill_construction/scripts/poh_build.rs2',
  '    $bit = calc($bit * 2);\n    $type = calc($type + 1);\n}\nreturn($mask);',
  '    $bit = calc($bit + 2);\n    $type = calc($type + 1);\n}\nreturn($mask);',
  '50 ~poh_fit_mask turns the ladder into one bitmask'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'def_int $a = ~poh_nth_fit($mask, calc($page * ^poh_menu_rows + 0));',
  'def_int $a = ~poh_nth_room($rx, $rz, $side, calc($page * ^poh_menu_rows + 0));',
  '50 the per-row walk is gone from the build, not just unused'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_room_count = 16', '^poh_room_count = 32',
  '50 the room types all fit in the bits of one mask, whose ceiling is 31'),
 ('scripts/skill_construction/configs/poh_furniture.enum',
  '[poh_fam_last]\ninputtype=int\noutputtype=int\nval=1,7',
  '[poh_fam_last]\ninputtype=int\noutputtype=int\nval=1,6',
  '6 the family is listed whole (furn sim)'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  'if ($item > enum(int, int, poh_fam_last, $fam)) {',
  'if ($item > enum(int, int, poh_fam_first, $fam)) {',
  '6 a furniture family showing only its first piece (furn sim)'),
 ('scripts/skill_construction/configs/poh_furniture.enum',
  '[poh_fam_first]\ninputtype=int\noutputtype=int\nval=1,1',
  '[poh_fam_first]\ninputtype=int\noutputtype=int\nval=1,2',
  '51 and each family\'s pieces really are consecutive - the arithmetic depends on it'),
 # Rule 17 shipped INERT the first time - it used the HEADER regex, which needs a comma, so it
 # never matched a config block header and reported nothing at all when a default= was deleted.
 # This mutation is here so that cannot happen twice.
 ('scripts/skill_slayer/configs/superiors.enum',
  'outputtype=npc\ndefault=null', 'outputtype=npc',
  '17 an enum whose miss returns a real id 0 and has no default= (rs2check)'),
 ('scripts/skill_construction/configs/poh_furniture.enum',
  '[poh_furn_flat]\ninputtype=int\noutputtype=namedobj\ndefault=null',
  '[poh_furn_flat]\ninputtype=int\noutputtype=namedobj',
  '17 the flatpack join answering obj 0 instead of null (rs2check)'),
 ('scripts/skill_construction/configs/poh_flatpacks.obj',
  '[poh_flat_chair_1]', '[poh_flat_chair_0]',
  '52 every flatpack obj is registered in obj.pack:'),
 ('scripts/skill_construction/configs/poh.loc',
  '[loc_13704]\nname=Workbench\ndesc=You can make furniture here.\nmodel=loc_10673i2\nwidth=2\nop1=Work-at',
  '[loc_13704]\nname=Workbench\ndesc=You can make furniture here.\nmodel=loc_10673i2\nwidth=2\nop1=Use',
  '52 loc_13704 carries op1=Work-at'),
 ('scripts/skill_construction/configs/poh_styles.enum',
  '[poh_style_cost]\ninputtype=int\noutputtype=int\ndefault=null',
  '[poh_style_cost]\ninputtype=int\noutputtype=int',
  '53 poh_style_cost declares default=null - a miss must not answer style 0'),
 ('scripts/skill_construction/configs/poh_styles.enum',
  'val=3,10000', 'val=3,1000', '53 the ladder only ever goes up: [1, 10, 20, 30, 40, 50] at [5000, 5000, 7500,'),
 ('scripts/skill_construction/scripts/poh.rs2',
  'case 5 : return(movecoord(^poh_templates_b, 0, 1, 0));',
  'case 5 : return(^poh_templates_b);',
  '53 each style is cut from a different square and level:'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  'if (stat(construction) < $level) {', 'if (false) {',
  '53 redecorating tests the level before it takes the coins'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  '''// re-check: the choice box gives the player a chance to drop or trade the coins away
if (inv_total(inv, coins) < $cost) {
    ~chatplayer("<p,sad>Actually, I don't have the money.");
    ~chatnpc("<p,sad>Come back when you do.");
    return;
}
~chatplayer("<p,happy>Here you are.");''',
  '~chatplayer("<p,happy>Here you are.");',
  '53 the purse is re-checked AFTER the confirm box - it is a suspend, and coins'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  '"<enum(int, string, poh_style_name, 5)> - <tostring(enum(int, int, poh_style_cost, 5))> coins", 2,',
  '"<enum(int, string, poh_style_name, 4)> - <tostring(enum(int, int, poh_style_cost, 4))> coins", 2,',
  '53 the two menu pages between them offer all six styles: [0, 1, 2, 3,'),
 ('maps/m39_48.jm2', '0 45 27: 15296 10 0', '0 45 27: 15296 10 2',
  '22 the one that was approved'),
 ('maps/m43_49.jm2', '0 7 40: 15296 10 3', '0 8 40: 15296 10 3',
  '21 town 4: the map and poh_loc_portal name the same tile ((0,'),
 ('maps/m41_56.jm2', '0 42 48: 3920', '0 47 48: 3920',
  '15 town 3: the estate agent does not stand inside the portal'),
 ('maps/m39_48.jm2', '0 45 27: 15296 10 0', '0 33 27: 15296 10 0',
  '15 town 5: the map and poh_loc_portal name the same tile ((0,'),
 ('scripts/skill_construction/configs/poh_costume.enum',
  'val=95,boots_wizard', 'val=95,rune_platebody',
  '55 and nothing in the chest is something a shop sells:'),
 ('scripts/skill_construction/configs/poh_costume.enum',
  'val=5,rune_full_helm_zamorak', 'val=5,rune_full_helm_saradomin',
  '55 no item is listed twice'),
 ('scripts/skill_construction/configs/poh_costume.enum',
  '[poh_costume_set_first]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,0\nval=1,5',
  '[poh_costume_set_first]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,0\nval=1,6',
  '55 the sets are consecutive and leave no item out'),
 ('scripts/skill_construction/configs/poh_costume.inv',
  '[poh_costume_store]\nscope=perm', '[poh_costume_store]\nscope=temp',
  '55 poh_costume_store is scope=perm - the whole point is that it survives logout'),
 ('scripts/skill_construction/scripts/poh_costume.rs2',
  'if (inv_total(inv, $item) > 0 & inv_total(poh_costume_store, $item) = 0) {',
  'if (inv_total(inv, $item) > 0) {',
  '55 storing puts ONE of each in - a second gold-trimmed platebody is not part of'),
 ('scripts/tutorial/scripts/tutorial.rs2',
  'if (%tutorial = ^newbie_basics_instructor_start) {\n    %tutorial = ^newbie_basics_instructor_designed_character;\n}',
  '%tutorial = ^newbie_basics_instructor_designed_character;',
  '55 the shared close handler only advances a player who is still IN the tutorial'),
 ('scripts/general/scripts/enchanted_jewellry/amulet_of_glory.rs2',
  'if (~glory_teleport($message) = false) {\n    return;\n}\ninv_setslot',
  'if (~glory_teleport($message) = false) {\n    return;\n}\n// inv_setslot',
  '55 the charge is eaten by the LABEL - a loc trigger has no last_slot worth'),
 ('scripts/skill_construction/scripts/poh_games.rs2',
  '[oploc1,poh_dartboard2] ~poh_darts;', '',
  '56 no op on a placed piece is a dead click:'),
 ('scripts/skill_construction/scripts/poh_games.rs2',
  'inv_del(inv, $obj, 1);\nanim($anim, 0);',
  'anim($anim, 0);',
  '56 the ammunition is spent before the roll - a miss has to cost something'),
 ('scripts/skill_construction/configs/poh_games.enum',
  'val=11,rune_dart_launch', 'val=11,rune_arrow_launch',
  '56 and it is the effect for that ammunition:'),
 ('scripts/skill_construction/configs/poh_games.enum',
  'val=6,bronze_dart', 'val=6,bronze_arrow',
  '56 and it is the effect for that ammunition:'),
 ('scripts/skill_construction/scripts/poh_games.rs2',
  '[proc,poh_darts]\nif (~poh_in_own_house = false) {\n    return;\n}',
  '[proc,poh_darts]',
  '56 poh_darts checks you are in your own house'),
 ('scripts/skill_construction/configs/poh.loc',
  'multiloc=9,poh_lumbridge_window_shutters', 'multiloc=9,poh_rimmington_window_shutters',
  '57 each child is the window for its own style and kind:'),
 ('scripts/skill_construction/configs/poh.loc',
  'multiloc=53,poh_yanille_window_zamorak2', 'multiloc=60,poh_yanille_window_zamorak2',
  '57 all 54 states are listed with no gap (54 found)'),
 ('scripts/skill_construction/configs/construction.varp',
  '[poh_window]\nscope=perm', '[poh_window]\nscope=temp',
  '57 and it is perm - a house does not reglaze itself on logout'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  '%poh_style = $style;\n// the windows are part of the style, and all 116 of them read one varp\n~poh_window_refresh;',
  '%poh_style = $style;',
  '57 redecorating calls it - the windows are part of the style'),
 ('tools/genfurn.py',
  "body = ['~poh_furn_sit(%s, %s);' % (op['seq'], q(op['mes']))]",
  "body = ['anim(%s, 0);' % op['seq'], 'mes(%s);' % q(op['mes'])]",
  '57 all 24 seats go through it (spec)'),
 ('maps/m45_54.jm2', '0 7 0: 15296 10 3', '0 7 1: 15296 10 3',
  '15 town 1: the map and poh_loc_portal name the same tile ((0, 7,'),
 ('scripts/skill_construction/configs/poh_locations.enum',
  'val=5,0_39_48_47_29', 'val=5,0_39_48_52_29',
  '15 town 5: leaving lands you next to the portal, at'),
 ('scripts/skill_construction/configs/construction.varp',
  '[poh_location]\nscope=perm', '[poh_location]\nscope=temp',
  '54 %poh_location is scope=perm'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  '~poh_free;\n%poh_location = $town;', '%poh_location = $town;',
  '54 the instance is freed BEFORE the move - someone standing in their house would'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  'if ($mine ! null & loc_coord ! $mine) {', 'if (false) {',
  '54 the click compares loc_coord against poh_loc_portal'),

 # --- 58, the portal chamber ---
 # a level that is no longer the spell's own - the whole point of copying them
 ('scripts/skill_construction/configs/poh_portal_dest.enum',
  'val=6,58', 'val=6,50', '58 every level and landing coord is its own teleport spell\'s:'),
 # a landing coord that drifts off the spell's
 ('scripts/skill_construction/configs/poh_portal_dest.enum',
  'val=7,0_45_57_11_23', 'val=7,0_45_57_11_24', '58 every level and landing coord is its own teleport spell\'s'),
 # the table that would let a marble portal to Camelot come up as a teak one somewhere else
 ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
  'case 28 : return(poh_portal_marble_camelot);', 'case 28 : return(poh_portal_teak_falador);',
  '58 every placeable piece has a Remove trigger:'),
 # a gap in the loc table - a frame with no case comes up as the default teak frame forever
 ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
  'case 24 : return(poh_portal_marble_empty);' + chr(10), '', '58 every placeable piece has a Remove trigger:'),
 # taking more runes than were checked for
 ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
  'inv_del(inv, airrune, 500); inv_del(inv, lawrune, 100);',
  'inv_del(inv, airrune, 600); inv_del(inv, lawrune, 100);',
  '58 checks exactly the runes it takes'),
 # the default that stops an undirected frame reading as Varrock, or coord 0
 ('scripts/skill_construction/configs/poh_portal_dest.enum',
  'outputtype=coord' + chr(10) + 'default=null', 'outputtype=coord', '58 poh_portal_coord has a default - 0 is a value it is really read with'),
 # a portal offset that no longer matches the template
 ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
  'movecoord($focus, 4, 0, 0)', 'movecoord($focus, 5, 0, 0)', '58 (7, 3) is reached as movecoord($focus, 4, 0, 0)'),
 # a directed portal nobody can take out again
 ('scripts/skill_construction/scripts/poh_portal_chamber.rs2',
  '[oploc5,poh_portal_marble_yanille] ~poh_portal_remove;' + chr(10), '',
  '58 every placeable piece has a Remove trigger: 350 placed,'),
 # and the piece itself going down as a fixed loc again, which loses the destination
 ('tools/genfurn.py',
  "        if f.get('show'):\n            o.append('    case %d : ~%s($spot, $angle, %d);' % (i['n'], f['show'], i['tier']))",
  "        if False:\n            o.append('    case %d : ~%s($spot, $angle, %d);' % (i['n'], f['show'], i['tier']))",
  '29 every placeable piece has a Remove trigger (spec)'),

 # --- 59, the combat ring ---
 # a rope one square out of the ring
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  '~poh_ring_wall($base, $rot, 2, 1, 1, poh_boxing_ringwall_white);',
  '~poh_ring_wall($base, $rot, 2, 0, 1, poh_boxing_ringwall_white);',
  '59 every tile laid is a template tile'),
 # a mat laid on the wall layer, which leaves the hotspot standing in the same tile
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  '~poh_ring_mat($base, $rot, 2, 2, 0, poh_boxing_ring_mat_corner);',
  '~poh_ring_wall($base, $rot, 2, 2, 0, poh_boxing_ring_mat_corner);',
  '59 at its shape and its angle'),
 # a tile dropped, so the ring has a hole in it
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  '~poh_ring_mat($base, $rot, 3, 3, 0, poh_combat_mat_middle);' + chr(10), '',
  '59 combat covers 36 tiles'),
 # the zone rotation drifting off the engine's, so a turned room lays its ring sideways
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  'case 1 : return(movecoord($base, $z, 0, calc(7 - $x)));',
  'case 1 : return(movecoord($base, calc(7 - $x), 0, $z));',
  '59 the zone rotation matches the engine'),
 # the angle no longer turning with the room
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  'return(modulo(calc($angle + $rot), 4));', 'return($angle);', '59 and so does the angle'),
 # removal looking under the clicked tile, which is never where the ring is stored
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  '~poh_furn_at($rx, $rz, 0, 0)', '~poh_furn_at($rx, $rz, 1, 1)',
  '59 removal looks the slot up at the anchor'),
 # a ring loc nobody can take out again
 ('scripts/skill_construction/scripts/poh_combat_ring.rs2',
  '[oploc5,poh_boxing_ring_mat_side] ~poh_combat_ring_remove;' + chr(10), '',
  '59 all 18 ring locs are wired to ~poh_combat_ring_remove:'),
 # wiring an empty-model hotspot, which is a click that cannot happen
 ('tools/furnspec.json', '15098,', '15098,\n   15104,', '59 the family takes the 16 visible hotspots'),
 # the anchor moved onto a tile the ring itself stands on
 ('tools/furnspec.json', '"anchor": [\n    0,\n    0\n   ],', '"anchor": [\n    1,\n    1\n   ],',
  '59 anchors where no hotspot of its own stands'),
 # cloth that cannot be bought, so three of the four rings are unbuildable
 ('scripts/skill_construction/scripts/sawmill.rs2',
  '~sawmill_sell(bolt_of_cloth, ^sawmill_cost_cloth);', '~sawmill_sell(saw, ^sawmill_cost_cloth);',
  '59 the sawmill operator sells it'),
 # and the anchor path removed from the click, which loses the ring the moment it is stored
 ('tools/genfurn.py', "'if ($ax >= 0) {',", "'if ($ax >= 99) {',",
  '29 an anchor overrides the clicked tile'),

 # --- 60, rugs and the gilded pieces ---
 # a rug tile one square out of the rectangle
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '~poh_rug_lay($base, $rot, 3, 0, 3, $tier, ^poh_rug_corner);',
  '~poh_rug_lay($base, $rot, 3, 7, 3, $tier, ^poh_rug_corner);',
  '60 every rug tile is the template\'s'),
 # a corner laid as a middle, which is a carpet with no fringe on two edges
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '~poh_rug_lay($base, $rot, 1, 1, 3, $tier, ^poh_rug_corner);',
  '~poh_rug_lay($base, $rot, 1, 1, 3, $tier, ^poh_rug_middle);',
  '60 at its angle and its kind'),
 # an angle that no longer turns the fringe outward
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '~poh_rug_lay($base, $rot, 1, 2, 3, $tier, ^poh_rug_side);',
  '~poh_rug_lay($base, $rot, 1, 2, 0, $tier, ^poh_rug_side);',
  '60 at its angle and its kind'),
 # a tier wearing another tier's piece
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  'case 12 : return(loc_13594);', 'case 12 : return(loc_13588);',
  '60 every case is its own tier\'s piece'),
 # a gap in the piece table, so a rug comes up as null
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '    case 9 : return(loc_13592);   // plain side' + chr(10), '', '60 the rug table is three tiers of three with no gap: [4, 5, 6, 8,'),
 # removal looking under the clicked tile rather than at the anchor
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '~poh_furn_at($rx, $rz, ^poh_rug_anchor, ^poh_rug_anchor)', '~poh_furn_at($rx, $rz, 0, 0)',
  '60 removal looks the slot up at the anchor'),
 # the step back from the anchor dropped, so every table reads from seven tiles out
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  'movecoord($spot, calc(0 - ^poh_rug_anchor), 0, calc(0 - ^poh_rug_anchor))', '$spot',
  '60 the anchor is stepped back to the zone corner'),
 # a rug loc nobody can take out again
 ('scripts/skill_construction/scripts/poh_rug.rs2',
  '[oploc5,loc_13592] ~poh_rug_remove;' + chr(10), '', '60 all nine rug locs are wired'),
 # the anchor moved onto a tile that IS a hotspot in one of the five rooms
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_rug_anchor = 7', '^poh_rug_anchor = 1', '60 ^poh_rug_anchor and the spec\'s anchor are the same tile:'),
 # gold leaf priced at something other than what OSRS charges
 ('scripts/skill_construction/configs/poh_formal_mats.obj',
  'cost=100000', 'cost=200000', '26 all four come out at the OSRS price:'),
 # and the stonemason no longer stocking it, which makes two pieces unbuildable
 ('scripts/skill_construction/configs/poh_stone.inv',
  'stock3=gold_leaf,20,100' + chr(10), '', '26 the Stonemason stocks what he is meant to'),

 # --- 61, the fence, the throne floor, the windows and the multiloc sweep ---
 # the check that would have caught the dead Remove on every window in the house
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  '[oploc5,poh_dynamic_window]' + chr(10)
  + 'mes("The windows are part of the house itself.");' + chr(10)
  + 'mes("Build a window in a chapel to change them, or ask the estate agent to redecorate.");' + chr(10),
  '', '61 and the house windows answer their own Remove'),
 # a fence post one square off the perimeter
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  '~poh_fence_wall($base, $rot, 0, 1, 0, $tier);', '~poh_fence_wall($base, $rot, 1, 1, 0, $tier);',
  '61 and every one is the template\'s tile, shape and angle'),
 # a fence corner laid on the straight-wall layer, which leaves the hotspot standing in it
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  '~poh_fence_corner($base, $rot, 0, 0, 3, $tier);', '~poh_fence_wall($base, $rot, 0, 0, 3, $tier);',
  '61 and every one is the template\'s tile, shape and angle'),
 # the window table reordered, so building Saradomin glass gives you Guthix
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  'case 2 : return(poh_rimmington_window_saradomin);', 'case 2 : return(poh_rimmington_window_guthix);',
  '61 the 54-window table is poh_dynamic_window\'s own child order:'),
 # a chapel window that no longer reglazes the house, so the six panes disagree with the other 110
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  '%poh_window = calc(%poh_style * ^poh_window_kinds + $choice);' + chr(10), '',
  '61 building a chapel window reglazes the whole house'),
 # the throne floor wearing another style's art
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  'case 3 : return(poh_floordecor_rellekka);', 'case 3 : return(poh_floordecor_yanille);',
  '61 one piece per house style'),
 # a window nobody can take out again
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  '[oploc5,poh_yanille_window_zamorak2] ~poh_window_remove;' + chr(10), '',
  '61 chapelwindow: all 54 locs are removable:'),
 # the anchor written into the generated file drifting from the spec's
 ('scripts/skill_construction/scripts/poh_decor.rs2',
  'def_coord $base = movecoord($spot, -1, 0, -3);', 'def_coord $base = movecoord($spot, -1, 0, -4);',
  '61 fence steps back from the spec\'s own anchor'),
 # The writer that keeps a generated file's line endings uniform. Reverting it is invisible on
 # Linux - the file is all LF either way - so the mutation has to be caught by the SOURCE check
 # in group 35, not by the byte comparison. See the note there.
 ('tools/genmenus.py',
  "text = nl.join(rs2).replace('\\r\\n', '\\n').rstrip('\\n')",
  "text = nl.join(rs2).rstrip('\\r\\n')",
  '35 the rs2 writer normalises before it converts, which is what keeps that true'),
 # ---- 62: the costume room's five storage spaces ----
 # an item in a storage space that the treasure chest also holds: storable twice, lost once
 ('tools/storespec.json',
  '"macro_frog_mask",', '"macro_frog_mask",\n     "piratehat",',
  '62 nothing is in both a storage space and the treasure chest'),
 # the same item in two stores
 ('tools/storespec.json',
  '"spinning_plate",', '"spinning_plate",\n     "santa_hat",',
  '62 none of them is in two stores'),
 # an obj name that does not exist - the mistake that shipped five wrong names in a drop table
 ('tools/storespec.json',
  '"rubber_chicken",', '"rubber_chicken_deluxe",',
  '62 every one of them is a real obj'),
 # the generated enum out of step with the spec it came from
 ('scripts/skill_construction/configs/poh_store.enum',
  'val=0,attack_cape', 'val=0,defence_cape',
  '62 and none of them is in two stores:'),
 # an inv one slot short: the last item in the last store can never be put away
 ('scripts/skill_construction/configs/poh_store.inv', 'size=307', 'size=306',
  '62 poh_store_inv holds one of each'),
 # storage that empties on logout, which is the one thing storage must not do
 ('scripts/skill_construction/configs/poh_store.inv', '\nscope=perm', '\nscope=temp',
  '62 it is scope=perm'),
 # the store windows overlapping: two spaces claiming the same item
 ('scripts/skill_construction/configs/poh_store.enum',
  '[poh_store_first]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,0\nval=1,87',
  '[poh_store_first]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,0\nval=1,86',
  '62 the five windows tile poh_store_item'),
 # a set straddling two stores, so the cape rack hands you the wardrobe's robes
 ('scripts/skill_construction/configs/poh_store.enum',
  '[poh_store_set_last]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,23',
  '[poh_store_set_last]\ninputtype=int\noutputtype=int\ndefault=null\nval=0,24',
  '62 every store\'s sets tile its own run'),
 # a top tier that cannot hold the list it is the top tier of
 ('scripts/skill_construction/configs/poh_store.enum',
  'val=6,87', 'val=6,80', '62 every tier of every space has a capacity, rising to the whole list:'),
 # a cape rack wired to the magic wardrobe: it opens, it works, it holds the wrong things
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '~poh_store_open(0, 323);', '~poh_store_open(1, 323);',
  '62 every piece opens its own store'),
 # the paging proc losing its store bound - "More sets..." walks on into the next space
 ('scripts/skill_construction/scripts/poh_stores.rs2',
  'def_int $last = enum(int, int, poh_store_setlast, $store);\ndef_int $seen = 0;',
  'def_int $last = enum(int, int, poh_store_last, $store);\ndef_int $seen = 0;',
  '62 poh_store_nth stops at its own store\'s last set'),
 # ...and wrapping to set 0 rather than to its own first set
 ('scripts/skill_construction/scripts/poh_stores.rs2',
  'def_int $home = $from;', 'def_int $home = 0;',
  '62 and "More sets..." wraps to its own store\'s first set, not to set 0'),
 # a piece nobody can take out again
 ('scripts/skill_construction/configs/poh_costume_storage.loc',
  'name=Marble cape rack\nmodel=loc474_18770\nambient=20\nop1=Search\nop5=Remove',
  'name=Marble cape rack\nmodel=loc474_18770\nambient=20\nop1=Search',
  '62 every placed loc carries op5=Remove:'),
 # a footprint that disagrees with its hotspot, so the wardrobe stands through a wall
 ('scripts/skill_construction/configs/poh_costume_storage.loc',
  'name=Magic wardrobe\nmodel=loc474_18784\nlength=3', 'name=Magic wardrobe\nmodel=loc474_18784\nlength=2',
  '62 hotspot-shaped'),
 # the five families inserted where they read best, renumbering every item above them
 ('tools/furnspec.json', '"key": "caperack",', '"key": "caperack_moved",',
  '62 tools/genstores.py runs clean'),
 # the level-99 cape rack made of planks after all, so the magic stone has no reason to exist
 ('tools/furnspec.json', '"magic_stone",\n       1', '"mahogany_plank",\n       4',
  '62 one magic stone, for the level-99 cape rack'),
 # a build level off OSRS's own
 ('tools/furnspec.json', '"label": "Oak cape rack",\n     "level": 54',
  '"label": "Oak cape rack",\n     "level": 52', '62 the build levels are OSRS\'s own'),
 # experience that is not planks x the wood
 ('tools/furnspec.json', '"label": "Oak toy box",\n     "level": 50,\n     "xp": 240',
  '"label": "Oak toy box",\n     "level": 50,\n     "xp": 300',
  '62 the experience is planks x the wood'),
 # the Stonemason no longer stocking the one thing a level-99 cape rack needs
 ('scripts/skill_construction/configs/poh_stone.inv', 'stock4=magic_stone,10,100' + chr(10), '',
  '62 the Stonemason stocks what he is meant to'),
 # ...or stocking it at the wrong price
 ('scripts/skill_construction/configs/poh_formal_mats.obj', 'cost=750000', 'cost=4000000',
  '62 all four come out at the OSRS price'),
 # ---- 63: hedging, and the shop prices ----
 # THE ORPHAN CHECK ON ITS OWN. The two mutations below pull a line out of the shop, which trips
 # the stock COUNT first - a real failure, but not this one. This one leaves the shop alone and
 # points a flowerbed at a real obj that no shop sells and no script makes, which is exactly the
 # shape the bagged flower bug had.
 ('tools/furnspec.json', '"poh_bag_sunflower",', '"granite_maul",',
  '63 every material is bought somewhere or made somewhere'),
 # THE ONE THAT WAS LIVE FOR A WEEK: a material nothing sells. Take the bagged flower back out of
 # the Garden Centre and six flowerbeds become unbuildable again.
 ('scripts/skill_construction/configs/poh_garden.inv',
  'stock11=poh_bag_flower,20,100' + chr(10), '',
  '63 every material is bought somewhere or made somewhere'),
 # ...and the same for a hedge
 ('scripts/skill_construction/configs/poh_garden.inv',
  'stock17=poh_bag_thorny_hedge,20,100' + chr(10), '',
  '63 every material is bought somewhere or made somewhere'),
 # a plank the sawmill no longer mills - the "made" half of the same check
 ('scripts/skill_construction/scripts/sawmill.rs2', 'mahogany_plank', 'mahogany_plank_DISABLED',
  '63 every "made" one is really named by the script that makes it'),
 # the mistake this round is fixing: the shop's SELLING multiplier set to its buying ratio
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_garden_sell = 1000', '^poh_garden_sell = 400',
  '63 every price comes out at the OSRS number'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_stone_sell = 1300', '^poh_stone_sell = 500',
  '48 all four come out at the OSRS price'),
 # ...and an item's cost inflated to hide it, which is how it survived the first time
 ('scripts/skill_construction/configs/poh_formal_mats.obj', 'cost=750000', 'cost=8000000',
  '48 all four come out at the OSRS price'),
 # the npc param drifting from the constant - two places, one number
 ('scripts/skill_construction/configs/poh_stone.npc',
  'param=shop_sell_multiplier,1300', 'param=shop_sell_multiplier,500',
  '48 his selling multiplier is ^poh_stone_sell'),
 # the magic stone stocked at the wrong depth
 ('scripts/skill_construction/configs/poh_stone.inv',
  'stock4=magic_stone,10,100', 'stock4=magic_stone,5,100',
  '48 a thousand bricks, twenty blocks, twenty leaves and ten stones'),
 # a hedge tier at a level OSRS does not use
 ('tools/furnspec.json', '"label": "Thorny hedge",\n     "level": 56',
  '"label": "Thorny hedge",\n     "level": 55', '63 at OSRS\'s levels'),
 # ...or the wrong experience
 ('tools/furnspec.json', '"label": "Tall box hedge",\n     "level": 80,\n     "xp": 316',
  '"label": "Tall box hedge",\n     "level": 80,\n     "xp": 300', '63 and OSRS\'s experience'),
 # the kind order swapped, so corners get a straight piece and the hedge has gaps in it
 ('tools/genhedge.py', "    ('thorny',     ['loc_13456', 'loc_13457', 'loc_13458']),",
  "    ('thorny',     ['loc_13457', 'loc_13456', 'loc_13458']),",
  '63 the thorny hedge IS the three ghosts'),
 # a tile laid at the wrong angle, so one hedge in the run faces out of the garden
 ('scripts/skill_construction/scripts/poh_hedge.rs2',
  '~poh_hedge_lay($base, $rot, 0, 1, 3, $tier, ^poh_hedge_b);',
  '~poh_hedge_lay($base, $rot, 0, 1, 1, $tier, ^poh_hedge_b);',
  '63 each at the template\'s own tile and angle'),
 # a tile laid on the wall layer, where the fence already is
 ('tools/genhedge.py', "centrepiece_straight, ^poh_loc_duration);", "wall_straight, ^poh_loc_duration);",
  '63 re-running it changes nothing'),
 # a hedge nobody can take out again
 ('scripts/skill_construction/scripts/poh_hedge.rs2',
  '[oploc5,loc_13476] ~poh_hedge_remove;' + chr(10), '',
  '63 all 21 are removable, none twice'),
 # ...or one wired in both files, which does not compile
 ('scripts/skill_construction/scripts/poh_hedge.rs2',
  '[oploc5,loc_13457] ~poh_hedge_remove;',
  '[oploc5,loc_13457] ~poh_hedge_remove;\n[oploc5,loc_13456] ~poh_hedge_remove;',
  '63 all 21 are removable, none twice'),
 # the hedge sharing the fence's anchor, so building one takes the other's slot
 ('tools/furnspec.json', '"key": "hedge",', '"key": "hedge_x",',
  '63 tools/genhedge.py runs clean'),
 # the anchor drifting from the spec, which is the mistake the rug round left open
 ('scripts/skill_construction/scripts/poh_hedge.rs2',
  'def_coord $base = movecoord($spot, -1, 0, -4);',
  'def_coord $base = movecoord($spot, -1, 0, -3);',
  '63 it steps back from the spec\'s own anchor'),
 # a formal garden hotspot left unclaimed again
 ('tools/furnspec.json', '"hotspots": [\n    15174,\n    15175,\n    15176\n   ],',
  '"hotspots": [\n    15174,\n    15175\n   ],',
  '49 they claim the centrepiece, the four flower spaces, the fencing and the hedging'),
 # ---- 64: the skilling outfits ----
 # THE ONE THE SWEEP FOUND: a piece with no way to get it. Take it out of the drop table and the
 # end-to-end check asks tools/obtainable.py, which says so.
 ('scripts/skilling_outfits/configs/outfits.enum',
  'val=36,carpenters_helm' + chr(10), '',
  '64 every piece of the ten outfits is in the table'),
 # ...and Graceful's cape, the piece that made the stride six in the first place
 ('scripts/skilling_outfits/configs/outfits.enum',
  'val=47,graceful_cape' + chr(10), '',
  '64 Graceful is the six-piece one'),
 # a skilling script going round the funnel - neither the bonus nor the roll reaches it
 ('scripts/areas/area_abyss/scripts/abyss_outer.rs2',
  '~mining_xp(250);', 'stat_advance(mining, 250);',
  '64 nothing outside a quest awards these skills directly'),
 # the same for each of the three new ones: an agility obstacle, a pickpocket and the altar
 ('scripts/skill_agility/scripts/gnome_course.rs2',
  '~agility_xp(75);', 'stat_advance(agility, 75);',
  '64 nothing outside a quest awards these skills directly'),
 ('scripts/skill_thieving/scripts/thieving.rs2',
  '~thieving_xp($experience);', 'stat_advance(thieving, $experience);',
  '64 nothing outside a quest awards these skills directly'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '~prayer_xp(calc(oc_param($bone, bone_exp) * $pct / 100));',
  'stat_advance(prayer, calc(oc_param($bone, bone_exp) * $pct / 100));',
  '64 nothing outside a quest awards these skills directly'),
 # ...and the one that made the carpenter's outfit possible at all
 ('tools/genfurn.py',
  "'~construction_xp(enum(int, int, poh_furn_xp, $item));',",
  "'stat_advance(construction, enum(int, int, poh_furn_xp, $item));',",
  '64 genfurn.py is what writes it'),
 # an outfit rolling for its neighbour, which would quietly hand a miner angler boots
 ('scripts/skilling_outfits/scripts/outfit_xp.rs2',
  '~outfit_roll(^outfit_prospector, $xp);', '~outfit_roll(^outfit_angler, $xp);',
  '64 every experience proc rolls for its own outfit'),
 # a proc that stopped rolling at all
 ('scripts/skilling_outfits/scripts/outfit_xp.rs2',
  '~outfit_roll(^outfit_eye, $xp);' + chr(10), '',
  '64 one roll per proc and no more'),
 # the roll paid on the post-bonus xp, so three pieces make the fourth come faster
 ('scripts/skilling_outfits/scripts/outfit_xp.rs2',
  '~outfit_roll(^outfit_smiths, $xp);', '~outfit_roll(^outfit_smiths, calc($xp + $extra));',
  '64 every experience proc rolls for its own outfit'),
 # a bonus OSRS does not give, on one of the three that give none
 ('scripts/skilling_outfits/scripts/outfit_xp.rs2',
  '~outfit_roll(^outfit_graceful, $xp);\nstat_advance(agility, $xp);',
  '~outfit_roll(^outfit_graceful, $xp);\nstat_advance(agility, calc($xp + $extra));',
  '64 every experience proc rolls for its own outfit'),
 # ...and a bonus quietly dropped from one of the seven that do
 ('scripts/skilling_outfits/scripts/outfit_xp.rs2',
  'def_int $bonus = ~outfit_xp_bonus(prospector_helm, prospector_jacket, prospector_legs, prospector_boots);',
  'def_int $bonus = 0;',
  '64 every experience proc rolls for its own outfit'),
 # the table reordered, so a hat sits in the torso slot
 ('scripts/skilling_outfits/configs/outfits.enum',
  'val=6,angler_hat\nval=7,angler_top', 'val=6,angler_top\nval=7,angler_hat',
  '64 each at its own wearpos slot in hat/torso/legs/feet/hands/back order'),
 # the Smiths' gloves swapped for a piece that is already in another outfit
 ('scripts/skilling_outfits/configs/outfits.enum',
  'val=34,smiths_gloves', 'val=34,prospector_helm',
  '64 and no piece is in two outfits'),
 # a piece the player already banked being given again
 ('scripts/skilling_outfits/scripts/outfit_drop.rs2',
  'if ($piece ! null & ~obj_gettotal($piece) = 0) {\n        $n = calc($n + 1);',
  'if ($piece ! null & inv_total(inv, $piece) = 0) {\n        $n = calc($n + 1);',
  '64 outfit_missing counts what you own everywhere'),
 # ...and a piece found with full hands going nowhere at all
 ('scripts/skilling_outfits/scripts/outfit_drop.rs2',
  'obj_add(coord, $piece, 1, ^lootdrop_duration);', 'mes("Your hands are full.");',
  '64 a piece found with a full inventory goes on the floor'),
 # the rate written into the script instead of the constant
 ('scripts/skilling_outfits/scripts/outfit_drop.rs2',
  'if (random(^outfit_roll_xp) >= $xp) {', 'if (random(50000) >= $xp) {',
  '64 no bare number in the roll'),
 # an outfit index that no longer lines up with the table it keys
 ('scripts/skilling_outfits/configs/outfits.constant',
  '^outfit_carpenters = 6', '^outfit_carpenters = 7',
  '64 the outfits are numbered from zero with no gap'),
 # the stride shortened, which loses Graceful's cape and the Rogue gloves off the end
 ('scripts/skilling_outfits/configs/outfits.constant',
  '^outfit_pieces = 6', '^outfit_pieces = 5',
  '64 ^outfit_count and ^outfit_pieces are every outfit and the six slots'),
 # the guild hunter outfit quietly given a source, which is the reminder this check exists to be
 ('scripts/_unpack/727/all.inv',
  'stock1=pot_empty,5,10',
  'stock1=pot_empty,5,10\nstock2=hunter_headwear,5,10\nstock3=hunter_top,5,10\n'
  'stock4=hunter_legs,5,10\nstock5=hunter_boots,5,10',
  '64 with no disagreement between the spec and what the game can actually give out'),
 # A STORAGE LIST IS NOT A MENTION. Excluding the costume room from `given` was not enough - it
 # still counted as a mention, which demoted seventeen unobtainable objs out of the real list and
 # into "worth a glance", including two Graceful pieces.
 # The check this is written for probes without_storage_lists with an input of its own now, so
 # the mutation breaks the function rather than the data: skip the block and it strips nothing.
 ('tools/obtainable.py',
  "            skip = s[1:-1] in STORAGE_LISTS",
  "            skip = False",
  '64 the mention scan drops a name that only a costume room storage list names'),
 # And the OTHER half of that pair: the function can be perfect and still not be called. This is
 # the mutation the original entry was, kept because unwiring it and breaking it are two faults.
 ('tools/obtainable.py',
  "for w in set(re.findall(r'([a-z][a-z0-9_+]{2,})', without_storage_lists(read(rel)))):",
  "for w in set(re.findall(r'([a-z][a-z0-9_+]{2,})', read(rel))):",
  '64 with the stripping wired into the mention scan itself'),
 # ---- 65: the checkers can go red ----
 # BOTH HISTORICAL INERT RULES, recreated. Each one shipped, did nothing, and the repo printed
 # 0 ERROR through it. The selftest exists so that cannot happen again, so the selftest has to be
 # shown catching them.
 #
 # check 11 read its line variable one statement before it was assigned and reported every hit one
 # line late. A selftest that only asked "did rule 11 appear?" would have passed on this - which is
 # why ALL_RULES pins the line as well as the rule.
 ('tools/rs2check.py',
  '            for m in re.finditer(r"@([a-zA-Z_0-9]+)\\s*[;(]", s):\n                report("ERROR", path, n, 11,',
  '            for m in re.finditer(r"@([a-zA-Z_0-9]+)\\s*[;(]", s):\n                report("ERROR", path, n + 1, 11,',
  '65 rs2check --selftest'),
 # check 17 matched the block header with a pattern a header never satisfies, so the rule was a
 # no-op from the day it was written
 ('tools/rs2check.py',
  'm = re.match(r"^\\[([^\\],]+)\\]\\s*$", raw.strip())',
  'm = re.match(r"^\\[([^\\],]+),([^\\]]+)\\]\\s*$", raw.strip())',
  '65 rs2check --selftest'),
 # and the one this round found: a missing pack turning rules 14 and 14b off without a word
 ('tools/rs2check.py',
  'if empty and not SELFTEST_RUNNING:', 'if False:',
  '65 with synth.pack taken away it STOPS rather than printing 0 ERROR:'),
 # a rule that fires on everything is no better than one that fires on nothing
 ('tools/rs2check.py',
  'if T["player_varps"].get(v, False) and v not in T["other_vars"]:',
  'if True:',
  '65 none of them fires on correct code'),
 # ---- 66: the slayer imbues ----
 # an imbued item that quietly stops inheriting the plain one's melee bonus
 ('scripts/skill_slayer/configs/black_mask.obj',
  'param=slayer_headgear,yes\nparam=slayer_imbued,yes',
  'param=slayer_imbued,yes',
  '66 every piece declares exactly what it is'),
 # ...or the earmuffs, nose peg and facemask, which is eight call sites at once
 ('scripts/skill_slayer/scripts/slayer_helm.rs2',
  'if (oc_param($hat, slayer_helmet) = true) {',
  'if (oc_param($hat, slayer_headgear) = true) {',
  '66 and the protections door does the same'),
 # the plain mask giving the imbued bonus, which would make the imbue worthless
 ('scripts/general/configs/osrs_items.obj',
  'param=slayer_helmet,yes\nparam=imbue_into,slayer_helm_i',
  'param=slayer_helmet,yes\nparam=slayer_imbued,yes\nparam=imbue_into,slayer_helm_i',
  '66 neither plain item claims to be imbued'),
 # the two doors drifting apart - the ranged boost applying off task
 ('scripts/skill_slayer/scripts/black_mask.rs2',
  '[proc,black_mask_imbued_on_task]()(boolean)\nif (~black_mask_on_task = false) {\n    return(false);\n}',
  '[proc,black_mask_imbued_on_task]()(boolean)',
  '66 the ranged/magic door reuses the melee door'),
 # the boost on the accuracy roll but not the damage
 ('scripts/skill_combat/scripts/player/player_ranged.rs2',
  '    $maxhit = scale($mask_num, $mask_div, $maxhit);' + chr(10), '',
  '66 and on the max hit too (ranged)'),
 # ...or on one roll in a file but not the other
 ('scripts/skill_combat/scripts/player/player_magic.rs2',
  'if (~player_npc_hit_roll_boosted(^magic_style, $mask_num, $mask_div) = true) {\n    def_int $maxhit = scale($mask_num, $mask_div, ~magic_spell_maxhit($spell_data));',
  'if (~player_npc_hit_roll(^magic_style) = true) {\n    def_int $maxhit = ~magic_spell_maxhit($spell_data);',
  '66 on every roll in the file, not some of them (magic)'),
 # the wrong percentage
 ('scripts/skill_combat/scripts/player/player_ranged.rs2',
  '    $mask_num = 23;\n    $mask_div = 20;', '    $mask_num = 7;\n    $mask_div = 6;',
  '66 at 23/20, which is the 15% OSRS gives (ranged)'),
 # THE MISTAKE ACTUALLY MADE WRITING THIS: a block reading a local another block declared
 ('scripts/skill_combat/scripts/player/player_magic.rs2',
  '// Its own lookup: this is a different proc from the single-target cast above, so that one\'s\n// $mask_num is not in scope here. Each extra target of a multi-target spell rolls separately, so\n// the mask has to be asked again for each of them anyway.\ndef_int $mask_num = 1;\ndef_int $mask_div = 1;\nif (~black_mask_imbued_on_task = true) {\n    $mask_num = 23;\n    $mask_div = 20;\n}\n',
  '',
  '66 every block that reads $mask_num declares it'),
 # ---- the Scroll of imbuing, which replaced that purchase ----
 # the points imbue growing back
 ('scripts/skill_slayer/configs/slayer.constant',
  '^imbue_scroll_hitpoints = 150000', '^imbue_scroll_hitpoints = 150000\n^slayer_imbue_cost = 1250',
  '66 the points imbue is gone: no price constant, no Buy row constant, no purchase proc'),
 # a pair that points only one way - the single mistake this shape can make
 ('scripts/skill_slayer/configs/imbue_scroll.obj',
  'param=imbue_from,seer_ring\n', '',
  '66 every imbue pair points both ways'),
 # an item that can be imbued and was never thought about. It is paired to ITSELF on purpose: a
 # half-pair would be caught by the both-ways check above instead, which proves nothing about this
 # one. A self-pair is well-formed and still wrong.
 ('scripts/general/configs/osrs_items.obj',
  "desc=If rocks could feel fear, they'd fear this.",
  "desc=If rocks could feel fear, they'd fear this.\nparam=imbue_into,dragon_pickaxe\nparam=imbue_from,dragon_pickaxe",
  "66 and they are the 22 items OSRS's scroll list leaves this build"),
 # OSRS's OWN number for the seers ring instead of double THIS build's ring
 ('scripts/skill_slayer/configs/imbue_scroll.obj',
  'param=magicattack,8\nparam=magicdefence,8', 'param=magicattack,12\nparam=magicdefence,12',
  '66 each imbued ring is its plain ring doubled, stat for stat'),
 # an imbued item you cannot get the scroll back out of
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  '[opheld4,seer_ring_i] @imbue_uncharge;\n', '',
  '66 Uncharge is on the five items the cache gives it to'),
 # an Uncharge op invented for the helmets, which no slayer helmet in the cache has
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  '[opheld4,black_mask_i] @imbue_uncharge;',
  '[opheld4,black_mask_i] @imbue_uncharge;\n[opheld5,slayer_helm_i] @imbue_uncharge;',
  '66 Uncharge is on the five items the cache gives it to'),
 # ...and the op in a slot of its own invention rather than the cache's
 ('scripts/skill_slayer/configs/imbue_scroll.obj',
  'iop2=Wear\niop4=Uncharge\nmembers=yes\ntradeable=no\n2dxof=3\n2dyof=-15',
  'iop2=Wear\niop3=Uncharge\nmembers=yes\ntradeable=no\n2dxof=3\n2dyof=-15',
  '66 ...in op slot 4, where OSRS puts it, and the trigger is on the same slot as the op'),
 # the helmets left with no route out at all: Disassemble stops handing the imbued mask back
 ('scripts/skill_slayer/scripts/slayer_helm.rs2',
  '[opheld4,slayer_helm_i] @slayer_helm_split(black_mask_i);',
  '[opheld6,slayer_helm_i] @slayer_helm_split(black_mask_i);',
  '66 and no imbued helmet has one - all 16 get the scroll back out through Disassemble'),
 # the imbued rings back on the plain rings' meshes, which is how they shipped
 ('scripts/skill_slayer/configs/imbue_scroll.obj',
  'model=obj_seer_ring_i', 'model=obj_seer_ring',
  "66 and wears its own imported mesh rather than the plain ring's"),
 # an invented suffix on an imbued ring's examine text
 ('scripts/skill_slayer/configs/imbue_scroll.obj',
  'desc=A legendary ring once worn by Fremennik warriors.',
  'desc=A legendary ring once worn by Fremennik warriors. It has been imbued.',
  "66 ...and the plain ring's examine text, which is what the cache does"),
 # the handoff removed, so the scroll works in one click order and not the other
 ('scripts/skill_slayer/scripts/slayer_helm.rs2',
  'if (last_useitem = slayer_imbue_scroll) {\n    ~imbue_scroll_read(last_item);\n    return;\n}\n',
  '',
  '66 the use is one trigger on the scroll, and the one imbueable item with an [opheldu] of its own hands the scroll on'),
 # a pair named in the script, which is what the params exist to avoid
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  'def_namedobj $into = oc_param($target, imbue_into);',
  'def_namedobj $into = null;\nif ($target = black_mask) {\n    $into = black_mask_i;\n}',
  '66 and both halves read the param, so no pair is named in the script'),
 # an already-imbued item falling through to "nothing interesting happens"
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  '    if (oc_param($target, imbue_from) ! null) {\n        mes("Your <lowercase(oc_name($target))> is already imbued.");\n        return;\n    }\n',
  '',
  '66 and an item that is already imbued says so rather than nothing interesting happening'),
 # a flat per-kill rate, which would make Turael's rats the fastest scroll farm in the game
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  'if (random(^imbue_scroll_hitpoints) >= npc_basestat(hitpoints)) {',
  'if (random(^imbue_scroll_hitpoints) ! 0) {',
  "66 the drop is weighted by the kill's hitpoints"),
 # rolled on the whole kill but not on the split one
 ('scripts/skill_slayer/scripts/slayer_task.rs2',
  '    ~imbue_scroll_kill_roll;\n    if(%slayer_count = 0) ~complete_task;\n    ~slayer_superior_roll(npc_type);\n',
  '    if(%slayer_count = 0) ~complete_task;\n    ~slayer_superior_roll(npc_type);\n',
  '66 and it is rolled from both on-task kill queues'),
 # ...and rolled somewhere an off-task kill can reach
 ('scripts/skill_combat/scripts/npc/npc_death.rs2',
  '~check_progress_task(npc_param(slayer_category));',
  '~check_progress_task(npc_param(slayer_category));\n~imbue_scroll_kill_roll;',
  '66 ...so an off-task kill can never give one'),
 # the superior's own rate taken away, leaving it just a bigger monster
 ('scripts/skill_slayer/scripts/superiors.rs2',
  '~imbue_scroll_superior_roll;', '',
  '66 a superior rolls a flat rate of its own on top of that'),
 # a rate written twice
 ('scripts/skill_slayer/scripts/imbue_scroll.rs2',
  'random(^imbue_scroll_superior_odds)', 'random(15)',
  '66 both rates are constants and neither value is written again in the script'),
 # assembling an imbued mask into a PLAIN helmet, silently spending what the player paid for
 ('scripts/skill_slayer/scripts/slayer_helm.rs2',
  'def_namedobj $helm = slayer_helm;\nif ($mask = black_mask_i) {\n    $helm = slayer_helm_i;\n}',
  'def_namedobj $helm = slayer_helm;',
  '66 and an imbued mask makes an imbued helmet'),
 # ...and the same on the way out
 ('scripts/skill_slayer/scripts/slayer_helm.rs2',
  '[opheld4,slayer_helm_i] @slayer_helm_split(black_mask_i);',
  '[opheld4,slayer_helm_i] @slayer_helm_split(black_mask);',
  '66 and disassembly hands back the mask that went in'),
 # NO MUTATION FOR "the sweep finds a real source for both imbued items", ON PURPOSE.
 #
 # Two were tried. Swapping the HELMET's line strands nothing - you can still imbue a mask and
 # assemble it, so the check was right and the mutation was wrong. Swapping the MASK's line does
 # strand both in the game, but not in tools/obtainable.py: the mask is still passed as a label
 # argument by @slayer_helm_split(black_mask_i), and the sweep counts a bare mention in a file that
 # gives items out, deliberately, because following every call is what it does not attempt. Its own
 # docstring says so and splits its output into two lists for exactly this reason.
 #
 # So that check catches the common case - an item nothing references at all, which is the shape all
 # 47 skilling outfit pieces were in - and cannot catch a circular one. Writing a mutation that
 # passes by breaking something else would be worse than admitting the gap.
 # the stats copied rather than compared - a defence quietly different from the plain item
 ('scripts/general/configs/osrs_items.obj',
  'param=magicattack,3\nparam=rangeattack,3\nparam=stabdefence,30',
  'param=magicattack,3\nparam=rangeattack,3\nparam=stabdefence,31',
  '66 slayer_helm_i keeps the plain item\'s defences exactly'),
 # ---- 67: every slayer helmet colour ----
 # a colour wearing the plain helmet's model again, which is the whole bug this round fixed: the
 # first version repainted two colours on the plain mesh and three helmets came out looking alike
 ('scripts/skill_slayer/configs/slayer_helm_colours.obj',
  'model=obj_slayer_helm_red\nmanwear=obj_slayer_helm_red_manwear,0',
  'model=obj_slayer_helm\nmanwear=obj_slayer_helm_manwear,0',
  "67 every colour carries its OWN five models, not the plain helmet's"),
 # a colour quietly pointed at another colour's art - the config and the spec would agree with each
 # other and only the recorded geometry notices
 ('tools/slayerhelmspec.json',
  '"models": "purple"', '"models": "hydra"',
  '67 every model is the shape the import recorded for it'),
 # a recolour source that matches no face - the helmet comes out unchanged and nothing errors
 ('scripts/skill_slayer/configs/slayer_helm_colours.obj',
  'recol1s=29695', 'recol1s=29694',
  '67 recolour pairs, all hitting real faces'),
 # a colour that is not the plain helmet underneath - here one that loses a wear position, which in
 # game means it stops hiding the player's hair and the helmet grows a fringe
 ('scripts/skill_slayer/configs/slayer_helm_colours.obj',
  '[slayer_helm_black]', '[slayer_helm_black]\nwearpos2=head\n',
  '67 each inherits every stat, op and gate from the plain helmet'),
 # a recolour anyone can do without the unlock they paid for
 ('scripts/skill_slayer/scripts/slayer_helm_colours.rs2',
  'if (~slayer_has_unlock(5) = false) {\n    mes("You need the Unholy Helmet unlock from a Slayer master to do that.");\n    return;\n}\n',
  '',
  '67 red needs its unlock (bit 5)'),
 # ...or one that does not use up the head
 ('scripts/skill_slayer/scripts/slayer_helm_colours.rs2',
  'inv_del(inv, abyssal_head, 1);' + chr(10), '',
  '67 ...and uses up the abyssal_head'),
 # an imbued helmet losing its imbue when recoloured - the player paid for that
 ('scripts/skill_slayer/scripts/slayer_helm_colours.rs2',
  'def_namedobj $into = slayer_helm_red;\nif (inv_total(inv, slayer_helm_i) > 0) {\n    $into = slayer_helm_red_i;\n}',
  'def_namedobj $into = slayer_helm_red;',
  '67 ...and an imbued helmet stays imbued through it'),
 # a colour nothing can make pretending it can - a disassemble that hands back a head that does not
 # exist in any inventory, out of an item there is no way to have obtained honestly
 ('scripts/skill_slayer/scripts/slayer_helm_colours.rs2',
  '[opheld4,slayer_helm_black] @slayer_helm_split_headless(black_mask);',
  '[opheld4,slayer_helm_black] @slayer_helm_split_coloured(black_mask, abyssal_head);',
  '67 all 28 disassemble into exactly what went into them'),
 # a drop rate that is not OSRS's
 ('scripts/drop_tables/scripts/abyssal_demon.rs2',
  'if (random(6000) = 0) {', 'if (random(600) = 0) {',
  "67 abyssal_head drops at 1/6000, which is OSRS's own rate"),
 # The chat menu that held this switch is gone - the Cosmetics tab of the rewards window reads the
 # price out of a table now, so the drift to guard against is that table against the spec.
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_cosmetic_cost]\ninputtype=int\noutputtype=int\ndefault=0\nval=0,1000',
  '[slayer_cosmetic_cost]\ninputtype=int\noutputtype=int\ndefault=0\nval=0,500',
  '67 ...on bit 5 for 1000 points, the numbers the recolour itself reads'),
 # a colour with no source turning up in the tab, which would sell an unlock that unlocks nothing
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1,Kalphite Khat\n', 'val=1,Kalphite Khat\nval=2,Tzkal Helmet\n',
  '67 the Cosmetics tab is exactly the colours you can unlock'),
 # two unlocks sharing a bit, so buying one gives both
 ('tools/slayerhelmspec.json', '"bit": 6', '"bit": 5',
  '67 on unlock bits nothing else uses'),
 # a colour that forgets it is a helmet - eight protections lost at once
 ('scripts/skill_slayer/configs/slayer_helm_colours.obj',
  '[slayer_helm_tzkal]\nname=Tzkal slayer helmet', '[slayer_helm_tzkal]\nname=Tzkal slayer helmet\nparam=slayer_imbued,yes',
  '67 every piece declares exactly what it is'),
 # a door going back to naming items, which is what stops a new colour working
 ('scripts/skill_slayer/scripts/black_mask.rs2',
  'if (oc_param($hat, slayer_headgear) = true) {',
  'if ($hat = black_mask | $hat = slayer_helm) {',
  '67 ~black_mask_on_task reads slayer_headgear'),
 # the sweep quietly dropping the deliberate ones instead of naming them, which is what an
 # exception list turns into: twelve colours would vanish from the report rather than be accounted
 # for, and the day one of them gets a source nothing would say the spec is out of date
 ('tools/obtainable.py',
  '    spec = json.loads(read(\'tools/slayerhelmspec.json\'))',
  '    return set(), []\n    spec = json.loads(read(\'tools/slayerhelmspec.json\'))',
  '67 and names the other 22 as deliberate, by name'),
 ]

# ---- 64b: what the three outfits that pay no experience do instead ---------------------------
# Appended rather than written into the literal above, because entries in that list contain rs2
# source with brackets and blank lines at column 0 - there is no reliable way to find its end by
# text, and a script that guesses wrong silently drops entries.
#
# NOT MUTATED HERE, deliberately: group 64b's four engine-side checks and its packed-artefact
# check read a sibling clone and a built cache, and no mutation to THIS tree can change either.
# They were proved by hand instead - a graceful weight edited, the build re-run, and
# tools/objpacked.py watched going red - which is written down in the project doc rather than
# implied by a green line here.
MUTS += [
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  '[proc,rogue_worn]()(int)\ndef_int $count = 0;',
  '[proc,graceful_worn]()(int)\nreturn(inv_total(worn, graceful_hood));\n\n'
  '[proc,rogue_worn]()(int)\ndef_int $count = 0;',
  '64b Graceful is not scripted'),
 ('scripts/skill_thieving/scripts/thieving.rs2',
  'if (~rogue_doubles = true) {\n    $multiplier = 2;\n}',
  'if (false = true) {\n    $multiplier = 2;\n}',
  '64b a pickpocket asks the Rogue outfit whether its loot doubles'),
 ('scripts/skill_thieving/scripts/thieving.rs2',
  'inv_add(inv, $reward, calc($quantity_roll * $multiplier));',
  'inv_add(inv, $reward, $quantity_roll);',
  '64b the roll happens once for the theft'),
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  'if (inv_getobj(worn, ^wearpos_hands) = rogue_gloves) {',
  'if (inv_getobj(worn, ^wearpos_torso) = rogue_gloves) {',
  '64b all five Rogue pieces are counted'),
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  'if ($worn >= ^rogue_full_pieces) {\n    return(^rogue_double_full);\n}\n',
  '',
  '64b the fifth piece is worth more than the other four'),
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  'if (random(100) < $chance) {',
  'if (random(100) < 15) {',
  '64b and no chance in this file is a bare number'),
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  'if (inv_getobj(worn, ^wearpos_legs) = zealots_bottom & random(^zealots_save_denom) = 0) {',
  'if (inv_getobj(worn, ^wearpos_feet) = zealots_bottom & random(^zealots_save_denom) = 0) {',
  "64b every Zealot's piece is looked for in its own slot"),
 ('scripts/skilling_outfits/scripts/outfit_effects.rs2',
  'if (inv_getobj(worn, ^wearpos_torso) = zealots_top & random(^zealots_save_denom) = 0) {',
  'if (inv_getobj(worn, ^wearpos_torso) = zealots_top) {',
  '64b and each of them rolls separately'),
 ('scripts/skill_prayer/scripts/bury_bone.rs2',
  'def_boolean $saved = ~zealots_saves;',
  'def_boolean $saved = false;',
  "64b Zealot's robes get their chance when burying a bone"),
 ('scripts/skill_prayer/scripts/bury_bone.rs2',
  'if ($saved = false) {\n    inv_delslot(inv, $slot);\n}',
  'inv_delslot(inv, $slot);',
  '64b and the remains are only used up when they did not save it, burying a bone'),
 ('scripts/skill_prayer/scripts/bury_bone.rs2',
  '~prayer_xp(oc_param($last_item, bone_exp));',
  'if ($saved = false) {\n    ~prayer_xp(oc_param($last_item, bone_exp));\n}',
  '64b while the experience is paid whichever way it went, burying a bone'),
 # The altar half is GENERATED, so the mutation goes in the generator: an edit to
 # poh_furn_ops.rs2 is overwritten by the battery's own regenerate before any check can see it,
 # which would read as a surviving mutation and be nothing of the kind.
 ('tools/genfurn.py',
  "'def_boolean $saved = ~zealots_saves;',",
  "'def_boolean $saved = false;',",
  '64b genfurn.py is what writes the altar call'),
]


# ---- 64b, second pass: Graceful pays 50% and the numbers are checked without a build ---------
_G_OBJ = 'scripts/skilling_outfits/configs/outfits.obj'
_G_CON = 'scripts/skilling_outfits/configs/outfits.constant'
_G_EFF = 'scripts/skilling_outfits/scripts/outfit_effects.rs2'
_G_SPEC = 'tools/gracefulspec.json'
_G_BAT = 'tools/poh_battery.py'

# WHAT CHANGED SINCE THE NOTE ABOVE. That note says the artefact and engine checks cannot be
# mutated from this tree, and that is still true. But the sandbox CAN build now, so the checks
# added in this round read the configs and tools/gracefulspec.json and every one of them is
# reachable from here.
#
# The anchors below were each confirmed to appear EXACTLY ONCE in their file before being written
# down. This harness replaces the first match and has no uniqueness rule of its own - the rule
# lives in tools/follower_mutate.py and tools/gamemode_mutate.py - so it is done by hand here.
#
# A NOTE ON DOUBLE CATCHES. A mutation to the spec makes tools/objpacked.py go red too, because
# that tool compares the real artefact against the spec in THIS tree. That is not a problem: the
# harness attributes by matching the named check's own text against the FAIL lines, so the entry
# is still reported as caught by its own check. It is written down because a reader seeing two
# red lines should know why.
MUTS += [
 # --- the spec has to add up before anything is compared to it
 (_G_SPEC, '"graceful_cape": 8,', '"graceful_capelet": 8,',
  "64b the spec names all six Graceful pieces and nothing else"),
 (_G_SPEC, '"total_pct": 50,', '"total_pct": 45,',
  "64b the spec's per-piece numbers add up to the total it claims"),
 # sum AND claimed total moved together to 45, so the only thing wrong is that 45 is not the
 # number Corey asked for - which is the one check this entry is for
 (_G_SPEC,
  '"graceful_legs": 10,\n      "graceful_top": 10,\n      "graceful_boots": 8,\n'
  '      "graceful_cape": 8,\n      "graceful_hood": 7,\n      "graceful_gloves": 7\n'
  '    },\n    "total_pct": 50,',
  '"graceful_legs": 9,\n      "graceful_top": 9,\n      "graceful_boots": 7,\n'
  '      "graceful_cape": 7,\n      "graceful_hood": 7,\n      "graceful_gloves": 6\n'
  '    },\n    "total_pct": 45,',
  "64b and that total is the 50 percent Corey asked for by name"),
 (_G_SPEC, '"full_set_total_pct": 30,', '"full_set_total_pct": 40,',
  "64b with OSRS's own figures recorded beside it as the thing being departed from"),

 # --- the configs agree with the spec, piece by piece
 # TWO PIECES SWAPPED, total untouched: 10+10 becomes 13+7. This is the mutation the per-piece
 # check exists for - a total-only check would call this correct.
 (_G_SPEC, '"graceful_legs": 10,\n      "graceful_top": 10,',
        '"graceful_legs": 13,\n      "graceful_top": 7,',
  "64b each piece's energy_restore in outfits.obj is the number the spec derived for it"),
 (_G_OBJ, 'param=energy_restore,7\ncost=30', 'param=energy_restore,9\ncost=30',
  "64b and the six together come to the full-set total, read out of the config"),
 (_G_OBJ, 'param=energy_restore,7\ncost=35', 'cost=35',
  "64b all six Graceful blocks carry one weight= and one energy_restore line"),

 # --- the shape, read off the config's own weight lines
 # legs take the most weight off and would recover the least
 (_G_OBJ, 'weight=-6kg\nparam=energy_restore,10', 'weight=-6kg\nparam=energy_restore,6',
  "64b recovery never goes down as the weight reduction goes up"),
 # boots and the cape both take 4kg off; only the cape's recovery moves
 (_G_OBJ, 'param=energy_restore,8\ncost=40\nmembers=yes\ntradeable=no\niop2=Wear\n'
       'category=armour_cape',
       'param=energy_restore,7\ncost=40\nmembers=yes\ntradeable=no\niop2=Wear\n'
       'category=armour_cape',
  "64b and two pieces that take the same weight off recover the same"),
 (_G_OBJ, 'weight=-6kg', 'weight=-7kg',
  "64b every piece's weight= is still exactly OSRS's"),

 # --- the sweeps, and their guards
 # THE GUARD IS MUTATED IN THE CHECKER ITSELF, which is the only place it can be: a guard that
 # says "the sweep found something" is a claim about the sweep, not about the tree.
 (_G_BAT, "for _rel, _t in _walk('.obj'):", "for _rel, _t in _walk('.obj-nothing'):",
  "64b the sweep below actually walked the obj configs"),
 (_G_OBJ, '[rogue_mask]', '[rogue_mask]\nparam=energy_restore,5',
  "64b and no obj config in the tree carries energy_restore but the six and their colours"),
 (_G_BAT, "for _rel, _t in _walk('.rs2'):", "for _rel, _t in _walk('.rs2-nothing'):",
  "64b and that sweep read the whole script tree rather than a handful"),
 (_G_EFF, '[proc,zealots_saves]',
        '[proc,graceful_restore_of](obj $obj)(int)\n'
        'return(oc_param($obj, energy_restore));\n\n[proc,zealots_saves]',
  "64b and no script anywhere reads energy_restore"),

 # --- the departure is written down where somebody would look
 (_G_CON, 'DEPARTURE', 'Departure',
  "64b outfits.constant's Graceful note says what this build pays and what OSRS pays"),
 (_G_EFF, '+50% natural run energy recovery (OSRS pays 30%).',
       '+50% natural run energy recovery.',
  "64b and the header of outfit_effects.rs2"),
 (_G_CON, 'tools/gracefulspec.json', 'the notes somewhere',
  "64b and points at the spec that holds the arithmetic"),

 # --- the model of the engine's arithmetic notices when the engine's arithmetic moves
 # The quoted line is broken in the SIM, which is the same thing as the engine's line changing as
 # far as the sim can tell - it compares the two and has nothing else to go on.
 ('tools/gracefulsim.py',
  "LOSS = 'const loss = (67 + (67 * clampWeight) / 64) | 0;'",
  "LOSS = 'const loss = (67 + (67 * clampWeight) / 65) | 0;'",
  "64b gracefulsim.py still recognises every line of updateEnergy() it models"),
]


# ---- 68: every obj can be got, or says why not -----------------------------------------------
MUTS += [
 ('tools/nosourcespec.json', '"macro_mime_mask": {', '"macro_mime_mask_GONE": {',
  '68 no obj in the game is unobtainable without a reason recorded for it'),
 ('tools/nosourcespec.json',
  '"why": "the Mime is not one of the 26 random events this build implements',
  '"why": "x", "_why": "the Mime is not one of the 26 random events this build implements',
  '68 and every entry that excuses one says why'),
 ('tools/nosourcespec.json', '"osrs_source": "the Mime random event, seven completions',
  '"_osrs_source": "the Mime random event, seven completions',
  '68 and what OSRS does instead'),
 ('scripts/skill_farming/scripts/farming_actions.rs2',
  'if (inv_total(inv, fairy_enchanted_secateurs) > 0) {',
  'if (inv_total(inv, magic_secateurs) > 0) {',
  '68 nothing in the game wires the duplicate magic secateurs'),
 ('scripts/macro events/scripts/woodcutting/macro_event_lost_axe.rs2',
  'if ($axe_head = null) {\n    return;\n}\n', '',
  '68 the lost-axe event leaves the axe alone when it has no head to drop'),
 ('scripts/macro events/scripts/mining/macro_event_lost_pickaxe.rs2',
  'if ($pickaxe_head = null) {\n    return;\n}\n', '',
  '68 and the lost-pickaxe event does the same'),
 ('scripts/skill_woodcutting/configs/axes/axes.obj',
  'param=axe_head,macro_dragon_hatchethead\n', '',
  '68 every axe the woodcutting checker can hand back names an axe_head'),
 ('scripts/skill_woodcutting/configs/axes/axes.obj',
  'param=axe_handle,macro_hatchethandle_dragon\n', '',
  '68 the dragon axe names its own handle'),
 ('scripts/macro events/scripts/woodcutting/macro_event_lost_axe.rs2',
  '[opheldu,macro_dragon_hatchethead] @check_axe_head;\n', '',
  '68 and the dragon head is accepted by both handles and by its own opheldu'),
 # One occurrence, so the plain handle's switch loses a head and the dragon handle's keeps it -
 # which is exactly the hole the whole-file version of this check could not see.
 ('scripts/macro events/scripts/woodcutting/macro_event_lost_axe.rs2',
  'macro_black_hatchethead, ', '',
  '68 and every axe head in the game is accepted by BOTH handles'),
]


# ---- 69: eight greegrees, one recipe ---------------------------------------------------------
MUTS += [
 ('scripts/quests/quest_mm/configs/mm_greegree.enum',
  'val=mm_bearded_gorilla_monkey_bones,mm_monkey_greegree_for_bearded_gorilla\n', '',
  '69 and every one of them has a relic that makes it'),
 ('scripts/quests/quest_mm/configs/quest_mm.obj',
  'param=mm_transmog_npc,mm_transmogrification_bearded_gorilla',
  'param=mm_transmog_npc,mm_transmogrification_normal_gorilla',
  '69 and no two of them name the same monkey'),
 # THE PIN ON THE CACHE: give a form the wrong animation set and the check has to notice, because
 # nothing else will until someone watches themselves walk.
 ('scripts/quests/quest_mm/scripts/mm_stage3.rs2',
  'case mm_transmogrification_normal_gorilla, mm_transmogrification_bearded_gorilla, mm_transmogrification_ancient_monkey : ~mm_bas(m_gorilla_ready, m_gorilla_walk);',
  'case mm_transmogrification_normal_gorilla, mm_transmogrification_bearded_gorilla, mm_transmogrification_ancient_monkey : ~mm_bas(monkey_ready, monkey_walk);',
  "69 every form's animation set is the one that form's own npc config asks for"),
 ('scripts/quests/quest_mm/scripts/mm_stage3.rs2',
  'case mm_transmogrification_small_ninja_monkey, mm_transmogrification_medium_ninja_monkey : ~mm_bas(m_monkey_ready, m_monkey_walk);\n',
  '',
  '69 and they are not all the same set, which is the mistake this replaced'),
 ('scripts/quests/quest_mm/scripts/mm_stage3.rs2',
  'def_namedobj $head = enum(obj, namedobj, mm_greegree_for, $relic);',
  'def_namedobj $head = mm_monkey_greegree_for_normal_monkey;',
  '69 the carve reads which head to make out of the table'),
 ('scripts/quests/quest_mm/scripts/mm_stage3.rs2',
  '    @mm_zooknock_carve;\n}\nif (%mm_main < ^mm_has_talisman) {',
  '    return;\n}\nif (%mm_main < ^mm_has_talisman) {',
  '69 and Zooknock carves again after the quest is over'),
 ('scripts/_unpack/377/all.npc',
  'param=death_drop,mm_bearded_gorilla_monkey_bones',
  'param=death_drop,mm_normal_gorilla_monkey_bones',
  '69 mm_religious_trapdoor_guard drops mm_bearded_gorilla_monkey_bones'),
 ('tools/nosourcespec.json',
  '"magic_secateurs": {',
  '"mm_monkey_greegree_for_normal_gorilla": {"why": "x", "osrs_source": "x"},\n  "magic_secateurs": {',
  '69 no greegree is excused as sourceless any more'),
]


def checker_for(why):
    if why.endswith('(rs2check)'):
        return 'tools/rs2check.py'
    if why.endswith('(build sim)'):
        return 'tools/poh_build_sim.py'
    if why.endswith('(furn sim)'):
        return 'tools/poh_furn_sim.py'
    return 'tools/poh_battery.py'

def main():
    # one copy of the tree, not one per mutation: the repo has 24k files in it and copying it
    # fifteen times turns a two-second test into a four-minute one
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    # A FULL RUN TAKES OVER AN HOUR now that the battery drives five generators. An argument
    # filters by the why string, which is how one round's entries get run on their own:
    #     python3 tools/poh_mutate.py 67
    only = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--shard') else None
    # SHARDING, so the full sweep can finish. 266 mutations at about a minute and a half each is
    # six and a half hours, past any CI job's timeout - and the reason this harness has never once
    # run to completion. --shard i/n takes every nth entry starting at i, so four runners bring it
    # under two hours each and none of them can lose another's work.
    shard = None
    for k, a in enumerate(sys.argv):
        if a == '--shard' and k + 1 < len(sys.argv):
            shard = tuple(int(x) for x in sys.argv[k + 1].split('/'))
    muts = [m for m in MUTS if not only or only in m[3]]
    if shard:
        muts = [m for k, m in enumerate(muts) if k % shard[1] == shard[0]]
        print('shard %d of %d: %d of %d mutations' % (shard[0], shard[1], len(muts), len(MUTS)))
    if only:
        print('running %d of %d mutations matching %r' % (len(muts), len(MUTS), only))
    fails = 0
    loose = 0
    for path, find, repl, why in muts:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        # A MUTATION TO A GENERATED FILE CANNOT BE RUN HERE. The battery re-runs the generators
        # before it checks anything, so the edit is overwritten before the check under test can
        # look at it - and group 38's "re-running it changes nothing" fires instead, which makes
        # the mutation read as caught while nothing it claims to test was tested. Two entries were
        # in exactly that state and had been for as long as they existed.
        #
        # Those are marked (spec) and belong to tools/poh_mutate_spec.py, which edits the spec the
        # generator reads, regenerates, and only then runs the battery - the sequence a person
        # would actually produce. Skipped here rather than silently mislabelled.
        if why.endswith('(spec)'):
            print('  -     %-62s %s' % (why, 'run by poh_mutate_spec.py, not here'))
            continue
        checker = checker_for(why)
        if f not in raw:
            print('  SKIP (pattern not found) %-44s %s' % (path, why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        # rs2check takes the current directory as the script root, and refuses to run anywhere
        # else - see the note beside engine.rs2 in it.
        cwd = os.path.join(W, 'scripts') if checker.endswith('rs2check.py') else W
        # POINT THE CHECKERS AT THE REAL ENGINE. Some checks read the engine source or the packed
        # data, which live in a SIBLING clone of this tree - and W is a scratch copy with no
        # sibling, so a plain run would have those checks go red for every mutation and drown out
        # the one under test. That is the "a shared check absorbs the individual ones" fault, and
        # it would have made this whole harness useless the moment group 64b landed.
        #
        # The consequence, stated rather than hidden: a mutation here cannot change the engine or
        # the packed artefact, so the engine-side and artefact checks are never the ones that
        # catch anything below. They are proved by hand instead - edit a weight, rebuild, watch
        # tools/objpacked.py go red - and that is recorded in the project doc rather than here.
        r = subprocess.run([sys.executable, os.path.join(W, checker)], capture_output=True,
                           text=True, cwd=cwd, env=dict(os.environ, LOSTCITY_ENGINE=ENGINE))
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        # WHICH check went red matters. A mutation that trips some OTHER check still exits
        # non-zero, so counting exit codes alone proves only that something noticed - not that
        # the check this mutation was written for is doing anything. The why string carries the
        # text of that check after its group number; if a FAIL line contains it, say so.
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in f for f in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'
            fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:60] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-46s %-20s %s' % (state, why, os.path.basename(checker), note))
    print()
    if loose:
        print('%d caught by a check other than the one named - see the note beside each' % loose)
    print('%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
