@echo off
C:\msys64\msys2_shell.cmd -mingw64 -defterm -no-start -c "cd /f/werk-selfrun-kimi/workspace/selfrun && gcc -O3 -static -o run_static.exe tools/llama2c/run.c tools/llama2c/win.c -lm"
