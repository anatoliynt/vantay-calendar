ALTER TABLE app.appointments
  ADD CONSTRAINT chk_appt_time CHECK (end_at > start_at);
