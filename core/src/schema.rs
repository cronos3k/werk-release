//! A JSON Schema (draft 2020-12) validator for exactly the subset the werk
//! schemas use, and no more.
//!
//! Stage 1 decision 12 says the schemas never `$ref` each other across files:
//! each is standalone so a validator needs no resolver. That is what makes a
//! purpose-built validator honest here — the whole schema is one document and
//! the keyword set is closed. Measured over `spec/schemas/*.json`, the
//! keywords in use are exactly:
//!
//!   $defs $id $ref $schema additionalProperties allOf anyOf const default
//!   description enum exclusiveMinimum format if items maxItems maxLength
//!   maximum minItems minLength minProperties minimum pattern
//!   patternProperties properties propertyNames required then title type
//!   uniqueItems $comment
//!
//! Every assertion in that list is implemented. `format` is an ANNOTATION in
//! draft 2020-12 and is treated as one (not asserted) — stated rather than
//! silently skipped. An assertion keyword that is NOT in the list is reported
//! as an error against the schema itself, because a validator that ignores a
//! constraint it does not understand is worse than no validator.

use crate::regexlite::Regex;
use serde_json::Value;
use std::cell::{Cell, RefCell};
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaError {
    /// JSON Pointer into the instance, e.g. `/nodes/3/versions/0/note`.
    pub instance_path: String,
    /// JSON Pointer into the schema, e.g. `/$defs/version/required`.
    pub schema_path: String,
    pub message: String,
}

impl std::fmt::Display for SchemaError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let at = if self.instance_path.is_empty() { "/" } else { &self.instance_path };
        write!(f, "{at}: {} (schema {})", self.message, self.schema_path)
    }
}

/// Keywords that carry no assertion. Anything outside this set and the
/// implemented set is flagged.
const ANNOTATIONS: &[&str] = &[
    "$schema", "$id", "$comment", "$anchor", "title", "description", "default",
    "examples", "deprecated", "readOnly", "writeOnly", "format", "$defs",
];

const IMPLEMENTED: &[&str] = &[
    "$ref", "type", "const", "enum", "required", "properties",
    "additionalProperties", "patternProperties", "propertyNames", "items",
    "minItems", "maxItems", "uniqueItems", "minProperties", "maxProperties",
    "minLength", "maxLength", "pattern", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "allOf", "anyOf",
    "oneOf", "not", "if", "then", "else",
];

/// How deep `check` may recurse before it stops and says so. The schemas this
/// crate ships nest a dozen levels; a JSON instance cannot nest deeper than
/// the parser's own limit. The bound exists for the schema a PACKAGE supplies
/// (SPEC.md section 2.2): `{"$ref": "#"}` is four tokens and, without a
/// bound, a stack overflow in whoever opens the file.
const MAX_DEPTH: usize = 200;

/// A `pattern` is for short strings: ids, hashes, paths, dates. The matcher is
/// a backtracking one, so a subject this long under a package-supplied pattern
/// is refused by name instead of evaluated.
const MAX_PATTERN_SUBJECT: usize = 1 << 16;

pub struct Validator {
    root: Value,
    cache: RefCell<HashMap<String, Regex>>,
    /// See [`Validator::lenient`].
    lenient: bool,
    depth: Cell<usize>,
}

impl Validator {
    pub fn new(schema_text: &str) -> Result<Validator, String> {
        let root: Value =
            serde_json::from_str(schema_text).map_err(|e| format!("schema is not JSON: {e}"))?;
        Ok(Validator::from_value(root))
    }

    pub fn from_value(root: Value) -> Validator {
        Validator { root, cache: RefCell::new(HashMap::new()), lenient: false, depth: Cell::new(0) }
    }

