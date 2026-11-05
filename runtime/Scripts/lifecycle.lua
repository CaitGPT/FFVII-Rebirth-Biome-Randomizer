-- The seeded choice: which composition a camp uses for a given counter value.
local M={algorithm='sha256-respawn-v1'}
-- Length framing avoids ambiguity and embedded NULs: pinned LuaMadeSimple
-- string getters use C strings. Seed control characters are rejected.
function M.selection(seed,camp,cycle,pool,sha256)
    assert(type(sha256)=='function','SHA256 provider required')
    assert(type(seed)=='string' and #seed>0 and #seed<=128 and not seed:find('[%z\1-\31]'),'invalid seed')
    assert(type(pool)=='table' and #pool>0,'invalid pool')
    local text=string.format('%s:%d:%s:%d:%s:%d',M.algorithm,#seed,seed,#camp,camp,cycle)
    local hash=sha256(text)
    assert(type(hash)=='string' and #hash==64 and hash:match('^[0-9a-f]+$'),'invalid SHA256 result')
    local value=assert(tonumber(hash:sub(1,8),16))
    return pool[(value%#pool)+1]
end
return M
