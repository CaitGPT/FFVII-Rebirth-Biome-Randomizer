"""Synthetic lifecycle sequences. These do not establish native respawn behavior."""
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
        lua.execute('hash=function(s) return python_sha256(s) end;M=assert(load(module_source))(); pools={camp05={0,1},camp23={0,1}}; s=M.new("test",pools,nil,hash);s:reset_epoch("load1");'+body)

    def test_streaming_absence_and_partial_kills_do_not_clear(self):
        self.run_case('''
            assert(s:observe_group('camp05','load1',{'a','b','c'},true))
            assert(s:death('camp05','load1','a',0))
            assert(not s:observe_group('camp05','load1',{},true))
            assert(not s:confirmed_clear('camp05','load1','victory'))
            assert(s.camps.camp05.cycle==0)
        ''')

    def test_retreat_defeat_and_unknown_outcomes_do_not_reroll(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a'},true);s:death('camp05','load1','a',0)
            for _,outcome in ipairs({'retreat','defeat','unknown'}) do
                assert(not s:confirmed_clear('camp05','load1',outcome))
            end
            assert(s.camps.camp05.cycle==0)
        ''')

    def test_full_clear_commits_once_and_matches_respawn(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a','b','c'},true)
            for _,id in ipairs({'a','b','c'}) do s:death('camp05','load1',id,0) end
            local p=assert(s:confirmed_clear('camp05','load1','victory'))
            assert(not s:confirmed_clear('camp05','load1','victory'))
            assert(s:commit(p,p.after));assert(not s:commit(p,p.after))
            assert(s.camps.camp05.cycle==1 and s.camps.camp23.cycle==0)
            assert(s:respawn('camp05','load1',p.after,{'d','e','f'},true))
            assert(s.camps.camp05.cycle==1)
        ''')

    def test_reload_ignores_stale_deaths_and_proposals(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a'},true);s:death('camp05','load1','a',0)
            local p=assert(s:confirmed_clear('camp05','load1','victory'))
            s:reset_epoch('load2')
            assert(not s:commit(p,p.after));assert(not s:death('camp05','load1','a',0))
            assert(s.camps.camp05.cycle==0)
        ''')

    def test_uncertain_write_and_wrong_respawn_latch_fault(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a'},true);s:death('camp05','load1','a',0)
            local p=assert(s:confirmed_clear('camp05','load1','victory'))
            assert(not s:commit(p,1-p.after));assert(s.fault)
            s:reset_epoch('load2');assert(s.fault);assert(not s:commit(p,p.after))
        ''')
        self.run_case('''
            s:observe_group('camp05','load1',{'a'},true);s:death('camp05','load1','a',0)
            local p=assert(s:confirmed_clear('camp05','load1','victory'));assert(s:commit(p,p.after))
            assert(not s:respawn('camp05','load1',1-p.after,{'b'},true));assert(s.fault)
        ''')

    def test_seed_replay_and_saved_cycle_are_deterministic(self):
        self.run_case('''
            local values={}
            for i=0,100 do values[M.selection('seed','camp05',i,{0,1},hash)]=true end
            assert(values[0] and values[1])
            local a=M.new('seed',pools,{camp05={cycle=17}},hash)
            local b=M.new('seed',pools,{camp05={cycle=17}},hash)
            assert(a.camps.camp05.choice==b.camps.camp05.choice)
            assert(a:checkpoint().camp05.cycle==17)
        ''')

    def test_unowned_and_nonzero_hp_deaths_are_rejected(self):
        self.run_case('''
            assert(not s:observe_group('quest','load1',{'x'},true))
            assert(not s:observe_group('camp05','load1',{'a','a'},true))
            s:observe_group('camp05','load1',{'a'},true)
            assert(not s:death('camp05','load1','x',0))
            assert(not s:death('camp05','load1','a',1))
            assert(not s:confirmed_clear('camp05','load1','victory'))
        ''')

    def test_stream_rebind_keeps_cycle_and_discards_old_deaths(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a','b','c'},true);s:death('camp05','load1','a',0)
            local choice=s.camps.camp05.choice
            assert(s:rebind_group('camp05','load1',choice,{'d','e','f'},true))
            assert(s.camps.camp05.cycle==0 and not next(s.camps.camp05.deaths))
            assert(not s:death('camp05','load1','a',0))
            assert(not s:confirmed_clear('camp05','load1','victory'))
        ''')

    def test_revival_and_defeat_cancel_invalidate_death_proof(self):
        self.run_case('''
            s:observe_group('camp05','load1',{'a'},true);s:death('camp05','load1','a',0)
            assert(s:alive('camp05','load1','a',1));assert(not s:confirmed_clear('camp05','load1','victory'))
            s:death('camp05','load1','a',0);assert(s:cancel_group('camp05','load1'))
            assert(not s:confirmed_clear('camp05','load1','victory'));assert(s.camps.camp05.cycle==0)
        ''')

if __name__=='__main__':unittest.main()
