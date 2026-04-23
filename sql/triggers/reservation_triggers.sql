-- SQL: reservation_triggers.sql
-- Creates scheduling table, trigger to schedule jobs when a reservation
-- becomes IN_PROGRESS, and a processor function to apply scheduled jobs.
-- To execute jobs automatically you should install and enable the pg_cron
-- extension (or run the processor periodically from an external cron).

-- Table to store scheduled jobs for reservations
CREATE TABLE IF NOT EXISTS scheduled_reservation_jobs (
    id serial PRIMARY KEY,
    reservation_id uuid NOT NULL,
    run_at timestamptz NOT NULL,
    job_type text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scheduled_reservation_jobs_run_at ON scheduled_reservation_jobs(run_at);

-- Function: schedule jobs when reservation transitions to IN_PROGRESS
CREATE OR REPLACE FUNCTION schedule_reservation_jobs() RETURNS trigger AS $$
BEGIN
    -- Only schedule when reservation becomes IN_PROGRESS
    IF (TG_OP = 'INSERT' AND NEW.status::text = 'in_progress') OR
       (TG_OP = 'UPDATE' AND OLD.status::text <> NEW.status::text AND NEW.status::text = 'in_progress') THEN

        -- schedule eviction-noon job at eviction_date 12:00 (local time)
        -- Cast date to timestamp and add 12:00, then treat as timestamptz
        INSERT INTO scheduled_reservation_jobs(reservation_id, run_at, job_type)
        VALUES (
            NEW.id,
            (NEW.eviction_date::timestamp + time '12:00')::timestamptz,
            'eviction_noon'
        );
    END IF;
    -- Schedule a cancel job at midnight of (check_in_date + 1 day)
    -- If reservation is still unconfirmed and has no room assigned at that time,
    -- the processor will mark it as cancelled.
    IF (TG_OP = 'INSERT' AND NEW.status::text = 'unconfirm') OR
       (TG_OP = 'UPDATE' AND OLD.status::text <> NEW.status::text AND NEW.status::text = 'unconfirm') OR
       (TG_OP = 'UPDATE' AND OLD.check_in_date IS DISTINCT FROM NEW.check_in_date AND NEW.status::text = 'unconfirm') THEN
        INSERT INTO scheduled_reservation_jobs(reservation_id, run_at, job_type)
        VALUES (
            NEW.id,
            (NEW.check_in_date::timestamp + interval '1 day')::timestamptz,
            'cancel_if_unconfirm'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: attach to reservations table
DROP TRIGGER IF EXISTS trg_schedule_reservation_jobs ON reservations;
CREATE TRIGGER trg_schedule_reservation_jobs
AFTER INSERT OR UPDATE ON reservations
FOR EACH ROW
EXECUTE FUNCTION schedule_reservation_jobs();

-- Processor: apply scheduled jobs whose run_at <= now()
CREATE OR REPLACE FUNCTION process_scheduled_reservation_jobs() RETURNS void AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT id, reservation_id, job_type FROM scheduled_reservation_jobs
        WHERE run_at <= now()
        ORDER BY run_at
        FOR UPDATE SKIP LOCKED
    LOOP
        -- Only update reservation if it still has IN_PROGRESS status
        UPDATE reservations
        SET status = 'completed', room_id = NULL
        WHERE id = r.reservation_id AND status::text = 'in_progress';

        -- remove job entry regardless
        DELETE FROM scheduled_reservation_jobs WHERE id = r.id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Extend processor: handle cancel_if_unconfirm jobs
CREATE OR REPLACE FUNCTION process_scheduled_reservation_jobs() RETURNS void AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT id, reservation_id, job_type FROM scheduled_reservation_jobs
        WHERE run_at <= now()
        ORDER BY run_at
        FOR UPDATE SKIP LOCKED
    LOOP
        IF r.job_type = 'eviction_noon' THEN
            UPDATE reservations
            SET status = 'completed', room_id = NULL
            WHERE id = r.reservation_id AND status::text = 'in_progress';
        ELSIF r.job_type = 'cancel_if_unconfirm' THEN
            UPDATE reservations
            SET status = 'cancelled'
            WHERE id = r.reservation_id AND status::text = 'unconfirm' AND room_id IS NULL;
        END IF;

        -- remove job entry regardless
        DELETE FROM scheduled_reservation_jobs WHERE id = r.id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Optional: schedule automatic execution via pg_cron (if available)
-- Example (run every minute):
--   CREATE EXTENSION IF NOT EXISTS pg_cron;
--   SELECT cron.schedule('process_scheduled_reservation_jobs', '*/1 * * * *', $$SELECT process_scheduled_reservation_jobs();$$);

-- Alternatively, call the processor periodically from an external cron/worker:
--   psql -d yourdb -c "SELECT process_scheduled_reservation_jobs();"
