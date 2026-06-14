import { betterAuth } from "better-auth";
import { Pool } from "pg";

const dbUrl = process.env.DATABASE_URL?.replace(/\?sslmode=[^&]*&?/, "").replace(/[?&]$/, "");
const pool = new Pool({
  connectionString: dbUrl,
  ssl: process.env.DATABASE_URL?.includes("neon.tech")
    ? { rejectUnauthorized: false }
    : process.env.NODE_ENV === "production"
    ? { rejectUnauthorized: true }
    : false,
  connectionTimeoutMillis: 10000,
});

export const auth = betterAuth({
  database: pool,
  emailAndPassword: {
    enabled: true,
  },
  trustHost: true,
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  session: {
    expiresIn: 60 * 60 * 24 * 7,
    updateAge: 60 * 60 * 24,
  },
});
