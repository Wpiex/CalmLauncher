import re
import weakref

from PySide6.QtWidgets import QMessageBox

RU = {
    "Play": "Играть",
    "Install": "Установить",
    "Content": "Контент",
    "Skins": "Скины",
    "Settings": "Настройки",
    "Show": "Показать",
    "Quit": "Выход",
    "Username or Email": "Логин или Email",
    "Password": "Пароль",
    "Login": "Войти",
    "You are using a third-party account system (Ely.by)\nSkin editing takes place ONLY on the Ely.by website.":
        "Вы используете стороннюю систему аккаунтов (Ely.by)\nСкины редактируются ТОЛЬКО на сайте Ely.by.",
    "Name (Optional)": "Название (необязательно)",
    "Name (optional)": "Название (необязательно)",
    "Version": "Версия",
    "Loader": "Загрузчик",
    "Optimizer": "Оптимизатор",
    "None": "Нет",
    "Cancel": "Отмена",
    "Cancelling": "Отмена...",
    "Completed": "Готово",
    "Cancelled": "Отменено",
    "Launcher": "Лаунчер",
    "Language": "Язык",
    "Launch at Windows startup": "Запускать вместе с Windows",
    "Close launcher after opening Minecraft": "Закрывать лаунчер после запуска Minecraft",
    "Reopen launcher when Minecraft closes": "Открывать лаунчер после закрытия Minecraft",
    "Keep in tray when closed": "Сворачивать в трей при закрытии",
    "Enable Optimized Versions": "Включить оптимизированные версии",
    "Enable Transparency (Experimental)": "Включить прозрачность (Экспериментально)",
    "Button Color": "Цвет кнопок",
    "Background Color": "Цвет фона",
    "Reset Colors": "Сбросить цвета",
    "Open instances folder": "Открыть папку сборок",
    "Check for updates": "Проверить обновления",
    "Logout": "Выйти",
    "Checking...": "Проверка...",
    "Downloading...": "Загрузка...",
    "No updates yet!": "Обновлений пока нет!",
    "Update check": "Проверка обновлений",
    "Calm Launcher update": "Обновление Calm Launcher",
    "No release notes provided.": "Описание релиза отсутствует.",
    "A new version is available: {}\n\n{}\n\nDownload and install this update?":
        "Доступна новая версия: {}\n\n{}\n\nСкачать и установить это обновление?",
    "Update failed": "Ошибка обновления",
    "Update installed": "Обновление установлено",
    "Calm Launcher {} has been installed.\n\nRestart Calm Launcher to use the updated files.":
        "Calm Launcher {} установлен.\n\nПерезапустите Calm Launcher, чтобы использовать обновлённые файлы.",
    "Color": "Цвет",
    "Java memory allocation": "Выделение памяти Java",
    "Memory: {} GB allocated · {} GB total · Recommended: {} GB":
        "Память: выделено {} ГБ · всего {} ГБ · рекомендуется {} ГБ",
    "Allocating more RAM than the recommended amount ({} GB) may lead to problems.":
        "Выделение больше рекомендуемого объёма ОЗУ ({} ГБ) может привести к проблемам.",
    "Use reccomended": "Рекомендуемое",
    "Java version": "Версия Java",
    "Auto (recommended)": "Авто (рекомендуется)",
    "Browse": "Обзор",
    "JVM arguments": "Аргументы JVM",
    "Select Java": "Выбор Java",
    "Invalid Java": "Некорректная Java",
    "Installation Error": "Ошибка установки",
    "Check your Internet connection": "Проверьте подключение к интернету",
    "Check your Internet connection.": "Проверьте подключение к интернету.",
    "Yes": "Да",
    "No": "Нет",
    "Checking session": "Проверка сессии",
    "Downloading authlib-injector": "Загрузка authlib-injector",
    "Checking Minecraft files and libraries": "Проверка файлов и библиотек Minecraft",
    "Checking loader libraries": "Проверка библиотек загрузчика",
    "Launching": "Запуск",
    "Instance has no Minecraft version": "У сборки не указана версия Minecraft",
    "Instance folder does not exist": "Папка сборки не существует",
    "Please log in first": "Сначала войдите в аккаунт",
    "Loader installation failed": "Не удалось установить загрузчик",
    "Session expired": "Сессия истекла",
    "Skin not found on Ely.by": "Скин не найден на Ely.by",
    "No skin": "Скин отсутствует",
    "CurseForge is temporarily unavailable": "CurseForge временно недоступен",
    "GitHub API rate limit reached. Try again later.": "Достигнут лимит запросов GitHub API. Повторите позже.",
    "Could not download the update. Check your Internet connection.":
        "Не удалось скачать обновление. Проверьте подключение к интернету.",
    "No compatible file": "Нет совместимого файла",
    "Auth error": "Ошибка авторизации",
    "Invalid credentials. Invalid username or password.": "Неверный логин или пароль.",
    "Search": "Поиск",
    "Go": "Найти",
    "Filters": "Фильтры",
    "Temporarily unavailable": "Временно недоступно",
    "More": "Ещё",
    "Loading": "Загрузка",
    "Nothing found": "Ничего не найдено",
    "No instances": "Нет сборок",
    "Unknown project": "Неизвестный проект",
    "Unknown": "Неизвестно",
    "downloads": "загрузок",
    "Update": "Обновить",
    "Installed": "Установлено",
    "Update Error": "Ошибка обновления",
    "Updated": "Обновлено",
    "Select an instance": "Выберите сборку",
    "Relevance": "Релевантность",
    "Downloads": "Загрузки",
    "Follows": "Подписчики",
    "Newest": "Новые",
    "Recently updated": "Недавно обновлённые",
    "There's no Instances": "Сборок нет",
    "Rename": "Переименовать",
    "Change Icon": "Сменить иконку",
    "Reset Icon": "Сбросить иконку",
    "Open Mods Folder": "Открыть папку модов",
    "Check for Content updates": "Проверить обновления контента",
    "Delete": "Удалить",
    "Checking content updates...": "Проверка обновлений контента...",
    "No content updates found": "Обновлений контента нет",
    "Content update check failed": "Не удалось проверить обновления контента",
    "Updates available:\n\n{}\n\nInstall these updates?": "Доступны обновления:\n\n{}\n\nУстановить эти обновления?",
    "Content updates": "Обновления контента",
    "Update cancelled": "Обновление отменено",
    "Updating content...": "Обновление контента...",
    "Updated {}; failed: {}": "Обновлено: {}; ошибок: {}",
    "Updated {} content item(s)": "Обновлено элементов контента: {}",
    "Name": "Название",
    "Icon": "Иконка",
    "Invalid image": "Некорректное изображение",
    "Delete {} with all its data?": "Удалить {} со всеми данными?",
    "Unnamed": "Unnamed",
    "Upload Skin": "Загрузить скин",
    "Arms": "Руки",
    "Default": "Обычные",
    "Slim": "Тонкие",
    "Manage on Ely.by": "Управление на Ely.by",
    "Reset Skin": "Сбросить скин",
    "Invalid skin": "Некорректный скин",
    "Skin must be a 64x64 or 64x32 PNG": "Скин должен быть PNG 64x64 или 64x32",
    "Uploading": "Загрузка",
    "Resetting": "Сброс",
    "Skin": "Скин",
    "Open {} and enter the code: {}": "Откройте {} и введите код: {}",
    "Waiting for Microsoft authorization...": "Ожидание авторизации Microsoft...",
    "Microsoft account": "Аккаунт Microsoft",
    "Ely.by account": "Аккаунт Ely.by",
    "Account": "Аккаунт",
    "I accept all registration terms for this launcher and assume full responsibility.": "Я принимаю все условия регистрации этого лаунчера и беру на себя полную ответственность.",
    "Your code is: {}": "Ваш код: {}",
    "Please Accept Registration terms": "Примите условия регистрации",
    "Login Via Microsoft": "Войти через Microsoft",
    "Ok": "Ок",
    "Copy": "Копировать",
    "Copied": "Скопировано",
    "Microsoft authorization was cancelled.": "Авторизация Microsoft отменена.",
    "Enter your Microsoft token (Azure application ID):": "Введите ваш токен Microsoft (ID приложения Azure):",
    "Enter your CurseForge API key (console.curseforge.com):": "Введите ваш API-ключ CurseForge (console.curseforge.com):",
    "Popularity": "Популярность",
    "Calm Launcher {} has been downloaded.\n\nThe launcher will now restart to apply the update.": "Calm Launcher {} скачан.\n\nЛаунчер сейчас перезапустится, чтобы применить обновление.",
    "The release ZIP does not contain Calm Launcher.exe.": "В ZIP-архиве релиза нет Calm Launcher.exe.",
    "Microsoft authorization timed out.": "Время ожидания авторизации Microsoft истекло.",
    "Microsoft authorization was declined.": "Авторизация Microsoft отклонена.",
    "Microsoft authorization code expired.": "Срок действия кода Microsoft истёк.",
    "No Minecraft Java profile was found on this Microsoft account.": "На этом аккаунте Microsoft не найден профиль Minecraft Java.",
    "Microsoft OAuth": "Ошибка Microsoft OAuth",
    "Microsoft token": "Ошибка токена Microsoft",
    "Xbox Live": "Ошибка Xbox Live",
    "Xbox XSTS": "Ошибка Xbox XSTS",
    "Minecraft Services": "Ошибка Minecraft Services",
    "Minecraft profile": "Ошибка профиля Minecraft",
    "Enter your Ely.by username and password.": "Введите логин и пароль Ely.by.",
    "The configuration has no client_token. Restart the launcher to recreate it.": "В конфигурации нет client_token. Перезапустите лаунчер, чтобы создать её заново.",
    "Ely.by login failed": "Ошибка входа Ely.by",
    "Ely.by returned an incomplete profile. Check the server response and API address.": "Ely.by вернул неполный профиль. Проверьте ответ сервера и адрес API.",
    "Ely.by did not return an accessToken.": "Ely.by не вернул accessToken.",
    "The Ely.by session has no token. Please log in again.": "В сессии Ely.by нет токена. Войдите заново.",
    "Ely.by session expired. Please log in again.": "Сессия Ely.by истекла. Войдите заново.",
    "The latest GitHub release does not have a version tag.": "У последнего релиза на GitHub нет тега версии.",
    "The latest GitHub release has no ZIP asset. Upload the launcher package ZIP in the release Assets section.": "У последнего релиза на GitHub нет ZIP-файла. Загрузите ZIP-архив лаунчера в раздел Assets релиза.",
    "ZIP auto-update is currently supported for the Python source version of Calm Launcher, not a packaged EXE.": "ZIP-обновление поддерживается только для версии Calm Launcher из исходников Python, но не для EXE.",
    "The update ZIP contains an unsafe file path.": "ZIP-архив обновления содержит небезопасный путь к файлу.",
    "The update ZIP contains a symbolic link; installation was cancelled.": "ZIP-архив обновления содержит символическую ссылку; установка отменена.",
    "The update ZIP is too large to unpack safely.": "ZIP-архив обновления слишком большой для безопасной распаковки.",
    "The update ZIP is too large to download safely.": "ZIP-архив обновления слишком большой для безопасной загрузки.",
    "The release ZIP does not contain the Calm Launcher source layout (main.py, constants.py, core/, ui/).": "В ZIP-архиве релиза нет структуры исходников Calm Launcher (main.py, constants.py, core/, ui/).",
    "The release download URL is invalid.": "Некорректная ссылка для загрузки релиза.",
    "The update ZIP contains no installable files.": "В ZIP-архиве обновления нет файлов для установки.",
    "The update contains a file outside the launcher directory.": "Обновление содержит файл вне папки лаунчера.",
    "CurseForge requires an API key. Enter it in Content → Source → CurseForge.": "CurseForge требует API-ключ. Введите его в Контент → Источник → CurseForge.",
    "CurseForge rejected the API key (401/403). Check the key and make sure your application is authorized to use the CurseForge API.": "CurseForge отклонил API-ключ (401/403). Проверьте ключ и убедитесь, что приложению разрешён доступ к API CurseForge.",
    "CurseForge returned an invalid response.": "CurseForge вернул некорректный ответ.",
    "No compatible CurseForge file was found for this Minecraft version/loader.": "Не найден совместимый файл CurseForge для этой версии Minecraft и загрузчика.",
    "CurseForge did not provide a file ID for downloading.": "CurseForge не передал ID файла для загрузки.",
    "CurseForge does not provide a direct download for this file. Try another project or file.": "CurseForge не даёт прямую загрузку этого файла. Попробуйте другой проект или файл.",
    "CurseForge returned a file without a filename.": "CurseForge вернул файл без имени.",
}

