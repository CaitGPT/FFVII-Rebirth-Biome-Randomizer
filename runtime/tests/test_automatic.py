"""Explicitly synthetic selector fixtures. Native spawning and fights are tested in the game, not here."""
from pathlib import Path
import hashlib
import unittest
from lupa.lua54 import LuaRuntime

ROOT=Path(__file__).parents[1]/'Scripts'

# Two Grasslands camps and one Junon camp. Catalog 3 is a Combat Assignment enemy that ground slots can take
# once its assignment is won.
POOLS='''{{asset='/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory',region='1200-GRASA',
    names={'mobgrasa_KalmFang_00','mobgrasa_Mu_00','mobgrasa_Ogre_Orc_00','mobgrasa_WereRat_Rare_00'},
    unlocks={{territory='Grassland_mob_09',enemy=3,flag='stfWorldReport_Finish_GRASA_002'}},
    camps={{id='Grassland_mob_05',base={{0,1,2},{0,1,2}},extra={{3},{3}},totals={2,3,4},original='t:0.2/c:1.2'},
           {id='Grassland_mob_23',base={{0,1}},extra={{3}},totals={1,2,3},original='t:0/c:2'}}},
 {asset='/Game/DataObject/Field/1300-JUNOA/EnemyTerritory.EnemyTerritory',region='1300-JUNOA',names={'mobjunon_Formula_00'},unlocks={},
    camps={{id='JunonArea_mob_01',base={{0}},extra={{}},totals={1,2},original='t:0/c:1'}}}}'''

