-- Versioned mod state, separate from game saves. Native I/O provides bounded
-- Unicode-safe reads, a verified prior copy and atomic replacement/readback.
local M={}
local function integer(n) return type(n)=='number' and n%1==0 and n>=0 and n<=10000000 end
local function copy(value)
    if type(value)~='table' then return value end
    local out={};for k,v in pairs(value) do out[k]=copy(v) end;return out
end
function M.new(options)
    local json=assert(options.json)
    local text,read_ok=options.read()
    assert(read_ok==true and type(text)=='string','state_read_failed')
    local document
    if text~='' then
        document=json.decode(text)
        assert(type(document)=='table' and document.version==1 and document.algorithm==options.algorithm and document.scope==options.scope,'state_schema_differs')
        assert(type(document.seed)=='string' and #document.seed>0 and #document.seed<=128 and not document.seed:find('[%z\1-\31]'),'state_seed_invalid')
        assert(type(document.cycles)=='table','state_cycles_invalid')
        for camp,value in pairs(document.cycles) do
            assert(options.pools[camp] and type(value)=='table' and integer(value.cycle),'state_cycle_invalid')
        end
        for camp in pairs(options.pools) do assert(document.cycles[camp],'state_cycle_missing') end
    end
    local fresh=not document or (options.seed~='auto' and options.seed~=document.seed)
    if fresh then
        local seed=options.seed=='auto' and options.random_seed() or options.seed
        assert(type(seed)=='string' and #seed>0 and #seed<=128 and not seed:find('[%z\1-\31]'),'seed_unavailable')
        document={version=1,algorithm=options.algorithm,scope=options.scope,seed=seed,cycles={}}
        for camp in pairs(options.pools) do document.cycles[camp]={cycle=0} end
    end
    local function persist()
        local encoded=json.encode(document)
        assert(#encoded<=16384 and options.write(encoded)==true,'state_write_unverified')
    end
    if fresh then persist() end
    local self={seed=document.seed,cycles=copy(document.cycles)}
    -- Saves one camp's new counter on a background thread. A crash before it lands
    -- only means that camp rolls its previous choice again next time.
    function self:save(camp,cycles)
        for name,row in pairs(document.cycles) do
            local expected=name==camp and row.cycle+1 or row.cycle
            assert(cycles[name] and cycles[name].cycle==expected,'save_cycle_differs')
        end
        document.cycles=copy(cycles);self.cycles=copy(cycles)
        local encoded=json.encode(document)
        assert(#encoded<=16384 and options.write_async(encoded)==true,'state_write_not_queued')
    end
    return self
end
return M
