# Frida 脚本最佳实践

## 关键规则

1. **不用 `--no-pause`** — 现代 Frida CLI spawn 后自动恢复
2. **加载事件驱动优于轮询**
3. **指针/缓冲区输出用 `hexdump()`**

## Module 加载时机

**不要假设 .so 已加载。** 优先顺序:

1. Hook `android_dlopen_ext` 或 `dlopen`，加载时安装 hook
2. 立即检查 `Process.findModuleByName()` (已加载的模块)
3. 轮询仅作 fallback

### 标准 loader hook 模板

```javascript
function hookModuleLoad(moduleName, callback) {
    const dlopen = Module.findExportByName(null, "android_dlopen_ext")
        || Module.findExportByName(null, "dlopen");
    const hooked = new Set();

    Interceptor.attach(dlopen, {
        onEnter(args) {
            this.path = args[0].readCString();
            this.shouldHook = this.path && this.path.includes(moduleName);
        },
        onLeave(retval) {
            if (!this.shouldHook || retval.isNull()) return;
            const mod = Process.findModuleByName(moduleName);
            if (!mod || hooked.has(mod.base.toString())) return;
            hooked.add(mod.base.toString());
            callback(mod);
        }
    });
}

// 加载时或已加载
function hookNowOrOnLoad(moduleName, callback) {
    const mod = Process.findModuleByName(moduleName);
    if (mod) { callback(mod); return; }
    hookModuleLoad(moduleName, callback);
}
```

## 禁止盲 Hook init 系列函数

**不要随便 Hook `.init`, `.init_array`, `JNI_OnLoad`** — 这些是脆弱点:

- 可能 crash 进程（一次性初始化被打断）
- 改变时序隐藏目标行为
- constructor 代码会扇出到大量无关函数

**Hook init 前必须:**
1. 说明为什么不 Hook 普通导出函数
2. 精确定位要 Hook 的具体地址/函数名
3. 告知用户可能 crash
4. 告知如何验证 Hook 没破坏初始化

**钩子优先级:**
1. `< 加载后稳定导出函数
2. `RegisterNatives`, `dlsym`, 首个业务函数
3. `JNI_OnLoad` (仅当 native 注册/反调试在这里)
4. constructor / `.init_array` (仅当有强证据)

## 反调试 constructor 分析

不要盲目 Hook 每个 `.init_array`，先 Hook dispatcher:

```
1. hookModuleLoad("libtarget.so")
2. 确认进程是否在 constructor 执行期间终止
3. 是 → Hook call_constructors / call_array (如果导出)
4. 逐一记录每个 constructor 地址
5. 定位反调试 constructor, 精确 patch
```

## Module & Symbol 现代 API

```javascript
const mod = Process.getModuleByName("libssl.so");
mod.name; mod.base; mod.size; mod.path;
const ptr = mod.getExportByName("SSL_read");
Module.getExportByName(null, "open");  // 全局搜索
Process.enumerateModules();            // 枚举所有模块
```

## Interceptor 模板

```javascript
Interceptor.attach(ptr, {
    onEnter(args) {
        console.log("arg0:", args[0].readUtf8String());
        console.log(hexdump(args[1], { offset:0, length:64 }));
    },
    onLeave(retval) {
        console.log("ret:", retval);
    }
});
```

## Memory 操作

```javascript
ptr(addr).readByteArray(size);
ptr(addr).readUtf8String();
ptr(addr).readU32(); ptr(addr).readPointer();
ptr(addr).writeByteArray(bytes);
Memory.scan(mod.base, mod.size, "48 89 5C ??", {
    onMatch(addr, size) { console.log("found:", addr); },
    onComplete() {}
});
```
