import json
import sqlite3

from pyscripts import object_store
from pyscripts.explore import cli, object_mining
from pyscripts.explore import game_card_mining as gcm

GENERIC = [
    "National Institute of Health Sciences",
    "National Institute for Medical Research",
    "National Research Council",
    "National Research Centre",
    "National Cancer Center",
    "National Physical Laboratory",
    "National Center for Tumor Diseases",
    "National Defense Medical Center",
    "National University of Defense Technology",
    "Southern Medical University",
    "Second Military Medical University",
    "Air Force Medical University",
    "Army Medical University",
    "Institute of Physics",
    "Institute of High Performance Computing",
]

MISDIRECTING = [
    "National Tsing Hua University",
    "National Sun Yat-sen University",
    "Universidad de Guadalajara",
    "Royal Children's Hospital",
    "University of Georgia",
    "The Abdus Salam International Centre for Theoretical Physics (ICTP)",
    "Medical University of Silesia",
    "Rega Institute for Medical Research",
]

BUDAPEST = gcm.Place(
    "bme", "Budapest University of Technology", "Budapest", "HU", 47.48, 19.06
)
ELTE = gcm.Place("elte", "Eötvös Loránd University", "Budapest", "HU", 47.49, 19.06)
SZEGED = gcm.Place("szte", "University of Szeged", "Szeged", "HU", 46.25, 20.15)
VIENNA = gcm.Place("univie", "University of Vienna", "Vienna", "AT", 48.21, 16.37)
BRATISLAVA = gcm.Place("uniba", "Comenius University", "Bratislava", "SK", 48.15, 17.11)
MUNICH = gcm.Place("lmu", "LMU Munich", "Munich", "DE", 48.15, 11.58)
UGA = gcm.Place("uga", "University of Georgia", "Athens", "US", 33.95, -83.37)
CERN = gcm.Place(
    "cern", "European Organization for Nuclear Research", "Geneva", "CH", 46.23, 6.05
)
DEBRECEN = gcm.Place("unideb", "Kossuth University", "Debrecen", "HU", 47.53, 21.63)
PECS = gcm.Place("pte", "Janus Pannonius University", "Pécs", "HU", 46.07, 18.23)
ROSTER = [ELTE, VIENNA, BRATISLAVA, MUNICH, BUDAPEST, SZEGED, DEBRECEN, PECS]

WORLD = gcm.World(
    iso2=frozenset({"HU", "AT", "SK", "DE", "GE", "US", "GB", "FR"}),
    cities={"budapest": "Budapest", "vienna": "Vienna", "bratislava": "Bratislava"},
    country_names={"HU": "Hungary", "GE": "Georgia", "US": "United States"},
    tiers={
        "elte": 1,
        "univie": 1,
        "uniba": 1,
        "lmu": 1,
        "unideb": 1,
        "bme": 2,
        "szte": 2,
        "pte": 2,
    },
    notes={"noted": "never an anchor"},
    homonyms=frozenset({"twin"}),
)


def test_generic_names_never_become_candidates() -> None:
    for name in GENERIC:
        assert gcm.is_generic_name(name), name
    for name in MISDIRECTING:
        assert not gcm.is_generic_name(name), name


def test_names_matches_whole_words_only() -> None:
    assert gcm.names("University of Georgia", "Georgia")
    assert gcm.names("Université de Genève", "geneve")
    assert not gcm.names("Indiana University", "India")
    assert not gcm.names("Anything", None)


def test_states_reads_head_words_and_former_place_names_too() -> None:
    assert gcm.states("Peking University", "Beijing")
    assert gcm.states("University of Tokyo", "Tokyo")
    assert gcm.states("Newcastle University", "Newcastle upon Tyne")
    assert gcm.states("Goethe University Frankfurt", "Frankfurt am Main")
    assert gcm.states("University of Freiburg", "Freiburg im Breisgau")
    assert gcm.states("Universidad de Buenos Aires", "Buenos Aires")
    assert not gcm.states("Fudan University", "Shanghai")
    assert not gcm.states("New York University", "Newark")
    assert not gcm.states("Anything", "")


def test_name_family_is_the_first_identifying_word() -> None:
    assert gcm.family("Duke University") == "duke"
    assert gcm.family("Duke University Hospital") == "duke"
    assert gcm.family("Duke Medical Center") == "duke"
    assert gcm.family("University of Szeged") == "szeged"
    assert gcm.family("Eötvös Loránd University") == "eotvos"
    assert gcm.family("Institute of Physics") == "physics"


