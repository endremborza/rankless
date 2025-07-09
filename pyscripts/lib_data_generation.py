import json
from pathlib import Path

import pandas as pd
from ccl_science_data.common import EntC, GenReader, get_arr

asset_dir = Path("src/lib/assets/data")

handed_names = [
    " - ",
    "Industrial relations - Business, Management and Accounting",
    "Molecular Biology - Biochemistry, Genetics and Molecular Biology",
    "Electrical and Electronic Engineering - Engineering",
    "Materials Chemistry - Materials Science",
    "Sociology and Political Science - Social Sciences",
    "Surgery - Medicine",
    "Plant Science - Agricultural and Biological Sciences",
    "Biomedical Engineering - Engineering",
    "Artificial Intelligence - Computer Science",
    "Epidemiology - Medicine",
    "Atomic and Molecular Physics, and Optics - Physics and Astronomy",
    "Genetics - Biochemistry, Genetics and Molecular Biology",
    "Physiology - Medicine",
    "Pulmonary and Respiratory Medicine - Medicine",
    "Organic Chemistry - Chemistry",
    "Oncology - Medicine",
    "Cognitive Neuroscience - Neuroscience",
    "Immunology - Immunology and Microbiology",
    "Public Health, Environmental and Occupational Health - Medicine",
    "Ecology - Environmental Science",
    "Cardiology and Cardiovascular Medicine - Medicine",
    "Mechanical Engineering - Engineering",
    "Clinical Psychology - Psychology",
    "Astronomy and Astrophysics - Physics and Astronomy",
    "Education - Social Sciences",
    "Cellular and Molecular Neuroscience - Neuroscience",
    "Computer Vision and Pattern Recognition - Computer Science",
    "Social Psychology - Psychology",
    "Global and Planetary Change - Environmental Science",
    "Political Science and International Relations - Social Sciences",
    "Radiology, Nuclear Medicine and Imaging - Medicine",
    "Cell Biology - Biochemistry, Genetics and Molecular Biology",
    "Computer Networks and Communications - Computer Science",
    "General Health Professions - Health Professions",
    "Renewable Energy, Sustainability and the Environment - Energy",
    "Atmospheric Science - Earth and Planetary Sciences",
    "Nuclear and High Energy Physics - Physics and Astronomy",
    "Endocrinology, Diabetes and Metabolism - Medicine",
    "Psychiatry and Mental health - Medicine",
    "Computational Mechanics - Engineering",
    "Control and Systems Engineering - Engineering",
    "Mechanics of Materials - Engineering",
    "Ecology, Evolution, Behavior and Systematics - Agricultural and Biological Sciences",
    "Cancer Research - Biochemistry, Genetics and Molecular Biology",
    "Geophysics - Earth and Planetary Sciences",
    "Civil and Structural Engineering - Engineering",
    "Experimental and Cognitive Psychology - Psychology",
    "Neurology - Medicine",
    "Strategy and Management - Business, Management and Accounting",
    "Pharmacology - Medicine",
    "Computational Theory and Mathematics - Computer Science",
    "Management Science and Operations Research - Decision Sciences",
    "Information Systems - Computer Science",
    "Spectroscopy - Chemistry",
    "Health, Toxicology and Mutagenesis - Environmental Science",
    "Biomaterials - Materials Science",
    "Food Science - Agricultural and Biological Sciences",
    "Nutrition and Dietetics - Nursing",
    "Aerospace Engineering - Engineering",
    "Pediatrics, Perinatology and Child Health - Medicine",
    "Rheumatology - Medicine",
    "Water Science and Technology - Environmental Science",
    "Statistics and Probability - Mathematics",
    "Statistical and Nonlinear Physics - Physics and Astronomy",
    "Oceanography - Earth and Planetary Sciences",
    "Pollution - Environmental Science",
    "Hematology - Medicine",
    "Inorganic Chemistry - Chemistry",
    "Organizational Behavior and Human Resource Management - Business, Management and Accounting",
    "Finance - Economics, Econometrics and Finance",
    "Polymers and Plastics - Materials Science",
    "Nature and Landscape Conservation - Environmental Science",
    "Environmental Engineering - Environmental Science",
    "Condensed Matter Physics - Physics and Astronomy",
    "Accounting - Business, Management and Accounting",
    "Environmental Chemistry - Environmental Science",
    "Genetics - Medicine",
    "Language and Linguistics - Arts and Humanities",
    "Physical and Theoretical Chemistry - Chemistry",
    "Building and Construction - Engineering",
    "Neurology - Neuroscience",
    "General Economics, Econometrics and Finance - Economics, Econometrics and Finance",
    "Ocean Engineering - Engineering",
    "Insect Science - Agricultural and Biological Sciences",
    "Reproductive Medicine - Medicine",
    "Management Information Systems - Business, Management and Accounting",
    "Hepatology - Medicine",
    "Gender Studies - Social Sciences",
    "Management, Monitoring, Policy and Law - Environmental Science",
    "Ophthalmology - Medicine",
    "Health - Social Sciences",
    "Animal Science and Zoology - Agricultural and Biological Sciences",
    "Nephrology - Medicine",
    "Applied Mathematics - Mathematics",
    "Anthropology - Social Sciences",
    "Marketing - Business, Management and Accounting",
    "Industrial and Manufacturing Engineering - Engineering",
    "Literature and Literary Theory - Arts and Humanities",
    "Statistics, Probability and Uncertainty - Decision Sciences",
    "Signal Processing - Computer Science",
    "Agronomy and Crop Science - Agricultural and Biological Sciences",
    "Mathematical Physics - Mathematics",
    "Endocrine and Autonomic Systems - Neuroscience",
    "Geometry and Topology - Mathematics",
    "Obstetrics and Gynecology - Medicine",
    "Automotive Engineering - Engineering",
    "Analytical Chemistry - Chemistry",
    "Dermatology - Medicine",
    "Biotechnology - Biochemistry, Genetics and Molecular Biology",
    "Safety Research - Social Sciences",
    "Demography - Social Sciences",
    "Communication - Social Sciences",
    "Surfaces, Coatings and Films - Materials Science",
    "Pharmacology - Pharmacology, Toxicology and Pharmaceutics",
    "Parasitology - Immunology and Microbiology",
    "Biochemistry - Medicine",
    "Pharmaceutical Science - Pharmacology, Toxicology and Pharmaceutics",
    "Emergency Medicine - Medicine",
    "Biochemistry - Biochemistry, Genetics and Molecular Biology",
    "Information Systems and Management - Decision Sciences",
    "Microbiology - Immunology and Microbiology",
    "Management of Technology and Innovation - Business, Management and Accounting",
    "Catalysis - Chemical Engineering",
    "Virology - Immunology and Microbiology",
    "Molecular Medicine - Biochemistry, Genetics and Molecular Biology",
    "Radiation - Physics and Astronomy",
    "Complementary and alternative medicine - Medicine",
    "Industrial and Manufacturing Engineering - Environmental Science",
    "Rehabilitation - Medicine",
    "Clinical Biochemistry - Biochemistry, Genetics and Molecular Biology",
    "Applied Psychology - Psychology",
    "Gastroenterology - Medicine",
    "Sensory Systems - Neuroscience",
    "Oral Surgery - Dentistry",
    "Media Technology - Engineering",
    "Hardware and Architecture - Computer Science",
    "Earth-Surface Processes - Earth and Planetary Sciences",
    "Aquatic Science - Agricultural and Biological Sciences",
    "Law - Social Sciences",
    "Periodontics - Dentistry",
    "General Agricultural and Biological Sciences - Agricultural and Biological Sciences",
    "Cultural Studies - Social Sciences",
    "Urology - Medicine",
    "Emergency Medical Services - Health Professions",
    "History and Philosophy of Science - Arts and Humanities",
    "Safety, Risk, Reliability and Quality - Engineering",
    "Electrochemistry - Chemistry",
    "Human-Computer Interaction - Computer Science",
    "Behavioral Neuroscience - Neuroscience",
    "Transportation - Social Sciences",
    "Geochemistry and Petrology - Earth and Planetary Sciences",
    "Orthodontics - Dentistry",
    "Modeling and Simulation - Mathematics",
    "Anesthesiology and Pain Medicine - Medicine",
    "Urban Studies - Social Sciences",
    "Critical Care and Intensive Care Medicine - Medicine",
    "Public Administration - Social Sciences",
    "Physiology - Biochemistry, Genetics and Molecular Biology",
    "Geriatrics and Gerontology - Medicine",
    "Otorhinolaryngology - Medicine",
    "Ecological Modeling - Environmental Science",
    "Speech and Hearing - Health Professions",
    "Computer Science Applications - Computer Science",
    "Geography, Planning and Development - Social Sciences",
    "Linguistics and Language - Social Sciences",
    "Physical Therapy, Sports Therapy and Rehabilitation - Health Professions",
    "Algebra and Number Theory - Mathematics",
    "Visual Arts and Performing Arts - Arts and Humanities",
    "Religious studies - Arts and Humanities",
    "Internal Medicine - Medicine",
    "Geology - Earth and Planetary Sciences",
    "General Decision Sciences - Decision Sciences",
    "Radiological and Ultrasound Technology - Health Professions",
    "Bioengineering - Chemical Engineering",
    "Computer Graphics and Computer-Aided Design - Computer Science",
    "Development - Social Sciences",
    "Health Information Management - Health Professions",
    "Pharmacy - Health Professions",
    "Software - Computer Science",
    "Music - Arts and Humanities",
    "Toxicology - Pharmacology, Toxicology and Pharmaceutics",
    "Classics - Arts and Humanities",
    "Transplantation - Medicine",
    "Occupational Therapy - Health Professions",
    "Biological Psychiatry - Neuroscience",
    "Process Chemistry and Technology - Chemical Engineering",
    "Discrete Mathematics and Combinatorics - Mathematics",
    "Developmental Biology - Biochemistry, Genetics and Molecular Biology",
    "Forestry - Agricultural and Biological Sciences",
    "General Psychology - Psychology",
    "Museology - Arts and Humanities",
    "Energy Engineering and Power Technology - Energy",
    "Family Practice - Medicine",
    "General Materials Science - Materials Science",
    "Instrumentation - Physics and Astronomy",
    "Complementary and Manual Therapy - Health Professions",
    "Theoretical Computer Science - Mathematics",
    "Neuropsychology and Physiological Psychology - Psychology",
    "Applied Microbiology and Biotechnology - Immunology and Microbiology",
    "Filtration and Separation - Chemical Engineering",
    "Conservation - Arts and Humanities",
    "Equine - Veterinary",
    "Human Factors and Ergonomics - Social Sciences",
    "Structural Biology - Biochemistry, Genetics and Molecular Biology",
    "Business and International Management - Business, Management and Accounting",
    "Issues, ethics and legal aspects - Nursing",
    "Architecture - Engineering",
    "Library and Information Sciences - Social Sciences",
    "Tourism, Leisure and Hospitality Management - Business, Management and Accounting",
    "Anatomy - Medicine",
    "Health Informatics - Medicine",
    "Acoustics and Ultrasonics - Physics and Astronomy",
    "Computational Mathematics - Mathematics",
    "General Energy - Energy",
    "Research and Theory - Nursing",
    "General Dentistry - Dentistry",
    "Medical Laboratory Technology - Health Professions",
    "Microbiology - Medicine",
    "Archeology - Social Sciences",
    "Space and Planetary Science - Earth and Planetary Sciences",
    "Horticulture - Agricultural and Biological Sciences",
    "Chemical Health and Safety - Chemical Engineering",
    "Leadership and Management - Nursing",
    "Fuel Technology - Energy",
    "General Arts and Humanities - Arts and Humanities",
    "Life-span and Life-course Studies - Social Sciences",
    "Medical Terminology - Health Professions",
    "Nuclear Energy and Engineering - Energy",
    "Drug Discovery - Pharmacology, Toxicology and Pharmaceutics",
    "Paleontology - Earth and Planetary Sciences",
    "General Engineering - Engineering",
    "Small Animals - Veterinary",
    "Economics and Econometrics - Economics, Econometrics and Finance",
    "Infectious Diseases - Medicine",
    "Electronic, Optical and Magnetic Materials - Materials Science",
    "Developmental and Educational Psychology - Psychology",
    "Orthopedics and Sports Medicine - Medicine",
    "Soil Science - Agricultural and Biological Sciences",
    "Immunology and Allergy - Medicine",
    "Philosophy - Arts and Humanities",
    "Biophysics - Biochemistry, Genetics and Molecular Biology",
    "Endocrinology - Biochemistry, Genetics and Molecular Biology",
    "Fluid Flow and Transfer Processes - Chemical Engineering",
    "Ceramics and Composites - Materials Science",
    "Developmental Neuroscience - Neuroscience",
    "Archeology - Arts and Humanities",
    "History - Arts and Humanities",
    "Numerical Analysis - Mathematics",
    "Aging - Biochemistry, Genetics and Molecular Biology",
    "Metals and Alloys - Materials Science",
    "General Social Sciences - Social Sciences",
    "Pathology and Forensic Medicine - Medicine",
]

