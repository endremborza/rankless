//! The expression language of the table: `where=` narrows a cohort with clauses over metric calls
//! combined by `and`, `or`, `not` and parentheses (precedence parentheses > not > and > or),
//! `sort=` names one call, `metrics=` a list of calls. Parsing is syntactic only; what a metric
//! is, whether an operator fits its value type and what a name resolves to is settled by the
//! binder against the registry.
//!
//! A name is a bare slug or a quoted string, in which `\X` is the character `X` — the only escape
//! there is, and what `Display` emits for a quote or a backslash. The limits below bound every
//! input before and during parsing, so nothing a request carries can drive the recursion deep
//! enough to overflow the stack.

use std::fmt;

use serde::Serialize;

// Every input is bounded. Depth is the one that matters for safety: the parser descends one level
// per nested parenthesis or `not`, and a stack overflow is not a catchable panic.
pub const MAX_INPUT_BYTES: usize = 2048;
pub const MAX_DEPTH: u8 = 16;
pub const MAX_CLAUSES: usize = 32;
pub const MAX_LIST_ITEMS: usize = 64;

// Externally tagged on purpose: an internal tag wraps the serializer per level, which a recursive
// tree turns into an unbounded type.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Expr {
    Clause(Clause),
    And(Vec<Expr>),
    Or(Vec<Expr>),
    Not(Box<Expr>),
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Clause {
    pub call: Call,
    pub op: Op,
    pub operand: Operand,
}

// A metric with its arguments: `papers`, `field_score(oncology)`, `window_papers(2020, 2024)`.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Call {
    pub metric: String,
    pub args: Vec<Arg>,
}

// A bare word is a slug (a semantic id), a quoted string a name that may carry spaces.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum Arg {
    Num(f64),
    Name(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Op {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    In,
    NotIn,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum Operand {
    Num(f64),
    Name(String),
    List(Vec<Arg>),
}

#[derive(Debug, Clone, PartialEq)]
pub struct ParseError {
    // A character position, not a byte offset: the tokens carry byte offsets, the error converts.
    pub at: usize,
    pub msg: &'static str,
}

#[derive(Debug, Clone, PartialEq)]
enum Token {
    Ident(String),
    Num(f64),
    Str(String),
    LParen,
    RParen,
    Comma,
    Op(Op),
    And,
    Or,
    Not,
    In,
}

struct Parser<'a> {
    src: &'a str,
    tokens: Vec<(usize, Token)>,
    pos: usize,
    clauses: usize,
}

impl Op {
    pub fn is_membership(self) -> bool {
        matches!(self, Self::In | Self::NotIn)
    }
}

impl fmt::Display for Op {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Eq => "=",
            Self::Ne => "!=",
            Self::Lt => "<",
            Self::Le => "<=",
            Self::Gt => ">",
            Self::Ge => ">=",
            Self::In => "in",
            Self::NotIn => "not in",
        })
    }
}

impl fmt::Display for Arg {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Num(n) => write!(f, "{n}"),
            Self::Name(s) => write_name(f, s),
        }
    }
}

impl fmt::Display for Operand {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Num(n) => write!(f, "{n}"),
            Self::Name(s) => write_name(f, s),
            Self::List(items) => {
                f.write_str("(")?;
                for (i, a) in items.iter().enumerate() {
                    if i > 0 {
                        f.write_str(", ")?;
                    }
                    write!(f, "{a}")?;
                }
                f.write_str(")")
            }
        }
    }
}

impl fmt::Display for Call {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.metric)?;
        if !self.args.is_empty() {
            f.write_str("(")?;
            for (i, a) in self.args.iter().enumerate() {
                if i > 0 {
                    f.write_str(", ")?;
                }
                write!(f, "{a}")?;
            }
            f.write_str(")")?;
        }
        Ok(())
    }
}

impl fmt::Display for Clause {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} {} {}", self.call, self.op, self.operand)
    }
}

