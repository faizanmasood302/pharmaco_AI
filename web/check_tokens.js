const { Pool } = require("pg");
const p = new Pool({
  connectionString: "postgresql://neondb_owner:npg_7BruTCWOIX3N@ep-lucky-bird-ao6tfag6.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
  ssl: { rejectUnauthorized: false },
  connectionTimeoutMillis: 10000,
});
p.query('SELECT token, length(token) as len FROM "session" ORDER BY "createdAt" DESC LIMIT 3', (e, r) => {
  if (e) console.log("ERR:", e.message);
  else r.rows.forEach((x) => console.log("TOKEN:", x.token, "LEN:", x.len));
  p.end();
});
