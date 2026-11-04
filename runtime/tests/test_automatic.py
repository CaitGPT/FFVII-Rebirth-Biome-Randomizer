"""Explicitly synthetic adapter fixtures. Native clear/spawn proof is separate."""
from pathlib import Path
import hashlib
import unittest
from lupa.lua54 import LuaRuntime

ROOT=Path(__file__).parents[1]/'Scripts'

SETUP=r'''
function object(value)
    value=value or {};value.IsValid=function() return true end;return value
end
function FName(s) return {ToString=function() return s end} end
function actor(name,spec,id)
    return object({name=name,spec=spec,id=id,hp=100,max=100,state=1,
        GetFullName=function(self) return self.id end,
        GetClass=function() return {GetFName=function() return FName('PC0000_00_Cloud_Standard_C') end} end})
end
cloud=actor('Cloud','player','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Cloud1')
tifa=actor('Tifa','player','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Tifa1')
aerith=actor('Aerith','player','PC /Game/Level/Game/EndGame.EndGame:PersistentLevel.Aerith1')
party_members={cloud,tifa,aerith};map={};battle_active=false;logs={};native_writes={};disk='';choices={0,0,0,0}
local battle=object({
 GetCharaFromActorName=function(_,name,allow_manager)
     if allow_manager then return map[name:ToString()] end
 end,
 GetActorName=function(_,a) return FName(a.name) end,
 GetCharaSpecName=function(_,a) return FName(a.spec) end,
 GetCharaHP=function(_,a) return a.hp end,GetHPMax=function(_,a) return a.max end,
 GetCharacterStateType=function(_,a) return a.state end})
local party=object({GetBattleMemberCount=function() return 3 end,GetBattleMember=function(_,i) return party_members[i+1] end})
local field=object({IsDuringBattle=function() return battle_active end})
local viewport=object();local engine=object({GameViewport=viewport,GetFullName=function() return 'GameEngine /Engine/Transient.GameEngine_1' end})
local statics=object({GetPlayerPawn=function() return cloud end})
local asset=object({GetAddress=function() return 123456 end,GetFullName=function() return 'EndDataObjectEnemyTerritory /Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory' end})
function StaticFindObject(path)
    if path=='/Engine/Transient.GameEngine_1' then return engine end
    if path=='/Script/Engine.Default__GameplayStatics' then return statics end
    if path=='/Script/EndGame.Default__EndBattleAPI' then return battle end
    if path=='/Script/EndGame.Default__EndPartyAPI' then return party end
    if path=='/Script/EndGame.Default__EndFieldAPI' then return field end
    if path=='/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory' then return asset end
end
function FindObject(_,_,path) return StaticFindObject(path) end
function FindFirstOf(class) if class=='GameEngine' then return engine end end
function FindAllOf() return {} end
function print(value) logs[#logs+1]=value end
function BiomeRandomizerIsGameThread() return true end
function BiomeRandomizerReadState() return disk,true end
function BiomeRandomizerWriteState(value) disk=value;return true end
function BiomeRandomizerRandomSeed() return '613' end
function BiomeRandomizerTableStatus() return json.encode({ok=true,choices=choices}) end
function BiomeRandomizerSetNext(address,index,expected,desired)
    if choices[index+1]~=expected then return json.encode({ok=false,reason='stale_expected_selection'}) end
    choices[index+1]=desired;native_writes[#native_writes+1]={index=index,before=expected,after=desired}
    return json.encode({ok=true,choices=choices})
end
function group(choice,suffix)
    local first=choice==0 and 'mobgrasa_KalmFang_000' or 'mobgrasa_Mu_000'
    local spec=choice==0 and 'CharaSpec_EN2000_05_GuardHound_KalmFangEnd2' or 'CharaSpec_EN2204_00_Mu_StandardEnd2'
    local rows={actor(first..'@Grassland_mob_05',spec,'first-'..suffix),
        actor('mobgrasa_Ogre_Orc_001@Grassland_mob_05','CharaSpec_EN2211_01_Ogre_OrcEnd2','orc1-'..suffix),
        actor('mobgrasa_Ogre_Orc_002@Grassland_mob_05','CharaSpec_EN2211_01_Ogre_OrcEnd2','orc2-'..suffix)}
    for _,a in ipairs(rows) do map[a.name]=a end;return rows
end
function kill(a) a.hp=0;a.state=6 end
rows=group(0,'one');auto=Automatic.new({enabled=true,seed='613'});auto:step();assert(not auto.fault)
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
        lua.globals().source=(ROOT/'automatic.lua').read_text(encoding='utf-8')
        lua.globals().Automatic=lua.execute('return assert(load(source))()')
        lua.execute(SETUP+body)

    def test_verified_clear_changes_only_its_camp_then_checks_respawn(self):
        self.run_case('''
            battle_active=true;kill(rows[1]);auto:step();kill(rows[2]);auto:step();kill(rows[3]);auto:step()
            assert(#native_writes==0)
            battle_active=false;auto:step();assert(not auto.fault and #native_writes==1)
            assert(choices[1]==1 and choices[2]==0 and choices[3]==0 and choices[4]==0)
            assert(json.decode(disk).cycles.Grassland_mob_05.cycle==1)
            rows=group(1,'two');auto:step();auto:step();assert(not auto.fault and #native_writes==1)
            assert(auto.policy.camps.Grassland_mob_05.phase=='active')
        ''')

    def test_absence_and_unload_endplay_never_count_as_deaths(self):
        self.run_case('''
            for _,a in ipairs(rows) do kill(a);auto:end_play({get=function() return a end},4) end
            map={};auto:step();assert(#native_writes==0 and not auto.fault)
        ''')

    def test_defeat_blocks_clear_even_if_enemy_deaths_were_observed(self):
        self.run_case('''
            battle_active=true;for _,a in ipairs(rows) do kill(a) end;auto:step()
            cloud.hp=0;tifa.hp=0;aerith.hp=0;auto:step()
            battle_active=false;cloud.hp=1;tifa.hp=1;aerith.hp=1;auto:step()
            assert(#native_writes==0 and json.decode(disk).cycles.Grassland_mob_05.cycle==0)
        ''')

    def test_stream_recreated_group_rebinds_without_reroll(self):
        self.run_case('''
            kill(rows[1]);auto:step();map={};auto:step();rows=group(0,'reloaded');auto:step()
            assert(not auto.fault and #native_writes==0 and not next(auto.policy.camps.Grassland_mob_05.deaths))
        ''')

    def test_another_reference_writer_stops_the_selector(self):
        self.run_case('''
            choices[1]=1;auto:step();assert(auto.fault and #native_writes==0)
            assert(json.decode(disk).cycles.Grassland_mob_05.cycle==0)
        ''')

    def test_preexisting_reference_writer_is_not_overwritten(self):
        self.run_case('''
            choices[1]=1;native_writes={}
            local fresh=Automatic.new({enabled=true,seed='613'});fresh:step()
            assert(fresh.fault and fresh.fault:find('preexisting_reference_change',1,true))
            assert(#native_writes==0 and choices[1]==1)
        ''')

    def test_late_initialization_preflights_all_camps_before_writing(self):
        self.run_case('''
            local seed
            for i=1,100 do
                local pick=require('lifecycle').selection
                if pick(tostring(i),'Grassland_mob_05',0,{0,1},BiomeRandomizerSHA256)==1 and
                   pick(tostring(i),'Grassland_mob_23',0,{0,1},BiomeRandomizerSHA256)==1 then seed=tostring(i);break end
            end
            map={}
            for _,a in ipairs(rows) do a.name=a.name:gsub('Grassland_mob_05','Grassland_mob_23');map[a.name]=a end
            assert(seed);disk='';native_writes={}
            local fresh=Automatic.new({enabled=true,seed=seed});fresh:step()
            assert(fresh.fault and fresh.fault:find('initial_living_group_choice_differs',1,true))
            assert(#native_writes==0)
            for _,choice in ipairs(choices) do assert(choice==0) end
        ''')

    def test_population_not_ready_defers_every_initial_write(self):
        self.run_case('''
            local seed
            for i=1,100 do
                if require('lifecycle').selection(tostring(i),'Grassland_mob_05',0,{0,1},BiomeRandomizerSHA256)==1 then seed=tostring(i);break end
            end
            assert(seed);disk='';native_writes={};rows[1].max=0
            local fresh=Automatic.new({enabled=true,seed=seed});fresh:step()
            assert(not fresh.fault and #native_writes==0)
            for _,choice in ipairs(choices) do assert(choice==0) end
            rows[1].max=100;fresh:step()
            assert(fresh.fault and #native_writes==0)
        ''')

if __name__=='__main__':unittest.main()
