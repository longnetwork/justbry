#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Рендер тегов и документа DOM

    Само-закрывающиеся:
        http://xahlee.info/js/html5_non-closing_tag.html

            <area />
            <base />
            <br />
            <col />
            <embed />
            <hr />
            <img />
            <input />
            <link />
            <meta />
            <param />
            <source />
            <track />
            <wbr />
            <command /> (obsolete)
            <keygen /> (obsolete)
            <menuitem /> (obsolete)
            <frame /> (obsolete)
            
            The space before the slash is optional.



    
    FIXME нужна оптимизация через lru_cache для рендеров/вычислений хешей/для всего рекурсивного...

"""
# pylint: disable=W1117

import itertools, inspect, textwrap as tw, weakref

from html import escape as html_escape

from . import HTMLResponse


class Tag:
    """
        Рендер тега в строковом представлении (уже оптимизирован при создании или изменении атрибутов)

        в `attrs` конструктора словарь или параметры с одноименным названием атрибутов тегов,
        возможно с замененным символом '-' на символ '_', или уже весь атрибут в строковом представлении
        в специальном параметре `literal`, который может быть как последовательный аргумент после `tag`,
        так и ключевым параметром в самих `attrs`
    """
    
    self_closing_tags = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr',
        'command', 'keygen', 'menuitem', 'frame',
        
        '!doctype', '!DOCTYPE', '!--',
    }

    NODE_TEXT = 'text';  # XXX В html такого тега не существует
    
    __slots__ = [
        'tag',
        '_attrs',  # Значение в инстанце для дескриптора attrs
        'id',
        'literal',
        'otag',    # open tag
        'ctag',    # close tag
    ]

    class Attrs:
        """
            Дескриптор данных для доступа к атрибутам в форме cmp.attrs.<name>

            FIXME:
                Доступ через дескриптор (через upd_attrs со словарем параметров) "передергивает" NODE_TEXT без escaped!
                Всегда есть выбора как изменять literal NODE_TEXT: через `.text` или через `.attrs.literal` для "сырого" рендера                   
        """
        
        class Proxy:
            __slots__ = [
                'tag'
            ]
            def __init__(self, tag):
                # self.__dict__['tag'] = tag
                self.__class__.tag.__set__(self, tag)
            def __getattr__(self, item):
                return self.tag.get_attrs().get(item)
            def __setattr__(self, item, val):
                self.tag.upd_attrs({item: val})
        
        def __get__(self, obj, objtype=None):
            return Tag.Attrs.Proxy(obj)
        def __set__(self, obj, value):
            raise AttributeError("read-only data descriptor")
                    

    attrs = Attrs()
    
    
    def __init__(self, tag, literal=None, /, **attrs):
        """
            Строковое представление тега создается сразу для возможности кеширования рендера DOM
            Ре-ререндер тега возможен путем замена ссылки на него на новый созданный тег

            `self.close` для само-закрывающихся тегов - пустая строка

            Если tag=='text', то это просто текстовая нода, где в `literal` ее содержимое

            XXX тега <NODE_TEXT> не существует - используем для задания текстовых нод
                `id` назначается и текстовым нодам для доступа на стороне сервера

        """
        self.tag = tag
        
        object.__setattr__(self, 'id', None)

        self.set_attrs(literal, **attrs)

    def set_attrs(self, literal=None, /, **attrs):
        """
            Каждый раз готовит новое строковое представление частей тега в html
            Если literal передается не как ключевой параметр, то это повод включить для него escape,
            а если как literal=... то он попадает в attrs и escape выключено
            
        """
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        attrs = attrs.copy()
        
        if literal is not None:
            attrs['literal'] = literal
            escaped = True
        else:
            escaped = False

        if 'id' in attrs:
            object.__setattr__(self, 'id', attrs.pop('id'))

        # self.literal = self._literal(escaped, **attrs);  # Без id
        object.__setattr__(self, 'literal', self._literal(escaped, **attrs))
        
        self.otag = self._otag(self.tag, self.literal, self.id);                 # С id если tag не NODE_TEXT
        self.ctag = self._ctag(self.tag)

        self._attrs = attrs

    def get_attrs(self):
        """
            Изменение по ссылке словаря атрибутов не изменит строковое представление (нужно потом делать set_attrs)
        """
        return self._attrs

    def upd_attrs(self, literal=None, /, **attrs):
        
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        _attrs = self.get_attrs(); _attrs.update(attrs)

        self.set_attrs(literal, **_attrs)
                
    def __setattr__(self, name, value):
        """
            Сокращение доступа без .attrs. к некоторым служебным атрибутам
            .text - форсирует escape, .attrs.literal - без escape
        """
        if name == 'literal':  # Запрещенный аттрибут для прямой модификации
            raise AttributeError(f"'{type(self).__name__}' attribute do not change directly '{name}'")
            
        if name == 'id':
            self.upd_attrs(id=value)
        elif name == 'text':
            if self.tag in {Tag.NODE_TEXT}:
                self.upd_attrs(value);                   # Форсированное включение escape
            else:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name):
        if name == 'text':
            if self.tag in {Tag.NODE_TEXT}:
                return self.get_attrs().get('literal');  # Здесь всегда unescaped оригинал
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
    
    @staticmethod
    def _literal(escaped=False, /, **attrs):
        """
            Рендер того что внутри тега после имени и до закрывающей скобки
        """
        
        parts = []
        for k, v in attrs.items():
            if k == 'literal':
                # для script / style escaped не нужно (внутри этих тегов literal - всегда от NODE_TEXT)
                if escaped:
                    parts.append(html_escape(str(v)))
                else:
                    parts.append(str(v))
                continue

            if k in {'classes', 'class', 'className'}:
                parts.append(f'class="{str(v)}"')
                continue
                
            k = k.replace('_', '-')

            if isinstance(v, bool):
                if v: parts.append(k)
                continue

            # Здесь те атрибуты которые игнорируют автоматическое escape

            if k.startswith("on"):
                parts.append(f'{k}="{str(v)}"')
                continue

            # Здесь могут быть data-атрибуты и они обязаны быть escaped
                
            if isinstance(v, str):
                parts.append(f'{k}="{html_escape(v)}"')
                continue

            parts.append(f'{k}="{html_escape(repr(v))}"')

        return ' '.join(parts)

            
    @staticmethod
    def _otag(tag, literal='', tag_id=None):
        """
            Рендер открывающего тега
        """
        if tag in {Tag.NODE_TEXT}:
            return literal
        else:
            if tag_id is not None:
                tag_id = f'id="{str(tag_id)}"' if not isinstance(tag_id, str) else f'id="{tag_id}"'
            else:
                tag_id = ''
            
            if tag in Tag.self_closing_tags:
                if tag[0] != '!':
                    return f"<{tag} {literal} {tag_id}/>"
                else:
                    if tag[1:] == '--':
                        return f"<{tag} {literal} -->"
                    else:
                        return f"<{tag} {literal}>"
                        
            else:
                return f"<{tag} {literal} {tag_id}>"

    @staticmethod
    def _ctag(tag):
        """
            Рендер закрывающего тега
        """
        if tag in {Tag.NODE_TEXT}:
            return ''
        else:
            if tag in Tag.self_closing_tags:
                return ''
            else:
                return f"</{tag}>"


    def __eq__(self, other):        
        if not isinstance(other, Tag): return False
        
        if self.tag in {Tag.NODE_TEXT}:
            return self.literal == other.literal
        else:
            return (self.tag == other.tag) and (self.literal == other.literal) and (self.id == other.id)

    def __hash__(self):
        if self.tag in {Tag.NODE_TEXT}:
            return hash(self.literal)
        else:
            # sys.hash_info.modulus == 2**61-1
            return ( hash(self.tag) * 961 + hash(self.literal) * 31 + hash(self.id) ) % 2305843009213693951
            

    def eql(self, other):  # Сравнение без учета идентификаторов
        if not isinstance(other, Tag): return False
        
        if self.tag in {Tag.NODE_TEXT}:
            return self.literal == other.literal
        else:
            return (self.tag == other.tag) and (self.literal == other.literal)
        
        

class Cmp(Tag):
    """
        Компонент с родителем и дочерней структурой. У каждого есть статический тег

        Парадигма декларации вложенной структуры DOM:

            dom = Cmp(tag)(
                h := Cmp(tag)(
                    ...
                ),
                b := Cmp(tag)(
                    ...
                )
                f := Cmp(tag)(
                    ...
                )
            )

        Атрибут `id` компонента назначается автоматически и передается в атрибут `id` тега,
        если он не задан при объявлении тега. Атрибут `name` не затрагивается


        __hash__ и __eq__ исходя из того что тэги задаются статически и их рендер сразу определяется
        в конструкторах Tag (то есть нам нужна только быстрая композиция хешей по дереву dom)

        XXX `id` в систему сравнений хешей ВХОДИТ (у текстовых нод нету `id`)

        XXX Ссылка на parent в childs утилитарная и слабая

    """

    id_count = itertools.count()

    __slots__ = [
        '__weakref__',

        '_parent',
        '_childs',
    ]

    def __init__(self, tag, literal=None, /, **attrs):
        
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        if 'id' not in attrs:
            attrs.update(id=next(Cmp.id_count))

        # XXX __init__ не возможно вызвать с literal и в позиционных и в ключевых одновременно
        
        if 'literal' in attrs:
            attrs['literal'] =  self._to_script(attrs['literal'])
        elif literal is not None:
            literal = self._to_script(literal)
        
        super().__init__(tag, literal, **attrs)


        self._parent = None
        self._childs = []

    def __deepcopy__(self, memo):
        inst = Cmp.__new__(Cmp)

        self_base = super()

        for slot in self_base.__slots__:
            object.__setattr__(inst, slot, getattr(self_base, slot))

        inst._parent = self._parent;  # Заменится на верхнем уровне дерева на копию родителя
        inst._childs = [c.__deepcopy__(memo) for c in self._childs]

        for c in inst._childs:
            c._parent = weakref.proxy(inst)
            
        return inst



    @staticmethod
    def _to_script(literal: callable):
        """
            Конверсия кода в скрипт для <script type="text/python">

            Прямое попадание в тег скрипта имеет смысл если код сразу запускается,
            то есть сюда попадает не декларация а тело функции, при этом имя функции не
            имеет значения и соответственно ее параметры тоже.
            Все нужные декларации могут быть уже в теле функции и даже
            задано имя модуля для импорта в других местах через `id`: <script type="text/python" id="module">
            (https://brython.info/static_doc/3.13/en/import.html)

        """
        if not callable(literal):
            if isinstance(literal, str):
                return tw.dedent(literal.strip('\r\n'))
                # return literal
            else:
                return literal

        source = inspect.getsource(literal)
        
        is_lambda = literal.__name__ == "<lambda>"
        if is_lambda:  # Лямбду нужно запихивать как декларацию и тут-же вызывать
            source = source.strip('\r\n'); return f"({tw.dedent(source)})()"
            
        # Берем только тело
        
        pos = source.find(':')
        if pos < 0:
            raise SyntaxError(f"{literal} is no function declaration")

        return tw.dedent(source[pos + 1:].strip('\r\n'))

    def _to_component(self: "parent", cmp):
        """
            В точках вызова _to_component() возвращает всегда дочернюю ноду, при этом self - это родитель
            Здесь можем автоматически определить необходимость escape (по родителю)
        """
        
        if isinstance(cmp, Cmp):
            if cmp.tag in {Tag.NODE_TEXT}:  # Cmp уже создан через literal и он уже escaped
                if self.tag in {'script', 'style', }:
                    cmp.upd_attrs(literal=cmp.get_attrs().get('literal'));  # Передернуть без escape         
            return cmp
            
        if isinstance(cmp, str):
            if self.tag not in {'script', 'style', }:  
                return Cmp(Tag.NODE_TEXT, cmp);                             # escaped
            else:
                return Cmp(Tag.NODE_TEXT, literal=cmp);                     # unescaped

        if callable(cmp):
            return Cmp(Tag.NODE_TEXT, literal=cmp)
            
        raise TypeError(f"{cmp} of unsupported type")
        

    def append(self, cmp):                  # list метод
        assert self.tag not in {Tag.NODE_TEXT};  # Эти не могут иметь дочерние
        self._childs.append(c := self._to_component(cmp)); c._parent = weakref.proxy(self)

    
    def add(self, *components: "[Cmp, ...]"):
        """
            TODO: сделать парсинг строк так, чтобы задавать компоненты целыми кусками html-кода
                  ( в точке `if isinstance(c, str):` )
        """
        for c in components:
            self.append(c)
            
        return self

    def clear(self):                        # list метод
        self._childs.clear()

    def clr(self):
        self.clear()
        
        return self    


    def __getitem__(self, child_idx):       # list метод
        return self._childs[child_idx]
        
    def __setitem__(self, child_idx, cmp):  # list метод
        assert self.tag not in {Tag.NODE_TEXT};  # Эти не могут иметь дочерние
        self._childs[child_idx] = (c := self._to_component(cmp)); c._parent = weakref.proxy(self)
        
    def __delitem__(self, child_idx):       # list метод
        del self._childs[child_idx]
    def __len__(self):                      # list метод
        return len(self._childs)
    def __iter__(self):                     # list метод
        return iter(self._childs)


    def insert(self, idx, cmp):             # list метод
        assert self.tag not in {Tag.NODE_TEXT};  # Эти не могут иметь дочерние
        self._childs.insert(idx, c := self._to_component(cmp)); c._parent = weakref.proxy(self)

        
    # ~ def render(self, tabs=''):
        
        # ~ parts = [self.otag + '\n']

        # ~ for c in self._childs:
            # ~ parts.append(c.render('' + '\t'))
    
        # ~ if (c := self.ctag):
            # ~ parts.append(c + '\n')
        
        # ~ return tw.indent(''.join(parts), tabs)

    def render(self):
        
        parts = [self.otag + '\n']

        for c in self._childs:
            parts.append(c.render())
    
        if (c := self.ctag):
            parts.append(c + '\n')
        
        return ''.join(parts)


    def _render(self):
        """
            Без спец символов для outerHTML / innerHTML
            XXX Спец символы при изменении уже загруженного DOM браузер не удаляет, а при загрузке
                страница отдается через render() и отступы сохраняются в исходном документе
                (баузер при загрузки всей страницы как единого документа игнорирует табуляцию и переносы строк)
                
            
        """
        parts = [self.otag]

        for c in self._childs:
            parts.append(c._render())
    
        if (c := self.ctag):
            parts.append(c)
        
        return ''.join(parts)


    def outer(self):
        return self._render()

    def inner(self):
        parts = []
        for c in self._childs:
            parts.append(c._render())
        return ''.join(parts)


    def __call__(self, *components: "[Cmp, ...]"):
        return self.add(*components)

    def __eq__(self, other):
        """
            XXX Протокол поиска объекта:
                - для list, вначале ищется через `is` и если не находит, то тогда через `==`;
                - для dict ключи сохраняются по __hash__
        """
        if not super().__eq__(other):
            return False
            
        return not any(c != o for c, o in itertools.zip_longest(self._childs, other._childs))
        
    def __hash__(self):
        
        result = super().__hash__()
        
        for c in self._childs:
            result = (result * 31 + hash(c)) % 2305843009213693951;  # sys.hash_info.modulus == 2**61-1

        return result
        
    def eql(self, other):  # Сравнение без учета идентификаторов
        """
            XXX Помним что bool(self) это фактически bool(len(self)) при перегруженном __len__ - при пустых childs возвращает False
        """
        if not super().eql(other):
            return False

        return not any( not (isinstance(o, Tag) and c.eql(o)) for c, o in itertools.zip_longest(self._childs, other._childs) )


    def _get_dom(self):
        """
            Комонент на вершине иерархии.
            Можно кешировать поиск, но лучшая практика обновлять dom накопительным итогом
        """
        
        child = self; parent = child._parent

        try:
            while parent:  # parent всегда weak proxy если не None
                child = parent(); parent = child._parent
        except ReferenceError:
            pass
            
        return child
        
    def bind(self, evtype, handler: "server-side"):
        dom = self._get_dom()
        if hasattr(dom, 'bind'):
            dom.bind(self, evtype, handler)

    def dirty(self, **props):
        """
            Маркировка компонента для гарантии обновления через морфинг dom и/или установки properties на стороне браузера (например value)
        """
        self.upd_attrs(data_dirty = (self.get_attrs().get('data_dirty') or 0) + 1)
        if props:
            self.upd_attrs(data_props = props)

    async def update(self):
        dom = self._get_dom()
        if hasattr(dom, 'update'):
            return await dom.update()
            
        return False


    @property
    def parent(self):
        return self._parent

    @property
    def childs(self):
        return self._childs

    @property
    def dom(self):
        return self._get_dom()


class DomHtml(Cmp):
    """
        Базовый шаблон документа (всей страницы)

        https://www.w3schools.com/html/html_head.asp
        
            The HTML <head> element is a container for the following elements: <title>, <style>, <meta>, <link>, <script>, and <base>


        starlette route:
            Mount('/', StaticFiles(directory="static"))
        

        XXX Важно указать в `pythonpath` в onload-событии загрузки <body> суб-каталог
            внутри статики для возможности загрузки скриптов через import:
                onload="brython({debug: 0, cache: false, pythonpath: ['py']})"
                
    """
    def __init__(self, /, *body_components, static="/", version=None, **kwargs):
        """
            Если `version` не задана то динамические импорты brython-а будут при каждом обновлении страницы
            ( cache: false )
        """

        version = str(version) if version is not None else version
        
        brydefer = kwargs.get('brydefer', True)
        
        super().__init__('!DOCTYPE', "html")

        self.add(html := Cmp('html')(
        
            head := Cmp('head')(
                Cmp('title')(title := Cmp(Tag.NODE_TEXT, "JustBry")),
                icon := Cmp('link', rel="icon", type="image/png", href = static + "brython.png"),

                Cmp('meta', charset="utf-8"),
                Cmp('meta', name="viewport", content="width=device-width, initial-scale=1"),

                Cmp('meta', name="version", content=f"{version}" if version else ""),

                Cmp('script', src = static + "brython.min.js" + (f"?v={version}" if version else ""), defer=brydefer),
                brylib := Cmp('script', src = static + "brython_stdlib.min.js" + (f"?v={version}" if version else ""), defer=brydefer),
                # brylib := Cmp('script', src = static + "brython_modules.js" + (f"?v={version}" if version else ""), defer=brydefer),

                Cmp('link', rel="stylesheet", href = static + "bulma.min.css" + (f"?v={version}" if version else "")),
                
                Cmp('script', src = static + "fontawesome_all.js" + (f"?v={version}" if version else ""), defer=True),

                
                style := Cmp('style', id='style')("""
                    [data-theme=light],
                    .theme-light {
                        background-color: var(--bulma-light);
                    }
                    [data-theme=dark],
                    .theme-dark {
                        background-color: var(--bulma-dark);
                    }
                """),

                Cmp('script', type="text/javascript", id="brython")(
                    f"window.onload = () => "
                    f"brython({{ "
                    f"debug: 0, "
                    f"cache: {'true' if version else 'false'}, "
                    f"pythonpath: ['{(static + 'py_v=' + version) if version else (static + 'py')}'], "
                    f"}})"  # Требуется отсечение '_v=version' со стороны starlette.staticfiles ( justbry.VersionMiddleware )
                )
            ),
            
            body := Cmp('body'),
        ))

        self.html = html
        self.head = head
        self.title = title
        self.icon = icon
        self.style = style
        self.body = body

        if body_components:            
            self.body.add(*body_components)

        self.brylib = brylib

    class brython:
        """
            Декторатор для встройки объявлений локальных переменных во фронт-энд скрипт.
            Эти два способа эквиваленты:
                Cmp('script', type="text/python")(
                    foo(variable=...),  # Отдекорированный @brython
                )
                Cmp('script', type="text/python")(
                    f"variable = {repr(...)}",
                    foo,                # Не отдекорированный скрипт или lambda
                )
                
        """
        def __new__(cls, func):

            def wrap(*args, **kwargs):

                parameters = inspect.signature(func).parameters; empty = inspect._empty

                # Точно в сигнатурное последовательности c empty если нету значения по умолчанию
                defaults = { name: param.default for name, param in parameters.items() }

                # Теперь знаем все имена в последовательности args

                localvars = {}

                for name, val in zip(defaults.keys(), args):
                    localvars[name] = val;  # Задано при вызове и значение по умолчанию перекрыто в любом случае

                localvars.update(kwargs);   # Задано при вызове и значение по умолчанию перекрыто в любом случае

                # Накатываем не перекрытые значения по умолчанию и если они не пустые

                for name, val in defaults.items():
                    if val is not empty and name not in localvars:
                        localvars[name] = val
                

                localvars = '\n'.join(f"{k} = {repr(v)}" for k, v in localvars.items());  # pylint: disable=R0204

                source = inspect.getsource(func)
                pos = source.find(':')
                if pos < 0:
                    raise SyntaxError(f"{func} is no function declaration")

                return '\n'.join( (localvars, tw.dedent(source[pos + 1:].strip('\r\n'))) ) 

            wrap.__name__ = func.__name__

            return wrap


    async def response(self, _request=None):
        return HTMLResponse(self.render())