def test_unusable_shuts_every_kind_for_notes_generic_and_shared_names() -> None:
    noted = gcm.Place("noted", "Anything University", "Town", "HU")
    assert set(gcm.unusable(noted, WORLD)) == set(gcm.KINDS)
    assert gcm.unusable(noted, WORLD)["city-card"] == "noted: never an anchor"
    generic = gcm.Place("g", "National Research Council", "Rome", "IT")
    assert gcm.unusable(generic, WORLD) == dict.fromkeys(gcm.KINDS, "generic name")
    twin = gcm.Place("twin", "Northeastern University", "Shenyang", "CN")
    assert set(gcm.unusable(twin, WORLD)) == set(gcm.KINDS)
    nowhere = gcm.Place("n", "Somewhere University", "", "")
    assert gcm.unusable(nowhere, WORLD) == dict.fromkeys(gcm.KINDS, "no country")


def test_unusable_keeps_a_city_naming_anchor_for_nearest_cards_only() -> None:
    shut = gcm.unusable(VIENNA, WORLD)
    assert shut == {k: "names its own city" for k in gcm.KINDS if k != "nearest-card"}
    hungary = gcm.Place("szte", "University of Hungary", "Pécs", "HU")
    shut = gcm.unusable(hungary, WORLD)
    assert shut["country-card"] == shut["intruder-card"] == "names its own country"
    assert "city-card" not in shut


def test_unusable_reads_the_tiers_for_nearest_and_local_cards() -> None:
    assert gcm.unusable(ELTE, WORLD) == {
        "country-card": "tier-1 fame",
        "intruder-card": "tier-1 fame",
    }
    tier2 = gcm.Place("szte", "Kossuth University", "Szeged", "HU")
    assert gcm.unusable(tier2, WORLD) == {"nearest-card": "not a tier-1 anchor"}
    assert gcm.unusable(CERN, WORLD) == {
        "nearest-card": "not a tier-1 anchor",
        "local-card": "not on the roster",
    }
    shut = gcm.unusable(gcm.Place("x", "Far Institute", "", "US"), WORLD)
    assert shut["city-card"] == shut["local-card"] == "no city"


def test_menu_lists_the_roster_around_a_tier1_anchor() -> None:
    have = {k: {} for k in gcm.KINDS}
    m = gcm.menu(BRATISLAVA, WORLD, ROSTER, have)
    assert m.open == ("nearest-card", "city-card", "local-card")
    assert [o.sem_id for o, _ in m.nearest] == [
        "univie",
        "elte",
        "bme",
        "pte",
        "szte",
        "unideb",
        "lmu",
    ]
    assert m.nearest[0][1] < 70 < m.nearest[1][1]
    have["nearest-card"]["uniba"] = "SK"
    assert "nearest-card" not in gcm.menu(BRATISLAVA, WORLD, ROSTER, have).open
    far = gcm.Place("far", "Far University", "Far", "NZ", -40.0, 170.0)
    m = gcm.menu(far, gcm.World(WORLD.iso2, {}, {}, {"far": 1}), ROSTER, have)
    assert m.shut["nearest-card"].startswith("no roster institution within")
    assert m.nearest == ()


def test_country_card_validates_decoys_against_the_truth_and_the_name() -> None:
    ok, _ = gcm.judge("country-card", UGA, [], ["ge", "GB", "FR"], WORLD)
    assert ok is None  # Georgia is in the name
    ok, _ = gcm.judge("country-card", UGA, [], ["US", "GB", "FR"], WORLD)
    assert ok is None  # the true country among the decoys
    ok, _ = gcm.judge("country-card", UGA, [], ["XX", "GB", "FR"], WORLD)
    assert ok is None
    ok, why = gcm.judge("country-card", UGA, [], ["de", "GB", "FR"], WORLD)
    assert ok == {"decoys": ["DE", "GB", "FR"]}, why


def test_city_card_needs_listed_cities_and_an_unnamed_city() -> None:
    ok, why = gcm.judge(
        "city-card", BUDAPEST, [], ["Vienna", "Bratislava", "Vienna"], WORLD
    )
    assert ok is None and why == "names its own city"
    ok, _ = gcm.judge(
        "city-card", ELTE, [], ["Vienna", "Bratislava", "Atlantis"], WORLD
    )
    assert ok is None
    ok, _ = gcm.judge(
        "city-card", ELTE, [], ["Vienna", "budapest", "Bratislava"], WORLD
    )
    assert ok is None
    ok, why = gcm.judge(
        "city-card", ELTE, [], ["vienna", "Bratislava", "Vienna"], WORLD
    )
    assert ok is None, why
    ok, why = gcm.judge(
        "city-card", CERN, [], ["vienna", "Bratislava", "Budapest"], WORLD
    )
    assert ok == {"city": "Geneva", "decoys": ["Vienna", "Bratislava", "Budapest"]}, why