    /// For a schema this crate did not ship. A keyword outside the implemented
    /// set is then NOT reported once per instance it is met on — a package's
    /// own schema may use one legitimately, and a page of identical complaints
    /// is noise. The caller asks [`Validator::unknown_keywords`] once instead
    /// and says, once, which constraints were not checked. The strict default
    /// stays right for the schemas in `spec/`, where an unknown keyword is a
    /// bug in this validator's keyword list.
    pub fn lenient(mut self) -> Validator {
        self.lenient = true;
        self
    }

    /// Every keyword in the schema that this validator neither implements nor
    /// knows as an annotation, each once, sorted.
    pub fn unknown_keywords(&self) -> Vec<String> {
        fn walk(v: &Value, depth: usize, out: &mut std::collections::BTreeSet<String>) {
            let map = match v {
                Value::Object(m) if depth < MAX_DEPTH => m,
                _ => return,
            };
            for (k, sub) in map {
                match k.as_str() {
                    // Maps from a NAME to a schema: the keys are not keywords.
                    "properties" | "patternProperties" | "$defs" | "definitions"
                    | "dependentSchemas" => {
                        if let Value::Object(m) = sub {
                            for s in m.values() {
                                walk(s, depth + 1, out);
                            }
                        }
                    }
                    // Lists of schemas.
                    "allOf" | "anyOf" | "oneOf" | "prefixItems" => {
                        if let Value::Array(a) = sub {
                            for s in a {
                                walk(s, depth + 1, out);
                            }
                        }
                    }
                    // One schema.
                    "items" | "additionalProperties" | "propertyNames" | "not" | "if"
                    | "then" | "else" | "contains" | "unevaluatedProperties"
                    | "unevaluatedItems" => walk(sub, depth + 1, out),
                    // Values that are data, not schemas.
                    _ => {}
                }
                if k == "definitions" {
                    continue; // draft-07 spelling of $defs: a container, harmless
                }
                if !ANNOTATIONS.contains(&k.as_str()) && !IMPLEMENTED.contains(&k.as_str()) {
                    out.insert(k.clone());
                }
            }
        }
        let mut out = std::collections::BTreeSet::new();
        walk(&self.root, 0, &mut out);
        out.into_iter().collect()
    }

    pub fn validate(&self, instance: &Value) -> Vec<SchemaError> {
        let mut errs = Vec::new();
        self.check(&self.root, instance, "", "", &mut errs);
        errs
    }

    fn regex(&self, pat: &str) -> Option<Regex> {
        if let Some(r) = self.cache.borrow().get(pat) {
            return Some(r.clone());
        }
        let r = Regex::new(pat).ok()?;
        self.cache.borrow_mut().insert(pat.to_string(), r.clone());
        Some(r)
    }

