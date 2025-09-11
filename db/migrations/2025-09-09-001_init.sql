-- схема app уже создана ранее

-- универсальная функция-«триггер» для обновления updated_at
CREATE OR REPLACE FUNCTION app.touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- пользователи сервиса (в дальнейшем сюда ляжет auth/idp)
CREATE TABLE IF NOT EXISTS app.users (
  id          BIGSERIAL PRIMARY KEY,
  email       TEXT NOT NULL UNIQUE,
  name        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DROP TRIGGER IF EXISTS trg_users_updated_at ON app.users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON app.users
FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

-- клиенты самозанятого (его заказчики)
CREATE TABLE IF NOT EXISTS app.clients (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  email       TEXT,
  phone       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clients_user_id ON app.clients(user_id);
DROP TRIGGER IF EXISTS trg_clients_updated_at ON app.clients;
CREATE TRIGGER trg_clients_updated_at
BEFORE UPDATE ON app.clients
FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

-- встречи/записи в календаре
CREATE TABLE IF NOT EXISTS app.appointments (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
  client_id   BIGINT REFERENCES app.clients(id) ON DELETE SET NULL,
  start_at    TIMESTAMPTZ NOT NULL,
  end_at      TIMESTAMPTZ NOT NULL,
  status      TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','canceled','done')),
  title       TEXT,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_appts_user_start ON app.appointments(user_id, start_at);
DROP TRIGGER IF EXISTS trg_appts_updated_at ON app.appointments;
CREATE TRIGGER trg_appts_updated_at
BEFORE UPDATE ON app.appointments
FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
