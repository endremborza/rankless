//! The expression language of the table: `where=` narrows a cohort with clauses over metric calls
//! combined by `and`, `or`, `not` and parentheses (precedence parentheses > not > and > or),
//! `sort=` names one call, `metrics=` a list of calls. Parsing is syntactic only; what a metric
//! is, whether an operator fits its value type and what a name resolves to is settled by the
//! binder against the registry.

use std::fmt;

use serde::Serialize;

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

struct Parser {
    tokens: Vec<(usize, Token)>,
    pos: usize,
    end: usize,
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

impl Parser {
    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos).map(|(_, t)| t)
    }

    fn at(&self) -> usize {
        self.tokens.get(self.pos).map_or(self.end, |(i, _)| *i)
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

    fn expr(&mut self) -> Result<Expr, ParseError> {
        let mut items = vec![self.and_expr()?];
        while self.peek() == Some(&Token::Or) {
            self.pos += 1;
            items.push(self.and_expr()?);
        }
        Ok(flatten(items, Expr::Or))
    }

    fn and_expr(&mut self) -> Result<Expr, ParseError> {
        let mut items = vec![self.not_expr()?];
        while self.peek() == Some(&Token::And) {
            self.pos += 1;
            items.push(self.not_expr()?);
        }
        Ok(flatten(items, Expr::And))
    }

    fn not_expr(&mut self) -> Result<Expr, ParseError> {
        if self.peek() == Some(&Token::Not) {
            self.pos += 1;
            return Ok(Expr::Not(Box::new(self.not_expr()?)));
        }
        self.primary()
    }

    fn primary(&mut self) -> Result<Expr, ParseError> {
        if self.peek() == Some(&Token::LParen) {
            self.pos += 1;
            let e = self.expr()?;
            self.expect(Token::RParen, "expected )")?;
            return Ok(e);
        }
        Ok(Expr::Clause(self.clause()?))
    }

    fn clause(&mut self) -> Result<Clause, ParseError> {
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
    let e = p.expr()?;
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

impl Parser {
    fn new(s: &str) -> Result<Self, ParseError> {
        Ok(Self {
            tokens: tokenize(s)?,
            pos: 0,
            end: s.len(),
        })
    }
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
                    match b.get(i) {
                        None => {
                            return Err(ParseError {
                                at: start,
                                msg: "unterminated string",
                            })
                        }
                        Some(&ch) if ch == quote => {
                            i += 1;
                            break;
                        }
                        Some(&b'\\') => {
                            i += 1;
                            if let Some(&ch) = b.get(i) {
                                text.push(ch as char);
                                i += 1;
                            }
                        }
                        Some(_) => {
                            let ch = s[i..].chars().next().unwrap();
                            text.push(ch);
                            i += ch.len_utf8();
                        }
                    }
                }
                Token::Str(text)
            }
            b'0'..=b'9' | b'.' => {
                while i < b.len() && (b[i].is_ascii_digit() || b[i] == b'.') {
                    i += 1;
                }
                if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
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
                let n: f64 = s[start..i].parse().map_err(|_| ParseError {
                    at: start,
                    msg: "bad number",
                })?;
                Token::Num(n)
            }
            b'-' if b.get(i + 1).is_some_and(u8::is_ascii_digit) => {
                i += 1;
                while i < b.len() && (b[i].is_ascii_digit() || b[i] == b'.') {
                    i += 1;
                }
                let n: f64 = s[start..i].parse().map_err(|_| ParseError {
                    at: start,
                    msg: "bad number",
                })?;
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
            _ => {
                return Err(ParseError {
                    at: start,
                    msg: "unexpected character",
                })
            }
        };
        out.push((start, tok));
    }
    Ok(out)
}

fn flatten(mut items: Vec<Expr>, make: fn(Vec<Expr>) -> Expr) -> Expr {
    if items.len() == 1 {
        items.pop().unwrap()
    } else {
        make(items)
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

#[cfg(test)]
mod tests {
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
            roundtrip("country=hun and city!=budapest and (papers>=500 or impact_score>=20)"),
            "country = hun and city != budapest and (papers >= 500 or impact_score >= 20)"
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
}
