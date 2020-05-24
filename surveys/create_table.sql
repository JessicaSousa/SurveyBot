CREATE TABLE IF NOT EXISTS survey_imdbot(
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    question_1 TEXT,
    question_2 TEXT,
    question_3 TEXT, 
    question_4 TEXT,
    question_5 TEXT,
    question_6 TEXT
);