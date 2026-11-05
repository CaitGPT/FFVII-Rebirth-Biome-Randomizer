"""The seeded choice. Native spawning is tested in the game, not here."""
from pathlib import Path
import unittest
import hashlib
from lupa.lua54 import LuaRuntime

SOURCE=(Path(__file__).parents[1]/'Scripts/lifecycle.lua').read_text(encoding='utf-8')

class Lifecycle(unittest.TestCase):
    def run_case(self,body):
        lua=LuaRuntime()
        lua.globals().module_source=SOURCE
        lua.globals().python_sha256=lambda s:hashlib.sha256(s.encode('utf-8')).hexdigest()
        lua.execute('hash=function(s) return python_sha256(s) end;M=assert(load(module_source))();pool={0,1,2,3}'+'\n'+body)

    def test_replay_is_deterministic_and_covers_the_pool(self):
        self.run_case('''
            local seen={}
            for i=0,200 do
                local a=M.selection('seed','camp05',i,pool,hash)
                assert(a==M.selection('seed','camp05',i,pool,hash))
                seen[a]=true
            end
            for _,v in ipairs(pool) do assert(seen[v]) end
        ''')

    def test_camp_and_seed_change_the_sequence(self):
        self.run_case('''
            local function run(seed,camp) local t={};for i=0,30 do t[#t+1]=M.selection(seed,camp,i,pool,hash) end;return table.concat(t) end
            assert(run('a','camp05')~=run('b','camp05'));assert(run('a','camp05')~=run('a','camp23'))
        ''')

    def test_invalid_seed_refused(self):
        self.run_case('''
            assert(not pcall(M.selection,'','camp05',0,pool,hash))
            assert(not pcall(M.selection,'x'..string.char(1),'camp05',0,pool,hash))
            assert(not pcall(M.selection,'x','camp05',0,{},hash))
        ''')

if __name__=='__main__':unittest.main()
