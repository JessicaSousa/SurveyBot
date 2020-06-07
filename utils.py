import settings
import json
import glob
import psycopg2
import os


def database_connection():
    connection = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = connection.cursor()
    return connection, cursor


def create_table():
    SQL_CREATE = """CREATE TABLE IF NOT EXISTS survey_{}(
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL UNIQUE,"""
    for key, values in _SURVEYS.items():
        create = SQL_CREATE.format(key)
        for ind, _ in enumerate(values["questions"]):
            create += f"\n    question_{ind+1} TEXT,"
        create += "\n    saved_on TIMESTAMP);"
        # cria a tabela no banco de dados
        cursor.execute(create)
        connection.commit()


def load_all_surveys():
    paths = glob.glob("surveys/*.json")
    for path in paths:
        _, key = path.split("_")
        key, _ = key.split(".")
        _SURVEYS[key] = load_survey(path)


def load_survey(path):
    with open(path) as json_file:
        data = json.load(json_file)
    return data


def save_answer(
    bot_name: str, user_id: int, question_number: int, answer: str
):
    try:
        colname = f"question_{question_number+1}"
        sql = f"""
        INSERT INTO survey_{bot_name} (user_id, {colname})
        VALUES
        (
            %s,
            %s
        ) 
        ON CONFLICT (user_id)
        DO
            UPDATE
            SET {colname} = EXCLUDED.{colname};
        """
        cursor.execute(sql, (user_id, answer))
        connection.commit()
        count = cursor.rowcount
        print(
            count, f"Record inserted successfully into survey_{bot_name} table"
        )
    except (Exception, psycopg2.Error) as error:
        if connection:
            print(
                f"Failed to insert record into survey_{bot_name} table", error
            )


def is_answered(user_id: int, bot_name: str):
    sql = f"select exists(select 1 from survey_{bot_name} where user_id={user_id});"
    cursor.execute(sql)
    record = cursor.fetchone()[0]
    return record


def close_connection():
    if connection:
        cursor.close()
        connection.close()
        print("PostgreSQL connection is closed")


_SURVEYS = dict()
load_all_surveys()
connection, cursor = database_connection()
# cria a tabela se não existir para cada survey_{}.json
create_table()