PATTERNS = (
    (re.compile(r"^Installing (.+)$"), "Установка {}"),
    (re.compile(r"^Repairing (.+) installation$"), "Восстановление установки {}"),
    (re.compile(r"^(.+) installation is incomplete$"), "Установка {} не завершена"),
    (re.compile(r"^(Microsoft OAuth|Microsoft token|Xbox Live|Xbox XSTS|Minecraft Services|Minecraft profile): (.+)$"), "{}: {}"),
    (re.compile(r"^(.+?) \(HTTP (\d+)\): (.+)$"), "{} (HTTP {}): {}"),
    (re.compile(r"^(.+?) \(HTTP (\d+)\)$"), "{} (HTTP {})"),
    (re.compile(r"^Could not connect to Ely\.by: (.+)$"), "Не удалось подключиться к Ely.by: {}"),
    (re.compile(r"^Could not install the update: (.+)$"), "Не удалось установить обновление: {}"),
    (re.compile(r"^GitHub update check failed \(HTTP (\d+)\)\.$"), "Не удалось проверить обновления GitHub (HTTP {})."),
    (re.compile(r"^CurseForge connection failed: (.+)$"), "Не удалось подключиться к CurseForge: {}"),
    (re.compile(r"^CurseForge API error: HTTP (\d+)$"), "Ошибка API CurseForge: HTTP {}"),
    (re.compile(r"^CurseForge download failed: (.+)$"), "Не удалось скачать с CurseForge: {}"),
)

STATE = {"lang": "en"}
BOUND = []


def set_lang(code):
    STATE["lang"] = code if code in ("en", "ru") else "en"


def tr(text):
    if STATE["lang"] != "ru":
        return text
    if text in RU:
        return RU[text]
    for pattern, template in PATTERNS:
        match = pattern.match(text)
        if match:
            return template.format(*[tr(group) for group in match.groups()])
    return text


def bind(target, text, method="setText"):
    getattr(target, method)(tr(text))
    BOUND.append((weakref.ref(target), method, text))
    return target


def retranslate():
    alive = []
    for ref, method, text in BOUND:
        target = ref()
        if target is None:
            continue
        try:
            getattr(target, method)(tr(text))
        except RuntimeError:
            continue
        alive.append((ref, method, text))
    BOUND[:] = alive


def ask(parent, title, text):
    box = QMessageBox(QMessageBox.Question, tr(title), text, QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    box.button(QMessageBox.Yes).setText(tr("Yes"))
    box.button(QMessageBox.No).setText(tr("No"))
    return box.exec() == QMessageBox.Yes
