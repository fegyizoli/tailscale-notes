import pytest
import os

from scripts import taildrop

try:
    import grp
    import getpass
    from types import SimpleNamespace
    ON_WIN = False
except ModuleNotFoundError:
    ON_WIN = True

# test print_error() with mocked print_usage()
# all error codes has to be covered, print_usage() for missing parameters
@pytest.fixture(autouse=True)
def mock_print_usage(monkeypatch):
    called = {"was_called": False}
    def fake_print_usage():
        called["was_called"] = True
    monkeypatch.setattr(taildrop, "print_usage", fake_print_usage)
    return called

def test_none_code_do_nothing(capsys, mock_print_usage):
    taildrop.print_error(taildrop.ec.NONE)
    out = capsys.readouterr().out
    assert out == ""
    assert not mock_print_usage["was_called"]

@pytest.mark.parametrize("code, expected_text, calls_print_usage", [
    (taildrop.ec.MISSING_PARAMETER, "Missing parameter!", True),
    (taildrop.ec.INVALID_PARAMETER, "Invalid parameter!", True),
    (taildrop.ec.OPERATOR_SET_FAIL, "Failed to set current user as operator!", False),
    (taildrop.ec.NON_OPERATOR_RECEIVE_FAIL, "Failed to initiate non-operator receive!", False),
    (taildrop.ec.RECEIVE_FAIL, "Failed to receive!", False),
    (taildrop.ec.SEND_FAIL, "Failed to send!", False),
    (taildrop.ec.EMPTY_FILELIST, "No files selected!", False),
    (taildrop.ec.NOTHING_SELECTED, "No device selected!", False),
    (taildrop.ec.STATUS_FAIL, "Failed to get tailscale status!", False)
])
def test_error_messages(capsys, mock_print_usage, code, expected_text, calls_print_usage):
    taildrop.print_error(code)
    out = capsys.readouterr().out

    assert f"[{int(code)}]" in out
    assert expected_text in out

    assert mock_print_usage["was_called"] == calls_print_usage

# test cmd_run()
class DummyCompletedProcess:
    def __init__(self, stdout=b"", stderr=b""):
        self.stdout = stdout
        self.stderr = stderr

# 1. executes a subpprocess, return True
def test_cmd_run_success(monkeypatch, capsys):
    def mock_subprocess_run(cmd, stdout, stderr, check):
        return DummyCompletedProcess(stdout=b"Ran successfully.")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r,o = taildrop.cmd_run(["tailscale", "status"])
    capture = capsys.readouterr()
    assert r is True
    assert "Ran successfully." in o
    assert "Output:" in capture.out

# 2. exception happens during subprocess.run, return False
def test_cmd_run_exception(monkeypatch, capsys):
    def mock_subprocess_run(cmd, stdout, stderr, check):
        raise OSError("Expect exception")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r,o = taildrop.cmd_run(["resonance", "cascade"])
    capture = capsys.readouterr()
    assert r is False
    assert "Exception occured" in capture.out

# 3. error occured, return False
def test_cmd_run_stderr_no_bypass(monkeypatch, capsys):
    def mock_subprocess_run(cmd, stdout, stderr, check):
        return DummyCompletedProcess(stdout=b"test chamber", stderr=b"resonance cascade")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r, o = taildrop.cmd_run(["gibberish"])
    capture = capsys.readouterr()
    assert r is False
    assert "Error:" in capture.out
    assert "resonance cascade" in capture.out

# 4. error occured bypass set to True, return True
def test_cmd_run_stderr_bypass(monkeypatch, capsys):

    def mock_subprocess_run(cmd, stdout, stderr, check):
        return DummyCompletedProcess(stdout=b"test chamber", stderr=b"resonance cascade")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r, o = taildrop.cmd_run(["gibberish"], bypass=True)
    capture = capsys.readouterr()
    assert r is True
    assert "resonance cascade" in capture.out
    assert "Error:" not in capture.out

# test can_use_tailscale() -- WINDOWS
# 1. prints 'Hello windows!' execute 'tailscale status' successfully
@pytest.mark.skipif(ON_WIN is False, reason="Windows test case")
def test_can_use_tailscale_win_success(monkeypatch, capsys):
    def mock_subprocess_run(cmd, stdout, stderr, check):
        return DummyCompletedProcess(stdout="tailscale status executed")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r = taildrop.can_use_tailscale(ON_WIN)
    capture = capsys.readouterr()
    assert r is True
    assert "Hello windows!" in capture.out

