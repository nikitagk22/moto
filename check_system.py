#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт проверки системы перед использованием

Этот скрипт проверяет:
1. Версию Python
2. Наличие и путь к J2534 DLL
3. Базовые зависимости
4. Подключение OpenPort 2.0 (если возможно)
"""

import sys
import os
import platform

def print_header(text):
    """Красивый заголовок"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_status(check, status, message=""):
    """Вывод статуса проверки"""
    if status:
        print(f"✅ {check}: OK {message}")
    else:
        print(f"❌ {check}: FAIL {message}")
    return status

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    is_32bit = sys.maxsize <= 2**32
    
    print(f"Python версия: {version.major}.{version.minor}.{version.micro}")
    print(f"Архитектура: {'32-бит' if is_32bit else '64-бит'}")
    
    if version.major == 3 and version.minor >= 7:
        print_status("Python версия", True, f"({version.major}.{version.minor}.{version.micro})")
    else:
        print_status("Python версия", False, f"Требуется Python 3.7+")
        return False
    
    if not is_32bit:
        print("⚠️  ПРЕДУПРЕЖДЕНИЕ: Используется 64-бит Python")
        print("   Рекомендуется 32-бит для совместимости с DLL")
    
    return True

def check_operating_system():
    """Проверка операционной системы"""
    os_name = platform.system()
    print(f"Операционная система: {os_name} {platform.release()}")
    
    if os_name == "Windows":
        return print_status("Windows", True)
    else:
        return print_status("Windows", False, "Требуется Windows")

def check_dll_exists():
    """Проверка наличия J2534 DLL"""
    # Добавление путей
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        import config
        
        # Проверка основного пути
        main_path = config.J2534_DLL_PATH
        print(f"\nОсновной путь: {main_path}")
        
        if os.path.exists(main_path):
            print_status("Основной DLL", True, f"Найден")
            return True
        else:
            print_status("Основной DLL", False, "Не найден")
        
        # Проверка альтернативных путей
        print("\nПоиск в альтернативных путях...")
        dll_path = config.find_dll_path()
        
        if dll_path:
            print_status("DLL найден", True, f"\n  Путь: {dll_path}")
            print(f"\n💡 Совет: Обновите config.py:")
            print(f"   J2534_DLL_PATH = r\"{dll_path}\"")
            return True
        else:
            print_status("DLL", False, "Не найден ни в одном из путей")
            print("\n📋 Проверенные пути:")
            for path in config.ALTERNATIVE_DLL_PATHS:
                print(f"   - {path}")
            print("\n💡 Решение:")
            print("   1. Установите драйверы Tactrix OpenPort 2.0")
            print("   2. Или найдите openport.dll и укажите путь в config.py")
            return False
            
    except Exception as e:
        print_status("Импорт config", False, f"{e}")
        return False

def check_imports():
    """Проверка импорта модулей"""
    modules = [
        ('ctypes', 'Встроенный'),
        ('threading', 'Встроенный'),
        ('logging', 'Встроенный'),
        ('time', 'Встроенный'),
    ]
    
    all_ok = True
    for module_name, source in modules:
        try:
            __import__(module_name)
            print_status(f"Модуль {module_name}", True, f"({source})")
        except ImportError:
            print_status(f"Модуль {module_name}", False)
            all_ok = False
    
    return all_ok

def check_project_files():
    """Проверка наличия файлов проекта"""
    files = [
        'config.py',
        'j2534_constants.py',
        'j2534_wrapper.py',
        'isotp_handler.py',
        'uds_client.py',
        'harley_diagnostics.py',
        'main.py',
        'README.md',
        'QUICKSTART.md',
        'EXPERIMENTAL_GUIDE.md'
    ]
    
    all_ok = True
    for filename in files:
        path = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(path):
            print_status(filename, True)
        else:
            print_status(filename, False, "Отсутствует")
            all_ok = False
    
    return all_ok

def test_j2534_connection():
    """Тест подключения к OpenPort 2.0"""
    print("\n⚠️  Убедитесь, что OpenPort 2.0 подключен к USB")
    response = input("Продолжить тест подключения? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Пропущено")
        return None
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from j2534_wrapper import J2534Wrapper
        
        print("Попытка открыть устройство...")
        j2534 = J2534Wrapper()
        j2534.open_device()
        
        print_status("Открытие устройства", True, f"DeviceID: {j2534.device_id}")
        
        # Закрытие
        j2534.close_device()
        return True
        
    except Exception as e:
        print_status("Подключение OpenPort", False, f"{e}")
        print("\n💡 Возможные причины:")
        print("   1. OpenPort 2.0 не подключен к USB")
        print("   2. Драйверы не установлены")
        print("   3. Устройство используется другой программой")
        return False

def main():
    """Главная функция"""
    print("""
╔══════════════════════════════════════════════════════════╗
║  Проверка системы для Harley-Davidson Diagnostic Tool   ║
║  Tactrix OpenPort 2.0 + J2534 + UDS/ISO-TP              ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    results = {}
    
    # 1. Проверка Python
    print_header("1. Проверка Python")
    results['python'] = check_python_version()
    
    # 2. Проверка ОС
    print_header("2. Проверка операционной системы")
    results['os'] = check_operating_system()
    
    # 3. Проверка модулей
    print_header("3. Проверка зависимостей")
    results['imports'] = check_imports()
    
    # 4. Проверка файлов проекта
    print_header("4. Проверка файлов проекта")
    results['files'] = check_project_files()
    
    # 5. Проверка DLL
    print_header("5. Проверка J2534 DLL")
    results['dll'] = check_dll_exists()
    
    # 6. Тест подключения (опционально)
    if results['dll']:
        print_header("6. Тест подключения OpenPort 2.0 (опционально)")
        results['connection'] = test_j2534_connection()
    
    # Итоги
    print_header("ИТОГИ")
    
    critical_checks = ['python', 'os', 'imports', 'files', 'dll']
    critical_passed = all(results.get(check, False) for check in critical_checks)
    
    if critical_passed:
        print("✅ Все критичные проверки пройдены!")
        print("\n📚 Следующие шаги:")
        print("   1. Подключите OpenPort 2.0 к компьютеру (USB)")
        print("   2. Подключите адаптер к OBD-II порту мотоцикла")
        print("   3. Включите зажигание")
        print("   4. Запустите: python main.py --read-vin")
        print("\n📖 Подробные инструкции:")
        print("   - QUICKSTART.md - быстрый старт")
        print("   - EXPERIMENTAL_GUIDE.md - поиск параметров")
        print("   - README.md - полная документация")
    else:
        print("❌ Обнаружены проблемы!")
        print("\n📝 Что нужно исправить:")
        
        if not results.get('python'):
            print("   - Установите Python 3.7+ (рекомендуется 32-бит)")
        
        if not results.get('os'):
            print("   - Требуется Windows")
        
        if not results.get('dll'):
            print("   - Установите драйверы Tactrix OpenPort 2.0")
            print("   - Или укажите правильный путь к DLL в config.py")
        
        if not results.get('files'):
            print("   - Проверьте целостность файлов проекта")
    
    print("\n" + "="*60)
    
    if results.get('connection') is False:
        print("\n⚠️  Подключение к OpenPort 2.0 не удалось")
        print("   Это не критично, но нужно для работы с мотоциклом")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
