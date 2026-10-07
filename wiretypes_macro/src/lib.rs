use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::{format_ident, quote, ToTokens};
use syn::{
    parse_macro_input, parse_quote,
    punctuated::Punctuated,
    visit_mut::{self, VisitMut},
    Attribute, Expr, ExprLit, Fields, Generics, Ident, Item, Lit, Meta, MetaNameValue, Path,
    StaticMutability, Token, TypePath,
};

/// Rewrites every `HashMap`/`HashSet` path in a type to the std one, which schemars describes;
/// any other map with that name (hashbrown's) serializes the same way.
struct StdMaps(bool);

impl VisitMut for StdMaps {
    fn visit_type_path_mut(&mut self, tp: &mut TypePath) {
        visit_mut::visit_type_path_mut(self, tp);
        let first = tp.path.segments.first().map(|s| s.ident.to_string());
        let last = tp.path.segments.last().unwrap();
        let is_map = last.ident == "HashMap" || last.ident == "HashSet";
        if is_map && tp.qself.is_none() && first.as_deref() != Some("std") {
            let (ident, args) = (&last.ident, &last.arguments);
            tp.path = parse_quote!(::std::collections::#ident #args);
            self.0 = true;
        }
    }
}

/// Derives `JsonSchema` for a struct or enum crossing a language boundary and registers it with
/// `wiretypes`. On a type alias it registers the aliased type under the alias name; an alias
/// over a non-std map also gets an `{Alias}Wire` twin over the std one, which a field of the
/// alias type names in `#[schemars(with = "..Wire")]`. On a `const` or an immutable `static`
/// whose type is `Serialize`, it registers the value, which the targets spell as a literal.
///
/// Goes above the item's `#[derive(..)]`, whose `Serialize`/`Deserialize` decide the contract:
/// `Serialize` describes what Rust sends, `Deserialize` alone what it accepts.
#[proc_macro_attribute]
pub fn wire(attr: TokenStream, item: TokenStream) -> TokenStream {
    if !attr.is_empty() {
        return error(TokenStream2::from(attr), "#[wire] takes no arguments");
    }
    match parse_macro_input!(item as Item) {
        Item::Struct(mut s) => {
            let contract = match contract(&s.attrs) {
                Ok(c) => c,
                Err(e) => return error(&s.ident, e),
            };
            annotate_fields(&mut s.fields);
            prepend_derive(&mut s.attrs);
            let extra = registration(&s.ident, &s.generics, &contract);
            quote!(#s #extra).into()
        }
        Item::Enum(mut e) => {
            let contract = match contract(&e.attrs) {
                Ok(c) => c,
                Err(msg) => return error(&e.ident, msg),
            };
            e.variants
                .iter_mut()
                .for_each(|v| annotate_fields(&mut v.fields));
            prepend_derive(&mut e.attrs);
            let extra = registration(&e.ident, &e.generics, &contract);
            quote!(#e #extra).into()
        }
        Item::Type(t) if t.generics.params.is_empty() => {
            let mut ty = (*t.ty).clone();
            let mut maps = StdMaps(false);
            maps.visit_type_mut(&mut ty);
            if !maps.0 {
                let submit = submit(&t.ident, &t.ident, quote!(registration));
                return quote!(#t #submit).into();
            }
            let (vis, twin) = (&t.vis, format_ident!("{}Wire", t.ident));
            let submit = submit(&twin, &t.ident, quote!(map_registration));
            quote! {
                #t
                #[doc(hidden)]
                #vis type #twin = #ty;
                #submit
            }
            .into()
        }
        Item::Const(c) => {
            let submit = const_submit(&c.ident, &c.attrs);
            quote!(#c #submit).into()
        }
        Item::Static(s) if matches!(s.mutability, StaticMutability::None) => {
            let submit = const_submit(&s.ident, &s.attrs);
            quote!(#s #submit).into()
        }
        other => error(
            other,
            "#[wire] goes on a struct, an enum, a non-generic type alias, a const or a static",
        ),
    }
}

fn contract(attrs: &[Attribute]) -> Result<Ident, &'static str> {
    let mut derived = Vec::new();
    for attr in attrs.iter().filter(|a| a.path().is_ident("derive")) {
        if let Ok(paths) = attr.parse_args_with(Punctuated::<Path, Token![,]>::parse_terminated) {
            derived.extend(
                paths
                    .into_iter()
                    .filter_map(|p| p.segments.last().map(|s| s.ident.to_string())),
            );
        }
    }
    let has = |name: &str| derived.iter().any(|d| d == name);
    match (has("Serialize"), has("Deserialize")) {
        (true, _) => Ok(Ident::new("Serialize", proc_macro2::Span::call_site())),
        (false, true) => Ok(Ident::new("Deserialize", proc_macro2::Span::call_site())),
        (false, false) => Err("#[wire] needs a serde Serialize or Deserialize derive below it"),
    }
}

fn prepend_derive(attrs: &mut Vec<Attribute>) {
    attrs.insert(
        0,
        parse_quote!(#[derive(::wiretypes::schemars::JsonSchema)]),
    );
    attrs.insert(
        1,
        parse_quote!(#[schemars(crate = "::wiretypes::schemars")]),
    );
}

fn annotate_fields(fields: &mut Fields) {
    for field in fields.iter_mut() {
        let spelled = |name: &str| -> String {
            field
                .attrs
                .iter()
                .filter(|a| a.path().is_ident(name))
                .map(|a| a.to_token_stream().to_string().replace(' ', ""))
                .collect()
        };
        let (serde, schemars) = (spelled("serde"), spelled("schemars"));
        if !schemars.contains("with=") {
            let mut ty = field.ty.clone();
            let mut maps = StdMaps(false);
            maps.visit_type_mut(&mut ty);
            if maps.0 {
                let with = ty.to_token_stream().to_string();
                field.attrs.push(parse_quote!(#[schemars(with = #with)]));
            }
        }
        if serde.contains("skip_serializing_if=\"Option::is_none\"") {
            field
                .attrs
                .push(parse_quote!(#[schemars(transform = ::wiretypes::never_null)]));
        }
    }
}

fn registration(ident: &Ident, generics: &Generics, contract: &Ident) -> TokenStream2 {
    let mut bounded = generics.clone();
    bounded
        .make_where_clause()
        .predicates
        .push(parse_quote!(Self: ::wiretypes::schemars::JsonSchema));
    let (impl_generics, ty_generics, where_clause) = bounded.split_for_impl();
    let wire_impl = quote! {
        impl #impl_generics ::wiretypes::Wire for #ident #ty_generics #where_clause {
            const CONTRACT: ::wiretypes::Contract = ::wiretypes::Contract::#contract;
        }
    };
    match generics.params.is_empty() {
        true => {
            let submit = submit(ident, ident, quote!(registration));
            quote!(#wire_impl #submit)
        }
        false => wire_impl,
    }
}

fn submit(ty: &Ident, name: &Ident, constructor: TokenStream2) -> TokenStream2 {
    let name = name.to_string();
    quote! {
        ::wiretypes::inventory::submit! {
            ::wiretypes::#constructor::<#ty>(::core::module_path!(), #name, ::core::line!())
        }
    }
}

fn const_submit(ident: &Ident, attrs: &[Attribute]) -> TokenStream2 {
    let (name, doc) = (ident.to_string(), doc(attrs));
    quote! {
        ::wiretypes::inventory::submit! {
            ::wiretypes::WireConst {
                module: ::core::module_path!(),
                name: #name,
                line: ::core::line!(),
                doc: #doc,
                value: || ::wiretypes::serde_json::to_value(&#ident),
            }
        }
    }
}

/// The `///` lines of an item, one space of indent dropped as rustdoc does.
fn doc(attrs: &[Attribute]) -> String {
    let lines: Vec<String> = attrs
        .iter()
        .filter_map(|a| match &a.meta {
            Meta::NameValue(MetaNameValue {
                path,
                value:
                    Expr::Lit(ExprLit {
                        lit: Lit::Str(s), ..
                    }),
                ..
            }) if path.is_ident("doc") => Some(s.value()),
            _ => None,
        })
        .map(|l| l.strip_prefix(' ').map(str::to_string).unwrap_or(l))
        .collect();
    lines.join("\n").trim().to_string()
}

fn error(tokens: impl ToTokens, msg: &str) -> TokenStream {
    syn::Error::new_spanned(tokens, msg)
        .to_compile_error()
        .into()
}
