from quarantine_plugine.server.models.create_run import RunRequest, RunTest


class Repository:
    def __init__(self, connection) -> None:
        self.conn = connection

    def save_run(self, run: RunRequest) -> bool:
        query = """
            INSERT INTO run (run_id, repo, commit, started_at, branch, ci_url)
            VALUES (%(run_id)s, %(repo)s, %(commit)s, %(started_at)s, %(branch)s, %(ci_url)s)
            ON CONFLICT (run_id) DO NOTHING
            RETURNING run_id
        """
        with self.conn.transaction(), self.conn.cursor() as cur:
            result = cur.execute(
                query,
                (run.model_dump(exclude={"tests"})),
            ).fetchone()
            if not result:
                return False
            tests = []
            for t in run.tests:
                test = t.model_dump()
                test["run_id"] = run.run_id
                tests.append(test)
            cur.executemany(
                "INSERT INTO result (run_id, nodeid, status, quarantined, duration, traceback) values (%(run_id)s, %(nodeid)s, %(status)s, %(quarantined)s, %(duration)s, %(traceback)s)",
                tests,
            )
        return True

    def get_run_by_run_id(self, run_id: str) -> RunRequest | None:
        query_run = """
        SELECT run_id, repo, commit, branch, started_at, ci_url FROM run WHERE run_id = %(run_id)s"""
        query_result = """
        SELECT * FROM result WHERE run_id = %(run_id)s ORDER BY nodeid
        """
        with self.conn.cursor() as cur:
            run = cur.execute(
                query_run,
                {"run_id": run_id},
            ).fetchone()
            if run is None:
                return None
            result = cur.execute(
                query_result,
                {"run_id": run_id},
            ).fetchall()
            tests = [RunTest.model_validate(test) for test in result]
            run["tests"] = tests
            run = RunRequest.model_validate(run)
            return run
