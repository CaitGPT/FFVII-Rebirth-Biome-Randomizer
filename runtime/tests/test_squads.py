"""Squad selection: synthetic fixtures. Spawning and fighting the squad enemies is tested in the game."""
from pathlib import Path
import hashlib
import re
import unittest
from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / 'Scripts'

# The plan the owner approved (2026-11-08), by enemy name: always, chapter select adds, from a chapter on.
SECURITY, GRENADIER, ELITE_GRENADIER, RIOT, FLAME, OPERATOR = 'SecuritySoldier_Standard', 'GrenadeSoldier_Standard', \
    'GrenadeSoldier_Senior', 'ShieldSoldier_Standard', 'ShieldSoldier_Flame', 'Soldier3rd_2ndEnd2'
J_SECURITY, J_ELITE, J_GRENADIER, J_RIOT = 'SecuritySoldier_JunonEnd2', 'SecuritySoldier_SeniorJunonEnd2', \
    'GrenadeSoldier_JunonEnd2', 'ShieldSoldier_JunonEnd2'
SWEEPER, SLUGRAY, SLUGRAY_G, SCRUTINEYE = 'Sweeper_Standard', 'StunRay_Standard', 'StunRay_GroundtypeEnd2', 'MonoDrive_ScrutinEyeEnd2'
BANDITS = {'Vice_Standard_Scimitar', 'Vice_Standard_IronPipe', 'Vice_VariationA_Axe', 'Vice_VariationB', 'Vice_VariationB_SpikedBat'}
THUGS = {'CorneoLackey_GreedAEnd2', 'CorneoLackey_GreedBEnd2', 'CorneoLackey_GreedCEnd2'}
PLAN = {
    ('1100-MIDGA', 'Grassland_midgamob_01'): ({SECURITY, GRENADIER, SLUGRAY}, {RIOT, FLAME, SLUGRAY_G}, set()),
    ('1200-GRASA', 'Grassland_mob_05'): (BANDITS, set(), set()),
    ('1300-JUNOA', 'JunonArea_mob_01'): ({J_SECURITY, J_GRENADIER, J_RIOT, SWEEPER, SLUGRAY}, {SLUGRAY_G}, {J_ELITE}),
    ('2200-CORLA', 'Corla_desert_mob_01'): (BANDITS | THUGS, set(), set()),
    ('2200-CORLA', 'Corla_southem_mob_01'): ({SECURITY, GRENADIER, FLAME, SLUGRAY, SCRUTINEYE}, {ELITE_GRENADIER, SLUGRAY_G}, set()),
    # Owner, 2026-11-08: no squads in Gongaga (a jungle) or Cosmo Canyon.
    ('2400-GONGA', 'Gongaga_west_mob_01'): (set(), set(), set()),
    ('2500-CSMOA', 'Cosmo_mob_01'): (set(), set(), set()),
    ('2600-NIBLA', 'Nibel_mob_01'): ({SECURITY, GRENADIER, RIOT, FLAME, SCRUTINEYE, SLUGRAY, SWEEPER}, {OPERATOR, SLUGRAY_G}, set()),
}

# A three-slot camp in each squad kind, to see slots and the Sweeper rule.
POOLS = '''{
 {asset='/Game/DataObject/Field/1300-JUNOA/EnemyTerritory.EnemyTerritory',region='1300-JUNOA',names={'mobjunon_Formula_00','mobjunon_Bird_00'},unlocks={},
  camps={{id='JunonArea_mob_01',base={{0,1},{0,1},{0,1}},extra={{},{},{}},totals={3,4,5},original='t:0.1.0/c:1.1.1'}}},
 {asset='/Game/DataObject/Field/2200-CORLA/EnemyTerritory.EnemyTerritory',region='2200-CORLA',names={'mobcorla_Cactuar_00'},unlocks={},
  camps={{id='Corla_desert_mob_01',base={{0},{0}},extra={{},{}},totals={2,3},original='t:0.0/c:1.1'},
         {id='Corla_southem_mob_01',base={{0},{0}},extra={{},{}},totals={2,3},original='t:0.0/c:1.1'},
         {id='Corla_other_mob_01',base={{0}},extra={{}},totals={2},original='t:0/c:2'}}},
 {asset='/Game/DataObject/Field/2600-NIBLA/EnemyTerritory.EnemyTerritory',region='2600-NIBLA',names={'mobnibla_Wolf_00'},unlocks={},
  camps={{id='NiblaArea_mob_01',base={{0},{0}},extra={{},{}},totals={2,3},original='t:0.0/c:1.1'}}}}'''


