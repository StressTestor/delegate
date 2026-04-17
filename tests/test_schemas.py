import json
from importlib.resources import files
from jsonschema import Draft202012Validator

SCHEMAS = ["brief.schema.json", "log.schema.json", "error.schema.json"]

def test_all_schemas_load_and_are_valid_json_schema():
    for name in SCHEMAS:
        raw = files("delegate.schemas").joinpath(name).read_text()
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)

def test_brief_schema_accepts_canonical_example():
    schema = json.loads(files("delegate.schemas").joinpath("brief.schema.json").read_text())
    canonical = {
        "brief_version": "1",
        "task": "Implement foo()",
        "read": ["src/foo.ts"],
        "write_allowed": ["src/foo.ts"],
        "new_file_patterns": ["src/**/*.test.ts"],
        "do_not_touch": [".env*"],
        "acceptance": ["tests pass"],
        "commit_format": "feat(foo): add",
        "constraints": [],
        "escape_hatch": "If blocked, print BLOCKER: and exit non-zero.",
    }
    Draft202012Validator(schema).validate(canonical)

def test_brief_schema_rejects_missing_required():
    schema = json.loads(files("delegate.schemas").joinpath("brief.schema.json").read_text())
    bad = {"brief_version": "1", "task": "x"}
    errs = list(Draft202012Validator(schema).iter_errors(bad))
    assert errs, "expected validation errors for missing required fields"
