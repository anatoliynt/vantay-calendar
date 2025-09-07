import express from "express";
import pkg from "pg";

const { Pool } = pkg;
const app = express();
const PORT = 3000;
const HOST = "127.0.0.1";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 5,
  idleTimeoutMillis: 30000
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

app.listen(PORT, HOST, () => {
  console.log(`Node API listening on http://${HOST}:${PORT}`);
});
