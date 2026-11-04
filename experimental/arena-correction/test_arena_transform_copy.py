"""Synthetic fail-closed checks, not native swap acceptance."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime

SOURCE = Path(__file__).parent / 'Scripts/main.lua'
SETUP = r'''
local source, count, destination_count, wrong_name, invalid_point, corrupt_write = ...
local path='/Game/Level/Game/Field/1200-GRASA/Layout/1200-GRASA_World_Navigation_Mod_ServerBuild.1200-GRASA_World_Navigation_Mod_ServerBuild:PersistentLevel.Grassland_mob_05'
local state={writes=0,logs={},loops={},hooks={}}
local function array(values)
  values.GetArrayNum=function(self) return #self end
  return values
end
local points={}
for i=1,count do points[i]={Rotation={X=0,Y=0,Z=0,W=1},Translation={X=i*100,Y=0,Z=-200},Scale3D={X=1,Y=1,Z=1}} end
if invalid_point and points[1] then points[1].Translation.X=0/0 end
local empty={}
for i=1,destination_count do empty[i]=points[i] end
local data={TerritoryGroundSpawnPoints_M=array(points),TerritoryGroundSpawnPoints_S=array(empty)}
local actor=setmetatable({}, {
  __index=function(_,key)
    if key=='IsValid' then return function() return true end end
    if key=='GetAddress' then return function() return 123 end end
    if key=='GetFullName' then return function() return 'EndFieldEnemyTerritoryServerBuildActor '..(wrong_name and '/OtherCamp' or path) end end
    return data[key]
  end,
  __newindex=function(_,key,value)
    state.writes=state.writes+1
    local independent={}
    for i,t in ipairs(value) do
      independent[i]={}
      for field,components in pairs(t) do
        independent[i][field]={}
        for component,n in pairs(components) do independent[i][field][component]=n end
      end
    end
    value=independent
    if corrupt_write then value[1].Translation.X=-999 end
    data[key]=array(value)
  end})
local env=setmetatable({
  StaticFindObject=function() return actor end,
  FindObject=function() return actor end,
  FindAllOf=function() return {actor} end,
  NotifyOnNewObject=function() end,
  ExecuteInGameThread=function(fn) fn() end,
  RegisterHook=function(_,fn) state.hooks[#state.hooks+1]=fn;return 1,2 end,
  RegisterLoadMapPostHook=function(fn) state.hooks[#state.hooks+1]=fn end,
  LoopAsync=function(_,fn) state.loops[#state.loops+1]=fn end,
  print=function(text) state.logs[#state.logs+1]=text end
},{__index=_G})
assert(load(source,'arena-diagnostic','t',env))()
for i=1,3 do
  for _,fn in ipairs(state.loops) do fn() end
  for _,fn in ipairs(state.hooks) do fn({get=function() return actor end}) end
end
return state.writes, data.TerritoryGroundSpawnPoints_S:GetArrayNum(), table.concat(state.logs,'\n')
'''

class ArenaCopyTests(unittest.TestCase):
    def run_case(self, count=12, destination_count=0, wrong_name=False, invalid_point=False, corrupt_write=False):
        return LuaRuntime().execute(SETUP, SOURCE.read_text(), count, destination_count, wrong_name, invalid_point, corrupt_write)

    def test_exact_camp_copies_once_and_reads_back_twelve_points(self):
        writes, count, log = self.run_case()
        self.assertEqual((writes,count),(1,12))
        self.assertIn('verified',log)

    def test_other_camp_is_never_modified(self):
        self.assertEqual(self.run_case(wrong_name=True)[:2],(0,0))

    def test_unreviewed_count_or_existing_destination_is_never_overwritten(self):
        self.assertEqual(self.run_case(count=11)[:2],(0,0))
        self.assertEqual(self.run_case(destination_count=1)[:2],(0,1))

    def test_unloaded_points_wait_and_invalid_point_refuses_mutation(self):
        self.assertEqual(self.run_case(count=0)[:2],(0,0))
        self.assertEqual(self.run_case(invalid_point=True)[:2],(0,0))

    def test_failed_readback_is_not_retried(self):
        writes, _, log = self.run_case(corrupt_write=True)
        self.assertEqual(writes,1)
        self.assertIn('FAILED',log)

if __name__=='__main__': unittest.main()
