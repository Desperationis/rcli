from unittest.mock import patch, MagicMock

from rcli.rcli import main


def test_cli_end_not_called_when_init_fails():
    """If cursedcli.__init__ raises, cli.end() should not be called (no NameError)."""
    with patch("rcli.rcli.docopt", return_value={"-v": False, "--clear-cache": False, "<remote>": "b2:"}):
        with patch("rcli.rcli.cursedcli", side_effect=RuntimeError("init failed")):
            # Should not raise NameError; the RuntimeError is caught internally
            main()


def test_keyboard_interrupt_produces_no_stderr(capsys):
    """KeyboardInterrupt should exit cleanly with no stderr output."""
    mock_cli = MagicMock()
    mock_cli.main.side_effect = KeyboardInterrupt

    with patch("rcli.rcli.docopt", return_value={"-v": False, "--clear-cache": False, "<remote>": "b2:"}):
        with patch("rcli.rcli.cursedcli", return_value=mock_cli):
            main()

    captured = capsys.readouterr()
    assert captured.err == ""


def test_exception_prints_traceback_to_stderr(capsys):
    """A generic exception should print its traceback to stderr."""
    mock_cli = MagicMock()
    mock_cli.main.side_effect = ValueError("something broke")

    with patch("rcli.rcli.docopt", return_value={"-v": False, "--clear-cache": False, "<remote>": "b2:"}):
        with patch("rcli.rcli.cursedcli", return_value=mock_cli):
            main()

    captured = capsys.readouterr()
    assert "ValueError" in captured.err
    assert "something broke" in captured.err


def test_no_remote_passes_none_to_cursedcli():
    """Calling main with no remote should pass remote=None to cursedcli."""
    mock_cli = MagicMock()

    with patch("rcli.rcli.docopt", return_value={"-v": False, "--clear-cache": False, "<remote>": None}):
        with patch("rcli.rcli.cursedcli", return_value=mock_cli) as mock_cls:
            main()

    mock_cls.assert_called_once_with(None)