    fn resolve<'a>(&'a self, pointer: &str) -> Option<&'a Value> {
        // Only same-document pointers exist in this format (decision 12).
        let p = pointer.strip_prefix('#')?;
        if p.is_empty() {
            return Some(&self.root);
        }
        self.root.pointer(&unescape_pointer(p))
    }

    #[allow(clippy::only_used_in_recursion)]
    fn check(&self, schema: &Value, inst: &Value, ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        let depth = self.depth.get();
        if depth >= MAX_DEPTH {
            push(errs, ipath, spath,
                 "schema recursion is deeper than 200 levels (a `$ref` cycle?); not followed further");
            return;
        }
        self.depth.set(depth + 1);
        self.check_inner(schema, inst, ipath, spath, errs);
        self.depth.set(depth);
    }

    #[allow(clippy::only_used_in_recursion)]
    fn check_inner(&self, schema: &Value, inst: &Value, ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        // A boolean schema: true accepts everything, false rejects everything.
        if let Some(b) = schema.as_bool() {
            if !b {
                push(errs, ipath, spath, "schema is `false`: nothing is valid here");
            }
            return;
        }
        let map = match schema.as_object() {
            Some(m) => m,
            None => {
                push(errs, ipath, spath, "schema is neither an object nor a boolean");
                return;
            }
        };

        for k in map.keys() {
            if self.lenient {
                break;
            }
            if !ANNOTATIONS.contains(&k.as_str()) && !IMPLEMENTED.contains(&k.as_str()) {
                push(errs, ipath, &format!("{spath}/{k}"),
                     &format!("schema uses keyword `{k}`, which this validator does not implement"));
            }
        }

        if let Some(r) = map.get("$ref").and_then(Value::as_str) {
            match self.resolve(r) {
                Some(target) => self.check(target, inst, ipath, &pointer_of(r), errs),
                None => push(errs, ipath, &format!("{spath}/$ref"),
                             &format!("unresolvable $ref `{r}`")),
            }
        }

        if let Some(t) = map.get("type") {
            if !type_ok(t, inst) {
                push(errs, ipath, &format!("{spath}/type"),
                     &format!("expected type {}, got {}", t, type_name(inst)));
                // Keep going: sibling keywords may still say something useful,
                // but skip the ones that would be nonsense for this type.
            }
        }

        if let Some(c) = map.get("const") {
            if !json_equal(c, inst) {
                push(errs, ipath, &format!("{spath}/const"),
                     &format!("must be exactly {c}, got {inst}"));
            }
        }

        if let Some(Value::Array(opts)) = map.get("enum") {
            if !opts.iter().any(|o| json_equal(o, inst)) {
                push(errs, ipath, &format!("{spath}/enum"),
                     &format!("{inst} is not one of the {} permitted values", opts.len()));
            }
        }

        match inst {
            Value::String(s) => self.check_string(map, s, ipath, spath, errs),
            Value::Number(_) => self.check_number(map, inst, ipath, spath, errs),
            Value::Array(a) => self.check_array(map, a, ipath, spath, errs),
            Value::Object(o) => self.check_object(map, o, ipath, spath, errs),
            _ => {}
        }

        if let Some(Value::Array(subs)) = map.get("allOf") {
            for (i, sub) in subs.iter().enumerate() {
                self.check(sub, inst, ipath, &format!("{spath}/allOf/{i}"), errs);
            }
        }
        if let Some(Value::Array(subs)) = map.get("anyOf") {
            // Report only the failure of the whole branch set: a list of every
            // alternative's complaints is noise, not a diagnosis.
            let any = subs.iter().any(|sub| {
                let mut probe = Vec::new();
                self.check(sub, inst, ipath, "", &mut probe);
                probe.is_empty()
            });
            if !any {
                push(errs, ipath, &format!("{spath}/anyOf"),
                     &format!("matches none of the {} alternatives", subs.len()));
            }
        }
        if let Some(Value::Array(subs)) = map.get("oneOf") {
            let n = subs.iter().filter(|sub| {
                let mut probe = Vec::new();
                self.check(sub, inst, ipath, "", &mut probe);
                probe.is_empty()
            }).count();
            if n != 1 {
                push(errs, ipath, &format!("{spath}/oneOf"),
                     &format!("must match exactly one alternative, matched {n}"));
            }
        }
        if let Some(sub) = map.get("not") {
            let mut probe = Vec::new();
            self.check(sub, inst, ipath, "", &mut probe);
            if probe.is_empty() {
                push(errs, ipath, &format!("{spath}/not"), "must NOT match this schema");
            }
        }

        if let Some(cond) = map.get("if") {
            let mut probe = Vec::new();
            self.check(cond, inst, ipath, "", &mut probe);
            let branch = if probe.is_empty() { "then" } else { "else" };
            if let Some(sub) = map.get(branch) {
                self.check(sub, inst, ipath, &format!("{spath}/{branch}"), errs);
            }
        }
    }

    fn check_string(&self, map: &serde_json::Map<String, Value>, s: &str, ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        // JSON Schema counts CHARACTERS (code points), not bytes.
        let n = s.chars().count() as u64;
        if let Some(v) = map.get("minLength").and_then(Value::as_u64) {
            if n < v {
                push(errs, ipath, &format!("{spath}/minLength"),
                     &format!("string of {n} characters is shorter than the required {v}"));
            }
        }
        if let Some(v) = map.get("maxLength").and_then(Value::as_u64) {
            if n > v {
                push(errs, ipath, &format!("{spath}/maxLength"),
                     &format!("string of {n} characters is longer than the permitted {v}"));
            }
        }
        if let Some(p) = map.get("pattern").and_then(Value::as_str) {
            if s.len() > MAX_PATTERN_SUBJECT {
                push(errs, ipath, &format!("{spath}/pattern"),
                     &format!("a string of {} bytes is too long to evaluate a pattern on (limit {MAX_PATTERN_SUBJECT}); refused, not guessed", s.len()));
                return;
            }
            match self.regex(p) {
                Some(re) => {
                    if !re.is_match(s) {
                        push(errs, ipath, &format!("{spath}/pattern"),
                             &format!("\"{}\" does not match /{p}/", truncate(s)));
                    }
                }
                None => push(errs, ipath, &format!("{spath}/pattern"),
                             &format!("pattern /{p}/ is outside the supported regex subset")),
            }
        }
    }

    fn check_number(&self, map: &serde_json::Map<String, Value>, inst: &Value, ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        let x = match inst.as_f64() {
            Some(x) => x,
            None => return,
        };
        for (kw, ok, word) in [
            ("minimum", (|a: f64, b: f64| a >= b) as fn(f64, f64) -> bool, "at least"),
            ("maximum", |a, b| a <= b, "at most"),
            ("exclusiveMinimum", |a, b| a > b, "greater than"),
            ("exclusiveMaximum", |a, b| a < b, "less than"),
        ] {
            if let Some(v) = map.get(kw).and_then(Value::as_f64) {
                if !ok(x, v) {
                    push(errs, ipath, &format!("{spath}/{kw}"),
                         &format!("{x} must be {word} {v}"));
                }
            }
        }
        if let Some(v) = map.get("multipleOf").and_then(Value::as_f64) {
            if v > 0.0 && (x / v).fract().abs() > 1e-9 {
                push(errs, ipath, &format!("{spath}/multipleOf"),
                     &format!("{x} is not a multiple of {v}"));
            }
        }
    }

    fn check_array(&self, map: &serde_json::Map<String, Value>, a: &[Value], ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        if let Some(v) = map.get("minItems").and_then(Value::as_u64) {
            if (a.len() as u64) < v {
                push(errs, ipath, &format!("{spath}/minItems"),
                     &format!("{} items is fewer than the required {v}", a.len()));
            }
        }
        if let Some(v) = map.get("maxItems").and_then(Value::as_u64) {
            if (a.len() as u64) > v {
                push(errs, ipath, &format!("{spath}/maxItems"),
                     &format!("{} items is more than the permitted {v}", a.len()));
            }
        }
        if map.get("uniqueItems").and_then(Value::as_bool) == Some(true) {
            for i in 0..a.len() {
                for j in (i + 1)..a.len() {
                    if json_equal(&a[i], &a[j]) {
                        push(errs, ipath, &format!("{spath}/uniqueItems"),
                             &format!("items {i} and {j} are duplicates"));
                    }
                }
            }
        }
        if let Some(items) = map.get("items") {
            for (i, item) in a.iter().enumerate() {
                self.check(items, item, &format!("{ipath}/{i}"), &format!("{spath}/items"), errs);
            }
        }
    }

    fn check_object(&self, map: &serde_json::Map<String, Value>, o: &serde_json::Map<String, Value>, ipath: &str, spath: &str, errs: &mut Vec<SchemaError>) {
        if let Some(Value::Array(req)) = map.get("required") {
            for r in req {
                if let Some(name) = r.as_str() {
                    if !o.contains_key(name) {
                        push(errs, ipath, &format!("{spath}/required"),
                             &format!("missing required property `{name}`"));
                    }
                }
            }
        }
        if let Some(v) = map.get("minProperties").and_then(Value::as_u64) {
            if (o.len() as u64) < v {
                push(errs, ipath, &format!("{spath}/minProperties"),
                     &format!("{} properties is fewer than the required {v}", o.len()));
            }
        }
        if let Some(v) = map.get("maxProperties").and_then(Value::as_u64) {
            if (o.len() as u64) > v {
                push(errs, ipath, &format!("{spath}/maxProperties"),
                     &format!("{} properties is more than the permitted {v}", o.len()));
            }
        }

        let props = map.get("properties").and_then(Value::as_object);
        let pat_props = map.get("patternProperties").and_then(Value::as_object);

        if let Some(pn) = map.get("propertyNames") {
            for key in o.keys() {
                self.check(pn, &Value::String(key.clone()),
                           &format!("{ipath}/{}", escape_token(key)),
                           &format!("{spath}/propertyNames"), errs);
            }
        }

        for (key, val) in o {
            let child_ipath = format!("{ipath}/{}", escape_token(key));
            let mut matched = false;
            if let Some(p) = props.and_then(|p| p.get(key)) {
                matched = true;
                self.check(p, val, &child_ipath,
                           &format!("{spath}/properties/{}", escape_token(key)), errs);
            }
            if let Some(pp) = pat_props {
                for (pat, sub) in pp {
                    if self.regex(pat).map_or(false, |r| r.is_match(key)) {
                        matched = true;
                        self.check(sub, val, &child_ipath,
                                   &format!("{spath}/patternProperties/{}", escape_token(pat)), errs);
                    }
                }
            }
            if !matched {
                match map.get("additionalProperties") {
                    Some(Value::Bool(false)) => push(
                        errs, &child_ipath, &format!("{spath}/additionalProperties"),
                        &format!("property `{key}` is not permitted here")),
                    Some(sub) if !sub.is_boolean() => self.check(
                        sub, val, &child_ipath, &format!("{spath}/additionalProperties"), errs),
                    _ => {}
                }
            }
        }
    }
}

