-- Ручные данные для шага 3, часть 1 (запрос флаки). Повторный запуск безопасен: сначала удаляет свои строки.
BEGIN;
DELETE FROM result WHERE run_id LIKE 'seed-%';
DELETE FROM run    WHERE run_id LIKE 'seed-%';

INSERT INTO run (run_id, repo, "commit", branch, started_at, ci_url) VALUES
  ('seed-r1', 'shop/api', 'c1', 'main', now() - interval '1 day',   NULL),
  ('seed-r2', 'shop/api', 'c1', 'main', now() - interval '1 day',   NULL),
  ('seed-r3', 'shop/api', 'c2', 'main', now() - interval '2 days',  NULL),
  ('seed-r4', 'shop/api', 'c2', 'main', now() - interval '2 days',  NULL),
  ('seed-r5', 'shop/api', 'c3', 'main', now() - interval '20 days', NULL),
  ('seed-r6', 'shop/api', 'c3', 'main', now() - interval '20 days', NULL),
  ('seed-r7', 'shop/web', 'c1', 'main', now() - interval '1 day',   NULL),
  ('seed-r8', 'shop/web', 'c1', 'main', now() - interval '1 day',   NULL);

INSERT INTO result (run_id, nodeid, status, quarantined, duration, traceback) VALUES
  -- c1 (r1, r2)
  ('seed-r1', 'tests/test_auth.py::test_login',      'passed',  false, 0.12, NULL),
  ('seed-r2', 'tests/test_auth.py::test_login',      'failed',  false, 0.15, 'AssertionError'),
  ('seed-r1', 'tests/test_cart.py::test_add',        'passed',  false, 0.05, NULL),
  ('seed-r2', 'tests/test_cart.py::test_add',        'skipped', false, 0.00, NULL),
  ('seed-r1', 'tests/test_search.py::test_query',    'passed',  false, 0.30, NULL),
  ('seed-r2', 'tests/test_search.py::test_query',    'passed',  false, 0.31, NULL),
  ('seed-r1', 'tests/test_flaky_known.py::test_ws',  'passed',  true,  1.20, NULL),
  ('seed-r2', 'tests/test_flaky_known.py::test_ws',  'failed',  true,  1.40, 'TimeoutError'),
  ('seed-r1', 'tests/test_stable.py::test_health',   'passed',  false, 0.01, NULL),
  ('seed-r2', 'tests/test_stable.py::test_health',   'passed',  false, 0.01, NULL),
  ('seed-r1', 'tests/test_broken.py::test_export',   'failed',  false, 0.40, 'KeyError'),
  ('seed-r2', 'tests/test_broken.py::test_export',   'failed',  false, 0.41, 'KeyError'),
  -- c2 (r3, r4)
  ('seed-r3', 'tests/test_pay.py::test_charge',      'passed',  false, 0.80, NULL),
  ('seed-r4', 'tests/test_pay.py::test_charge',      'failed',  false, 2.10, 'ConnectionError'),
  ('seed-r3', 'tests/test_search.py::test_query',    'failed',  false, 0.35, 'AssertionError'),
  ('seed-r4', 'tests/test_search.py::test_query',    'failed',  false, 0.34, 'AssertionError'),
  ('seed-r3', 'tests/test_db.py::test_migrate',      'error',   false, 0.02, 'fixture error'),
  ('seed-r4', 'tests/test_db.py::test_migrate',      'passed',  false, 0.90, NULL),
  ('seed-r3', 'tests/test_stable.py::test_health',   'passed',  false, 0.01, NULL),
  ('seed-r4', 'tests/test_stable.py::test_health',   'passed',  false, 0.01, NULL),
  -- c3 (r5, r6) — 20 дней назад
  ('seed-r5', 'tests/test_old.py::test_legacy',      'passed',  false, 0.10, NULL),
  ('seed-r6', 'tests/test_old.py::test_legacy',      'failed',  false, 0.11, 'AssertionError'),
  -- shop/web, тот же хеш c1 (r7, r8)
  ('seed-r7', 'tests/test_ui.py::test_button',       'passed',  false, 0.50, NULL),
  ('seed-r8', 'tests/test_ui.py::test_button',       'failed',  false, 0.55, 'ElementNotFound');
COMMIT;
