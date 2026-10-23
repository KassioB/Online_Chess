''' Receita local do pygame para o python-for-android (substitui a que vem com ele).

É a mesma receita original (pygame 2.1.0), com um ajuste: os arquivos C de pygame._sdl2 vêm gerados no
repositório do pygame por um Cython antigo (0.29.24), que não compila com o Python 3.11
("longintrepr.h not found" e a mudança nos frames). Aqui eles são apagados e gerados de novo com o
Cython 0.29.37 que o fluxo instala. O módulo "touch" não tem fonte .pyx para regerar e o pygame nem o
importa, então ele sai da lista de módulos. '''

import glob
import os
import subprocess
import sys
from os.path import join

from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class Pygame2Recipe(CompiledComponentsPythonRecipe):
    version = '2.1.0'
    url = 'https://github.com/pygame/pygame/archive/{version}.tar.gz'

    site_packages_name = 'pygame'
    name = 'pygame'

    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf', 'setuptools', 'jpeg', 'png']
    call_hostpython_via_targetpython = False  # Due to setuptools
    install_in_hostpython = False

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            setup_template = open(join("buildconfig", "Setup.Android.SDL2.in")).read()
            env = self.get_recipe_env(arch)
            env['ANDROID_ROOT'] = join(self.ctx.ndk.sysroot, 'usr')

            png = self.get_recipe('png', self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), '.libs')
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe('jpeg', self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            sdl2_mixer_recipe = self.get_recipe('sdl2_mixer', self.ctx)
            for include_dir in sdl2_mixer_recipe.get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            sdl2_image_includes = ""
            sdl2_image_recipe = self.get_recipe('sdl2_image', self.ctx)
            for include_dir in sdl2_image_recipe.get_include_dirs(arch):
                sdl2_image_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I" + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL', 'include') +
                    " -L" + join(self.ctx.bootstrap.build_dir, "libs", str(arch)) +
                    " -L" + png_lib_dir + " -L" + jpeg_lib_dir + " -L" + arch.ndk_lib_dir_versioned),
                sdl_ttf_includes="-I"+join(self.ctx.bootstrap.build_dir, 'jni', 'SDL2_ttf'),
                sdl_image_includes=sdl2_image_includes,
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I"+jpeg_inc_dir,
                png_includes="-I"+png_inc_dir,
                freetype_includes=""
            )
            # sem o módulo touch (veja a explicação no topo do arquivo)
            setup_file = "\n".join(l for l in setup_file.split("\n") if "_sdl2.touch" not in l)
            open("Setup", "w").write(setup_file)

            self.regenerate_cython_sources()

    def regenerate_cython_sources(self):
        generated = os.path.join("src_c", "_sdl2")
        pyx = glob.glob(os.path.join("src_c", "cython", "pygame", "_sdl2", "*.pyx"))
        for path in glob.glob(os.path.join(generated, "*.c")):
            os.remove(path)  # "python setup.py cython" só regera o que estiver ausente ou desatualizado
        # o resto do setup.py (que procura o SDL do desktop) pode falhar depois da etapa do Cython: não importa
        subprocess.call([sys.executable, "setup.py", "cython"])
        missing = [os.path.splitext(os.path.basename(p))[0] for p in pyx
                   if not os.path.isfile(os.path.join(generated, os.path.splitext(os.path.basename(p))[0] + ".c"))]
        if missing:
            raise RuntimeError(f"O Cython não gerou os módulos do pygame._sdl2: {missing}")


recipe = Pygame2Recipe()