fn push(errs: &mut Vec<SchemaError>, ipath: &str, spath: &str, msg: &str) {
    errs.push(SchemaError {
        instance_path: ipath.to_string(),
        schema_path: if spath.is_empty() { "/".into() } else { spath.to_string() },
        message: msg.to_string(),
    });
}

fn truncate(s: &str) -> String {
    if s.chars().count() <= 60 {
        s.to_string()
    } else {
        let head: String = s.chars().take(57).collect();
        format!("{head}...")
    }
}

fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "boolean",
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() { "integer" } else { "number" }
        }
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

fn type_ok(t: &Value, inst: &Value) -> bool {
    match t {
        Value::String(s) => one_type(s, inst),
        Value::Array(a) => a.iter().filter_map(Value::as_str).any(|s| one_type(s, inst)),
        _ => false,
    }
}

fn one_type(t: &str, inst: &Value) -> bool {
    match t {
        "null" => inst.is_null(),
        "boolean" => inst.is_boolean(),
        "string" => inst.is_string(),
        "array" => inst.is_array(),
        "object" => inst.is_object(),
        "number" => inst.is_number(),
        // JSON Schema: a number with a zero fractional part IS an integer.
        "integer" => match inst {
            Value::Number(n) => n.is_i64() || n.is_u64()
                || n.as_f64().map_or(false, |f| f.fract() == 0.0),
            _ => false,
        },
        _ => false,
    }
}

