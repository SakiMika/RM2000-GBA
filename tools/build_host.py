#!/usr/bin/env python3
"""Portable clang/LLD ROM builder (mainly for Windows build.bat)."""
from pathlib import Path
import os,sys,subprocess,shutil
root=Path(__file__).resolve().parents[1]
os.chdir(root)
def run(args):
 print('>', ' '.join(map(str,args)),flush=True)
 subprocess.run(list(map(str,args)),check=True)

def exe(default,env):
 val=os.environ.get(env,default)
 if not shutil.which(val):
  raise RuntimeError('Tool missing: '+val+'; set '+env+' to its path')
 return val
try:
 cc=exe('clang','CC'); ld=exe('ld.lld','LD');objcopy=exe('llvm-objcopy','OBJCOPY')
 run([sys.executable,'tools/prepare_sample.py'])
 run([sys.executable,'tools/make_mode4.py'])
 run([sys.executable,'tools/make_font.py'])
 run([sys.executable,'tools/make_hardware_bg.py'])
 run([sys.executable,'tools/make_title.py'])
 (root/'build').mkdir(exist_ok=True)
 target=['-target','armv4t-none-eabi','-mcpu=arm7tdmi','-marm']
 run([cc,*target,'-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fdata-sections','-ffunction-sections','-O2','-c','src/main.c','-o','build/main.o'])
 for name in ['startup','assets']:
  run([cc,*target,'-c','src/'+name+'.s','-o','build/'+name+'.o'])
 run([ld,'-T','linker.ld','--gc-sections','-Map=build/sample.map','-o','build/sample.elf','build/startup.o','build/main.o','build/assets.o'])
 run([objcopy,'-O','binary','build/sample.elf','build/sample.bin'])
 run([sys.executable,'tools/make_rom.py','build/sample.bin','build/sample.gba'])
except (OSError,RuntimeError,subprocess.CalledProcessError) as exc:
 print('BUILD FAILED:',exc,file=sys.stderr);sys.exit(1)
