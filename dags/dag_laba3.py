import csv
from airflow import DAG
from datetime import datetime
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.hooks.postgres_hook import PostgresHook
from airflow.operators.empty import EmptyOperator
from airflow.operators.bash import BashOperator

# Загружаем данные в таблицу из csv
def insert_data_py():
    src = PostgresHook(postgres_conn_id='qiberry')
    print("Postgres connect success")
    csv_path = "./dags/data.csv"
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            src.insert_rows(table='public.people', rows=[row])

# Делаем select запрос к таблице planes и заносим полученные данные в xcom
def select_data_py(**kwargs):
    ti = kwargs["ti"]
    src = PostgresHook(postgres_conn_id='qiberry')
    src_conn = src.get_conn()
    print("Postgres connect success")
    cursor = src_conn.cursor()
    select_query = "select avg(public.people.age) from public.people"
    cursor.execute(select_query)
    value = float(cursor.fetchall()[0][0])*2
    print(value)
    ti.xcom_push(value=value, key='avg_cost')

with DAG(
    dag_id = "qiberry",
    start_date = datetime(2021, 12, 1),
    schedule = None,
    catchup = False,
    tags = ['qiberry']
) as dag:
    src = PostgresHook(postgres_conn_id='qiberry')
    src_conn = src.get_conn()

    # Удалить таблицу/таблицы
    delete_table = PostgresOperator(
        task_id="delete_table",
        postgres_conn_id="qiberry",
        sql="""
        DROP TABLE if exists public.people
        """
    )

    # Создаем таблицу в БД airflow (схема public)
    create_table_people = PostgresOperator(
        task_id="create_table_people",
        #trigger_rule='one_failed',
        postgres_conn_id="qiberry",
        sql="""
        CREATE TABLE IF NOT EXISTS public.people (
            firstname varchar,
            lastname varchar,
            age int,
            sex varchar,
            color varchar
        );
        """
    )

    # Заносим данные в таблицу
    insert_data = PythonOperator(
        task_id='insert_data',
        python_callable=insert_data_py,
        provide_context=True
    )

    # Запрос к таблице
    select_data = PythonOperator(
        task_id='select_data',
        python_callable=select_data_py
    )

    # Выводим среднее значение cost из xcom в логи
    bash_step = BashOperator(
        task_id='bash_step_py',
        bash_command="echo {{ti.xcom_pull(key = 'avg_cost')}}"
    )

    delete_table >> create_table_people >> insert_data >> select_data >> bash_step
