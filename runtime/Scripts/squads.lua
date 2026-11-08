-- Shinra and bandit squads: which human and machine enemies a region's camps can roll instead of monsters.
-- They come from the always-loaded Resident table's combat-simulator templates, each of which points at the
-- ordinary field enemy. A squad never mixes with monsters, and a region has one kind of squad.
local M={}
-- Must match reviewed::resident_templates in Native/src/resident_templates.hpp, in order (r0, r1, ...).
M.resident={
    'mobcolvr_EN0000_00_SecuritySoldier_Standard_00',        -- r0 Security Officer
    'mobcolvr_EN0001_00_GrenadeSoldier_Standard_00',         -- r1 Grenadier
    'mobcolvr_EN0001_01_GrenadeSoldier_Senior_00',           -- r2 Elite Grenadier
    'mobcolvr_EN0002_00_ShieldSoldier_Standard_00',          -- r3 Riot Trooper
    'mobcolvr_EN0002_03_ShieldSoldier_Flame_00',             -- r4 Flametrooper
    'mobcolvr_EN0007_03_Soldier3rd_2ndEnd2_00',              -- r5 2-C SOLDIER Operator
    'mobcolvr_EN0000_06_SecuritySoldier_JunonEnd2_00',       -- r6 Junon Security Officer
    'mobcolvr_EN0000_08_SecuritySoldier_SeniorJunonEnd2_00', -- r7 Junon Elite Security Officer
    'mobcolvr_EN0001_02_GrenadeSoldier_JunonEnd2_00',        -- r8 Junon Grenadier
    'mobcolvr_EN0002_04_ShieldSoldier_JunonEnd2_00',         -- r9 Junon Riot Trooper
    'mobcolvr_EN1001_00_Sweeper_Standard_00',                -- r10 J-Unit Sweeper
    'mobcolvr_EN1008_00_StunRay_Standard_00',                -- r11 Slug-Ray
    'mobcolvr_EN1008_06_StunRay_GroundtypeEnd2_00',          -- r12 Type G Slug-Ray
    'mobcolvr_EN3000_02_MonoDrive_ScrutinEyeEnd2_00',        -- r13 Scrutineye
    'mobcolvr_EN0008_00_Vice_Standard_Scimitar_00',          -- r14 Bandit
    'mobcolvr_EN0008_00_Vice_Standard_IronPipe_00',          -- r15 Bandit
    'mobcolvr_EN0008_01_Vice_VariationA_Axe_00',             -- r16 Bandit
    'mobcolvr_EN0008_02_Vice_VariationB_00',                 -- r17 Bandit
    'mobcolvr_EN0008_02_Vice_VariationB_SpikedBat_00',       -- r18 Bandit
    'mobcolvr_EN0009_20_CorneoLackey_GreedAEnd2_00',         -- r19 Thug
    'mobcolvr_EN0009_21_CorneoLackey_GreedBEnd2_00',         -- r20 Thug
    'mobcolvr_EN0009_22_CorneoLackey_GreedCEnd2_00',         -- r21 Thug
}
local security,grenadier,elite_grenadier,riot,flame,operator=0,1,2,3,4,5
local junon_security,junon_elite_security,junon_grenadier,junon_riot=6,7,8,9
local sweeper,slugray,slugray_g,scrutineye=10,11,12,13
local bandits={14,15,16,17,18}
local thugs={19,20,21}
M.sweeper=sweeper
local function join(...)
    local out={};for _,list in ipairs({...}) do for _,v in ipairs(list) do out[#out+1]=v end end;return out
end
-- always: from the start. chapter_select: once Chapter 14 is cleared (the game's chapter-select release flag).
-- from_chapter: from that chapter on, or with chapter select.
local pools={
    ['1100-MIDGA']={always={security,grenadier,slugray},chapter_select={riot,flame,slugray_g}},
    ['1200-GRASA']={always=bandits},
    ['1300-JUNOA']={always={junon_security,junon_grenadier,junon_riot,sweeper,slugray},chapter_select={slugray_g},
        from_chapter={[5]={junon_elite_security}}},
    ['2200-CORLA:desert']={always=join(bandits,thugs)},
    ['2200-CORLA:southern']={always={security,grenadier,flame,slugray,scrutineye},chapter_select={elite_grenadier,slugray_g}},
    ['2600-NIBLA']={always={security,grenadier,riot,flame,scrutineye,slugray,sweeper},chapter_select={operator,slugray_g}},
}
M.pools=pools
-- Corel's camps are two biomes: the southern coast and the desert.
local function key_of(region,camp)
    if region=='2200-CORLA' then
        if camp:find('^Corla_southem_') then return region..':southern' end
        if camp:find('^Corla_desert_') then return region..':desert' end
        return nil
    end
    return region
end
-- A squad unit: a region, or one of Corel's two halves. Each has its own pool; nil for camps without squads.
function M.unit(region,camp)
    local key=key_of(region,camp)
    return key and pools[key] and key or nil
end
-- The resident template numbers a unit's squads may use, given what the loaded save allows, or nil.
-- gates: {chapter_select=bool, chapter=number}
function M.unit_pool(unit,gates)
    local entry=unit and pools[unit]
    if not entry then return nil end
    local out={};for _,v in ipairs(entry.always or {}) do out[#out+1]=v end
    if gates.chapter_select then for _,v in ipairs(entry.chapter_select or {}) do out[#out+1]=v end end
    for chapter,list in pairs(entry.from_chapter or {}) do
        if gates.chapter_select or (gates.chapter or 0)>=chapter then for _,v in ipairs(list) do out[#out+1]=v end end
    end
    table.sort(out)
    return #out>0 and out or nil
end
function M.pool(region,camp,gates) return M.unit_pool(M.unit(region,camp),gates) end
-- How many squad enemy types each region's table can use at once. Measured live (2026-11-08): past this, the
-- first types a region's camps ask for spawn and any further type spawns nothing for the whole visit, whatever
-- its size. The cause in the game isn't known. Corel's two halves share one table, so one type each.
M.type_budget={['1100-MIDGA']=2,['1200-GRASA']=2,['1300-JUNOA']=2,['2200-CORLA']=2,['2600-NIBLA']=1}
return M
