"""Package smoke test (task 1.3 AC: package importable, version present).

Note: pytest does not collect tests from conftest.py, so the import smoke is
an explicit test file — this also keeps ``uv run pytest`` exit 0 on a tree
that only contains the skeleton.
"""

import mcp_jira


def test_package_imports_with_version() -> None:
    assert isinstance(mcp_jira.__version__, str)
    assert mcp_jira.__version__
