import os
import PyInstaller.__main__

script_path = os.path.join(os.getcwd(), "run.py")
icon_path = os.path.join(os.getcwd(), "assets\\icon.ico")
output_dir = os.path.join(os.getcwd(), "dist")

PyInstaller.__main__.run([
    script_path,
    '--onefile',
    '--windowed',
    '--icon=' + icon_path,
    '--add-data', f'{icon_path};.',
    '--distpath', output_dir,
    '--name', 'Vextract-winx64',
])
