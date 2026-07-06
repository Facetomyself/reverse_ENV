---
name: reverse-engineering
description: CTF/general reverse engineering reference only. In real D:\reverse_ENV projects, start with reverse-coordinator and route APK/native/Web JS/firmware tasks to the dedicated project skills; use this skill only as supporting background when those skills need generic CTF-style techniques. Do not use it as the primary project router, and do not use it for exploitation-only, pure web, forensics, or standalone crypto work unless reversing the implementation is the actual blocker.
license: MIT
compatibility: Requires filesystem-based agent with local D:\reverse_ENV tools. Do not install global packages or upload samples to public services by default.
allowed-tools: Bash Read Write Edit Glob Grep Task
metadata:
  user-invocable: "false"
---

# Reverse Engineering CTF Reference

Quick reference for CTF-style RE challenges. For real project work inside `D:\reverse_ENV`, this skill is reference material only: create or use `workspace\<项目名>\`, start with `reverse-coordinator`, then route APK, native `.so`/PE/ELF, Web JS, proxy, radare2, or IDA work to the dedicated project skill.

External information routing is fixed:

- General external资料/search: use `search-layer`.
- GitHub code, issues, PRs, examples, or release notes: use `github-solution-research`.
- Login-required pages, browser state, or JS-rendered targets: use `ruyi` / `js-reverse-mcp`.
- Do not use WebFetch, and do not upload binaries to public services unless the user explicitly authorizes that exact sample.

## Prerequisites

These are reference notes, not default setup commands. In this repository, prefer already bundled tools under `D:\reverse_ENV\tools\` and the project venv at `D:\reverse_ENV\.venv\`.

**Python packages, only when the task really needs them:**
```powershell
& "D:\reverse_ENV\.venv\Scripts\python.exe" -m pip install frida-tools angr qiling uncompyle6 capstone lief z3-solver
```

**Local project tool examples:**

```powershell
& "D:\reverse_ENV\tools\radare2\bin\radare2.exe" -v
& "D:\reverse_ENV\tools\apktool\apktool.bat" --version
& "D:\reverse_ENV\tools\jadx\bin\jadx.bat" --version
& "D:\reverse_ENV\.venv\Scripts\frida.exe" --version
```

System-level `pip`, `apt`, `brew`, `r2pm`, and ad hoc `git clone` setup commands are external references only and must not be executed by default in `D:\reverse_ENV`. If a source build is unavoidable, clone/build under `D:\reverse_ENV\tools\src\...`, record the source URL and commit/hash, and update the relevant project docs if it becomes a maintained tool.

## Additional Resources

- [tools.md](tools.md) - Static analysis tools (GDB, Ghidra, radare2, IDA, Binary Ninja, local decompiler comparison, RISC-V with Capstone, Unicorn emulation, Python bytecode, WASM, Android APK, .NET, packed binaries)
- [tools-dynamic.md](tools-dynamic.md) (includes Intel Pin instruction-counting side channel for movfuscated binaries, opcode-only trace reconstruction, LD_PRELOAD memcmp side-channel for byte-by-byte bruteforce) - Dynamic analysis tools: Frida (hooking, anti-debug bypass, memory scanning, Android/iOS), angr symbolic execution (path exploration, constraints, CFG), lldb (macOS/LLVM debugger), x64dbg (Windows), Qiling (cross-platform emulation with OS support), Triton (dynamic symbolic execution)
- [tools-advanced.md](tools-advanced.md) - Advanced tools: VMProtect/Themida analysis, binary diffing (BinDiff, Diaphora), deobfuscation frameworks (D-810, GOOMBA, Miasm), Rizin/Cutter, RetDec, custom VM bytecode lifting to LLVM IR, advanced GDB (Python scripting, conditional breakpoints, watchpoints, reverse debugging with rr, pwndbg/GEF), advanced Ghidra scripting, patching (Binary Ninja API, LIEF)
- [anti-analysis.md](anti-analysis.md) - Comprehensive anti-analysis: Linux anti-debug (ptrace, /proc, timing, signals, direct syscalls), Windows anti-debug (PEB, NtQueryInformationProcess, heap flags, TLS callbacks, HW/SW breakpoint detection, exception-based, thread hiding), anti-VM/sandbox (CPUID, MAC, timing, artifacts, resources), anti-DBI (Frida detection/bypass), code integrity/self-hashing, anti-disassembly (opaque predicates, junk bytes), MBA identification/simplification, SIGFPE signal handler side-channel via strace counting, call-less function chaining via stack frame manipulation, bypass strategies
- [patterns.md](patterns.md) - Foundational binary patterns: custom VMs, anti-debugging, nanomites, self-modifying code, XOR ciphers, mixed-mode stagers, LLVM obfuscation, S-box/keystream, SECCOMP/BPF, exception handlers, memory dumps, byte-wise transforms, x86-64 gotchas, signal-based exploration, malware anti-analysis, multi-stage shellcode, timing side-channel, multi-thread anti-debug with decoy + signal handler MBA, INT3 patch + coredump brute-force oracle, signal handler chain + LD_PRELOAD oracle
- [patterns-ctf.md](patterns-ctf.md) - Competition-specific patterns (Part 1): hidden emulator opcodes, LD_PRELOAD key extraction, SPN static extraction, image XOR smoothness, byte-at-a-time cipher, mathematical convergence bitmap, Windows PE XOR bitmap OCR, two-stage RC4+VM loaders, GBA ROM meet-in-the-middle, Sprague-Grundy game theory, kernel module maze solving, multi-threaded VM channels, backdoored shared library detection via string diffing, custom binfmt kernel module with RC4 flat binaries, hash-resolved imports / no-import ransomware, ELF section header corruption for anti-analysis
- [patterns-ctf-2.md](patterns-ctf-2.md) - Competition-specific patterns (Part 2): multi-layer self-decrypting brute-force, embedded ZIP+XOR license, stack string deobfuscation, prefix hash brute-force, CVP/LLL lattice for integer validation, decision tree function obfuscation, GF(2^8) Gaussian elimination, ROP chain obfuscation analysis (ROPfuscation)
- [patterns-ctf-3.md](patterns-ctf-3.md) - Competition-specific patterns (Part 3): Z3 single-line Python circuit, sliding window popcount, keyboard LED Morse code via ioctl, C++ destructor-hidden validation, syscall side-effect memory corruption, MFC dialog event handlers, VM sequential key-chain brute-force, Burrows-Wheeler transform inversion, OpenType font ligature exploitation, GLSL shader VM with self-modifying code, instruction counter as cryptographic state, batch crackme automation via objdump, fork+pipe+dead branch anti-analysis, TensorFlow DNN inversion via sigmoid layer inversion, BPF filter analysis via kernel JIT to x64 assembly
- [languages.md](languages.md) - Language-specific: Python bytecode & opcode remapping, Python version-specific bytecode, Pyarmor static unpack, DOS stubs, Unity IL2CPP, HarmonyOS HAP/ABC, Brainfuck/esolangs (+ BF character-by-character static analysis, BF side-channel read count oracle, BF comparison idiom detection), UEFI, transpilation to C, code coverage side-channel, OPAL functional reversing, non-bijective substitution, FRACTRAN program inversion
- [languages-platforms.md](languages-platforms.md) - Platform/framework-specific: Roblox place file analysis, Godot game asset extraction, Rust serde_json schema recovery, Android JNI RegisterNatives obfuscation, Android DEX runtime bytecode patching via /proc/self/maps, Android native .so loading bypass via new project, Frida Firebase Cloud Functions bypass, Verilog/hardware RE, prefix-by-prefix hash reversal, Ruby/Perl polyglot constraint satisfaction, Electron ASAR extraction + native binary analysis, Node.js npm runtime introspection
- [languages-compiled.md](languages-compiled.md) - Go binary reversing (GoReSym, goroutines, memory layout, channel ops, embed.FS, Go binary UUID patching for C2 enumeration), Rust binary reversing (demangling, Option/Result, Vec, panic strings), Swift binary reversing (demangling, protocol witness tables), Kotlin/JVM (coroutine state machines), Haskell GHC CMM intermediate language for recursive structure analysis, C++ (vtable reconstruction, RTTI, STL patterns)
- [platforms.md](platforms.md) - Platform-specific RE: macOS/iOS (Mach-O, code signing, Objective-C runtime, Swift, dyld, jailbreak bypass), embedded/IoT firmware (binwalk, UART/JTAG/SPI extraction, ARM/MIPS, RTOS), kernel drivers (Linux .ko, eBPF, Windows .sys), game engines (Unreal Engine, Unity, anti-cheat, Lua), automotive CAN bus
- [platforms-hardware.md](platforms-hardware.md) - Hardware and advanced architecture RE: HD44780 LCD controller GPIO reconstruction, RISC-V advanced (custom extensions, privileged modes, debugging), ARM64/AArch64 reversing and exploitation (calling convention, ROP gadgets, qemu-aarch64-static emulation)
- [field-notes.md](field-notes.md) - Quick reference notes: binary types, anti-debugging bypass, specialized patterns, CTF case notes

---

## When to Pivot

- In real `D:\reverse_ENV` projects, pivot first to `reverse-coordinator`; then use `apk-reverse`, `native-reverse`, `ida-reverse`, `radare2`, `ruyi-reverse`, `proxy-usage`, or other dedicated skills according to target type.
- If you already understand the binary and now need heap, ROP, or kernel exploitation, switch to `/ctf-pwn`.
- If the challenge is really about recovering deleted files, PCAP data, or disk artifacts, switch to `/ctf-forensics`.
- If the target is a web app and you are only reversing a small client-side helper script, switch to `/ctf-web`.
- If the binary implements a machine learning model and the challenge is about model attacks or adversarial inputs, switch to `/ctf-ai-ml`.
- If the reversed binary's core logic is a cryptographic algorithm or math problem, switch to `/ctf-crypto`.
- If the binary is a real malware sample with C2, packing, or evasion behavior, switch to `/ctf-malware`.
- If the challenge is a toy VM, encoding puzzle, or pyjail rather than a real binary, switch to `/ctf-misc`.

## Problem-Solving Workflow

1. **Create/use `workspace\<项目名>\` first** - keep binaries, dumps, traces, keys, decrypted blobs, and generated files inside that project directory, not `workspace\` root and not `/tmp`.
2. **Preserve evidence chain** - record input file path, SHA-256, tool/version, command, timestamp, and output path for each claim.
3. **Start with strings extraction** - many easy challenges have plaintext flags.
4. **Try ltrace/strace** - dynamic analysis often reveals flags without reversing.
5. **Try Frida hooking** - hook strcmp/memcmp to capture expected values without reversing.
6. **Try angr/Qiling only when static triage justifies it** - symbolic execution and emulation are powerful but heavier.
7. **Map control flow** before modifying execution.
8. **Automate manual processes** via scripting (r2pipe, Frida, angr, Python), with outputs written under `workspace\<项目名>\`.
9. **Validate assumptions** by comparing local decompiler/disassembler outputs; public upload services require explicit authorization, sample desensitization, hash/time records, and confirmation that the sample is authorized for upload.
10. **Deliver project-mode artifacts** - `report.md`, `findings.json`, and `triage.md`, with unsupported claims marked `待验证`.
11. **Run desensitization review** - redact secrets, tokens, private URLs, real keys, customer data, and live infrastructure details before final output or knowledge-base reuse.

## Quick Wins (Try First!)

```bash
# Plaintext flag extraction
strings binary | grep -E "flag\{|CTF\{|pico"
strings binary | grep -iE "flag|secret|password"
rabin2 -z binary | grep -i "flag"

