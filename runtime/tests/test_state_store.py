"""Synthetic journal crash/corruption cases; not native filesystem acceptance."""
from pathlib import Path
import hashlib
import unittest
from lupa.lua54 import LuaRuntime

ROOT=Path(__file__).parents[1]/'Scripts'

class Store(unittest.TestCase):
    def run_case(self,body):
        lua=LuaRuntime()
        for name in ('biome_json','state_store','lifecycle'):
            lua.globals()[name+'_source']=(ROOT/(name+'.lua')).read_text(encoding='utf-8')
        lua.globals().python_sha=lambda value:hashlib.sha256(value.encode()).hexdigest()
        lua.execute('''
            json=assert(load(biome_json_source))();Store=assert(load(state_store_source))();Life=assert(load(lifecycle_source))()
            hash=function(s) return python_sha(s) end
            pools={camp05={0,1},camp23={0,1}};disk='';writes=0;write_ok=true
            function options(seed)
                return {json=json,read=function() return disk,true end,
                    write=function(value) writes=writes+1;if not write_ok then return false end;disk=value;return true end,
                    random_seed=function() return 'created-seed' end,seed=seed or 'auto',
                    algorithm=Life.algorithm,scope='fixture',pools=pools,
                    selection=function(seed,camp,cycle,pool) return Life.selection(seed,camp,cycle,pool,hash) end}
            end
        '''+body)

    def test_new_auto_seed_is_written_once_and_reused(self):
        self.run_case('''
            local a=Store.new(options());assert(a.seed=='created-seed' and writes==1)
            local b=Store.new(options());assert(b.seed==a.seed and writes==1)
            assert(b.cycles.camp05.cycle==0 and b.cycles.camp23.cycle==0)
        ''')

    def test_prepared_clear_recovers_exactly_once_after_crash(self):
        self.run_case('''
            local a=Store.new(options('613'))
            local p={camp='camp05',cycle=1,before=Life.selection('613','camp05',0,pools.camp05,hash),
                after=Life.selection('613','camp05',1,pools.camp05,hash)}
            a:prepare(p);assert(json.decode(disk).pending.cycle==1)
            local b=Store.new(options('613'));assert(b.cycles.camp05.cycle==1 and not json.decode(disk).pending)
            local before=writes;local c=Store.new(options('613'));assert(c.cycles.camp05.cycle==1 and writes==before)
        ''')

    def test_failed_write_refuses_start_or_commit(self):
        self.run_case('''
            write_ok=false;assert(not pcall(function() Store.new(options()) end));assert(disk=='')
        ''')
        self.run_case('''
            local a=Store.new(options('s'));write_ok=false
            local p={camp='camp05',cycle=1,before=Life.selection('s','camp05',0,pools.camp05,hash),
                after=Life.selection('s','camp05',1,pools.camp05,hash)}
            assert(not pcall(function() a:prepare(p) end));assert(not json.decode(disk).pending)
        ''')

    def test_corrupt_or_incompatible_state_never_silently_resets(self):
        self.run_case('''
            disk='{broken';assert(not pcall(function() Store.new(options()) end));assert(writes==0)
            disk='';Store.new(options('s'));local good=json.decode(disk)
            for _,mutate in ipairs({function(d) d.version=99 end,function(d) d.scope='different' end,
                function(d) d.cycles.camp05.cycle=-1 end,function(d) d.cycles.quest={cycle=0} end,
                function(d) d.cycles.camp23=nil end}) do
                local d=json.decode(json.encode(good));mutate(d);disk=json.encode(d)
                local before=writes;assert(not pcall(function() Store.new(options('s')) end));assert(writes==before)
            end
        ''')

    def test_explicit_seed_change_starts_new_counters(self):
        self.run_case('''
            local a=Store.new(options('first'));local first=a.seed
            local b=Store.new(options('second'));assert(b.seed=='second' and b.cycles.camp05.cycle==0 and writes==2)
        ''')

    def test_commit_cannot_advance_an_unselected_camp(self):
        self.run_case('''
            local a=Store.new(options('s'))
            local p={camp='camp05',cycle=1,before=Life.selection('s','camp05',0,pools.camp05,hash),
                after=Life.selection('s','camp05',1,pools.camp05,hash)}
            a:prepare(p)
            assert(not pcall(function() a:commit({camp05={cycle=1},camp23={cycle=1}}) end))
            a:commit({camp05={cycle=1},camp23={cycle=0}})
            assert(json.decode(disk).cycles.camp05.cycle==1 and not json.decode(disk).pending)
        ''')

if __name__=='__main__':unittest.main()
