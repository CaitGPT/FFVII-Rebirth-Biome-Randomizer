local config=require('config')
local automatic=require('automatic').new(config)
local queued=false
local stopped=false
ExecuteInGameThread(function() end)
local begin_ok,begin_error=pcall(RegisterHook,'/Script/Engine.Actor:ReceiveBeginPlay',function(context) automatic:begin_play(context) end)
local end_ok,end_error=pcall(RegisterHook,'/Script/Engine.Actor:ReceiveEndPlay',function(context,reason) automatic:end_play(context,reason) end)
print('[BiomeRandomizerRuntime] hooks begin='..tostring(begin_ok)..' end='..tostring(end_ok)..'\n')
LoopAsync(100,function()
    if stopped or queued then return end
    queued=true
    local ok,error_value=pcall(ExecuteInGameThread,function()
        local result,why=pcall(function() automatic:step() end)
        queued=false
        if not result then stopped=true;print('[BiomeRandomizerRuntime] automatic stopped '..tostring(why)..'\n') end
    end)
    if not ok then queued=false;stopped=true;print('[BiomeRandomizerRuntime] executor stopped '..tostring(error_value)..'\n') end
end)
