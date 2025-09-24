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

import itertools, inspect, textwrap as tw, weakref


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

    NODE_TEXT = 'text'
    SCRIPT_TEXT = 'python'

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
            Дескриптор данных для для доступа к атрибутам в форме cmp.attrs.<name>
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
    
    
    def __init__(self, tag, literal=None, **attrs):
        """
            Строковое представление тега создается сразу для возможности кеширования рендера DOM
            Ре-ререндер тега возможен путем замена ссылки на него на новый созданный тег

            `self.close` для само-закрывающихся тегов - пустая строка

            Если tag=='text', то это просто текстовая нода, где в `literal` ее содержимое

            XXX тега <NODE_TEXT> не существует - используем для задания текстовых нод
                `id` назначается и текстовым нодам для доступа на стороне сервера

        """
        self.tag = tag
        self.id = None

        self.set_attrs(literal, **attrs)

    def set_attrs(self, literal=None, **attrs):
        """
            Каждый раз готовит новое строковое представление частей тега в html
        """
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        
        attrs = attrs.copy()
        
        if literal is not None:
            attrs['literal'] = literal

        if 'id' in attrs:
            self.id = attrs.pop('id')

        
        self.literal = self._literal(**attrs);                    # Без id
        self.otag = self._otag(self.tag, self.literal, self.id);  # С id если tag не NODE_TEXT
        self.ctag = self._ctag(self.tag)

        self._attrs = attrs

    def get_attrs(self):
        """
            Изменение по ссылке словаря атрибутов не изменит строковое представление (нужно потом делать set_attrs)
        """
        return self._attrs

    def upd_attrs(self, literal=None, **attrs):
        
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        _attrs = self.get_attrs(); _attrs.update(attrs)

        if literal is not None:
            _attrs.update(literal=literal)

        self.set_attrs(**_attrs)
                
    

    @staticmethod
    def _literal(**attrs):
        """
            Рендер того что внутри тега после имени и до закрывающей скобки
        """
        parts = []
        for k, v in attrs.items():
            if k == 'literal':
                # parts.append(tw.dedent(str(v)))
                parts.append(str(v))
                continue

            if k in {'classes', '_class', 'class_', 'class', 'className'}:
                # parts.append(f'class="{tw.dedent(str(v))}"')
                parts.append(f'class="{str(v)}"')
                continue
                
            k = k.replace('_', '-')

            if isinstance(v, bool):
                if v: parts.append(k)
                continue
                
            if isinstance(v, str):
                # parts.append(f'{k}="{tw.dedent(v)}"')
                parts.append(f'{k}="{v}"')
                continue

            # parts.append(f'{k}={tw.dedent(repr(v))}')
            parts.append(f'{k}={repr(v)}')
            
        return ' '.join(parts)

            
    @staticmethod
    def _otag(tag, literal='', tag_id=None):
        """
            Рендер открывающего тега
        """
        if tag in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT}:
            return literal
        else:
            if tag_id is not None:
                tag_id = f'id="{str(tag_id)}"' if not isinstance(tag_id, str) else f'id={tag_id}'
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
        if tag in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT}:
            return ''
        else:
            if tag in Tag.self_closing_tags:
                return ''
            else:
                return f"</{tag}>"


    def __eq__(self, other):        
        if not isinstance(other, Tag): return False
        
        if self.tag in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT}:
            return self.literal == other.literal
        else:
            return (self.tag == other.tag) and (self.literal == other.literal) and (self.id == other.id)

    def __hash__(self):
        if self.tag in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT}:
            return hash(self.literal)
        else:
            # sys.hash_info.modulus == 2**61-1
            return ( hash(self.tag) * 961 + hash(self.literal) * 31 + hash(self.id) ) % 2305843009213693951
            

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

        XXX `id` в систему сравнений хешей не входит (`name` - входит)

        XXX Ссылка на parent в childs утилитарная и слабая

    """

    id_count = itertools.count()

    __slots__ = [
        '__weakref__',

        '_parent',
        '_childs',
    ]

    def __init__(self, tag, literal=None, **attrs):
        
        literal_is_dict = isinstance(literal, dict)
        assert not (literal_is_dict and attrs)
        if literal_is_dict: attrs = literal; literal = None

        if 'id' not in attrs:
            attrs.update(id=next(Cmp.id_count))
            
        literal = self._to_script(literal)
        if 'literal' in attrs:
            attrs['literal'] =  self._to_script(attrs['literal'])
        

        super().__init__(tag, literal, **attrs)


        self._parent = None
        self._childs = []


    def __deepcopy__(self, memo):
        inst = Cmp.__new__(Cmp)

        self_base = super()

        for slot in self_base.__slots__:
            setattr(inst, slot, getattr(self_base, slot))

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
                # return tw.dedent(literal.strip('\r\n'))
                return literal
            else:
                return literal

        source = inspect.getsource(literal)
        
        is_lambda = literal.__name__ == "<lambda>"
        if is_lambda:  # Лямбду нужно запихивать как декларацию и тут-же вызывать
            source = source.strip('\r\n')
            return f"({tw.dedent(source)})()"
            
        # Берем только тело
        
        pos = source.find(':')
        if pos < 0:
            raise SyntaxError(f"{literal} is no function declaration")

        return tw.dedent(source[pos + 1:].strip('\r\n'))


    @staticmethod
    def _to_component(cmp):
        if isinstance(cmp, Cmp):
            return cmp
            
        if isinstance(cmp, str):
            return Cmp(Tag.NODE_TEXT, cmp)

        if callable(cmp):
            return Cmp(Tag.SCRIPT_TEXT, cmp)
            
        raise TypeError(f"{cmp} of unsupported type")
        

    def append(self, cmp):                  # list метод
        assert self.tag not in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT};  # Эти не могут иметь дочерние
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
        assert self.tag not in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT};  # Эти не могут иметь дочерние
        self._childs[child_idx] = (c := self._to_component(cmp)); c._parent = weakref.proxy(self)
        
    def __delitem__(self, child_idx):       # list метод
        del self._childs[child_idx]
    def __len__(self):                      # list метод
        return len(self._childs)
    def __iter__(self):                     # list метод
        return iter(self._childs)


    def insert(self, idx, cmp):             # list метод
        assert self.tag not in {Tag.NODE_TEXT, Tag.SCRIPT_TEXT};  # Эти не могут иметь дочерние
        self._childs.insert(idx, c := self._to_component(cmp)); c._parent = weakref.proxy(self)

        
    def render(self, tabs=''):
        
        parts = [self.otag + '\n']

        for c in self._childs:
            parts.append(c.render('' + '\t'))
    
        if (c := self.ctag):
            parts.append(c + '\n')
        
        return tw.indent(''.join(parts), tabs)
        

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
        

    def _get_dom(self):
        """
            Комонент на вершине иерархии.
            FIXME Можно кешировать поиск, но лучшая практика обновлять dom накопительным итогом в не покомпонентно
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

