import json

from pydantic import BaseModel

from poe.output import _format_dict_human, _format_human, _format_json, human_formatter, render


class _UnregModel(BaseModel):
    name: str


class SampleModel(BaseModel):
    name: str
    value: int
    optional: str | None = None


class TestFormatJson:
    def test_dict(self):
        result = _format_json({"key": "val"})
        assert json.loads(result) == {"key": "val"}

    def test_pydantic_model(self):
        m = SampleModel(name="test", value=42)
        result = _format_json(m)
        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42

    def test_pydantic_excludes_none(self):
        m = SampleModel(name="test", value=1, optional=None)
        result = _format_json(m)
        assert "optional" not in result

    def test_pydantic_list(self):
        items = [SampleModel(name="a", value=1), SampleModel(name="b", value=2)]
        result = _format_json(items)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "a"
        assert parsed[1]["name"] == "b"

    def test_list_excludes_none(self):
        items = [SampleModel(name="a", value=1, optional=None)]
        result = _format_json(items)
        parsed = json.loads(result)
        assert "optional" not in parsed[0]


class TestFormatDictHuman:
    def test_simple_dict(self):
        result = _format_dict_human({"name": "test", "value": 42})
        assert "name: test" in result
        assert "value: 42" in result

    def test_nested_dict(self):
        result = _format_dict_human({"outer": {"inner": "val"}})
        assert "outer:" in result
        assert "  inner: val" in result

    def test_list_of_strings(self):
        result = _format_dict_human(["a", "b", "c"])
        assert "- a" in result
        assert "- b" in result

    def test_list_of_dicts(self):
        result = _format_dict_human([{"k": "v"}, {"k": "v2"}])
        assert "k: v" in result
        assert "k: v2" in result

    def test_scalar(self):
        result = _format_dict_human("hello")
        assert result == "hello"


class TestHumanFormatter:
    def test_registered_formatter(self):
        @human_formatter(SampleModel)
        def fmt(m):
            return f"{m.name} = {m.value}"

        result = _format_human(SampleModel(name="x", value=5))
        assert result == "x = 5"

    def test_registered_formatter_list(self):
        # Uses the formatter registered above
        items = [SampleModel(name="a", value=1), SampleModel(name="b", value=2)]
        result = _format_human(items)
        assert "a = 1" in result
        assert "b = 2" in result

    def test_dict_fallback(self):
        result = _format_human({"key": "val"})
        assert "key: val" in result


class TestRender:
    def test_render_defaults_to_human(self, capsys):
        from poe.models.build.build import MutationResult

        data = MutationResult(status="ok")
        render(data)
        out = capsys.readouterr().out
        assert "status: ok" in out

    def test_render_json_mode_outputs_json(self, capsys):
        from poe.models.build.build import MutationResult

        data = MutationResult(status="ok")
        render(data, json_mode=True)
        out = capsys.readouterr().out
        assert '"status"' in out

    def test_render_json_dict(self, capsys):
        render({"x": 1}, json_mode=True)
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"x": 1}

    def test_render_json_model(self, capsys):
        render(SampleModel(name="test", value=99), json_mode=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["name"] == "test"

    def test_render_human_dict(self, capsys):
        render({"key": "val"})
        captured = capsys.readouterr()
        assert "key: val" in captured.out

    def test_render_human_model(self, capsys):
        render(SampleModel(name="hi", value=7))
        captured = capsys.readouterr()
        assert "hi" in captured.out

    def test_render_unregistered_model_uses_dict_fallback(self, capsys):
        class Unregistered(BaseModel):
            foo: str = "bar"
            count: int = 42

        render(Unregistered(foo="baz", count=99))
        out = capsys.readouterr().out
        assert "foo: baz" in out
        assert "count: 99" in out

    def test_render_unicode_characters(self, capsys):
        render({"name": "Black Mórrigan", "league": "Cola küsst Orange"})
        captured = capsys.readouterr()
        assert "Mórrigan" in captured.out
        assert "küsst" in captured.out


# ── render() invariants: structure stable across runs ───────────────────────


class TestRenderStructureInvariants:
    def test_same_model_produces_same_output(self, capsys):
        a = SampleModel(name="x", value=42)
        b = SampleModel(name="x", value=42)
        render(a, json_mode=True)
        out_a = capsys.readouterr().out
        render(b, json_mode=True)
        out_b = capsys.readouterr().out
        assert out_a == out_b

    def test_json_mode_outputs_parseable_json(self, capsys):
        render(SampleModel(name="x", value=1), json_mode=True)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["name"] == "x"
        assert parsed["value"] == 1

    def test_human_mode_is_not_json_for_dict(self, capsys):
        render({"only_field": 42}, json_mode=False)
        out = capsys.readouterr().out.strip()
        assert "only_field: 42" in out

    def test_render_writes_trailing_newline(self, capsys):
        render({"x": 1}, json_mode=True)
        out = capsys.readouterr().out
        assert out.endswith("\n")

    def test_json_mode_excludes_none_for_model(self, capsys):
        render(SampleModel(name="x", value=1, optional=None), json_mode=True)
        out = capsys.readouterr().out
        assert "optional" not in out

    def test_list_of_models_json_mode(self, capsys):
        items = [SampleModel(name="a", value=1), SampleModel(name="b", value=2)]
        render(items, json_mode=True)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_list_of_models_human_mode_unregistered_uses_dict_fallback(self, capsys):
        render([_UnregModel(name="a"), _UnregModel(name="b")], json_mode=False)
        out = capsys.readouterr().out
        assert "a" in out
        assert "b" in out

    def test_empty_dict_renders_empty_string_with_newline(self, capsys):
        render({}, json_mode=False)
        out = capsys.readouterr().out
        assert out == "\n"

    def test_empty_list_json_mode(self, capsys):
        render([], json_mode=True)
        out = capsys.readouterr().out
        assert json.loads(out) == []
