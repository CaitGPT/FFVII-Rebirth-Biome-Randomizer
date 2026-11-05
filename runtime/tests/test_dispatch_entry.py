"""Paired Lua entry contract; native scheduler lifetime needs game acceptance."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime

class DispatchEntry(unittest.TestCase):
    def test_synchronous_callbacks_need_no_async_hooks_and_survive_collection(self):
        lua=LuaRuntime()
        lua.execute('''
            ticks=0;begins=0;ends={}
            function BiomeRandomizerTableStatus() end
            package.loaded.config={enabled=true,seed='13'}
            package.loaded.automatic={new=function(config) return {
                step=function() ticks=ticks+1 end,
                territory_begin=function() begins=begins+1 end,
                end_play_name=function(_,id,reason) ends[#ends+1]={id,reason} end
            } end}
            function LoopAsync() error('async work forbidden') end
            function ExecuteInGameThread() error('transient coroutine forbidden') end
            function RegisterHook() error('cross-thread Lua hook forbidden') end
        ''')
        lua.execute((Path(__file__).parents[1]/'Scripts/main.lua').read_text(encoding='utf-8'))
        lua.execute('''
            BiomeRandomizerTerritoryBegin()
            for i=1,10000 do BiomeRandomizerTick();if i%100==0 then collectgarbage('collect') end end
            BiomeRandomizerActorEnd('exact-owned-id',0)
            assert(ticks==10000 and begins==1 and #ends==1)
            assert(ends[1][1]=='exact-owned-id' and ends[1][2]==0)
        ''')

    def test_missing_native_module_stays_inactive_and_says_so(self):
        # The DLL refused the loader, or the loader could not load the DLL.
        lua=LuaRuntime()
        lua.execute('''
            printed={}
            function print(text) printed[#printed+1]=text end
            package.loaded.config={enabled=true,seed='13'}
            package.loaded.automatic={new=function() error('selector must not start') end}
        ''')
        lua.execute((Path(__file__).parents[1]/'Scripts/main.lua').read_text(encoding='utf-8'))
        lua.execute('''
            assert(#printed==1 and printed[1]:find('inactive',1,true) and printed[1]:find('1.0.2',1,true))
            assert(BiomeRandomizerTick==nil)
        ''')

if __name__=='__main__':unittest.main()
