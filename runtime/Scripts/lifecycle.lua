-- Engine-independent lifecycle policy. Native adapters must supply verified
-- identities/deaths/clear outcomes; an actor disappearing is never a death.
local M={algorithm='fnv1a32-xorshift-v1'}
local function integer(n) return type(n)=='number' and n%1==0 end
local function selection(seed,camp,cycle,pool)
    local value=2166136261
    local text=seed..'\0'..camp..'\0'..tostring(cycle)
    for i=1,#text do value=((value~text:byte(i))*16777619)&0xffffffff end
    value=(value~((value<<13)&0xffffffff))&0xffffffff
    value=(value~(value>>17))&0xffffffff
    value=(value~((value<<5)&0xffffffff))&0xffffffff
    return pool[(value%#pool)+1]
end
function M.new(seed,pools,saved)
    assert(type(seed)=='string' and #seed>0 and #seed<=128,'invalid seed')
    local self={seed=seed,pools=pools,camps={},epoch=nil,fault=nil}
    for camp,pool in pairs(pools) do
        assert(type(camp)=='string' and type(pool)=='table' and #pool>0,'invalid pool')
        local seen={}
        for _,v in ipairs(pool) do assert(integer(v) and v>=0 and not seen[v],'invalid choice');seen[v]=true end
        local previous=saved and saved[camp]
        local cycle=previous and previous.cycle or 0
        assert(integer(cycle) and cycle>=0 and cycle<=10000000,'invalid cycle')
        self.camps[camp]={cycle=cycle,choice=selection(seed,camp,cycle,pool),members={},deaths={},phase='unknown'}
    end
    function self:reset_epoch(epoch)
        assert(type(epoch)=='string' and #epoch>0,'invalid epoch')
        if self.epoch==epoch then return end
        self.epoch=epoch
        for _,state in pairs(self.camps) do
            state.members={};state.deaths={};state.phase='unknown'
            -- A reload invalidates an uncommitted proposal, never an accepted
            -- cycle or a fault caused by an uncertain native write.
            state.proposal=nil
        end
    end
    function self:observe_group(camp,epoch,ids,complete)
        local state=self.camps[camp]
        if self.fault or not state or epoch~=self.epoch or not complete or #ids==0 then return false end
        if state.phase=='cleared' or state.phase=='pending' then return false end
        local members={}
        for _,id in ipairs(ids) do
            if type(id)~='string' or id=='' or members[id] then return false end
            members[id]=true
        end
        if state.phase=='active' then
            for id in pairs(state.members) do if not members[id] then return false end end
            for id in pairs(members) do if not state.members[id] then return false end end
            return true
        end
        state.members=members;state.deaths={};state.phase='active';return true
    end
    function self:death(camp,epoch,id,hp)
        local state=self.camps[camp]
        if self.fault or not state or epoch~=self.epoch or state.phase~='active' or hp~=0 or not state.members[id] then return false end
        state.deaths[id]=true;return true
    end
    function self:confirmed_clear(camp,epoch,outcome)
        local state=self.camps[camp]
        if self.fault or not state or epoch~=self.epoch or state.phase~='active' or outcome~='victory' then return nil end
        local count=0
        for id in pairs(state.members) do
            count=count+1;if not state.deaths[id] then return nil end
        end
        if count==0 or state.cycle>=10000000 then return nil end
        state.phase='pending'
        state.proposal={camp=camp,epoch=epoch,cycle=state.cycle+1,
            before=state.choice,after=selection(self.seed,camp,state.cycle+1,self.pools[camp])}
        -- Return a copy: outside code cannot change the pending transaction.
        local copy={};for k,v in pairs(state.proposal) do copy[k]=v end;return copy
    end
    function self:commit(proposal,verified_choice)
        if self.fault or type(proposal)~='table' then return false end
        local state=self.camps[proposal.camp];local pending=state and state.proposal
        if not pending or self.epoch~=proposal.epoch then return false end
        for k,v in pairs(pending) do if proposal[k]~=v then return false end end
        if verified_choice~=pending.after then
            self.fault='native_selection_unverified';return false
        end
        state.cycle=pending.cycle;state.choice=pending.after;state.proposal=nil;state.phase='cleared'
        return true
    end
    function self:respawn(camp,epoch,choice,ids,complete)
        local state=self.camps[camp]
        if self.fault or not state or epoch~=self.epoch or state.phase~='cleared' or not complete or #ids==0 then return false end
        if choice~=state.choice then self.fault='spawn_composition_differs';return false end
        state.phase='unknown';return self:observe_group(camp,epoch,ids,true)
    end
    function self:checkpoint()
        local out={};for camp,state in pairs(self.camps) do out[camp]={cycle=state.cycle} end;return out
    end
    return self
end
M.selection=selection
return M
