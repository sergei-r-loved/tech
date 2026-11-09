import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quarantine_plugine.server.app import app

client = TestClient(app)

BASE_URL = "http://127.0.0.1:8000"

DEFAULT_TESTS = """
    from random import randint

    import pytest

    def test_stable():
        pass

    def test_failed():
        pytest.fail("Incorrect result")

    def test_flaky_quarantined():
        pytest.fail("Incorrect result")
    """

PARAMETRIZED_TESTS = """
    import pytest

    @pytest.mark.parametrize("case", ["a", "b"])
    def test_p(case):
        pytest.fail("Incorrect result")
    """

TESTS_FOR_REPORT = [
    """
    def test_stable():
        pass
    """,
    """
    import pytest
    @pytest.fixture
    def failed_fixture():
        raise RuntimeError("стенд недоступен")

    def test_stable(failed_fixture):
        pass
    """,
    """
    import pytest
    @pytest.mark.skip()
    def test_stable():
        pass
    """,
    """
    import pytest
    @pytest.fixture
    def failed_fixture():
        raise RuntimeError("стенд недоступен")

    def test_stable(failed_fixture):
        pass
    """,
    """
    import pytest
    def test_stable():
        pytest.skip()
    """,
    """
    def test_stable():
        raise RuntimeError("стенд недоступен")
    """,
    """
    def test_stable():
        pass
    """,
    """
    def test_stable():
        raise RuntimeError("стенд недоступен")
    """,
    """
    import pytest
    @pytest.fixture
    def failed_fixture():
        yield
        raise RuntimeError("стенд недоступен")

    def test_stable(failed_fixture):
        pass
    """,
    """
    import pytest
    @pytest.mark.xfail(reason="JIRA-123")
    def test_stable():
        raise RuntimeError("известный баг")
    """,
]


def _read_real_conftest():
    path_to_conftest = Path(__file__).resolve().parent.parent / "plugin.py"
    return path_to_conftest.read_text("utf-8")


@pytest.fixture
def make_quarantine_file(pytester, request):
    """Create quarantine.txt file"""
    func_name = request.node.originalname

    def _wrap(test_name: str | None = None):
        name = test_name or "test_flaky_quarantined"
        pytester.makefile(
            ".txt",
            quarantine=f"{func_name}.py::" + name,
        )

    return _wrap


def test_quarantined(pytester, make_quarantine_file):
    """Make sure that our plugin works."""

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file()
    # Create a temporary test file
    pytester.makepyfile(DEFAULT_TESTS)

    result = pytester.runpytest()
    result.assert_outcomes(passed=1, xfailed=1, failed=1)


