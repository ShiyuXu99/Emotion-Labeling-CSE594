"""Preserve existing records while adding separate task IDs. Safe to rerun."""
from pathlib import Path
from database import get_connection


def main():
    c = get_connection()
    try:
        with c:
            with c.cursor() as q:
                q.execute("SELECT pg_advisory_xact_lock(594102)")
                q.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='annotations' AND column_name='task_id')")
                if not q.fetchone()[0]:
                    q.execute("LOCK TABLE participants, annotations IN ACCESS EXCLUSIVE MODE")
                    q.execute("SELECT count(*) FROM annotations")
                    before = q.fetchone()[0]
                    q.execute("""CREATE TABLE tasks (
                        task_id UUID PRIMARY KEY,
                        participant_id UUID NOT NULL REFERENCES participants(participant_id),
                        started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMPTZ,
                        UNIQUE(task_id, participant_id),
                        CHECK(completed_at IS NULL OR completed_at >= started_at))""")
                    q.execute("INSERT INTO tasks SELECT participant_id,participant_id,started_at,completed_at FROM participants")
                    q.execute("ALTER TABLE annotations ADD COLUMN task_id UUID")
                    q.execute("UPDATE annotations SET task_id=participant_id")
                    q.execute("ALTER TABLE annotations ALTER COLUMN task_id SET NOT NULL")
                    q.execute("ALTER TABLE annotations DROP CONSTRAINT annotations_pkey, DROP CONSTRAINT annotations_participant_id_position_key")
                    q.execute("""ALTER TABLE annotations ADD PRIMARY KEY(task_id,tweet_id),
                        ADD UNIQUE(task_id,position), ADD FOREIGN KEY(task_id,participant_id) REFERENCES tasks(task_id,participant_id)""")
                    q.execute("SELECT count(*) FROM annotations")
                    assert q.fetchone()[0] == before
                    print(f"Preserved {before} annotations; existing participants retained as separate identities.")
                q.execute(Path(__file__).with_name('schema.sql').read_text())
        print('Task schema ready.')
    finally:
        c.close()

if __name__ == '__main__':
    main()
