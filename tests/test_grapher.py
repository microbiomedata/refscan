from refscan.grapher import load_template


def test_load_template():
    template = load_template(r"templates/graph.template.html")
    assert isinstance(template, str)
    assert len(template) > 0
