-- TODO: return min max timestamps and row count

CREATE OR REPLACE FUNCTION stream_info_fast(
    stream_id              INTEGER,
    OUT rows BIGINT,
    OUT min_ts TIMESTAMP,
    OUT max_ts TIMESTAMP

)
LANGUAGE PLPGSQL STABLE STRICT
               AS
$BODY$
DECLARE
  _table_name VARCHAR;
BEGIN

  -- ALL STATISTICS COMPUTED FROM BASE TABLE
  SELECT format('data.stream%s', stream_id::text) INTO _table_name;



  -- COMPUTE TIME BOUNDS
  EXECUTE format(' SELECT time FROM %s ORDER BY time ASC LIMIT 1 ',_table_name) INTO min_ts;
  EXECUTE format(' SELECT time FROM %s ORDER BY time DESC LIMIT 1 ',_table_name) INTO max_ts;

  -- COMPUTE TOTAL ROWS
  IF min_ts is NULL THEN
    rows = 0;
  ELSE
      EXECUTE format('SELECT COUNT(*) FROM %s',_table_name) INTO rows;
  END IF;

END;
$BODY$;