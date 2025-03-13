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

# HTML-страница для входа в админку (с оранжевым цветом)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Вход в панель администратора</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #fff3e0;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 15px rgba(255, 152, 0, 0.3);
            width: 100%;
            max-width: 400px;
            border-top: 4px solid #FF9800;
        }
        h1 {
            color: #E65100;
            font-size: 24px;
            margin-bottom: 20px;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #F57C00;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #FFB74D;
            border-radius: 5px;
            box-sizing: border-box;
            transition: border-color 0.3s, box-shadow 0.3s;
        }
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #FF9800;
            box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.2);
        }
        button {
            width: 100%;
            padding: 12px;
            background-color: #FF9800;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
            font-weight: bold;
        }
        button:hover {
            background-color: #F57C00;
        }
        .error-message {
            color: #D50000;
            margin-bottom: 15px;
            text-align: center;
            background-color: #FFEBEE;
            padding: 8px;
            border-radius: 4px;
            border-left: 4px solid #D50000;
        }
        .back-link {
            display: block;
            text-align: center;
            margin-top: 20px;
            color: #FF9800;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
            color: #F57C00;
        }
    </style>
</head>
<body>
    <div class="login-container">
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
</body>
</html>
"""

# HTML-страница для управления командами (с оранжевыми акцентами и настройкой интервала пинга)
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Управление компьютерами</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.1/socket.io.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #fff3e0;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: #E65100;
            font-size: 28px;
            margin-bottom: 20px;
        }
        .input-container {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            width: 100%;
            max-width: 600px;
        }
        #commandInput {
            flex: 1;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #FFB74D;
            border-radius: 5px;
            outline: none;
            transition: border-color 0.3s;
        }
        #commandInput:focus {
            border-color: #FF9800;
            box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.2);
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            background-color: #FF9800;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
            font-weight: bold;
        }
        button:hover {
            background-color: #F57C00;
        }
        #response {
            background-color: #1e1e1e;
            color: #ffffff;
            padding: 15px;
            border-radius: 5px;
            width: 100%;
            max-width: 600px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre-wrap;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 4px solid #FF9800;
        }
        .client-list {
            width: 100%;
            max-width: 600px;
            margin-bottom: 20px;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 5px;
            overflow: hidden;
        }
        .client-list th, .client-list td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #FFE0B2;
        }
        .client-list th {
            background-color: #FF9800;
            color: white;
            font-weight: bold;
        }
        .client-list tr:hover {
            background-color: #FFF8E1;
        }
        .status-online {
            color: #2E7D32;
            font-weight: bold;
        }
        .status-offline {
            color: #D32F2F;
        }
        .back-link {
            margin-bottom: 20px;
            text-decoration: none;
            color: #FF9800;
            font-weight: bold;
        }
        .back-link:hover {
            text-decoration: underline;
            color: #F57C00;
        }
        .logout-link {
            position: absolute;
            top: 20px;
            right: 20px;
            text-decoration: none;
            color: #D32F2F;
            font-weight: bold;
            background-color: white;
            padding: 8px 15px;
            border-radius: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .logout-link:hover {
            background-color: #D32F2F;
            color: white;
        }
        .settings-panel {
            width: 100%;
            max-width: 600px;
            background-color: white;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .settings-panel h2 {
            color: #E65100;
            font-size: 20px;
            margin-top: 0;
            margin-bottom: 15px;
            border-bottom: 2px solid #FFE0B2;
            padding-bottom: 8px;
        }
        .settings-group {
            margin-bottom: 15px;
        }
        .settings-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #F57C00;
        }
        .settings-group input[type="number"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #FFB74D;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        .settings-group input[type="number"]:focus {
            outline: none;
            border-color: #FF9800;
            box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.2);
        }
        .settings-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
        .provider-row {
            cursor: pointer;
        }
        .provider-row:hover {
            background-color: #FFF8E1;
        }
        .provider-row.selected {
            background-color: #FFF3E0;
            border-left: 3px solid #FF9800;
        }
        .success-message {
            background-color: #E8F5E9;
            color: #2E7D32;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 15px;
            border-left: 4px solid #2E7D32;
            display: none;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Вернуться на главную</a>
    <a href="/logout" class="logout-link">Выйти</a>
    <h1>Управление компьютерами</h1>
    
    <div class="settings-panel">
        <h2>Настройки пинга</h2>
        <div id="successMessage" class="success-message">Настройки успешно применены</div>
        
        <div class="settings-group">
            <label for="pingInterval">Интервал пинга (секунды):</label>
            <input type="number" id="pingInterval" min="0.1" step="0.1" value="1.0">
            <small style="color: #757575; display: block; margin-top: 5px;">Минимальное значение: 0.1 секунды</small>
        </div>
        
        <div class="settings-group">
            <label>Применить к:</label>
            <select id="applyTo" style="width: 100%; padding: 8px; border: 1px solid #FFB74D; border-radius: 4px;">
                <option value="all">Всем провайдерам</option>
                <option value="selected">Выбранному провайдеру</option>
            </select>
        </div>
        
        <div class="settings-actions">
            <button id="applySettings">Применить настройки</button>
        </div>
    </div>
    
    <table class="client-list">
        <thead>
            <tr>
                <th>Провайдер</th>
                <th>Статус</th>
                <th>Последний пинг</th>
            </tr>
        </thead>
        <tbody id="clientList">
            <!-- Клиенты будут добавлены динамически -->
        </tbody>
    </table>
    
    <div class="input-container">
        <input type="text" id="commandInput" placeholder="Введите команду для выполнения">
        <button onclick="sendCommand()">Отправить</button>
    </div>
    <pre id="response">[Консоль готова к работе]
</pre>

    <script>
        var socket = io();
        var selectedProvider = null;
        
        socket.on('connect', function() {
            console.log('Connected to server');
            // Запрашиваем список клиентов при подключении
            socket.emit('get_clients');
        });
        
        socket.on('clients_list', function(clients) {
            updateClientList(clients);
        });
        
        socket.on('client_update', function(client) {
            // Обновляем информацию о клиенте в списке
            socket.emit('get_clients');
        });
        
        socket.on('command_result', function(data) {
            var responseBox = document.getElementById('response');
            responseBox.innerText += data + '\\n';
            responseBox.scrollTop = responseBox.scrollHeight; // Автоскролл вниз
        });
        
        function updateClientList(clients) {
            var clientList = document.getElementById('clientList');
            clientList.innerHTML = '';
            
            for (var provider in clients) {
                var client = clients[provider];
                var row = document.createElement('tr');
                row.className = 'provider-row';
                row.dataset.provider = provider;
                
                if (selectedProvider === provider) {
                    row.classList.add('selected');
                }
                
                var lastPingTime = new Date(client.last_ping);
                var now = new Date();
                var timeDiff = (now - lastPingTime) / 1000; // в секундах
                
                var isOnline = timeDiff < 30; // Считаем клиента онлайн, если пинг был менее 30 секунд назад
                
                row.innerHTML = `
                    <td>${provider}</td>
                    <td class="${isOnline ? 'status-online' : 'status-offline'}">${isOnline ? 'Онлайн' : 'Оффлайн'}</td>
                    <td>${lastPingTime.toLocaleString()}</td>
                `;
                
                row.addEventListener('click', function() {
                    var provider = this.dataset.provider;
                    selectProvider(provider);
                });
                
                clientList.appendChild(row);
            }
        }
        
        function selectProvider(provider) {
            selectedProvider = provider;
            
            // Обновляем выделение в таблице
            document.querySelectorAll('.provider-row').forEach(function(row) {
                if (row.dataset.provider === provider) {
                    row.classList.add('selected');
                } else {
                    row.classList.remove('selected');
                }
            });
            
            // Автоматически переключаем на "Выбранному провайдеру"
            document.getElementById('applyTo').value = 'selected';
            
            console.log('Выбран провайдер:', provider);
        }
        
        function sendCommand() {
            var command = document.getElementById('commandInput').value.trim();
            if (command) {
                socket.emit('admin_command', command);
                document.getElementById('response').innerText += `[${new Date().toLocaleTimeString()}] > ${command}\\n`;
                document.getElementById('commandInput').value = '';
            }
        }
        
        // Отправка команды по нажатию Enter
        document.getElementById('commandInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });
        
        // Обработчик кнопки применения настроек
        document.getElementById('applySettings').addEventListener('click', function() {
            var pingInterval = parseFloat(document.getElementById('pingInterval').value);
            var applyTo = document.getElementById('applyTo').value;
            
            if (isNaN(pingInterval) || pingInterval < 0.1) {
                alert('Пожалуйста, введите корректный интервал пинга (минимум 0.1 секунды)');
                return;
            }
            
            if (applyTo === 'selected' && !selectedProvider) {
                alert('Пожалуйста, выберите провайдера из списка');
                return;
            }
            
            // Отправляем настройки на сервер
            socket.emit('update_ping_interval', {
                interval: pingInterval,
                provider: applyTo === 'selected' ? selectedProvider : 'all'
            });
            
            // Показываем сообщение об успехе
            var successMessage = document.getElementById('successMessage');
            successMessage.style.display = 'block';
            successMessage.textContent = `Интервал пинга (${pingInterval} сек) успешно применен к ${applyTo === 'selected' ? 'провайдеру ' + selectedProvider : 'всем провайдерам'}`;
            
            // Скрываем сообщение через 3 секунды
            setTimeout(function() {
                successMessage.style.display = 'none';
            }, 3000);
        });
        
        // Обновляем список клиентов каждые 10 секунд
        setInterval(function() {
            socket.emit('get_clients');
        }, 10000);
    </script>
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
    
    return render_template_string(ADMIN_HTML)

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

@socketio.on('command_result')
def handle_command_result(result):
    print(f"[DEBUG] Command result received: {result}")
    # Отправляем результат выполнения команды всем админам
    socketio.emit('command_result', result)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=True, use_reloader=False)

print("Server is running with authentication enabled.")
print(f"Admin username: {ADMIN_USERNAME}")
print(f"Admin password: {ADMIN_PASSWORD}")
