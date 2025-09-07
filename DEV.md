1) Окружение разработки:  

`sudo apt-get install -y python3.11`  
`sudo apt-get install -y python3.11-venv`  
`sudo apt-get install -y python3.11-dev`  
<!-- `pip install flake8 pyflakes pylint pylint-venv`  # --init-hook="import pylint_venv; pylint_venv.inithook()" -->  


2) виртуальное окружение python3.11 (из каталога приложения):  
    
`python3.11 -m venv --upgrade-deps .venv`  
`source .venv/bin/activate`  
_(.venv)$_  `pip install --upgrade pip`  
_(.venv)$_  `pip install flake8 pyflakes pylint`  
_(.venv)$_  `pip install -r requirements.txt`  
_(.venv)$_  `deactivate`  
 

3) Пакетные зависимости:  

_(.venv)$_  `pip install uvicorn`  
_(.venv)$_  `pip install starlette`  
_(.venv)$_  `pip install websockets`  
_(.venv)$_  `pip install itsdangerous`  
_(.venv)$_  `pip install requests`  

<!-- _(.venv)$_  `pip install brython=="3.11.3"`  # для оптимизации и замены `brython_stdlib.js` на `brython_modules.js`  -->  





3) Чтобы запуск из исходников был таким-же как и после pip install justbry (импорт правильно разрешался):  
_(.venv)$_  `pip install --editable .`  # https://setuptools.pypa.io/en/latest/userguide/development_mode.html  


