"""Seeded, allowlisted table edits. This module sends no input to the game."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ALGORITHM = "sha256-encounter-v2"
CHANGED_PROPERTY = "MobTemplateList_Array"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_export(path: Path) -> dict[str, dict[str, str]]:
    """Read DataBuilder's lossless long CSV format, never the expanded index CSV."""
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["Index", "Name", "Property", "Value"]:
            raise ValueError("Use a DataBuilder export with Index,Name,Property,Value columns")
        for record in reader:
            if None in record or any(v is None for v in record.values()):
                raise ValueError("Malformed exported row")
            name, prop, value = record["Name"], record["Property"], record["Value"]
            if not name or not prop or prop in rows.setdefault(name, {}):
                raise ValueError(f"Missing or duplicate property: {name}.{prop}")
            rows[name][prop] = value
    if not rows:
        raise ValueError("Empty table export")
    return rows


def split(value: str) -> list[str]:
    return value.split("|") if value else []


def validate_pool(pool: dict, territories: dict, mobs: dict, battles: dict, characters: dict) -> None:
    targets, donors = pool["targets"], pool["donors"]
    if (not targets or len(targets) != len(set(targets)) or len(donors) < 2
            or len(donors) != len(set(donors))):
        raise ValueError("Pool requires unique targets and at least two unique donors")
    if (pool["region"] != "1200-GRASA" or pool["levels"] != [15, 15] or pool["counts"] != [1, 2]
            or pool["physique_size"] != 1 or pool["move_type"] != 0):
        raise ValueError("This prototype only supports the reviewed level-15 Grasslands pool")
    for mob, expected in pool["enemies"].items():
        template = mobs.get(mob, {})
        if template.get("BattleCharaSpecID") != expected["battle_spec"] or template.get("ActorNameTemplate") != mob:
            raise ValueError(f"Unverified mob-to-character mapping: {mob}")
        battle = battles.get(expected["battle_spec"], {})
        if (battle.get("CharaSpecID") != expected["chara_spec"]
                or battle.get("HP") != str(expected["hp_coefficient"]) or battle.get("HPDirect") != "0"):
            raise ValueError(f"Unverified character or HP mapping: {mob}")
        character = characters.get(expected["chara_spec"], {})
        if (character.get("PhysiqueSize") != str(pool["physique_size"])
                or character.get("MoveType") != str(pool["move_type"])):
            raise ValueError(f"Incompatible physique or movement: {mob}")
    for name in set(targets) | set(donors):
        row = territories.get(name)
        if row is None:
            raise ValueError(f"Missing territory {name}")
        templates = split(row[CHANGED_PROPERTY])
        expected = donors[name]["templates"] if name in donors else pool["original_templates"]
        if (templates != expected or len(templates) != 2 or any(m not in pool["enemies"] for m in templates)
                or templates[1] != pool["fixed_mob"]
                or (name in targets and templates != pool["original_templates"])):
            raise ValueError(f"Composition outside the explicit pool: {name}")
        counts = donors[name]["counts"] if name in donors else pool["counts"]
        if counts not in ([1, 2], [2, 2]) or (name in targets and counts != pool["counts"]):
            raise ValueError(f"Unreviewed donor count budget: {name}")
        count_text = "|".join(map(str, counts))
        for prop, expected in {
            "MobLevelList_Array": "15|15", "MinPopList_Array": count_text, "MaxPopList_Array": count_text,
            "FieldAINameList_Array": "1|1", "AerialEnemyFlag_Array": "", "TerritoryType": "0",
            "RespawnTimer": "180", "BattleSceneBluePrint": "", "WaveMobTemplateList_Array": "",
            "ExternalEnemiesList_Array": "", "SaveStateLocationWorkList_Array": "",
            "SaveStateLocationWorkExternalEnemy_Array": "", "BattleConditionTriggerGroupId_Array": "",
            "TerritoryDefeatedStateLocationWork": "", "RespawnReadyStateTrigger": "",
            "SummonConditionID": "", "SaveTerritoryState": "0", "ForceFinishBattleOnKill_Array": ""
        }.items():
            if row.get(prop) != expected:
                raise ValueError(f"Unreviewed encounter behavior: {name}.{prop}")
        # The donor supplies species, never its population count. Evaluate
        # both variants using the target's unchanged 1+2 population budget.
        original_hp = hp_budget(pool, pool["original_templates"])
        ratio = hp_budget(pool, templates) / original_hp
        if not pool["hp_budget_ratio"][0] <= ratio <= pool["hp_budget_ratio"][1]:
            raise ValueError(f"Composition outside the reviewed HP budget: {name}")
    if len({territories[name][CHANGED_PROPERTY] for name in donors}) < 2:
        raise ValueError("Donors do not provide composition variation")


