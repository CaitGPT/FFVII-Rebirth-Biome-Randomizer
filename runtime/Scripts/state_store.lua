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
    if document.pending then
        local p=document.pending;local row=type(p)=='table' and document.cycles[p.camp]
        assert(row and integer(p.cycle) and p.cycle==row.cycle+1,'pending_cycle_invalid')
        assert(p.before==options.selection(document.seed,p.camp,row.cycle,options.pools[p.camp]),'pending_before_invalid')
        assert(p.after==options.selection(document.seed,p.camp,p.cycle,options.pools[p.camp]),'pending_after_invalid')
        -- A clear was proved before preparing this intent. A fresh process
        -- has original game data, so finish that intent exactly once.
        row.cycle=p.cycle;document.pending=nil;persist()
    elseif fresh then persist() end
    local self={seed=document.seed,cycles=copy(document.cycles)}
    function self:prepare(proposal)
        assert(not document.pending,'pending_transaction_exists')
        local row=document.cycles[proposal.camp]
        assert(row and proposal.cycle==row.cycle+1,'proposal_cycle_differs')
        assert(proposal.before==options.selection(document.seed,proposal.camp,row.cycle,options.pools[proposal.camp]),'proposal_before_differs')
        assert(proposal.after==options.selection(document.seed,proposal.camp,proposal.cycle,options.pools[proposal.camp]),'proposal_after_differs')
        document.pending={camp=proposal.camp,cycle=proposal.cycle,before=proposal.before,after=proposal.after}
        persist()
    end
    function self:commit(cycles)
        assert(document.pending,'missing_pending_transaction')
        for camp,row in pairs(document.cycles) do
            local expected=camp==document.pending.camp and document.pending.cycle or row.cycle
            assert(cycles[camp] and cycles[camp].cycle==expected,'commit_cycle_differs')
        end
        document.cycles=copy(cycles);document.pending=nil;persist();self.cycles=copy(cycles)
    end
    return self
end
return M