SETUP=r'''
local clock=0;os.clock=function() clock=clock+10;return clock end
function object(value)
    value=value or {};value.IsValid=function() return true end;return value
end
function FName(s) return {ToString=function() return s end,name=s} end
function actor(name,id)
    return object({name=name,id=id,hp=100,
        GetFullName=function(self) return self.id end,
        GetAddress=function(self) return self.id end,
        GetClass=function() return {GetFName=function() return FName('PC0000_00_Cloud_Standard_C') end} end})
end
cloud=actor('Cloud','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Cloud1')
tifa=actor('Tifa','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Tifa1')
party_members={cloud,tifa};battle_active=false;pawn_gone=false;roster={};field_enemies={};logs={};native_writes={};disk=''
choices={[0]={'o','o'},[1]={'o'}};loaded_assets={['/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory']=0};finds=0;scans=0;status_calls=0;battle_calls=0
local battle=object({
 IsInBattle=function() battle_calls=battle_calls+1;return battle_active end,
 GetEnemyMembersRef=function(_,out) for i,a in ipairs(roster) do out[i]=a end end,
 GetActorName=function(_,a) return FName(a.name) end,
 GetCharaFromActorName=function(_,name) return field_enemies[name.name] end,
 GetCharaHP=function(_,a) return a.hp end})
-- The save's story flags, as EndDataBaseAPI:IsStoryFlag reads them.
story_flags={};flag_reads=0
local database=object({IsStoryFlag=function(_,name) flag_reads=flag_reads+1;return story_flags[name.name]==true end})
local party=object({GetBattleMemberCount=function() return #party_members end,GetBattleMember=function(_,i) return party_members[i+1] end})
local viewport=object({World=object({GetAddress=function() return 77 end})});local engine=object({GameViewport=viewport})
-- As in the game: no player pawn for the whole of a battle.
local statics=object({GetPlayerPawn=function() if battle_active or pawn_gone then return nil end;return cloud end})
function StaticFindObject(path)
    finds=finds+1
    if path=='/Script/Engine.Default__GameplayStatics' then return statics end
    if path=='/Script/EndGame.Default__EndBattleAPI' then return battle end
    if path=='/Script/EndGame.Default__EndPartyAPI' then return party end
    if path=='/Script/EndGame.Default__EndDataBaseAPI' then return database end
    local index=loaded_assets[path]
    if index then return object({GetAddress=function() return index+1000 end}) end
end
function FindFirstOf(class) if class=='GameEngine' then return engine end end
function print(value) logs[#logs+1]=value end
function BiomeRandomizerIsGameThread() return true end
function BiomeRandomizerStateWriteFailed() return false end
function BiomeRandomizerReadState() return disk,true end
function BiomeRandomizerWriteState(value) disk=value;return true end
function BiomeRandomizerWriteStateAsync(value) disk=value;return true end
function BiomeRandomizerRandomSeed() return '613' end
function BiomeRandomizerSpawnReady(camp) return spawn_ready[camp]==true end
function BiomeRandomizerSpawnPoll()
    scans=scans+1
    local fresh,gone,names=0,0,{}
    for camp in pairs(spawn_ready) do if not polled[camp] then fresh=fresh+1 end end
    for camp in pairs(polled) do if not spawn_ready[camp] then gone=gone+1;names[#names+1]=camp end end
    polled={};for camp in pairs(spawn_ready) do polled[camp]=true end
    return json.encode({fresh=fresh,gone=gone,gone_camps=table.concat(names,',')})
end
function BiomeRandomizerSpawnStats() return '{}' end
function BiomeRandomizerTableStatus(address,index) status_calls=status_calls+1;return json.encode({ok=true,asset_content=address,choices=choices[index]}) end
-- Like the native writer: a composition names one enemy per slot and an exact count per slot.
function BiomeRandomizerSetNext(address,index,target,expected,desired)
    if choices[index][target+1]~=expected then return json.encode({ok=false,reason='stale_expected_selection'}) end
    if desired~='o' then
        local enemies,counts=desired:match('^t:([%d%.]+)/c:([%d%.]+)$')
        assert(enemies,'malformed composition '..desired)
        local e={};for v in enemies:gmatch('%d+') do e[#e+1]=tonumber(v) end
        local c={};for v in counts:gmatch('%d+') do c[#c+1]=tonumber(v) end
        assert(#e==#c,'slots and counts differ')
        for _,v in ipairs(c) do assert(v>=1,'empty slot') end
    end
    choices[index][target+1]=desired;native_writes[#native_writes+1]={index=index,target=target,before=expected,after=desired}
    return json.encode({ok=true,choices=choices[index]})
end
function enemy(name) local a=actor(name,'EN-'..name);field_enemies[name]=a;return a end
function BiomeRandomizerSetMany(address,index,spec)
    local result
    for target,expected,desired in spec:gmatch('(%d+)|([^|;]+)|([^;]+)') do
        result=json.decode(BiomeRandomizerSetNext(address,index,tonumber(target),expected,desired))
        if not result.ok then return json.encode(result) end
    end
    return json.encode(result)
end
polled={};spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true,JunonArea_mob_01=true}
auto=Automatic.new({enabled=true,seed='613'});auto:step();auto:step();auto:step();assert(not auto.fault,auto.fault)
start_writes=#native_writes
function committed(camp) return json.decode(disk).cycles[camp or 'Grassland_mob_05'].cycle end
function fight(names)
    roster={};for _,n in ipairs(names) do roster[#roster+1]=enemy(n) end
    battle_active=true;auto:step();battle_active=false;auto:step()
end
'''

