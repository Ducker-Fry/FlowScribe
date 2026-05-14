from flowscribe.gui.__main__ import main


def test_gui_entrypoint_self_test_exits_successfully() -> None:
    assert main(["--self-test"]) == 0