def test_nearest_card_needs_a_clear_nearest_under_the_ceiling() -> None:
    ok, why = gcm.judge(
        "nearest-card", BRATISLAVA, [ELTE, VIENNA, MUNICH, SZEGED], [], WORLD
    )
    assert ok is not None, why
    kms = [o["km"] for o in ok["options"]]
    assert kms[1] == min(kms) and 40 < kms[1] < 70
    assert [o["semId"] for o in ok["options"]] == ["elte", "univie", "lmu", "szte"]
    assert ok["lat"] == 48.15 and ok["options"][1]["lon"] == 16.37
    # Budapest at 161 km against Bratislava at 312 km: inside the 2x margin
    ok, why = gcm.judge(
        "nearest-card", ELTE, [SZEGED, BRATISLAVA, MUNICH, VIENNA], [], WORLD
    )
    assert ok is None and why.startswith("no clear nearest")
    # co-located options share the nearest slot
    ok, _ = gcm.judge(
        "nearest-card", DEBRECEN, [ELTE, BUDAPEST, VIENNA, MUNICH], [], WORLD
    )
    assert ok is None
    ok, why = gcm.judge(
        "nearest-card", SZEGED, [ELTE, VIENNA, MUNICH, BRATISLAVA], [], WORLD
    )
    assert ok is None and why == "not a tier-1 anchor"


def test_options_must_be_roster_ids_with_two_of_tier_1() -> None:
    ok, why = gcm.judge(
        "nearest-card", BRATISLAVA, [ELTE, VIENNA, MUNICH, CERN], [], WORLD
    )
    assert ok is None and why == "options off the roster ['cern']"
    ok, why = gcm.judge("local-card", ELTE, [DEBRECEN, BUDAPEST, SZEGED], [], WORLD)
    assert ok is None and why == "fewer than 2 tier-1 options"


def test_intruder_and_local_options_never_state_their_own_place() -> None:
    # Vienna and Munich name their cities: fine as nearest options only
    ok, why = gcm.judge(
        "nearest-card", BRATISLAVA, [ELTE, VIENNA, MUNICH, SZEGED], [], WORLD
    )
    assert ok is not None, why
    ok, why = gcm.judge("local-card", ELTE, [VIENNA, MUNICH, BRATISLAVA], [], WORLD)
    assert ok is None and why.startswith("options stating their own place")
    peking = gcm.Place("pku", "Peking University", "Beijing", "CN", 39.99, 116.31)
    world = gcm.World(
        WORLD.iso2, WORLD.cities, WORLD.country_names, WORLD.tiers | {"pku": 1}
    )
    ok, why = gcm.judge("local-card", ELTE, [peking, BRATISLAVA, DEBRECEN], [], world)
    assert ok is None and why == "options stating their own place ['Peking University']"
    # intruder locals need no tier-1 fame, only names that give nothing away
    ok, why = gcm.judge("intruder-card", CERN, [ELTE, BUDAPEST, SZEGED], [], WORLD)
    assert ok is None and why.startswith("options stating their own place")
    ok, why = gcm.judge("intruder-card", CERN, [PECS, DEBRECEN, SZEGED], [], WORLD)
    assert (
        ok is None and why == "options stating their own place ['University of Szeged']"
    )
    ok, why = gcm.judge("intruder-card", CERN, [PECS, DEBRECEN, ELTE], [], WORLD)
    assert ok is not None and ok["country"] == "HU", why


def test_nearest_needs_a_distinct_location() -> None:
    twin = gcm.Place("uniba", "Comenius University", "Bratislava", "SK", 48.21, 16.37)
    ok, why = gcm.judge(
        "nearest-card", VIENNA, [twin, ELTE, MUNICH, DEBRECEN], [], WORLD
    )
    assert ok is None and why == "the nearest shares the anchor's location"
    have = {k: {} for k in gcm.KINDS}
    m = gcm.menu(VIENNA, WORLD, [twin, ELTE, MUNICH, DEBRECEN], have)
    assert [o.sem_id for o, _ in m.nearest] == ["elte", "lmu", "unideb"]


def test_menu_closes_a_kind_at_its_country_cap_or_outside_the_round() -> None:
    have = {k: {} for k in gcm.KINDS}
    caps = {k: object_mining.CcCap([], 1) for k in gcm.KINDS}
    caps["city-card"].add("SK")
    m = gcm.menu(BRATISLAVA, WORLD, ROSTER, have, caps)
    assert m.open == ("nearest-card", "local-card")
    assert "city-card" not in m.shut
    m = gcm.menu(BRATISLAVA, WORLD, ROSTER, have, caps, ("local-card", "city-card"))
    assert m.open == ("local-card",)