// The canonical text: minimal parentheses, one space around every operator.
impl fmt::Display for Expr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Clause(c) => write!(f, "{c}"),
            Self::And(items) => join(f, items, " and ", 2),
            Self::Or(items) => join(f, items, " or ", 3),
            Self::Not(e) => {
                f.write_str("not ")?;
                paren_if(f, e, 1)
            }
        }
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} at character {}", self.msg, self.at + 1)
    }
}

impl<'a> Parser<'a> {
    fn new(s: &'a str) -> Result<Self, ParseError> {
        if s.len() > MAX_INPUT_BYTES {
            return Err(err_at(s, MAX_INPUT_BYTES, "expression too long"));
        }
        Ok(Self {
            src: s,
            tokens: tokenize(s)?,
            pos: 0,
            clauses: 0,
        })
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos).map(|(_, t)| t)
    }

    fn at(&self) -> usize {
        let byte = self
            .tokens
            .get(self.pos)
            .map_or(self.src.len(), |(i, _)| *i);
        char_pos(self.src, byte)
    }

    fn next(&mut self) -> Option<Token> {
        let t = self.tokens.get(self.pos).map(|(_, t)| t.clone());
        self.pos += 1;
        t
    }

    fn expect(&mut self, want: Token, msg: &'static str) -> Result<(), ParseError> {
        if self.peek() == Some(&want) {
            self.pos += 1;
            Ok(())
        } else {
            Err(self.err(msg))
        }
    }

    fn err(&self, msg: &'static str) -> ParseError {
        ParseError { at: self.at(), msg }
    }

    fn expr(&mut self, depth: u8) -> Result<Expr, ParseError> {
        let mut items = vec![self.and_expr(depth)?];
        while self.peek() == Some(&Token::Or) {
            self.pos += 1;
            items.push(self.and_expr(depth)?);
        }
        Ok(flatten(items, Expr::Or))
    }

    fn and_expr(&mut self, depth: u8) -> Result<Expr, ParseError> {
        let mut items = vec![self.not_expr(depth)?];
        while self.peek() == Some(&Token::And) {
            self.pos += 1;
            items.push(self.not_expr(depth)?);
        }
        Ok(flatten(items, Expr::And))
    }

    // Every nesting level — a parenthesis or a `not` — descends through here, so one check bounds
    // the whole recursion, and with it the depth of the tree anything downstream walks.
    fn not_expr(&mut self, depth: u8) -> Result<Expr, ParseError> {
        if depth > MAX_DEPTH {
            return Err(self.err("nested too deeply"));
        }
        if self.peek() == Some(&Token::Not) {
            self.pos += 1;
            return Ok(Expr::Not(Box::new(self.not_expr(depth + 1)?)));
        }
        self.primary(depth)
    }

    fn primary(&mut self, depth: u8) -> Result<Expr, ParseError> {
        if self.peek() == Some(&Token::LParen) {
            self.pos += 1;
            let e = self.expr(depth + 1)?;
            self.expect(Token::RParen, "expected )")?;
            return Ok(e);
        }
        Ok(Expr::Clause(self.clause()?))
    }

    fn clause(&mut self) -> Result<Clause, ParseError> {
        self.clauses += 1;
        if self.clauses > MAX_CLAUSES {
            return Err(self.err("too many clauses"));
        }
        let call = self.call()?;
        let op = match self.next() {
            Some(Token::Op(op)) => op,
            Some(Token::In) => Op::In,
            Some(Token::Not) => {
                self.expect(Token::In, "expected in after not")?;
                Op::NotIn
            }
            _ => {
                self.pos -= 1;
                return Err(self.err("expected an operator"));
            }
        };
        let operand = if op.is_membership() {
            Operand::List(self.list()?)
        } else {
            match self.next() {
                Some(Token::Num(n)) => Operand::Num(n),
                Some(Token::Ident(s)) | Some(Token::Str(s)) => Operand::Name(s),
                _ => {
                    self.pos -= 1;
                    return Err(self.err("expected a value"));
                }
            }
        };
        Ok(Clause { call, op, operand })
    }

    fn call(&mut self) -> Result<Call, ParseError> {
        let metric = match self.next() {
            Some(Token::Ident(s)) => s,
            _ => {
                self.pos -= 1;
                return Err(self.err("expected a metric"));
            }
        };
        let args = if self.peek() == Some(&Token::LParen) {
            self.list()?
        } else {
            Vec::new()
        };
        Ok(Call { metric, args })
    }

    // `( arg, arg, ... )`, at least one.
    fn list(&mut self) -> Result<Vec<Arg>, ParseError> {
        self.expect(Token::LParen, "expected (")?;
        let mut items = Vec::new();
        loop {
            match self.next() {
                Some(Token::Num(n)) => items.push(Arg::Num(n)),
                Some(Token::Ident(s)) | Some(Token::Str(s)) => items.push(Arg::Name(s)),
                _ => {
                    self.pos -= 1;
                    return Err(self.err("expected a value"));
                }
            }
            if items.len() > MAX_LIST_ITEMS {
                return Err(self.err("too many values"));
            }
            match self.next() {
                Some(Token::Comma) => continue,
                Some(Token::RParen) => return Ok(items),
                _ => {
                    self.pos -= 1;
                    return Err(self.err("expected , or )"));
                }
            }
        }
    }

    fn done(&self) -> Result<(), ParseError> {
        if self.pos < self.tokens.len() {
            return Err(self.err("unexpected input"));
        }
        Ok(())
    }
}

