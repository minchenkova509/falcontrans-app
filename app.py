from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.utils import secure_filename
from PIL import Image
import os
from datetime import datetime
import json
import io

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

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
    'Еремин': {'password': 'driver1', 'name': 'Еремин'},
    'Уранов': {'password': 'driver2', 'name': 'Уранов'},
    'Падалец': {'password': 'driver3', 'name': 'Падалец'},
    'Новиков': {'password': 'driver4', 'name': 'Новиков'}
}

# Админ
ADMIN_PASSWORD = 'admin123'

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

def compress_image(image_file, max_size=(1920, 1080), quality=85):
    """Сжимает изображение для уменьшения размера"""
    try:
        # Открываем изображение
        image = Image.open(image_file)
        
        # Конвертируем в RGB если нужно
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        # Изменяем размер если изображение слишком большое
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Сохраняем сжатое изображение в байты
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"Ошибка сжатия изображения: {e}")
        return None

def get_file_size_mb(file_path):
    """Возвращает размер файла в МБ"""
    try:
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    except:
        return 0



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
        
        # Определяем расширение файла
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Если это изображение, сжимаем его
        if file_ext in ['jpg', 'jpeg', 'png']:
            compressed_image = compress_image(file)
            if compressed_image:
                # Создаем новое имя файла с .jpg
                new_filename = f"{driver_name}_{timestamp}_{filename.rsplit('.', 1)[0]}.jpg"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', new_filename)
                
                # Сохраняем сжатое изображение
                with open(file_path, 'wb') as f:
                    f.write(compressed_image.getvalue())
                
                # Показываем информацию о сжатии
                original_size = len(file.read())
                compressed_size = os.path.getsize(file_path)
                compression_ratio = round((1 - compressed_size / original_size) * 100, 1)
                
                flash(f'Документ успешно загружен! Размер уменьшен на {compression_ratio}%')
            else:
                # Если сжатие не удалось, сохраняем оригинал
                new_filename = f"{driver_name}_{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'documents', new_filename))
                flash('Документ загружен (сжатие не удалось)')
        else:
            # Для PDF файлов сохраняем как есть
            new_filename = f"{driver_name}_{timestamp}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'documents', new_filename))
            flash('Документ успешно загружен!')
        
        data = load_data()
        
        # Получаем размер файла
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', new_filename)
        file_size_mb = get_file_size_mb(file_path)
        
        data['documents'].append({
            'filename': new_filename,
            'original_name': filename,
            'driver': driver_name,
            'request_number': request_number,
            'upload_time': datetime.now().isoformat(),
            'size_mb': file_size_mb
        })
        save_data(data)
        
        flash('Документ успешно загружен!')
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
        
        flash('Заявка успешно загружена!')
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



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port) 