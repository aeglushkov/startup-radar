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
