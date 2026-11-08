-- Chooses each generic camp's next composition. A camp's counter advances once for each fight against
-- it that ends without a Game Over, and the seed, camp and counter pick what stands in each of its slots
-- and how many there are. The game's own respawning does the rest, so a camp changes when it next spawns.
--
-- This runs on the game thread during recording sessions, so it must stay cheap: object path lookups
-- cost milliseconds, so anything lasting the whole process is found once, and tables only on a level change.
local Lifecycle=require('lifecycle')
local StateStore=require('state_store')
local json=require('biome_json')
local tables=require('world_pools')
local Squads=require('squads')
local M={}
-- About one roll in five makes a camp a squad, where its region has one. Chapter select is the game's own flag
-- for it being released, which happens when Chapter 14 is cleared.
local default_squad_percent=20
local chapter_select_flag='stfComn_Release_ChapterSelect'
local hundred={};for k=1,100 do hundred[k]=k end
local idle_seconds,battle_seconds=1,0.5
local load_ticks=3 -- this many ticks with no player and no battle: stop touching the game's APIs
-- A level's groups spawn soon after its spawn actors appear, so they're looked for often. It's cheap.
local poll_seconds=0.25
local unlock_seconds=20 -- how long after a won assignment to wait for its enemies to be gone
local flag_delay=3 -- seconds after a load or a fight before reading the save's assignment records
local repeat_tries=8
-- A table whose camps arrived but which can't be found yet is looked for again this many polls, then left
-- until more of its camps arrive. Each failed lookup searches the game's objects, so it isn't free.
local lookup_tries=4
-- A step slower than this reports which of its parts took the time, at most once every slow_report_seconds.
local slow_step_ms,slow_report_seconds=100,1
local function valid(object)
    local ok,result=pcall(function() return object and object:IsValid() end)
    return ok and result==true
end
local function resolve(path)
    local ok,object=pcall(StaticFindObject,path)
    if ok and valid(object) then return object end
end
local function text(value) return value and value:ToString() or '' end
local function emit(event,fields)
    fields=fields or {};fields.event=event;fields.at_utc=os.date('!%Y-%m-%dT%H:%M:%SZ')
    print('[BiomeRandomizerRuntime] '..json.encode(fields)..string.char(10))
end
-- Out-parameter and array entries can hold their object behind :get().
local function unwrap(value)
    if type(value)~='userdata' then return value end
    local ok,kind=pcall(function() return value:type() end)
    if ok and (kind=='RemoteUnrealParam' or kind=='LocalUnrealParam') then
        local got,inner=pcall(function() return value:get() end)
        return got and inner or nil
    end
    return value
end
local function key_of(enemies,counts)
    return 't:'..table.concat(enemies,'.')..'/c:'..table.concat(counts,'.')
end
-- A total spread over the slots, as evenly as possible.
local function split(total,slots)
    local out={}
    for k=1,slots do out[k]=total//slots+(k<=total%slots and 1 or 0) end
    return out
