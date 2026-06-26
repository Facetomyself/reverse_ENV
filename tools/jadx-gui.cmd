@echo off
REM Launch jadx-gui with jadx-ai-mcp plugin loaded
REM The plugin listens on port 8650 for MCP server communication
set JAVA_HOME=%~dp0jdk
set PATH=%JAVA_HOME%\bin;%PATH%
echo Starting jadx-gui with jadx-ai-mcp plugin (port 8650)...
start "jadx-gui" /B "%~dp0jadx\bin\jadx-gui.bat" %*
echo jadx-gui started. Open an APK, then MCP tools are ready.
