# radare2 速查表

## 基础侦察

```powershell
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -I sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -S sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -i sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -E sample.exe
D:\reverse_ENV\tools\radare2\bin\rabin2.exe -zz sample.exe
```

## 进入交互

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe sample.exe
```

```text
aaa
afl
iz
iS
is
s entry0
pdf
q
```

## 字符串和引用

```text
iz~http
iz~error
axt <addr>
s <addr>
pdf
```

## 常用查看

```text
px 64
pd 20
psz
pxa
```

## patch

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe -w sample.exe
```

```text
s 0x401000
wa nop
wx 9090
wq
```

## 非交互模式

```powershell
D:\reverse_ENV\tools\radare2\bin\radare2.exe -A -q -c "afl;iz;ii;q" sample.exe
```

## 其他工具

### rasm2

```powershell
D:\reverse_ENV\tools\radare2\bin\rasm2.exe -d "9090"
D:\reverse_ENV\tools\radare2\bin\rasm2.exe -a x86 -b 64 "xor eax, eax"
```

### radiff2

```powershell
D:\reverse_ENV\tools\radare2\bin\radiff2.exe old.exe new.exe
D:\reverse_ENV\tools\radare2\bin\radiff2.exe -C old.exe new.exe
```

### rahash2

```powershell
D:\reverse_ENV\tools\radare2\bin\rahash2.exe -a md5 sample.exe
D:\reverse_ENV\tools\radare2\bin\rahash2.exe -a sha256 sample.exe
```

### rax2

```powershell
D:\reverse_ENV\tools\radare2\bin\rax2.exe 0x401000
D:\reverse_ENV\tools\radare2\bin\rax2.exe 4198400
D:\reverse_ENV\tools\radare2\bin\rax2.exe -s hello
```