# Dynamic analysis - often captures flag directly
ltrace ./binary
strace -f -s 500 ./binary

# Hex dump search
xxd binary | grep -i flag

# Run with test inputs
./binary AAAA
echo "test" | ./binary
```

## Initial Analysis

```bash
file binary           # Type, architecture
checksec --file=binary # Security features (for pwn)
chmod +x binary       # Make executable
```

## Memory Dumping Strategy

**Key insight:** Let the program compute the answer, then dump it. Break at final comparison (`b *main+OFFSET`), enter any input of correct length, then `x/s $rsi` to dump computed flag.

## Decoy Flag Detection

**Pattern:** Multiple fake targets before real check. Look for multiple comparison targets in sequence with different success messages. Set breakpoint at FINAL comparison, not earlier ones.

## GDB PIE Debugging

PIE binaries randomize base address. Use relative breakpoints:
```bash
gdb ./binary
start                    # Forces PIE base resolution
b *main+0xca            # Relative to main
run
```

## Comparison Direction (Critical!)

Two patterns: (1) `transform(flag) == stored_target` — reverse the transform. (2) `transform(stored_target) == flag` — flag IS the transformed data, just apply transform to stored target.

## Common Encryption Patterns

- XOR with single byte - try all 256 values
- XOR with known plaintext (`flag{`, `CTF{`)
- RC4 with hardcoded key
- Custom permutation + XOR
- XOR with position index (`^ i` or `^ (i & 0xff)`) layered with a repeating key

## Quick Tool Reference

```powershell
# Radare2
& "D:\reverse_ENV\tools\radare2\bin\radare2.exe" -d "D:\reverse_ENV\workspace\<项目名>\binary"
aaa                # Analyze
afl                # List functions
pdf @ main         # Disassemble main

# IDA project tools
# Use ida-multi-mcp tools with an instance_id: survey_binary, decompile, disasm,
# analyze_function, trace_data_flow.

# Android local tools
& "D:\reverse_ENV\tools\apktool\apktool.bat" d "D:\reverse_ENV\workspace\<项目名>\app.apk" -o "D:\reverse_ENV\workspace\<项目名>\decoded"
& "D:\reverse_ENV\tools\jadx\bin\jadx.bat" -d "D:\reverse_ENV\workspace\<项目名>\jadx" "D:\reverse_ENV\workspace\<项目名>\app.apk"
```

## Deep-Dive Notes

Use [field-notes.md](field-notes.md) after the first round of triage when you know what kind of target you have.

- Target formats: Python bytecode, WASM, Android, Flutter, .NET, UPX, Tauri
- Technique notes: anti-debug bypass, VM analysis, x86-64 gotchas, iterative solvers, Unicorn, timing side channels
- Platform notes: Godot, Roblox, macOS/iOS, embedded firmware, kernel drivers, game engines, Swift, Kotlin, Go, Rust, D
- Case notes: modern CTF-specific reversing patterns and older classic challenge patterns
