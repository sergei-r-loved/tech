-- Create table structure
CREATE TABLE run (
    run_id text PRIMARY KEY,
    repo text NOT NULL,
    "commit" text NOT NULL,
    branch text NULL,
    started_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    ci_url text
);

CREATE TABLE result (
    run_id text NOT NULL,
    FOREIGN KEY (run_id) REFERENCES run(run_id),
    nodeid text NOT NULL,
    "status" text NOT NULL CHECK ("status" IN ('passed', 'failed', 'skipped', 'error')),
    quarantined boolean NOT NULL,
    duration float NOT NULL,
    traceback text, 
    PRIMARY KEY (run_id, nodeid)
);