# ~     async def update(self):
# ~         dom = self._get_dom()
# ~         if hasattr(dom, 'update'):
# ~             await dom.update()


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
    def __init__(self, /, *body_components, static="/", version=None):
        """
            Если `version` не задана то динамические импорты brython-а будут при каждом обновлении страницы
            ( cache: false )
        """

        version = str(version) if version is not None else version
        
        super().__init__('!DOCTYPE', "html")

        self.add(html := Cmp('html')(
        
            head := Cmp('head')(
                Cmp('title')(title := Cmp(Tag.NODE_TEXT, "JustBry")),
                icon := Cmp('link', rel="icon", type="image/png", href = static + "brython.png"),

                Cmp('meta', charset="utf-8"),
                Cmp('meta', name="viewport", content="width=device-width, initial-scale=1"),

                Cmp('script', src = static + "brython.min.js" + (f"?v={version}" if version else "")),
                brylib := Cmp('script', src = static + "brython_stdlib.min.js" + (f"?v={version}" if version else "")),
                # brylib := Cmp('script', src = static + "brython_modules.js" + (f"?v={version}" if version else "")),

                Cmp('link', rel="stylesheet", href = static + "bulma.min.css" + (f"?v={version}" if version else "")),
                Cmp('script', defer=True, src = static + "fontawesome_all.js" + (f"?v={version}" if version else "")),
                
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



