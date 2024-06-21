#!/usr/bin/env python3
from typing import Optional
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from nicegui import Client, app, ui
import mysql.connector

# MySQL database connection
db_config = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'school_diary',
}


def get_db_connection():
    return mysql.connector.connect(**db_config)


# In reality, users' passwords would obviously need to be hashed
passwords = {'admin': 'admin', 'user': 'user'}

unrestricted_page_routes = {'/login', '/not_found'}


class AuthMiddleware(BaseHTTPMiddleware):
    """This middleware restricts access to all NiceGUI pages.

    It redirects the user to the login page if they are not authenticated.
    """

    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get('authenticated', False):
            if request.url.path in Client.page_routes.values() and request.url.path not in unrestricted_page_routes:
                app.storage.user['referrer_path'] = request.url.path  # remember where the user wanted to go
                return RedirectResponse('/login')
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@ui.page('/')
def main_page() -> None:
    ui.navigate.to('/user_page')


@ui.page('/not_found')
def not_found() -> None:
    with ui.card().classes('absolute-center'):
        ui.label('Страница не найдена').classes('text-2xl')
        ui.button('Назад', on_click=lambda: ui.navigate.to('/'))


@ui.page('/start_page')
def start_page() -> None:
    with ui.card().classes('absolute-center'):
        ui.label('Электронный журнал').classes('text-2xl')
        ui.button(text='Войти как учитель',
                  on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/login'))).tailwind.align_self('center')
        ui.button(text='Войти как ученик',
                  on_click=lambda: (app.storage.user.clear(), ui.navigate.to('/login'))).tailwind.align_self('center')


@ui.page('/user_page')
def user_page() -> None:
    with ui.card().classes('absolute-center'):
        ui.label('Выберите класс').classes('text-3xl')
        for i in range(1, 12):
            ui.button(text=f'{i} Класс', on_click=lambda i=i: ui.navigate.to(f'/user_page1?class={i}'))


@ui.page('/user_page1')
def user_page1(request: Request) -> None:
    selected_class = request.query_params.get('class')
    with ui.card().classes('absolute-center'):
        ui.label('Выберите букву класса').classes('text-3xl')
        for letter in ['А', 'Б', 'В', 'Г', 'Д']:
            ui.button(text=f'{letter} Класс',
                      on_click=lambda letter=letter: ui.navigate.to(f'/changer?class={selected_class}&letter={letter}'))


@ui.page('/changer')
def changer(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')
    with ui.card().classes('absolute-center'):
        ui.label(f'Что вы хотите сделать с классом {selected_class}{selected_letter}?').classes(
            'text-3xl').tailwind.align_self('center')
        ui.button(text='Показать список класса', on_click=lambda: ui.navigate.to(
            f'/Name_info?class={selected_class}&letter={selected_letter}')).tailwind.align_self('center')
        ui.button(text='Показать список предметов',
                  on_click=lambda: ui.navigate.to('/subject_name')).tailwind.align_self('center')
        ui.button(text='Показать оценки', on_click=lambda: ui.navigate.to(
            f'/date?class={selected_class}&letter={selected_letter}')).tailwind.align_self('center')
        ui.button(text='Поставить оценки',on_click=lambda:ui.navigate.to(f'/set_score?class={selected_class}&letter={selected_letter}')).tailwind.align_self('center')

'''  
        ui.button(text='Изменить список учеников',on_click=lambda: ui.navigate.to('/edit_students')).tailwind.align_self('center')
        ui.button(text='Изменить список предметов', on_click=lambda: ui.navigate.to('/edit_subjects')).tailwind.align_self('center')
'''

@ui.page('/date')
def date(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')
    with ui.card().classes('absolute-center'):
        ui.label('Выберите дату').classes('text-3xl')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Выбираем уникальные даты из базы данных
        cursor.execute("""
            SELECT DISTINCT DATE_FORMAT(score_date, '%d.%m.%Y') AS score_date
            FROM scores 
            JOIN classes ON scores.class_id = classes.id
            WHERE classes.grade = %s AND classes.letter = %s
        """, (selected_class, selected_letter))

        dates = cursor.fetchall()
        cursor.close()
        conn.close()

        if not dates:
            ui.navigate.to('/not_found')

        for date_record in dates:
            ui.button(text=date_record['score_date'],
                      on_click=lambda date=date_record['score_date']: show_scores(selected_class, selected_letter,
                                                                                  date))


@ui.page('/edit_students')
def edit_students(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = app.storage.user.get('selected_letter')

    # Проверяем, что выбраны и класс, и буква
    if selected_class is None or selected_letter is None:
        ui.notify('Ошибка: Не выбран класс или буква', color='negative')
        return

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Получаем текущий список учеников для выбранного класса и буквы
    cursor.execute("""
        SELECT id, name
        FROM students
        WHERE class_id = (
            SELECT id FROM classes WHERE grade = %s AND letter = %s
        )
    """, (selected_class, selected_letter))

    students = cursor.fetchall()

    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label('Изменить список учеников').classes('text-3xl')

        # Отображаем текущий список учеников
        for student in students:
            with ui.row():
                ui.label(student['name']).flex_grow(1)
                ui.button('Удалить', on_click=lambda student_id=student['id']: delete_student(student_id))

        # Кнопка для добавления нового ученика
        ui.button('Добавить ученика', on_click=lambda: show_add_student_form())


def add_student(name):
    selected_class = app.storage.user.get('selected_class')
    selected_letter = app.storage.user.get('selected_letter')

    # Проверяем, что выбраны и класс, и буква
    if selected_class is None or selected_letter is None:
        ui.notify('Ошибка: Не выбран класс или буква', color='negative')
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO students (name, class_id)
            VALUES (%s, (SELECT id FROM classes WHERE grade = %s AND letter = %s))
        """, (name, selected_class, selected_letter))

        conn.commit()
        ui.navigate.to('/edit_students')  # Перенаправляем после успешной вставки
    except mysql.connector.Error as err:
        ui.notify(f'Ошибка базы данных: {err}', color='negative')
    finally:
        cursor.close()
        conn.close()


def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
    conn.commit()
    cursor.close()
    conn.close()
    ui.refresh()  # Перезагрузить страницу после удаления для обновления списка


def show_add_student_form():
    # Функция для отображения формы добавления нового ученика
    with ui.card().classes('absolute-center'):
        ui.label('Добавить нового ученика').classes('text-3xl')
        name_input = ui.input(label='Имя ученика')
        ui.button('Сохранить', on_click=lambda: add_student(name_input.value))





def show_scores(selected_class, selected_letter, selected_date):
    # Функция для отображения оценок за выбранную дату
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            @rownum := @rownum + 1 AS row_number,
            students.id AS student_id,
            students.name AS student_name,
            subjects.name AS subject,
            scores.score
        FROM scores
        JOIN students ON scores.student_id = students.id
        JOIN subjects ON scores.subject_id = subjects.id
        JOIN classes ON scores.class_id = classes.id
        CROSS JOIN (SELECT @rownum := 0) AS dummy
        WHERE classes.grade = %s 
          AND classes.letter = %s 
          AND DATE_FORMAT(scores.score_date, '%d.%m.%Y') = %s
    """, (selected_class, selected_letter, selected_date))
    scores = cursor.fetchall()
    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label(f'Оценки за {selected_date} класса {selected_class}{selected_letter}').classes('text-3xl')
        columns = [
            {'name': 'row_number', 'label': 'Порядковый номер', 'field': 'row_number', 'required': True,
             'align': 'left'},
            {'name': 'student_name', 'label': 'ФИО', 'field': 'student_name'},
            {'name': 'subject', 'label': 'Предмет', 'field': 'subject', 'align': 'center'},
            {'name': 'score', 'label': 'Оценка', 'field': 'score', 'align': 'center'}
        ]
        rows = [
            {'row_number': score['row_number'], 'student_name': score['student_name'], 'subject': score['subject'],
             'score': score['score']}
            for score in scores
        ]
        ui.table(columns=columns, rows=rows, row_key='row_number')


def show_scores(selected_class, selected_letter, selected_date):
    # Функция для отображения оценок за выбранную дату
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            @rownum := @rownum + 1 AS row_number,
            students.id AS student_id,
            students.name AS student_name,
            subjects.name AS subject,
            scores.score
        FROM scores
        JOIN students ON scores.student_id = students.id
        JOIN subjects ON scores.subject_id = subjects.id
        JOIN classes ON scores.class_id = classes.id
        CROSS JOIN (SELECT @rownum := 0) AS dummy
        WHERE classes.grade = %s 
          AND classes.letter = %s 
          AND DATE_FORMAT(scores.score_date, '%d.%m.%Y') = %s
    """, (selected_class, selected_letter, selected_date))
    scores = cursor.fetchall()
    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label(f'Оценки за {selected_date} класса {selected_class}{selected_letter}').classes('text-3xl')
        columns = [
            {'name': 'row_number', 'label': 'Порядковый номер', 'field': 'row_number', 'required': True,
             'align': 'left'},
            {'name': 'student_name', 'label': 'ФИО', 'field': 'student_name'},
            {'name': 'subject', 'label': 'Предмет', 'field': 'subject', 'align': 'center'},
            {'name': 'score', 'label': 'Оценка', 'field': 'score', 'align': 'center'}
        ]
        rows = [
            {'row_number': score['row_number'], 'student_name': score['student_name'], 'subject': score['subject'],
             'score': score['score']}
            for score in scores
        ]
        ui.table(columns=columns, rows=rows, row_key='row_number')


def show_scores(selected_class, selected_letter, selected_date):
    # Функция для отображения оценок за выбранную дату
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT students.id, students.name, subjects.name AS subject, scores.score
        FROM scores
        JOIN students ON scores.student_id = students.id
        JOIN subjects ON scores.subject_id = subjects.id
        JOIN classes ON scores.class_id = classes.id
        WHERE classes.grade = %s AND classes.letter = %s AND DATE_FORMAT(scores.score_date, '%d.%m.%Y') = %s
    """, (selected_class, selected_letter, selected_date))
    scores = cursor.fetchall()
    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label(f'Оценки за {selected_date} класса {selected_class}{selected_letter}').classes('text-3xl')
        columns = [
            {'name': 'id', 'label': 'Порядковый номер', 'field': 'id', 'required': True, 'align': 'left'},
            {'name': 'name', 'label': 'ФИО', 'field': 'name'},
            {'name': 'subject', 'label': 'Предмет', 'field': 'subject', 'align': 'center'},
            {'name': 'score', 'label': 'Оценка', 'field': 'score', 'align': 'center'}
        ]
        rows = [
            {'id': score['id'], 'name': score['name'], 'subject': score['subject'], 'score': score['score']}
            for score in scores
        ]
        ui.table(columns=columns, rows=rows, row_key='id')


@ui.page('/edit_subjects')
def edit_subjects(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Получаем текущий список предметов для выбранного класса
    cursor.execute("""
        SELECT id, name
        FROM subjects
        WHERE class_id = (
            SELECT id FROM classes WHERE grade = %s AND letter = %s
        )
    """, (selected_class, selected_letter))

    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label('Изменить список предметов').classes('text-3xl')

        # Отображаем текущий список предметов
        for subject in subjects:
            with ui.row():
                ui.label(subject['name']).flex_grow(1)
                ui.button('Удалить', on_click=lambda subject_id=subject['id']: delete_subject(subject_id))

        # Кнопка для добавления нового предмета
        ui.button('Добавить предмет', on_click=lambda: show_add_subject_form())


def delete_subject(subject_id):
    # Функция для удаления предмета из базы данных
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
    conn.commit()
    cursor.close()
    conn.close()
    ui.refresh()  # Перезагрузить страницу после удаления для обновления списка


def show_add_subject_form():
    # Функция для отображения формы добавления нового предмета
    with ui.card().classes('absolute-center'):
        ui.label('Добавить новый предмет').classes('text-3xl')
        name_input = ui.input(label='Название предмета')
        ui.button('Сохранить', on_click=lambda: add_subject(name_input.value))


def add_subject(name):
    # Функция для добавления нового предмета в базу данных
    selected_class = app.storage.user.get('selected_class')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO subjects (name, class_id) VALUES (%s, (SELECT id FROM classes WHERE grade = %s AND letter = %s))",
        (name, selected_class, selected_letter))
    conn.commit()
    cursor.close()
    conn.close()
    ui.navigate.to('/edit_subjects')  # Перенаправить на страницу с обновленным списком предметов


@ui.page('/score')
def score(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')
    selected_date = request.query_params.get('date')
    # Fetch scores from the database for the selected class, letter, and date
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT students.id, students.name, subjects.name AS subject, scores.score
        FROM scores
        JOIN students ON scores.student_id = students.id
        JOIN subjects ON scores.subject_id = subjects.id
        JOIN classes ON scores.class_id = classes.id
        WHERE classes.grade = %s AND classes.letter = %s AND scores.score_date = %s
    """, (selected_class, selected_letter, selected_date))
    scores = cursor.fetchall()
    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label(f'Оценки за {selected_date} класса {selected_class}{selected_letter}').classes('text-3xl')
        columns = [
            {'name': 'id', 'label': 'Порядковый номер', 'field': 'id', 'required': True, 'align': 'left'},
            {'name': 'name', 'label': 'ФИО', 'field': 'name'},
            {'name': 'subject', 'label': 'Предмет', 'field': 'subject', 'align': 'center'},
            {'name': 'score', 'label': 'Оценка', 'field': 'score', 'align': 'center'}
        ]
        rows = [
            {'id': score['id'], 'name': score['name'], 'subject': score['subject'], 'score': score['score']}
            for score in scores
        ]
        ui.table(columns=columns, rows=rows, row_key='id')


@ui.page('/subject_name')
def subject_name() -> None:
    with ui.card().classes('absolute-center'):
        ui.label('Список предметов').classes('text-3xl')
        columns = [
            {'name': 'id', 'label': 'Порядковый номер', 'field': 'id', 'required': True, 'align': 'left'},
            {'name': 'subject', 'label': 'Название предмета', 'field': 'subject'},
        ]
        rows = [
            {'id': '1', 'subject': 'Математика'},
            {'id': '2', 'subject': 'Русский'},
            {'id': '3', 'subject': 'Английский'},
        ]
        ui.table(columns=columns, rows=rows, row_key='id')


@ui.page('/Name_info')
def Name_info(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT students.id, students.name
        FROM students
        JOIN classes ON students.class_id = classes.id
        WHERE classes.grade = %s AND classes.letter = %s
    """, (selected_class, selected_letter))
    students = cursor.fetchall()
    cursor.close()
    conn.close()

    with ui.card().classes('absolute-center'):
        ui.label('Список учащихся класса').classes('text-3xl')
        columns = [
            {'name': 'id', 'label': 'Порядковый номер', 'field': 'id', 'required': True, 'align': 'left'},
            {'name': 'name', 'label': 'ФИО', 'field': 'name'},
        ]
        rows = [
            {'id': student['id'], 'name': student['name']}
            for student in students
        ]
        ui.table(columns=columns, rows=rows, row_key='id')


@ui.page('/login')
def login() -> Optional[RedirectResponse]:
    def try_login() -> None:  # local function to avoid passing username and password as arguments
        if passwords.get(username.value) == password.value:
            app.storage.user.update({'username': username.value, 'authenticated': True})
            ui.navigate.to(app.storage.user.get('referrer_path', '/'))  # go back to where the user wanted to go
        else:
            ui.notify('Неправильный логин или пароль', color='negative')

    if app.storage.user.get('authenticated', False):
        return RedirectResponse('/')
    with ui.card().classes('absolute-center'):
        username = ui.input('Логин').on('keydown.enter', try_login)
        password = ui.input('Пароль', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Войти', on_click=try_login)
    return None

@ui.page('/set_score')
def set_score(request: Request) -> None:
    selected_class = request.query_params.get('class')
    selected_letter = request.query_params.get('letter')
    if not (selected_class and selected_letter):
        ui.notify('Класс или буква не выбраны', color='negative')
        return

    with ui.card().classes('absolute-center'):
        ui.label('Выставить оценку').classes('text-3xl')

        # Получаем список студентов для выбранного класса и буквы
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, name
                FROM students
                WHERE class_id = (
                    SELECT id FROM classes WHERE grade = %s AND letter = %s
                )
            """, (selected_class, selected_letter))
            students = cursor.fetchall()

            # Получаем список предметов
            cursor.execute("SELECT id, name FROM subjects")
            subjects = cursor.fetchall()

            # Выпадающее меню для выбора ученика
            student_select = ui.select(label='Выберите ученика', options=[(s['id'], s['name']) for s in students])
            # Выпадающее меню для выбора предмета
            subject_select = ui.select(label='Выберите предмет', options=[(s['name'], s['id']) for s in subjects])
            # Выпадающее меню для выбора оценки
            score_select = ui.select(label='Выберите оценку', options=[(str(i), i) for i in range(1, 6)])

            # Кнопка для сохранения оценки
            ui.button('Сохранить', on_click=lambda selected_class=selected_class, selected_letter=selected_letter: save_score(
                student_id=student_select.value,
                subject_id=subject_select.value,
                score=score_select.value,
                class_id=selected_class,
                letter=selected_letter
            ))

        except mysql.connector.Error as err:
            ui.notify(f'Ошибка при получении данных: {err}', color='negative')
        finally:
            cursor.close()
            conn.close()

def save_score(student_id: int, subject_id: int, score: int, class_grade: str, letter: str) -> None:
    # Current date
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Save the score in the database
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO scores (student_id, subject_id, score_date, score, class_id)
            SELECT %s, %s, %s, %s, classes.id
            FROM classes
            WHERE classes.grade = %s AND classes.letter = %s
        """, (student_id, subject_id, current_date, score, class_grade, letter))
        conn.commit()
        ui.notify('Оценка сохранена', color='positive')
    except mysql.connector.Error as err:
        ui.notify(f'Ошибка при сохранении оценки: {err}', color='negative')
    finally:
        cursor.close()
        conn.close()


@ui.page('/logout')
def logout() -> None:
    app.storage.user.clear()
    ui.navigate.to('/login')


ui.run(storage_secret='THIS_NEEDS_TO_BE_CHANGED')
