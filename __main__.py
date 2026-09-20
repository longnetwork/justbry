#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, importlib, shutil, requests


try:
    import config as u_config;               # Пользовательский
except ModuleNotFoundError:
    u_config = None

try:
    from justbry import config as jb_config;  # Пакетный
except ModuleNotFoundError:
    jb_config = None
        


if __name__ == '__main__':
    """
        Обновление ресурсов

        python -m justbry -h

        XXX `python -m justbry optimize` генерит brython_modules.js только по содержимому файлов в `static/py/`
            (неявные импорты должны быть явно предусмотрены в `static/py/__init__.py`)
            
    """

    STATIC_PATH = 'static'

    try: os.makedirs(STATIC_PATH)
    except: pass



    BRYTHON_VERSION = getattr(u_config, 'BRYTHON_VERSION', getattr(jb_config, 'BRYTHON_VERSION', '3.14.3'))
    BRYTHON_LINKS = [
        f"https://cdnjs.cloudflare.com/ajax/libs/brython/{BRYTHON_VERSION}/brython.min.js",
        f"https://cdnjs.cloudflare.com/ajax/libs/brython/{BRYTHON_VERSION}/brython_stdlib.min.js",
        # f"https://cdnjs.cloudflare.com/ajax/libs/brython/{BRYTHON_VERSION}/brython_stdlib.js",
    ]

    BULMA_VERSION = getattr(u_config, 'BULMA_VERSION', getattr(jb_config, 'BULMA_VERSION', '1.0.2'))
    BULMA_LINKS = [
        f"https://cdn.jsdelivr.net/npm/bulma@{BULMA_VERSION}/css/bulma.min.css",
    ]

    FONTAWESOME_VERSION = getattr(u_config, 'FONTAWESOME_VERSION', getattr(jb_config, 'FONTAWESOME_VERSION', '6.6.0'))
    FONTAWESOME_LINKS = [
        # f"https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{FONTAWESOME_VERSION}/css/fontawesome.min.css"
        f"https://use.fontawesome.com/releases/v{FONTAWESOME_VERSION}/js/all.js"
    ]


    PICOCSS_VERSION = getattr(u_config, 'PICOCSS_VERSION', getattr(jb_config, 'PICOCSS_VERSION', '2.1.1'))
    PICOCSS_LINKS = [
        f"https://cdn.jsdelivr.net/npm/@picocss/pico@{PICOCSS_VERSION}/css/pico.min.css"
    ]


    REMIXICON_VERSION = getattr(u_config, 'REMIXICON_VERSION', getattr(jb_config, 'REMIXICON_VERSION', '4.9.1'))
    REMIXICON_LINKS = [
        f"https://cdn.jsdelivr.net/npm/remixicon@{REMIXICON_VERSION}/fonts/remixicon.min.css",
        f"https://cdn.jsdelivr.net/npm/remixicon@{REMIXICON_VERSION}/fonts/remixicon.woff2",
        f"https://cdn.jsdelivr.net/npm/remixicon@{REMIXICON_VERSION}/fonts/remixicon.woff",
    ]


    import argparse
    
    parser = argparse.ArgumentParser(description="JustBry Tools", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    subparsers = parser.add_subparsers(dest='command', help="See help: command -h")
    if subparsers:
        _brython = subparsers.add_parser('brython', description="Download Brython Engine")
        _brython.add_argument('links', type=str, nargs='*', default=BRYTHON_LINKS, help="Bruthon Links (space-separated)")


        _bulma = subparsers.add_parser('bulma', description="Download Bulma CSS")
        _bulma.add_argument('links', type=str, nargs='*', default=BULMA_LINKS, help="Bulma Links (space-separated)")

        _fas = subparsers.add_parser('fas', description="Download FontAwesome CSS")
        _fas.add_argument('links', type=str, nargs='*', default=FONTAWESOME_LINKS, help="FontAwesome Links (space-separated)")


        _picocss = subparsers.add_parser('picocss', description="Download Pico CSS")
        _picocss.add_argument('links', type=str, nargs='*', default=PICOCSS_LINKS, help="Pico Links (space-separated)")

        _remixicon = subparsers.add_parser('ri', description="Download RemixIcon Pack")
        _remixicon.add_argument('links', type=str, nargs='*', default=REMIXICON_LINKS, help="RemixIcon Pack Links (space-separated)")

        

        _optimize = subparsers.add_parser('optimize',
                                          description="Generate brython_modules.js to Replace brython_stdlib.js",
                                          help=f'pip install brython=="{BRYTHON_VERSION}" required'
                                          )


    args = parser.parse_args()

    if args.command == 'brython':
        BRYTHON_LINKS = args.links or BRYTHON_LINKS
        print(f"{BRYTHON_LINKS=}")
        
        for link in BRYTHON_LINKS:
            with requests.get(link, timeout=(6, 60)) as rx, open(os.path.join(STATIC_PATH, os.path.basename(link)), 'wb') as f:
                f.write(rx.content)


    if args.command == 'bulma':
        BULMA_LINKS = args.links or BULMA_LINKS
        print(f"{BULMA_LINKS=}")
        
        for link in BULMA_LINKS:
            with requests.get(link, timeout=(6, 60)) as rx, open(os.path.join(STATIC_PATH, os.path.basename(link)), 'wb') as f:
                f.write(rx.content)


    if args.command == 'fas':
        FONTAWESOME_LINKS = args.links or FONTAWESOME_LINKS
        print(f"{FONTAWESOME_LINKS=}")
        
        for link in FONTAWESOME_LINKS:
            with requests.get(link, timeout=(6, 60)) as rx, open(os.path.join(STATIC_PATH, "fontawesome_" + os.path.basename(link)), 'wb') as f:
                f.write(rx.content)        

    if args.command == 'picocss':
        PICOCSS_LINKS = args.links or PICOCSS_LINKS
        print(f"{PICOCSS_LINKS=}")
        
        for link in PICOCSS_LINKS:
            with requests.get(link, timeout=(6, 60)) as rx, open(os.path.join(STATIC_PATH, os.path.basename(link)), 'wb') as f:
                f.write(rx.content)

    if args.command == 'ri':
        REMIXICON_LINKS = args.links or REMIXICON_LINKS
        print(f"{REMIXICON_LINKS=}")
        
        for link in REMIXICON_LINKS:
            with requests.get(link, timeout=(6, 60)) as rx, open(os.path.join(STATIC_PATH, os.path.basename(link)), 'wb') as f:
                f.write(rx.content)       



    if args.command == 'optimize':
        try:
            try:
                import brython

                assert brython.__version__ == BRYTHON_VERSION

                brython_data = importlib.resources.files('brython.data')
                
            except ModuleNotFoundError:
                raise ModuleNotFoundError(f'Requires: pip install brython=="{BRYTHON_VERSION}"') from None
        
            brython_stdlib_path = brython_data.joinpath('brython_stdlib.js')

            wrk_dir = os.getcwd()
            
            tmp_stdlib_path = os.path.join(wrk_dir, STATIC_PATH, 'py', 'brython_stdlib.js')
            out_path = os.path.join(wrk_dir, STATIC_PATH)
            

            shutil.copy(brython_stdlib_path, tmp_stdlib_path)
            
            os.chdir(os.path.join(out_path, 'py')); error = os.system("brython-cli make_modules")

            if not error:
                shutil.move(os.path.join(out_path, 'py', 'brython_modules.js'), os.path.join(out_path, 'brython_modules.js'))


        finally:
            try:
                os.remove(tmp_stdlib_path)
            except:
                pass

        














        
