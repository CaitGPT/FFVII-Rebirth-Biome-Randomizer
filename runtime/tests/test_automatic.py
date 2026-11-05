"""Explicitly synthetic selector fixtures. Native spawning and fights are tested in the game, not here."""
from pathlib import Path
import hashlib
import unittest
from lupa.lua54 import LuaRuntime

ROOT=Path(__file__).parents[1]/'Scripts'

POOLS='''{{asset='/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory',region='1200-GRASA',camps={
    {id='Grassland_mob_05',options=4},{id='Grassland_mob_23',options=3}}},
 {asset='/Game/DataObject/Field/1300-JUNOA/EnemyTerritory.EnemyTerritory',region='1300-JUNOA',camps={{id='JunonArea_mob_01',options=2}}}}'''

SETUP=r'''
local clock=0;os.clock=function() clock=clock+10;return clock end
function object(value)
    value=value or {};value.IsValid=function() return true end;return value
end
function FName(s) return {ToString=function() return s end} end
function actor(name,id)
    return object({name=name,id=id,hp=100,
        GetFullName=function(self) return self.id end,
        GetAddress=function(self) return self.id end,
        GetClass=function() return {GetFName=function() return FName('PC0000_00_Cloud_Standard_C') end} end})
end
cloud=actor('Cloud','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Cloud1')
tifa=actor('Tifa','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Tifa1')
party_members={cloud,tifa};battle_active=false;pawn_gone=false;roster={};logs={};native_writes={};disk=''
choices={[0]={0,0},[1]={0}};loaded_assets={['/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory']=0};spawn_ready={};finds=0;scans=0;status_calls=0;battle_calls=0
local battle=object({
 IsInBattle=function() battle_calls=battle_calls+1;return battle_active end,
 GetEnemyMembersRef=function(_,out) for i,a in ipairs(roster) do out[i]=a end end,
 GetActorName=function(_,a) return FName(a.name) end,
 GetCharaHP=function(_,a) return a.hp end})
local party=object({GetBattleMemberCount=function() return #party_members end,GetBattleMember=function(_,i) return party_members[i+1] end})
local viewport=object();local engine=object({GameViewport=viewport})
-- As in the game: no player pawn for the whole of a battle.
local statics=object({GetPlayerPawn=function() if battle_active or pawn_gone then return nil end;return cloud end})
function StaticFindObject(path)
    finds=finds+1
    if path=='/Script/Engine.Default__GameplayStatics' then return statics end
    if path=='/Script/EndGame.Default__EndBattleAPI' then return battle end
    if path=='/Script/EndGame.Default__EndPartyAPI' then return party end
    local index=loaded_assets[path]
    if index then return object({GetAddress=function() return index+1000 end}) end
end
function FindFirstOf(class) if class=='GameEngine' then return engine end end
function FindAllOf(class) scans=scans+1;return {} end
function print(value) logs[#logs+1]=value end
function BiomeRandomizerIsGameThread() return true end
function BiomeRandomizerStateWriteFailed() return false end
function BiomeRandomizerReadState() return disk,true end
function BiomeRandomizerWriteState(value) disk=value;return true end
function BiomeRandomizerWriteStateAsync(value) disk=value;return true end
function BiomeRandomizerRandomSeed() return '613' end
function BiomeRandomizerSpawnReady(camp) return spawn_ready[camp]==true end
function BiomeRandomizerSpawnScan() scans=scans+1;return found_actors or 0 end
function BiomeRandomizerSpawnReset() spawn_ready={} end
function BiomeRandomizerSpawnStats() return '{}' end
function BiomeRandomizerTableStatus(address,index) status_calls=status_calls+1;return json.encode({ok=true,asset_content=address,choices=choices[index]}) end
function BiomeRandomizerSetNext(address,index,target,expected,desired)
    if choices[index][target+1]~=expected then return json.encode({ok=false,reason='stale_expected_selection'}) end
    choices[index][target+1]=desired;native_writes[#native_writes+1]={index=index,target=target,before=expected,after=desired}
    return json.encode({ok=true,choices=choices[index]})
end
function enemy(name) return actor(name,'EN-'..name) end
function pick(seed,camp,cycle,n) local p={};for i=1,n do p[i]=i-1 end;return require('lifecycle').selection(seed,camp,cycle,p,BiomeRandomizerSHA256) end
spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true,JunonArea_mob_01=true}
auto=Automatic.new({enabled=true,seed='613'});auto:step();assert(not auto.fault,auto.fault)
start_writes=#native_writes
function committed() return json.decode(disk).cycles.Grassland_mob_05.cycle end
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

    def test_a_fight_advances_only_its_camp_when_it_ends(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05'),enemy('mobgrasa_Ogre_Orc_001@Grassland_mob_05')}
            battle_active=true;auto:step();auto:step();assert(committed()==0)
            roster={};battle_active=false;auto:step()
            assert(not auto.fault,auto.fault);assert(committed()==1)
            assert(json.decode(disk).cycles.Grassland_mob_23.cycle==0)
            assert(auto.current[1][1]==pick('613','Grassland_mob_05',1,4))
        ''')

    def test_fleeing_counts_the_same_as_winning(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step();battle_active=false;auto:step()
            assert(committed()==1)
        ''')

    def test_game_over_never_counts(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step();cloud.hp=0;tifa.hp=0;auto:step()
            cloud.hp=100;tifa.hp=100;battle_active=false;auto:step()
            assert(committed()==0)
        ''')

    def test_party_wiped_as_the_battle_flag_clears_never_counts(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step();cloud.hp=0;tifa.hp=0;battle_active=false;auto:step()
            assert(committed()==0)
        ''')

    def test_a_fight_with_anything_off_the_list_changes_nothing(self):
        self.run_case('''
            for _,name in ipairs({'mobgrasa_Mu_000@GRASA_Quest04_TargetEnemy','mobgrasa_Mu_000@Grassland_mob_01','boss_without_a_territory','EN9999@terVR_COL30_SUMMON'}) do
                roster={enemy(name)};battle_active=true;auto:step();battle_active=false;auto:step()
            end
            assert(committed()==0 and #native_writes==start_writes and not auto.fault)
        ''')

    def test_a_reload_during_a_fight_does_not_count(self):
        self.run_case('''
            roster={enemy('mobgrasa_Mu_000@Grassland_mob_05')}
            battle_active=true;auto:step()
            battle_active=false;pawn_gone=true;for i=1,5 do auto:step() end
            pawn_gone=false;auto:step()
            assert(committed()==0)
        ''')

    def test_a_table_is_only_changed_once_its_spawn_lists_are_ready(self):
        self.run_case('''
            local seed
            for i=1,200 do
                if pick(tostring(i),'Grassland_mob_05',0,4)~=0 then seed=tostring(i);break end
            end
            disk='';spawn_ready={};native_writes={};choices={[0]={0,0},[1]={0}};scans=0
            local fresh=Automatic.new({enabled=true,seed=seed});fresh:step()
            assert(not fresh.fault,fresh.fault);assert(#native_writes==0,'wrote before the spawn lists were ready')
            assert(scans==1,'expected the one-off fallback scan')
            spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true}
            fresh.loaded={};fresh:territory_begin('1200-GRASA');fresh:step()
            assert(not fresh.fault,fresh.fault);assert(#native_writes>=1)
        ''')

    def test_after_a_load_a_fresh_table_is_written_again(self):
        self.run_case('''
            local seed
            for i=1,200 do
                if pick(tostring(i),'Grassland_mob_05',0,4)~=0 then seed=tostring(i);break end
            end
            disk='';choices={[0]={0,0},[1]={0}};native_writes={}
            local run=Automatic.new({enabled=true,seed=seed});run:step();local first=#native_writes;assert(first>=1)
            pawn_gone=true;for i=1,5 do run:step() end
            assert(next(run.loaded)==nil)
            spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true}
            loaded_assets={['/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory']=0}
            choices={[0]={0,0},[1]={0}}
            local oldStatus=BiomeRandomizerTableStatus
            function BiomeRandomizerTableStatus(address,index) return json.encode({ok=true,asset_content=address+1,choices=choices[index]}) end
            pawn_gone=false;run:step()
            assert(not run.fault,run.fault);assert(run.loaded[1]);assert(#native_writes>first)
            BiomeRandomizerTableStatus=oldStatus
        ''')

    def test_every_load_puts_a_surviving_table_back_to_the_original(self):
        # The table outlives the level, whose new spawn actors have empty lists.
        self.run_case('''
            local seed
            for i=1,200 do
                if pick(tostring(i),'Grassland_mob_05',0,4)~=0 then seed=tostring(i);break end
            end
            disk='';choices={[0]={0,0},[1]={0}};native_writes={}
            local run=Automatic.new({enabled=true,seed=seed});run:step();assert(choices[0][1]~=0)
            pawn_gone=true;for i=1,5 do run:step() end
            assert(not run.fault,run.fault);assert(choices[0][1]==0 and choices[0][2]==0,'a changed row survived the load')
            spawn_ready={Grassland_mob_05=true,Grassland_mob_23=true}
            pawn_gone=false;run:step();assert(not run.fault,run.fault);assert(choices[0][1]~=0)
        ''')

    def test_another_writer_is_never_overwritten(self):
        self.run_case('''
            disk='';native_writes={};choices={[0]={1,0},[1]={0}}
            local fresh=Automatic.new({enabled=true,seed='613'});fresh:step()
            assert(fresh.fault and fresh.fault:find('preexisting_reference_change',1,true));assert(#native_writes==0)
        ''')

    def test_idle_play_does_no_lookups_or_table_reads(self):
        # Path lookups stalled the game thread by 60 ms a tick before this design.
        self.run_case('''
            auto:step();finds=0;status_calls=0;scans=0
            for i=1,100 do auto:step() end
            assert(finds==0,'idle ticks looked things up: '..finds)
            assert(status_calls==0 and scans==0 and not auto.fault)
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
