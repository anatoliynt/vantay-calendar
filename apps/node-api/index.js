import express from "express";
import pkg from "pg";

const { Pool } = pkg;
const app = express();
const PORT = 3000;
const HOST = "127.0.0.1";

app.use(express.json()); // JSON body

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 5,
  idleTimeoutMillis: 30000,
});

// --- Bearer auth middleware ---
const API_KEY = process.env.API_KEY;
function auth(req, res, next) {
  if (!API_KEY) return res.status(500).json({ ok: false, error: "API key not set" });
  const h = req.get("authorization") || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (!m || m[1] !== API_KEY) return res.status(401).json({ ok: false, error: "unauthorized" });
  next();
}

app.use("/db-check", auth);
app.use("/api", auth);

// ---- health / db-check
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

// list (с лимитом)
app.get("/api/users", async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit ?? "100", 10) || 100, 500);
  try {
    const r = await pool.query(
      "select id, email, name, created_at, updated_at from app.users order by id desc limit $1",
      [limit]
    );
    res.json({ items: r.rows });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// create
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

// update
app.put("/api/users/:id", async (req, res) => {
  const id = Number(req.params.id);
  const { email, name } = req.body ?? {};
  try {
    const r = await pool.query(
      `update app.users
         set email = coalesce($1, email),
             name  = coalesce($2, name)
       where id = $3
       returning id, email, name, created_at, updated_at`,
      [email ?? null, name ?? null, id]   // <-- ключевой момент: undefined -> null
    );
    if (r.rowCount === 0) return res.status(404).json({ ok: false, error: "not found" });
    res.json({ ok: true, item: r.rows[0] });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// delete
app.delete("/api/users/:id", async (req, res) => {
  const id = parseInt(req.params.id, 10);
  try {
    const r = await pool.query("delete from app.users where id=$1", [id]);
    if (r.rowCount === 0) return res.status(404).json({ ok: false, error: "not found" });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Node API listening on http://${HOST}:${PORT}`);
});
