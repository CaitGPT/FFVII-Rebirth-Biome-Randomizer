local config=require('config')
local automatic=require('automatic').new(config)
-- The paired DLL owns synchronous dispatch on the verified game thread.
-- No LoopAsync, ExecuteInGameThread or Lua RegisterHook coroutines.
function BiomeRandomizerTick() automatic:step() end
function BiomeRandomizerTerritoryBegin() automatic:territory_begin() end
function BiomeRandomizerActorEnd(id,reason) automatic:end_play_name(id,reason) end