/// Equality for `const`/`enum`/`uniqueItems`. Numbers compare by VALUE, so
/// `const: 1.0` accepts `1` — which is what JSON Schema says and what stops a
/// writer that emits `1` from failing `units_per_meter`.
pub fn json_equal(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => match (x.as_f64(), y.as_f64()) {
            (Some(x), Some(y)) => x == y,
            _ => x == y,
        },
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(a, b)| json_equal(a, b))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len()
                && x.iter().all(|(k, v)| y.get(k).map_or(false, |w| json_equal(v, w)))
        }
        _ => a == b,
    }
}

fn escape_token(s: &str) -> String {
    s.replace('~', "~0").replace('/', "~1")
}

fn unescape_pointer(p: &str) -> String {
    // serde_json's `pointer` wants the raw pointer including leading '/'.
    p.to_string()
}

fn pointer_of(reference: &str) -> String {
    reference.trim_start_matches('#').to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn required_and_additional() {
        let v = Validator::from_value(json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["a"],
            "properties": {"a": {"type": "integer", "minimum": 1}}
        }));
        assert!(v.validate(&json!({"a": 3})).is_empty());
        assert_eq!(v.validate(&json!({})).len(), 1);
        assert_eq!(v.validate(&json!({"a": 3, "b": 1})).len(), 1);
        assert_eq!(v.validate(&json!({"a": 0})).len(), 1);
    }

    #[test]
    fn const_number_equality_ignores_spelling() {
        let v = Validator::from_value(json!({"const": 1.0}));
        assert!(v.validate(&json!(1)).is_empty());
        assert!(v.validate(&json!(1.0)).is_empty());
        assert_eq!(v.validate(&json!(2)).len(), 1);
    }

    #[test]
    fn if_then_is_law_five() {
        // The real shape from manifest.schema.json: measured/inferred REQUIRE
        // input_hash and an ordered input_files list.
        let v = Validator::from_value(json!({
            "type": "object",
            "allOf": [{
                "if": {"properties": {"epistemic": {"enum": ["measured", "inferred"]}},
                       "required": ["epistemic"]},
                "then": {"required": ["input_hash", "input_files"]}
            }]
        }));
        assert!(v.validate(&json!({"epistemic": "authored"})).is_empty());
        assert_eq!(v.validate(&json!({"epistemic": "measured"})).len(), 2);
        assert!(v.validate(&json!({
            "epistemic": "inferred", "input_hash": "x", "input_files": []
        })).is_empty());
    }

    #[test]
    fn local_ref_resolves() {
        let v = Validator::from_value(json!({
            "type": "array",
            "items": {"$ref": "#/$defs/sha256"},
            "$defs": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}
        }));
        assert!(v.validate(&json!([ "a".repeat(64) ])).is_empty());
        assert_eq!(v.validate(&json!([ "zz" ])).len(), 1);
    }

    #[test]
    fn a_ref_cycle_in_a_supplied_schema_is_reported_not_followed_forever() {
        // Four tokens, and without the depth bound a stack overflow in whoever
        // opens the package that ships them.
        let v = Validator::from_value(json!({"$ref": "#"})).lenient();
        let errs = v.validate(&json!({"a": 1}));
        assert_eq!(errs.len(), 1);
        assert!(errs[0].message.contains("recursion"), "{}", errs[0].message);
        // And the validator is usable afterwards: the depth counter unwound.
        assert_eq!(v.validate(&json!(1)).len(), 1);
    }

    #[test]
    fn lenient_mode_lists_unknown_keywords_once_instead_of_per_instance() {
        let schema = json!({
            "type": "array",
            "items": {"type": "object", "dependentRequired": {"a": ["b"]},
                      "properties": {"dependentRequired": {"type": "integer"}}}
        });
        let strict = Validator::from_value(schema.clone());
        assert_eq!(strict.validate(&json!([{}, {}, {}])).len(), 3);
        let lenient = Validator::from_value(schema).lenient();
        assert!(lenient.validate(&json!([{}, {}, {}])).is_empty());
        // A PROPERTY called `dependentRequired` is a name, not a keyword.
        assert_eq!(lenient.unknown_keywords(), vec!["dependentRequired".to_string()]);
    }

    #[test]
    fn unimplemented_keyword_is_reported_not_ignored() {
        let v = Validator::from_value(json!({"dependentRequired": {"a": ["b"]}}));
        let errs = v.validate(&json!({"a": 1}));
        assert_eq!(errs.len(), 1);
        assert!(errs[0].message.contains("dependentRequired"));
    }
}
