use super::*;

const TEST_SIZE: usize = 16;

fn get_test_engine() -> SearchEngine<TEST_SIZE> {
    let haystacks = vec![
        "abc",
        "xyz",
        "man woo",
        "axa",
        "mewixalion",
        "bumble rumble",
    ];
    SearchEngine::new(haystacks.iter().map(|s| s.to_string()))
}

#[test]
fn test_extend_sorted() {
    let mut v1 = vec![1, 2, 3];
    let v2 = vec![2, 3, 4];
    extend_sorted(&mut v1, v2);
    assert_eq!(v1, vec![1, 2, 3, 4]);
}

#[test]
fn gets_empty() {
    let engine = get_test_engine();
    assert_eq!(engine.query("").len(), 6);
}

#[test]
fn gets_starts() {
    let engine = get_test_engine();
    for (q, r0) in vec![
        ("a", 0),
        ("x", 1),
        ("ma", 2),
        ("w", 2),
        ("ax", 3),
        ("mewix", 4),
    ]
    .iter()
    {
        let result = engine.query(q);
        assert_eq!(result[0], *r0);
    }
    assert_eq!(engine.query("a")[1], 3);
    assert_eq!(engine.query("q").len(), 0);
}

#[test]
fn gets_innards() {
    let engine = get_test_engine();
    for (q, r0) in vec![
        ("y", 1),
        ("an", 2),
        ("xa", 3),
        ("ion", 4),
        ("wix", 4),
        ("ix", 4),
    ]
    .iter()
    {
        let result = engine.query(q);
        println!("{:?} for {}", result, q);
        assert_eq!(result[0], *r0);
    }
    assert_eq!(engine.query("x")[1], 3);
    assert_eq!(engine.query("x").len(), 3);
    //cant find based on one character that is the last one
    println!("{:?}", engine.query("c"));
    assert_eq!(engine.query("c").len(), 0);
}

#[test]
fn no_multiplied_result() {
    let haystacks = vec!["aba aba aba", "xxx", "zzz"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    println!("tlen: {}", engine.tree.char_array.len());
    assert_eq!(engine.query("ab").len(), 1);

    let haystacks = vec!["abas abazz abaxy", "tabaxi", "zzz"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    assert_eq!(engine.query("ab").len(), 2);
}

#[test]
fn multi_word_query() {
    let haystacks = vec!["aba cdx", "aba", "cdx", "crum brabn", "udx crtasba"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    assert_eq!(engine.query("ab cd"), vec![0]);
    assert_eq!(engine.query("ru ra"), vec![3]);
    assert_eq!(engine.query("dx ba"), vec![0, 4]);
}

#[test]
fn optimized_array() {
    let haystacks = vec!["ababc", "xaabc", "wuabc"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    assert_eq!(engine.tree.char_array.len(), 3);
}

#[test]
fn gets_long() {
    let haystacks = vec!["Hiroyasa Hidaka", "Manuel Hidalgo", "Hisao Hidaka"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    assert_eq!(engine.query("hidalgo")[0], 1);
}

#[test]
fn gets_ch() {
    let haystacks = vec!["China", "Chile", "Chad"];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    assert_eq!(engine.query("ch")[0], 0);
}

#[test]
fn perfect_match() {
    let mut haystacks: Vec<String> = (0..30).map(|_| "Wes".to_string()).collect();
    haystacks.push("West".to_string());
    let engine: SearchEngine<TEST_SIZE> = SearchEngine::new(haystacks.into_iter());
    assert_eq!(engine.query("west")[0], 30);
}

#[test]
fn serialization_roundtrip() {
    let engine = get_test_engine();
    let queries = [
        "", "a", "x", "ma", "w", "ax", "mewix", "y", "an", "xa", "ion", "wix", "ix", "ab cd",
        "man woo", "bumble", "rumble", "q",
    ];
    let expected: Vec<Vec<IndType>> = queries.iter().map(|q| engine.query(q)).collect();

    let mut buf = Vec::new();
    engine.save(&mut buf).unwrap();

    let loaded: SearchEngine<TEST_SIZE> =
        SearchEngine::try_load(&mut &buf[..]).expect("load failed");

    for (i, q) in queries.iter().enumerate() {
        assert_eq!(loaded.query(q), expected[i], "mismatch for query '{}'", q);
    }
}

#[test]
fn serialization_rejects_bad_magic() {
    let buf = vec![0u8; 200];
    assert!(SearchEngine::<TEST_SIZE>::try_load(&mut &buf[..]).is_none());
}

#[test]
fn serialization_rejects_truncated() {
    let engine = get_test_engine();
    let mut buf = Vec::new();
    engine.save(&mut buf).unwrap();
    buf.truncate(buf.len() / 2);
    assert!(SearchEngine::<TEST_SIZE>::try_load(&mut &buf[..]).is_none());
}

#[test]
fn serialization_rejects_wrong_s() {
    let engine = get_test_engine();
    let mut buf = Vec::new();
    engine.save(&mut buf).unwrap();
    assert!(SearchEngine::<4>::try_load(&mut &buf[..]).is_none());
}

#[test]
fn lincoln() {
    //because it assumes to that results for words are all sorted
    let haystacks = vec![
        "MIT",
        "MITb",
        "MITc",
        "MIT Lincoln Laboratory",
        "GlaxoSmithKline",
        "MITc",
        "MITc",
        "MITc",
        "MITc",
    ];
    let engine: SearchEngine<TEST_SIZE> =
        SearchEngine::new(haystacks.iter().map(|s| s.to_string()));
    println!("{:?}", engine.query("mit linc"));
    assert_eq!(engine.query("mit linc")[0], 3);
}
