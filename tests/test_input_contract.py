from subsim.config import KEYMAP


def test_quit_key_does_not_overlap_heading_controls() -> None:
    heading_keys = {
        KEYMAP["heading_left"],
        KEYMAP["heading_right"],
        KEYMAP["heading_fine_left"],
        KEYMAP["heading_fine_right"],
    }
    assert KEYMAP["quit"] not in heading_keys
