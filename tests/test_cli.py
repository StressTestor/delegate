import json
import pytest
from delegate.cli import parse_args, build_brief_from_args


def test_parse_minimal_task():
    args = parse_args(["implement foo"])
    assert args.task == "implement foo"
    assert args.type == "code-gen"
    assert args.read == []
    assert args.write == []

def test_parse_with_read_and_write_csv():
    args = parse_args([
        "implement foo",
        "--read", "src/a.ts,src/b.ts",
        "--write", "src/a.ts",
        "--accept", "tests pass",
    ])
    assert args.read == ["src/a.ts", "src/b.ts"]
    assert args.write == ["src/a.ts"]
    assert args.accept == ["tests pass"]

def test_parse_accept_repeatable():
    args = parse_args([
        "x",
        "--accept", "a",
        "--accept", "b",
    ])
    assert args.accept == ["a", "b"]

def test_parse_provider_override():
    args = parse_args(["x", "--provider", "gemini-pro"])
    assert args.provider == "gemini-pro"

def test_parse_bulk():
    args = parse_args([
        "--type", "bulk",
        "--files", "src/**/*.ts",
        "--task", "add jsdoc",
        "--concurrency", "5",
    ])
    assert args.type == "bulk"
    assert args.files == "src/**/*.ts"
    assert args.task_template == "add jsdoc"
    assert args.concurrency == 5

def test_parse_brief_file():
    args = parse_args(["--brief", "b.json"])
    assert args.brief == "b.json"

def test_build_brief_from_args_sets_commit_format_default():
    args = parse_args(["implement foo", "--write", "src/foo.ts"])
    brief = build_brief_from_args(args)
    assert "implement foo" in brief["commit_format"] or brief["commit_format"].startswith("feat")
