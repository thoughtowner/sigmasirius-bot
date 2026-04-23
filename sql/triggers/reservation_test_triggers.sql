-- SQL: reservation_test_triggers.sql
-- Test-only triggers: schedule a delayed job 30 seconds after reservation becomes IN_PROGRESS.
-- Apply this file only in test environments (do NOT apply in production).

-- Function: schedule a single delayed job (30 seconds after IN_PROGRESS)
CREATE OR REPLACE FUNCTION schedule_reservation_test_jobs() RETURNS trigger AS $$
DECLARE
    v_room_id UUID;
BEGIN
    IF (TG_OP = 'INSERT' AND NEW.status::text = 'in_progress') OR
       (TG_OP = 'UPDATE' AND OLD.status::text <> NEW.status::text AND NEW.status::text = 'in_progress') THEN
        INSERT INTO scheduled_reservation_jobs(reservation_id, run_at, job_type)
        VALUES (NEW.id, now() + interval '30 seconds', 'delayed_30s');
                -- For test environments: attach room by id using full_room_number '1-1-101'
                SELECT id
                INTO v_room_id
                FROM rooms
                WHERE full_room_number = '1-1-101'
                LIMIT 1;

                IF v_room_id IS NOT NULL THEN
                        UPDATE reservations
                        SET room_id = v_room_id
                        WHERE id = NEW.id
                            AND (room_id IS DISTINCT FROM v_room_id);
                END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for test env only
DROP TRIGGER IF EXISTS trg_schedule_reservation_test_jobs ON reservations;
CREATE TRIGGER trg_schedule_reservation_test_jobs
AFTER INSERT OR UPDATE ON reservations
FOR EACH ROW
EXECUTE FUNCTION schedule_reservation_test_jobs();

-- NOTE: This file is intentionally separate. Do not load it into production databases.