def test_intruder_card_recomputes_the_country_from_the_locals() -> None:
    ok, why = gcm.judge("intruder-card", CERN, [ELTE, PECS, DEBRECEN], [], WORLD)
    assert ok is not None and ok["country"] == "HU", why
    assert [o["semId"] for o in ok["options"]] == ["elte", "pte", "unideb"]
    ok, why = gcm.judge("intruder-card", BRATISLAVA, [ELTE, PECS, DEBRECEN], [], WORLD)
    assert ok is None and why == "tier-1 fame"
    ok, _ = gcm.judge("intruder-card", CERN, [ELTE, BRATISLAVA, DEBRECEN], [], WORLD)
    assert ok is None
    ok, _ = gcm.judge("intruder-card", ELTE, [PECS, DEBRECEN, BRATISLAVA], [], WORLD)
    assert ok is None
    us_named = gcm.Place(
        "usn", "United States Naval Academy", "Annapolis", "US", 38.98, -76.48
    )
    ok, _ = gcm.judge("intruder-card", us_named, [ELTE, PECS, DEBRECEN], [], WORLD)
    assert ok is None


def test_local_card_keeps_the_others_out_of_the_city_and_its_name() -> None:
    ok, why = gcm.judge("local-card", ELTE, [BRATISLAVA, DEBRECEN, PECS], [], WORLD)
    assert ok is not None and ok["city"] == "Budapest", why
    assert ok["options"][0] == {
        "semId": "uniba",
        "name": "Comenius University",
        "cc": "SK",
        "city": "Bratislava",
    }
    ok, _ = gcm.judge("local-card", ELTE, [BUDAPEST, BRATISLAVA, DEBRECEN], [], WORLD)
    assert ok is None
    ok, why = gcm.judge("local-card", BUDAPEST, [BRATISLAVA, DEBRECEN, PECS], [], WORLD)
    assert ok is None and why == "names its own city"
    world = gcm.World(
        WORLD.iso2, WORLD.cities, WORLD.country_names, WORLD.tiers | {"b2": 1}
    )
    ok, why = gcm.judge(
        "local-card",
        ELTE,
        [
            DEBRECEN,
            gcm.Place("b2", "Budapest Business School", "Vienna", "AT"),
            BRATISLAVA,
        ],
        [],
        world,
    )
    assert ok is None and why.startswith("options naming the city")


def test_unusable_line_groups_kinds_by_reason() -> None:
    line = gcm.unusable_line(
        gcm.Place("uh", "University of Hungary", "Pécs", "HU"),
        {
            "country-card": "names its own country",
            "intruder-card": "names its own country",
        },
    )
    assert (
        line
        == "- `uh` University of Hungary: names its own country (country, intruder)"
    )
    line = gcm.unusable_line(BUDAPEST, dict.fromkeys(gcm.KINDS, "generic name"))
    assert line.endswith(": generic name (all kinds)")
    assert gcm.unusable_line(CERN, gcm.unusable(CERN, WORLD)) == ""
    line = gcm.unusable_line(VIENNA, gcm.unusable(VIENNA, WORLD))
    assert line.endswith(": names its own city (country, intruder, city, local)")


def test_taste_groups_rejection_notes_with_examples() -> None:
    con = sqlite3.connect(":memory:")
    con.executescript(object_store.SCHEMA)
    rows = [
        ("country-card", "a", "A University", "rejected", "names the city", "t1"),
        ("city-card", "c", "C Institute", "rejected", "too famous", "t2"),
        ("country-card", "b", "B University", "rejected", "names the city", "t3"),
        ("game-card", "d", "D", "rejected", "legacy kind", "t4"),
        ("country-card", "e", "E", "new", None, "t5"),
    ]
    con.executemany(
        "INSERT INTO mcp_objects (kind, obj_key, bundle, line, gen_at, title, status,"
        " status_note, updated_at) VALUES (?, ?, 'b', 0, '2026', ?, ?, ?, ?)",
        [(k, f"institutions|{s}", t, st, n, u) for k, s, t, st, n, u in rows],
    )
    assert gcm._taste(con) == [
        "- names the city (e.g. B University, A University)",
        "- too famous (e.g. C Institute)",
    ]


def test_unwrap_result_reads_usage_from_the_json_envelope() -> None:
    envelope = {
        "type": "result",
        "result": ' {"cards": []} ',
        "duration_ms": 1500,
        "total_cost_usd": 0.5,
        "usage": {
            "output_tokens": 120,
            "output_tokens_details": {"thinking_tokens": 100},
        },
    }
    stats: dict = {}
    assert cli.unwrap_result(json.dumps(envelope), stats) == '{"cards": []}'
    assert stats == {
        "seconds": 1.5,
        "output_tokens": 120,
        "thinking_tokens": 100,
        "usd": 0.5,
    }


def test_place_parts_reads_city_and_flag() -> None:
    assert gcm.place_parts("Stanford, 🇺🇸") == ("Stanford", "US")
    assert gcm.place_parts(
        "",
    ) == ("", "")
