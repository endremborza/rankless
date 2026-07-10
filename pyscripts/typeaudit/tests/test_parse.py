"""Parser behaviour on inline fixtures (stable, independent of the live files)."""

from pyscripts.typeaudit import rustparse, tsparse

_RUST = """
#[derive(Serialize, Clone)]
pub(crate) struct Inner {
    pub name: String,
    #[serde(rename = "semanticId")]
    pub semantic_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extra: Option<u32>,
}

#[derive(Serialize)]
pub struct Outer {
    #[serde(flatten)]
    pub inner: Inner,
    #[serde(skip_serializing)]
    pub secret: u8,
    pub tail: u16,
}

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum Ev {
    MergeAuthors {
        keep: Subject,
        drop: Subject,
    },
    ClaimPaper,
}
"""

_TS = """
export type Inner = {
    name: string;
    semanticId: string;
    extra?: number;
};
type Local = { only: number };
export type Ev =
    | { kind: 'merge_authors'; keep: Subject; drop: Subject; note?: string }
    | { kind: 'claim_paper'; work: Subject };
"""


def test_rust_rename_flatten_skip_optional():
    reg = rustparse.parse_rust(_RUST, "fix")
    keys = rustparse.serialized_keys("Outer", reg)
    # flatten inlines Inner's keys (with rename), skip drops `secret`
    assert set(keys) == {"name", "semanticId", "extra", "tail"}
    assert keys["extra"].optional and not keys["tail"].optional


def test_rust_enum_variant_tags_and_fields():
    reg = rustparse.parse_rust(_RUST, "fix")
    ev = reg["Ev"]
    tags = {
        rustparse.variant_tag(v, ev.rename_all): [f.ident for f in fs]
        for v, fs in ev.variants.items()
    }
    assert tags == {"merge_authors": ["keep", "drop"], "claim_paper": []}


def test_ts_object_union_optional_and_local():
    reg = tsparse.parse_ts(_TS, "fix")
    assert set(reg["Inner"].keys) == {"name", "semanticId", "extra"}
    assert reg["Inner"].keys["extra"].optional
    assert set(reg["Local"].keys) == {"only"}  # unexported alias is still parsed
    variants = reg["Ev"].variants
    assert set(variants["merge_authors"]) == {"keep", "drop", "note"}  # `kind` dropped
    assert variants["merge_authors"]["note"].optional