pub fn parse_where(s: &str) -> Result<Expr, ParseError> {
    let mut p = Parser::new(s)?;
    let e = p.expr(0)?;
    p.done()?;
    Ok(e)
}

pub fn parse_call(s: &str) -> Result<Call, ParseError> {
    let mut p = Parser::new(s)?;
    let c = p.call()?;
    p.done()?;
    Ok(c)
}

// Comma-separated calls: `field_share(oncology), window_papers(2020, 2024)`.
pub fn parse_calls(s: &str) -> Result<Vec<Call>, ParseError> {
    let mut p = Parser::new(s)?;
    let mut calls = vec![p.call()?];
    while p.peek() == Some(&Token::Comma) {
        p.pos += 1;
        calls.push(p.call()?);
    }
    p.done()?;
    Ok(calls)
}

fn tokenize(s: &str) -> Result<Vec<(usize, Token)>, ParseError> {
    let b = s.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < b.len() {
        let c = b[i];
        let start = i;
        let tok = match c {
            b' ' | b'\t' | b'\n' | b'\r' => {
                i += 1;
                continue;
            }
            b'(' => {
                i += 1;
                Token::LParen
            }
            b')' => {
                i += 1;
                Token::RParen
            }
            b',' => {
                i += 1;
                Token::Comma
            }
            b'=' => {
                i += 1;
                Token::Op(Op::Eq)
            }
            b'!' if b.get(i + 1) == Some(&b'=') => {
                i += 2;
                Token::Op(Op::Ne)
            }
            b'<' | b'>' => {
                let eq = b.get(i + 1) == Some(&b'=');
                i += if eq { 2 } else { 1 };
                Token::Op(match (c, eq) {
                    (b'<', false) => Op::Lt,
                    (b'<', true) => Op::Le,
                    (b'>', false) => Op::Gt,
                    _ => Op::Ge,
                })
            }
            b'"' | b'\'' => {
                let quote = c;
                i += 1;
                let mut text = String::new();
                loop {
                    let Some(&byte) = b.get(i) else {
                        return Err(err_at(s, start, "unterminated string"));
                    };
                    if byte == quote {
                        i += 1;
                        break;
                    }
                    // A backslash names the character after it, whatever that character is. The
                    // unit is a character and not a byte: stepping one byte on would leave the
                    // next read inside a UTF-8 sequence.
                    if byte == b'\\' {
                        i += 1;
                    }
                    let Some(ch) = s[i..].chars().next() else {
                        return Err(err_at(s, start, "unterminated string"));
                    };
                    text.push(ch);
                    i += ch.len_utf8();
                }
                Token::Str(text)
            }
            _ if is_number_start(b, i) => {
                i = scan_number(b, i);
                let n: f64 = s[start..i]
                    .parse()
                    .map_err(|_| err_at(s, start, "bad number"))?;
                // An overflowing literal reads as an infinity, which no clause can mean and no
                // printing round-trips.
                if !n.is_finite() {
                    return Err(err_at(s, start, "bad number"));
                }
                Token::Num(n)
            }
            _ if c.is_ascii_alphabetic() || c == b'_' => {
                while i < b.len() && (b[i].is_ascii_alphanumeric() || b[i] == b'_' || b[i] == b'-')
                {
                    i += 1;
                }
                let word = &s[start..i];
                match word.to_ascii_lowercase().as_str() {
                    "and" => Token::And,
                    "or" => Token::Or,
                    "not" => Token::Not,
                    "in" => Token::In,
                    _ => Token::Ident(word.to_string()),
                }
            }
            _ => return Err(err_at(s, start, "unexpected character")),
        };
        out.push((start, tok));
    }
    Ok(out)
}

