-- Explicit bounded table-reference experiment. This is not a randomizer yet.
local root='D:/FF7RebirthModding/Mods/BiomeRandomizer/native-20261104/'
local path='EndDataObjectEnemyTerritory /Game/DataObject/Field/1200-GRASA/EnemyTerritory.EnemyTerritory'
local queued=false
local function table_request()
    local request=io.open(root..'runtime-table.request','r')
    if not request then return end
    local line=request:read('*l');request:close()
    local label,action,target,expected,desired=line:match('^([a-z0-9%-]+) (%a+) (%d) (%d) (%d)$')
    if not label or (action~='status' and action~='set') then return end
    local output_path=root..'runtime-table-'..label..'.json'
    local existing=io.open(output_path,'r')
    if existing then
        existing:close();os.remove(root..'runtime-table.request')
        print('[BiomeRandomizerRuntime] duplicate evidence label refused '..label..'\n')
        return
    end
    if type(BiomeRandomizerTableStatus)~='function' then return end
    for _,asset in ipairs(FindAllOf('EndDataObjectEnemyTerritory') or {}) do
        if asset:IsValid() and asset:GetFullName()==path then
            local address=asset:GetAddress()
            local before=BiomeRandomizerTableStatus(address)
            -- A loading-thread ProcessEvent may drain the UE4SS executor.
            -- No write was attempted; retain the request for a window-thread
            -- callback instead of weakening the native thread guard.
            if before:find('"reason":"wrong_thread"',1,true) or before:find('"reason":"game_window_thread_unavailable"',1,true) then return end
            local result=before
            if action=='set' then result=BiomeRandomizerSetNext(address,tonumber(target),tonumber(expected),tonumber(desired)) end
            local file=assert(io.open(output_path,'w'))
            file:write('{"action":"'..action..'","before":'..before..',"result":'..result..'}');file:close()
            os.remove(root..'runtime-table.request')
            print('[BiomeRandomizerRuntime] table experiment '..label..' result='..result..'\n')
            return
        end
    end
end
local function sample()
    local request=io.open(root..'runtime-inspect.request','r')
    if not request then return end
    local label=request:read('*l');request:close()
    if not label or not label:match('^[a-z0-9%-]+$') then return end
    if type(BiomeRandomizerInspectAsset)~='function' then return end
    for _,asset in ipairs(FindAllOf('EndDataObjectEnemyTerritory') or {}) do
        if asset:IsValid() and asset:GetFullName()==path then
            local output=BiomeRandomizerInspectAsset(asset:GetAddress())
            local file=assert(io.open(root..'runtime-inspect-'..label..'.json','w'))
            file:write(output);file:close()
            os.remove(root..'runtime-inspect.request')
            print('[BiomeRandomizerRuntime] read-only asset inspection '..label..'\n')
            return
        end
    end
end
ExecuteInGameThread(function() end) -- register the executor at mod startup
LoopAsync(1000,function()
    if queued then return end
    queued=true
    ExecuteInGameThread(function()
        local ok,err=pcall(function() sample();table_request() end)
        if not ok then print('[BiomeRandomizerRuntime] inspection failed '..tostring(err)..'\n') end
        queued=false
    end)
end)
