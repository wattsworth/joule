CREATE OR REPLACE FUNCTION stream_row_count(
  stream_id INTEGER,
  start_ts TIMESTAMP,
  end_ts TIMESTAMP
) RETURNS BIGINT
LANGUAGE PLPGSQL STABLE STRICT AS
$BODY$
DECLARE
  base_name VARCHAR;
  level_name VARCHAR;
  max_decim_level INTEGER;
  decim_level INTEGER;
  base_count BIGINT;
  level_count BIGINT;
BEGIN

  SELECT format('stream%s\_%%',stream_id::text) INTO base_name;
  SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='data'
    AND table_type='BASE TABLE' AND table_name LIKE base_name
    AND table_name NOT LIKE '%intervals' INTO max_decim_level;

  base_count = -1;
  FOR decim_level IN REVERSE max_decim_level..1 LOOP
    RAISE notice 'level %', 4^decim_level;
    SELECT format('data.stream%s_%s',stream_id,(4^decim_level)::text) INTO level_name;
    EXECUTE format('SELECT COUNT(*) FROM %s WHERE time >= $1 AND time < $2', level_name)
      USING start_ts, end_ts
      INTO level_count;
    RAISE notice '-> rows %', level_count;
    IF level_count >= 25 THEN
      base_count = level_count * 4^decim_level;
      EXIT;
    END IF;
  END LOOP;

  IF base_count = -1 THEN
    RAISE notice 'counting from base stream';
    EXECUTE format('SELECT COUNT(*) FROM data.stream%s WHERE time >= $1 AND time <= $2', stream_id::text)
      USING start_ts, end_ts
      INTO base_count;
  END IF;

  IF base_count IS NULL THEN
    base_count = 0;
  END IF;

  RETURN base_count;
END;
$BODY$;