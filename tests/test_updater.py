"""Software update against local git repositories (no network)."""
import subprocess
import sys

import pytest

from app.updater import UpdateError, Updater, parse_version

OK = [sys.executable, "-c", "pass"]
FAIL = [sys.executable, "-c", "import sys; sys.exit('no space left')"]


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, name, tag=None):
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)
    if tag:
        git(repo, "tag", tag)


@pytest.fixture()
def origin(tmp_path):
    """Upstream with the releases v0.0.1 and v0.0.2 and one commit after v0.0.2."""
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q", "-b", "main")
    commit(src, "requirements.txt", "v0.0.1")
    commit(src, "b", "v0.0.2")
    commit(src, "c")
    return src


def clone(origin, tmp_path, ref):
    dst = tmp_path / "panel"
    git(tmp_path, "clone", "-q", str(origin), str(dst))
    if ref != "main":
        git(dst, "checkout", "-q", ref)
    return dst


def release(tag):
    return lambda url: {"tag_name": tag, "body": "notes", "html_url": url}


def test_parse_version():
    assert parse_version("v1.2.10") == (1, 2, 10) > parse_version("1.2.9")
    assert parse_version("0.0.3-4-gabc") == (0, 0, 3)
    assert parse_version("main") is None


def test_update_to_latest_release(origin, tmp_path):
    repo = clone(origin, tmp_path, "v0.0.1")
    up = Updater(repo, fetch_json=release("v0.0.2"), pip_command=OK)
    assert up.supported and up.installed() == "0.0.1"
    check = up.check()
    assert (check.current, check.latest, check.available) == ("0.0.1", "v0.0.2", True)
    up.install("v0.0.2")
    assert up.installed() == "0.0.2"
    assert up.check().available is False


def test_checkout_of_main_is_never_updated_backwards(origin, tmp_path):
    repo = clone(origin, tmp_path, "main")
    up = Updater(repo, fetch_json=release("v0.0.2"), pip_command=OK)
    assert up.installed().startswith("0.0.2-1-g")
    assert up.check().available is False


def test_failed_pip_goes_back(origin, tmp_path):
    repo = clone(origin, tmp_path, "main")
    commit(origin, "d", "v0.0.3")
    up = Updater(repo, fetch_json=release("v0.0.3"), pip_command=FAIL)
    assert up.check().available
    with pytest.raises(UpdateError, match="no space left"):
        up.install("v0.0.3")
    assert git(repo, "symbolic-ref", "--short", "HEAD") == "main"      # back on the branch


def test_local_changes_and_bad_input(origin, tmp_path):
    repo = clone(origin, tmp_path, "v0.0.1")
    (repo / "b").write_text("changed")
    git(repo, "add", "b")
    up = Updater(repo, fetch_json=release("v0.0.2"), pip_command=OK)
    with pytest.raises(UpdateError, match="local changes"):
        up.install("v0.0.2")
    with pytest.raises(UpdateError, match="unexpected release tag"):
        up.install("--upload-pack=evil")
    with pytest.raises(UpdateError, match="unexpected release tag"):
        Updater(repo, fetch_json=release("nightly")).check()

    def offline(url):
        raise OSError("Network is unreachable")
    with pytest.raises(UpdateError, match="unreachable"):
        Updater(repo, fetch_json=offline).check()


def test_not_a_git_checkout(tmp_path):
    up = Updater(tmp_path)
    assert not up.supported
    with pytest.raises(UpdateError):
        up.check()
