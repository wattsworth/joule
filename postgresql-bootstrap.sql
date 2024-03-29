CREATE DATABASE joule;
\c joule
CREATE USER joule WITH PASSWORD 'joule';
ALTER ROLE joule WITH CREATEROLE REPLICATION;
GRANT ALL PRIVILEGES ON DATABASE joule TO joule WITH GRANT OPTION;
GRANT pg_read_all_settings TO joule;
GRANT CREATE ON SCHEMA public TO joule;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;