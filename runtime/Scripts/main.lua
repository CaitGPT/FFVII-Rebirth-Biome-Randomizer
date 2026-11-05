local config=require('config')
-- The DLL registers these before this file runs. It refuses any UE4SS build
-- other than the tested one, and an incompatible build may not load it at all.
if type(BiomeRandomizerTableStatus)~='function' then
    print('[BiomeRandomizerRuntime] inactive: this mod needs RE-UE4SS FF7R 1.0.2 (Nexus file 1351). No enemies were changed. See the guide.\n')
    return
end
local automatic=require('automatic').new(config)
-- The paired DLL owns synchronous dispatch on the verified game thread.
-- No LoopAsync, ExecuteInGameThread or Lua RegisterHook coroutines.
function BiomeRandomizerTick() automatic:step() end
