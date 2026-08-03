from app.tools import execute_approved_patch, patch_preview, repo_list_files, repo_read_file


def test_fixture_tools_are_scoped():
    files = repo_list_files("python-average-empty")
    assert "calculator.py" in files
    assert "tests/test_calculator.py" in files
    assert "return sum(values)" in repo_read_file("python-average-empty", "calculator.py")


def test_patch_preview_is_minimal():
    diff = patch_preview("python-average-empty")
    assert "--- a/calculator.py" in diff
    assert "+    if not values:" in diff


def test_approved_patch_runs_real_pytest():
    diff, result = execute_approved_patch("python-average-empty")
    assert diff
    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert "passed" in str(result["output"])


def test_path_traversal_is_rejected():
    try:
        repo_read_file("python-average-empty", "../python-slug/slug.py")
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("path traversal must be rejected")