scales = [130, 100]


def scaleri(s, i):
    return lambda x: round((x - s["min"]) / (s["max"] - s["min"]) * scales[i], 1)


def get_loc_inds(gr: GenReader):
    f_names = gr.get_names(EntC.FIELDS)
    our_full_names = [
        f"{sfn} - {f_names[fi]}"
        for sfn, fi in zip(
            gr.get_names(EntC.SUBFIELDS), get_arr(f"a2_init_atts/subfield-ancestors", 8)
        )
    ]
    return {v: i for i, v in enumerate(our_full_names)}


def get_maps(els, gr):
    idmap = {}
    locmap = {}
    our_inds = get_loc_inds(gr)
    for n in els["nodes"]:
        nd = n["data"]
        shid = nd["shared_name"]
        our_ind = our_inds[handed_names[int(shid)]]
        # our_ind = int(shid)
        idmap[nd["id"]] = our_ind
        locmap[our_ind] = [int(n["position"][k]) for k in ["x", "y"]]
    return idmap, locmap


def get_edges(els, idmap):
    es = []
    for e in els["edges"]:
        ed = e["data"]
        es.append(
            [idmap[ed[k]] for k in ["source", "target"]]
            + [round(ed["Column_3"] * 100, 2)]
        )
    return es


if __name__ == "__main__":
    gr = GenReader()
    d = json.loads(Path("extern/TreeAuthors025.csv.json").read_text())

    els = d["elements"]
    idmap, locmap = get_maps(els, gr)
    edges = get_edges(els, idmap)

    scis = (
        pd.DataFrame(locmap)
        .T.agg(["min", "max"])
        .pipe(lambda df: [df.loc[:, i].pipe(scaleri, i=i) for i in range(2)])
    )

    scaled_locs = {k: [scis[i](e) for i, e in enumerate(v)] for k, v in locmap.items()}

    hier_desc = {
        k: [
            [name, anc]
            for name, anc in zip(
                gr.get_names(k),
                map(int, get_arr(f"a2_init_atts/{k[:-1]}-ancestors", 8)),
            )
        ]
        for k in [EntC.SUBFIELDS, EntC.FIELDS]
    } | {EntC.DOMAINS: gr.get_names(EntC.DOMAINS)}

    nw_n2 = (
        pd.DataFrame(edges)
        .drop(2, axis=1)
        .pipe(
            lambda df: pd.concat(
                [
                    df.assign(v=10),
                    df.merge(
                        pd.DataFrame(edges)
                        .drop(2, axis=1)
                        .rename(columns=lambda e: e + 1)
                    )
                    .assign(v=1)
                    .drop(1, axis=1)
                    .rename(columns={2: 1}),
                ]
            )
        )
        .pipe(lambda df: pd.concat([df, df.rename(columns={0: 1, 1: 0})]))
        .drop_duplicates()
    )

    adj_m = (
        nw_n2.pipe(
            lambda df: df.assign(
                **{
                    f"e-{k}": pd.DataFrame(hier_desc[EntC.SUBFIELDS])
                    .loc[:, 1]
                    .reindex(df.loc[:, k])
                    .values
                    for k in range(2)
                }
            )
        )
        .loc[lambda df: df["e-0"] != df["e-1"]]
        .pivot_table(index="e-0", columns="e-1", values="v", aggfunc="sum")
        .fillna(0)
    )

    ordered_fs = [adj_m.sum().idxmin()]
    ordered_fs = [adj_m.sum().idxmax()]
    der = 1.1
    ordered_fs = [adj_m.sum().sort_values().pipe(lambda s: s.index[int(len(s) / der)])]
    while len(ordered_fs) < len(adj_m.columns):
        ordered_fs.append(
            adj_m.apply(lambda s: s / s.sum())
            .loc[ordered_fs, :]
            .drop(ordered_fs, axis=1)
            .sum()
            .idxmax()
        )

    Path(asset_dir, "concept-map.json").write_text(
        json.dumps({"nodes": scaled_locs, "edges": edges})
    )
    Path(asset_dir, "field-hierarchy.json").write_text(json.dumps(hier_desc))
    Path(asset_dir, "fields-ordered.json").write_text(
        json.dumps({int(v): i for i, v in enumerate(ordered_fs)})
    )
