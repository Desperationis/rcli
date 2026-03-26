from rcli.enums import CHOICE, SCENES


def _all_values(cls):
    """Return all integer attribute values of a class (excluding dunder attrs)."""
    return {
        name: val
        for name, val in vars(cls).items()
        if not name.startswith("_") and isinstance(val, int)
    }


def test_choice_values_are_unique():
    vals = _all_values(CHOICE)
    assert len(vals) == len(set(vals.values())), (
        f"Duplicate CHOICE values: {vals}"
    )


def test_scenes_values_are_unique():
    vals = _all_values(SCENES)
    assert len(vals) == len(set(vals.values())), (
        f"Duplicate SCENES values: {vals}"
    )


def test_choice_no_bitmask_collisions():
    vals = list(_all_values(CHOICE).values())
    for i, a in enumerate(vals):
        for b in vals[i + 1 :]:
            if a != 0 and b != 0:
                assert a & b == 0, f"CHOICE bitmask collision: {a:#09b} & {b:#09b}"


def test_scenes_no_bitmask_collisions():
    vals = list(_all_values(SCENES).values())
    for i, a in enumerate(vals):
        for b in vals[i + 1 :]:
            assert a & b == 0, f"SCENES bitmask collision: {a:#09b} & {b:#09b}"


def test_choice_upload_exists():
    assert hasattr(CHOICE, "UPLOAD")
    assert CHOICE.UPLOAD == 0b0100000


def test_scenes_upload_exists():
    assert hasattr(SCENES, "UPLOAD")
    assert SCENES.UPLOAD == 0b100000


def test_scenes_remote_picker_exists():
    assert hasattr(SCENES, "REMOTE_PICKER")
    assert SCENES.REMOTE_PICKER == 0b1000000
