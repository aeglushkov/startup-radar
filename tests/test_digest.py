from radar.digest import compose

C = {"name": "Acme <X>", "url": "https://acme.io", "one_liner": "Does acme.", "tags": ["ai"]}


def test_empty_day():
    msgs = compose([], "1 sources checked · 0 new · failures: none")
    assert len(msgs) == 1
    assert "Nothing new today." in msgs[0]
    assert "failures: none" in msgs[0]


def test_grouped_and_escaped():
    msgs = compose([("Y Combinator", [C])], "footer")
    assert len(msgs) == 1
    m = msgs[0]
    assert "<b>Y Combinator</b>" in m
    assert '<a href="https://acme.io">Acme &lt;X&gt;</a>' in m
    assert "Does acme." in m and "#ai" in m


def test_splits_long_digests():
    many = [dict(C, name=f"Company {i}", url=f"https://c{i}.io") for i in range(200)]
    msgs = compose([("YC", many)], "footer")
    assert len(msgs) > 1
    assert all(len(m) <= 4000 for m in msgs)
    assert "footer" in msgs[-1]


def test_url_escaped_in_href():
    c = dict(C, url="https://acme.io/?a=1&b=2")
    msgs = compose([("YC", [c])], "footer")
    assert 'href="https://acme.io/?a=1&amp;b=2"' in msgs[0]


def test_pathological_fields_stay_sendable():
    cases = [
        dict(C, one_liner="x" * 5000),
        dict(C, name="N" * 9000),
        dict(C, url="https://acme.io/?q=" + "y" * 9000),
        dict(C, tags=["t" * 5000] * 10),
    ]
    msgs = compose([("S" * 5000, cases)], "footer")
    assert all(0 < len(m) <= 4000 for m in msgs)
    for m in msgs:
        assert m.count("<a ") == m.count("</a>")  # no mid-tag splits
    assert "footer" in msgs[-1]


def test_description_fallback():
    c = {"name": "Beta", "url": "https://beta.io", "one_liner": None,
         "tags": [], "description": "Raw desc"}
    msgs = compose([("YC", [c])], "footer")
    assert "Raw desc" in msgs[0]
