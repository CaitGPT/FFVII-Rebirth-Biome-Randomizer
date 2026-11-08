#pragma once
#include <array>
// Squad enemies: templates in the always-loaded Resident EnemyTerritoryMob table (the combat simulator's copies),
// each pointing at the ordinary field enemy's own spec. A composition names one as "r<index>". The order must
// match `resident` in Scripts/squads.lua; the offline tests compare the two lists.
namespace reviewed {
constexpr std::array<const wchar_t*,22> resident_templates{
    L"mobcolvr_EN0000_00_SecuritySoldier_Standard_00",       // 0 Security Officer
    L"mobcolvr_EN0001_00_GrenadeSoldier_Standard_00",        // 1 Grenadier
    L"mobcolvr_EN0001_01_GrenadeSoldier_Senior_00",          // 2 Elite Grenadier
    L"mobcolvr_EN0002_00_ShieldSoldier_Standard_00",         // 3 Riot Trooper
    L"mobcolvr_EN0002_03_ShieldSoldier_Flame_00",            // 4 Flametrooper
    L"mobcolvr_EN0007_03_Soldier3rd_2ndEnd2_00",             // 5 2-C SOLDIER Operator
    L"mobcolvr_EN0000_06_SecuritySoldier_JunonEnd2_00",      // 6 Junon Security Officer
    L"mobcolvr_EN0000_08_SecuritySoldier_SeniorJunonEnd2_00",// 7 Junon Elite Security Officer
    L"mobcolvr_EN0001_02_GrenadeSoldier_JunonEnd2_00",       // 8 Junon Grenadier
    L"mobcolvr_EN0002_04_ShieldSoldier_JunonEnd2_00",        // 9 Junon Riot Trooper
    L"mobcolvr_EN1001_00_Sweeper_Standard_00",               // 10 J-Unit Sweeper
    L"mobcolvr_EN1008_00_StunRay_Standard_00",               // 11 Slug-Ray
    L"mobcolvr_EN1008_06_StunRay_GroundtypeEnd2_00",         // 12 Type G Slug-Ray
    L"mobcolvr_EN3000_02_MonoDrive_ScrutinEyeEnd2_00",       // 13 Scrutineye
    L"mobcolvr_EN0008_00_Vice_Standard_Scimitar_00",         // 14 Bandit
    L"mobcolvr_EN0008_00_Vice_Standard_IronPipe_00",         // 15 Bandit
    L"mobcolvr_EN0008_01_Vice_VariationA_Axe_00",            // 16 Bandit
    L"mobcolvr_EN0008_02_Vice_VariationB_00",                // 17 Bandit
    L"mobcolvr_EN0008_02_Vice_VariationB_SpikedBat_00",      // 18 Bandit
    L"mobcolvr_EN0009_20_CorneoLackey_GreedAEnd2_00",        // 19 Thug
    L"mobcolvr_EN0009_21_CorneoLackey_GreedBEnd2_00",        // 20 Thug
    L"mobcolvr_EN0009_22_CorneoLackey_GreedCEnd2_00",        // 21 Thug
};
}