// `and`/`or` are associative, so a parenthesized child of the same kind is absorbed: `(a and b)
// and c` is one conjunction of three, not a conjunction holding a conjunction. Readers downstream
// get a normal form — the chip list is flat, `Display` needs no parentheses, and `Bound::split`
// sees every top-level clause.
fn flatten(items: Vec<Expr>, make: fn(Vec<Expr>) -> Expr) -> Expr {
    let is_and = matches!(make(Vec::new()), Expr::And(_));
    let mut out: Vec<Expr> = Vec::with_capacity(items.len());
    for item in items {
        match item {
            Expr::And(inner) if is_and => out.extend(inner),
            Expr::Or(inner) if !is_and => out.extend(inner),
            other => out.push(other),
        }
    }
    if out.len() == 1 {
        out.pop().unwrap()
    } else {
        make(out)
    }
}

// Binding strength: not 1, and 2, or 3; a child bound looser than its parent needs parentheses.
fn strength(e: &Expr) -> u8 {
    match e {
        Expr::Clause(_) => 0,
        Expr::Not(_) => 1,
        Expr::And(_) => 2,
        Expr::Or(_) => 3,
    }
}

fn paren_if(f: &mut fmt::Formatter<'_>, e: &Expr, parent: u8) -> fmt::Result {
    if strength(e) > parent {
        write!(f, "({e})")
    } else {
        write!(f, "{e}")
    }
}

fn join(f: &mut fmt::Formatter<'_>, items: &[Expr], sep: &str, parent: u8) -> fmt::Result {
    for (i, e) in items.iter().enumerate() {
        if i > 0 {
            f.write_str(sep)?;
        }
        paren_if(f, e, parent)?;
    }
    Ok(())
}