end
function M.new(config)
    local self={fault=nil,store=nil,apis={},next_step=0,pawnless=0,pawn_seen=false,fight=nil,loaded={},current={},
        camp_table={},camp_info={},assignment_of={},pending_unlocks={},tokens={},poll_at=0,chosen={},
        pending_tables={},found={},sections={},slow_reported_at=nil,slow_unreported=0,
        gates={chapter_select=false,chapter=0},active_units={}}
    local squad_percent=default_squad_percent
    if type(config.squad_percent)=='number' and config.squad_percent>=0 and config.squad_percent<=100 then
        squad_percent=config.squad_percent -- for testing; not in the shipped config
    end
    -- Timing for the slow-step report: each lap adds the time since the last one to its part of the step.
    local clock=type(BiomeRandomizerClockMs)=='function' and BiomeRandomizerClockMs or nil
    local lap_at=0
    local function lap(part)
        if not clock then return end
        local at=clock();self.sections[part]=(self.sections[part] or 0)+(at-lap_at);lap_at=at
    end
    for index,entry in ipairs(tables) do
        for target,camp in ipairs(entry.camps) do
            self.camp_table[camp.id]={table=index,target=target}
            self.camp_info[camp.id]={entry=entry,camp=camp}
        end
        for _,unlock in ipairs(entry.unlocks) do
            self.assignment_of[unlock.territory]={entry=entry,name=entry.names[unlock.enemy+1],flag=unlock.flag}
        end
    end
    local check_flags -- defined with the unlock checks below; the spawn poll calls it first
    local function fail(reason)
        if not self.fault then self.fault=tostring(reason);emit('automatic_disabled',{reason=self.fault}) end
    end
    local function api(name)
        local object=self.apis[name]
        if valid(object) then return object end
        object=resolve('/Script/EndGame.Default__'..name) or resolve('/Script/EndDataBase.Default__'..name)
        self.apis[name]=object
        return object
    end
    local function pawn()
        local engine=self.engine
        if not valid(engine) then
            engine=FindFirstOf('GameEngine');self.engine=engine
            if not valid(engine) then return nil end
        end
        local statics=self.statics
        if not valid(statics) then
            statics=resolve('/Script/Engine.Default__GameplayStatics');self.statics=statics
            if not valid(statics) then return nil end
        end
        local viewport=engine.GameViewport
        if not valid(viewport) then return nil end
        local actor=statics:GetPlayerPawn(viewport,0)
        if not valid(actor) then return nil end
        local address=actor:GetAddress()
        if address==self.pawn_address then return actor end
        local class=actor:GetClass():GetFName():ToString()
        if not class:match('^PC%d%d%d%d_') and not class:match('^VE%d%d%d%d_') then return nil end
        if not actor:GetFullName():find('/Game/Level/Game/EndGame.EndGame:',1,true) then return nil end
        self.pawn_address=address
        self.flags_due=os.clock() -- a new pawn: a load, so maybe another save's records
        return actor
    end
    local function initialize()
        if self.store then return end
        local camps={};for camp in pairs(self.camp_table) do camps[camp]=true end
        self.store=StateStore.new({json=json,read=BiomeRandomizerReadState,write=BiomeRandomizerWriteState,
            write_async=BiomeRandomizerWriteStateAsync,random_seed=BiomeRandomizerRandomSeed,seed=config.seed,
            algorithm=Lifecycle.algorithm,scope='field-camps-v1',pools=camps})
        emit('selector_ready',{seed=self.store.seed,algorithm=Lifecycle.algorithm,unlocked=#self.store.unlocked})
    end
    local function pick(salt,cycle,pool)
        return Lifecycle.selection(self.store.seed,salt,cycle,pool,BiomeRandomizerSHA256)
    end
    -- A squad: every slot from the region's squad pool, never monsters, and at most one J-Unit Sweeper, which
    -- then stands alone in its slot. The camp's own range of totals still sets how many there are.
    local function squad_roll(camp,cycle,tag,pool)
        local info=self.camp_info[camp]
        local enemies={};local sweeper_at
        local without={};for _,v in ipairs(pool) do if v~=Squads.sweeper then without[#without+1]=v end end
        for slot=1,#info.camp.base do
            local choices=(sweeper_at and #without>0) and without or pool
            local enemy=pick(camp..'#q'..slot..tag,cycle,choices)
            if enemy==Squads.sweeper then sweeper_at=slot end
            enemies[slot]='r'..enemy
        end
        local counts=split(pick(camp..'#qn'..tag,cycle,info.camp.totals),#enemies)
        if sweeper_at then
            local extra=counts[sweeper_at]-1;counts[sweeper_at]=1
            for slot=1,#counts do if slot~=sweeper_at then counts[slot]=counts[slot]+extra;break end end
        end
        return key_of(enemies,counts)
    end
    -- What stands in each slot and how many: seeded by camp and counter, from the camp's own
    -- enemies plus any its region's won assignments have added. Salt k gives another roll.
    local function roll(camp,cycle,k)
        local info=self.camp_info[camp];local names=info.entry.names;local unlocked=self.store.unlocked_set
        local tag=k>0 and ('~'..k) or ''
        local unit=Squads.unit(info.entry.region,camp);local active=unit and self.active_units[unit]
        local squad=active and #active.types>0 and active.types or nil
        if squad and squad_percent>0 and pick(camp..'#squad'..tag,cycle,hundred)<=squad_percent then
            return squad_roll(camp,cycle,tag,squad)
        end
        local enemies={}
        for slot,base in ipairs(info.camp.base) do
            local pool={};for _,enemy in ipairs(base) do pool[#pool+1]=enemy end
            for _,enemy in ipairs(info.camp.extra[slot]) do
                if unlocked[names[enemy+1]] then pool[#pool+1]=enemy end
            end
            enemies[slot]=pick(camp..'#'..slot..tag,cycle,pool)
        end
        local total=pick(camp..'#n'..tag,cycle,info.camp.totals)
        return key_of(enemies,split(total,#enemies))
    end
    -- Never the same composition twice running: a roll matching the one before it rolls again. Each
    -- camp's sequence is worked out once and kept, until a won assignment changes what can be rolled.
    local function choice_of(camp,cycle)
        local known=self.chosen[camp]
        if not known then known={[-1]=self.camp_info[camp].camp.original};self.chosen[camp]=known end
        for c=0,cycle do
            if known[c]==nil then
                local key=roll(camp,c,0);local k=0
                while key==known[c-1] and k<repeat_tries do k=k+1;key=roll(camp,c,k) end
                known[c]=key
            end
        end
        return known[cycle]
    end
    -- Point every camp in a loaded table at its chosen composition, and only once its spawn lists can
    -- hold that composition. A camp that isn't ready keeps the game's own enemies, which is always safe.
    -- The squad types each loaded unit uses this visit. The game spawns only a couple of squad enemy types it
    -- doesn't load for the area itself, so the units loaded at once share that budget: one unit alone gets two
    -- types, two at once (Corel's halves) one each, and a unit arriving with the budget spent gets none this visit
    -- (its camps stay monsters). A Sweeper is never a unit's only type. Each visit draws a new set.
    local function choose_types(unit,pool,count,visit)
        local left={};for _,v in ipairs(pool) do left[#left+1]=v end
        local out={}
        for i=1,count do
            local candidates={}
            for _,v in ipairs(left) do if not (count==1 and v==Squads.sweeper) then candidates[#candidates+1]=v end end
            if #candidates==0 then break end
            local chosen=pick('squadset:'..unit..'#'..i,visit,candidates);out[#out+1]=chosen
            for k,v in ipairs(left) do if v==chosen then table.remove(left,k);break end end
        end
        table.sort(out)
        return out
    end
    local function activate_units(index)
        local entry=tables[index];local seen,fresh={},{}
        for _,camp in ipairs(entry.camps) do
            local unit=Squads.unit(entry.region,camp.id)
            if unit and not seen[unit] then seen[unit]=true;if not self.active_units[unit] then fresh[#fresh+1]=unit end end
        end
        if #fresh==0 then return end
        table.sort(fresh)
        local used=0;for _,active in pairs(self.active_units) do used=used+#active.types end
        local left=math.max(0,Squads.type_budget-used)
        local each=left>=2*#fresh and 2 or (left>=#fresh and 1 or 0)
        for k,unit in ipairs(fresh) do
            local share=each>0 and each or (k<=left and 1 or 0)
            local pool=Squads.unit_pool(unit,self.gates) or {}
            local types={}
            if share>0 and #pool>0 then types=choose_types(unit,pool,math.min(share,#pool),self.store:next_visit(unit)) end
            self.active_units[unit]={types=types,table=index}
            local names={};for _,v in ipairs(types) do names[#names+1]=Squads.resident[v+1] end
            emit('squad_types',{unit=unit,types=names,budget_left=left})
        end
        self.chosen={} -- squad camps now draw from these types
    end
    local function release_units(index)
        for unit,active in pairs(self.active_units) do if active.table==index then self.active_units[unit]=nil end end
    end
    -- A table object, once found, is kept for the session and reused while it's valid, including on later
    -- visits: looking one up by its path took about 30 ms live, and every table at each arrival cost hundreds.
    -- The identity check in the table status and the token below still catch a table reloaded in its place.
    local function prepare_table(index)
        local entry=tables[index]
        local object=self.loaded[index]
        if not valid(object) then object=self.found[index] end
        if not valid(object) then object=resolve(entry.asset);lap('lookup') end
        if not valid(object) then self.loaded[index]=nil;self.found[index]=nil;return nil end
        self.found[index]=object
        local status=json.decode(BiomeRandomizerTableStatus(object:GetAddress(),index-1))
        lap('table_check')
        if not status.ok then error('table_guard:'..entry.region..':'..tostring(status.reason)) end
        local token=tostring(object:GetAddress())..':'..tostring(status.asset_content)
        if self.tokens[index]~=token then self.current[index]=nil end
        if self.current[index] then
            for target=1,#entry.camps do assert(status.choices[target]==self.current[index][target],'external_reference_change') end
        else
            -- A fresh table holds the original lists. Anything else is another writer.
            for target=1,#entry.camps do assert(status.choices[target]=='o','preexisting_reference_change') end
        end
        self.tokens[index]=token;self.loaded[index]=object
        activate_units(index)
        local changed=0;local waiting=0;local lines={};local wanted={}
        local current={};for target=1,#entry.camps do current[target]=status.choices[target] end
        for target,camp in ipairs(entry.camps) do
            local desired=choice_of(camp.id,self.store.cycles[camp.id].cycle)
            if desired~=current[target] then
                if BiomeRandomizerSpawnReady(camp.id) then
                    lines[#lines+1]=(target-1)..'|'..current[target]..'|'..desired;wanted[target]=desired
                else
                    waiting=waiting+1
                end
            end
        end
        lap('choices')
        if #lines>0 then
            local result=json.decode(BiomeRandomizerSetMany(object:GetAddress(),index-1,table.concat(lines,';')))
            assert(result.ok,'reference_unverified:'..tostring(result.reason))
            for target,desired in pairs(wanted) do
                assert(result.choices[target]==desired,'reference_unverified');current[target]=desired;changed=changed+1
            end
            lap('table_write')
        end
        self.current[index]=current
        emit('table_ready',{region=entry.region,camps=#entry.camps,changed=changed,waiting=waiting,spawn=json.decode(BiomeRandomizerSpawnStats())})
        lap('report')
        return waiting==0
    end
    -- At most one table a step, so a load that brings several regions' camps spreads the work out. A camp
    -- whose table isn't done yet keeps the game's own enemies, which is always safe.
    local function prepare_next()
        local index
        for candidate in pairs(self.pending_tables) do if not index or candidate<index then index=candidate end end
        if not index then return end
        local tries=self.pending_tables[index]
        if prepare_table(index)==nil and tries<lookup_tries then self.pending_tables[index]=tries+1
        else self.pending_tables[index]=nil end
    end
    -- A table can outlive the level that uses it, and the new level's spawn actors start with empty
    -- lists. A changed row left behind could ask for a size that isn't there yet, which crashes the
    -- game. So a region's table goes back to the game's own lists as its level leaves.
    -- Only a table this mod prepared can hold its changes, and that one is still at hand, so nothing is looked up.
    local function restore_table(index)
        local entry=tables[index]
        local object=self.loaded[index]
        release_units(index)
        self.loaded[index]=nil;self.current[index]=nil;self.tokens[index]=nil
        if not valid(object) then return 0 end
        local status=json.decode(BiomeRandomizerTableStatus(object:GetAddress(),index-1))
        if not status.ok then return 0 end
        local lines={}
        for target=1,#entry.camps do
            if status.choices[target]~='o' then lines[#lines+1]=(target-1)..'|'..status.choices[target]..'|o' end
        end
        if #lines>0 then
            local result=json.decode(BiomeRandomizerSetMany(object:GetAddress(),index-1,table.concat(lines,';')))
            assert(result.ok,'restore_unverified:'..tostring(result.reason))
        end
        return #lines
    end
    -- New spawn actors are filled by the poll itself; then their camps can change. Actors that have
    -- gone mean a level is unloading, so its tables go back to the original before the next one.
    local function poll_spawn_actors(now)
        if now<self.poll_at then return end
        self.poll_at=now+poll_seconds
        local engine=self.engine;if not valid(engine) then return end
        local viewport=engine.GameViewport;if not valid(viewport) then return end
        local world=viewport.World;if not valid(world) then return end
        local result=json.decode(BiomeRandomizerSpawnPoll(world:GetAddress()))
        lap('spawn_poll')
        if result.gone>0 then
            local regions={}
            for camp in result.gone_camps:gmatch('[^,]+') do
                local where=self.camp_table[camp];if where then regions[where.table]=true end
            end
            local restored=0
            for index in pairs(regions) do restored=restored+restore_table(index) end
            self.flags_checked=false -- leaving a level: a load or fast travel, maybe into another save
            emit('level_left',{actors=result.gone,restored=restored})
            lap('restore')
        end
        if result.fresh>0 then
            initialize()
            -- A load streams spawn levels in before the pawn: start it with its save's unlocks. Once a load.
            if not self.flags_checked then self.flags_checked=true;check_flags();lap('flags') end
            -- Only the tables of the camps that arrived. A list cut short means camps went unnamed: all tables.
            local named=0
            for camp in (result.fresh_camps or ''):gmatch('[^,]+') do
                named=named+1
                local where=self.camp_table[camp]
                if where then self.pending_tables[where.table]=self.pending_tables[where.table] or 0 end
            end
            if named<result.fresh then
                for index in ipairs(tables) do self.pending_tables[index]=self.pending_tables[index] or 0 end
            end
        end
    end
    local function party_alive(battle,party)
        local count=party:GetBattleMemberCount()
        if type(count)~='number' or count<1 or count>8 or count%1~=0 then return nil end
        local alive=0
        for index=0,count-1 do
            local actor=party:GetBattleMember(index)
            if not valid(actor) then return nil end
            local hp=battle:GetCharaHP(actor)
            if type(hp)~='number' then return nil end
            if hp>0 then alive=alive+1 end
        end
        return alive
    end
    -- The battle's own roster names each enemy's territory: mobgrasa_Mu_000@Grassland_mob_05.
    local function note_camps(battle)
        local out={}
        local ok=pcall(function() battle:GetEnemyMembersRef(out) end)
        if not ok then return end
        for _,entry in ipairs(out) do
            local actor=unwrap(entry)
            if valid(actor) then
                local name=text(battle:GetActorName(actor))
                local camp=name:match('@(.+)$')
                if camp and self.camp_table[camp] and not self.fight.camps[camp] then
                    self.fight.camps[camp]=true
                    emit('fight_observed',{camp=camp,cycle=self.store.cycles[camp].cycle})
                elseif camp and self.assignment_of[camp] then
                    self.fight.assignments[camp]=self.fight.assignments[camp] or {}
                    self.fight.assignments[camp][name]=true
                end
            end
        end
    end
    local function finish_fight(battle,party,now)
        local fight=self.fight;self.fight=nil
        if fight.lost then return end
        if party_alive(battle,party)==0 then return end -- a Game Over, not a fight won or fled
        if next(fight.assignments) then self.flags_due=now+flag_delay end
        -- An assignment counts as won once its enemies are gone from the field, not merely left behind.
        for territory,names in pairs(fight.assignments) do
            self.pending_unlocks[territory]={names=names,until_at=now+unlock_seconds}
        end
        if not next(fight.camps) then return end
        local cycles={};for camp,row in pairs(self.store.cycles) do cycles[camp]={cycle=row.cycle} end
        for camp in pairs(fight.camps) do
            local cycle=cycles[camp].cycle+1;cycles[camp].cycle=cycle
            self.store:save(camp,cycles)
            local desired=choice_of(camp,cycle)
            local where=self.camp_table[camp];local object=self.loaded[where.table];local current=self.current[where.table]
            local before=current and current[where.target]
            if object and current and before~=desired and BiomeRandomizerSpawnReady(camp) then
                local result=json.decode(BiomeRandomizerSetNext(object:GetAddress(),where.table-1,where.target-1,before,desired))
                assert(result.ok and result.choices[where.target]==desired,'reference_unverified:'..tostring(result.reason))
                current[where.target]=desired
            end
            emit('cycle_committed',{camp=camp,cycle=cycle,before=before,after=desired})
        end
    end
    local function unlock(territory,enemy,source)
        if self.store:unlock(enemy) then
            self.chosen={}
            emit('assignment_unlocked',{territory=territory,enemy=enemy,source=source})
            -- Only compositions chosen from now on can use it: the next sweep or fight picks it up.
        end
    end
    -- The save's own record of each won Combat Assignment: the World Report's completion flag, the same one
    -- the Fiend Intel screen reads. This is what lets assignments won before the mod was installed count.
    -- What the loaded save allows squads to use: its chapter, and whether chapter select is released.
    local function read_gates(db)
        local ok_progress,progress=pcall(function() return db:GetChapterProgress() end)
        local ok_flag,released=pcall(function() return db:IsStoryFlag(FName(chapter_select_flag)) end)
        if not ok_progress or type(progress)~='number' or not ok_flag or type(released)~='boolean' then return end
        local gates={chapter_select=released,chapter=progress//1000}
        if gates.chapter_select~=self.gates.chapter_select or gates.chapter~=self.gates.chapter then
            self.gates=gates;self.chosen={}
            emit('squad_gates',{chapter=gates.chapter,chapter_progress=progress,chapter_select=gates.chapter_select})
        end
    end
    function check_flags()
        local db=api('EndDataBaseAPI')
        if not valid(db) then return end
        read_gates(db)
        for territory,info in pairs(self.assignment_of) do
            if info.flag and not self.store.unlocked_set[info.name] then
                local ok,won=pcall(function() return db:IsStoryFlag(FName(info.flag)) end)
                if ok and won==true then unlock(territory,info.name,'save') end
            end
        end
    end
    local function check_unlocks(battle,now)
        for territory,pending in pairs(self.pending_unlocks) do
            local standing=false
            for name in pairs(pending.names) do
                local actor=battle:GetCharaFromActorName(FName(name),true)
                if valid(actor) and (battle:GetCharaHP(actor) or 0)>0 then standing=true end
            end
            if not standing then
                self.pending_unlocks[territory]=nil
                unlock(territory,self.assignment_of[territory].name,'fight')
            elseif now>pending.until_at then
                self.pending_unlocks[territory]=nil -- still standing: the party fled
            end
        end
    end
    -- Which parts of a slow step took the time. A part that is only a game call (pawn, battle_state, flags)
    -- also holds any other mod's queued game-thread work that the engine ran inside that call.
    local function report_slow(total,now)
        if total<slow_step_ms then return end
        if self.slow_reported_at and now-self.slow_reported_at<slow_report_seconds then
            self.slow_unreported=self.slow_unreported+1;return
        end
        local parts,counted={},0
        for part,ms in pairs(self.sections) do parts[part]=math.floor(ms*10+0.5)/10;counted=counted+ms end
        parts.other=math.floor((total-counted)*10+0.5)/10
        emit('slow_step',{ms=math.floor(total*10+0.5)/10,parts=parts,unreported_since_last=self.slow_unreported,
            pending_tables=(function() local n=0;for _ in pairs(self.pending_tables) do n=n+1 end;return n end)()})
        self.slow_reported_at=now;self.slow_unreported=0
    end
    function self:step()
        if self.fault or config.enabled~=true then return end
        local now=os.clock()
        if now<self.next_step then return end
        self.next_step=now+idle_seconds
        local started=clock and clock() or 0
        lap_at=started;self.sections={}
        local ok,error_value=pcall(function()
            if BiomeRandomizerStateWriteFailed() and not self.write_warned then
                self.write_warned=true;emit('state_write_failed',{})
            end
            local actor=pawn()
            lap('pawn')
            if not actor and not self.pawn_seen then return end -- the title screen: don't touch the game yet
            self.pawn_seen=true
            self.next_step=math.min(self.next_step,now+poll_seconds)
            -- Before the camp tables are prepared, so a load starts with its save's unlocks.
            if actor and self.store and self.flags_due and now>=self.flags_due then self.flags_due=nil;check_flags();lap('flags') end
            poll_spawn_actors(now)
            prepare_next()
            -- Past this point, with no pawn, the game may be loading or shutting down. Leave it alone.
            if not actor and self.pawnless>=load_ticks then return end
            local battle,party=api('EndBattleAPI'),api('EndPartyAPI')
            if not valid(battle) or not valid(party) then return end
            local in_battle=battle:IsInBattle()
            lap('battle_state')
            if type(in_battle)~='boolean' then return end
            if not actor and not in_battle then
                self.pawnless=self.pawnless+1
                if self.pawnless>=load_ticks then self.fight=nil;self.pawn_address=nil;self.flags_checked=false end
                return
            end
            self.pawnless=0
            initialize()
            if actor and self.flags_due and now>=self.flags_due then self.flags_due=nil;check_flags();lap('flags') end
            if in_battle then
                self.next_step=now+battle_seconds
                self.fight=self.fight or {camps={},assignments={}}
                note_camps(battle)
                if party_alive(battle,party)==0 then self.fight.lost=true end
                lap('battle')
                return
            end
            if not actor then return end
            if self.fight then finish_fight(battle,party,now);lap('fight_end') end
            if next(self.pending_unlocks) then check_unlocks(battle,now);lap('unlocks') end
        end)
        if not ok then fail(error_value) end
        if clock then report_slow(clock()-started,now) end
    end
    -- For the offline fixtures only: the composition a camp gets at a counter value.
    function self.choice_of_for_tests(camp,cycle) initialize();return choice_of(camp,cycle) end
    function self.read_gates_for_tests(db) read_gates(db) end
    function self.activate_for_tests(index) initialize();activate_units(index) end
    function self.release_for_tests(index) release_units(index) end
    return self
end
return M
