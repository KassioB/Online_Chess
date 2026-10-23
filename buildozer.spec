[app]
title = Pawnthon Chess
package.name = pawnthonchess
package.domain = br.kassiobc

# o cliente pygame fica em web/pawnthon (o pygbag usa a subpasta build, que não entra no aplicativo)
source.dir = web/pawnthon
source.include_exts = py,png,ttf,txt
source.exclude_dirs = build,__pycache__

version = 1.0.0
# pygame roda sobre SDL2; o "websockets" (Python puro) substitui o aiohttp, que não compila no Android,
# e o certifi traz os certificados para o wss:// do Render funcionar
requirements = python3,pygame,websockets,certifi,openssl

icon.filename = %(source.dir)s/img/logo_mark.png
presplash.filename = %(source.dir)s/img/logo_mark.png
android.presplash_color = #00183a

orientation = portrait
fullscreen = 1

android.permissions = INTERNET
# versões fixas: o python-for-android mais novo usa o Python 3.14, com o qual a receita do pygame não compila
p4a.branch = v2024.01.21
# receita própria do pygame (regera os arquivos Cython que não compilam no Python 3.11)
p4a.local_recipes = ./p4a-recipes
android.ndk = 25b
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 0
