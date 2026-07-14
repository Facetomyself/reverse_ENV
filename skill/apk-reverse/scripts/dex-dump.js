/**
 * dex-dump.js — observation-only DEX/ClassLoader trace for packed Android apps.
 *
 * Capabilities:
 *   - trace DexFile.loadDex and file-backed class-loader construction;
 *   - trace InMemoryDexClassLoader construction;
 *   - inspect registered dexElements after Application.attach.
 *
 * This script never reads or writes DEX bytes. Use dump-dex.ps1 for the
 * validated panda whole-DEX export route.
 */

'use strict';

function safeText(value) {
    try {
        return value === null || value === undefined ? '<null>' : value.toString();
    } catch (_) {
        return '<unprintable>';
    }
}

function inspectDexElements(loader, reason) {
    if (loader === null || loader === undefined) return;

    try {
        let klass = loader.getClass();
        let pathListField = null;
        while (klass !== null) {
            try {
                pathListField = klass.getDeclaredField('pathList');
                break;
            } catch (_) {
                klass = klass.getSuperclass();
            }
        }

        if (pathListField === null) {
            console.log('[loader] ' + reason + ' class=' + loader.getClass().getName() + ' pathList=<not-found>');
            return;
        }

        pathListField.setAccessible(true);
        const pathList = pathListField.get(loader);
        const elementsField = pathList.getClass().getDeclaredField('dexElements');
        elementsField.setAccessible(true);
        const elements = elementsField.get(pathList);
        const count = elements === null ? 0 : elements.length;
        console.log('[loader] ' + reason + ' class=' + loader.getClass().getName() + ' dexElements=' + count);
        for (let i = 0; i < Math.min(count, 20); i++) {
            console.log('  [' + i + '] ' + safeText(elements[i]));
        }
        if (count > 20) console.log('  ... ' + (count - 20) + ' more elements');
    } catch (error) {
        console.log('[loader] inspection failed for ' + reason + ': ' + error);
    }
}

Java.perform(function () {
    try {
        const DexFile = Java.use('dalvik.system.DexFile');
        const loadDex = DexFile.loadDex.overload('java.lang.String', 'java.lang.String', 'int');
        loadDex.implementation = function (sourcePath, outputPath, flags) {
            console.log('[DexFile.loadDex] source=' + sourcePath + ' output=' + outputPath + ' flags=' + flags);
            return loadDex.call(this, sourcePath, outputPath, flags);
        };
    } catch (error) {
        console.log('[DexFile.loadDex] hook unavailable: ' + error);
    }

    try {
        const DexClassLoader = Java.use('dalvik.system.DexClassLoader');
        const init = DexClassLoader.$init.overload(
            'java.lang.String',
            'java.lang.String',
            'java.lang.String',
            'java.lang.ClassLoader'
        );
        init.implementation = function (dexPath, optimizedDirectory, librarySearchPath, parent) {
            console.log('[DexClassLoader] dexPath=' + dexPath + ' libPath=' + librarySearchPath);
            const result = init.call(this, dexPath, optimizedDirectory, librarySearchPath, parent);
            inspectDexElements(this, 'DexClassLoader.<init>');
            return result;
        };
    } catch (error) {
        console.log('[DexClassLoader] hook unavailable: ' + error);
    }

    try {
        const InMemoryDexClassLoader = Java.use('dalvik.system.InMemoryDexClassLoader');
        InMemoryDexClassLoader.$init.overloads.forEach(function (overload) {
            overload.implementation = function () {
                const signature = overload.argumentTypes.map(function (type) { return type.className; }).join(', ');
                console.log('[InMemoryDexClassLoader] constructor=(' + signature + ')');
                const result = overload.apply(this, arguments);
                inspectDexElements(this, 'InMemoryDexClassLoader.<init>');
                return result;
            };
        });
    } catch (error) {
        console.log('[InMemoryDexClassLoader] unavailable on this Android version: ' + error);
    }

    try {
        const Application = Java.use('android.app.Application');
        const attach = Application.attach.overload('android.content.Context');
        attach.implementation = function (context) {
            const result = attach.call(this, context);
            const loader = context.getClassLoader();
            console.log('[Application.attach] package=' + context.getPackageName());
            inspectDexElements(loader, 'Application.attach');
            return result;
        };
    } catch (error) {
        console.log('[Application.attach] hook failed: ' + error);
    }
});

console.log('[*] dex-dump.js loaded: observation only; no DEX bytes will be exported');