def lua_runtime(pools=POOLS):
    lua = LuaRuntime()
    lua.globals().python_hash = lambda value: hashlib.sha256(value.encode()).hexdigest()
    lua.execute('''BiomeRandomizerSHA256=function(s) return python_hash(s) end
        BiomeRandomizerReadState=function() return '',true end
        BiomeRandomizerWriteState=function() return true end
        disk='';BiomeRandomizerWriteStateAsync=function(v) disk=v;return true end
        BiomeRandomizerRandomSeed=function() return '613' end
        logs={};function print(v) logs[#logs+1]=v end
        function FName(s) return {name=s} end''')
    for module in ('biome_json', 'lifecycle', 'state_store', 'squads'):
        lua.globals().source = (SCRIPTS / (module + '.lua')).read_text(encoding='utf-8')
        lua.globals().package.loaded[module] = lua.execute('return assert(load(source))()')
    lua.execute('package.loaded.world_pools=' + pools)
    lua.globals().source = (SCRIPTS / 'automatic.lua').read_text(encoding='utf-8')
    lua.globals().Automatic = lua.execute('return assert(load(source))()')
    return lua


def names_of(lua, numbers):
    resident = lua.eval('package.loaded.squads.resident')
    return {resident[n + 1] for n in numbers}


class Squads(unittest.TestCase):
    def test_lua_and_native_lists_match(self):
        native = re.findall(r'L"(mobcolvr_[A-Za-z0-9_]+)"', (ROOT / 'Native/src/resident_templates.hpp').read_text(encoding='utf-8'))
        lua = lua_runtime()
        self.assertEqual(native, list(lua.eval('package.loaded.squads.resident').values()))

    def test_every_template_is_in_the_resident_table_and_names_the_field_enemy(self):
        lua = lua_runtime()
        for name in lua.eval('package.loaded.squads.resident').values():
            self.assertRegex(name, r'^mobcolvr_EN\d{4}_\d{2}_[A-Za-z0-9_]+_00$')

    def test_the_regions_match_the_approved_plan(self):
        lua = lua_runtime();squads = lua.eval('package.loaded.squads')
        def pool(region, camp, chapter_select, chapter):
            gates = lua.table_from({'chapter_select': chapter_select, 'chapter': chapter})
            got = squads.pool(region, camp, gates)
            return set() if got is None else {n.split('_', 3)[3].removesuffix('_00') for n in names_of(lua, got.values())}
        for (region, camp), (always, chapter_select, from_chapter) in PLAN.items():
            with self.subTest(region=region, camp=camp):
                self.assertEqual(pool(region, camp, False, 2), always)
                self.assertEqual(pool(region, camp, False, 5), always | from_chapter)
                self.assertEqual(pool(region, camp, True, 2), always | chapter_select | from_chapter)
        self.assertIsNone(squads.pool('2200-CORLA', 'Corla_other_mob_01', lua.table_from({'chapter_select': True, 'chapter': 14})))

    # The fixture's tables: 1 is Junon, 2 is Corel (both halves).
    TABLE = {'JunonArea_mob_01': 1, 'Corla_desert_mob_01': 2, 'Corla_southem_mob_01': 2, 'Corla_other_mob_01': 2, 'NiblaArea_mob_01': 3}

    def new(self, lua, percent=100, chapter_select=False, chapter=2):
        lua.execute(f"auto=Automatic.new({{enabled=true,seed='613',squad_percent={percent}}})")
        lua.execute(f"auto.gates={{chapter_select={'true' if chapter_select else 'false'},chapter={chapter}}}")

    def keys(self, lua, camp, cycles, percent=100, chapter_select=False, chapter=2, types=None):
        self.new(lua, percent, chapter_select, chapter)
        if types is None:
            lua.execute(f"auto.activate_for_tests({self.TABLE[camp]})")
        else:
            unit = lua.eval(f"package.loaded.squads.unit(package.loaded.world_pools[{self.TABLE[camp]}].region,'{camp}')")
            lua.execute(f"auto.choice_of_for_tests('{camp}',0);auto.active_units['{unit}']={{types={{{','.join(map(str, types))}}},table={self.TABLE[camp]}}};auto.chosen={{}}")
        return [lua.eval(f"auto.choice_of_for_tests('{camp}',{c})") for c in range(cycles)]

    @staticmethod
    def entries(keys):
        return {e for k in keys for e in k[2:].split('/')[0].split('.')}

    def active(self, lua, unit):
        got = lua.eval(f"auto.active_units['{unit}']")
        return None if got is None else sorted(got['types'].values())

    def test_a_squad_never_mixes_with_monsters_and_keeps_the_camp_range(self):
        lua = lua_runtime()
        for camp, totals in (('JunonArea_mob_01', {3, 4, 5}), ('Corla_desert_mob_01', {2, 3})):
            for key in self.keys(lua, camp, 200):
                enemies, counts = re.match(r'^t:([r\d.]+)/c:([\d.]+)$', key).groups()
                self.assertTrue(all(e.startswith('r') for e in enemies.split('.')), key)
                self.assertIn(sum(map(int, counts.split('.'))), totals, key)
                self.assertTrue(all(int(c) >= 1 for c in counts.split('.')), key)

    def test_at_most_one_sweeper_and_it_stands_alone(self):
        lua = lua_runtime();seen = 0
        for key in self.keys(lua, 'JunonArea_mob_01', 400, types=[6, 10]):
            enemies, counts = re.match(r'^t:([r\d.]+)/c:([\d.]+)$', key).groups()
            enemies, counts = enemies.split('.'), counts.split('.')
            self.assertLessEqual(enemies.count('r10'), 1, key)
            if 'r10' in enemies:
                seen += 1;self.assertEqual(counts[enemies.index('r10')], '1', key)
        self.assertGreater(seen, 0, 'the Sweeper never came up in 400 rolls')

    def test_a_squad_uses_only_its_units_active_types(self):
        lua = lua_runtime()
        self.assertEqual(self.entries(self.keys(lua, 'JunonArea_mob_01', 200, types=[6, 8])), {'r6', 'r8'})

    def test_one_unit_alone_gets_two_types_from_its_pool(self):
        lua = lua_runtime();self.new(lua)
        lua.execute('auto.activate_for_tests(1)')
        types = self.active(lua, '1300-JUNOA')
        self.assertEqual(len(types), 2);self.assertTrue(set(types) <= {6, 8, 9, 10, 11}, types)

    def test_corels_halves_share_the_budget_one_type_each(self):
        lua = lua_runtime();self.new(lua)
        lua.execute('auto.activate_for_tests(2)')
        desert, coast = self.active(lua, '2200-CORLA:desert'), self.active(lua, '2200-CORLA:southern')
        self.assertEqual(len(desert), 1);self.assertEqual(len(coast), 1)
        self.assertTrue(set(desert) <= set(range(14, 22)), desert);self.assertTrue(set(coast) <= {0, 1, 4, 11, 13}, coast)
        keys = self.keys(lua, 'Corla_desert_mob_01', 100)
        self.assertEqual(len(self.entries(keys)), 1, keys[:5])

    def test_each_table_has_its_own_budget(self):
        lua = lua_runtime();self.new(lua)
        lua.execute('auto.activate_for_tests(1);auto.activate_for_tests(2);auto.activate_for_tests(3)')
        self.assertEqual(len(self.active(lua, '1300-JUNOA')), 2)
        self.assertEqual(len(self.active(lua, '2200-CORLA:desert')), 1);self.assertEqual(len(self.active(lua, '2200-CORLA:southern')), 1)
        self.assertEqual(len(self.active(lua, '2600-NIBLA')), 1, 'Nibelheim takes one type')
        keys = [lua.eval(f"auto.choice_of_for_tests('NiblaArea_mob_01',{c})") for c in range(80)]
        self.assertEqual(len(self.entries(keys)), 1, keys[:5])

    def test_a_region_without_a_budget_gets_no_squads(self):
        lua = lua_runtime();self.new(lua)
        lua.execute("package.loaded.squads.type_budget['1300-JUNOA']=nil;auto.activate_for_tests(1)")
        self.assertEqual(self.active(lua, '1300-JUNOA'), [])
        keys = [lua.eval(f"auto.choice_of_for_tests('JunonArea_mob_01',{c})") for c in range(50)]
        self.assertFalse(any(k.startswith('t:r') for k in keys), 'a squad without budget')
        lua.execute("package.loaded.squads.type_budget['1300-JUNOA']=2")

    def test_a_sweeper_is_never_a_units_only_type(self):
        lua = lua_runtime();self.new(lua)
        lua.execute("package.loaded.squads.type_budget['1300-JUNOA']=1")
        for _ in range(60):
            lua.execute('auto.release_for_tests(1);auto.activate_for_tests(1)')
            self.assertNotEqual(self.active(lua, '1300-JUNOA'), [10])
        lua.execute("package.loaded.squads.type_budget['1300-JUNOA']=2")

    def test_each_visit_draws_again_and_the_count_is_saved(self):
        lua = lua_runtime();self.new(lua);sets = set()
        for _ in range(30):
            lua.execute('auto.release_for_tests(1);auto.activate_for_tests(1)')
            sets.add(tuple(self.active(lua, '1300-JUNOA')))
        self.assertGreater(len(sets), 3, sets)
        import json
        self.assertEqual(json.loads(lua.eval('disk'))['squad_visits']['1300-JUNOA'], 30)

    def test_gated_enemies_appear_only_when_the_save_allows_them(self):
        lua = lua_runtime()
        def seen(**gates):
            self.new(lua, **gates);out = set()
            for _ in range(80):
                lua.execute('auto.release_for_tests(1);auto.activate_for_tests(1)');out |= set(self.active(lua, '1300-JUNOA'))
            return out
        early, later, post = seen(chapter=4), seen(chapter=5), seen(chapter_select=True, chapter=3)
        self.assertNotIn(7, early);self.assertNotIn(12, early)
        self.assertIn(7, later);self.assertNotIn(12, later)
        self.assertIn(7, post);self.assertIn(12, post)

    def test_about_one_roll_in_five_is_a_squad_by_default(self):
        lua = lua_runtime()
        lua.execute("auto=Automatic.new({enabled=true,seed='613'});auto.activate_for_tests(1)")
        keys = [lua.eval(f"auto.choice_of_for_tests('JunonArea_mob_01',{c})") for c in range(1000)]
        share = sum(1 for k in keys if k.startswith('t:r')) / len(keys)
        self.assertGreater(share, 0.14);self.assertLess(share, 0.26)

    def test_a_region_without_squads_never_gets_one(self):
        lua = lua_runtime()
        for key in self.keys(lua, 'Corla_other_mob_01', 100):
            self.assertNotIn('r', key[2:].split('/')[0], key)

    def test_reading_the_save_sets_the_gates_and_rerolls(self):
        lua = lua_runtime()
        lua.execute("""auto=Automatic.new({enabled=true,seed='613',squad_percent=100})
            db={GetChapterProgress=function() return 13050 end,IsStoryFlag=function(_,n) return n.name=='stfComn_Release_ChapterSelect' end}
            auto.choice_of_for_tests('JunonArea_mob_01',3);auto.read_gates_for_tests(db)""")
        self.assertTrue(lua.eval('auto.gates.chapter_select'));self.assertEqual(lua.eval('auto.gates.chapter'), 13)
        self.assertIsNone(lua.eval("auto.chosen['JunonArea_mob_01']"), 'compositions not rerolled for the new save')
        self.assertTrue(any('"event":"squad_gates"' in line for line in lua.eval('logs').values()))
        lua.execute("auto.read_gates_for_tests({GetChapterProgress=function() error('x') end,IsStoryFlag=function() return true end})")
        self.assertEqual(lua.eval('auto.gates.chapter'), 13, 'a failed read changed the gates')


if __name__ == '__main__':
    unittest.main()
