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

WORLD = gcm.World(
    iso2=frozenset({"HU", "AT", "SK", "DE", "GE", "US", "GB", "FR"}),
    cities={"budapest": "Budapest", "vienna": "Vienna", "bratislava": "Bratislava"},
    country_names={"HU": "Hungary", "GE": "Georgia", "US": "United States"},
)

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


def test_country_card_validates_decoys_against_the_truth_and_the_name() -> None:
    ok, _ = gcm.judge("country-card", UGA, [], ["ge", "GB", "FR"], WORLD)
    assert ok is None  # Georgia is in the name
    ok, _ = gcm.judge("country-card", UGA, [], ["US", "GB", "FR"], WORLD)
    assert ok is None  # the true country among the decoys
    ok, _ = gcm.judge("country-card", UGA, [], ["XX", "GB", "FR"], WORLD)
    assert ok is None
    ok, why = gcm.judge("country-card", UGA, [], ["de", "GB", "FR"], WORLD)
    assert ok == {"decoys": ["DE", "GB", "FR"]}, why


def test_city_card_needs_pool_cities_and_an_unnamed_city() -> None:
    ok, _ = gcm.judge(
        "city-card", BUDAPEST, [], ["Vienna", "Bratislava", "Munich"], WORLD
    )
    assert ok is None  # the anchor names its city
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
    ok, _ = gcm.judge(
        "nearest-card", SZEGED, [ELTE, BRATISLAVA, MUNICH, VIENNA], [], WORLD
    )
    assert ok is None
    # co-located options share the nearest slot
    ok, _ = gcm.judge(
        "nearest-card", SZEGED, [ELTE, BUDAPEST, VIENNA, MUNICH], [], WORLD
    )
    assert ok is None
    far = gcm.Place("far", "Far University", "Far", "US", -40.0, 170.0)
    ok, _ = gcm.judge(
        "nearest-card", far, [ELTE, VIENNA, MUNICH, BRATISLAVA], [], WORLD
    )
    assert ok is None
    unlocated = gcm.Place("x", "X", "", "")
    ok, _ = gcm.judge(
        "nearest-card", SZEGED, [unlocated, VIENNA, MUNICH, ELTE], [], WORLD
    )
    assert ok is None


def test_intruder_card_recomputes_the_country_from_the_locals() -> None:
    ok, why = gcm.judge("intruder-card", VIENNA, [ELTE, BUDAPEST, SZEGED], [], WORLD)
    assert ok is not None and ok["country"] == "HU", why
    assert [o["semId"] for o in ok["options"]] == ["elte", "bme", "szte"]
    ok, _ = gcm.judge("intruder-card", VIENNA, [ELTE, BRATISLAVA, SZEGED], [], WORLD)
    assert ok is None
    ok, _ = gcm.judge("intruder-card", ELTE, [BUDAPEST, SZEGED, ELTE], [], WORLD)
    assert ok is None
    us_named = gcm.Place(
        "usn", "United States Naval Academy", "Annapolis", "US", 38.98, -76.48
    )
    ok, _ = gcm.judge("intruder-card", us_named, [ELTE, BUDAPEST, SZEGED], [], WORLD)
    assert ok is None


def test_local_card_keeps_the_others_out_of_the_city_and_its_name() -> None:
    ok, why = gcm.judge("local-card", ELTE, [VIENNA, MUNICH, BRATISLAVA], [], WORLD)
    assert ok is not None and ok["city"] == "Budapest", why
    assert ok["options"][0] == {
        "semId": "univie",
        "name": "University of Vienna",
        "cc": "AT",
        "city": "Vienna",
    }
    ok, _ = gcm.judge("local-card", ELTE, [BUDAPEST, MUNICH, BRATISLAVA], [], WORLD)
    assert ok is None
    ok, _ = gcm.judge("local-card", BUDAPEST, [VIENNA, MUNICH, BRATISLAVA], [], WORLD)
    assert ok is None
    ok, _ = gcm.judge(
        "local-card",
        ELTE,
        [
            VIENNA,
            gcm.Place("b2", "Budapest Business School", "Vienna", "AT"),
            BRATISLAVA,
        ],
        [],
        WORLD,
    )
    assert ok is None


def test_place_parts_reads_city_and_flag() -> None:
    assert gcm.place_parts("Stanford, 🇺🇸") == ("Stanford", "US")
    assert gcm.place_parts("") == ("", "")
