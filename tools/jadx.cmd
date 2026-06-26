@echo off
set JAVA_HOME=%~dp0jdk
set PATH=%JAVA_HOME%\bin;%PATH%
call "%~dp0jadx\bin\jadx.bat" %*
