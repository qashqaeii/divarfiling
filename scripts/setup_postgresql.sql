-- PostgreSQL setup for divarfiling.ir
-- Run on server (replace PASSWORD with DATABASE_PASSWORD from .env):
--
--   sudo -u postgres psql -f scripts/setup_postgresql.sql
--
-- Or run commands manually:

CREATE USER divarfilingAdmin WITH PASSWORD 'YOUR_DATABASE_PASSWORD';
CREATE DATABASE divarfilingDb OWNER divarfilingAdmin;
GRANT ALL PRIVILEGES ON DATABASE divarfilingDb TO divarfilingAdmin;

-- After Django migrate, grant schema (PostgreSQL 15+):
-- \c divarfilingDb
-- GRANT ALL ON SCHEMA public TO divarfilingAdmin;
