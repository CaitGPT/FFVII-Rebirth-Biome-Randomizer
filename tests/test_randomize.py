"""Synthetic fixtures only; these tests do not establish native gameplay success."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from randomize import CHANGED_PROPERTY, load_export, make_plan, validate_pool, verify_result


def fixture():
    catalog = json.loads((ROOT / "data/pools.json").read_text())
    pool = catalog["pools"][0]
    # Deliberately synthetic property values; no original asset files are distributed.
    base = {
        "MobLevelList_Array": "15|15", "MinPopList_Array": "1|2", "MaxPopList_Array": "1|2",
        "FieldAINameList_Array": "1|1", "AerialEnemyFlag_Array": "", "TerritoryType": "0",
        "RespawnTimer": "180", "BattleSceneBluePrint": "", "WaveMobTemplateList_Array": "",
        "ExternalEnemiesList_Array": "", "SaveStateLocationWorkList_Array": "",
        "SaveStateLocationWorkExternalEnemy_Array": "", "BattleConditionTriggerGroupId_Array": "",
        "TerritoryDefeatedStateLocationWork": "", "RespawnReadyStateTrigger": "",
        "SummonConditionID": "", "SaveTerritoryState": "0", "ForceFinishBattleOnKill_Array": "",
        "SyntheticSentinel": "preserve me"
    }
    territories = {}
    for i, name in enumerate(pool["targets"]):
        row = dict(base)
        small = "mobgrasa_Mandragora_00" if name == "Grassland_mob_02" else "mobgrasa_KalmFang_00"
        row[CHANGED_PROPERTY] = small + "|mobgrasa_Ogre_Orc_00"
        row["UniqueIndex"] = str(i)
        territories[name] = row
    for name in ("Grassland_mob_01", "Grassland_mob_01_Media", "SyntheticBoss", "SyntheticHunt", "SyntheticQuest", "SyntheticSwamp"):
        territories[name] = {"Script": "do not modify", CHANGED_PROPERTY: "synthetic_protected_actor"}
    mobs = {mob: {"BattleCharaSpecID": spec} for mob, spec in pool["small_mobs"].items()}
    mobs[pool["fixed_mob"]["id"]] = {"BattleCharaSpecID": pool["fixed_mob"]["spec"]}
    return catalog, territories, mobs


class RandomizerTests(unittest.TestCase):
    def test_seed_is_reproducible_and_independent_of_dictionary_order(self):
        catalog, rows, mobs = fixture()
        first = make_plan(catalog, rows, mobs, "repeatable seed")
        catalog2 = copy.deepcopy(catalog)
        catalog2["pools"][0]["targets"].reverse()
        catalog2["pools"][0]["donors"].reverse()
        self.assertEqual(first, make_plan(catalog2, dict(reversed(list(rows.items()))), mobs, "repeatable seed"))

    def test_seeded_variation_stays_in_pool_and_changes_only_allowed_property(self):
        catalog, rows, mobs = fixture()
        compositions = {name: set() for name in catalog["pools"][0]["targets"]}
        for seed in map(str, range(100)):
            spec, audit = make_plan(catalog, rows, mobs, seed)
            modified = copy.deepcopy(rows)
            for edit in spec["tables"][0]["rows"]:
                self.assertIn(edit["name"], compositions)
                self.assertEqual(list(edit["set"]), [CHANGED_PROPERTY])
                modified[edit["name"]][CHANGED_PROPERTY] = "|".join(edit["set"][CHANGED_PROPERTY])
            verify_result(rows, modified, spec)
            for choice in audit["choices"]:
                self.assertEqual(choice["after"][1], "mobgrasa_Ogre_Orc_00")
                self.assertIn(choice["after"][0], catalog["pools"][0]["small_mobs"])
                compositions[choice["target"]].add(tuple(choice["after"]))
            for protected in set(rows) - set(compositions):
                self.assertEqual(modified[protected], rows[protected])
        self.assertTrue(all(len(found) == 2 for found in compositions.values()))

    def test_unknown_and_protected_only_targets_are_refused(self):
        catalog, rows, mobs = fixture()
        for targets in (["Grassland_mob_01"], ["SyntheticBoss"], ["unknown"], [], ["Grassland_mob_02"] * 2):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                make_plan(catalog, rows, mobs, "44", targets)

    def test_target_subset_preserves_other_targets(self):
        catalog, rows, mobs = fixture()
        spec, audit = make_plan(catalog, rows, mobs, "44", ["Grassland_mob_02"])
        self.assertEqual([c["target"] for c in audit["choices"]], ["Grassland_mob_02"])
        self.assertTrue(all(edit["name"] == "Grassland_mob_02" for edit in spec["tables"][0]["rows"]))

    def test_changed_progression_or_authored_flags_refuse_the_build(self):
        for prop, value in [("MobLevelList_Array", "99|99"), ("MinPopList_Array", "1|8"),
                            ("AerialEnemyFlag_Array", "1|0"), ("BattleSceneBluePrint", "synthetic_story"),
                            ("WaveMobTemplateList_Array", "synthetic_wave"),
                            ("SaveStateLocationWorkList_Array", "synthetic_quest")]:
            catalog, rows, mobs = fixture()
            rows["Grassland_mob_02"][prop] = value
            with self.subTest(prop=prop), self.assertRaises(ValueError):
                make_plan(catalog, rows, mobs, "44")

    def test_wrong_enemy_mapping_or_missing_donor_is_refused(self):
        catalog, rows, mobs = fixture()
        mobs["mobgrasa_KalmFang_00"]["BattleCharaSpecID"] = "synthetic_boss"
        with self.assertRaises(ValueError):
            make_plan(catalog, rows, mobs, "44")
        catalog, rows, mobs = fixture()
        del rows["Grassland_mob_05"]
        with self.assertRaises(ValueError):
            make_plan(catalog, rows, mobs, "44")

    def test_independent_verifier_detects_unrequested_changes(self):
        catalog, rows, mobs = fixture()
        spec, _ = make_plan(catalog, rows, mobs, "44")
        for mutate in (lambda result: result.pop("SyntheticBoss"),
                       lambda result: result["SyntheticBoss"].update(Script="changed"),
                       lambda result: result["Grassland_mob_02"].update(MobLevelList_Array="99|99")):
            result = copy.deepcopy(rows)
            for edit in spec["tables"][0]["rows"]:
                result[edit["name"]][CHANGED_PROPERTY] = "|".join(edit["set"][CHANGED_PROPERTY])
            mutate(result)
            with self.assertRaises(ValueError):
                verify_result(rows, result, spec)

    def test_long_export_parser_preserves_empty_and_array_values(self):
        temp_root = ROOT / "build" / "test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            path = Path(directory) / "export.csv"
            with path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerows([["Index", "Name", "Property", "Value"], [0, "synthetic", "empty", ""],
                                 [0, "synthetic", "array", "a|b"]])
            self.assertEqual(load_export(path), {"synthetic": {"empty": "", "array": "a|b"}})
            with path.open("a", newline="", encoding="utf-8") as output:
                csv.writer(output).writerow([0, "synthetic", "empty", "duplicate"])
            with self.assertRaises(ValueError):
                load_export(path)


if __name__ == "__main__":
    unittest.main()
