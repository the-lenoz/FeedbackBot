#!/bin/bash
# Переход в директорию скрипта (предполагается, что bot.py находится в той же папке)
cd "$(dirname "$0")"

# При необходимости можно активировать виртуальное окружение:
# source venv/bin/activate

# Запуск бота. Логирование стандартного вывода и ошибок в bot.log
venv/bin/python3 bot.py >> bot.log 2>&1
