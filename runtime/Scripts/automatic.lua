-- Chooses each generic camp's next composition. A camp's counter advances once for each fight against
-- it that ends without a Game Over, and the seed, camp and counter pick the composition from its pool.
-- The game's own respawning does the rest, so a camp changes the next time it spawns.
--
-- This runs on the game thread during recording sessions, so it must stay cheap: object path lookups
-- cost milliseconds, so anything lasting the whole process is found once, and tables only after a load.
local Lifecycle=require('lifecycle')
local StateStore=require('state_store')
local json=require('biome_json')
local tables=require('world_pools')
local M={}
local idle_seconds,battle_seconds=1,0.5
local load_ticks=3 -- this many seconds with no player and no battle means a load or a scene
local scan_retry_seconds=2
local scan_tries=15
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
function M.new(config)
    local self={fault=nil,store=nil,apis={},next_step=0,pawnless=0,pawn_seen=false,fight=nil,loaded={},current={},pending={},
        camp_table={},pools={},retry_at=0,need_sweep=true,tokens={}}
    for index,entry in ipairs(tables) do
        for target,camp in ipairs(entry.camps) do
            local pool={};for k=1,camp.options do pool[k]=k-1 end
            self.pools[camp.id]=pool
            self.camp_table[camp.id]={table=index,target=target}
        end
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
        self.store=StateStore.new({json=json,read=BiomeRandomizerReadState,write=BiomeRandomizerWriteState,
            write_async=BiomeRandomizerWriteStateAsync,random_seed=BiomeRandomizerRandomSeed,seed=config.seed,
            algorithm=Lifecycle.algorithm,scope='field-camps-v1',pools=self.pools})
        emit('selector_ready',{seed=self.store.seed,algorithm=Lifecycle.algorithm})
    end
    local function choice_of(camp,cycle)
        return Lifecycle.selection(self.store.seed,camp,cycle,self.pools[camp],BiomeRandomizerSHA256)
    end
    -- At most once per sweep: about 100 ms, and only ever just after a load.
    local function scan_spawn_actors()
        if self.scanned_this_sweep then return end
        self.scanned_this_sweep=true
        self.found_actors=BiomeRandomizerSpawnScan()
        emit('spawn_scan',{found=self.found_actors,spawn=json.decode(BiomeRandomizerSpawnStats())})
    end
    -- Point every camp in a loaded table at its chosen composition, and only once its spawn lists can
    -- hold that composition. A camp that isn't ready keeps the game's own enemies, which is always safe.
    local function prepare_table(index)
        local entry=tables[index]
        local object=resolve(entry.asset)
        if not valid(object) then return false end
        local status=json.decode(BiomeRandomizerTableStatus(object:GetAddress(),index-1))
        if not status.ok then error('table_guard:'..entry.region..':'..tostring(status.reason)) end
        local token=tostring(object:GetAddress())..':'..tostring(status.asset_content)
        if self.tokens[index]~=token then self.current[index]=nil end
        if self.current[index] then
            for target=1,#entry.camps do assert(status.choices[target]==self.current[index][target],'external_reference_change') end
        else
            -- A fresh table holds the original references. Anything else is another mod's write.
            for target=1,#entry.camps do assert(status.choices[target]==0,'preexisting_reference_change') end
        end
        self.tokens[index]=token;self.loaded[index]=object
        local changed=0;local waiting=0
        local current={};for target=1,#entry.camps do current[target]=status.choices[target] end
        for target,camp in ipairs(entry.camps) do
            local desired=choice_of(camp.id,self.store.cycles[camp.id].cycle)
            if desired~=current[target] then
                if not BiomeRandomizerSpawnReady(camp.id) then scan_spawn_actors() end
                if BiomeRandomizerSpawnReady(camp.id) then
                    local result=json.decode(BiomeRandomizerSetNext(object:GetAddress(),index-1,target-1,current[target],desired))
                    assert(result.ok and result.choices[target]==desired,'reference_unverified:'..tostring(result.reason))
                    current[target]=desired;changed=changed+1
                else
                    waiting=waiting+1
                end
            end
        end
        self.current[index]=current
        emit('table_ready',{region=entry.region,camps=#entry.camps,changed=changed,waiting=waiting,spawn=json.decode(BiomeRandomizerSpawnStats())})
        return waiting==0
    end
    -- A table can outlive the level that uses it. The next level rebuilds its spawn actors with
    -- empty lists, so a changed row left behind could ask for a size that isn't there yet, which
    -- crashes the game. So every load starts from the game's own references.
    local function restore_tables()
        local restored=0
        for index,entry in ipairs(tables) do
            local object=resolve(entry.asset)
            if valid(object) then
                local status=json.decode(BiomeRandomizerTableStatus(object:GetAddress(),index-1))
                if status.ok then
                    for target=1,#entry.camps do
                        if status.choices[target]~=0 then
                            local result=json.decode(BiomeRandomizerSetNext(object:GetAddress(),index-1,target-1,status.choices[target],0))
                            assert(result.ok,'restore_unverified:'..tostring(result.reason))
                            status=result;restored=restored+1
                        end
                    end
                end
            end
            self.current[index]=nil;self.tokens[index]=nil
        end
        emit('tables_restored',{rows=restored})
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
                local camp=text(battle:GetActorName(actor)):match('@(.+)$')
                if camp and self.pools[camp] and not self.fight.camps[camp] then
                    self.fight.camps[camp]=true
                    emit('fight_observed',{camp=camp,cycle=self.store.cycles[camp].cycle})
                end
            end
        end
    end
    local function finish_fight(battle,party)
        local fight=self.fight;self.fight=nil
        if fight.lost or not next(fight.camps) then return end
        if party_alive(battle,party)==0 then return end -- a Game Over, not a fight won or fled
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
            -- Past this point, with no pawn, the game may be loading or shutting down. Leave it alone.
            if not actor and self.pawnless>=load_ticks then return end
            local battle,party=api('EndBattleAPI'),api('EndPartyAPI')
            if not valid(battle) or not valid(party) then return end
            local in_battle=battle:IsInBattle()
            if type(in_battle)~='boolean' then return end
            if not actor and not in_battle then
                self.pawnless=self.pawnless+1
                if self.pawnless>=load_ticks then
                    self.fight=nil;self.loaded={};self.pawn_address=nil;self.need_sweep=true;self.pending={}
                    self.retry_at=0;self.tries=0;BiomeRandomizerSpawnReset()
                    if self.store then restore_tables() end
                end
                return
            end
            self.pawnless=0
            initialize()
            if in_battle then
                self.next_step=now+battle_seconds
                self.fight=self.fight or {camps={}}
                note_camps(battle)
                if party_alive(battle,party)==0 then self.fight.lost=true end
                return
            end
            if not actor then return end
            if self.fight then finish_fight(battle,party) end
            if now>=self.retry_at and (self.need_sweep or next(self.pending)) then
                self.retry_at=now+scan_retry_seconds
                self.scanned_this_sweep=false;self.found_actors=0
                local again=false
                for index,entry in ipairs(tables) do
                    if self.need_sweep or self.pending[entry.region] then
                        local ready=prepare_table(index)
                        -- Camps still waiting for their spawn lists get a few more tries.
                        if ready then self.pending[entry.region]=nil
                        elseif self.loaded[index] then self.pending[entry.region]=true;again=true end
                    end
                end
                self.need_sweep=false
                self.tries=(self.tries or 0)+1
                -- Once the actors exist, a camp still waiting simply has none, so stop looking.
                if not again or self.tries>=scan_tries or self.found_actors>0 then self.pending={} end
            end
        end)
        if not ok then fail(error_value) end
    end
    -- A territory actor from this region began play, so its table is about to matter. Only a flag:
    -- a level brings dozens of these at once, and this runs inside the engine's own call.
    function self:territory_begin(region)
        if self.fault or config.enabled~=true or type(region)~='string' then return end
        for index,entry in ipairs(tables) do
            if entry.region==region and not self.loaded[index] then self.pending[region]=true end
        end
    end
    return self
end
return M