class Adapter(unittest.TestCase):
    def run_case(self,body):
        lua=LuaRuntime()
        lua.globals().python_hash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        lua.execute('BiomeRandomizerSHA256=function(s) return python_hash(s) end')
        for module in ('biome_json','lifecycle','state_store'):
            lua.globals().source=(ROOT/(module+'.lua')).read_text(encoding='utf-8')
            value=lua.execute('return assert(load(source))()')
            lua.globals().package.loaded[module]=value
            if module=='biome_json':lua.globals().json=value
        lua.execute('package.loaded.world_pools='+POOLS)
        lua.globals().source=(ROOT/'automatic.lua').read_text(encoding='utf-8')
        lua.globals().Automatic=lua.execute('return assert(load(source))()')
        lua.execute(SETUP+body)

    def test_compositions_are_written_when_the_level_appears(self):
        self.run_case('''
            assert(choices[0][1]~='o' and choices[0][2]~='o','camps not changed')
            assert(choices[1][1]=='o','a table not loaded was written')
        ''')

    def test_each_slot_holds_an_allowed_enemy_and_counts_fit_the_range(self):
        self.run_case('''
            for cycle=0,200 do
                local key=auto.choice_of_for_tests('Grassland_mob_05',cycle)
                local a,b,c1,c2=key:match('^t:(%d+)%.(%d+)/c:(%d+)%.(%d+)$')
                assert(a,'bad key '..key)
                a,b,c1,c2=tonumber(a),tonumber(b),tonumber(c1),tonumber(c2)
                assert(a<=2 and b<=2,'locked or foreign enemy chosen: '..key)
                assert(c1+c2>=2 and c1+c2<=4 and c1>=1 and c2>=1,'count outside the range: '..key)
            end
        ''')

    def test_every_count_and_enemy_in_the_pool_turns_up(self):
        self.run_case('''
            local totals,first={},{}
            for cycle=0,300 do
                local key=auto.choice_of_for_tests('Grassland_mob_05',cycle)
                local a,c1,c2=key:match('^t:(%d+)%.%d+/c:(%d+)%.(%d+)$')
                totals[tonumber(c1)+tonumber(c2)]=true;first[tonumber(a)]=true
            end
            assert(totals[2] and totals[3] and totals[4],'a total never appears')
            assert(first[0] and first[1] and first[2],'an enemy never appears')
        ''')

    def test_a_camp_never_repeats_its_previous_composition(self):
        self.run_case('''
            local previous='t:0.2/c:1.2'
            for cycle=0,300 do
                local key=auto.choice_of_for_tests('Grassland_mob_05',cycle)
                assert(key~=previous,'repeated at cycle '..cycle..': '..key);previous=key
            end
        ''')

    def test_a_fight_advances_only_its_camp_when_it_ends(self):
        self.run_case('''
            local before=choices[0][1]
            fight({'mobgrasa_Mu_000@Grassland_mob_05','mobgrasa_Ogre_Orc_001@Grassland_mob_05'})
            assert(not auto.fault,auto.fault);assert(committed()==1)
            assert(json.decode(disk).cycles.Grassland_mob_23.cycle==0)
            assert(choices[0][1]==auto.choice_of_for_tests('Grassland_mob_05',1) and choices[0][1]~=before)
        ''')

    def test_game_over_never_counts(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step();cloud.hp=0;tifa.hp=0;auto:step()
            cloud.hp=100;tifa.hp=100;battle_active=false;auto:step()
            assert(committed()==0)
        ''')

    def test_a_fight_with_anything_off_the_list_changes_nothing(self):
        self.run_case('''
            for _,name in ipairs({'mobgrasa_Mu_000@GRASA_Quest04_TargetEnemy','mobgrasa_Mu_000@Grassland_mob_01','boss_without_a_territory'}) do
                fight({name})
            end
            assert(committed()==0 and #native_writes==start_writes and not auto.fault)
        ''')

    def test_a_won_assignment_unlocks_its_enemy_for_the_region(self):
        self.run_case('''
            fight({'mobgrasa_WereRat_Rare_000@Grassland_mob_09'})
            field_enemies['mobgrasa_WereRat_Rare_000@Grassland_mob_09'].hp=0
            auto:step()
            assert(json.decode(disk).unlocked[1]=='mobgrasa_WereRat_Rare_00','not unlocked')
            local seen=false
            for cycle=0,200 do if auto.choice_of_for_tests('Grassland_mob_23',cycle):find('^t:3/') then seen=true end end
            assert(seen,'the unlocked enemy never appears')
            -- Junon keeps its own pool.
            for cycle=0,50 do assert(auto.choice_of_for_tests('JunonArea_mob_01',cycle):find('^t:0/'),'leaked into another region') end
        ''')

    def test_an_assignment_won_before_the_mod_unlocks_on_load(self):
        self.run_case('''
            disk='';native_writes={};choices={[0]={'o','o'},[1]={'o'}};polled={}
            story_flags['stfWorldReport_Finish_GRASA_002']=true
            local fresh=Automatic.new({enabled=true,seed='613'});for i=1,3 do fresh:step() end
            assert(not fresh.fault,fresh.fault)
            assert(json.decode(disk).unlocked[1]=='mobgrasa_WereRat_Rare_00','not unlocked from the save')
            local said=false;for _,line in ipairs(logs) do if line:find('"source":"save"',1,true) then said=true end end
            assert(said,'no unlock event from the save')
        ''')

    def test_the_save_record_after_a_fight_unlocks_when_the_roster_missed_it(self):
        self.run_case('''
            fight({'mobgrasa_WereRat_Rare_000@Grassland_mob_09'})
            story_flags['stfWorldReport_Finish_GRASA_002']=true
            for i=1,3 do auto:step() end
            assert(json.decode(disk).unlocked[1]=='mobgrasa_WereRat_Rare_00','the save record was not read after the fight')
        ''')

    def test_a_save_without_the_record_unlocks_nothing(self):
        self.run_case('''
            for i=1,10 do auto:step() end
            assert(#(json.decode(disk).unlocked or {})==0,'unlocked with no record')
        ''')

    def test_fleeing_an_assignment_unlocks_nothing(self):
        self.run_case('''
            fight({'mobgrasa_WereRat_Rare_000@Grassland_mob_09'})
            for i=1,10 do auto:step() end
            assert(#json.decode(disk).unlocked==0,'a fled assignment unlocked its enemy')
        ''')

    def test_a_reload_during_a_fight_does_not_count(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step()
            battle_active=false;pawn_gone=true;for i=1,5 do auto:step() end
            pawn_gone=false;auto:step()
            assert(committed()==0)
        ''')

    def test_a_camp_only_changes_once_its_spawn_lists_are_ready(self):
        self.run_case('''
            disk='';spawn_ready={};native_writes={};choices={[0]={'o','o'},[1]={'o'}};polled={}
            local fresh=Automatic.new({enabled=true,seed='9'})
            for i=1,3 do fresh:step() end
            assert(not fresh.fault,fresh.fault);assert(#native_writes==0,'wrote before the spawn lists were ready')
        ''')

    def test_leaving_a_level_restores_its_table_then_chooses_when_actors_return(self):
        self.run_case('''
            spawn_ready={};pawn_gone=true;auto:step()
            assert(not auto.fault,auto.fault);assert(choices[0][1]=='o' and choices[0][2]=='o','a changed row survived the level')
            for i=1,5 do auto:step() end
            assert(choices[0][1]=='o','chose before the actors returned')
            spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true};auto:step()
            assert(not auto.fault,auto.fault);assert(choices[0][1]~='o','not chosen while still loading')
        ''')

    def test_conversations_with_no_player_do_no_table_work(self):
        self.run_case('''
            status_calls=0
            pawn_gone=true;for i=1,20 do auto:step() end;pawn_gone=false;for i=1,5 do auto:step() end
            assert(status_calls==0,'a scene caused table work')
        ''')

    def test_another_writer_is_never_overwritten(self):
        self.run_case('''
            disk='';native_writes={};choices={[0]={'t:1.1/c:1.1','o'},[1]={'o'}};polled={}
            local fresh=Automatic.new({enabled=true,seed='613'});for i=1,3 do fresh:step() end
            assert(fresh.fault and fresh.fault:find('preexisting_reference_change',1,true));assert(#native_writes==0)
        ''')

    def test_idle_play_does_no_lookups_or_table_reads(self):
        # Path lookups stalled the game thread by 60 ms a tick before this design.
        self.run_case('''
            auto:step();finds=0;status_calls=0;flag_reads=0
            for i=1,100 do auto:step() end
            assert(finds==0,'idle ticks looked things up: '..finds)
            assert(flag_reads==0,'idle ticks read story flags: '..flag_reads)
            assert(status_calls==0 and not auto.fault)
        ''')

    def test_a_load_or_shutdown_stops_touching_the_game(self):
        self.run_case('''
            pawn_gone=true;for i=1,5 do auto:step() end
            battle_calls=0;for i=1,100 do auto:step() end
            assert(battle_calls==0,'touched the battle API with no player: '..battle_calls)
        ''')

    def test_nothing_runs_before_the_first_player_is_seen(self):
        self.run_case('''
            pawn_gone=true;battle_calls=0
            local early=Automatic.new({enabled=true,seed='613'});for i=1,20 do early:step() end
            assert(battle_calls==0 and not early.fault)
        ''')

if __name__=='__main__':unittest.main()
