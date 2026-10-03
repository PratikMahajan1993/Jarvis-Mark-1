from app.features.sheets import FEATURE


def test_sheets_registered():
    assert FEATURE.id == "sheets"
