-- exclusion_rule is an application rule table, not exchange data. load_data.py moves it to the
-- app schema with ALTER TABLE ... SET SCHEMA when it finds it here; this migration only records
-- that the data schema no longer owns it. (No statement: the move needs the app schema first.)
SELECT 1;
