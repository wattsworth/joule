# Apply database migrations based on the difference between the current Joule version and the 
# last version of Joule that accessed this database. This tool is run on daemon startup.

import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from joule.version import version as joule_version
from joule.errors import ConfigurationError
import packaging.version
import psycopg2.errors
log = logging.getLogger('joule')

def apply_database_migrations(engine):
    # if this is a new database, no need to run migrations
    if is_new_database(engine):
        print("New database, no need to run migrations")
        return
    
    current_version = get_db_version(engine)
    if current_version == packaging.version.parse(joule_version):
        return
    if current_version > packaging.version.parse(joule_version):
        raise ConfigurationError(f"Database version {current_version} is newer than Joule version {joule_version}. This is not supported")
    print(f"Detected version: {current_version}, running migrations to version {joule_version} ")
    if current_version < packaging.version.parse("0.11"):
        # Apply migrations for version 0.11
        print("Applying migration for version 0.11")
        make_timestamps_timezone_aware(engine)
    else:
        print("No migrations to apply")

        
def make_timestamps_timezone_aware(engine):
    with engine.connect() as conn:
        for table,column in [("annotation","start"),
                             ("annotation","end"),
                             ("folder","updated_at"),
                             ("stream","updated_at"),
                             ("eventstream","updated_at"),]:
            conn.execute(text(f"""ALTER TABLE metadata.{table} ALTER COLUMN "{column}" SET DATA TYPE TIMESTAMPTZ  USING "{column}" at time zone 'UTC'"""))

def get_db_version(engine):
    with engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version FROM metadata.node")).fetchone()
            if row is None:
                return packaging.version.parse("0.0")
            return packaging.version.parse(row[0])
        except SQLAlchemyError:
            print("missing table, returning version 0.0")
            return packaging.version.parse("0.0")
       
def is_new_database(engine):
    # if the metadata schema does not exist, no need to run migrations, this is a new database
    with engine.connect() as conn:
        row = conn.execute(text("SELECT 1 FROM pg_namespace WHERE nspname = 'metadata'")).fetchone()
        return row is None
        