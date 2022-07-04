-- Initialize the database.
-- Drop any existing data and create empty tables.

DROP TABLE IF EXISTS Users CASCADE;
DROP TABLE IF EXISTS UserShowsJoin CASCADE;
DROP TABLE IF EXISTS Shows CASCADE;
DROP TABLE IF EXISTS Episodes CASCADE;
DROP TYPE IF EXISTS Weekday CASCADE;

SET TIMEZONE = "UTC";

CREATE TABLE Users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  superuser INTEGER NOT NULL DEFAULT 0,
  modified_by INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (modified_by) REFERENCES Users (id)
);

-- Necessary to set modified_by to the id of the user account just
-- created
CREATE OR REPLACE FUNCTION insert_modified_by_id() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.modified_by IS NULL THEN
        NEW.modified_by := NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_insert_modified_by_id
BEFORE INSERT
ON Users
FOR EACH ROW
EXECUTE PROCEDURE insert_modified_by_id();

CREATE TYPE weekday AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');

CREATE TABLE Shows (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  day_of_week weekday NOT NULL,
  start_time TIME WITHOUT TIME ZONE NOT NULL,
  description TEXT NOT NULL,
  file_path TEXT NOT NULL,
  created_by INTEGER NOT NULL,
  updated_by INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (created_by) REFERENCES Users (id),
  FOREIGN KEY (updated_by) REFERENCES Users (id)
);

-- Prevent shows from being created during the same timeslot
CREATE UNIQUE INDEX uidx_show_timeslot ON Shows (day_of_week, start_time);

CREATE TABLE UserShowsJoin (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  show_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES Users (id),
  FOREIGN KEY (show_id) REFERENCES Shows (id)
);

CREATE TABLE Episodes (
  id SERIAL PRIMARY KEY,
  show_id INTEGER NOT NULL,
  title TEXT,
  air_date TIMESTAMP WITH TIME ZONE UNIQUE NOT NULL,
  file_id TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  description TEXT,
  created_by INTEGER NOT NULL,
  updated_by INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (show_id) REFERENCES Shows (id),
  FOREIGN KEY (created_by) REFERENCES Users (id),
  FOREIGN KEY (updated_by) REFERENCES Users (id)
);
