-- Runs once, when the PostgreSQL volume is created.
-- Separate database for automated tests, so they never touch real orders.
CREATE DATABASE pelargonium_test OWNER pelargonium;
