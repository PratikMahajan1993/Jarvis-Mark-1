from app.core import features as f


def test_register_and_publish():
    f.register_feature(f.Feature(id="t"))
    assert any(x.id == "t" for x in f.features())
    f.publish("x", {"a": 1})
