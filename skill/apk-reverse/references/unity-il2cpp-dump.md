# Unity IL2CPP 符号提取

## 关键文件

| 文件 | Android | iOS | 说明 |
|------|---------|-----|------|
| Native binary | `lib/arm64-v8a/libil2cpp.so` | `UnityFramework.framework/UnityFramework` | 编译后 native 代码 |
| Metadata | `assets/bin/Data/Managed/Metadata/global-metadata.dat` | `Data/Managed/Metadata/` | 所有类型/方法/字符串 |

## 工具选择

| 工具 | 适用 |
|------|------|
| **roytu/Il2CppDumper** (v39 fork) | Unity 6+, metadata v24-39 |
| Perfare/Il2CppDumper (原版) | Unity 2021 及以前 (≤ v29) |
| SamboyCoding/Cpp2IL | C# 源码重建, IDA 导入不太适用 |

## 工作流

### 1. 定位文件
```bash
# Android
unzip -o app.apk -d apk_out/
BINARY="apk_out/lib/arm64-v8a/libil2cpp.so"
METADATA="apk_out/assets/bin/Data/Managed/Metadata/global-metadata.dat"

# iOS
unzip -o app.ipa -d ipa_out/
BINARY="ipa_out/Payload/*.app/Frameworks/UnityFramework.framework/UnityFramework"
METADATA="ipa_out/Payload/*.app/Data/Managed/Metadata/global-metadata.dat"
```

### 2. 检查版本
```bash
xxd -l 8 "$METADATA"
# af1b b1fa 2700 0000 → magic OK, version 0x27 = 39 (Unity 6)
```

### 3. 运行 Il2CppDumper
```bash
git clone -b v39 https://github.com/roytu/Il2CppDumper.git
cd Il2CppDumper
DOTNET_ROLL_FORWARD=LatestMajor dotnet run \
  --project Il2CppDumper/Il2CppDumper.csproj \
  -c Release -- "$BINARY" "$METADATA" output_dir
```

### 4. 验证输出
| 文件 | 说明 |
|------|------|
| `script.json` | 函数地址 + 名称 (IDA 导入) |
| `dump.cs` | C# 类 dump (快速查阅) |
| `il2cpp.h` | 结构体定义 |
| `ida_py3.py` | IDA 导入脚本 |

### 5. 导入 IDA
1. 打开 `libil2cpp.so` 到 IDA
2. `File → Script file...` → 选 `ida_py3.py`
3. 可选: `File → Load file → Parse C header file...` → `il2cpp.h`

## 常见问题

| 错误 | 原因 | 解决 |
|------|------|------|
| `not supported version[39]` | 原版不支持 | 切 roytu v39 fork |
| SIGKILL (macOS) | 未签名 | `codesign -s - <binary>` |
| 空输出 | binary/metadata 不匹配 | 确认同一版本提取 |
