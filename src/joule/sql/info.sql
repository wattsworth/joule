CREATE OR REPLACE FUNCTION stream_info(
    stream_id              INTEGER,
    OUT size BIGINT,
    OUT rows BIGINT,
    OUT min_ts TIMESTAMP,
    OUT max_ts TIMESTAMP

)
LANGUAGE PLPGSQL STABLE STRICT
               AS
$BODY$
DECLARE
  base_name VARCHAR;
  _table_name VARCHAR;
  _table_size BIGINT;
  /*_size BIGINT;
  _acc BIGINT = 0;
  _rows BIGINT;
  _min_ts TIMESTAMP;
  _max_ts TIMESTAMP;*/
BEGIN

  select format('stream%s\_%%', stream_id::text) into base_name;
  -- COMPUTE TOTAL SIZE
  size = 0;
  FOR _table_name IN SELECT format('%s.%s',table_schema, table_name)
    FROM information_schema.tables WHERE table_schema='data'
    AND table_type='BASE TABLE' AND table_name LIKE base_name
    AND table_name NOT LIKE '%intervals' LOOP

    EXECUTE 'SELECT total_bytes FROM hypertable_detailed_size($1)'
      INTO _table_size
      USING _table_name;

    IF _table_size IS NOT NULL THEN
      size = size + _table_size;
    END IF;

  END LOOP;

  -- ALL STATISTICS COMPUTED FROM BASE TABLE
  SELECT format('data.stream%s', stream_id::text) INTO _table_name;



  -- COMPUTE TIME BOUNDS
  EXECUTE format(' SELECT time FROM %s ORDER BY time ASC LIMIT 1 ',_table_name) INTO min_ts;
  EXECUTE format(' SELECT time FROM %s ORDER BY time DESC LIMIT 1 ',_table_name) INTO max_ts;

  -- COMPUTE TOTAL ROWS
  IF min_ts is NULL THEN
    rows = 0;
  ELSE
    EXECUTE 'SELECT stream_row_count($1, $2, $3)' INTO rows USING stream_id, min_ts, max_ts;
  END IF;

END;
$BODY$;