def hp_budget(pool: dict, templates: list[str]) -> int:
    return sum(pool["enemies"][mob]["hp_coefficient"] * count for mob, count in zip(templates, pool["counts"], strict=True))


def make_plan(catalog: dict, territories: dict, mobs: dict, battles: dict, characters: dict,
              seed: str, only: list[str] | None = None) -> tuple[dict, dict]:
    if catalog.get("schema_version") != 2 or catalog.get("algorithm") != ALGORITHM:
        raise ValueError("Unsupported catalog or selection algorithm")
    if not isinstance(seed, str) or not seed or len(seed) > 256 or "\0" in seed:
        raise ValueError("Seed must contain 1 to 256 characters without NUL")
    allowed = [name for pool in catalog["pools"] for name in pool["targets"]]
    if len(allowed) != len(set(allowed)):
        raise ValueError("An encounter cannot belong to two pools")
    if only is not None and (not only or len(only) != len(set(only)) or not set(only) <= set(allowed)):
        raise ValueError("--only must be a unique subset of the explicit target allowlist")
    edits, choices = [], []
    for pool in sorted(catalog["pools"], key=lambda p: p["id"]):
        validate_pool(pool, territories, mobs, battles, characters)
        donors = sorted(pool["donors"])
        for target in sorted(pool["targets"]):
            if only is not None and target not in only:
                continue
            key = json.dumps([ALGORITHM, seed, pool["id"], target], ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            donor = donors[int(digest, 16) % len(donors)]
            before = split(territories[target][CHANGED_PROPERTY])
            after = split(territories[donor][CHANGED_PROPERTY])
            choices.append({"target": target, "pool": pool["id"], "donor": donor,
                            "before": before, "after": after, "selection_sha256": digest,
                            "levels": pool["levels"], "counts": pool["counts"],
                            "donor_native_counts": pool["donors"][donor]["counts"],
                            "physique_size": pool["physique_size"], "move_type": pool["move_type"],
                            "hp_coefficient_budget": {"before": hp_budget(pool, before), "after": hp_budget(pool, after)}})
            if before != after:
                edits.append({"name": target, "set": {CHANGED_PROPERTY: after}})
    spec = {"tables": [{"asset": catalog["assets"]["territory"]["path"], "rows": edits}]}
    audit = {"schema_version": 2, "algorithm": ALGORITHM, "seed": seed, "choices": choices,
             "changed_count": len(edits), "native_validation": "pending",
             "note": "Offline table checks do not prove arena validity, completion, or balance in game."}
    return spec, audit


def verify_result(before: dict, after: dict, spec: dict) -> None:
    if before.keys() != after.keys():
        raise ValueError("Output added or removed territory rows")
    expected = {row["name"]: "|".join(row["set"][CHANGED_PROPERTY]) for row in spec["tables"][0]["rows"]}
    for name, original in before.items():
        wanted = dict(original)
        if name in expected:
            wanted[CHANGED_PROPERTY] = expected[name]
        if after[name] != wanted:
            raise ValueError(f"Unexpected change in output territory {name}")
