from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Email конфигурация
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')

mail = Mail(app)

# Конфигурация
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Создаем папку для загрузок если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'documents'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'requests'), exist_ok=True)

# Данные водителей
DRIVERS = {
    'Еремин': {'password': 'driver1', 'name': 'Еремин', 'email': 'driver1@falcontrans.com'},
    'Уранов': {'password': 'driver2', 'name': 'Уранов', 'email': 'driver2@falcontrans.com'},
    'Падалец': {'password': 'driver3', 'name': 'Падалец', 'email': 'driver3@falcontrans.com'},
    'Новиков': {'password': 'driver4', 'name': 'Новиков', 'email': 'driver4@falcontrans.com'}
}

# Админ
ADMIN_PASSWORD = 'admin123'
ADMIN_EMAIL = 'admin@falcontrans.com'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'documents': [], 'requests': []}

def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_notification_email(to_email, subject, body):
    """Отправка email уведомления"""
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False

def notify_admin_new_document(driver_name, filename, request_number):
    """Уведомление админа о новом документе"""
    subject = f"Новый документ от водителя {driver_name}"
    body = f"""
Новый документ загружен в систему FalconTrans

Водитель: {driver_name}
Файл: {filename}
Номер заявки: {request_number if request_number else 'Не указан'}
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Для просмотра перейдите в панель администратора.
"""
    return send_notification_email(ADMIN_EMAIL, subject, body)

def notify_driver_new_request(driver_name, request_number, filename):
    """Уведомление водителя о новой заявке"""
    driver_email = DRIVERS[driver_name]['email']
    subject = f"Новая заявка #{request_number}"
    body = f"""
Новая заявка доступна в системе FalconTrans

Номер заявки: {request_number}
Файл: {filename}
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Для просмотра заявки войдите в систему как водитель {driver_name}.
"""
    return send_notification_email(driver_email, subject, body)

@app.route('/')
def index():
    return render_template('index.html', drivers=DRIVERS.keys())

@app.route('/driver/<driver_name>')
def driver_login(driver_name):
    if driver_name not in DRIVERS:
        return redirect(url_for('index'))
    return render_template('driver_login.html', driver_name=driver_name)

@app.route('/driver/<driver_name>/login', methods=['POST'])
def driver_auth(driver_name):
    password = request.form.get('password')
    if password == DRIVERS[driver_name]['password']:
        session['driver'] = driver_name
        return redirect(url_for('driver_panel', driver_name=driver_name))
    else:
        flash('Неверный пароль!')
        return redirect(url_for('driver_login', driver_name=driver_name))

@app.route('/driver/<driver_name>/panel')
def driver_panel(driver_name):
    if 'driver' not in session or session['driver'] != driver_name:
        return redirect(url_for('driver_login', driver_name=driver_name))
    
    data = load_data()
    driver_documents = [doc for doc in data['documents'] if doc['driver'] == driver_name]
    requests = data['requests']
    
    return render_template('driver_panel.html', 
                         driver_name=driver_name, 
                         documents=driver_documents,
                         requests=requests)

@app.route('/driver/<driver_name>/upload', methods=['POST'])
def upload_document(driver_name):
    if 'driver' not in session or session['driver'] != driver_name:
        return redirect(url_for('driver_login', driver_name=driver_name))
    
    if 'file' not in request.files:
        flash('Файл не выбран!')
        return redirect(url_for('driver_panel', driver_name=driver_name))
    
    file = request.files['file']
    request_number = request.form.get('request_number', '')
    
    if file.filename == '':
        flash('Файл не выбран!')
        return redirect(url_for('driver_panel', driver_name=driver_name))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{driver_name}_{timestamp}_{filename}"
        
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'documents', new_filename))
        
        data = load_data()
        data['documents'].append({
            'filename': new_filename,
            'original_name': filename,
            'driver': driver_name,
            'request_number': request_number,
            'upload_time': datetime.now().isoformat()
        })
        save_data(data)
        
        # Отправляем уведомление админу
        notify_admin_new_document(driver_name, filename, request_number)
        
        flash('Документ успешно загружен! Уведомление отправлено администратору.')
    else:
        flash('Недопустимый тип файла!')
    
    return redirect(url_for('driver_panel', driver_name=driver_name))

@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_auth():
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        session['admin'] = True
        return redirect(url_for('admin_panel'))
    else:
        flash('Неверный пароль!')
        return redirect(url_for('admin_login'))

@app.route('/admin/panel')
def admin_panel():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    data = load_data()
    return render_template('admin_panel.html', 
                         documents=data['documents'],
                         requests=data['requests'],
                         drivers=DRIVERS.keys())

@app.route('/admin/upload_request', methods=['POST'])
def upload_request():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    if 'file' not in request.files:
        flash('Файл не выбран!')
        return redirect(url_for('admin_panel'))
    
    file = request.files['file']
    driver = request.form.get('driver')
    request_number = request.form.get('request_number')
    
    if file.filename == '':
        flash('Файл не выбран!')
        return redirect(url_for('admin_panel'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"request_{driver}_{timestamp}_{filename}"
        
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'requests', new_filename))
        
        data = load_data()
        data['requests'].append({
            'filename': new_filename,
            'original_name': filename,
            'driver': driver,
            'request_number': request_number,
            'upload_time': datetime.now().isoformat()
        })
        save_data(data)
        
        # Отправляем уведомление водителю
        notify_driver_new_request(driver, request_number, filename)
        
        flash('Заявка успешно загружена! Уведомление отправлено водителю.')
    else:
        flash('Недопустимый тип файла!')
    
    return redirect(url_for('admin_panel'))

@app.route('/download/<folder>/<filename>')
def download_file(folder, filename):
    # Проверяем права доступа
    if 'admin' not in session and 'driver' not in session:
        return redirect(url_for('index'))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
    if not os.path.exists(file_path):
        flash('Файл не найден!')
        if 'admin' in session:
            return redirect(url_for('admin_panel'))
        else:
            return redirect(url_for('driver_panel', driver_name=session['driver']))
    
    # Если это водитель, проверяем права доступа
    if 'driver' in session:
        data = load_data()
        if folder == 'requests':
            # Проверяем что заявка предназначена для этого водителя
            request_found = False
            for req in data['requests']:
                if req['filename'] == filename and req['driver'] == session['driver']:
                    request_found = True
                    break
            if not request_found:
                flash('Доступ запрещен!')
                return redirect(url_for('driver_panel', driver_name=session['driver']))
        elif folder == 'documents':
            # Проверяем что документ принадлежит этому водителю
            document_found = False
            for doc in data['documents']:
                if doc['filename'] == filename and doc['driver'] == session['driver']:
                    document_found = True
                    break
            if not document_found:
                flash('Доступ запрещен!')
                return redirect(url_for('driver_panel', driver_name=session['driver']))
    
    return send_file(file_path, as_attachment=True)

@app.route('/ping')
def ping():
    """Маршрут для поддержания активности приложения"""
    return {'status': 'alive', 'timestamp': datetime.now().isoformat()}

@app.route('/keep-alive')
def keep_alive():
    """Страница для поддержания активности приложения"""
    return render_template('keep_alive.html')

@app.route('/admin/settings')
def admin_settings():
    """Страница настроек администратора"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port) 