local Lifecycle=require('lifecycle')
local StateStore=require('state_store')
local json=require('biome_json')
local M={}
local ids={'Grassland_mob_05','Grassland_mob_23','Grassland_mob_29','Grassland_mob_30'}
local pools={};for _,camp in ipairs(ids) do pools[camp]={0,1} end
local asset_path='/Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory'
local asset_full='EndDataObjectEnemyTerritory '..asset_path
local first_names={'mobgrasa_KalmFang_000','mobgrasa_Mu_000'}
local specs={'CharaSpec_EN2000_05_GuardHound_KalmFangEnd2','CharaSpec_EN2204_00_Mu_StandardEnd2'}
local orc_spec='CharaSpec_EN2211_01_Ogre_OrcEnd2'
-- Work is paced by distance, because object path lookups cost milliseconds on
-- the game thread and this game is recorded for video. World positions of the
-- four territories (cm), read from the live game's territory actors.
local camp_positions={Grassland_mob_05={131878,-71156},Grassland_mob_23={171443,-71068},
    Grassland_mob_29={120825,-58499},Grassland_mob_30={196655,-73926}}
local near_cm,region_cm=20000,250000
local far_seconds,near_seconds=1,0.5
local members_seconds,table_seconds,retry_seconds,territory_seconds=2,5,5,5
local pawnless_limit=3
local function valid(object)
    local ok,result=pcall(function() return object and object:IsValid() end)
    return ok and result==true
end
local function resolve(path)
    local ok,object=pcall(StaticFindObject,path)
    if ok and valid(object) then return object end
    ok,object=pcall(FindObject,nil,nil,path,false)
    if ok and valid(object) then return object end
end
local function cdo(name)
    return resolve('/Script/EndGame.Default__'..name) or resolve('/Script/EndDataBase.Default__'..name)
end
local function text(value) return value and value:ToString() or '' end
local function emit(event,fields)
    fields=fields or {};fields.event=event;fields.at_utc=os.date('!%Y-%m-%dT%H:%M:%SZ')
    print('[BiomeRandomizerRuntime] '..json.encode(fields)..'\n')
