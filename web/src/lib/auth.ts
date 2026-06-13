import { betterAuth } from "better-auth";
import { Pool } from "pg";

// The DATABASE_URL should be your direct Supabase connection string (Postgres)
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false, // Required for Supabase connection poolers on Vercel
  },
});

export const auth = betterAuth({
  database: pool,
  emailAndPassword: {
    enabled: true,
  },
  // trustHost is required for Vercel/HuggingFace proxied environments
  advanced: {
    trustHost: true,
  },
  // Ensure the base URL is correct for your environment
  baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
  secret: process.env.BETTER_AUTH_SECRET,
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24, // 1 day
  },
});
