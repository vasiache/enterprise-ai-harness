
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kagent') THEN
    CREATE ROLE kagent LOGIN;
  END IF;
END
$$;