fn write_name(f: &mut fmt::Formatter<'_>, s: &str) -> fmt::Result {
    let bare = !s.is_empty()
        && s.bytes()
            .next()
            .is_some_and(|c| c.is_ascii_alphabetic() || c == b'_')
        && s.bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
        && !matches!(s.to_ascii_lowercase().as_str(), "and" | "or" | "not" | "in");
    if bare {
        f.write_str(s)
    } else {
        write!(f, "\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
    }
}

fn is_number_start(b: &[u8], i: usize) -> bool {
    match b[i] {
        b'0'..=b'9' | b'.' => true,
        b'-' => b
            .get(i + 1)
            .is_some_and(|c| c.is_ascii_digit() || *c == b'.'),
        _ => false,
    }
}

// One grammar for every number: an optional sign, digits and dots, an optional exponent. What it
// spans is what `f64` is asked to read, so `1.2.3` is one bad number rather than three tokens.
fn scan_number(b: &[u8], mut i: usize) -> usize {
    if b[i] == b'-' {
        i += 1;
    }
    while i < b.len() && (b[i].is_ascii_digit() || b[i] == b'.') {
        i += 1;
    }
    if i < b.len() && b[i].eq_ignore_ascii_case(&b'e') {
        let mut j = i + 1;
        if j < b.len() && (b[j] == b'-' || b[j] == b'+') {
            j += 1;
        }
        if j < b.len() && b[j].is_ascii_digit() {
            i = j;
            while i < b.len() && b[i].is_ascii_digit() {
                i += 1;
            }
        }
    }
    i
}

fn err_at(s: &str, byte: usize, msg: &'static str) -> ParseError {
    ParseError {
        at: char_pos(s, byte),
        msg,
    }
}

// Counting rather than slicing: a position that is not a character boundary still answers.
fn char_pos(s: &str, byte: usize) -> usize {
    s.char_indices().take_while(|(i, _)| *i < byte).count()
}

#[cfg(test)]
mod tests {
    #[test]
    fn a_parenthesized_conjunction_is_one_conjunction() {
        use super::*;
        let flat = parse_where("a > 1 and b > 2 and c > 3").unwrap();
        for text in [
            "(a > 1 and b > 2) and c > 3",
            "a > 1 and (b > 2 and c > 3)",
            "((a > 1 and b > 2) and c > 3)",
        ] {
            assert_eq!(parse_where(text).unwrap(), flat, "{text}");
        }
        assert!(
            matches!(parse_where("(a > 1 or b > 2) and c > 3").unwrap(), Expr::And(i) if i.len() == 2)
        );
    }

    use super::*;

    fn roundtrip(s: &str) -> String {
        parse_where(s).unwrap().to_string()
    }

    #[test]
    fn precedence_is_parentheses_not_and_or() {
        assert_eq!(roundtrip("a=1 or b=2 and c=3"), "a = 1 or b = 2 and c = 3");
        assert_eq!(
            roundtrip("(a=1 or b=2) and c=3"),
            "(a = 1 or b = 2) and c = 3"
        );
        assert_eq!(roundtrip("not a=1 and b=2"), "not a = 1 and b = 2");
        assert_eq!(roundtrip("not (a=1 and b=2)"), "not (a = 1 and b = 2)");
        assert_eq!(roundtrip("NOT a=1 OR b=2"), "not a = 1 or b = 2");
        let e = parse_where("a=1 or b=2 and c=3").unwrap();
        assert!(
            matches!(&e, Expr::Or(items) if items.len() == 2 && matches!(items[1], Expr::And(_)))
        );
    }

    #[test]
    fn clauses_carry_calls_operators_and_typed_operands() {
        assert_eq!(
            roundtrip(
                "country=hun and city!=budapest and (papers>=500 or weighted_paper_score>=20)"
            ),
            "country = hun and city != budapest and (papers >= 500 or weighted_paper_score >= 20)"
        );
        assert_eq!(
            roundtrip("field_citations(oncology) > 0 and window_papers(2020, 2024) >= 10"),
            "field_citations(oncology) > 0 and window_papers(2020, 2024) >= 10"
        );
        assert_eq!(
            roundtrip("cited_from(usa) >= 0.3"),
            "cited_from(usa) >= 0.3"
        );
        assert_eq!(
            roundtrip("country in (hun, aut) and city not in (\"new york\", 'los angeles')"),
            "country in (hun, aut) and city not in (\"new york\", \"los angeles\")"
        );
        assert_eq!(
            roundtrip("papers_at(budapesti-corvinus-egyetem) >= 5"),
            "papers_at(budapesti-corvinus-egyetem) >= 5"
        );
        assert_eq!(
            roundtrip("year_centroid <= 2005.5"),
            "year_centroid <= 2005.5"
        );
        assert_eq!(roundtrip("x = -1"), "x = -1");
        let c = match parse_where("papers > 1e3").unwrap() {
            Expr::Clause(c) => c,
            _ => panic!(),
        };
        assert_eq!(c.operand, Operand::Num(1000.0));
    }

    #[test]
    fn calls_and_call_lists_parse_alone() {
        assert_eq!(
            parse_call("field_score(oncology)").unwrap().to_string(),
            "field_score(oncology)"
        );
        assert_eq!(parse_call("citations").unwrap().args, vec![]);
        let calls = parse_calls("field_share(oncology), window_papers(2020, 2024)").unwrap();
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[1].args, vec![Arg::Num(2020.0), Arg::Num(2024.0)]);
        assert!(parse_call("a b").is_err());
        assert!(parse_calls("a,").is_err());
    }

    #[test]
    fn every_malformed_input_is_a_positioned_error() {
        for (s, msg) in [
            ("a=", "expected a value"),
            ("a", "expected an operator"),
            ("(a=1", "expected )"),
            ("a=1)", "unexpected input"),
            ("a in b", "expected ("),
            ("a in ()", "expected a value"),
            ("a not b", "expected in after not"),
            ("a = \"x", "unterminated string"),
            ("a = 1 & b = 2", "unexpected character"),
            ("1 = a", "expected a metric"),
            ("a(1,) = 2", "expected a value"),
        ] {
            let err = parse_where(s).unwrap_err();
            assert_eq!(err.msg, msg, "{s}");
            assert!(err.at <= s.len());
        }
        assert_eq!(
            parse_where("a=1)").unwrap_err().to_string(),
            "unexpected input at character 4"
        );
    }

    #[test]
    fn the_tree_serializes_for_a_client() {
        let e = parse_where("not country=hun and papers in (1, 2)").unwrap();
        let json = serde_json::to_string(&e).unwrap();
        assert!(
            json.starts_with("{\"and\":[{\"not\":{\"clause\":"),
            "{json}"
        );
        assert!(json.contains("\"op\":\"not_in\"") || json.contains("\"op\":\"in\""));
        assert!(json.contains("\"metric\":\"country\""));
    }

    #[test]
    fn an_escape_names_a_character_not_a_byte() {
        assert_eq!(
            operand_of(r#"city = "Budap\ést""#),
            Operand::Name("Budapést".into())
        );
        assert_eq!(
            operand_of(r#"city = "a\"b\\c""#),
            Operand::Name(r#"a"b\c"#.into())
        );
        assert_eq!(roundtrip(r#"city = "a\"b\\c""#), r#"city = "a\"b\\c""#);
        assert_eq!(
            parse_where(r#"city = "a\"#).unwrap_err().msg,
            "unterminated string"
        );
        // A position counts characters, not the bytes a name before it happened to need.
        assert_eq!(
            parse_where("x = \"á\" & 1").unwrap_err().to_string(),
            "unexpected character at character 9"
        );
    }

    #[test]
    fn one_numeric_grammar_covers_sign_and_exponent() {
        assert_eq!(operand_of("x = -1e3"), Operand::Num(-1000.0));
        assert_eq!(operand_of("x = -.5"), operand_of("x = -0.5"));
        assert_eq!(operand_of("x = 1E-2"), Operand::Num(0.01));
        for bad in ["x = 1.2.3", "x = 1e400", "x = -1e400", "x = ."] {
            assert_eq!(parse_where(bad).unwrap_err().msg, "bad number", "{bad}");
        }
    }

    #[test]
    fn every_input_is_bounded_before_it_is_parsed() {
        let depth = MAX_DEPTH as usize;
        let nested = |n: usize| format!("{}a=1{}", "(".repeat(n), ")".repeat(n));
        let nots = |n: usize| format!("{}a=1", "not ".repeat(n));
        let clauses = |n: usize| vec!["a=1"; n].join(" and ");
        let list = |n: usize| format!("a in ({})", vec!["1"; n].join(", "));
        for ok in [
            nested(depth),
            nots(depth),
            clauses(MAX_CLAUSES),
            list(MAX_LIST_ITEMS),
        ] {
            assert!(parse_where(&ok).is_ok(), "{ok}");
        }
        for (s, msg) in [
            (nested(depth + 1), "nested too deeply"),
            (nots(depth + 1), "nested too deeply"),
            (clauses(MAX_CLAUSES + 1), "too many clauses"),
            (list(MAX_LIST_ITEMS + 1), "too many values"),
            ("(".repeat(3000), "expression too long"),
            ("a".repeat(MAX_INPUT_BYTES + 1), "expression too long"),
        ] {
            assert_eq!(
                parse_where(&s).unwrap_err().msg,
                msg,
                "{}",
                &s[..8.min(s.len())]
            );
        }
    }

    // Nothing the language cannot name may panic, and everything it prints it reads back as the
    // same tree: token soup and arbitrary characters for the first, printed random trees for the
    // second.
    #[test]
    fn no_input_panics_and_whatever_prints_parses_as_itself() {
        let mut seed = 0x2545_f491_4f6c_dd1d;
        for _ in 0..5_000 {
            let printed = rand_expr(&mut seed, 3).to_string();
            let e = parse_where(&printed).unwrap_or_else(|e| panic!("{printed:?}: {e}"));
            assert_eq!(parse_where(&e.to_string()).as_ref(), Ok(&e), "{printed:?}");
        }
        const PIECES: [&str; 26] = [
            "a", "(", ")", ",", "=", "!=", ">=", "and", "or", "not", "in", "1", "-2.5", "1e3",
            "\"", "'", "\\", "é", "😊", "\\é", " ", "_x-y", ".", "e", "\t", "\u{0}",
        ];
        for _ in 0..20_000 {
            let mut s = String::new();
            for _ in 0..(1 + roll(&mut seed) % 12) {
                s.push_str(PIECES[roll(&mut seed) as usize % PIECES.len()]);
            }
            let _ = parse_where(&s);
            let _ = parse_calls(&s);
        }
        for _ in 0..20_000 {
            let mut s = String::new();
            for _ in 0..(1 + roll(&mut seed) % 8) {
                s.push(char::from_u32(roll(&mut seed) as u32 % 0x11_000).unwrap_or('x'));
            }
            let _ = parse_where(&s);
            let _ = parse_calls(&s);
        }
    }

    fn operand_of(s: &str) -> Operand {
        match parse_where(s).unwrap() {
            Expr::Clause(c) => c.operand,
            other => panic!("{other} is not one clause"),
        }
    }

    fn roll(seed: &mut u64) -> u64 {
        *seed ^= *seed << 13;
        *seed ^= *seed >> 7;
        *seed ^= *seed << 17;
        *seed
    }

    // A tree of every shape the printer has to handle: names that must be quoted, keywords and an
    // empty string among them, numbers, argument lists and each operator.
    fn rand_expr(seed: &mut u64, depth: u8) -> Expr {
        const NAMES: [&str; 8] = [
            "hun",
            "new york",
            "a\"b",
            "c\\d",
            "büdapest",
            "and",
            "",
            "x-1",
        ];
        const OPS: [Op; 8] = [
            Op::Eq,
            Op::Ne,
            Op::Lt,
            Op::Le,
            Op::Gt,
            Op::Ge,
            Op::In,
            Op::NotIn,
        ];
        const NUMS: [f64; 5] = [0.0, -1.5, 1e3, 2024.0, 0.125];
        let name = |seed: &mut u64| NAMES[roll(seed) as usize % NAMES.len()].to_string();
        if depth == 0 || roll(seed) % 3 == 0 {
            let op = OPS[roll(seed) as usize % OPS.len()];
            let args = match roll(seed) % 3 {
                0 => Vec::new(),
                1 => vec![Arg::Name(name(seed))],
                _ => vec![
                    Arg::Num(NUMS[roll(seed) as usize % NUMS.len()]),
                    Arg::Name(name(seed)),
                ],
            };
            let operand = if op.is_membership() {
                Operand::List(vec![Arg::Name(name(seed)), Arg::Num(2024.0)])
            } else if roll(seed) % 2 == 0 {
                Operand::Num(NUMS[roll(seed) as usize % NUMS.len()])
            } else {
                Operand::Name(name(seed))
            };
            let metric = ["papers", "field_score", "_x-y"][roll(seed) as usize % 3].to_string();
            return Expr::Clause(Clause {
                call: Call { metric, args },
                op,
                operand,
            });
        }
        let kids = 2 + roll(seed) % 2;
        let items = (0..kids).map(|_| rand_expr(seed, depth - 1)).collect();
        match roll(seed) % 3 {
            0 => Expr::And(items),
            1 => Expr::Or(items),
            _ => Expr::Not(Box::new(rand_expr(seed, depth - 1))),
        }
    }
}
