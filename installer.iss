; Inno Setup скрипт для сборки установщика Excel Converter
; Требуется Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Инструкция по сборке установщика:
; 1. Установите Inno Setup
; 2. Откройте этот файл в Inno Setup Compiler
; 3. Нажмите "Compile" (Ctrl+F9)
; 4. Готовый установщик появится в папке Output/
;
; Для автоматической сборки из командной строки:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

#define MyAppName "Excel Converter"
#define MyAppVersion "1.0.6"
#define MyAppPublisher "Dgigin"
#define MyAppURL "https://github.com/Dgigin/Personal-assistant"
#define MyAppExeName "run.bat"

[Setup]
; Базовые настройки
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases

; Директория установки
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Настройки установки
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=ExcelConverter-Setup-{#MyAppVersion}
SetupIconFile=
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

; Информация о приложении
UninstallDisplayIcon={app}\excel_converter.ico
UninstallDisplayName={#MyAppName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные задачи:"; Flags: checkedonce

[Dirs]
; Директории для пользовательских данных (за пределами Program Files)
Name: "{userappdata}\Excel Converter\logs"
Name: "{userappdata}\Excel Converter\uploads"
Name: "{userappdata}\Excel Converter\flask_session"
Name: "{userappdata}\Excel Converter\temp\update"
Name: "{userappdata}\Excel Converter\config"
Name: "{userappdata}\Excel Converter\config\constructor_scenarios"
Name: "{userappdata}\Excel Converter\profiles"

[Files]
; Корневые файлы
Source: "app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "wsgi.py"; DestDir: "{app}"; Flags: ignoreversion

; Батники для запуска и установки зависимостей
Source: "run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_deps.bat"; DestDir: "{app}"; Flags: ignoreversion

; Скрипт генерации .env с уникальным SECRET_KEY
Source: "setup_env.py"; DestDir: "{app}"; Flags: ignoreversion

; Папка src (рекурсивно)
Source: "src\*.py"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs
Source: "src\routes\*.py"; DestDir: "{app}\src\routes"; Flags: ignoreversion recursesubdirs
Source: "src\models\*.py"; DestDir: "{app}\src\models"; Flags: ignoreversion recursesubdirs
Source: "src\services\*.py"; DestDir: "{app}\src\services"; Flags: ignoreversion recursesubdirs
Source: "src\utils\*.py"; DestDir: "{app}\src\utils"; Flags: ignoreversion recursesubdirs

; Папка templates
Source: "templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs

; Папка plans (документация)
Source: "plans\*.md"; DestDir: "{app}\plans"; Flags: ignoreversion recursesubdirs

; README
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

; .env.example — шаблон с гостевыми данными (будет скопирован в .env при установке)
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion

; update.bat (если есть — для автообновлений)
Source: "update.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Ярлык в меню Пуск
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
; Ярлык для веб-интерфейса
Name: "{group}\Excel Converter (веб-интерфейс)"; Filename: "http://localhost:5000"
; Ярлык удаления
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
; Ярлык на рабочем столе (опционально)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Устанавливаем зависимости Python
Filename: "{cmd}"; Parameters: "/C """"{app}\install_deps.bat"""""; WorkingDir: "{app}"; Description: "Установить зависимости Python"; Flags: postinstall skipifsilent runhidden

; Запускаем приложение после установки
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "Запустить {#MyAppName}"; Flags: postinstall nowait skipifsilent shellexec

[UninstallRun]
; Останавливаем сервер перед удалением
Filename: "{cmd}"; Parameters: "/C taskkill /f /im python.exe 2>nul & exit /b 0"; Flags: runhidden

[Code]
function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('cmd', '/C python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := ResultCode = 0;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsPythonInstalled() then
  begin
    MsgBox(
      'Python не найден на этом компьютере.' + #13#10 + #13#10 +
      'Для работы Excel Converter требуется Python 3.8 или выше.' + #13#10 + #13#10 +
      'Скачайте Python с https://www.python.org/downloads/' + #13#10 +
      'и запустите установщик снова.',
      mbError,
      MB_OK
    );
    // Не прерываем установку — пользователь может установить Python позже
    // и запустить install_deps.bat вручную
  end;
end;