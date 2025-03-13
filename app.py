# Import eventlet first and monkey patch before any other imports
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response, render_template_string
from flask_socketio import SocketIO, emit
import json
import os
from datetime import datetime
import re
from dotenv import load_dotenv
import secrets

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Set a secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Admin credentials from environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'rocksmolly88')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Exonet_15')

data_dir = "ping_data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Хранение подключенных клиентов
connected_clients = {}
# Хранение клиентов для выполнения команд
command_clients = []
# Хранение списков хостов для провайдеров
provider_hosts = {}

# HTML-страница для входа в админку (в стиле Windows 95/98)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Вход в панель администратора</title>
    <style>
        @font-face {
            font-family: 'MS Sans Serif';
            src: url('https://unpkg.com/98.css@0.1.17/dist/ms_sans_serif.woff2') format('woff2');
            font-weight: normal;
            font-style: normal;
        }
        
        @font-face {
            font-family: 'MS Sans Serif';
            src: url('https://unpkg.com/98.css@0.1.17/dist/ms_sans_serif_bold.woff2') format('woff2');
            font-weight: bold;
            font-style: normal;
        }
        
        body {
            font-family: 'MS Sans Serif', sans-serif;
            background-color: #008080;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-size: 12px;
        }
        
        .login-container {
            background-color: #c0c0c0;
            border: 2px solid #fff;
            border-right-color: #000;
            border-bottom-color: #000;
            box-shadow: 2px 2px 0 #dfdfdf inset, -2px -2px 0 #808080 inset;
            width: 100%;
            max-width: 400px;
        }
        
        .window-title {
            background: linear-gradient(90deg, #000080, #1084d0);
            color: white;
            font-weight: bold;
            padding: 3px 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .window-title-text {
            flex-grow: 1;
            text-align: center;
        }
        
        .window-buttons {
            display: flex;
        }
        
        .window-button {
            width: 16px;
            height: 14px;
            background-color: #c0c0c0;
            border: 1px solid #000;
            border-top-color: #fff;
            border-left-color: #fff;
            margin-left: 2px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 10px;
            cursor: pointer;
        }
        
        .window-content {
            padding: 10px;
        }
        
        h1 {
            color: #000;
            font-size: 16px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 5px;
            font-size: 12px;
            border: 2px solid #000;
            border-right-color: #fff;
            border-bottom-color: #fff;
            background-color: #fff;
            box-sizing: border-box;
            font-family: 'MS Sans Serif', sans-serif;
        }
        
        button {
            width: 100%;
            padding: 5px;
            background-color: #c0c0c0;
            border: 2px solid #fff;
            border-right-color: #000;
            border-bottom-color: #000;
            box-shadow: 1px 1px 0 #dfdfdf inset, -1px -1px 0 #808080 inset;
            font-size: 12px;
            cursor: pointer;
            font-family: 'MS Sans Serif', sans-serif;
            font-weight: bold;
        }
        
        button:active {
            border: 2px solid #000;
            border-right-color: #fff;
            border-bottom-color: #fff;
            box-shadow: -1px -1px 0 #dfdfdf inset, 1px 1px 0 #808080 inset;
        }
        
        .error-message {
            color: #f00;
            margin-bottom: 15px;
            text-align: center;
            background-color: #c0c0c0;
            border: 2px solid #000;
            border-right-color: #fff;
            border-bottom-color: #fff;
            padding: 5px;
        }
        
        .back-link {
            display: block;
            text-align: center;
            margin-top: 15px;
            color: #000;
            text-decoration: none;
            background-color: #c0c0c0;
            border: 2px solid #fff;
            border-right-color: #000;
            border-bottom-color: #000;
            padding: 5px;
            box-shadow: 1px 1px 0 #dfdfdf inset, -1px -1px 0 #808080 inset;
        }
        
        .back-link:active {
            border: 2px solid #000;
            border-right-color: #fff;
            border-bottom-color: #fff;
            box-shadow: -1px -1px 0 #dfdfdf inset, 1px 1px 0 #808080 inset;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="window-title">
            <div class="window-title-text">Вход в систему</div>
            <div class="window-buttons">
                <div class="window-button" onclick="window.location.href='/'">×</div>
            </div>
        </div>
        
        <div class="window-content">
            <h1>Вход в панель администратора</h1>
            
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
            
            <form method="post" action="/login">
                <div class="form-group">
                    <label for="username">Логин:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Пароль:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                
                <button type="submit">Войти</button>
            </form>
            
            <a href="/" class="back-link">← Вернуться на главную</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('admin'))
        else:
            return render_template_string(LOGIN_HTML, error='Неверный логин или пароль')
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    return render_template('admin.html')

@app.route('/get_history')
def get_history():
    history = []
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(data_dir, filename), 'r') as f:
                    file_data = json.load(f)
                    for entry in file_data:
                        if 'timestamp' not in entry:
                            date_match = re.search(r'ping_log_(\d{4}-\d{2}-\d{2})\.json', filename)
                            if date_match:
                                date_str = date_match.group(1)
                                entry['timestamp'] = f"{date_str}T00:00:00"
                    history.extend(file_data)
            except json.JSONDecodeError:
                print(f"Ошибка чтения {filename}: Неверный JSON")
            except Exception as e:
                print(f"Ошибка чтения {filename}: {str(e)}")
    
    # Исправлена ошибка с незакрытой скобкой
    history.sort(key=lambda x: x.get('timestamp', ''))
    return jsonify(history)

@socketio.on('connect')
def handle_connect():
    print(f"[DEBUG] Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[DEBUG] Client disconnected: {request.sid}")
    # Удаляем клиента из списка подключенных
    for provider, data in list(connected_clients.items()):
        if data['sid'] == request.sid:
            del connected_clients[provider]
            print(f"[DEBUG] Removed client: {provider}")
            break
    
    # Удаляем клиента из списка для выполнения команд
    if request.sid in command_clients:
        command_clients.remove(request.sid)
        print(f"[DEBUG] Removed command client: {request.sid}")

@socketio.on('register')
def handle_register(data):
    print(f"[DEBUG] Client registration: {data}")
    provider = data.get('provider')
    if provider:
        connected_clients[provider] = {
            'sid': request.sid,
            'connected_at': datetime.now().isoformat(),
            'last_ping': datetime.now().isoformat()
        }
        emit('register_ack', {'status': 'success', 'message': 'Registration successful'})

@socketio.on('register_command')
def handle_register_command():
    print(f"[DEBUG] Command client registration: {request.sid}")
    if request.sid not in command_clients:
        command_clients.append(request.sid)
    emit('register_command_ack', {'status': 'success'})

@socketio.on('ping_data')
def handle_ping(data):
    provider = data.get('provider')
    
    if provider and provider in connected_clients:
        connected_clients[provider]['last_ping'] = datetime.now().isoformat()
    
    data['timestamp'] = datetime.now().isoformat()
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = os.path.join(data_dir, f"ping_log_{date_str}.json")
    
    # Сохраняем данные в файл
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []
    else:
        existing_data = []
    
    existing_data.append(data)
    with open(filename, 'w') as f:
        json.dump(existing_data, f)
    
    # Отправляем обновление графика
    socketio.emit('update_chart', data)
    
    # Отправляем обновление статуса клиента
    socketio.emit('client_update', {
        'provider': provider,
        'last_ping': datetime.now().isoformat()
    })
    
    return {'status': 'success'}

@socketio.on('get_clients')
def handle_get_clients():
    emit('clients_list', connected_clients)

@socketio.on('admin_command')
def handle_admin_command(command):
    # Проверяем, что команда отправлена аутентифицированным пользователем
    if not session.get('authenticated'):
        return
    
    print(f"[DEBUG] Admin command received: {command}")
    # Отправляем команду всем подключенным клиентам для выполнения команд
    for client_sid in command_clients:
        socketio.emit('execute', command, room=client_sid)

@socketio.on('update_ping_interval')
def handle_update_ping_interval(data):
    # Проверяем, что запрос отправлен аутентифицированным пользователем
    if not session.get('authenticated'):
        return
    
    interval = data.get('interval', 1.0)
    provider = data.get('provider', 'all')
    
    try:
        interval = float(interval)
        if interval < 0.1:
            print(f"[ERROR] Некорректный интервал пинга: {interval}")
            return
        
        print(f"[DEBUG] Обновление интервала пинга: {interval} сек для {provider}")
        
        # Отправляем обновление интервала клиентам
        if provider == 'all':
            # Отправляем всем клиентам
            for client_provider, client_data in connected_clients.items():
                socketio.emit('update_interval', {'interval': interval}, room=client_data['sid'])
                print(f"[DEBUG] Отправлено обновление интервала для {client_provider}: {interval} сек")
        else:
            # Отправляем только выбранному провайдеру
            if provider in connected_clients:
                socketio.emit('update_interval', {'interval': interval}, room=connected_clients[provider]['sid'])
                print(f"[DEBUG] Отправлено обновление интервала для {provider}: {interval} сек")
            else:
                print(f"[ERROR] Провайдер не найден: {provider}")
    
    except Exception as e:
        print(f"[ERROR] Ошибка при обновлении интервала пинга: {str(e)}")

@socketio.on('update_hosts')
def handle_update_hosts(data):
    # Проверяем, что запрос отправлен аутентифицированным пользователем
    if not session.get('authenticated'):
        return
    
    hosts = data.get('hosts', [])
    provider = data.get('provider', 'all')
    
    try:
        if not hosts:
            print(f"[ERROR] Получен пустой список хостов")
            return
        
        print(f"[DEBUG] Обновление списка хостов для {provider}: {', '.join(hosts)}")
        
        # Сохраняем список хостов
        if provider == 'all':
            # Обновляем для всех провайдеров
            for client_provider, client_data in connected_clients.items():
                provider_hosts[client_provider] = hosts
                socketio.emit('update_hosts', {'hosts': hosts}, room=client_data['sid'])
                print(f"[DEBUG] Отправлен обновленный список хостов для {client_provider}")
        else:
            # Обновляем только для выбранного провайдера
            if provider in connected_clients:
                provider_hosts[provider] = hosts
                socketio.emit('update_hosts', {'hosts': hosts}, room=connected_clients[provider]['sid'])
                print(f"[DEBUG] Отправлен обновленный список хостов для {provider}")
            else:
                print(f"[ERROR] Провайдер не найден: {provider}")
    
    except Exception as e:
        print(f"[ERROR] Ошибка при обновлении списка хостов: {str(e)}")

@socketio.on('get_provider_hosts')
def handle_get_provider_hosts(data):
    # Проверяем, что запрос отправлен аутентифицированным пользователем
    if not session.get('authenticated'):
        return
    
    provider = data.get('provider')
    
    if provider:
        hosts = provider_hosts.get(provider, [])
        emit('provider_hosts', {'provider': provider, 'hosts': hosts})

@socketio.on('command_result')
def handle_command_result(result):
    print(f"[DEBUG] Command result received: {result}")
    # Отправляем результат выполнения команды всем админам
    socketio.emit('command_result', result)

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Ошибка доступа</title>
        <style>
            @font-face {
                font-family: 'MS Sans Serif';
                src: url('https://unpkg.com/98.css@0.1.17/dist/ms_sans_serif.woff2') format('woff2');
                font-weight: normal;
                font-style: normal;
            }
            
            @font-face {
                font-family: 'MS Sans Serif';
                src: url('https://unpkg.com/98.css@0.1.17/dist/ms_sans_serif_bold.woff2') format('woff2');
                font-weight: bold;
                font-style: normal;
            }
            
            body {
                font-family: 'MS Sans Serif', sans-serif;
                background-color: #008080;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                font-size: 12px;
            }
            
            .error-container {
                background-color: #c0c0c0;
                border: 2px solid #fff;
                border-right-color: #000;
                border-bottom-color: #000;
                box-shadow: 2px 2px 0 #dfdfdf inset, -2px -2px 0 #808080 inset;
                width: 100%;
                max-width: 500px;
                text-align: center;
            }
            
            .window-title {
                background: linear-gradient(90deg, #000080, #1084d0);
                color: white;
                font-weight: bold;
                padding: 3px 5px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .window-title-text {
                flex-grow: 1;
                text-align: center;
            }
            
            .window-content {
                padding: 10px;
            }
            
            h1 {
                color: #000;
                font-size: 16px;
                margin-bottom: 15px;
            }
            
            p {
                color: #000;
                margin-bottom: 10px;
                line-height: 1.4;
            }
            
            .back-link {
                display: inline-block;
                margin-top: 15px;
                color: #000;
                text-decoration: none;
                background-color: #c0c0c0;
                border: 2px solid #fff;
                border-right-color: #000;
                border-bottom-color: #000;
                padding: 5px 10px;
                box-shadow: 1px 1px 0 #dfdfdf inset, -1px -1px 0 #808080 inset;
            }
            
            .back-link:active {
                border: 2px solid #000;
                border-right-color: #fff;
                border-bottom-color: #fff;
                box-shadow: -1px -1px 0 #dfdfdf inset, 1px 1px 0 #808080 inset;
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="window-title">
                <div class="window-title-text">Ошибка</div>
            </div>
            <div class="window-content">
                <h1>Ошибка доступа к странице</h1>
                <p>Метод запроса не разрешен для запрашиваемого URL.</p>
                <p>Пожалуйста, проверьте правильность URL или вернитесь на главную страницу.</p>
                <a href="/" class="back-link">Вернуться на главную</a>
            </div>
        </div>
    </body>
    </html>
    """), 405

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=True, use_reloader=False)

print("Server is running with authentication enabled.")
print(f"Admin username: {ADMIN_USERNAME}")
print(f"Admin password: {ADMIN_PASSWORD}")
