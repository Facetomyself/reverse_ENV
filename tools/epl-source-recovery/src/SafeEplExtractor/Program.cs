using QIQI.EProjectFile;
using QIQI.EProjectFile.Expressions;
using QIQI.EProjectFile.Sections;
using System.Collections;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private static int Main(string[] args)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        if (args.Length != 2)
        {
            Console.Error.WriteLine("Usage: SafeEplExtractor <input.e> <output-directory>");
            return 2;
        }

        var inputPath = Path.GetFullPath(args[0]);
        var outputRoot = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(outputRoot);

        var document = new EplDocument();
        using (var stream = File.OpenRead(inputPath))
        {
            document.Load(stream);
        }

        var system = document.GetOrNull(ESystemInfoSection.Key);
        var projectConfig = document.GetOrNull(ProjectConfigSection.Key);
        var code = document.Get(CodeSection.Key);
        var resources = document.Get(ResourceSection.Key);
        var dependencies = document.GetOrNull(ECDependenciesSection.Key);
        var initEc = document.GetOrNull(InitECSection.Key);
        var nameMap = new IdToNameMap(document);

        var sourceRoot = Path.Combine(outputRoot, "source");
        var classRoot = Path.Combine(sourceRoot, "classes");
        var orphanRoot = Path.Combine(sourceRoot, "orphan-methods");
        var resourceRoot = Path.Combine(outputRoot, "resources");
        var failedRoot = Path.Combine(outputRoot, "failed-methods");
        Directory.CreateDirectory(classRoot);
        Directory.CreateDirectory(orphanRoot);
        Directory.CreateDirectory(resourceRoot);
        Directory.CreateDirectory(failedRoot);

        var inputBytes = File.ReadAllBytes(inputPath);
        var inputSha256 = Hex(SHA256.HashData(inputBytes));
        var methodsById = code.Methods.ToDictionary(method => method.Id);
        var claimedMethodIds = new HashSet<int>();
        var methodErrors = new List<object>();
        var resourceManifest = new List<object>();
        var combined = new StringBuilder();

        AppendHeader(combined, inputPath, inputSha256, system, projectConfig, code);
        AppendDefinitions(combined, nameMap, code.GlobalVariables, "全局变量");

        foreach (var classInfo in code.Classes)
        {
            var classText = new StringBuilder();
            AppendTextCode(classText, writer => classInfo.ToTextCode(nameMap, writer, 0, null),
                $"class 0x{classInfo.Id:X8}");
            classText.Append("\n");

            foreach (var methodId in classInfo.Methods ?? new List<int>())
            {
                claimedMethodIds.Add(methodId);
                if (!methodsById.TryGetValue(methodId, out var method))
                {
                    classText.Append($"' [safe-parser] 缺失方法对象: 0x{methodId:X8}\n\n");
                    continue;
                }
                classText.Append(RenderMethod(method, nameMap, failedRoot, methodErrors));
                classText.Append("\n\n");
            }

            var classFileName = $"C_{classInfo.Id:X8}_{SafeFileName(classInfo.Name)}.ecode";
            WriteUtf8Lf(Path.Combine(classRoot, classFileName), classText.ToString());
            combined.Append(classText);
            combined.Append("\n");
        }

        foreach (var method in code.Methods.Where(method => !claimedMethodIds.Contains(method.Id)))
        {
            var text = RenderMethod(method, nameMap, failedRoot, methodErrors);
            var fileName = $"M_{method.Id:X8}_{SafeFileName(method.Name)}.ecode";
            WriteUtf8Lf(Path.Combine(orphanRoot, fileName), text);
            combined.Append("' [未归属程序集的方法]\n");
            combined.Append(text);
            combined.Append("\n\n");
        }

        AppendDefinitions(combined, nameMap, code.DllDeclares, "DLL 命令");
        AppendDefinitions(combined, nameMap, code.Structs, "数据类型");

        var constantText = new StringBuilder();
        foreach (var constant in resources.Constants)
        {
            if (constant.Value is byte[] bytes)
            {
                var resource = WriteBinaryResource(resourceRoot, constant.Id, constant.Name, bytes);
                resourceManifest.Add(new
                {
                    id = IdHex(constant.Id),
                    kind = ResourceKind(constant.Id),
                    constant.Name,
                    constant.Comment,
                    constant.Public,
                    constant.Hidden,
                    length = bytes.Length,
                    sha256 = Hex(SHA256.HashData(bytes)),
                    path = RelativeUnix(outputRoot, resource),
                    executed = false,
                });
                constantText.Append($"' [二进制资源] {nameMap.GetUserDefinedName(constant.Id)} -> {RelativeUnix(outputRoot, resource)}\n");
                continue;
            }

            if (constant.LongText && constant.Value is string longText)
            {
                var path = Path.Combine(resourceRoot, $"R_{constant.Id:X8}_{SafeFileName(constant.Name)}.txt");
                WriteUtf8Lf(path, longText);
                resourceManifest.Add(new
                {
                    id = IdHex(constant.Id),
                    kind = "long-text",
                    constant.Name,
                    constant.Comment,
                    constant.Public,
                    constant.Hidden,
                    length = Encoding.UTF8.GetByteCount(longText),
                    sha256 = Hex(SHA256.HashData(Encoding.UTF8.GetBytes(longText))),
                    path = RelativeUnix(outputRoot, path),
                    executed = false,
                });
            }

            AppendTextCode(constantText, writer => constant.ToTextCode(nameMap, writer, 0),
                $"constant 0x{constant.Id:X8}");
            constantText.Append("\n");
        }
        WriteUtf8Lf(Path.Combine(sourceRoot, "constants.ecode"), constantText.ToString());
        combined.Append("' ===== 常量与资源 =====\n");
        combined.Append(constantText);
        combined.Append("\n");

        WriteUtf8Lf(Path.Combine(sourceRoot, "all.ecode"), combined.ToString());

        WriteJson(Path.Combine(outputRoot, "project_metadata.json"), new
        {
            input = inputPath,
            inputSha256,
            fileSize = inputBytes.Length,
            encoding = document.DetermineEncoding().WebName,
            system = system == null ? null : new
            {
                eSystemVersion = system.ESystemVersion?.ToString(),
                system.Language,
                projectFormatVersion = system.EProjectFormatVersion?.ToString(),
                system.FileType,
                system.ProjectType,
            },
            project = projectConfig == null ? null : new
            {
                projectConfig.Name,
                projectConfig.Description,
                projectConfig.Author,
                projectConfig.ZipCode,
                projectConfig.Address,
                projectConfig.TelephoneNumber,
                projectConfig.FaxNumber,
                projectConfig.Email,
                projectConfig.Homepage,
                projectConfig.Copyright,
                version = projectConfig.Version?.ToString(),
                projectConfig.WriteVersion,
                projectConfig.CompilePlugins,
                projectConfig.ExportPublicClassMethod,
            },
            counts = new
            {
                sections = document.Sections.Count,
                libraries = code.Libraries?.Length ?? 0,
                classes = code.Classes?.Count ?? 0,
                methods = code.Methods?.Count ?? 0,
                globalVariables = code.GlobalVariables?.Count ?? 0,
                structs = code.Structs?.Count ?? 0,
                dllDeclares = code.DllDeclares?.Count ?? 0,
                forms = resources.Forms?.Count ?? 0,
                constants = resources.Constants?.Count ?? 0,
                ecDependencies = dependencies?.ECDependencies?.Count ?? 0,
                methodParseErrors = methodErrors.Count,
            },
            code = new
            {
                allocatedIdNum = code.AllocatedIdNum,
                flag = code.Flag,
                mainMethod = IdHex(code.MainMethod),
                debugCommandParameters = code.DebugCommandParameters,
            },
            initialModules = initEc == null ? null : new
            {
                names = initEc.ECName,
                methods = initEc.InitMethod?.Select(IdHex),
            },
            sections = document.Sections.Select(section => new
            {
                key = $"0x{section.SectionKey:X8}",
                section.SectionName,
                section.IsOptional,
                runtimeType = section.GetType().FullName,
            }),
            safety = new
            {
                targetExecuted = false,
                embeddedResourceExecuted = false,
                supportLibraryLoaded = false,
                externalHelperProcessStarted = false,
                parserBuild = "OpenEpl/EProjectFile v1.9.4 source, locally patched safe build",
            },
        });

        WriteJson(Path.Combine(outputRoot, "libraries.json"), (code.Libraries ?? Array.Empty<LibraryRefInfo>()).Select((library, index) => new
        {
            index,
            library.FileName,
            library.GuidString,
            version = library.Version?.ToString(),
            library.Name,
            library.MinRequiredCmd,
            library.MinRequiredDataType,
            library.MinRequiredConstant,
            metadataResolved = false,
            reason = "safe build intentionally disables support-library helper execution",
        }));

        WriteJson(Path.Combine(outputRoot, "ec_dependencies.json"),
            (dependencies?.ECDependencies ?? new List<ECDependencyInfo>()).Select(dependency => new
            {
                dependency.InfoVersion,
                dependency.FileSize,
                dependency.FileLastModifiedDate,
                dependency.ReExport,
                dependency.Name,
                dependency.Path,
                definedIds = dependency.DefinedIds?.Select(range => new
                {
                    start = IdHex(range.Start),
                    range.Count,
                }),
            }));

        WriteJson(Path.Combine(outputRoot, "symbols.json"), nameMap.UserDefinedName
            .OrderBy(pair => unchecked((uint)pair.Key))
            .Select(pair => new { id = IdHex(pair.Key), name = pair.Value }));

        WriteJson(Path.Combine(outputRoot, "methods.json"), code.Methods.Select(method => new
        {
            id = IdHex(method.Id),
            classId = IdHex(method.Class),
            method.Name,
            method.Comment,
            method.Flags,
            method.Public,
            method.Hidden,
            returnDataType = IdHex(method.ReturnDataType),
            parameters = Variables(method.Parameters),
            variables = Variables(method.Variables),
            code = new
            {
                expressionLength = method.CodeData.ExpressionData?.Length ?? 0,
                expressionSha256 = HashOrEmpty(method.CodeData.ExpressionData),
                lineOffsetLength = method.CodeData.LineOffest?.Length ?? 0,
                blockOffsetLength = method.CodeData.BlockOffest?.Length ?? 0,
                methodReferenceLength = method.CodeData.MethodReference?.Length ?? 0,
                methodReferences = Int32Ids(method.CodeData.MethodReference),
                variableReferenceLength = method.CodeData.VariableReference?.Length ?? 0,
                variableReferences = Int32Ids(method.CodeData.VariableReference),
                constantReferenceLength = method.CodeData.ConstantReference?.Length ?? 0,
                constantReferences = Int32Ids(method.CodeData.ConstantReference),
            },
        }));

        var dependencyRanges = (dependencies?.ECDependencies ?? new List<ECDependencyInfo>())
            .SelectMany(dependency => dependency.DefinedIds ?? new List<ECDependencyInfo.PackedIds>())
            .ToArray();
        var appMethods = code.Methods.Where(method => !IsInDependencyRange(method.Id, dependencyRanges)).ToArray();
        WriteJson(Path.Combine(outputRoot, "app_calls.json"), appMethods.Select(method => new
        {
            id = IdHex(method.Id),
            classId = IdHex(method.Class),
            method.Name,
            calls = CollectCalls(method, nameMap).Select(call => new
            {
                libraryId = call.LibraryId,
                methodId = IdHex(call.MethodId),
                resolvedName = call.LibraryId == -2 || call.LibraryId == -3
                    ? nameMap.GetUserDefinedName(call.MethodId)
                    : nameMap.GetLibCmdName(call.LibraryId, call.MethodId),
                userDefined = call.LibraryId == -2,
                dllDeclare = call.LibraryId == -3,
                definitionPresent = call.LibraryId == -2 && methodsById.ContainsKey(call.MethodId),
                dependencyOwned = call.LibraryId == -2 && IsInDependencyRange(call.MethodId, dependencyRanges),
                invokeSpecial = call.InvokeSpecial,
            }),
        }));

        WriteJson(Path.Combine(outputRoot, "dll_declares.json"), code.DllDeclares.Select(item => new
        {
            id = IdHex(item.Id),
            item.Name,
            item.LibraryName,
            item.EntryPoint,
            item.Comment,
            item.Flags,
            item.Public,
            item.Hidden,
            returnDataType = IdHex(item.ReturnDataType),
            parameters = Variables(item.Parameters),
        }));

        WriteJson(Path.Combine(outputRoot, "forms.json"), resources.Forms.Select(form => new
        {
            id = IdHex(form.Id),
            classId = IdHex(form.Class),
            form.Name,
            form.Comment,
            elements = form.Elements.Select(ElementSummary),
        }));

        WriteJson(Path.Combine(outputRoot, "constants.json"), resources.Constants.Select(constant => new
        {
            id = IdHex(constant.Id),
            kind = ResourceKind(constant.Id),
            constant.Name,
            constant.Comment,
            constant.Flags,
            constant.Public,
            constant.Hidden,
            constant.LongText,
            valueType = constant.Value?.GetType().FullName ?? "null",
            value = ScalarConstantValue(constant.Value),
            byteLength = constant.Value is byte[] data ? data.Length : 0,
            sha256 = constant.Value is byte[] data2 ? Hex(SHA256.HashData(data2)) : null,
        }));

        WriteJson(Path.Combine(outputRoot, "resources_manifest.json"), resourceManifest);
        WriteJson(Path.Combine(outputRoot, "method_errors.json"), methodErrors);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            input = inputPath,
            output = outputRoot,
            sha256 = inputSha256,
            classes = code.Classes.Count,
            methods = code.Methods.Count,
            forms = resources.Forms.Count,
            constants = resources.Constants.Count,
            resourcesExtracted = resourceManifest.Count,
            methodParseErrors = methodErrors.Count,
            targetExecuted = false,
        }, JsonOptions));
        return 0;
    }

    private static void AppendHeader(StringBuilder target, string inputPath, string sha256,
        ESystemInfoSection system, ProjectConfigSection config, CodeSection code)
    {
        target.Append("' Safe EPL static extraction\n");
        target.Append($"' Input: {inputPath}\n");
        target.Append($"' SHA-256: {sha256}\n");
        target.Append("' Target and embedded resources were not executed.\n");
        target.Append("' Support-library names are intentionally unresolved and appear as _Lib* placeholders.\n");
        if (system != null)
        {
            target.Append($"' EPL: {system.ESystemVersion}; format: {system.EProjectFormatVersion}; language: {system.Language}\n");
        }
        if (config != null)
        {
            target.Append($"' Project: {config.Name}; version: {config.Version}\n");
        }
        target.Append($"' Libraries: {code.Libraries?.Length ?? 0}; classes: {code.Classes?.Count ?? 0}; methods: {code.Methods?.Count ?? 0}\n\n");
    }

    private static void AppendDefinitions<T>(StringBuilder target, IdToNameMap nameMap,
        IEnumerable<T> values, string title) where T : IToTextCodeAble
    {
        target.Append($"' ===== {title} =====\n");
        foreach (var value in values ?? Enumerable.Empty<T>())
        {
            AppendTextCode(target, writer => value.ToTextCode(nameMap, writer, 0), title);
            target.Append("\n");
        }
        target.Append("\n");
    }

    private static string RenderMethod(MethodInfo method, IdToNameMap nameMap, string failedRoot,
        List<object> errors)
    {
        var writer = new StringWriter(CultureInfo.InvariantCulture);
        try
        {
            method.ToTextCode(nameMap, writer, 0);
            return NormalizeLf(writer.ToString());
        }
        catch (Exception exception)
        {
            writer = new StringWriter(CultureInfo.InvariantCulture);
            try
            {
                method.ToTextCode(nameMap, writer, 0, false);
            }
            catch (Exception signatureException)
            {
                writer.Write($".子程序 {nameMap.GetUserDefinedName(method.Id)}");
                writer.WriteLine();
                writer.WriteLine($"' [safe-parser] 方法签名恢复失败: {signatureException.GetType().Name}");
            }
            var raw = method.CodeData.ExpressionData ?? Array.Empty<byte>();
            var rawPath = Path.Combine(failedRoot, $"M_{method.Id:X8}_{SafeFileName(method.Name)}.expression.bin");
            File.WriteAllBytes(rawPath, raw);
            writer.WriteLine();
            writer.WriteLine($"' [safe-parser] 方法体仅部分恢复: {exception.GetType().Name}: {SingleLine(exception.Message)}");
            writer.WriteLine($"' [safe-parser] 原始表达式: {Path.GetFileName(rawPath)}, {raw.Length} bytes, SHA-256={HashOrEmpty(raw)}");
            errors.Add(new
            {
                id = IdHex(method.Id),
                method.Name,
                errorType = exception.GetType().FullName,
                error = SingleLine(exception.Message),
                expressionLength = raw.Length,
                expressionSha256 = HashOrEmpty(raw),
                rawPath = rawPath.Replace('\\', '/'),
            });
            return NormalizeLf(writer.ToString());
        }
    }

    private static void AppendTextCode(StringBuilder target, Action<TextWriter> action, string context)
    {
        var writer = new StringWriter(CultureInfo.InvariantCulture);
        try
        {
            action(writer);
            target.Append(NormalizeLf(writer.ToString()));
        }
        catch (Exception exception)
        {
            target.Append($"' [safe-parser] {context} 输出失败: {exception.GetType().Name}: {SingleLine(exception.Message)}");
        }
    }

    private static IEnumerable<object> Variables(IEnumerable<AbstractVariableInfo> variables)
    {
        return (variables ?? Enumerable.Empty<AbstractVariableInfo>()).Select(variable => new
        {
            id = IdHex(variable.Id),
            variable.Name,
            variable.Comment,
            dataType = IdHex(variable.DataType),
            variable.Flags,
            upperBounds = variable.UBound,
        });
    }

    private static object ElementSummary(FormElementInfo element)
    {
        if (element is FormControlInfo control)
        {
            return new
            {
                kind = "control",
                id = IdHex(control.Id),
                dataType = IdHex(control.DataType),
                control.Name,
                control.Comment,
                control.Tag,
                control.Visible,
                control.Disable,
                control.TabStop,
                control.Locked,
                control.TabIndex,
                control.Left,
                control.Top,
                control.Width,
                control.Height,
                parent = IdHex(control.Parent),
                children = control.Children?.Select(IdHex),
                events = control.Events?.Select(item => new { eventId = item.Key, methodId = IdHex(item.Value) }),
                cursorLength = control.Cursor?.Length ?? 0,
                cursorSha256 = HashOrEmpty(control.Cursor),
                extensionLength = control.ExtensionData?.Length ?? 0,
                extensionSha256 = HashOrEmpty(control.ExtensionData),
            };
        }
        if (element is FormMenuInfo menu)
        {
            return new
            {
                kind = "menu",
                id = IdHex(menu.Id),
                dataType = IdHex(menu.DataType),
                menu.Name,
                menu.Text,
                menu.Visible,
                menu.Disable,
                menu.Selected,
                menu.HotKey,
                menu.Level,
                clickEvent = IdHex(menu.ClickEvent),
            };
        }
        return new
        {
            kind = element.GetType().FullName,
            id = IdHex(element.Id),
            dataType = IdHex(element.DataType),
            element.Name,
            element.Visible,
            element.Disable,
        };
    }

    private static string WriteBinaryResource(string resourceRoot, int id, string name, byte[] data)
    {
        var extension = DetectExtension(data);
        var path = Path.Combine(resourceRoot, $"R_{id:X8}_{SafeFileName(name)}{extension}");
        File.WriteAllBytes(path, data);
        return path;
    }

    private static string DetectExtension(byte[] data)
    {
        if (StartsWith(data, new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A })) return ".png";
        if (StartsWith(data, new byte[] { 0xFF, 0xD8, 0xFF })) return ".jpg";
        if (StartsWith(data, Encoding.ASCII.GetBytes("GIF87a")) || StartsWith(data, Encoding.ASCII.GetBytes("GIF89a"))) return ".gif";
        if (StartsWith(data, Encoding.ASCII.GetBytes("BM"))) return ".bmp";
        if (StartsWith(data, new byte[] { 0x00, 0x00, 0x01, 0x00 })) return ".ico";
        if (StartsWith(data, Encoding.ASCII.GetBytes("PK\x03\x04"))) return ".zip";
        if (StartsWith(data, Encoding.ASCII.GetBytes("Rar!\x1A\x07"))) return ".rar";
        if (StartsWith(data, new byte[] { 0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C })) return ".7z";
        if (StartsWith(data, Encoding.ASCII.GetBytes("MZ"))) return ".exe";
        if (StartsWith(data, Encoding.ASCII.GetBytes("RIFF")) && data.Length >= 12 && Encoding.ASCII.GetString(data, 8, 4) == "WAVE") return ".wav";
        if (StartsWith(data, Encoding.ASCII.GetBytes("ID3"))) return ".mp3";
        if (StartsWith(data, Encoding.ASCII.GetBytes("%PDF"))) return ".pdf";
        return ".bin";
    }

    private static bool StartsWith(byte[] data, byte[] prefix)
    {
        if (data == null || data.Length < prefix.Length) return false;
        for (var index = 0; index < prefix.Length; index++)
        {
            if (data[index] != prefix[index]) return false;
        }
        return true;
    }

    private static string SafeFileName(string value)
    {
        var source = string.IsNullOrWhiteSpace(value) ? "unnamed" : value.Trim();
        var invalid = Path.GetInvalidFileNameChars().Concat(new[] { '/', '\\' }).ToHashSet();
        var builder = new StringBuilder();
        foreach (var character in source)
        {
            builder.Append(invalid.Contains(character) || char.IsControl(character) ? '_' : character);
        }
        var result = builder.ToString().Trim(' ', '.');
        if (string.IsNullOrEmpty(result)) result = "unnamed";
        if (result.Length > 80) result = result.Substring(0, 80);
        return result;
    }

    private static string ResourceKind(int id)
    {
        return (unchecked((uint)id) >> 28) switch
        {
            1 => "constant",
            2 => "image",
            3 => "sound",
            _ => "unknown",
        };
    }

    private static object ScalarConstantValue(object value)
    {
        return value is byte[] ? null : value;
    }

    private static string RelativeUnix(string root, string path)
    {
        return Path.GetRelativePath(root, path).Replace('\\', '/');
    }

    private static void WriteJson(string path, object value)
    {
        WriteUtf8Lf(path, JsonSerializer.Serialize(value, JsonOptions) + "\n");
    }

    private static void WriteUtf8Lf(string path, string value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, NormalizeLf(value), new UTF8Encoding(false));
    }

    private static string NormalizeLf(string value)
    {
        return (value ?? string.Empty).Replace("\r\n", "\n").Replace("\r", "\n");
    }

    private static string SingleLine(string value)
    {
        return NormalizeLf(value).Replace("\n", " ").Trim();
    }

    private static string IdHex(int value) => $"0x{unchecked((uint)value):X8}";

    private static IEnumerable<string> Int32Ids(byte[] data)
    {
        if (data == null || data.Length < 4) return Array.Empty<string>();
        var count = data.Length / 4;
        var result = new string[count];
        for (var index = 0; index < count; index++)
        {
            result[index] = IdHex(BitConverter.ToInt32(data, index * 4));
        }
        return result;
    }

    private static bool IsInDependencyRange(int id, IEnumerable<ECDependencyInfo.PackedIds> ranges)
    {
        var value = unchecked((uint)id);
        foreach (var range in ranges)
        {
            var start = unchecked((uint)range.Start);
            if (value >= start && value < start + unchecked((uint)range.Count)) return true;
        }
        return false;
    }

    private static IEnumerable<CallExpression> CollectCalls(MethodInfo method, IdToNameMap nameMap)
    {
        object root;
        try
        {
            root = CodeDataParser.ParseStatementBlock(method.CodeData.ExpressionData, method.CodeData.Encoding);
        }
        catch
        {
            return Array.Empty<CallExpression>();
        }

        var calls = new List<CallExpression>();
        var visited = new HashSet<object>(ReferenceEqualityComparer.Instance);
        WalkObjectGraph(root, visited, calls);
        return calls;
    }

    private static void WalkObjectGraph(object value, HashSet<object> visited, List<CallExpression> calls)
    {
        if (value == null) return;
        var type = value.GetType();
        if (type.IsPrimitive || type.IsEnum || value is string || value is decimal || value is DateTime || value is byte[]) return;
        if (!type.IsValueType && !visited.Add(value)) return;

        if (value is CallExpression call) calls.Add(call);
        if (value is IEnumerable enumerable)
        {
            foreach (var item in enumerable) WalkObjectGraph(item, visited, calls);
        }

        if (type.Namespace == null || !type.Namespace.StartsWith("QIQI.EProjectFile", StringComparison.Ordinal)) return;
        foreach (var property in type.GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
        {
            if (!property.CanRead || property.GetIndexParameters().Length != 0) continue;
            try { WalkObjectGraph(property.GetValue(value), visited, calls); } catch { }
        }
        foreach (var field in type.GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
        {
            try { WalkObjectGraph(field.GetValue(value), visited, calls); } catch { }
        }
    }

    private static string HashOrEmpty(byte[] data)
    {
        return data == null || data.Length == 0 ? Hex(SHA256.HashData(Array.Empty<byte>())) : Hex(SHA256.HashData(data));
    }

    private static string Hex(byte[] data)
    {
        return Convert.ToHexString(data).ToLowerInvariant();
    }
}
