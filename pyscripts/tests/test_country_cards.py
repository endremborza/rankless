from pyscripts.explore import country_cards

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


def test_generic_names_never_become_candidates() -> None:
    for name in GENERIC:
        assert country_cards.is_generic_name(name), name
    for name in MISDIRECTING:
        assert not country_cards.is_generic_name(name), name