end
function M.new(config)
    local self={fault=nil,policy=nil,store=nil,epoch=nil,apis={},health={},stale={},next_step=0,members_at=0,pawnless=0,table_at=0,retry_at=0,territory_at=0,prepared=false}
    local function fail(reason)
        if not self.fault then self.fault=tostring(reason);emit('automatic_disabled',{reason=self.fault}) end
    end
    local function asset()
        -- Exact path lookups only. Outside the Grasslands this asset may not be
        -- loaded, and a FindAllOf fallback would stall the game thread each time.
        local object=resolve(asset_path)
        if valid(object) and object:GetFullName()==asset_full then return object end
    end
    -- Default objects and the engine live as long as the process, so they are
    -- found once. Anything a level can unload is still looked up afresh.
    local function api(name)
        local object=self.apis[name]
        if not valid(object) then object=cdo(name);self.apis[name]=object end
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
        self.pawn_address=address;self.members_at=0
        return actor
    end
    local function table_status(object)
        local result=json.decode(BiomeRandomizerTableStatus(object:GetAddress()))
        if not result.ok then error('table_guard:'..tostring(result.reason)) end
        return result
    end
    local function expect_references(object,status)
        local token=tostring(object:GetAddress())..':'..tostring(status.asset_content)
        if self.asset_token==token and self.last_references then
            for index=1,4 do assert(status.choices[index]==self.last_references[index],'external_reference_change') end
        else
            -- A fresh native asset starts with the original references. A
            -- nonzero reference before our first write belongs to somebody
            -- else; never adopt it as permission to overwrite that mod.
            for index=1,4 do assert(status.choices[index]==0,'preexisting_reference_change') end
            self.asset_token=token;self.last_references=nil
        end
    end
    local function remember(status)
        self.last_references={};for index=1,4 do self.last_references[index]=status.choices[index] end
    end
    local function initialize()
        if self.policy then return end
        self.store=StateStore.new({json=json,read=BiomeRandomizerReadState,write=BiomeRandomizerWriteState,
            write_async=BiomeRandomizerWriteStateAsync,
            random_seed=BiomeRandomizerRandomSeed,seed=config.seed,algorithm=Lifecycle.algorithm,
            scope='grasslands-four-level15-e515-v1',pools=pools,
            selection=function(seed,camp,cycle,pool) return Lifecycle.selection(seed,camp,cycle,pool,BiomeRandomizerSHA256) end})
        self.policy=Lifecycle.new(self.store.seed,pools,self.store.cycles,BiomeRandomizerSHA256)
        emit('selector_ready',{seed=self.store.seed,algorithm=Lifecycle.algorithm,cycles=self.policy:checkpoint()})
    end
    local function prepare_references(object,status)
        expect_references(object,status)
        -- Preflight every changed camp before writing any of them. Late
        -- initialization must not change a living group's next-stream choice,
        -- nor leave other camps changed after a later camp refuses startup.
        local battle=api('EndBattleAPI');assert(valid(battle),'initial_battle_api_unavailable')
        for index,camp in ipairs(ids) do
            local desired=self.policy.camps[camp].choice
            if status.choices[index]~=desired then
                local live=false;local live_first;local dead_first;local ambiguous_dead=false
                local function inspect(name,spec,choice)
                    local actor=battle:GetCharaFromActorName(FName(name),true)
                    if not valid(actor) then return true end
                    assert(text(battle:GetActorName(actor))==name and text(battle:GetCharaSpecName(actor))==spec,'initial_character_identity_differs')
                    local hp,max=battle:GetCharaHP(actor),battle:GetHPMax(actor)
                    assert(type(hp)=='number' and type(max)=='number' and hp>=0 and max>=0,'initial_character_hp_unreadable')
                    if max==0 then return false end -- population is not ready; defer all writes
                    if hp>0 then
                        live=true
                        if choice~=nil then
                            assert(live_first==nil or live_first==choice,'initial_multiple_first_members')
                            live_first=choice
                        end
                    else
                        if battle:GetCharacterStateType(actor)~=6 then return false end
                        if choice~=nil then
                            if dead_first~=nil and dead_first~=choice then ambiguous_dead=true end
                            dead_first=choice
                        end
                    end
                    return true
                end
                for choice,base in ipairs(first_names) do
                    if not inspect(base..'@'..camp,specs[choice],choice-1) then return false end
                end
                for suffix=1,2 do
                    if not inspect(string.format('mobgrasa_Ogre_Orc_%03d@%s',suffix,camp),orc_spec) then return false end
                end
                local observed=live_first or (not ambiguous_dead and dead_first or nil)
                if live then assert(observed==desired,'initial_living_group_choice_differs:'..camp) end
            end
        end
        for index,camp in ipairs(ids) do
            local desired=self.policy.camps[camp].choice
            if status.choices[index]~=desired then
                local result=json.decode(BiomeRandomizerSetNext(object:GetAddress(),index-1,status.choices[index],desired))
                assert(result.ok and result.choices[index]==desired,'initial_reference_unverified')
                status=result;emit('reference_ready',{camp=camp,cycle=self.policy.camps[camp].cycle,choice=desired})
            end
        end
        remember(status)
        return true
    end
    local function members(battle,party)
        local count=party:GetBattleMemberCount()
        if type(count)~='number' or count<1 or count>8 or count%1~=0 then return nil end
        local names={};local alive=0
        for index=0,count-1 do
            local actor=party:GetBattleMember(index)
            if not valid(actor) then return nil end
            local hp,max=battle:GetCharaHP(actor),battle:GetHPMax(actor)
            if type(hp)~='number' or type(max)~='number' or hp<0 or max<=0 then return nil end
            names[#names+1]=actor:GetFullName();if hp>0 then alive=alive+1 end
        end
        table.sort(names);return table.concat(names,'|'),alive
    end
    local function row(battle,name)
        -- Ordinary field enemies belong to CharaPopManager. The global-only
        -- lookup returned a non-live reference in the native acceptance run.
        local actor=battle:GetCharaFromActorName(FName(name),true)
        if not valid(actor) then return nil end
        if text(battle:GetActorName(actor))~=name then return nil end
        local spec=text(battle:GetCharaSpecName(actor))
        local hp,max,state=battle:GetCharaHP(actor),battle:GetHPMax(actor),battle:GetCharacterStateType(actor)
        if type(hp)~='number' or type(max)~='number' or hp<0 or max<=0 then return nil end
        return {id=actor:GetFullName(),name=name,spec=spec,hp=hp,max_hp=max,state=state}
    end
    local function refresh_members(battle,party)
        local epoch,alive=members(battle,party)
        if not epoch then return false end
        initialize()
        self.alive=alive
        if epoch~=self.epoch then
            self.epoch=epoch;self.health={};self.stale={};self.policy:reset_epoch(epoch)
            emit('epoch_observed',{actor_count=party:GetBattleMemberCount()})
        end
        return true
    end
    function self:step()
        if self.fault or config.enabled~=true then return end
        local now=os.clock()
        if now<self.next_step then return end
        self.next_step=now+far_seconds
        local ok,error_value=pcall(function()
            local actor=pawn()
            local near={};local in_region=false
            if actor then
                self.pawnless=0
                local location=actor:K2_GetActorLocation()
                for index,camp in ipairs(ids) do
                    local dx,dy=location.X-camp_positions[camp][1],location.Y-camp_positions[camp][2]
                    local distance=dx*dx+dy*dy
                    if distance<near_cm*near_cm then near[#near+1]=index end
                    if distance<region_cm*region_cm then in_region=true end
                end
                self.last_near=near
            else
                -- The game reports no player pawn for the whole of a battle, as well
                -- as during loads and scenes. Keep watching a camp the player was at
                -- if a battle is on. Otherwise leave the game alone: whatever was
                -- resolved may be gone, and this may be the game shutting down.
                local last=self.last_near
                if not last or #last==0 then
                    self.asset_object=nil;self.prepared=false;self.pawn_address=nil
                    return
                end
                local battle=api('EndBattleAPI')
                if not valid(battle) or battle:IsInBattle()~=true then
                    self.asset_object=nil;self.prepared=false;self.pawn_address=nil
                    self.pawnless=self.pawnless+1
                    if self.pawnless>=pawnless_limit then self.last_near=nil end
                    return
                end
                self.pawnless=0;near=last
            end
            if #near==0 then
                self.asset_object=nil
                if self.prepared or not in_region or now<self.retry_at then return end
                self.retry_at=now+retry_seconds
            end
            local object=self.asset_object;local fresh=false
            if not object then
                object=asset();if not valid(object) then return end
                fresh=true
            end
            local battle,party=api('EndBattleAPI'),api('EndPartyAPI')
            if not valid(battle) or not valid(party) then return end
            if self.alive==nil or now>=self.members_at then
                if not refresh_members(battle,party) then return end
                self.members_at=now+members_seconds
            end
            if not self.write_warned and BiomeRandomizerStateWriteFailed() then
                self.write_warned=true;emit('state_write_failed',{})
            end
            if fresh or now>=self.table_at then
                local status=table_status(object);if not prepare_references(object,status) then return end
                self.prepared=true;self.table_at=now+table_seconds
            end
            if #near==0 then return end
            self.asset_object=object
            if self.alive==0 then
                for _,camp in ipairs(ids) do self.policy:cancel_group(camp,self.epoch) end
                return
            end
            -- EndFieldAPI's IsDuringBattle stays false through ordinary field fights.
            local in_battle=battle:IsInBattle()
            if type(in_battle)~='boolean' then return end
            self.next_step=now+near_seconds
            for _,index in ipairs(near) do
                local camp=ids[index]
                local current={};local first_choice
                for choice,base in ipairs(first_names) do
                    local value=row(battle,base..'@'..camp)
                    if value then
                        assert(value.spec==specs[choice],'first_character_spec_differs')
                        current[#current+1]=value;if value.hp>0 then first_choice=choice-1 end
                    end
                end
                for suffix=1,2 do
                    local value=row(battle,string.format('mobgrasa_Ogre_Orc_%03d@%s',suffix,camp))
                    if value then assert(value.spec==orc_spec,'orc_spec_differs');current[#current+1]=value end
                end
                local live_ids={}
                for _,value in ipairs(current) do
                    if value.hp>0 then live_ids[#live_ids+1]=value.id end
                end
                local state=self.policy.camps[camp]
                if #current==0 then self.stale[camp]=nil end
                if #live_ids==3 and first_choice~=nil and not (self.stale[camp] and first_choice~=state.choice) then
                    self.stale[camp]=nil
                    if state.phase=='cleared' then
                        assert(self.policy:respawn(camp,self.epoch,first_choice,live_ids,true),'respawn_unverified')
                        emit('spawn_observed',{camp=camp,cycle=state.cycle,choice=first_choice,ids=live_ids})
                    elseif state.phase=='unknown' then
                        if first_choice~=state.choice then
                            -- A late initialization must never leave a living
                            -- group with a different next-stream composition.
                            local restored=json.decode(BiomeRandomizerSetNext(object:GetAddress(),index-1,state.choice,first_choice))
                            assert(restored.ok,'late_initialization_restore_unverified')
                            error('initial_spawn_choice_differs:'..camp)
                        end
                        assert(self.policy:observe_group(camp,self.epoch,live_ids,true),'initial_group_unverified')
                        emit('group_observed',{camp=camp,cycle=state.cycle,choice=first_choice,ids=live_ids})
                    elseif state.phase=='active' then
                        assert(first_choice==state.choice,'active_group_choice_differs')
                        local changed=false
                        for _,id in ipairs(live_ids) do if not state.members[id] then changed=true end end
                        if changed then
                            assert(self.policy:rebind_group(camp,self.epoch,first_choice,live_ids,true),'stream_rebind_unverified')
                            emit('group_rebound',{camp=camp,cycle=state.cycle,choice=first_choice})
                        end
                    end
                end
                if in_battle then
                    -- Enemies report 1/1 HP until a battle takes them in. Real HP arriving,
                    -- damage or a loss means this camp is in the fight; another enemy
                    -- nearby, or a simulator battle, changes none of them.
                    local before=self.health[camp]
                    local joined=false
                    for _,value in ipairs(current) do
                        if value.hp<value.max_hp or (before and before.waiting and value.max_hp>1) then joined=true end
                    end
                    if (joined or (before and #live_ids<before.alive)) and self.policy:engage(camp,self.epoch) then
                        emit('fight_observed',{camp=camp,cycle=state.cycle})
                    end
                    if not before and #live_ids>0 then self.health[camp]={alive=#live_ids,waiting=false} end
                else
                    if state.engaged then
                        -- The party is otherwise sampled slowly. Never decide on an old
                        -- reading: all of them down here means a Game Over, not a fight won.
                        if not refresh_members(battle,party) then return end
                        if self.alive==0 then
                            self.policy:cancel_group(camp,self.epoch)
                            return
                        end
                        local proposal=self.policy:fight_ended(camp,self.epoch)
                        if proposal then
                            local result=json.decode(BiomeRandomizerSetNext(object:GetAddress(),index-1,proposal.before,proposal.after))
                            assert(result.ok and self.policy:commit(proposal,result.choices[index]),'native_cycle_unverified')
                            remember(result)
                            self.store:save(camp,self.policy:checkpoint())
                            self.stale[camp]=#live_ids>0 or nil
                            emit('cycle_committed',{camp=camp,cycle=proposal.cycle,before=proposal.before,after=proposal.after,survivors=#live_ids})
                        end
                    end
                    local waiting=false
                    for _,value in ipairs(current) do if value.max_hp==1 then waiting=true end end
                    self.health[camp]=#live_ids>0 and {alive=#live_ids,waiting=waiting} or nil
                end
            end
        end)
        if not ok then fail(error_value) end
    end
    function self:territory_begin()
        if self.fault or config.enabled~=true or not BiomeRandomizerIsGameThread() then return end
        -- A level brings dozens of territory actors at once; one check covers them.
        local now=os.clock()
        if now<self.territory_at then return end
        local ok,error_value=pcall(function()
            local object=asset();if not valid(object) then return end
            self.territory_at=now+territory_seconds
            initialize();prepare_references(object,table_status(object))
        end)
        if not ok then fail(error_value) end
    end
    return self
end
return M