# 2. prints 'Hello windows!' execute 'tailscale status' with exception
@pytest.mark.skipif(ON_WIN is False, reason="Windows test case")
def test_can_use_tailscale_win_exception(monkeypatch, capsys):
    def mock_subprocess_run(cmd, stdout, stderr, check):
        raise OSError("Expect exception")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r = taildrop.can_use_tailscale(ON_WIN)
    capture = capsys.readouterr()
    assert r is False
    assert "Hello windows!" in capture.out

# test can_use_tailscale() -- NOT-WINDOWS
# need mocks: getpass.getuser(), os.geteuid(), grp.getgrall()
# 1. user is root, return successfully
@pytest.mark.skipif(ON_WIN is True, reason="Linux test case")
def test_can_use_tailscale_linux_root_success(monkeypatch):
    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(os, "geteuid", lambda: 0)

    r = taildrop.can_use_tailscale(ON_WIN)
    assert r is True

# 2. user is not root, part of tailscale group, success
@pytest.mark.skipif(ON_WIN is True, reason="Linux test case")
def test_can_use_tailscale_linux_non_root_grouped_success(monkeypatch):

    # use SimpleNamespace for minimal grp databases
    mock_groups = [
        SimpleNamespace(gr_name="tailscale"),
        SimpleNamespace(gr_name="users")
    ]

    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(grp, "getgrall", lambda: mock_groups)

    def mock_subprocess_run(cmd, stdout, stderr, check):
        return DummyCompletedProcess(stdout="tailscale status executed")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r = taildrop.can_use_tailscale(ON_WIN)
    assert r is True

# 3. user is not root, part of tailscale group, exception happens
@pytest.mark.skipif(ON_WIN is True, reason="Linux test case")
def test_can_use_tailscale_linux_non_root_grouped_exception(monkeypatch):
    # use SimpleNamespace for minimal grp databases
    mock_groups = [
        SimpleNamespace(gr_name="tailscale"),
        SimpleNamespace(gr_name="users")
    ]

    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(grp, "getgrall", lambda: mock_groups)

    def mock_subprocess_run(cmd, stdout, stderr, check):
        raise OSError("Exception occured")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r = taildrop.can_use_tailscale(ON_WIN)
    assert r is False

# 4. user is not root, not part of tailscale group, exception
@pytest.mark.skipif(ON_WIN is True, reason="Linux test case")
def test_can_use_tailscale_linux_non_root_non_grouped(monkeypatch):
    # use SimpleNamespace for minimal grp databases
    mock_groups = [
        SimpleNamespace(gr_name="users")
    ]

    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(grp, "getgrall", lambda: mock_groups)

    def mock_subprocess_run(cmd, stdout, stderr, check):
        raise OSError("Unknown command")
    monkeypatch.setattr(taildrop.subprocess, "run", mock_subprocess_run)

    r = taildrop.can_use_tailscale(ON_WIN)
    assert r is False

# test show_choices()
# 1. options list empty, return empty list
def test_show_choices_el_ret_el(monkeypatch):
    keys = ["ESC"]
    def mock_getkey():
        return keys.pop(0)

    monkeypatch.setattr(taildrop, "getkey", mock_getkey)
    opts = []
    result = taildrop.show_choices("title", opts)
    assert result == []

# 2. option list len 1, proceed as not multiple, up, space, enter, return same list
def test_show_choices_l1_nonmulti_u_s_ent_ret_l1(monkeypatch):
    keys = ["UP", "SPACE", "ENTER"]
    def mock_getkey():
        return keys.pop(0)

    monkeypatch.setattr(taildrop, "getkey", mock_getkey)
    opts = ["a"]
    result = taildrop.show_choices("title", opts, multiple=False)
    assert result == ["a"]

# 3. option list len 1, proceed as not multiple, up, space, esc, return empty list
def test_show_choices_l1_nomulti_u_s_esc_ret_l1(monkeypatch):
    keys = ["UP", "SPACE", "ESC"]
    def mock_getkey():
        return keys.pop(0)

    monkeypatch.setattr(taildrop, "getkey", mock_getkey)
    opts = ["a"]
    result = taildrop.show_choices("title", opts, multiple=False)
    assert result == []

# 4. option list len 3, not multiple, all, enter, return index 0 single element in list
# 5. option list len 3, none, esc, return empty list
# 6. option list len 3, none, up, down, enter, return [index 0]
# 7. option list len 3, up, up, down, enter, return [index 2]
# 8. option list len 3, down, up, down, enter, return [index 1]
# 9. option list len 3, all, esc, return empty list
# 10. option list len 3, n, enter, return empty list
# 11. option list len 3, down, space, enter, return [index 1]
# 12. option list len 3, space, down, space, enter, return list [index 0, index 1]
# 13. option list len 3, a, enter, return list [index 0, index 1, index 2]
# 14. option list len 3, a, space, enter, return list [index 1, index 2]


# test select_device()


# test main()

