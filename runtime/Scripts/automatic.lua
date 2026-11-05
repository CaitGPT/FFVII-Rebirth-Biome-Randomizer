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
local M={}
local idle_seconds,battle_seconds=1,0.5
local load_ticks=3 -- this many ticks with no player and no battle: stop touching the game's APIs
-- A level's groups spawn soon after its spawn actors appear, so they're looked for often. It's cheap.
local poll_seconds=0.25
local unlock_seconds=20 -- how long after a won assignment to wait for its enemies to be gone
local repeat_tries=8
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
        camp_table={},camp_info={},assignment_of={},pending_unlocks={},tokens={},poll_at=0,chosen={}}
    for index,entry in ipairs(tables) do
        for target,camp in ipairs(entry.camps) do
            self.camp_table[camp.id]={table=index,target=target}
            self.camp_info[camp.id]={entry=entry,camp=camp}
        end
        for _,unlock in ipairs(entry.unlocks) do self.assignment_of[unlock.territory]={entry=entry,name=entry.names[unlock.enemy+1]} end
    end
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
    -- What stands in each slot and how many: seeded by camp and counter, from the camp's own
    -- enemies plus any its region's won assignments have added. Salt k gives another roll.
    local function roll(camp,cycle,k)
        local info=self.camp_info[camp];local names=info.entry.names;local unlocked=self.store.unlocked_set
        local tag=k>0 and ('~'..k) or ''
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
    local function prepare_table(index)
        local entry=tables[index]
        local object=resolve(entry.asset)
        if not valid(object) then self.loaded[index]=nil;return false end
        local status=json.decode(BiomeRandomizerTableStatus(object:GetAddress(),index-1))
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
        if #lines>0 then
            local result=json.decode(BiomeRandomizerSetMany(object:GetAddress(),index-1,table.concat(lines,';')))
            assert(result.ok,'reference_unverified:'..tostring(result.reason))
            for target,desired in pairs(wanted) do
                assert(result.choices[target]==desired,'reference_unverified');current[target]=desired;changed=changed+1
            end
        end
        self.current[index]=current
        emit('table_ready',{region=entry.region,camps=#entry.camps,changed=changed,waiting=waiting,spawn=json.decode(BiomeRandomizerSpawnStats())})
        return waiting==0
    end
    -- A table can outlive the level that uses it, and the new level's spawn actors start with empty
    -- lists. A changed row left behind could ask for a size that isn't there yet, which crashes the
    -- game. So a region's table goes back to the game's own lists as its level leaves.
    local function restore_table(index)
        local entry=tables[index]
        local object=resolve(entry.asset)
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
        if result.gone>0 then
            local regions={}
            for camp in result.gone_camps:gmatch('[^,]+') do
                local where=self.camp_table[camp];if where then regions[where.table]=true end
            end
            local restored=0
            for index in pairs(regions) do restored=restored+restore_table(index) end
            emit('level_left',{actors=result.gone,restored=restored})
        end
        if result.fresh>0 then
            initialize()
            for index in ipairs(tables) do prepare_table(index) end
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
    local function check_unlocks(battle,now)
        for territory,pending in pairs(self.pending_unlocks) do
            local standing=false
            for name in pairs(pending.names) do
                local actor=battle:GetCharaFromActorName(FName(name),true)
                if valid(actor) and (battle:GetCharaHP(actor) or 0)>0 then standing=true end
            end
            if not standing then
                self.pending_unlocks[territory]=nil
                local enemy=self.assignment_of[territory].name
                if self.store:unlock(enemy) then
                    self.chosen={}
                    emit('assignment_unlocked',{territory=territory,enemy=enemy})
                    -- Only compositions chosen from now on can use it: the next sweep or fight picks it up.
                end
            elseif now>pending.until_at then
                self.pending_unlocks[territory]=nil -- still standing: the party fled
            end
        end
    end
    function self:step()
        if self.fault or config.enabled~=true then return end
        local now=os.clock()
        if now<self.next_step then return end
        self.next_step=now+idle_seconds
        local ok,error_value=pcall(function()
            if BiomeRandomizerStateWriteFailed() and not self.write_warned then
                self.write_warned=true;emit('state_write_failed',{})
            end
            local actor=pawn()
            if not actor and not self.pawn_seen then return end -- the title screen: don't touch the game yet
            self.pawn_seen=true
            self.next_step=math.min(self.next_step,now+poll_seconds)
            poll_spawn_actors(now)
            -- Past this point, with no pawn, the game may be loading or shutting down. Leave it alone.
            if not actor and self.pawnless>=load_ticks then return end
            local battle,party=api('EndBattleAPI'),api('EndPartyAPI')
            if not valid(battle) or not valid(party) then return end
            local in_battle=battle:IsInBattle()
            if type(in_battle)~='boolean' then return end
            if not actor and not in_battle then
                self.pawnless=self.pawnless+1
                if self.pawnless>=load_ticks then self.fight=nil;self.pawn_address=nil end
                return
            end
            self.pawnless=0
            initialize()
            if in_battle then
                self.next_step=now+battle_seconds
                self.fight=self.fight or {camps={},assignments={}}
                note_camps(battle)
                if party_alive(battle,party)==0 then self.fight.lost=true end
                return
            end
            if not actor then return end
            if self.fight then finish_fight(battle,party,now) end
            if next(self.pending_unlocks) then check_unlocks(battle,now) end
        end)
        if not ok then fail(error_value) end
    end
    -- For the offline fixtures only: the composition a camp gets at a counter value.
    function self.choice_of_for_tests(camp,cycle) initialize();return choice_of(camp,cycle) end
    return self
end
return M
