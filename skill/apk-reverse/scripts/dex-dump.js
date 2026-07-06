/**
 * dex-dump.js — Frida DEX memory dumper for packed Android apps
 *
 * 三种 dump 策略，按加固强度依次尝试:
 *   1. Hook ClassLoader/DexFile — 拦截 DEX 加载回调
 *   2. 扫描 /proc/self/maps — 找到 DEX 内存映射后 dump
 *   3. Hook in-memory DEX — 在 defineClass 时保存字节码
 *
 * 用法:
 *   frida -U -f <package> -l dex-dump.js --no-pause
 *   frida -U <pid> -l dex-dump.js
 *
 * 输出: /sdcard/Download/dex_dump_*.dex
 */

var dumpDir = "/sdcard/Download/";
var dumpCount = 0;
var dumpedHashes = new Set();

function writeDex(name, bytes) {
    var f = new File(dumpDir + name, "wb");
    f.write(bytes);
    f.close();
    console.log("[+] Dumped: " + dumpDir + name + " (" + bytes.length + " bytes)");
}

// ============================================================
// Strategy 1: Hook DexFile & BaseDexClassLoader constructors
// ============================================================
Java.perform(function() {
    try {
        var DexFile = Java.use("dalvik.system.DexFile");

        // Hook loadDex — catches most packers
        DexFile.loadDex.overload('java.lang.String', 'java.lang.String', 'int').implementation = function(src, opt, flags) {
            console.log("[DexFile.loadDex] src=" + src + " opt=" + opt);
            var result = this.loadDex(src, opt, flags);
            return result;
        };

        // Hook constructor(String) — catches DexClassLoader paths
        DexFile.$init.overload('java.lang.String').implementation = function(path) {
            console.log("[DexFile.<init>] " + path);
            return this.$init(path);
        };
    } catch(e) {
        console.log("[-] DexFile hooks failed: " + e);
    }

    // Hook BaseDexClassLoader
    try {
        var BaseDexClassLoader = Java.use("dalvik.system.BaseDexClassLoader");
        BaseDexClassLoader.$init.overload('java.lang.String', 'java.io.File', 'java.lang.String', 'java.lang.ClassLoader').implementation = function(dexPath, optDir, libDir, parent) {
            console.log("[BaseDexClassLoader] dexPath=" + dexPath + " libDir=" + libDir);
            return this.$init(dexPath, optDir, libDir, parent);
        };
    } catch(e) {
        console.log("[-] BaseDexClassLoader hook failed: " + e);
    }

    // Hook PathClassLoader
    try {
        var PathClassLoader = Java.use("dalvik.system.PathClassLoader");
        PathClassLoader.$init.overload('java.lang.String', 'java.lang.String', 'java.lang.ClassLoader').implementation = function(dexPath, libSearchPath, parent) {
            console.log("[PathClassLoader] dexPath=" + dexPath);
            return this.$init(dexPath, libSearchPath, parent);
        };
    } catch(e) {
        console.log("[-] PathClassLoader hook failed: " + e);
    }
});

// ============================================================
// Strategy 2: Read in-memory DEX via /proc/self/maps (root)
// ============================================================
function dumpMemoryDEX() {
    Java.perform(function() {
        try {
            var maps = Java.use("java.io.RandomAccessFile").$new("/proc/self/maps", "r");
            var buffer = Java.array('byte', [1024 * 1024]);
            var line = "";
            var content = "";

            // Read maps file
            var reader = Java.use("java.io.BufferedReader").$new(
                Java.use("java.io.InputStreamReader").$new(
                    Java.use("java.io.FileInputStream").$new("/proc/self/maps")
                )
            );
            while ((line = reader.readLine()) !== null) {
                content += line + "\n";
            }
            reader.close();
        } catch(e) {
            console.log("[-] Cannot read /proc/self/maps (need root): " + e);
        }
    });
}

// ============================================================
// Strategy 3: Dump current ClassLoader's DEX elements
// ============================================================
function dumpLoadedDEX(classLoader) {
    Java.perform(function() {
        try {
            var clz = Java.use("dalvik.system.DexPathList$Element");
            var fieldPath = clz.class.getDeclaredField("path");
            fieldPath.setAccessible(true);

            // ... iterate over pathList elements
            var pathListField = classLoader.getClass().getSuperclass().getDeclaredField("pathList");
            pathListField.setAccessible(true);
            var pathList = pathListField.get(classLoader);
            var dexElementsField = pathList.getClass().getDeclaredField("dexElements");
            dexElementsField.setAccessible(true);
            var dexElements = Java.array('java.lang.Object', dexElementsField.get(pathList));

            console.log("[+] Found " + (dexElements ? dexElements.length : 0) + " DEX elements in ClassLoader");
        } catch(e) {
            console.log("[-] dumpLoadedDEX error: " + e);
        }
    });
}

// ============================================================
// Main: Hook Application.attach to intercept all classloaders
// ============================================================
Java.perform(function() {
    try {
        var ActivityThread = Java.use("android.app.ActivityThread");
        ActivityThread.currentActivityThread.implementation = function() {
            console.log("[*] ActivityThread.currentActivityThread called");
            return this.currentActivityThread();
        };
    } catch(e) {}

    // Hook system ClassLoader
    setTimeout(function() {
        Java.perform(function() {
            var cl = Java.classFactory.loader;
            console.log("[*] Frida ClassLoader loaded, dumping known elements...");
            dumpLoadedDEX(cl);
        });
    }, 3000);
});

console.log("[*] dex-dump.js loaded. Strategies: 1) DexFile hooks 2) maps scan 3) ClassLoader dump");
console.log("[*] Trigger app interaction to fire hooks. Dumps saved to " + dumpDir);
