import express from "express";
import pkg from "pg";

const { Pool } = pkg;
const app = express();
const PORT = 3000;
const HOST = "127.0.0.1";

app.use(express.json()); // парсим JSON для POST

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 5,
  idleTimeoutMillis: 30000,
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "node", ciTag: "ci-test-1", time: new Date().toISOString() });
});

app.get("/db-check", async (_req, res) => {
  try {
    const r = await pool.query("select current_user, current_database(), now()");
    res.json({ ok: true, db: r.rows[0] });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ---- USERS ----
app.get("/api/users", async (_req, res) => {
  try {
    const r = await pool.query(
      "select id, email, name, created_at, updated_at from app.users order by id desc limit 100"
    );
    res.json({ items: r.rows });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post("/api/users", async (req, res) => {
  const { email, name } = req.body ?? {};
  if (!email) return res.status(400).json({ ok: false, error: "email is required" });
  try {
    const r = await pool.query(
      "insert into app.users(email, name) values($1, $2) returning id, email, name, created_at, updated_at",
      [email, name ?? null]
    );
    res.status(201).json({ ok: true, item: r.rows[0] });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ---- CLIENTS ----
app.get("/api/clients", async (req, res) => {
  const userId = parseInt(req.query.user_id);
  if (!userId) return res.status(400).json({ ok: false, error: "user_id is required" });
  try {
    const r = await pool.query(
      "select id, user_id, name, email, phone, created_at, updated_at from app.clients where user_id=$1 order by id desc limit 100",
      [userId]
    );
    res.json({ items: r.rows });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post("/api/clients", async (req, res) => {
  const { user_id, name, email, phone } = req.body ?? {};
  if (!user_id || !name) return res.status(400).json({ ok: false, error: "user_id and name are required" });
  try {
    const r = await pool.query(
      "insert into app.clients(user_id, name, email, phone) values($1,$2,$3,$4) returning id, user_id, name, email, phone, created_at, updated_at",
      [user_id, name, email ?? null, phone ?? null]
    );
    res.status(201).json({ ok: true, item: r.rows[0] });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ---- APPOINTMENTS ----
app.get("/api/appointments", async (req, res) => {
  const userId = parseInt(req.query.user_id);
  const from = req.query.from ?? null;
  const to = req.query.to ?? null;
  if (!userId) return res.status(400).json({ ok: false, error: "user_id is required" });

  let sql = `
    select a.id, a.user_id, a.client_id, a.start_at, a.end_at, a.status, a.title, a.notes,
           a.created_at, a.updated_at, c.name as client_name
    from app.appointments a
    left join app.clients c on c.id=a.client_id
    where a.user_id=$1`;
  const params = [userId];
  if (from) { params.push(from); sql += ` and a.start_at >= $${params.length}`; }
  if (to)   { params.push(to);   sql += ` and a.start_at <  $${params.length}`; }
  sql += " order by a.start_at desc limit 200";

  try {
    const r = await pool.query(sql, params);
    res.json({ items: r.rows });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post("/api/appointments", async (req, res) => {
  const { user_id, client_id, start_at, end_at, title, notes } = req.body ?? {};
  if (!user_id || !start_at || !end_at) {
    return res.status(400).json({ ok: false, error: "user_id, start_at, end_at are required" });
  }
  try {
    const r = await pool.query(
      `insert into app.appointments(user_id, client_id, start_at, end_at, title, notes)
       values($1,$2,$3,$4,$5,$6)
       returning id, user_id, client_id, start_at, end_at, status, title, notes, created_at, updated_at`,
      [user_id, client_id ?? null, start_at, end_at, title ?? null, notes ?? null]
    );
    res.status(201).json({ ok: true, item: r.rows[0] });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Node API listening on http://${HOST}:${PORT}`);
});
