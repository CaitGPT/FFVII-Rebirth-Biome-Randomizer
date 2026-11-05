-- Private issue44 experiment, only camp05. Supply its missing S points from
-- the same arena's existing M points. No input, healing, enemy spawning,
-- character-definition edits, table edits or save writes.
local path='/Game/Level/Game/Field/1200-GRASA/Layout/1200-GRASA_World_Navigation_Mod_ServerBuild.1200-GRASA_World_Navigation_Mod_ServerBuild:PersistentLevel.Grassland_mob_05'
local expected='EndFieldEnemyTerritoryServerBuildActor '..path
local applied_address=nil
local failed=false
local queued=false
local ticks=0
local scan_needed=true
local function log(s) print('[BiomeRandomizerArenaDiagnostic] '..s..'\n') end
local function vector(v) return {X=v.X,Y=v.Y,Z=v.Z} end
local function transform(v)
    return {Rotation={X=v.Rotation.X,Y=v.Rotation.Y,Z=v.Rotation.Z,W=v.Rotation.W},
            Translation=vector(v.Translation),Scale3D=vector(v.Scale3D)}
end
local function check(t)
    for _,v in pairs(t) do
        for _,n in pairs(v) do
            assert(type(n)=='number' and n==n and math.abs(n)<10000,'invalid transform number')
        end
    end
    assert(t.Scale3D.X>0 and t.Scale3D.Y>0 and t.Scale3D.Z>0,'invalid scale')
end
local function equal(a,b)
    for name,v in pairs(a) do
        for key,n in pairs(v) do if math.abs(n-b[name][key])>0.0001 then return false end end
    end
    return true
end
local function attempt(phase, candidate)
    if failed then return end
    -- Both name lookup overloads failed to find this streamed level object.
    -- Use the same class enumeration that actually returned it in the
    -- read-only inventory. Never retain a UObject across callbacks/unloads.
    local actor=candidate
    if not actor then
        for _,value in ipairs(FindAllOf('EndFieldEnemyTerritoryServerBuildActor') or {}) do
            if value:IsValid() and value:GetFullName()==expected then actor=value;break end
        end
    end
    if not actor or not actor:IsValid() or actor:GetFullName()~=expected then return end
    local address=actor:GetAddress()
    local source=actor.TerritoryGroundSpawnPoints_M
    local destination=actor.TerritoryGroundSpawnPoints_S
    if address==applied_address and destination:GetArrayNum()==12 then scan_needed=false;return end
    local count=source:GetArrayNum()
    if count==0 then return end -- constructed but not deserialized yet
    assert(count==12,'unreviewed source point count')
    assert(destination:GetArrayNum()==0,'destination already populated; no overwrite')
    local copied={}
    for i=1,count do copied[i]=transform(source[i]);check(copied[i]) end
    -- Mark failure before attempting a write so an uncertain setter is never
    -- replayed. Only an exact full readback clears it.
    failed=true
    actor.TerritoryGroundSpawnPoints_S=copied
    local result=actor.TerritoryGroundSpawnPoints_S
    assert(result:GetArrayNum()==count,'destination count differs')
    for i=1,count do assert(equal(copied[i],transform(result[i])),'transform readback differs') end
    applied_address=address
    scan_needed=false
    failed=false
    log('verified phase='..phase..' actor='..expected..' S_before=0 S_after='..count..' M='..source:GetArrayNum())
end
local function guarded(phase, candidate)
    local ok,err=pcall(attempt,phase,candidate)
    if not ok then failed=true;log('FAILED phase='..phase..' error='..tostring(err)) end
end
-- Register during mod startup, before any manual play or map load.
ExecuteInGameThread(function() guarded('startup') end)
local hook_ok,pre_id,post_id=pcall(RegisterHook,'/Script/Engine.Actor:ReceiveBeginPlay',function(context)
    local actor=context:get()
    if actor:GetFullName()==expected then guarded('receive_begin_play',actor) end
end)
log('begin_play_hook='..tostring(hook_ok)..' pre='..tostring(pre_id)..' post='..tostring(post_id))
NotifyOnNewObject('/Script/EndGame.EndFieldEnemyTerritoryServerBuildActor',function()
    -- Only schedule a scan; construction may run before property loading.
    scan_needed=true
end)
RegisterLoadMapPostHook(function() scan_needed=true;guarded('load_map_post') end)
LoopAsync(100,function()
    if failed or queued then return end
    queued=true
    ExecuteInGameThread(function()
        ticks=ticks+1
        if scan_needed or ticks%20==0 then guarded('game_thread_poll') end
        queued=false
    end)
end)
log('initialized scoped camp05-only experiment')
