#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random
from time import time

from justbry import Justbry
from justbry.domreact import DomReact, Cmp as _Cmp

class Cmp(_Cmp): pass
brython = DomReact.brython

class WNotify(Cmp):
    """
        Само-внедряемый виджет нотификаций

        XXX Приватные аттрибуты (с двойным подчеркиванием в начале имени) не пересекаются с наследниками
            (python не явно делает Name Mangling для приватных атрибутов, добавляя префикс `_<имя класса>` к имени атрибута)
    """

    @staticmethod
    @brython
    def wnotify_scripts(WNOTIFY_ID):
        # pylint: disable=E0401,W0104
        
        from browser import document, window, timer

        notify_data = document.select_one(f"script[name='wnotify{WNOTIFY_ID}-data']")
        notify_container = document.select_one(f"div[name='wnotify{WNOTIFY_ID}-container']")
        
        if notify_data and notify_container:
            def notify_handler(mutations, _ob):
                
                for mutation in mutations:
                    if mutation.type == 'childList':
                        content = notify_data.textContent; accent = notify_data.attrs.get('data-accent')
                        if content:
                            nfy = document.createElement('div')
                            nfy.className = f"notification {'is-info is-light' if not accent else accent}"
                            nfy.style.cssText = "box-shadow: 0 0 20px 5px rgba(0,0,0,0.5);"  # 0 0 [размытие] [растяжение] [цвет]
                            nfy.innerHTML = content

                            nfy.style.opacity = '0'
                            nfy.style.transform = 'translateY(50%)'
                            nfy.style.transition = 'all 0.3s ease-out'

                            notify_container.appendChild(nfy)

                            nfy.offsetHeight;  # "Force Reflow" - заставляем браузер применить начальные стили

                            # Теперь плавно проявляется
                            nfy.style.opacity = '1'                                
                            nfy.style.transform = 'translateY(0)'

                            def _toast_remove(nfy):
                                nfy.style.opacity = '0'
                                nfy.style.transform = 'scale(0.85)';  # Эффект уменьшения при исчезновении
                                nfy.addEventListener('transitionend', lambda ev: nfy.remove(), {'once': True})
                                
                            timer.set_timeout(_toast_remove, 5000, nfy)

                            
            notify_observer = window.MutationObserver.new(notify_handler);  # Наблюдение за изменением notify_data
            notify_observer.observe(notify_data, {'childList': True, 'subtree': False, 'attributes': False, 'characterData': False})

        
   
    def __init__(self, **attrs):
        super().__init__('script', type='application/json');  # содержимое для нотификаций в .textContent 

        self.attrs.name = f"wnotify{self.id}-data";           # self.id есть после super().__init__()
        
        self.language = '';  # ru-RU en-US
        self.tzoffset = 0;   # sec

        self.scripts = Cmp('script', type="text/python", id=f"wnotify{self.id}");  # Контейнер для скриптов наследников

        self.container = Cmp('div',
                             style=(
                                 "position: fixed; "
                                 "top: 50%; left: 50%; "
                                 "transform: translate(-50%, -50%); "  # /* Центрирование */
                                 "width: 90%; "                        # /* Ширина на мобильных */
                                 "max-width: 500px; "                  # /* Максимальная ширина на десктопе */
                                 "z-index: 999; "
                                 "display: flex; "
                                 "flex-direction: column; "
                                 "align-items: center; "               # /* Центрирует сами плашки внутри */"
                                 "pointer-events: none; "              # /* Чтобы контейнер не мешал кликам, если он пустой */                                        
                             ),
                             name=f"wnotify{self.id}-container")

        self.__rendered = False;  
                                  
    def render(self):
        """
            Внедрение фронт-энд скриптов поддержки виджета и react-биндинг

            XXX К моменту вызова этого метода есть self.dom для биндингов и внедрения
                ( для полиморфизма перегружаются render(self) )

            FIXME: Необходимость во флаге __rendered возникает только когда мы перегружаем render(self)
                   и динамически там что-то добавляем в dom. Также при добавлении в dom важно помнить
                   последовательность просмотра структуры dom при рендере, чтобы не вставить что-то
                   куда-то уже после того как этот участок был просмотрен.
                   (надежно только dom.body.add() для добавления в конец еще не просмотренного)
        """

        if (dom := self.dom):
            # XXX У нас может быть расшаренный dom-объект и при ре-рендере нужно предотвратить дубликаты скриптов и элементов
            if not self.__rendered:
                
                # Наследники смогут импортировать модуль `wnotify{wnotify.id}`, если будут добавлять свои скрипты в self.scripts
                self.scripts.insert(0, WNotify.wnotify_scripts(self.id))  

                dom.body.add(
                    self.container,
                    self.scripts,
                )

                self.__rendered = True
                       
        return super().render()


    async def notificate(self, content, *, accent="is-info is-light"):
        self.attrs.data_accent = accent
        self.dirty(textContent=content);  # XXX textContent - это действительное свойство элемента на стороне браузера
        await self.update()


class DomView(DomReact):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.body.add(
            Cmp('div', classes="container is-flex is-justify-content-center")(
                _button := Cmp('button', classes="button is-primary")(_label := Cmp('text', "Notificate"))
            ),            
            _wnotify := WNotify(),
        )

        _button.label = _label;  # _button.label.attrs.literal = ...

        self.button = _button

        self.wnotify = _wnotify


        self.button.bind('click', self.notificate)


    async def notificate(self, req):

        self.wnotify.language = req.event.get('language', self.wnotify.language)
        self.wnotify.tzoffset = req.event.get('tzoffset', self.wnotify.tzoffset)

        await self.wnotify.notificate(
            f"language={self.wnotify.language}, tzoffset={self.wnotify.tzoffset}, timestamp={int(time())}",
            accent = random.choice(["is-link is-light", "is-primary is-light", "is-info is-light", "is-success is-light", "is-warning is-light", "is-danger is-light"])
        )


    async def response(self, request=None):
        return await super().response(request)


app = Justbry(
    debug = True,
)


@app.route('/')
async def web(request):
    return await DomView().response(request)
 