def test_outcomes_code(pytester, make_quarantine_file):

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file()
    # Create a temporary test file
    pytester.makepyfile(
        """
        from random import randint

        import pytest

        def test_stable():
            pass

        def test_flaky_quarantined():
            pass
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, xpassed=1)
    assert result.ret == pytest.ExitCode.OK


def test_passed_quarantined(pytester, make_quarantine_file):

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file()
    # Create a temporary test file
    pytester.makepyfile(
        """
        from random import randint

        import pytest

        def test_stable():
            pass

        def test_flaky_quarantined():
            pytest.fail("Incorrect result")
        """
    )

    result = pytester.runpytest()
    result.assert_outcomes(passed=1, xfailed=1)
    assert result.ret == pytest.ExitCode.OK


def test_empty_quarantined(pytester):

    pytester.makeconftest(_read_real_conftest())
    # Make empty qurantined file
    pytester.makefile(
        ".txt",
        quarantine="",
    )
    # Create a temporary test file
    pytester.makepyfile(DEFAULT_TESTS)

    result = pytester.runpytest()
    result.assert_outcomes(passed=1, xfailed=0, failed=2)


def test_no_quarantined_file(pytester):

    pytester.makeconftest(_read_real_conftest())
    # Create a temporary test file
    pytester.makepyfile(DEFAULT_TESTS)

    result = pytester.runpytest()
    result.assert_outcomes(passed=1, xfailed=0, failed=2)


def test_parametrized_base_quarantined(pytester, make_quarantine_file):
    """test_p в файле накрывает все параметры: test_p[a] и test_p[b]."""

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file("test_p")
    pytester.makepyfile(PARAMETRIZED_TESTS)

    result = pytester.runpytest()
    result.assert_outcomes(xfailed=2)


def test_parametrized_single_case_quarantined(pytester, make_quarantine_file):
    """test_p[a] в файле накрывает только свой параметр."""

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file("test_p[a]")
    pytester.makepyfile(PARAMETRIZED_TESTS)

    result = pytester.runpytest()
    result.assert_outcomes(xfailed=1, failed=1)


def test_unknown_nodeid_warns(pytester, make_quarantine_file):
    """Файл собран, а теста в нём нет — опечатка или тест удалён: предупреждение."""

    pytester.makeconftest(_read_real_conftest())
    make_quarantine_file("test_typo")
    pytester.makepyfile(
        """
        def test_stable():
            pass
        """
    )

    result = pytester.runpytest()
    result.assert_outcomes(passed=1, warnings=1)
    result.stdout.fnmatch_lines(["*quarantine: *::test_typo не найден*"])


def test_not_collected_file_no_warning(pytester):
    """Тест из другого файла не выбран в этом запуске — молчим."""

    pytester.makeconftest(_read_real_conftest())
    pytester.makefile(".txt", quarantine="test_other.py::test_flaky")
    pytester.makepyfile(
        """
        def test_stable():
            pass
        """
    )

    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    result.stdout.no_fnmatch_line("*не найден*")


# параметризируем, по таблице, читаем файл смотрим что там наши тесты
@pytest.mark.parametrize(
    "test, in_quarantine, status, quarantined_flag",
    [
        pytest.param(TESTS_FOR_REPORT[0], None, "passed", False, id="passed_stable"),
        pytest.param(
            TESTS_FOR_REPORT[1],
            None,
            "error",
            False,
            id="failed_fixture_no_quarantined",
        ),
        pytest.param(
            TESTS_FOR_REPORT[2], None, "skipped", False, id="pytest_mark_skipped"
        ),
        pytest.param(
            TESTS_FOR_REPORT[3],
            "test_stable",
            "error",
            True,
            id="failed_fixture_xfail_test",
        ),
        pytest.param(
            TESTS_FOR_REPORT[4], None, "skipped", False, id="pytest_skip_inside_test"
        ),
        pytest.param(
            TESTS_FOR_REPORT[5], "test_stable", "failed", True, id="xfail_hided_fail"
        ),
        pytest.param(
            TESTS_FOR_REPORT[6], "test_stable", "passed", True, id="xpassed_to_pass"
        ),
        pytest.param(TESTS_FOR_REPORT[7], "", "failed", False, id="just_failed_test"),
        pytest.param(TESTS_FOR_REPORT[8], "", "passed", False, id="failed_in_teardown"),
        pytest.param(
            TESTS_FOR_REPORT[9], None, "failed", False, id="code_xfail_not_quarantined"
        ),
    ],
)
def test_report_from_plugin(
    pytester, make_quarantine_file, test, in_quarantine, status, quarantined_flag
):

    pytester.makeconftest(_read_real_conftest())
    pytester.makepyfile(test)
    make_quarantine_file(in_quarantine if in_quarantine else None)
    # monkeypatch.setenv("RUN_ID", "run-42")

    pytester.runpytest("--flaky-report=r.json")
    path_to_report = pytester.path / "r.json"
    report = json.loads(path_to_report.read_text())
    assert len(report["tests"]) == 1
    assert report["tests"][0]["status"] == status
    assert report["tests"][0]["quarantined"] == quarantined_flag


def test_report_format(pytester, monkeypatch):
    pytester.makeconftest(_read_real_conftest())
    pytester.makepyfile(DEFAULT_TESTS)
    run_id = "run-42"
    repo = "my_quarantine_repo"
    commit = "dhasda33434hash"
    branch = "tests_branch"
    ci_url = "https://github.com/some_url_bla"
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("REPO", repo)
    monkeypatch.setenv("GIT_COMMIT", commit)
    monkeypatch.setenv("BRANCH", branch)
    monkeypatch.setenv("CI_URL", ci_url)

    pytester.runpytest("--flaky-report=r.json")
    path_to_report = pytester.path / "r.json"
    report = json.loads(path_to_report.read_text())
    assert report["run_id"] == run_id
    assert report["repo"] == repo
    assert report["commit"] == commit
    assert report["branch"] == branch
    assert report["ci_url"] == ci_url
    assert len(report["tests"]) > 0


def test_report_unexisting_folder(pytester):

    pytester.makeconftest(_read_real_conftest())
    pytester.makepyfile("""def test_stable(): pass""")

    result = pytester.runpytest("--flaky-report=nope/r.json")
    assert result.ret == pytest.ExitCode.OK
    result.stdout.fnmatch_lines(["*flaky-report: не записал*"])


def test_no_report_if_no_flag(pytester):

    pytester.makeconftest(_read_real_conftest())
    pytester.makepyfile("""def test_stable(): pass""")

    pytester.runpytest()
    assert not (pytester.path / "r.json").exists()


@pytest.mark.skip(
    "Нужен фикс, пока не додумался как отправлять не на реальный сервер и честные результаты иметь"
)
def test_send_report_if_flag(pytester):

    pytester.makeconftest(_read_real_conftest())
    pytester.makepyfile("""def test_stable(): pass""")

    pytester.runpytest(f"--send-report={BASE_URL}/runs", "--flaky-report=r.json")

    report = json.loads((pytester.path / "r.json").read_text("utf-8"))
    stored = client.get(BASE_URL.format(run_id=report["run_id"])).json()

    # assert stored == report
    print(stored)
