from wfmt.visual import PART_LABELS, category_of, part_of, unmatched_group


def test_part_of_warframe_parts():
    assert part_of("protea_prime_chassis_blueprint") == "chassis"
    assert part_of("protea_prime_neuroptics_blueprint") == "neuroptics"
    assert part_of("protea_prime_systems_blueprint") == "systems"
    assert part_of("protea_prime_blueprint") == "blueprint"
    assert part_of("protea_prime_set") == "set"


def test_part_of_weapon_parts():
    assert part_of("soma_prime_barrel") == "barrel"
    assert part_of("soma_prime_receiver") == "receiver"
    assert part_of("fluctus_limbs") == "limbs"
    assert part_of("dual_kamas_prime_blade") == "blade"
    assert part_of("primed_continuity") is None


def test_every_part_has_label():
    for key in ("chassis", "neuroptics", "systems", "blueprint", "set", "barrel", "receiver", "stock", "blade", "handle"):
        assert PART_LABELS[key]


def test_category_of():
    assert category_of(["mod", "rare"]) == "mod"
    assert category_of(["arcane_enhancement"]) == "arcane"
    assert category_of(["relic"]) == "relic"
    assert category_of(["component", "prime", "warframe", "blueprint"]) == "prime"
    assert category_of(["key"]) == "other"


def test_unmatched_group():
    assert unmatched_group("/Lotus/Types/Items/MiscItems/OrokinCell") == "Ресурсы"
    assert unmatched_group("/Lotus/Types/Recipes/Weapons/GalariakPrimeBlueprint") == "Чертежи"
    assert unmatched_group("/Lotus/Upgrades/Mods/Randomized/RawRifleRandomMod") == "Моды"
    assert unmatched_group("/Lotus/Something/Else") == "Прочее"


def test_rarity_of():
    from wfmt.visual import rarity_of

    assert rarity_of(["mod", "rare", "pistol"]) == "rare"
    assert rarity_of(["mod", "legendary"]) == "legendary"
    assert rarity_of(["prime", "component"]) is None


def test_relic_tier():
    from wfmt.visual import relic_tier

    assert relic_tier("lith_g1_relic") == "lith"
    assert relic_tier("requiem_iv_relic") == "requiem"
    assert relic_tier("ash_prime_set") is None


def test_subcategory_of():
    from wfmt.visual import SUBCAT_LABELS, subcategory_of

    assert subcategory_of(["blueprint", "component", "prime", "warframe"], "ash_prime_systems_blueprint") == "prime:warframe"
    # weapon parts have no weapon-class tag: it comes from the set
    assert subcategory_of(["component", "prime", "weapon"], "soma_prime_barrel", set_tags=["weapon", "prime", "primary", "set"]) == "prime:primary"
    assert subcategory_of(["mod", "primary", "rare", "rifle"], "serration") == "mod:primary"
    assert subcategory_of(["mod", "pistol", "secondary", "uncommon"], "x") == "mod:secondary"
    assert subcategory_of(["aura", "mod", "rare"], "x") == "mod:aura"
    assert subcategory_of(["mod", "stance", "melee", "rare"], "x") == "mod:stance"
    assert subcategory_of(["mod", "parazon", "rare"], "x") == "mod:parazon"
    assert subcategory_of(["mod", "railjack", "rare"], "x") == "mod:railjack"
    assert subcategory_of(["arcane_enhancement", "rare"], "x") == "arcane:rare"
    assert subcategory_of(["meso", "relic"], "meso_v2_relic") == "relic:meso"
    assert subcategory_of(["misc", "scene"], "x") == "other:scene"
    assert subcategory_of(["fish"], "x") == "other:fish"
    assert subcategory_of(["focus", "lens"], "x") == "other:lens"
    assert subcategory_of(["ayatan_sculpture"], "x") == "other:ayatan"
    assert subcategory_of(["component", "weapon"], "x") == "other:parts"
    for key in ("prime:warframe", "mod:aura", "relic:meso", "other:scene", "arcane:rare"):
        assert SUBCAT_LABELS[key]
